"""Private image assets stored in the same GitHub repository as the application.

Existing database field `drive_file_id` is kept for schema compatibility, but
new values are asset paths (assets/recipes/...) rather than Google Drive IDs.
"""
from __future__ import annotations
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageOps
from uuid import uuid4
import re
from sheet_store import GitHubStore

class PersistentImages:
    def __init__(self,credentials,*,bucket=''):
        self.store=GitHubStore(credentials['repo'],credentials['token'],credentials.get('branch','main'))

    def upload(self,folder_id,filename,data,mime):
        if not mime.startswith('image/') or len(data)>8_000_000:
            raise ValueError('Upload an image smaller than 8 MB')
        if mime not in ('image/png','image/jpeg','image/webp'):
            raise ValueError('Only PNG/JPG/WebP images are allowed')
        # Normalise uploads to a reasonably sized photo; no large binaries in
        # the GitHub Contents API and no original private images in app source.
        with Image.open(BytesIO(data)) as loaded:
            loaded=ImageOps.exif_transpose(loaded)
            if loaded.width*loaded.height>30_000_000:
                raise ValueError('Image resolution is too large')
            if loaded.mode in ('RGBA','LA') or (loaded.mode=='P' and 'transparency' in loaded.info):
                rgba=loaded.convert('RGBA')
                bg=Image.new('RGB',rgba.size,'white')
                bg.paste(rgba,mask=rgba.getchannel('A'))
                loaded=bg
            else:
                loaded=loaded.convert('RGB')
            raw=None
            for dimension in (1100,900,700,500):
                picture=loaded.copy();picture.thumbnail((dimension,dimension))
                for quality in (84,72,58):
                    temp=BytesIO()
                    picture.save(temp,format='JPEG',quality=quality,optimize=True)
                    if len(temp.getvalue())<950_000:
                        raw=temp.getvalue();break
                if raw is not None:break
            if raw is None:raise ValueError('Could not compress image for GitHub')
        stem=re.sub(r'[^a-zA-Z0-9_-]+','-',Path(filename).stem).strip('-')[:60] or 'image'
        subdir='logo' if folder_id=='logo' else 'recipes'
        path=f'assets/{subdir}/{stem}-{uuid4().hex[:12]}.jpg'
        data=raw
        self.store.write_bytes(path,data,message='Ragasaan PO: add recipe image')
        return path

    def read(self,file_id):
        if not str(file_id).startswith(('assets/recipes/','assets/logo/')):
            return None  # Legacy Drive IDs cannot be fetched without Google.
        payload,_=self.store.read_bytes(str(file_id))
        return payload
