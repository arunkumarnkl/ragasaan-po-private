"""Private GitHub repository-backed data store for Ragasaan PO.

Data is JSON row matrices in database/*.json. The public Streamlit interface
never receives the GitHub token, which belongs in the deployment Secrets.
The adapter preserves the original spreadsheet repository API.
"""
from __future__ import annotations
import base64
import io
import json
import os
import re
from pathlib import Path
from urllib.parse import quote
import requests

SHEET_ID = "github-only"  # Compatibility with old application import.
TABS = ["Users", "Ingredients", "Recipe", "Vendor Data", "Contacts", "Venue"]
TABLE_PATHS = {
    "Users":"database/users.json",
    "Ingredients":"database/ingredients.json",
    "Recipe":"database/recipe.json",
    "Vendor Data":"database/vendor_data.json",
    "Contacts":"database/contacts.json",
    "Venue":"database/venue.json",
    "PO_Rules":"database/po_rules.json",
    "PO_Alcohol_Matrix":"database/po_alcohol_matrix.json",
    "PO_Settings":"database/po_settings.json",
    "PO_Supplier_Prices":"database/po_supplier_prices.json",
    "PO_Recipe_Notes":"database/po_recipe_notes.json",
    "PO_Recipe_Images":"database/po_recipe_images.json",
}


def safe_cell(value):
    if value is None:return ""
    if isinstance(value,(bool,int,float,str)):return value
    if hasattr(value,'item') and callable(value.item):
        try:return safe_cell(value.item())
        except (TypeError,ValueError):pass
    return str(value)


class GitHubStore:
    """Read and commit GitHub Contents API files with SHA-based conflict detection."""
    writable=True
    def __init__(self, repo: str, token: str, branch: str = 'main', *, session=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',str(repo or '')) or any(part in ('.','..') for part in str(repo).split('/')):
            raise ValueError('Set github_repo as owner/repository in Streamlit Secrets')
        if not token or not isinstance(token,str):
            raise ValueError('Set github_token in Streamlit Secrets')
        if not re.fullmatch(r'[A-Za-z0-9_./-]{1,160}',str(branch)) or '..' in str(branch):
            raise ValueError('Invalid GitHub branch')
        self.repo=repo
        self.branch=branch
        self.credentials={'repo':repo,'token':token,'branch':branch}
        self.session=session or requests.Session()
        self.base=f'https://api.github.com/repos/{repo}/contents/'

    def _request(self,method,path,**kwargs):
        if path.startswith('/') or '..' in Path(path).parts:
            raise ValueError('Unsafe repository path')
        url=self.base+quote(path,safe='/')
        headers={'Authorization':'Bearer '+self.credentials['token'],
                 'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28'}
        response=self.session.request(method,url,headers=headers,timeout=30,**kwargs)
        if response.status_code==404 and method=='GET':return None
        if response.status_code in (409,422) and method=='PUT':
            raise RuntimeError(f'GitHub file changed during your edit ({response.status_code}). Refresh data and retry; nothing was overwritten.')
        if not response.ok:
            raise RuntimeError(f'GitHub {method} {path}: HTTP {response.status_code}. Check repository token permissions and branch.')
        return response.json()

    def read_bytes(self,path):
        meta=self._request('GET',path,params={'ref':self.branch})
        if not meta:return None,None
        if meta.get('type')!='file':raise ValueError(f'{path} is not a file')
        content=meta.get('content')
        if not isinstance(content,str):
            raise ValueError(f'{path} is too large for GitHub Contents API; keep JSON files below 1 MB')
        return base64.b64decode(content),meta.get('sha')

    def write_bytes(self,path,data,*,existing_sha=None,message=None):
        if len(data)>950_000:raise ValueError(f'{path} exceeds the safe 950 KB limit. Split/archive older records.')
        payload={'message':message or f'Ragasaan PO: update {Path(path).name}',
                 'branch':self.branch,'content':base64.b64encode(data).decode('ascii')}
        if existing_sha:payload['sha']=existing_sha
        return self._request('PUT',path,json=payload)

    def _read_file(self,title):
        path=TABLE_PATHS.get(title)
        if path is None:raise ValueError(f'Unknown data table: {title}')
        data,sha=self.read_bytes(path)
        if data is None:return [],None
        try:payload=json.loads(data)
        except json.JSONDecodeError as exc:raise ValueError(f'Invalid JSON in {path}') from exc
        rows=payload.get('rows') if isinstance(payload,dict) else payload
        if not isinstance(rows,list) or any(not isinstance(row,list) for row in rows):
            raise ValueError(f'{path} must contain a matrix of rows')
        return rows,sha

    def _write_file(self,title,rows,sha):
        path=TABLE_PATHS[title]
        raw=json.dumps({'rows':rows},ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        return self.write_bytes(path,raw,existing_sha=sha)

    def read(self,title):
        return self._read_file(title)[0]

    def save_table(self,title,rows,headers):
        _,sha=self._read_file(title)
        headers=[str(h) for h in headers]
        values=[headers]+[[safe_cell(row.get(header,'')) for header in headers] for row in rows]
        return self._write_file(title,values,sha)

    def update_cells(self,title,changes):
        rows,sha=self._read_file(title)
        if not rows:raise ValueError(f'{title} has no header row')
        for r,c,value in changes:
            r=int(r);c=int(c)
            if r<1 or c<1 or r>20000 or c>5000:raise ValueError('Cell outside supported range')
            while len(rows)<r:rows.append([])
            while len(rows[r-1])<c:rows[r-1].append('')
            rows[r-1][c-1]=safe_cell(value)
        return self._write_file(title,rows,sha) if changes else None

    def append_rows(self,title,items):
        rows,sha=self._read_file(title)
        if not rows:raise ValueError(f'{title} is missing the header row')
        rows.extend([[safe_cell(x) for x in row] for row in items])
        return self._write_file(title,rows,sha) if items else None

    def delete_row(self,title,row_number):
        rows,sha=self._read_file(title)
        row_number=int(row_number)
        if row_number<3 or row_number>len(rows):raise ValueError('Cannot remove a header or missing row')
        del rows[row_number-1]
        return self._write_file(title,rows,sha)


def credentials_from_secrets(secrets):
    """No Google secrets are read, even if left in Streamlit deployment settings."""
    try:
        repo=str(secrets.get('github_repo','')).strip()
        token=str(secrets.get('github_token','')).strip()
        branch=str(secrets.get('github_branch','main')).strip()
    except (OSError,FileNotFoundError):
        repo=token='';branch='main'
    repo=repo or os.environ.get('GITHUB_REPO','')
    token=token or os.environ.get('GITHUB_TOKEN','')
    branch=branch or os.environ.get('GITHUB_BRANCH','main')
    if not repo or not token:return None
    return {'repo':repo,'token':token,'branch':branch}
