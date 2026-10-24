"""Generate a LOCAL .streamlit/secrets.toml from a service-account JSON key.

Usage: python prepare_cloud_secrets.py /secure/path/new-key.json
NEVER commit the generated file. Paste its content into the private Streamlit Cloud
Advanced settings → Secrets field, then delete any temporary key copies.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

DEFAULT_SHEET_ID='1uRbY-CehE2s9oVXRYkdSl6qcLIaYDYTfGXzFgGT4cmw'
JSON_KEYS=('type','project_id','private_key_id','private_key','client_email','client_id',
           'auth_uri','token_uri','auth_provider_x509_cert_url','client_x509_cert_url','universe_domain')


def secrets_content(credentials,sheet_id=DEFAULT_SHEET_ID,bucket=''):
    if not isinstance(credentials,dict) or credentials.get('type')!='service_account':
        raise ValueError('Expected a Google service-account JSON key')
    for field in ('client_email','private_key','project_id'):
        if not credentials.get(field):
            raise ValueError(f'Missing Google service-account field: {field}')
    if not str(credentials['private_key']).startswith('-----BEGIN PRIVATE KEY-----'):
        raise ValueError('The private key does not appear to be valid')
    if not str(sheet_id).strip():raise ValueError('Google Sheet ID cannot be blank')
    rows=['# PRIVATE. NEVER commit this file to GitHub.',
          'deployment_mode = "cloud"',
          'gsheet_id = '+json.dumps(str(sheet_id).strip()),
          'gcs_image_bucket = '+json.dumps(str(bucket or '').strip()),
          '', '[gcp_service_account]']
    for key in JSON_KEYS:
        if credentials.get(key) is not None:
            rows.append(key+' = '+json.dumps(str(credentials[key]),ensure_ascii=True))
    return '\n'.join(rows)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser(description='Prepare private Streamlit Cloud secrets locally')
    parser.add_argument('json_key',type=Path,help='NEW service-account key JSON (not an old exposed key)')
    parser.add_argument('--sheet-id',default=DEFAULT_SHEET_ID)
    parser.add_argument('--gcs-bucket',default='',help='Optional private Cloud Storage bucket (personal Gmail-compatible)')
    parser.add_argument('--force',action='store_true',help='Replace an existing local secrets.toml')
    args=parser.parse_args(argv)
    target=Path(__file__).resolve().parent/'.streamlit'/'secrets.toml'
    if target.exists() and not args.force:
        parser.error(f'{target} exists. Refusing to overwrite without --force.')
    payload=json.loads(args.json_key.read_text(encoding='utf-8'))
    result=secrets_content(payload,args.sheet_id,args.gcs_bucket)
    target.parent.mkdir(exist_ok=True,parents=True)
    # Exclusive write unless --force; avoid partial content.
    if args.force:
        target.write_text(result,encoding='utf-8')
    else:
        with target.open('x',encoding='utf-8') as f:f.write(result)
    if os.name=='posix':target.chmod(0o600)
    print(f'Created {target}. This file contains a private key: do not upload it to GitHub.')
    print('In Streamlit Cloud: Create app > Advanced settings > Secrets; paste the TOML from this file.')
    print('Only store the key in Streamlit Cloud Secrets, not in the app interface.')


if __name__=='__main__':main()
