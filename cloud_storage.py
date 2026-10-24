"""Cloud-persistent company logo: private Drive file ID stored in PO_Settings.

Google Workspace Shared Drive is required for service-account uploads. Streamlit's
container filesystem is ephemeral, so never store the cloud logo there.
"""
from __future__ import annotations
import io
from PIL import Image, UnidentifiedImageError
from persistent_images import PersistentImages

LOGO_SETTING='Company_Logo_Drive_File_ID'
SETTINGS_HEADERS=['Setting','Value']


def logo_drive_id(settings):
    return str((settings or {}).get(LOGO_SETTING,'')).strip()


def validate_logo(data,filename):
    if not data or len(data)>4_000_000:
        raise ValueError('Logo must be less than 4 MB')
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ('PNG','JPEG') or img.width*img.height>16_000_000:
                raise ValueError('Logo must be a PNG/JPG under 16 megapixels')
            mime='image/png' if img.format=='PNG' else 'image/jpeg'
    except (UnidentifiedImageError,OSError) as exc:
        raise ValueError('Not a valid PNG/JPG image') from exc
    return mime, ('ragasaan_company_logo.png' if mime=='image/png' else 'ragasaan_company_logo.jpg')


def settings_with_value(rows,name,value):
    result=[dict(r) for r in rows if str(r.get('Setting','')).strip()!=name]
    if value: result.append({'Setting':name,'Value':value})
    return result


def save_cloud_logo(store,settings_rows,folder_id,filename,data,client_class=PersistentImages,bucket=""):
    """Upload first, then write the Drive ID to Google Sheets (no local disk writes)."""
    mime,safe_name=validate_logo(data,filename)
    drive_id=client_class(store.credentials,bucket=bucket).upload(folder_id,safe_name,data,mime)
    store.save_table('PO_Settings',settings_with_value(settings_rows,LOGO_SETTING,drive_id),SETTINGS_HEADERS)
    return drive_id


def clear_cloud_logo(store,settings_rows):
    store.save_table('PO_Settings',settings_with_value(settings_rows,LOGO_SETTING,''),SETTINGS_HEADERS)


def fetch_cloud_logo(settings,credentials,client_class=PersistentImages,bucket=""):
    drive_id=logo_drive_id(settings)
    if not drive_id:return None
    try:
        return client_class(credentials,bucket=bucket).read(drive_id)
    except Exception:
        return None  # Missing Drive permissions should not stop purchase orders.
