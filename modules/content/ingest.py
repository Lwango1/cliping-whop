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
        from playwright.async_api import async_playwright
        from urllib.parse import parse_qs

        suffix = int(time.time())
        output_path = output_dir / f"clip_{suffix}.mp4"

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox", "--disable-blink-features=AutomationControlled"]
                )
                ctx = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )
                await ctx.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                """)
                page = await ctx.new_page()
                await page.goto(query, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(8000)

                player_data = await page.evaluate("""() => {
                    try { return ytInitialPlayerResponse; } catch(e) { return null; }
                }""")
                await browser.close()

            if not player_data:
                return "No player data found on page"

            playability = player_data.get("playabilityStatus", {})
            if playability.get("status") != "OK":
                reason = playability.get("reason", playability.get("status", "unknown"))
                return f"Video not playable: {reason}"

            streaming = player_data.get("streamingData")
            if not streaming:
                return f"No streaming data (playability: {playability.get('status', '?')} - {playability.get('reason', 'no reason')})"

            formats = streaming.get("formats") or []
            adaptive = streaming.get("adaptiveFormats") or []

            dl_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://www.youtube.com/",
            }

            def get_url(fmt):
                url = fmt.get("url")
                if url:
                    return url
                cipher = fmt.get("signatureCipher") or fmt.get("cipher", "")
                if cipher:
                    qs = parse_qs(cipher)
                    return qs.get("url", [None])[0]
                return None

            chosen = None
            for fmt in formats:
                url = get_url(fmt)
                if url and fmt.get("height", 0) <= 720:
                    if not chosen or fmt.get("height", 0) > chosen.get("height", 0):
                        fmt["_url"] = url
                        chosen = fmt

            if not chosen and adaptive:
                videos = [f for f in adaptive if get_url(f) and f.get("mimeType", "").startswith("video/") and f.get("height", 0) <= 720]
                for f in videos:
                    f["_url"] = get_url(f)
                audios = [f for f in adaptive if get_url(f) and f.get("mimeType", "").startswith("audio/")]
                for f in audios:
                    f["_url"] = get_url(f)
                bv = max(videos, key=lambda f: f.get("height", 0)) if videos else None
                ba = max(audios, key=lambda f: f.get("bitrate", 0)) if audios else None
                if bv and ba:
                    from utils import get_ffmpeg_path
                    ffmpeg = get_ffmpeg_path()
                    vp = output_dir / f"clip_{suffix}_v.mp4"
                    ap = output_dir / f"clip_{suffix}_a.m4a"
                    vr = await asyncio.to_thread(requests.get, bv["_url"], headers=dl_headers, timeout=120)
                    with open(vp, "wb") as f:
                        f.write(vr.content)
                    ar = await asyncio.to_thread(requests.get, ba["_url"], headers=dl_headers, timeout=120)
                    with open(ap, "wb") as f:
                        f.write(ar.content)
                    import subprocess
                    await asyncio.to_thread(subprocess.run, [ffmpeg, "-y", "-i", str(vp), "-i", str(ap), "-c", "copy", str(output_path)], capture_output=True, timeout=120)
                    vp.unlink(missing_ok=True)
                    ap.unlink(missing_ok=True)
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
