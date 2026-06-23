from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from config import PROCESSED_DIR


class ImageGenerator:

    @staticmethod
    def create_social_post_image(
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

        img.save(output_path, quality=95, subsampling=0)
        print(f"[ImageGen] Post image created: {output_path.name}")
        return output_path
