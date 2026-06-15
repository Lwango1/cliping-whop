import json
import time
import requests
from pathlib import Path
from typing import Optional

from config import RAW_DIR
from utils import init_output

init_output()


SPORTS_API_URL = "https://www.thesportsdb.com/api/v1/json/3"
RECENT_EVENTS_ENDPOINT = f"{SPORTS_API_URL}/eventslast.php"
SEARCH_EVENTS_ENDPOINT = f"{SPORTS_API_URL}/searchevents.php"
SEARCH_TEAMS_ENDPOINT = f"{SPORTS_API_URL}/searchteams.php"

TEAM_IDS = {
    "canada": 140073,
    "brazil": 140077,
    "argentina": 140075,
    "france": 140081,
    "germany": 140083,
    "england": 140088,
    "portugal": 140085,
    "netherlands": 140087,
    "spain": 140082,
}


class ContentIngestor:

    @staticmethod
    def fetch_sports_events(team: str = "canada", limit: int = 5) -> list[dict]:
        try:
            team_id = TEAM_IDS.get(team.lower())
            if not team_id:
                resp = requests.get(SEARCH_TEAMS_ENDPOINT, params={"t": team}, timeout=15)
                data = resp.json()
                if data.get("teams"):
                    team_id = data["teams"][0]["idTeam"]

            if not team_id:
                print(f"[Ingest] Team '{team}' not found")
                return []

            resp = requests.get(RECENT_EVENTS_ENDPOINT, params={"id": team_id}, timeout=15)
            data = resp.json()
            events = data.get("results", [])[:limit]

            results = []
            for ev in events:
                results.append({
                    "id": ev.get("idEvent"),
                    "name": ev.get("strEvent"),
                    "league": ev.get("strLeague"),
                    "home_team": ev.get("strHomeTeam"),
                    "away_team": ev.get("strAwayTeam"),
                    "date": ev.get("dateEvent"),
                    "home_score": ev.get("intHomeScore"),
                    "away_score": ev.get("intAwayScore"),
                    "thumb": ev.get("strThumb"),
                    "video": ev.get("strVideo"),
                    "description": ev.get("strDescriptionEN", "")[:500],
                    "source": "thesportsdb",
                })

            return results

        except Exception as e:
            print(f"[Ingest] Sports API error: {e}")
            return []

    @staticmethod
    def search_sports_events(query: str, limit: int = 5) -> list[dict]:
        try:
            resp = requests.get(SEARCH_EVENTS_ENDPOINT, params={"e": query}, timeout=15)
            data = resp.json()
            events = data.get("event", [])[:limit]

            results = []
            for ev in events:
                results.append({
                    "id": ev.get("idEvent"),
                    "name": ev.get("strEvent"),
                    "league": ev.get("strLeague"),
                    "home_team": ev.get("strHomeTeam"),
                    "away_team": ev.get("strAwayTeam"),
                    "date": ev.get("dateEvent"),
                    "home_score": ev.get("intHomeScore"),
                    "away_score": ev.get("intAwayScore"),
                    "source": "thesportsdb",
                })

            return results

        except Exception as e:
            print(f"[Ingest] Search error: {e}")
            return []

    @staticmethod
    async def download_youtube_replay(query: str, max_duration: int = 300, output_dir: Optional[Path] = None):
        output_dir = output_dir or RAW_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        is_url = query.startswith("http://") or query.startswith("https://")
        if not is_url:
            return "Only direct YouTube URLs are supported"

        import re
        match = re.search(r"(?:v=|/v/|youtu\.be/|/shorts/)([a-zA-Z0-9_-]{11})", query)
        if not match:
            return "Could not extract video ID from URL"
        video_id = match.group(1)

        import asyncio
        suffix = int(time.time())
        output_path = output_dir / f"clip_{suffix}.mp4"

        try:
            # Load cookies from file
            cookie_file = Path(__file__).parent.parent / "youtube_cookies.txt"
            if not cookie_file.exists():
                return "Cookies file not found"

            import http.cookiejar
            cj = http.cookiejar.MozillaCookieJar(str(cookie_file))
            cj.load()

            sess = requests.Session()
            sess.cookies = cj
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            })

            # First visit YouTube (refreshes cookies)
            await asyncio.to_thread(sess.get, "https://www.youtube.com", timeout=15)

            # Call YouTube internal API with cookies
            body = {
                "videoId": video_id,
                "context": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": "2.20250101.00.00",
                        "hl": "en",
                        "gl": "US",
                    }
                }
            }
            api_url = "https://www.youtube.com/youtubei/v1/player?key=AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
            resp = await asyncio.to_thread(sess.post, api_url, json=body, timeout=30)

            if resp.status_code != 200:
                # Fallback to yt-dlp
                print(f"[Ingest] API {resp.status_code}, falling back to yt-dlp")
                return await ContentIngestor._ytdlp_download(query, cookie_file, output_path, output_dir, suffix)

            data = resp.json()
            playability = data.get("playabilityStatus", {})
            if playability.get("status") != "OK":
                reason = playability.get("reason", playability.get("status", "unknown"))
                print(f"[Ingest] API playability: {reason}, falling back to yt-dlp")
                return await ContentIngestor._ytdlp_download(query, cookie_file, output_path, output_dir, suffix)

            streaming = data.get("streamingData")
            if not streaming:
                print(f"[Ingest] No streaming data, falling back to yt-dlp")
                return await ContentIngestor._ytdlp_download(query, cookie_file, output_path, output_dir, suffix)

            formats = streaming.get("formats") or []
            adaptive = streaming.get("adaptiveFormats") or []

            from urllib.parse import parse_qs
            def get_url(fmt):
                u = fmt.get("url")
                if u:
                    return u
                c = fmt.get("signatureCipher") or fmt.get("cipher", "")
                if c:
                    return parse_qs(c).get("url", [None])[0]
                return None

            chosen = None
            for f in formats:
                u = get_url(f)
                if u and f.get("height", 0) <= 720:
                    if not chosen or f["height"] > chosen["height"]:
                        f["_url"] = u
                        chosen = f

            if not chosen and adaptive:
                vids = [f for f in adaptive if get_url(f) and f.get("mimeType","").startswith("video/") and f.get("height",0) <= 720]
                for f in vids:
                    f["_url"] = get_url(f)
                auds = [f for f in adaptive if get_url(f) and f.get("mimeType","").startswith("audio/")]
                for f in auds:
                    f["_url"] = get_url(f)
                bv = max(vids, key=lambda f: f["height"]) if vids else None
                ba = max(auds, key=lambda f: f.get("bitrate",0)) if auds else None
                if bv and ba:
                    from utils import get_ffmpeg_path
                    ff = get_ffmpeg_path()
                    vp = output_dir / f"clip_{suffix}_v.mp4"
                    ap = output_dir / f"clip_{suffix}_a.m4a"
                    vr = await asyncio.to_thread(sess.get, bv["_url"], timeout=120)
                    with open(vp, "wb") as f:
                        f.write(vr.content)
                    ar = await asyncio.to_thread(sess.get, ba["_url"], timeout=120)
                    with open(ap, "wb") as f:
                        f.write(ar.content)
                    import subprocess
                    await asyncio.to_thread(subprocess.run, [ff, "-y", "-i", str(vp), "-i", str(ap), "-c", "copy", str(output_path)], capture_output=True, timeout=120)
                    vp.unlink(missing_ok=True)
                    ap.unlink(missing_ok=True)
                    if output_path.exists() and output_path.stat().st_size > 100000:
                        print(f"[Ingest] Downloaded (adaptive): {output_path.name}")
                        return output_path
                    output_path.unlink(missing_ok=True)
                    return "Failed to mux adaptive formats"

            if not chosen:
                return "No downloadable format found"

            resp = await asyncio.to_thread(sess.get, chosen["_url"], timeout=300)
            with open(output_path, "wb") as f:
                f.write(resp.content)

            if output_path.exists() and output_path.stat().st_size > 100000:
                print(f"[Ingest] Downloaded: {output_path.name}")
                return output_path
            return "Downloaded file too small"

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Ingest] Download failed: {e}\n{tb}")
            err = str(e)
            if len(err) > 300:
                err = err[:300]
            return f"Download failed: {err}"

    @staticmethod
    async def _ytdlp_download(query, cookie_file, output_path, output_dir, suffix):
        try:
            import asyncio, yt_dlp
            from utils import get_ffmpeg_path

            ydl_opts = {
                "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "outtmpl": str(output_path),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "ffmpeg_location": get_ffmpeg_path(),
                "merge_output_format": "mp4",
                "cookiefile": str(cookie_file),
                "geo_bypass": True,
                "geo_bypass_country": "US",
                "throttled_rate": "500K",
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios", "web_embedded", "android_embedded"],
                        "skip": ["webpage", "dash", "hls"],
                    }
                },
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            }

            def _run():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(query, download=True)

            result = await asyncio.to_thread(_run)
            if not result:
                return "yt-dlp returned no data"

            if output_path.exists() and output_path.stat().st_size > 100000:
                return output_path
            for f in sorted(output_dir.glob(f"clip_{suffix}.*"), key=lambda x: x.stat().st_size, reverse=True):
                if f.stat().st_size > 100000:
                    return f
            return "Downloaded file not found"

        except Exception as e:
            return f"yt-dlp fallback failed: {str(e)[:200]}"

    @staticmethod
    def cache_event_data(events: list[dict], cache_file: str = "events_cache.json"):
        cache_path = RAW_DIR / cache_file
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"events": events, "cached_at": time.time()}, f, indent=2)

    @staticmethod
    def load_cached_events(cache_file: str = "events_cache.json", max_age_hours: int = 48) -> list[dict]:
        cache_path = RAW_DIR / cache_file
        if not cache_path.exists():
            return []

        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        age = time.time() - data.get("cached_at", 0)
        if age > max_age_hours * 3600:
            return []

        return data.get("events", [])
