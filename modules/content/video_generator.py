import random
from pathlib import Path
from typing import Optional

from config import RAW_DIR, PROCESSED_DIR, ASSETS_DIR
from modules.content.templates import VIDEO_INTRO_TEMPLATES, VIDEO_OUTRO_TEMPLATES
from utils import run_ffmpeg, run_ffprobe


class VideoGenerator:

    @staticmethod
    def generate_clip(
        input_video: Path,
        output_name: str = "clip",
        start_time: float = 0,
        duration: float = 30,
        resolution: str = "1080x1920",
        add_intro: bool = True,
        add_outro: bool = True,
    ) -> Optional[Path]:
        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        filter_parts = []

        crop_scale = f"crop=ih*9/16:ih,scale={resolution}"
        filter_parts.append(crop_scale)

        if add_intro:
            intro = random.choice(VIDEO_INTRO_TEMPLATES)
            drawtext = (
                f"drawtext=text='{intro['text']}':"
                f"fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:"
                f"enable='between(t,0,{intro['duration']})'"
            )
            filter_parts.append(drawtext)

        filter_chain = ",".join(filter_parts) if filter_parts else crop_scale

        try:
            run_ffmpeg([
                "-y",
                "-ss", str(start_time),
                "-i", str(input_video),
                "-t", str(duration),
                "-vf", filter_chain,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(output_path),
            ], timeout=180)
            print(f"[VideoGen] Created: {output_path.name}")
            return output_path
        except Exception as e:
            print(f"[VideoGen] FFmpeg error: {e}")
            return None

    @staticmethod
    def crop_portrait(input_video: Path, output_name: str = "portrait") -> Optional[Path]:
        return VideoGenerator.generate_clip(
            input_video=input_video,
            output_name=output_name,
            start_time=0,
            duration=30,
            resolution="1080x1920",
            add_intro=False,
            add_outro=False,
        )

    @staticmethod
    def generate_highlights_reel(
        input_video: Path,
        clips: list[tuple[float, float]],
        output_name: str = "highlights",
    ) -> Optional[Path]:
        if not clips:
            return None

        concat_file = RAW_DIR / "concat_list.txt"
        with open(concat_file, "w") as f:
            for start, dur in clips:
                segment_path = RAW_DIR / f"seg_{start}_{dur}.mp4"
                VideoGenerator.generate_clip(
                    input_video, f"seg_{start}_{dur}",
                    start_time=start, duration=dur,
                    add_intro=False, add_outro=False
                )
                f.write(f"file '{segment_path}'\n")

        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        try:
            run_ffmpeg([
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(output_path),
            ], timeout=300)
            return output_path
        except Exception as e:
            print(f"[VideoGen] Concat error: {e}")
            return None

    @staticmethod
    def get_video_duration(video_path: Path) -> float:
        try:
            result = run_ffprobe([
                "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", str(video_path),
            ])
            return float(result.stdout.strip())
        except Exception:
            return 0
