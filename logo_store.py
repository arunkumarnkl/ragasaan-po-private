"""Persist a non-secret company logo for Streamlit preview and Word purchase orders."""
from __future__ import annotations
from pathlib import Path
import os
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'assets'  # legacy per-version location
# A shared user location survives ZIP upgrades/extracting into a new folder.
APPDATA=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local'/'share')))
PERSISTENT_ASSETS=APPDATA/'Ragasaan_PO'/'assets'
LOGO_PATH=PERSISTENT_ASSETS/'ragasaan_logo.png'
REMOTE_URL='https://drive.google.com/uc?export=view&id=1ggVYW2TF97BYp4JbmABYJA1bE8-ryyno'
_ATTEMPTED=False


def _image_type(data:bytes)->str:
    if data.startswith(b'\x89PNG\r\n\x1a\n'):return 'png'
    if data.startswith(b'\xff\xd8\xff'):return 'jpg'
    raise ValueError('Not a valid PNG/JPEG logo. Please select an image file.')


def saved_logo_path()->Path|None:
    for folder in (PERSISTENT_ASSETS,ASSETS):
        for name in ('ragasaan_logo.png','ragasaan_logo.jpg'):
            candidate=folder/name
            if candidate.is_file():return candidate
    return None


def save_logo(data:bytes)->Path:
    if not data or len(data)>4_000_000:raise ValueError('Logo must be a PNG/JPEG smaller than 4 MB.')
    extension=_image_type(data)
    PERSISTENT_ASSETS.mkdir(exist_ok=True,parents=True)
    newpath=PERSISTENT_ASSETS/f'ragasaan_logo.{extension}'
    newpath.write_bytes(data)
    for name in ('ragasaan_logo.png','ragasaan_logo.jpg'):
        if PERSISTENT_ASSETS/name!=newpath:(PERSISTENT_ASSETS/name).unlink(missing_ok=True)
    return newpath


def clear_logo()->None:
    for folder in (PERSISTENT_ASSETS,ASSETS):
        for name in ('ragasaan_logo.png','ragasaan_logo.jpg'):
            (folder/name).unlink(missing_ok=True)


def load_default_logo(try_remote:bool=True)->bytes|None:
    global _ATTEMPTED
    f=saved_logo_path()
    if f:return f.read_bytes()
    if not try_remote or _ATTEMPTED:return None
    _ATTEMPTED=True
    try:
        with urlopen(Request(REMOTE_URL,headers={'User-Agent':'Mozilla/5.0'}),timeout=4) as r:
            body=r.read(4_000_001)
        save_logo(body)
        return body
    except (OSError,ValueError):
        return None
