"""Run locally, never in GitHub Actions or a public terminal."""
from getpass import getpass
from po_auth import password_hash

if __name__=='__main__':
    pwd=getpass('Choose a new administrator password (12+ characters): ')
    if len(pwd)<12:raise SystemExit('Use at least 12 characters.')
    check=getpass('Repeat password: ')
    if pwd!=check:raise SystemExit('Passwords did not match.')
    print('\nPaste this line in Streamlit Secrets (keep the password private):')
    print('bootstrap_admin_password_hash = "'+password_hash(pwd)+'"')
