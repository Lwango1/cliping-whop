import sys
import os
import subprocess
from pathlib import Path


def init_output():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        pass

    for path in os.environ.get("PATH", "").split(os.pathsep):
        for name in ("ffmpeg.exe", "ffmpeg"):
            candidate = Path(path) / name
            if candidate.exists():
                return str(candidate)

    return "ffmpeg"


def get_ffprobe_path() -> str:
    ffmpeg = Path(get_ffmpeg_path())
    ffprobe = ffmpeg.with_name("ffprobe" + ffmpeg.suffix)
    if ffprobe.exists():
        return str(ffprobe)
    return "ffprobe"


def run_ffmpeg(args: list[str], timeout: int = 120, check: bool = True):
    ffmpeg = get_ffmpeg_path()
    cmd = [ffmpeg] + args
    return subprocess.run(cmd, check=check, capture_output=True, timeout=timeout)


def run_ffprobe(args: list[str], timeout: int = 30):
    ffprobe = get_ffprobe_path()
    cmd = [ffprobe] + args
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)


def run_ytdlp(args: list[str], timeout: int = 120):
    python = sys.executable
    cmd = [python, "-m", "yt_dlp"] + args
    return subprocess.run(cmd, check=False, capture_output=True, timeout=timeout)
