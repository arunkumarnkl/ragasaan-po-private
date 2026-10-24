# Ragasaan Purchase Order — Private Streamlit Community Cloud deployment

This is the **cloud-ready edition of V3.6.1**. Python modules, the category-grouped read-only Recipe Book, existing meal/alcohol formulas, Google Sheets writes, Word PO downloads, role permissions and 76 × 76 px (approximately 2 × 2 cm) drink images are retained. The cloud edition adds cloud-only configuration and persistent logo/photo storage.

## 0. Before publishing any code

- **Revoke the Google service-account key exposed in the original specification** and generate a new JSON key. Use only the new key for deployment.
- **Rotate all old or shared user passwords** using the Windows version's Admin Settings, then migrate plaintext entries to PBKDF2 hashes. Cloud app authentication still reads the live `Users` sheet. Do this before opening cloud access.
- Backup the live Google Spreadsheet. Never add Excel copies of Ingredients/Users, private keys, `.streamlit/secrets.toml`, venue/client data or generated order documents to GitHub.
- A **private GitHub repository is not the same thing as private access to the running app**. Confirm the Streamlit app's sharing/access settings after deployment.

## 1. Choose persistent image storage

| Choice | Who can use it? | Setup | Recommendation |
|---|---|---|---|
| **Private Google Cloud Storage bucket** | Personal Gmail OR Google Workspace | Create a bucket in Google Cloud; give the service-account email `Storage Object Admin` for **that bucket only**; add bucket name as `gcs_image_bucket` in Streamlit Secrets | **Recommended if using personal Gmail**; usage charges may apply |
| **Google Workspace Shared Drive folder** | Google Workspace with Shared Drives enabled | Enable Drive API; place an image folder inside a Shared Drive, share it with service account with write access; set folder ID in Admin Settings → Recipe images | Good if you already have Google Workspace |

**Ordinary personal My Drive folders are NOT a reliable service-account upload destination:** service accounts cannot own files or use My Drive storage quota. Do not assume sharing an ordinary personal Drive folder will enable uploads.

Existing images recorded as `drive_file_id` in `PO_Recipe_Images` will continue to load from Google Drive. New GCS images are recorded in the *same* column as `gcs://bucket/ragasaan/<object>`; the app detects the scheme. This preserves the Google Sheet structure. The company logo's permanent file ID is written to `PO_Settings` under `Company_Logo_Drive_File_ID` even when stored in GCS, so no new worksheet is required. Never move/remove the backing file until you replace its reference.

You can defer image-storage setup until after deploying: public Wikimedia Commons suggestions remain available, but **your own uploaded recipe images and persistent cloud company logo require one of the storage options above**.

## 2. Prepare a GitHub-safe code repository

