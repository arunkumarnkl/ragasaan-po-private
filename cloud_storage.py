"""Persistent company logo in GitHub assets, referenced from PO_Settings.

No Google Drive / Cloud Storage connection is needed. Old setting names are
not used for new writes; the settings table remains backwards compatible.
"""
from __future__ import annotations
import io
from PIL import Image,UnidentifiedImageError
from persistent_images import PersistentImages

LOGO_SETTING='Company_Logo_GitHub_Path'
SETTINGS_HEADERS=['Setting','Value']

def logo_drive_id(settings):
    return str((settings or {}).get(LOGO_SETTING,'')).strip()

def validate_logo(data,filename):
    if not data or len(data)>950_000:raise ValueError('Logo must be under 950 KB for GitHub storage')
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ('PNG','JPEG') or im.width*im.height>16_000_000:
                raise ValueError('Use a PNG/JPG logo smaller than 16 megapixels')
            mime='image/png' if im.format=='PNG' else 'image/jpeg'
    except (UnidentifiedImageError,OSError) as exc:
        raise ValueError('Not a valid PNG or JPG logo') from exc
    return mime,'ragasaan_logo.png' if mime=='image/png' else 'ragasaan_logo.jpg'

def settings_with_value(rows,name,value):
    existing=[dict(r) for r in rows if str(r.get('Setting','')).strip()!=name]
    if value:existing.append({'Setting':name,'Value':value})
    return existing

def save_cloud_logo(store,settings_rows,folder_id,filename,data,client_class=PersistentImages,bucket=''):
    mime,name=validate_logo(data,filename)
    img_path=client_class(store.credentials).upload('logo',name,data,mime)
    # Asset path is stored in PO_Settings so it persists over redeployments.
    rows=settings_with_value(settings_rows,LOGO_SETTING,img_path)
    headers=SETTINGS_HEADERS+(['Purpose'] if any('Purpose' in row for row in settings_rows) else [])
    store.save_table('PO_Settings',rows,headers)
    return img_path

def clear_cloud_logo(store,settings_rows):
    rows=settings_with_value(settings_rows,LOGO_SETTING,'')
    headers=SETTINGS_HEADERS+(['Purpose'] if any('Purpose' in row for row in settings_rows) else [])
    store.save_table('PO_Settings',rows,headers)

def fetch_cloud_logo(settings,credentials,client_class=PersistentImages,bucket=''):
    path=logo_drive_id(settings)
    if not path:return None
    try:return client_class(credentials).read(path)
    except (RuntimeError,ValueError):return None
