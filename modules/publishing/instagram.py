import time
import random
from pathlib import Path
from typing import Optional

import requests

from config import InstagramConfig, LOGS_DIR


class InstagramPublisher:
    BASE_URL = "https://www.instagram.com"
    GRAPHQL_URL = "https://www.instagram.com/graphql/query"

    def __init__(self, ig_cfg: InstagramConfig):
        self.cfg = ig_cfg
        self.session = requests.Session()
        self.csrf_token = ""
        self.logged_in = False
        self.user_id = ""

    def login(self) -> bool:
        if not self.cfg.username or not self.cfg.password:
            print("[Instagram] Missing username/password")
            return False

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/",
        })

        try:
            resp = self.session.get(f"{self.BASE_URL}/api/v1/web/accounts/login/", timeout=15)
            self.csrf_token = self.session.cookies.get("csrftoken", "")

            login_data = {
                "username": self.cfg.username,
                "password": self.cfg.password,
                "queryParams": "{}",
                "optIntoOneTap": "false",
                "stopDeletionNonce": "",
                "trustedDeviceRecords": "{}",
            }
            headers = {"X-CSRFToken": self.csrf_token}
            resp = self.session.post(
                f"{self.BASE_URL}/api/v1/web/accounts/login/ajax/",
                data=login_data,
                headers=headers,
                timeout=15,
            )
            result = resp.json()

            if result.get("authenticated"):
                self.logged_in = True
                self.user_id = result.get("userId", "")
                print(f"[Instagram] Logged in as {self.cfg.username}")
                return True
            else:
                print(f"[Instagram] Login failed: {result}")
                return False

        except Exception as e:
            print(f"[Instagram] Login error: {e}")
            return False

    def upload_reel(self, video_path: Path, caption: str, hashtags: list[str] = None) -> bool:
        if not self.logged_in and not self.login():
            return False

        if not video_path.exists():
            print(f"[Instagram] File not found: {video_path}")
            return False

        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(hashtags)

        try:
            upload_url = f"{self.BASE_URL}/api/v1/media/upload_reel/"
            headers = {"X-CSRFToken": self.csrf_token}
            with open(video_path, "rb") as f:
                files = {"video": (video_path.name, f, "video/mp4")}
                data = {"caption": full_caption}
                resp = self.session.post(upload_url, files=files, data=data, headers=headers, timeout=300)

            if resp.ok:
                with open(LOGS_DIR / "instagram_posts.log", "a", encoding="utf-8") as log:
                    log.write(f"[{time.ctime()}] Published reel: {video_path.name} | {caption[:50]}...\n")
                print(f"[Instagram] Reel published: {caption[:50]}...")
                return True
            else:
                print(f"[Instagram] Upload failed: {resp.status_code} {resp.text[:200]}")
                return False

        except Exception as e:
            print(f"[Instagram] Upload error: {e}")
            return False

    def upload_photo(self, image_path: Path, caption: str, hashtags: list[str] = None) -> bool:
        if not self.logged_in and not self.login():
            return False

        if not image_path.exists():
            print(f"[Instagram] File not found: {image_path}")
            return False

        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(hashtags)

        try:
            upload_url = f"{self.BASE_URL}/api/v1/media/upload_photo/"
            headers = {"X-CSRFToken": self.csrf_token}
            with open(image_path, "rb") as f:
                files = {"photo": (image_path.name, f, "image/jpeg")}
                data = {"caption": full_caption}
                resp = self.session.post(upload_url, files=files, data=data, headers=headers, timeout=120)

            if resp.ok:
                print(f"[Instagram] Photo published: {caption[:50]}...")
                return True
            else:
                print(f"[Instagram] Photo upload failed: {resp.status_code}")
                return False

        except Exception as e:
            print(f"[Instagram] Photo error: {e}")
            return False
