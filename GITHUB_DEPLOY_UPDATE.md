# Ragasaan PO — update your existing Streamlit Cloud / GitHub deployment

**This is a PATCH, not a second complete application.** Replace/add these files
in the same private repository that already runs your old Google-linked app.
Keep existing business logic modules and `app.py` entrypoint in the root.

## Before changing the app

1. Confirm your GitHub repository is **Private**. The new `database/` files
   contain contact/vendor/business information. Do not upload them to a public repo.
2. Make a backup of the existing GitHub repository and live Google spreadsheet.
3. The included JSON seed reflects the last spreadsheet copy provided for this
   project (V3.3); it may **not** include later live Google Sheet changes.
   If your live spreadsheet has more recent edits, export it as `.xlsx` and run:

   ```powershell
   python migrate_excel_to_github.py "latest-export.xlsx"
   ```

   This updates local `database/*.json` using your latest workbook, **except
   Users/passwords**, which are deliberately never imported. Upload the updated
   `database/` instead of the provided snapshot.
4. Prepare a NEW administrator password. On your Windows PC with the existing
   app's dependencies installed, run:

   ```powershell
   python create_admin_hash.py
   ```

   Copy the printed hash, not your actual password. `database/users.json`
   contains no plaintext or legacy accounts. The first sign-in will use the
   bootstrap administrator defined in Streamlit Secrets. Create new hashed
   users in Admin Settings later.

## Replace/add files in your existing GitHub repository

Use the folders/paths exactly as provided in this patch ZIP. In GitHub's UI,
use **Add file -> Upload files** for new files. To replace an existing file,
open it and edit/replace it, or use GitHub Desktop / git. Keep the existing
`app.py` as the Streamlit entrypoint; the patch replaces that file in-place.

### Changed existing paths

- `app.py`
- `sheet_store.py`
- `persistent_images.py`
- `cloud_storage.py`
- `recipe_management.py`
- `ui_theme.py`
- `po_auth.py` (hashed logins only)
- `recipe_images.py` (removes obsolete Google Drive image provider)
- `logo_store.py` (removes legacy Google Drive fallback)
- `requirements.txt`
- `.streamlit/config.toml`
- `.streamlit/secrets.toml.example`
- `.gitignore`

### New paths

- `database/*.json` (12 JSON data files)
- `create_admin_hash.py`
- `migrate_excel_to_github.py`
- `tests/test_github_only.py` (new)
- `tests/test_cloud_deployment.py`, `tests/test_v34.py`, `tests/test_v352.py` (updated obsolete expectations)
- `GITHUB_DEPLOY_UPDATE.md`

**No private JSON key, GitHub token, administrator password, or plaintext
Google workbook passwords are included in this patch.**

### Remove obsolete Google integration files (optional clean-up)

You may remove `prepare_cloud_secrets.py` and old `CLOUD_DEPLOYMENT.md` /
`START_HERE_CLOUD.md` files after GitHub migration is confirmed. Old Google
service-account settings can then be deleted from Streamlit Secrets.
Existing `po_logic.py`, `po_v3_logic.py`, `po_word.py`, `recipe_book_view.py`,
`calculation_guide.py`, etc. must **remain** in the repository.

## Choose a data branch (recommended)

Once the changed files and `database/` are pushed to `main`:

1. In the GitHub repository, open the branch selector currently showing `main`.
2. Enter `po-data` and select **Create branch: po-data from main**.
3. Keep Streamlit Cloud deploying app code from `main`.
4. Put `github_branch = "po-data"` in Streamlit Cloud Secrets.

Admin edits will now commit to `po-data`, avoiding a code redeployment for
every recipe or ingredient edit. The code files remain on `main`.

If you prefer a single branch, use `github_branch = "main"`. This works, but
GitHub commits from Admin may trigger a Streamlit redeploy.

## Generate a GitHub access token

In [GitHub token settings](https://github.com/settings/personal-access-tokens/new),
create a **fine-grained personal access token** restricted to your Ragasaan
repository. Grant **Repository permissions -> Contents: Read and write**.
Do not grant all-repository access unnecessarily. Copy the token immediately;
GitHub won't show it again. The token should be treated like a password.

## Change the secrets of your EXISTING Streamlit Cloud app

Go to https://share.streamlit.io -> find your existing Ragasaan app ->
**Settings -> Secrets**. Replace the Google configuration with:

```toml
deployment_mode = "cloud"
github_repo = "YOUR_USERNAME/YOUR_PRIVATE_REPO"
github_branch = "po-data"
github_token = "PASTE_YOUR_FINE_GRAINED_TOKEN_HERE"
bootstrap_admin_username = "YOUR_NEW_ADMIN_USERNAME"
bootstrap_admin_password_hash = "pbkdf2_sha256$...FROM_CREATE_ADMIN_HASH_PY..."
```

These are private Streamlit Secrets, **not** a file to commit into GitHub.
The app uses only GitHub after the change. Keep old Google credentials until
GitHub migration is verified, then revoke/delete unused keys securely.

## Launch and verify

Refresh the existing `*.streamlit.app` URL and log in with the new bootstrap
administrator username and password. You should see **GitHub · Private data
repository** in the left sidebar. Use **Appearance → Dark** to test dark mode,
or **Auto** to follow the browser/system theme.

Check:

- Recipe Book categories, separate ingredient/quantity lines, 2 × 2 cm images
- Alcohol calculation for Grey Goose, wine and beer cases
- Water bottle/case conversions and one sample source-wise PO
- Word download with the logo/title and meal breakdown
- Admin edit of one harmless test recipe note; refresh and confirm it persists
- Add a new hashed administrator account under Admin Settings
- Upload a new recipe photo or logo to GitHub and confirm it survives refresh

Images previously stored *only* as private Google Drive IDs cannot be loaded
without Google. Re-upload them once under Admin → Recipe Management → Images;
new files will be committed to `assets/recipes/` on `po-data`.

## GitHub-specific limitations

- All writes are Git commits, so it is best for mostly single-user, low-rate
  editing rather than frequent concurrent database transactions.
- Concurrent edits to the same file are rejected when its GitHub SHA changes;
  refresh before retrying. There is no multi-file database transaction.
- The private GitHub token must remain valid and have Contents write access.
- For a private repo, the app must also be private under Streamlit Sharing.
- Media is compressed to JPEG under 950 KB for the GitHub Contents API.
- Live GitHub permissions and the actual Streamlit browser layout have not been
  verified with your account in this build.
