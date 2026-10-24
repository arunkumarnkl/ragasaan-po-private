"""Recipe images: suggestions from openly licensed Wikimedia Commons, overrides in Google Drive.

Images are NOT downloaded into the workbook. PO_Recipe_Images holds a recipe-name
key, image URL or Drive file id, provenance, and attribution.
"""
from __future__ import annotations
import html
import io
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

import requests

IMAGE_COLUMNS = ['recipe_name', 'image_url', 'drive_file_id', 'source', 'attribution', 'updated_at']
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'RagasaanPO/3.4 (recipe photo discovery; Wikimedia Commons API)'


def image_record(rows, recipe_name):
    key = recipe_name.casefold().strip()
    return next((row for row in rows if str(row.get('recipe_name', '')).casefold().strip() == key), {})


def upsert_image_record(rows, recipe_name, *, image_url='', drive_file_id='', source='', attribution=''):
    if not str(recipe_name).strip():
        raise ValueError('Recipe name is required')
    key = recipe_name.casefold().strip()
    remaining = [dict(r) for r in rows if str(r.get('recipe_name', '')).casefold().strip() != key]
    remaining.append({
        'recipe_name': recipe_name, 'image_url': image_url, 'drive_file_id': drive_file_id,
        'source': source, 'attribution': attribution,
        'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    })
    return remaining


def suggested_image(recipe_name, category='', requester=None):
    """Return a Commons thumbnail and license credit, or None.

    The result is only a *suggestion*: filenames aren't a guarantee that a
    photo shows the exact recipe. Searches are intentionally restricted to
    Commons images and use a recipe name instead of arbitrary stock results.
    """
    if requester is None:
        requester = requests.get
    name = str(recipe_name).strip()
    if not name:
        return None
    terms = [f'{name} cocktail', name]
    if str(category).strip() and category.casefold() != 'uncategorised':
        terms.append(f'{category} cocktail')
    for phrase in terms:
        try:
            response = requester(COMMONS_API, params={
                'action': 'query', 'format': 'json', 'generator': 'search',
                'gsrsearch': phrase, 'gsrnamespace': 6,
                'gsrlimit': 5, 'prop': 'imageinfo', 'iiprop': 'url|mime|extmetadata',
                'iiurlwidth': 620,
            }, headers={'User-Agent': USER_AGENT}, timeout=8)
            response.raise_for_status()
            pages = response.json().get('query', {}).get('pages', {})
            # Search order: generator results carry index; don't pick a random image.
            for page in sorted(pages.values(), key=lambda p: p.get('index', 99)):
                infos = page.get('imageinfo') or []
                if not infos:
                    continue
                item = infos[0]
                mime = item.get('mime', '')
                if mime not in ('image/jpeg', 'image/png', 'image/webp'):
                    continue
                meta = item.get('extmetadata') or {}
                license_name = re.sub(r'<[^>]*>', '', html.unescape((meta.get('LicenseShortName') or {}).get('value', ''))).strip()
                if not license_name:
                    continue
                title = page.get('title', '')
                artist = re.sub(r'<[^>]*>', ' ', html.unescape((meta.get('Artist') or {}).get('value', ''))).strip()
                artist = re.sub(r'\s+', ' ', artist)[:180]
                # No claim the name/license was inspected by a person.
                return {
                    'url': item.get('thumburl') or item.get('url', ''),
                    'page': item.get('descriptionurl') or 'https://commons.wikimedia.org/wiki/' + quote(title.replace(' ', '_')),
                    'license': license_name,
                    'attribution': f'Wikimedia Commons · {title} · {artist or "author in source"} · {license_name}',
                    'search': phrase,
                }
        except (requests.RequestException, ValueError, KeyError, TypeError):
            continue
    return None


def verify_upload(data, filename):
    """Reject untrusted or oversized upload; decode rather than trusting suffix."""
    from PIL import Image
    if not data or len(data) > 8 * 1024 * 1024:
        raise ValueError('Select an image under 8 MB')
    from PIL import UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Uploaded file is not a recognised image') from exc
    with img:
        if img.format not in ('PNG', 'JPEG', 'WEBP'):
            raise ValueError('Only PNG, JPG and WebP images are supported')
        if img.width * img.height > 30_000_000:
            raise ValueError('Image resolution is too large')
        mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}[img.format]
        ext = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[img.format]
    return mime, re.sub(r'[^a-zA-Z0-9_.-]+', '_', filename.rsplit('.', 1)[0])[:90] + '.' + ext


class GoogleDriveImages:
    """Private images accessible to the service account; public sharing isn't required.

    To upload, Google Drive API must be enabled, and the target folder must be
    shared with the service account (Editor). Uploaded images remain private.
    """
    def __init__(self, credentials_dict):
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import AuthorizedSession
        creds = Credentials.from_service_account_info(credentials_dict, scopes=[
            'https://www.googleapis.com/auth/drive',
        ])
        self.session = AuthorizedSession(creds)

    def upload(self, folder_id, filename, data, mime):
        if not folder_id or not re.fullmatch(r'[A-Za-z0-9_-]{8,}', str(folder_id)):
            raise ValueError('Enter the target Google Drive folder ID under Admin Settings')
        metadata = {'name': filename, 'parents': [folder_id]}
        from requests_toolbelt.multipart.encoder import MultipartEncoder
        mp = MultipartEncoder(fields={
            'metadata': ('metadata', json.dumps(metadata), 'application/json; charset=UTF-8'),
            'media': (filename, data, mime),
        })
        response = self.session.post('https://www.googleapis.com/upload/drive/v3/files',
            params={'uploadType': 'multipart', 'fields': 'id,name', 'supportsAllDrives': 'true'},
            data=mp, headers={'Content-Type': mp.content_type}, timeout=45)
        if not response.ok:
            raise RuntimeError(f'Drive upload failed ({response.status_code}). Enable Drive API and share the folder with your service-account email as Editor.')
        image_id = response.json().get('id')
        if not image_id:
            raise RuntimeError('Drive upload returned no file ID')
        return image_id

    def read(self, file_id):
        if not file_id:
            return None
        response = self.session.get('https://www.googleapis.com/drive/v3/files/' + quote(str(file_id), safe=''),
            params={'alt': 'media','supportsAllDrives': 'true'}, timeout=25)
        response.raise_for_status()
        return response.content
