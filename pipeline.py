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

        print("[Pipeline] Aucun contenu automatique genere. Utilise l'interface web pour generer des clips.")
        results["message"] = "Pipeline terminee. Utilise l'onglet Contenu > Creer un clip pour generer des videos."

        return results

    def generate_clips_from_url(
        self,
        url: str,
        num_clips: int = 1,
        clip_duration: float = 120,
        start_offset: float = 10,
    ) -> dict:
        results = {"clips": [], "errors": []}

        print(f"\n[Pipeline] Downloading: {url}")
        downloaded = None
        for attempt in range(2):
            try:
                downloaded = self.ingestor.download_youtube_replay(
                    url,
                    max_duration=num_clips * clip_duration + 60,
                    output_dir=RAW_DIR,
                )
                if downloaded:
                    break
            except Exception as e:
                print(f"[Pipeline] Download attempt {attempt+1} failed: {e}")
                time.sleep(3)

        if not downloaded or isinstance(downloaded, str):
            results["errors"].append(f"Download failed: {downloaded}")
            return results

        total_duration = self.video_gen.get_video_duration(downloaded)
        print(f"[Pipeline] Video duration: {total_duration}s")

        needed = num_clips * clip_duration
        available = total_duration - start_offset
        if available < clip_duration:
            results["errors"].append(f"Video too short ({total_duration}s), need at least {start_offset + clip_duration}s")
            return results

        actual_num = min(num_clips, int(available // clip_duration))

        for i in range(actual_num):
            start = start_offset + (i * clip_duration)
            if start + clip_duration > total_duration:
                break

            print(f"\n[Pipeline] Generating clip {i+1}/{actual_num} (start={start}s, duration={clip_duration}s)")

            intro_text = self.translator.translate(random.choice(VIDEO_INTRO_TEMPLATES)["text"])
            outro_text = self.translator.translate(random.choice(VIDEO_OUTRO_TEMPLATES)["text"])

            clip = self.video_gen.generate_pro_clip(
                input_video=downloaded,
                output_name=f"clip_{int(time.time())}_{i+1}",
                start_time=start,
                duration=clip_duration,
                add_ken_burns=True,
                add_color_grade=True,
                add_intro=True,
                add_outro=True,
                intro_text=intro_text,
                outro_text=outro_text,
            )

            if clip:
                try:
                    voice_text = self.translator.translate(random.choice([
                        "This is absolutely incredible! You have to see this!",
                        "Wait till the end, it gets wild!",
                        "I can't believe this is real!",
                        "This moment was absolutely insane!",
                        "The best thing you'll see today!",
                    ]))
                    tts_voice = self.translator.get_tts_voice()

                    voiceover = self.audio_gen.generate_voiceover(
                        text=voice_text,
                        output_name=f"vo_{int(time.time())}_{i+1}",
                        voice=tts_voice,
                    )
                    if voiceover and voiceover[0]:
                        mixed = self.audio_gen.mix_audio_with_video(clip, voiceover[0])
                        if mixed:
                            clip = mixed
                except Exception as e:
                    print(f"[Pipeline] Voiceover error: {e}")

                results["clips"].append(str(clip))

        results["clips_created"] = len(results["clips"])
        print(f"\n[Pipeline] Generated {results['clips_created']} clips")
        return results

    def _publish_video_content(self, video_path: Path, caption_prefix: str, results: dict):
        platforms = self._get_enabled_platforms()

        if "tiktok" in platforms:
            caption = self.translator.translate(random.choice(SOCIAL_CAPTIONS["tiktok"]))
            if self.tiktok.login_via_session():
                if self.tiktok.upload_video(video_path, caption, HASHTAGS["tiktok"]):
                    results["posts_published"] += 1
            time.sleep(5)

        if "youtube" in platforms:
            title = self.translator.translate(f"{caption_prefix} #shorts")
            desc = self.translator.translate(random.choice(SOCIAL_CAPTIONS["youtube_shorts"]))
            if self.youtube.login():
                if self.youtube.upload_short(video_path, title, desc, HASHTAGS["youtube"]):
                    results["posts_published"] += 1
            time.sleep(5)

    def _get_enabled_platforms(self) -> list[str]:
        platforms = []
        if self.cfg.tiktok.session_id:
            platforms.append("tiktok")
        if self.cfg.youtube.client_id:
            platforms.append("youtube")
        return platforms
