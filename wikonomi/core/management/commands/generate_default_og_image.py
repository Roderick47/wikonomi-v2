from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont


class Command(BaseCommand):
    help = "Generate the default Wikonomi Open Graph image without storing a binary in git."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Optional output path. Defaults to core/static/img/wikonomi-og-default.jpg.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"] or settings.BASE_DIR / "core" / "static" / "img" / "wikonomi-og-default.jpg")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.generate_image(output_path)
        self.stdout.write(self.style.SUCCESS(f"Generated default OG image at {output_path}"))

    def generate_image(self, output_path):
        width, height = 1200, 630
        image = Image.new("RGB", (width, height), "#f8fafc")
        draw = ImageDraw.Draw(image)

        start = (102, 209, 126)
        middle = (77, 184, 255)
        end = (75, 39, 152)
        for x in range(width):
            t = x / (width - 1)
            if t < 0.5:
                blend = t / 0.5
                color = tuple(int(start[i] * (1 - blend) + middle[i] * blend) for i in range(3))
            else:
                blend = (t - 0.5) / 0.5
                color = tuple(int(middle[i] * (1 - blend) + end[i] * blend) for i in range(3))
            draw.line([(x, 0), (x, height)], fill=color)

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle((70, 70, width - 70, height - 70), radius=42, fill=(255, 255, 255, 232))
        overlay_draw.ellipse((width - 330, -90, width + 120, 360), fill=(75, 39, 152, 30))
        overlay_draw.ellipse((-140, height - 280, 260, height + 120), fill=(102, 209, 126, 45))
        image = Image.alpha_composite(image.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(image)

        brand_font = self.get_font(96, bold=True)
        headline_font = self.get_font(58, bold=True)
        body_font = self.get_font(34)
        pill_font = self.get_font(28, bold=True)
        mark_font = self.get_font(92, bold=True)

        purple = (75, 39, 152, 255)
        dark = (17, 24, 39, 255)
        muted = (75, 85, 99, 255)
        green = (102, 209, 126, 255)

        draw.rounded_rectangle((110, 120, 245, 255), radius=30, fill=purple)
        draw.text((145, 130), "W", font=mark_font, fill=(255, 255, 255, 255))
        draw.text((280, 122), "Wikonomi", font=brand_font, fill=purple)
        draw.text((115, 300), "PNG Price Comparison", font=headline_font, fill=dark)
        draw.text((118, 385), "Find and compare prices across shops", font=body_font, fill=muted)
        draw.text((118, 432), "in Papua New Guinea.", font=body_font, fill=muted)
        draw.rounded_rectangle((115, 510, 520, 565), radius=27, fill=green)
        draw.text((145, 521), "wikonomi.com", font=pill_font, fill=(255, 255, 255, 255))

        image.convert("RGB").save(output_path, format="JPEG", quality=88, optimize=True, progressive=True)

    def get_font(self, size, bold=False):
        file_names = [
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
            "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
        ]
        directories = [
            Path("/usr/share/fonts/truetype/dejavu"),
            Path("/usr/share/fonts/truetype/liberation2"),
        ]

        for directory in directories:
            for file_name in file_names:
                font_path = directory / file_name
                if font_path.exists():
                    return ImageFont.truetype(str(font_path), size)

        return ImageFont.load_default()
