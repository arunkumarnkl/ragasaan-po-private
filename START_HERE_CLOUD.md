# Deploy Ragasaan PO privately — the short version

1. **Rotate exposed credentials**: revoke the old Google service-account key, create a new one, and rotate/migrate old app user passwords. Back up the spreadsheet.
2. **Create a PRIVATE GitHub repository** and upload the extracted application source. Put `app.py` and `requirements.txt` at the repository root. Never upload a JSON key, `.streamlit/secrets.toml`, Excel data or client records.
3. **Create Cloud Secrets locally**: run `py prepare_cloud_secrets.py "C:\\path\\to\\NEW-service-account.json"` (add `--gcs-bucket YOUR_BUCKET` if using private Cloud Storage). This creates a private, Git-ignored `.streamlit/secrets.toml` file.
4. **Deploy at https://share.streamlit.io** → Create app → select your private GitHub repository, `main` and `app.py` → Advanced settings → Python 3.12, paste the complete generated TOML into **Secrets** → Deploy.
5. **Check app privacy settings**: Restrict to yourself or explicitly invited people. Your own app's `Users` login still applies as another layer.
6. **Connect data**: Your `gsheet_id` and Google service-account credentials are read from Streamlit Secrets automatically; no browser JSON upload.
7. **Persistent images**: For a personal Gmail account use a private **Google Cloud Storage bucket** and grant the service account Storage Object Admin on that bucket. For Google Workspace Shared Drives, configure the Shared Drive folder ID in Admin Settings. Upload your logo once in Admin Settings and recipe photos in Recipe Management. Image IDs live in Google Sheets; binary files live in private cloud storage.
8. **Validate**: Open Recipe Book, create a test calculation, download a sample Word PO, test admin-only screens, and reboot the app to check logo/photo persistence.

**Detailed instructions and troubleshooting:** `CLOUD_DEPLOYMENT.md`.

**Status:** 71 local regression tests passed; no live deployment or authenticated cloud upload was performed in this package build.
