import random
import time
from pathlib import Path
from typing import Optional

from config import UserConfig, PROCESSED_DIR, RAW_DIR
from modules.content.ingest import ContentIngestor
from modules.content.video_generator import VideoGenerator
from modules.content.audio_generator import AudioGenerator
from modules.content.image_generator import ImageGenerator
from modules.content.templates import SOCIAL_CAPTIONS, HASHTAGS, VIDEO_INTRO_TEMPLATES, VIDEO_OUTRO_TEMPLATES
from modules.content.translator import Translator
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
        self.translator = Translator(user_cfg.target_language)

        self.tiktok = TikTokPublisher(user_cfg.tiktok)
        self.youtube = YouTubePublisher(user_cfg.youtube)
        self.instagram = InstagramPublisher(user_cfg.instagram)
        self.facebook = FacebookPublisher(user_cfg.facebook)

    def run_full_pipeline(self) -> dict:
        results = {"applied_campaigns": 0, "clips_created": 0, "posts_published": 0, "whop_campaigns_found": 0, "message": ""}

        print("\n=== PHASE 1: Whop - Recherche et postulation aux campagnes ===")
        if self.cfg.whop.email:
            try:
                applier = WhopAutoApply(self.cfg, headless=True)
                whop_result = applier.run_auto_apply(max_applications=5)
                results["whop_campaigns_found"] = whop_result.get("campaigns_found", 0)
                results["applied_campaigns"] = whop_result.get("campaigns_applied", 0)
                print(f"[Pipeline] Whop phase: {results['whop_campaigns_found']} found, {results['applied_campaigns']} applied")
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

        events = []
        try:
            events = self.ingestor.fetch_sports_events("canada", limit=3)
        except Exception as e:
            print(f"[Pipeline] Sports API error: {e}")
        if not events:
            events = self.ingestor.load_cached_events()
        if not events:
            print("[Pipeline] No events found, trying search...")
            try:
                events = self.ingestor.search_sports_events("World Cup 2026", limit=3)
            except Exception as e:
                print(f"[Pipeline] Search error: {e}")

        if events:
            self.ingestor.cache_event_data(events)

        for event in events:
            print(f"\n[Pipeline] Processing event: {event.get('name', 'Unknown')}")

            team_home = event.get("home_team", "Canada")
            team_away = event.get("away_team", "Opponent")
            score_home = event.get("home_score") or "?"
            score_away = event.get("away_score") or "?"

            downloaded = None
            for attempt in range(2):
                try:
                    downloaded = self.ingestor.download_youtube_replay(
                        f"{team_home} vs {team_away} highlights",
                        max_duration=300,
                    )
                    if downloaded:
                        break
                except Exception as e:
                    print(f"[Pipeline] Download attempt {attempt+1} failed: {e}")
                    time.sleep(3)

            if not downloaded:
                print("[Pipeline] No video downloaded, creating image post instead")
                try:
                    thumbnail = self.image_gen.create_thumbnail(
                        team_home, team_away,
                        str(score_home), str(score_away),
                        output_name=f"event_{event.get('id', 'unknown')}",
                    )
                    self._publish_image_content(thumbnail, event, results)
                except Exception as e:
                    print(f"[Pipeline] Image post error: {e}")
                continue

            try:
                intro_text = self.translator.translate(random.choice(VIDEO_INTRO_TEMPLATES)["text"])
                outro_text = self.translator.translate(random.choice(VIDEO_OUTRO_TEMPLATES)["text"])

                clip = self.video_gen.generate_pro_clip(
                    input_video=downloaded,
                    output_name=f"clip_{event.get('id', 'unknown')}",
                    start_time=random.uniform(10, 60),
                    duration=60,
                    team_home=team_home,
                    team_away=team_away,
                    score_home=str(score_home),
                    score_away=str(score_away),
                    add_ken_burns=True,
                    add_color_grade=True,
                    add_scoreboard=True,
                    add_intro=True,
                    add_outro=True,
                    intro_text=intro_text,
                    outro_text=outro_text,
                )

                if clip:
                    try:
                        voice_text = random.choice([
                            "What a goal from {player}! The crowd goes wild at the World Cup 2026!",
                            "Unbelievable save! This is why the World Cup is the biggest stage in football.",
                            "Canada making history at the World Cup! Can they go all the way?",
                            "The pressure is on! Every pass counts in this World Cup showdown.",
                            "That skill move was FILTHY! World Cup 2026 delivering the best football.",
                            "The World Cup brings the best football action. Who's your pick?",
                            "From the stands to the pitch, the energy is UNREAL at the World Cup!",
                            "World Cup 2026 - where legends are made. Subscribe for daily highlights!",
                        ]).format(player="Canada")
                        voice_text = self.translator.translate(voice_text)
                        tts_voice = self.translator.get_tts_voice()

                        voiceover = self.audio_gen.generate_voiceover(
                            text=voice_text,
                            output_name=f"vo_{event.get('id', 'unknown')}",
                            voice=tts_voice,
                        )
                        if voiceover:
                            mixed = self.audio_gen.mix_audio_with_video(clip, voiceover)
                            if mixed:
                                clip = mixed
                    except Exception as e:
                        print(f"[Pipeline] Voiceover error: {e}")

                    results["clips_created"] += 1
                    self._publish_video_content(clip, event, results)
            except Exception as e:
                print(f"[Pipeline] Clip generation error: {e}")

            try:
                self.image_gen.create_thumbnail(
                    team_home, team_away,
                    str(score_home), str(score_away),
                    output_name=f"thumb_{event.get('id', 'unknown')}",
                )
            except Exception as e:
                print(f"[Pipeline] Thumbnail error: {e}")

        if results["clips_created"] == 0:
            results["message"] = "Aucun clip cree. Verifie que les replays YouTube sont disponibles et que les comptes reseaux sont configures."
        else:
            results["message"] = f"Pipeline terminee: {results['clips_created']} clips, {results['posts_published']} publications"
        return results

    def _publish_video_content(self, video_path: Path, event: dict, results: dict):
        event_name = event.get("name", "World Cup 2026")

        platforms = self._get_enabled_platforms()

        if "tiktok" in platforms:
            caption = self.translator.translate(random.choice(SOCIAL_CAPTIONS["tiktok"]))
            if self.tiktok.login_via_session():
                if self.tiktok.upload_video(video_path, caption, HASHTAGS["tiktok"]):
                    results["posts_published"] += 1
            time.sleep(5)

        if "youtube" in platforms:
            title = self.translator.translate(f"{event_name} - World Cup 2026 Highlights #shorts")
            desc = self.translator.translate(random.choice(SOCIAL_CAPTIONS["youtube_shorts"]))
            if self.youtube.login():
                if self.youtube.upload_short(video_path, title, desc, HASHTAGS["youtube"]):
                    results["posts_published"] += 1
            time.sleep(5)

        if "instagram" in platforms:
            caption = self.translator.translate(random.choice(SOCIAL_CAPTIONS["instagram"]))
            if self.instagram.login():
                if self.instagram.upload_reel(video_path, caption, HASHTAGS["instagram"]):
                    results["posts_published"] += 1
            time.sleep(5)

        if "facebook" in platforms:
            title = self.translator.translate(f"{event_name} - World Cup 2026")
            desc = self.translator.translate(random.choice(SOCIAL_CAPTIONS["facebook"]))
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
            caption = self.translator.translate(random.choice(SOCIAL_CAPTIONS["instagram"]))
            if self.instagram.login():
                if self.instagram.upload_photo(image_path, caption, HASHTAGS["instagram"]):
                    results["posts_published"] += 1
            time.sleep(3)

        if "facebook" in platforms:
            caption = self.translator.translate(random.choice(SOCIAL_CAPTIONS["facebook"]))
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
