import time
import random
from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.exceptions import RefreshError

from config import YouTubeConfig, LOGS_DIR


class YouTubePublisher:
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"

    def __init__(self, yt_cfg: YouTubeConfig):
        self.cfg = yt_cfg
        self.service = None
        self.logged_in = False

    def login(self) -> bool:
        if not self.cfg.client_id or not self.cfg.refresh_token:
            print("[YouTube] Missing client_id or refresh_token")
            return False

        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials(
                token=None,
                refresh_token=self.cfg.refresh_token,
                client_id=self.cfg.client_id,
                client_secret=self.cfg.client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=self.SCOPES,
            )
            self.service = build(self.API_SERVICE_NAME, self.API_VERSION, credentials=creds)
            self.logged_in = True
            return True

        except RefreshError:
            print("[YouTube] Token expired. Need new refresh_token.")
            return False
        except Exception as e:
            print(f"[YouTube] Login error: {e}")
            return False

    def upload_short(self, video_path: Path, title: str, description: str, hashtags: list[str] = None) -> bool:
        if not self.logged_in and not self.login():
            return False

        if not video_path.exists():
            print(f"[YouTube] File not found: {video_path}")
            return False

        full_desc = description
        if hashtags:
            full_desc += "\n\n" + " ".join(hashtags)

        body = {
            "snippet": {
                "title": title[:100],
                "description": full_desc[:5000],
                "tags": ["WorldCup", "Betway", "Shorts"] + (hashtags or []),
                "categoryId": "17",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            }
        }

        try:
            media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
            request = self.service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
            response = request.execute()

            with open(LOGS_DIR / "youtube_posts.log", "a", encoding="utf-8") as log:
                log.write(f"[{time.ctime()}] Published: {response.get('id')} | {title}\n")

            print(f"[YouTube] Published short: {title} (id: {response.get('id')})")
            return True

        except Exception as e:
            print(f"[YouTube] Upload error: {e}")
            return False
