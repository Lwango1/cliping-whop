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
    def get_youtube_cookies(target_url: str = "") -> Optional[str]:
        cookie_path = str(RAW_DIR / "yt_cookies.txt")
        if Path(cookie_path).exists() and time.time() - Path(cookie_path).stat().st_mtime < 1800:
            return cookie_path
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                )
                page = ctx.new_page()
                url_to_visit = target_url if target_url.startswith("http") else "https://www.youtube.com"
                page.goto(url_to_visit, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(8000)
                cookies = ctx.cookies()
                browser.close()
            with open(cookie_path, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                for c in cookies:
                    domain = (c.get("domain", "") or "").lstrip(".")
                    if domain and domain.startswith("."):
                        domain = domain[1:]
                    flag = "TRUE" if c.get("domain", "").startswith(".") else "FALSE"
                    secure = "TRUE" if c.get("secure", False) else "FALSE"
                    f.write(f"{domain}\t{flag}\t{c.get('path','/')}\t{secure}\t{int(c.get('expires',0))}\t{c.get('name','')}\t{c.get('value','')}\n")
            print(f"[Ingest] YouTube cookies saved ({len(cookies)} cookies, via {url_to_visit})")
            return cookie_path
        except Exception as e:
            print(f"[Ingest] Cookie fetch failed: {e}")
            return None

    @staticmethod
    def download_youtube_replay(query: str, max_duration: int = 300, output_dir: Optional[Path] = None):
        output_dir = output_dir or RAW_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        is_url = query.startswith("http://") or query.startswith("https://")

        try:
            import yt_dlp
            from utils import get_ffmpeg_path

            suffix = int(time.time())
            output_template = str(output_dir / f"clip_{suffix}.%(ext)s")

            ydl_opts = {
                "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "outtmpl": output_template,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "ffmpeg_location": get_ffmpeg_path(),
                "merge_output_format": "mp4",
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-us,en;q=0.5",
                    "Sec-Fetch-Mode": "navigate",
                },
                "geo_bypass": True,
                "sleep_interval": 3,
                "sleep_interval_requests": 1,
                "throttled_rate": "500K",
            }

            cookie_file = ContentIngestor.get_youtube_cookies(query if is_url else "")
            if cookie_file:
                ydl_opts["cookiefile"] = cookie_file

            if is_url:
                url = query
            else:
                ydl_opts["match_filter"] = yt_dlp.utils.match_filter_func(f"duration < {max_duration}")
                url = f"ytsearch1:{query} World Cup 2026 highlights"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    print("[Ingest] yt-dlp returned no info")
                    return None

                # Find the downloaded file
                for f in output_dir.glob(f"clip_{suffix}.*"):
                    if f.suffix.lower() in (".mp4", ".webm", ".mkv", ".m4a") and f.stat().st_size > 100000:
                        print(f"[Ingest] Downloaded: {f.name}")
                        return f

                # Fallback: most recent file in output_dir
                recent = sorted(output_dir.glob("*.*"), key=lambda x: x.stat().st_mtime, reverse=True)
                for f in recent:
                    if f.suffix.lower() in (".mp4", ".webm", ".mkv", ".m4a") and f.stat().st_size > 100000:
                        age = time.time() - f.stat().st_mtime
                        if age < 60:
                            print(f"[Ingest] Downloaded (recent): {f.name}")
                            return f

                print(f"[Ingest] File not found after download (suffix={suffix})")
                return None

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
