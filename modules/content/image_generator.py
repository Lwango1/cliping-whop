import random
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

from config import PROCESSED_DIR, ASSETS_DIR


class ImageGenerator:

    @staticmethod
    def create_thumbnail(
        team_home: str = "Canada",
        team_away: str = "Brazil",
        score_home: str = "",
        score_away: str = "",
        output_name: str = "thumbnail",
    ) -> Optional[Path]:
        output_path = PROCESSED_DIR / "thumbnails" / f"{output_name}.jpg"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        width, height = 1920, 1080
        bg_color = (20, 30, 60)
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        gradient = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for y in range(height):
            alpha = int(80 * (1 - y / height))
            gradient.putpixel((0, y), (0, 0, 0, alpha))

        gradient = gradient.resize((width, height))
        img = Image.alpha_composite(img.convert("RGBA"), gradient).convert("RGB")
        draw = ImageDraw.Draw(img)

        try:
            font_large = ImageFont.truetype("arial.ttf", 72)
            font_medium = ImageFont.truetype("arial.ttf", 48)
            font_score = ImageFont.truetype("arial.ttf", 96)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_score = ImageFont.load_default()

        draw.text((width // 2, 80), "WORLD CUP 2026", font=font_large, fill=(255, 215, 0), anchor="mt")

        score_text = f"{score_home or '?'} - {score_away or '?'}"
        draw.text((width // 2, height // 2 - 40), score_text, font=font_score, fill="white", anchor="mt")

        draw.text((width // 2 - 200, height // 2 + 80), team_home, font=font_medium, fill=(255, 80, 80), anchor="mt")
        draw.text((width // 2 + 200, height // 2 + 80), team_away, font=font_medium, fill=(80, 180, 255), anchor="mt")

        draw.text((width // 2, height - 100), "World Cup 2026", font=font_medium, fill=(255, 215, 0), anchor="mt")

        img.save(output_path, quality=95, subsampling=0)
        print(f"[ImageGen] Thumbnail created: {output_path.name}")
        return output_path

    @staticmethod
    def create_social_post_image(
        event_name: str,
        caption: str,
        output_name: str = "social_post",
    ) -> Optional[Path]:
        output_path = PROCESSED_DIR / "images" / f"{output_name}.jpg"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        width, height = 1080, 1080
        img = Image.new("RGB", (width, height), (10, 20, 40))
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("arial.ttf", 52)
            font_body = ImageFont.truetype("arial.ttf", 36)
        except (OSError, IOError):
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()

        draw.text((width // 2, 150), event_name or "World Cup 2026", font=font_title, fill=(255, 215, 0), anchor="mt")

        lines = []
        words = caption.split()
        current_line = ""
        for word in words:
            test = current_line + " " + word if current_line else word
            bbox = draw.textbbox((0, 0), test, font=font_body)
            if bbox[2] - bbox[0] > width - 100:
                lines.append(current_line)
                current_line = word
            else:
                current_line = test
        if current_line:
            lines.append(current_line)

        y_start = 400
        for i, line in enumerate(lines):
            draw.text((width // 2, y_start + i * 50), line, font=font_body, fill="white", anchor="mt")

        draw.text((width // 2, height - 80), "World Cup 2026", font=font_body, fill=(255, 215, 0), anchor="mt")

        img.save(output_path, quality=95, subsampling=0)
        print(f"[ImageGen] Post image created: {output_path.name}")
        return output_path

    @staticmethod
    def create_video_overlay(team_a: str, team_b: str, score_a: str, score_b: str) -> Optional[Path]:
        output_path = PROCESSED_DIR / "overlays" / f"scoreboard_{team_a}_{team_b}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        width, height = 600, 100
        img = Image.new("RGBA", (width, height), (0, 0, 0, 180))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except (OSError, IOError):
            font = ImageFont.load_default()

        draw.text((20, height // 2), team_a[:10], font=font, fill="white", anchor="lm")
        draw.text((width // 2, height // 2), f"{score_a} - {score_b}", font=font, fill=(255, 215, 0), anchor="mm")
        draw.text((width - 20, height // 2), team_b[:10], font=font, fill="white", anchor="rm")

        img.save(output_path)
        return output_path
