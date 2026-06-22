import json
import os
from pathlib import Path
from pydantic import BaseModel
from typing import Optional


ROOT_DIR = Path(__file__).parent
CONFIG_FILE = ROOT_DIR / "config.json"
STORAGE_DIR = ROOT_DIR / "storage"
RAW_DIR = STORAGE_DIR / "raw"
PROCESSED_DIR = STORAGE_DIR / "processed"
ASSETS_DIR = ROOT_DIR / "assets"
LOGS_DIR = ROOT_DIR / "logs"


class TikTokConfig(BaseModel):
    session_id: str = ""
    csrf_token: str = ""


class YouTubeConfig(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""


class InstagramConfig(BaseModel):
    username: str = ""
    password: str = ""


class FacebookConfig(BaseModel):
    page_id: str = ""
    access_token: str = ""


class WhopConfig(BaseModel):
    email: str = ""
    password: str = ""
    cookie_file: str = ""


class UserConfig(BaseModel):
    whop: WhopConfig = WhopConfig()
    tiktok: TikTokConfig = TikTokConfig()
    youtube: YouTubeConfig = YouTubeConfig()
    instagram: InstagramConfig = InstagramConfig()
    facebook: FacebookConfig = FacebookConfig()
    posts_per_day: int = 3
    preferred_hours: list[int] = [10, 14, 18, 21]
    campaign_keywords: list[str] = ["world cup", "sports", "canada", "football"]
    content_sources: list[str] = ["youtube_replays", "sports_api"]
    target_language: str = "fr"
    locale: str = "en-CA"


class AppConfig(BaseModel):
    users: dict[str, UserConfig] = {}
    active_user: Optional[str] = None
    max_concurrent_posts: int = 2
    headless_browser: bool = True
    content_cache_ttl_hours: int = 48


def load_config() -> AppConfig:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppConfig.model_validate(data)
    return AppConfig()


def save_config(cfg: AppConfig):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(mode="json"), f, indent=2)


def init_user_interactive():
    cfg = load_config()
    print("=== Betway Clipper - First Time Setup ===\n")

    username = input("Choose a username: ").strip()
    if username in cfg.users:
        print(f"User '{username}' already exists. Loading config.")
        cfg.active_user = username
        save_config(cfg)
        return username

    print("\n--- Whop Account ---")
    whop_email = input("Whop email: ").strip()
    whop_password = input("Whop password: ").strip()

    print("\n--- TikTok (optional) ---")
    tiktok_session = input("TikTok session_id (press Enter to skip): ").strip()

    print("\n--- YouTube (optional) ---")
    yt_client_id = input("YouTube client_id (press Enter to skip): ").strip()

    print("\n--- Instagram (optional) ---")
    ig_username = input("Instagram username (press Enter to skip): ").strip()
    ig_password = input("Instagram password (press Enter to skip): ").strip()

    print("\n--- Facebook (optional) ---")
    fb_page_id = input("Facebook page_id (press Enter to skip): ").strip()
    fb_token = input("Facebook access_token (press Enter to skip): ").strip()

    print("\n--- Language ---")
    from modules.content.translator import LANGUAGE_NAMES, SUPPORTED_LANGUAGES
    print("Available languages:")
    for code in SUPPORTED_LANGUAGES:
        print(f"  {code}: {LANGUAGE_NAMES[code]}")
    lang = input(f"Target language [fr]: ").strip().lower() or "fr"
    if lang not in SUPPORTED_LANGUAGES:
        print(f"'{lang}' not supported, using English.")
        lang = "en"

    user_cfg = UserConfig(
        whop=WhopConfig(email=whop_email, password=whop_password),
        tiktok=TikTokConfig(session_id=tiktok_session),
        youtube=YouTubeConfig(client_id=yt_client_id),
        instagram=InstagramConfig(username=ig_username, password=ig_password),
        facebook=FacebookConfig(page_id=fb_page_id, access_token=fb_token),
        target_language=lang,
    )

    cfg.users[username] = user_cfg
    cfg.active_user = username
    save_config(cfg)
    print(f"\n User '{username}' saved successfully!")
    return username
