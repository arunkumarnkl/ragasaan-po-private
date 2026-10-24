"""Square recipe-photo display helpers (2 cm at nominal 96 CSS px/in)."""
from __future__ import annotations
from io import BytesIO
from html import escape
from urllib.parse import urlsplit
from PIL import Image, ImageOps

RECIPE_IMAGE_PX = 76  # 2 cm at nominal 96 CSS pixels/inch (75.59 px).

def crop_thumbnail(image_bytes: bytes):
    """Preserve the stored original; crop a separate display thumbnail to 76×76."""
    with Image.open(BytesIO(image_bytes)) as source:
        source.load()
        return ImageOps.fit(source.convert("RGB"), (RECIPE_IMAGE_PX, RECIPE_IMAGE_PX), method=Image.Resampling.LANCZOS)

def safe_thumbnail_html(image_url: str, alt: str = "Drink photo") -> str:
    """Square display for external images without changing their remote file."""
    parts = urlsplit(str(image_url).strip())
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
        raise ValueError("Recipe photo requires a valid HTTPS image URL")
    url = escape(str(image_url).strip(), quote=True)
    alt_text = escape(str(alt), quote=True)
    return (f'<img src="{url}" alt="{alt_text}" width="{RECIPE_IMAGE_PX}" '
            f'height="{RECIPE_IMAGE_PX}" '
            f'style="width:{RECIPE_IMAGE_PX}px;height:{RECIPE_IMAGE_PX}px;'
            'object-fit:cover;object-position:center;display:block;'
            'border-radius:4px;max-width:none;" />')
