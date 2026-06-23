import random
from pathlib import Path
from typing import Optional

from config import PROCESSED_DIR, RAW_DIR
from utils import run_ffmpeg


CAPTION_TEMPLATES = [
    "This is absolutely incredible! You have to see this!",
    "Wait till the end, it gets wild!",
    "I can't believe this is real!",
    "This moment was absolutely insane!",
    "The best thing you'll see today!",
    "This is too good to be true!",
    "Absolutely mind-blowing!",
    "You won't believe what happens next!",
]


class AudioGenerator:

    @staticmethod
    def generate_voiceover(text: Optional[str] = None, output_name: str = "voiceover", voice: str = "en-US-ChristopherNeural") -> tuple:
        if not text:
            text = random.choice(CAPTION_TEMPLATES)

        output_path = PROCESSED_DIR / "audio" / f"{output_name}.mp3"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import edge_tts
            import asyncio
            import threading

            async def _run():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(str(output_path))

            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    new_loop = asyncio.new_event_loop()
                    t = threading.Thread(target=new_loop.run_until_complete, args=(_run(),))
                    t.start()
                    t.join()
                    new_loop.close()
                else:
                    asyncio.run(_run())
            except RuntimeError:
                asyncio.run(_run())

            print(f"[AudioGen] Voiceover created: {output_path.name}")
            return output_path, text

        except ImportError:
            print("[AudioGen] edge-tts not installed. Falling back to ffmpeg silence generation.")
            silence = AudioGenerator._generate_silence(output_path)
            return (silence, text) if silence else (None, text)

        except Exception as e:
            print(f"[AudioGen] TTS error: {e}")
            return None, text

    @staticmethod
    def _generate_silence(output_path: Path, duration: int = 15) -> Optional[Path]:
        try:
            run_ffmpeg([
                "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(duration),
                str(output_path),
            ], timeout=30)
            return output_path
        except Exception:
            return None

    @staticmethod
    def mix_audio_with_video(video_path: Path, audio_path: Path, output_name: str = "mixed") -> Optional[Path]:
        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            run_ffmpeg([
                "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "aac",
                "-filter_complex", "[1:a]aloop=loop=-1:size=1,atrim=duration=300[a];[0:a][a]amix=inputs=2:duration=first[d]",
                "-map", "0:v:0",
                "-map", "[d]",
                "-shortest",
                str(output_path),
            ], timeout=60)
            return output_path
        except Exception as e:
            print(f"[AudioGen] Mix error: {e}")
            return None

    @staticmethod
    def generate_music_background(output_name: str = "background_music", duration: int = 30) -> Optional[Path]:
        output_path = PROCESSED_DIR / "audio" / f"{output_name}.mp3"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            run_ffmpeg([
                "-y",
                "-f", "lavfi", "-i",
                f"sine=frequency=140:duration={duration},atempo=1.0,aformat=sample_rates=44100",
                "-af", "volume=0.3",
                str(output_path),
            ], timeout=30)
            return output_path
        except Exception:
            return None

    @staticmethod
    def extract_audio_from_video(video_path: Path, output_name: str = "extracted_audio") -> Optional[Path]:
        output_path = RAW_DIR / f"{output_name}.mp3"
        try:
            run_ffmpeg([
                "-y",
                "-i", str(video_path),
                "-q:a", "0",
                "-map", "a",
                str(output_path),
            ], timeout=60)
            return output_path
        except Exception as e:
            print(f"[AudioGen] Extract audio error: {e}")
            return None
