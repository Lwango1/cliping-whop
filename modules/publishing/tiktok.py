import json
import time
import random
from pathlib import Path
from typing import Optional

import requests

from config import TikTokConfig, LOGS_DIR


class TikTokPublisher:
    BASE_URL = "https://www.tiktok.com"

    def __init__(self, tiktok_cfg: TikTokConfig):
        self.cfg = tiktok_cfg
        self.session = requests.Session()
        self.logged_in = False

    def login_via_session(self) -> bool:
        if not self.cfg.session_id:
            print("[TikTok] No session_id configured")
            return False

        self.session.cookies.set("sessionid", self.cfg.session_id, domain=".tiktok.com")
        if self.cfg.csrf_token:
            self.session.cookies.set("csrf_session_id", self.cfg.csrf_token, domain=".tiktok.com")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tiktok.com/",
        })

        try:
            resp = self.session.get(f"{self.BASE_URL}/", timeout=15)
            self.logged_in = resp.ok
            return self.logged_in
        except Exception as e:
            print(f"[TikTok] Login error: {e}")
            return False

    def upload_video(self, video_path: Path, caption: str, hashtags: list[str] = None) -> bool:
        if not self.logged_in and not self.login_via_session():
            return False

        if not video_path.exists():
            print(f"[TikTok] File not found: {video_path}")
            return False

        full_caption = caption
        if hashtags:
            full_caption += " " + " ".join(hashtags)

        try:
            upload_url = f"{self.BASE_URL}/api/v1/video/upload/"
            with open(video_path, "rb") as f:
                files = {"video": (video_path.name, f, "video/mp4")}
                data = {"description": full_caption}
                resp = self.session.post(upload_url, files=files, data=data, timeout=300)

            if resp.ok:
                with open(LOGS_DIR / "tiktok_posts.log", "a", encoding="utf-8") as log:
                    log.write(f"[{time.ctime()}] Published: {video_path.name} | {full_caption[:50]}...\n")
                print(f"[TikTok] Published: {video_path.name}")
                return True
            else:
                print(f"[TikTok] Upload failed: {resp.status_code} {resp.text[:200]}")
                return False

        except Exception as e:
            print(f"[TikTok] Upload error: {e}")
            return False

    def upload_photo_slideshow(self, image_paths: list[Path], caption: str, hashtags: list[str] = None) -> bool:
        if not self.logged_in and not self.login_via_session():
            return False

        full_caption = caption
        if hashtags:
            full_caption += " " + " ".join(hashtags)

        try:
            upload_url = f"{self.BASE_URL}/api/v1/video/upload/"
            files = []
            for img in image_paths:
                if img.exists():
                    files.append(("images", (img.name, open(img, "rb"), "image/jpeg")))

            if not files:
                return False

            data = {"description": full_caption, "slideshow": "1"}
            resp = self.session.post(upload_url, files=files, data=data, timeout=300)

            for _, f in files:
                f[1].close()

            if resp.ok:
                print(f"[TikTok] Slideshow published: {caption[:50]}...")
                return True
            else:
                print(f"[TikTok] Slideshow failed: {resp.status_code}")
                return False

        except Exception as e:
            print(f"[TikTok] Slideshow error: {e}")
            return False
