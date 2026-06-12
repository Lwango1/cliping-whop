import time
import random
from pathlib import Path
from typing import Optional

import requests

from config import FacebookConfig, LOGS_DIR


class FacebookPublisher:
    GRAPH_API_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, fb_cfg: FacebookConfig):
        self.cfg = fb_cfg
        self.logged_in = False

    def login(self) -> bool:
        if not self.cfg.page_id or not self.cfg.access_token:
            print("[Facebook] Missing page_id or access_token")
            return False

        try:
            resp = requests.get(
                f"{self.GRAPH_API_URL}/{self.cfg.page_id}",
                params={"access_token": self.cfg.access_token, "fields": "id,name"},
                timeout=15,
            )
            if resp.ok:
                self.logged_in = True
                print(f"[Facebook] Connected to page: {resp.json().get('name')}")
                return True
            else:
                print(f"[Facebook] Auth failed: {resp.text[:200]}")
                return False

        except Exception as e:
            print(f"[Facebook] Login error: {e}")
            return False

    def upload_video(self, video_path: Path, title: str, description: str, hashtags: list[str] = None) -> bool:
        if not self.logged_in and not self.login():
            return False

        if not video_path.exists():
            print(f"[Facebook] File not found: {video_path}")
            return False

        full_desc = description
        if hashtags:
            full_desc += "\n\n" + " ".join(hashtags)

        try:
            url = f"{self.GRAPH_API_URL}/{self.cfg.page_id}/videos"
            params = {
                "access_token": self.cfg.access_token,
                "title": title[:100],
                "description": full_desc[:5000],
            }

            with open(video_path, "rb") as f:
                files = {"source": (video_path.name, f, "video/mp4")}
                resp = requests.post(url, params=params, files=files, timeout=600)

            if resp.ok:
                video_id = resp.json().get("id", "unknown")
                with open(LOGS_DIR / "facebook_posts.log", "a", encoding="utf-8") as log:
                    log.write(f"[{time.ctime()}] Published video: {video_id} | {title}\n")
                print(f"[Facebook] Video published (id: {video_id})")
                return True
            else:
                print(f"[Facebook] Upload failed: {resp.status_code} {resp.text[:200]}")
                return False

        except Exception as e:
            print(f"[Facebook] Upload error: {e}")
            return False

    def upload_photo(self, image_path: Path, caption: str, hashtags: list[str] = None) -> bool:
        if not self.logged_in and not self.login():
            return False

        if not image_path.exists():
            print(f"[Facebook] File not found: {image_path}")
            return False

        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(hashtags)

        try:
            url = f"{self.GRAPH_API_URL}/{self.cfg.page_id}/photos"
            params = {"access_token": self.cfg.access_token, "message": full_caption[:5000]}

            with open(image_path, "rb") as f:
                files = {"source": (image_path.name, f, "image/jpeg")}
                resp = requests.post(url, params=params, files=files, timeout=120)

            if resp.ok:
                print(f"[Facebook] Photo published: {caption[:50]}...")
                return True
            else:
                print(f"[Facebook] Photo upload failed: {resp.status_code}")
                return False

        except Exception as e:
            print(f"[Facebook] Photo error: {e}")
            return False
