"""Generate Android launcher icons as PNG without committing binary source files.

The artwork is intentionally drawn within Android's maskable safe area.
"""
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw


@lru_cache(maxsize=4)
def png_icon(size: int, *, maskable: bool = False) -> bytes:
    if size not in (192, 512):
        raise ValueError("Unsupported Android icon size")
    background = "#5149dd"
    image = Image.new("RGBA", (size, size), background)
    draw = ImageDraw.Draw(image)
    if not maskable:
        inset = round(size * 0.06)
        radius = round(size * 0.20)
        # A rounded square is familiar on regular Android launchers.
        # Keep outer pixels solid rather than transparent for older devices.
        draw.rounded_rectangle(
            (inset, inset, size - inset, size - inset),
            radius=radius, fill="#5b53e4",
        )
    # Centered W silhouette inside central 66% of the maskable icon.
    points = [
        (.23, .34), (.33, .69), (.50, .45), (.67, .69), (.77, .34)
    ]
    pixels = [(round(x * size), round(y * size)) for x, y in points]
    width = max(8, round(size * .068))
    draw.line(pixels, fill="white", width=width, joint="curve")
    radius = width // 2
    for x, y in (pixels[0], pixels[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
