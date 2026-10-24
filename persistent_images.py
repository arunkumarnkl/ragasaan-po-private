"""Persistent private image storage: Google Workspace Shared Drive or GCS bucket.

Cloud Storage is optional, useful for personal Gmail accounts without Shared Drives.
The metadata stays in existing Google Sheets fields; no schema migration is needed.
"""
from __future__ import annotations
from urllib.parse import quote, urlsplit
from uuid import uuid4
import re
from recipe_images import GoogleDriveImages

_BUCKET_RE=re.compile(r'^[a-z0-9][a-z0-9._-]{2,221}[a-z0-9]$')


class PersistentImages:
    def __init__(self,credentials,bucket=''):
        self.credentials=dict(credentials)
        self.bucket=str(bucket or '').strip()
        if self.bucket and not _BUCKET_RE.fullmatch(self.bucket):
            raise ValueError('Invalid Cloud Storage bucket name')

    def _session(self):
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import AuthorizedSession
        creds=Credentials.from_service_account_info(self.credentials,scopes=[
            'https://www.googleapis.com/auth/devstorage.read_write'])
        return AuthorizedSession(creds)

    def upload(self,folder_id,filename,data,mime):
        if not self.bucket:
            return GoogleDriveImages(self.credentials).upload(folder_id,filename,data,mime)
        ext={'image/jpeg':'jpg','image/png':'png','image/webp':'webp'}.get(mime)
        if ext is None:raise ValueError('Unsupported image MIME type')
        # Unique object names avoid overwriting another user's upload.
        name=f'ragasaan/{uuid4().hex}.{ext}'
        res=self._session().post(
            f'https://storage.googleapis.com/upload/storage/v1/b/{quote(self.bucket,safe="")}/o',
            params={'uploadType':'media','name':name},data=data,
            headers={'Content-Type':mime},timeout=45)
        if not res.ok:
            raise RuntimeError(f'Private image upload failed (HTTP {res.status_code}); confirm Storage Object Admin on the bucket')
        return f'gcs://{self.bucket}/{name}'

    def read(self,file_id):
        file_id=str(file_id or '').strip()
        if not file_id:return None
        if not file_id.startswith('gcs://'):
            return GoogleDriveImages(self.credentials).read(file_id)
        raw=file_id[6:]
        bucket,sep,name=raw.partition('/')
        if not sep or not name or not self.bucket or bucket!=self.bucket:
            raise ValueError('Cloud Storage bucket mismatch or invalid object path')
        res=self._session().get(
            f'https://storage.googleapis.com/storage/v1/b/{quote(bucket,safe="")}/o/{quote(name,safe="")}',
            params={'alt':'media'},timeout=25)
        res.raise_for_status()
        return res.content
