import random
import shutil
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
        duration: float = 60,
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
                "-preset", "medium",
                "-crf", "18",
                "-profile:v", "high",
                "-level", "4.2",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-movflags", "+faststart",
                str(output_path),
            ], timeout=300)
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

    @staticmethod
    def apply_color_grade(
        input_video: Path,
        output_name: str = "graded",
        contrast: float = 1.25,
        saturation: float = 1.35,
        brightness: float = 0.05,
        gamma: float = 1.0,
    ) -> Optional[Path]:
        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            run_ffmpeg([
                "-y", "-i", str(input_video),
                "-vf", f"eq=contrast={contrast}:saturation={saturation}:brightness={brightness}:gamma={gamma}",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(output_path),
            ], timeout=120)
            print(f"[VideoGen] Color graded: {output_path.name}")
            return output_path
        except Exception as e:
            print(f"[VideoGen] Color grade error: {e}")
            return None

    @staticmethod
    def apply_ken_burns(
        input_video: Path,
        output_name: str = "kenburns",
        zoom_speed: float = 0.003,
        max_zoom: float = 1.2,
        duration: float = 60,
    ) -> Optional[Path]:
        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            scale_factor = max_zoom + 0.05
            run_ffmpeg([
                "-y", "-i", str(input_video),
                "-vf",
                f"scale=iw*{scale_factor}:ih*{scale_factor},"
                f"crop=iw/(1+{zoom_speed}*t):ih/(1+{zoom_speed}*t):"
                f"(iw-iw/(1+{zoom_speed}*t))/2:(ih-ih/(1+{zoom_speed}*t))/2,"
                f"scale=1080x1920",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart",
                str(output_path),
            ], timeout=180)
            print(f"[VideoGen] Ken Burns: {output_path.name}")
            return output_path
        except Exception as e:
            print(f"[VideoGen] Ken Burns error: {e}")
            return None

    @staticmethod
    def apply_slow_motion(
        input_video: Path,
        output_name: str = "slowmo",
        speed: float = 0.5,
    ) -> Optional[Path]:
        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        setpts = 1.0 / speed
        try:
            run_ffmpeg([
                "-y", "-i", str(input_video),
                "-vf", f"setpts={setpts}*PTS,minterpolate=fps=30:mi_mode=mci",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-af", f"atempo={speed}",
                "-movflags", "+faststart",
                str(output_path),
            ], timeout=300)
            print(f"[VideoGen] Slow motion: {output_path.name}")
            return output_path
        except Exception as e:
            print(f"[VideoGen] Slow motion error: {e}")
            return None

    @staticmethod
    def apply_scoreboard(
        input_video: Path,
        output_name: str = "scored",
        team_home: str = "Canada",
        team_away: str = "Opponent",
        score_home: str = "0",
        score_away: str = "0",
        duration: float = 60,
    ) -> Optional[Path]:
        from modules.content.image_generator import ImageGenerator
        overlay = ImageGenerator.create_video_overlay(team_home, team_away, score_home, score_away)
        if not overlay:
            return None

        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            run_ffmpeg([
                "-y", "-i", str(input_video),
                "-i", str(overlay),
                "-filter_complex",
                f"[0:v][1:v]overlay=10:H-h-10:format=auto,format=yuv420p[v]",
                "-map", "[v]", "-map", "0:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
                "-c:a", "copy",
                "-t", str(duration),
                "-movflags", "+faststart",
                str(output_path),
            ], timeout=120)
            print(f"[VideoGen] Scoreboard: {output_path.name}")
            return output_path
        except Exception as e:
            print(f"[VideoGen] Scoreboard error: {e}")
            return None

    @staticmethod
    def apply_transition(
        video_a: Path,
        video_b: Path,
        output_name: str = "transitioned",
        transition: str = "fade",
        transition_duration: float = 0.5,
    ) -> Optional[Path]:
        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            offset_sec = VideoGenerator.get_video_duration(video_a) - transition_duration
            if offset_sec <= 0:
                offset_sec = 0
            run_ffmpeg([
                "-y",
                "-i", str(video_a),
                "-i", str(video_b),
                "-filter_complex",
                f"xfade=transition={transition}:duration={transition_duration}:offset={offset_sec}",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart",
                str(output_path),
            ], timeout=180)
            print(f"[VideoGen] Transition: {output_path.name}")
            return output_path
        except Exception as e:
            print(f"[VideoGen] Transition error: {e}")
            return None

    @staticmethod
    def generate_pro_clip(
        input_video: Path,
        output_name: str = "pro_clip",
        start_time: float = 0,
        duration: float = 60,
        team_home: str = "",
        team_away: str = "",
        score_home: str = "",
        score_away: str = "",
        add_ken_burns: bool = True,
        add_color_grade: bool = True,
        add_scoreboard: bool = True,
        add_intro: bool = True,
        add_outro: bool = True,
    ) -> Optional[Path]:
        output_path = PROCESSED_DIR / f"{output_name}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        filter_parts = []

        crop_scale = f"crop=ih*9/16:ih,scale=1080x1920"
        filter_parts.append(crop_scale)

        if add_color_grade:
            filter_parts.append(f"eq=contrast=1.25:saturation=1.35:brightness=0.05")

        if add_intro:
            intro = random.choice(VIDEO_INTRO_TEMPLATES)
            filter_parts.append(
                f"drawtext=text='{intro['text']}':"
                f"fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:"
                f"enable='between(t,0,{intro['duration']})'"
            )

        filter_chain = ",".join(filter_parts)

        try:
            run_ffmpeg([
                "-y",
                "-ss", str(start_time),
                "-i", str(input_video),
                "-t", str(duration),
                "-vf", filter_chain,
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-movflags", "+faststart",
                str(output_path),
            ], timeout=300)
            print(f"[VideoGen] Base clip: {output_path.name}")
        except Exception as e:
            print(f"[VideoGen] Base clip error: {e}")
            return None

        current = output_path

        if add_ken_burns:
            kb = VideoGenerator.apply_ken_burns(
                current, f"_pro_kb_{output_name}",
                zoom_speed=0.003, max_zoom=1.2, duration=duration,
            )
            if kb:
                current.unlink(missing_ok=True)
                current = kb

        if add_scoreboard and team_home:
            scored = VideoGenerator.apply_scoreboard(
                current, f"_pro_scored_{output_name}",
                team_home, team_away, score_home, score_away,
                duration=duration,
            )
            if scored:
                current.unlink(missing_ok=True)
                shutil.move(str(scored), str(current))

        return current if current.exists() else None