1. Extract the supplied cloud-ready ZIP. Its **contents** (including `app.py`, `requirements.txt`, modules, `.streamlit/config.toml`, and `assets/`) belong at the **root** of the repository—not inside an extra ZIP folder.
2. Create a **private** repository on [GitHub](https://github.com/new), e.g. `ragasaan-po-private`.
3. Upload the application code and directory contents. GitHub's browser upload may hide dotfiles, so verify `.gitignore` and `.streamlit/config.toml` made it into GitHub. Do **not** upload `.streamlit/secrets.toml` or the JSON key.
4. Verify the repository does **not** contain business/customer spreadsheets, private credentials or `Users` data.

To use Git instead of the GitHub web uploader:

```bash
git init
git add .
git status  # check for secrets before committing!
git commit -m "Ragasaan private cloud deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ragasaan-po-private.git
git push -u origin main
```

## 3. Set up a private Google Sheets connection

1. In Google Cloud Console, enable **Google Sheets API** for the service-account project. Enable **Google Drive API** only if using Shared Drive photos. For GCS uploads, enable **Cloud Storage API** and grant the service account bucket-level Storage Object Admin.
2. Share the existing Google Spreadsheet with the **new service account's `client_email`** as **Editor**.
3. On **your own Windows PC** (never in GitHub), open Command Prompt in the extracted app folder and run:

```bat
py prepare_cloud_secrets.py "C:\\path\\to\\new-service-account.json"
```

If you created a private Cloud Storage bucket:

```bat
py prepare_cloud_secrets.py "C:\\path\\to\\new-service-account.json" --gcs-bucket YOUR_BUCKET_NAME
```

This generates `.streamlit/secrets.toml` *locally* (the Git `.gitignore` excludes it). Open that file in Notepad and copy its **complete** contents into Streamlit Cloud Secrets. Keep the private key out of emails, screenshots and GitHub.

If you already have a local secrets file, `prepare_cloud_secrets.py` refuses to overwrite it; explicitly delete or back it up first, or use `--force` once you're sure.

## 4. Deploy the app privately

1. Visit [share.streamlit.io](https://share.streamlit.io) and log in with GitHub. Connect private repository permissions if prompted.
2. Choose **Create app → Yup, I have an app**.
3. Select your **private repository**, `main` branch, and `app.py` as the entrypoint.
4. Under **Advanced settings**, select **Python 3.12** (supported and tested by the platform), and **paste the entire locally generated secrets TOML** into **Secrets**. Ensure `deployment_mode = "cloud"`.
5. Deploy, then open the Streamlit app's **Settings → Sharing/Access** and confirm the running app is **private**. Do not invite people who do not need access. Streamlit private viewers must authenticate with their invited identity. Remember that the Ragasaan app has its *own* additional `Users` login.
6. First sign in as an existing Admin to verify the live sheets. Verify the application can load `Ingredients`, `Recipe`, `PO_Rules`, `PO_Alcohol_Matrix`, `PO_Settings`, `Users` and the optional image/pricing tables.
7. Before doing actual purchasing, run a small test order and export one Word PO. Compare quantities and price totals against your Google Sheet, including Source changes and editable meal breakdown.

### Existing cloud logo and recipe images

**GCS users:** Set `gcs_image_bucket` in Streamlit Cloud Secrets. Under Admin Settings, upload your logo once via **Company logo — persistent cloud storage**, and upload recipe photos in **Recipe Management → Images & Drive**. No Drive folder ID is needed for GCS.

**Shared Drive users:** In Admin Settings → Recipe images, save a folder ID inside your Shared Drive. Then use the same Admin upload controls. The `supportsAllDrives` flag is enabled in the Google Drive API calls.

The Word PO embeds the uploaded logo. Private recipe images are read with the service account; they do not require a public URL. Suggested Wikimedia Commons images remain public URLs. Uploaded images are not kept on the temporary Streamlit server filesystem.

## 5. Updating, security and troubleshooting

- **Updates:** Commit new source code to `main`; Streamlit redeploys. The recipe master, image references, accounts, logo references and formulas remain in Google Sheets / your private image store.
- **Key lifecycle:** Change or revoke service-account keys in Google Cloud and replace the key contents under **Streamlit Cloud → App settings → Secrets**. The Windows Credential Manager key is separate and does not transfer to cloud.
- **Cloud cannot connect:** Check `deployment_mode = "cloud"`, `gsheet_id`, valid `[gcp_service_account]` and Spreadsheet Editor sharing. The cloud app intentionally **does not offer a JSON-key upload through the browser**.
- **Cloud images fail:** Shared Drive storage needs Drive API and access; Cloud Storage needs the correct bucket name and IAM role. No image upload is attempted until Admin requests it.
- **Old photos fail after switching to GCS:** Existing Drive-file IDs still require Drive API and access. To migrate them, re-upload or reset those image overrides.
- **Logo disappeared:** Verify `Company_Logo_Drive_File_ID` exists in `PO_Settings` and the backend file still exists. A missing or inaccessible logo is omitted from the Word output; purchasing calculations remain available.
- **Quotas / latency:** Google Sheets access is cached for 60 seconds. Avoid repeatedly clicking refresh. Streamlit Community Cloud apps can sleep when idle.
- **Backup:** Make independent Google Sheet backups regularly; accidental spreadsheet edits are **not** fixed by redeploying the app. Back up any GCS/Shared Drive images independently if required.
- **Availability / costs:** Community Cloud is intended for relatively lightweight apps and has resource limits; Google Cloud Storage may have billing charges. Free service and private-app policies can change. Check provider terms before depending on it operationally.

## Test status

Local Python tests and syntax checks run on the cloud-ready source. **A live Cloud deployment, real service-account connection, private GCS/Shared Drive uploads and cross-session persistence have not been tested** because they require your Google/GitHub account access. Configure them and run the checks described above before using the system for real supplier orders.
