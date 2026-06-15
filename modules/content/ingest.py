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
    def _get_format_url(fmt: dict) -> Optional[str]:
        url = fmt.get("url")
        if url:
            return url
        cipher = fmt.get("signatureCipher") or fmt.get("cipher", "")
        if cipher:
            import urllib.parse
            parsed = urllib.parse.parse_qs(cipher)
            if parsed.get("url"):
                return parsed["url"][0]
        return None

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

        try:
            suffix = int(time.time())
            output_path = output_dir / f"clip_{suffix}.mp4"

            # YouTube internal web API (same endpoint the website uses)
            import asyncio
            api_key = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
            api_url = f"https://www.youtube.com/youtubei/v1/player?key={api_key}"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Origin": "https://www.youtube.com",
                "Referer": f"https://www.youtube.com/watch?v={video_id}",
                "Accept-Language": "en-US,en;q=0.9",
            }
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

            resp = await asyncio.to_thread(requests.post, api_url, json=body, headers=headers, timeout=30)
            if resp.status_code != 200:
                return f"YouTube API returned status {resp.status_code}"

            player_data = resp.json()

            playback = player_data.get("playabilityStatus", {})
            if playback.get("status") != "OK":
                reason = playback.get("reason", playback.get("status", "unknown"))
                return f"Video not playable: {reason}"

            streaming = player_data.get("streamingData")
            if not streaming:
                return "No streaming data in API response"

            formats = streaming.get("formats") or []
            adaptive = streaming.get("adaptiveFormats") or []

            dl_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://www.youtube.com/",
            }

            # Find best muxed format (has both video+audio) with resolvable URL
            chosen = None
            for fmt in formats:
                url = ContentIngestor._get_format_url(fmt)
                if url and fmt.get("height", 0) <= 720:
                    if not chosen or fmt.get("height", 0) > chosen.get("height", 0):
                        fmt["_url"] = url
                        chosen = fmt

            if not chosen and adaptive:
                videos = []
                for f in adaptive:
                    url = ContentIngestor._get_format_url(f)
                    if url and f.get("mimeType", "").startswith("video/") and f.get("height", 0) <= 720:
                        f["_url"] = url
                        videos.append(f)
                audios = []
                for f in adaptive:
                    url = ContentIngestor._get_format_url(f)
                    if url and f.get("mimeType", "").startswith("audio/"):
                        f["_url"] = url
                        audios.append(f)
                best_v = max(videos, key=lambda f: f.get("height", 0)) if videos else None
                best_a = max(audios, key=lambda f: f.get("bitrate", 0)) if audios else None
                if best_v and best_a:
                    from utils import get_ffmpeg_path
                    import asyncio, subprocess
                    ffmpeg = get_ffmpeg_path()
                    vid_path = output_dir / f"clip_{suffix}_v.mp4"
                    aud_path = output_dir / f"clip_{suffix}_a.m4a"
                    vresp = await asyncio.to_thread(requests.get, best_v["_url"], headers=dl_headers, timeout=120)
                    with open(vid_path, "wb") as f:
                        f.write(vresp.content)
                    aresp = await asyncio.to_thread(requests.get, best_a["_url"], headers=dl_headers, timeout=120)
                    with open(aud_path, "wb") as f:
                        f.write(aresp.content)
                    await asyncio.to_thread(subprocess.run, [ffmpeg, "-y", "-i", str(vid_path), "-i", str(aud_path), "-c", "copy", str(output_path)], capture_output=True, timeout=120)
                    vid_path.unlink(missing_ok=True)
                    aud_path.unlink(missing_ok=True)
                    if output_path.exists() and output_path.stat().st_size > 100000:
                        print(f"[Ingest] Downloaded (adaptive): {output_path.name}")
                        return output_path
                    output_path.unlink(missing_ok=True)
                    return "Failed to mux adaptive formats"

            if not chosen:
                return "No downloadable format found"

            resp = await asyncio.to_thread(requests.get, chosen["_url"], headers=dl_headers, timeout=300)
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
            return f"Download failed: {e}"

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
