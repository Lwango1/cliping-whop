import random
import time
from pathlib import Path
from typing import Optional

from config import UserConfig, PROCESSED_DIR, RAW_DIR
from modules.content.ingest import ContentIngestor
from modules.content.video_generator import VideoGenerator
from modules.content.audio_generator import AudioGenerator
from modules.content.image_generator import ImageGenerator
from modules.content.templates import SOCIAL_CAPTIONS, HASHTAGS
from modules.publishing.tiktok import TikTokPublisher
from modules.publishing.youtube import YouTubePublisher
from modules.publishing.instagram import InstagramPublisher
from modules.publishing.facebook import FacebookPublisher
from modules.whop.auto_apply import WhopAutoApply


class ContentPipeline:

    def __init__(self, user_cfg: UserConfig):
        self.cfg = user_cfg
        self.ingestor = ContentIngestor()
        self.video_gen = VideoGenerator()
        self.audio_gen = AudioGenerator()
        self.image_gen = ImageGenerator()

        self.tiktok = TikTokPublisher(user_cfg.tiktok)
        self.youtube = YouTubePublisher(user_cfg.youtube)
        self.instagram = InstagramPublisher(user_cfg.instagram)
        self.facebook = FacebookPublisher(user_cfg.facebook)

    def run_full_pipeline(self) -> dict:
        results = {"applied_campaigns": 0, "clips_created": 0, "posts_published": 0, "whop_campaigns_found": 0}

        print("\n=== PHASE 1: Whop - Recherche et postulation aux campagnes ===")
        if self.cfg.whop.email:
            try:
                applier = WhopAutoApply(self.cfg, headless=True)
                applier.run_auto_apply(max_applications=5)
                print("[Pipeline] Whop phase complete")
            except Exception as e:
                print(f"[Pipeline] Whop error (non-blocking): {e}")
        else:
            print("[Pipeline] Whop non configure, passage a la creation de contenu")

        print("\n=== PHASE 2: Creation de contenu ===")
        content_results = self._create_content()
        results["clips_created"] = content_results.get("clips_created", 0)
        results["posts_published"] = content_results.get("posts_published", 0)

        return results

    def run_daily_pipeline(self) -> dict:
        return self.run_full_pipeline()

    def _create_content(self) -> dict:
        results = {"clips_created": 0, "posts_published": 0}

        events = self.ingestor.fetch_sports_events("canada", limit=3)
        if not events:
            events = self.ingestor.load_cached_events()
        if not events:
            print("[Pipeline] No events found, trying search...")
            events = self.ingestor.search_sports_events("World Cup 2026", limit=3)

        if events:
            self.ingestor.cache_event_data(events)

        for event in events:
            print(f"\n[Pipeline] Processing event: {event.get('name', 'Unknown')}")

            team_home = event.get("home_team", "Canada")
            team_away = event.get("away_team", "Opponent")
            score_home = event.get("home_score") or "?"
            score_away = event.get("away_score") or "?"

            downloaded = self.ingestor.download_youtube_replay(
                f"{team_home} vs {team_away} highlights",
                max_duration=600,
            )

            if not downloaded:
                print("[Pipeline] No video downloaded, creating image post instead")
                thumbnail = self.image_gen.create_thumbnail(
                    team_home, team_away,
                    str(score_home), str(score_away),
                    output_name=f"event_{event.get('id', 'unknown')}",
                )
                self._publish_image_content(thumbnail, event, results)
                continue

            clip = self.video_gen.generate_clip(
                input_video=downloaded,
                output_name=f"clip_{event.get('id', 'unknown')}",
                start_time=random.uniform(10, 60),
                duration=30,
                add_intro=True,
                add_outro=True,
            )

            if clip:
                voiceover = self.audio_gen.generate_voiceover(
                    output_name=f"vo_{event.get('id', 'unknown')}",
                )
                if voiceover:
                    mixed = self.audio_gen.mix_audio_with_video(clip, voiceover)
                    if mixed:
                        clip = mixed

                results["clips_created"] += 1
                self._publish_video_content(clip, event, results)

            thumbnail = self.image_gen.create_thumbnail(
                team_home, team_away,
                str(score_home), str(score_away),
                output_name=f"thumb_{event.get('id', 'unknown')}",
            )

        return results

    def _publish_video_content(self, video_path: Path, event: dict, results: dict):
        event_name = event.get("name", "World Cup 2026")

        platforms = self._get_enabled_platforms()

        if "tiktok" in platforms:
            caption = random.choice(SOCIAL_CAPTIONS["tiktok"])
            if self.tiktok.login_via_session():
                if self.tiktok.upload_video(video_path, caption, HASHTAGS["tiktok"]):
                    results["posts_published"] += 1
            time.sleep(5)

        if "youtube" in platforms:
            title = f"{event_name} - World Cup 2026 Highlights #shorts"
            desc = random.choice(SOCIAL_CAPTIONS["youtube_shorts"])
            if self.youtube.login():
                if self.youtube.upload_short(video_path, title, desc, HASHTAGS["youtube"]):
                    results["posts_published"] += 1
            time.sleep(5)

        if "instagram" in platforms:
            caption = random.choice(SOCIAL_CAPTIONS["instagram"])
            if self.instagram.login():
                if self.instagram.upload_reel(video_path, caption, HASHTAGS["instagram"]):
                    results["posts_published"] += 1
            time.sleep(5)

        if "facebook" in platforms:
            title = f"{event_name} - World Cup 2026"
            desc = random.choice(SOCIAL_CAPTIONS["facebook"])
            if self.facebook.login():
                if self.facebook.upload_video(video_path, title, desc, HASHTAGS["facebook"]):
                    results["posts_published"] += 1
            time.sleep(5)

    def _publish_image_content(self, image_path: Optional[Path], event: dict, results: dict):
        if not image_path:
            return

        platforms = self._get_enabled_platforms()
        event_name = event.get("name", "World Cup 2026")

        if "instagram" in platforms:
            caption = random.choice(SOCIAL_CAPTIONS["instagram"])
            if self.instagram.login():
                if self.instagram.upload_photo(image_path, caption, HASHTAGS["instagram"]):
                    results["posts_published"] += 1
            time.sleep(3)

        if "facebook" in platforms:
            caption = random.choice(SOCIAL_CAPTIONS["facebook"])
            if self.facebook.login():
                if self.facebook.upload_photo(image_path, caption, HASHTAGS["facebook"]):
                    results["posts_published"] += 1
            time.sleep(3)

    def _get_enabled_platforms(self) -> list[str]:
        platforms = []
        if self.cfg.tiktok.session_id:
            platforms.append("tiktok")
        if self.cfg.youtube.client_id:
            platforms.append("youtube")
        if self.cfg.instagram.username:
            platforms.append("instagram")
        if self.cfg.facebook.page_id:
            platforms.append("facebook")
        return platforms
