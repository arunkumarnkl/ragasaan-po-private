# Ragasaan Purchase Order — Streamlit V3.5

V3.5 builds on V3.4 and retains the existing Google Sheets connection, calculation
rules, image suggestions and Admin image-upload functionality.

## V3.5 features

- **Recipe Book:** one row split into three visual columns: drink title above photo;
  ingredients and quantity; garnish and glassware with quantity. Garnish and glasses
  are classified from `Ingredients.category`; ingredient IDs, recipe matrix columns,
  quantities and admin inline-save behavior are unchanged.
- **Bartenders role:** add or reset a user to **Bartenders** in Admin Settings →
  Users & diagnostics. When that user logs in, only the **read-only Recipe Book**
  is rendered. There are no Calculation, Purchase Order or Admin tabs. Existing
  Admin and Standard user roles keep their earlier access. Passwords for new
  users are written as PBKDF2-SHA256 hashes (not plaintext) to `Users`.
- **Alcohol Package:** starts with exactly **20 entry lines**, prefilled with
  available alcohol categories from the Google Sheet. Use **＋ Add alcohol item**
  to add more lines, or × to delete individual entries. All quantities and pack
  factors continue to come from Sheets.
- **PO preview:** one table within each Source section (Supplier/Majestics/Unit),
  with bold category header rows inside the table and a single Name/Qty/Unit/Remarks
  set of columns. No repeated Item title under category groups.
- **Alcohol inventory Word page:** when included, appends all alcoholic products
  **actually purchased from that source**, regardless of whether the item came
  from an alcohol guide, a manual selection or a recipe. Groups Beer, Wine &
  Sparkling, and Spirits & Liqueurs. Includes whisky, vodka, rum, gin, tequila,
  cognac and liqueurs; each product has its own ruled stock-count row.
  Opening stock is calculated as PO quantity × current purchasable pack factor.
  It remains source-specific and part of the Word PO (no extra download).

**No change to the Google Sheet schema is required for these V3.5 changes.**
Google Sheets remains the source of truth for ingredient categories, purchases,
case sizes, yields, prices and formulas. No workbook upload is required when
upgrading from an already configured V3.4 installation.

**Important:** Do not copy a new `Users` worksheet over your live one when
installing V3.5. Create Bartenders accounts through Admin Settings so the existing
accounts, passwords and roles are preserved.

**Verification:** `py -m pytest -q tests`; includes new V3.5 regression tests.
Visual Word output was rendered and reviewed. Live Streamlit and authenticated
Google Sheets writes were not exercised in this packaging environment.

---

# Ragasaan Purchase Order — Streamlit V3.4

This internal-use Streamlit application reads **live Google Sheets**. Ingredients, suppliers, recipes, pack sizes, yields, guest calculation formulas, alcohol guest-band values, alcohol guide-to-bottle multipliers, settings and prices are data-driven: **do not edit Python code to change an ingredient's case size or guest ratio.**

## Install and connect on Windows

1. Extract the ZIP to a folder, e.g. `C:\Ragasaan_PO`.
2. Double-click `install_windows.bat` (first time) and then `start_windows.bat`. Alternatively run `py -m pip install -r requirements.txt` and `py -m streamlit run app.py`.
3. The first-run connection screen accepts a **new** Google service-account JSON key. Share your Google Spreadsheet with that service account as **Editor**. Check **Remember securely on this computer** to save the key to Windows Credential Manager (via `keyring`), not as a regular JSON file. The app then connects automatically at subsequent launches. A server/cloud installation should use Streamlit secrets rather than a local Windows vault.
4. Log in using a user from the Google Sheet's `Users` tab. Administrator permissions are required for spreadsheet edits, prices, backups and configuration sync.
5. **Important: V3.3 requires new configuration fields and tabs.** The supplied `MYPOspreadsheetNEW_V3_3_Updated.xlsx` is a *template/copy*, **not an already-synced live Google Sheet**. Sign in as Admin and import its configuration tabs (`PO_Rules`, `PO_Alcohol_Matrix`, `PO_Settings`, `PO_Supplier_Prices`) via **Admin Settings → Vendors, Venues, Contacts → Sync revised calculation workbook**. If configuration is missing and the main screen cannot load, Admins are offered a one-time **Install updated calculation tabs** import in the error screen. Back up the live Sheet before overwriting.
6. Your `Ingredients` tab must include `price_basis` (`Pack` or `Single`). **Do not overwrite the whole Ingredients master just to add this field.** If the app remains on the one-time setup screen after syncing the four configuration tabs, use the **Repair Ingredients.price_basis only** button in the updated recovery screen. Upload `MYPOspreadsheetNEW_V3_3_Updated.xlsx`, confirm that you backed up the live Sheet, and click repair. The app matches existing Ingredient IDs and writes *only* previously missing/invalid `price_basis` cells; bottle sizes, yields, case sizes, pricing and item names are preserved. If a live ingredient is absent from the uploaded template, the repair will stop and list its ID rather than guess a price basis. The app then automatically reopens the main tabs if all required configuration is present.

**Security:** Revoke the service-account private key exposed in the original specification, create a new key, and never post keys or password files publicly. Change legacy plaintext `Users` passwords in the Admin user interface before running the app on a shared host. The app has not been live-tested against your Google account; test with a spreadsheet copy before ordering.

## V3.3 startup navigation fix (when stuck on one-time setup)

The old app blocked the main navigation if `Ingredients.price_basis` was absent, even after you installed `PO_Rules`, `PO_Alcohol_Matrix`, `PO_Settings` and `PO_Supplier_Prices`. This ZIP fixes that flow.

1. Stop the previous Streamlit terminal using Ctrl+C; extract this ZIP into a new folder and run `start_windows.bat` (or `streamlit run app.py`). The saved Google connection remains available if it was stored in Windows Credential Manager.
2. Sign in as Admin. If your four configuration tabs are already present, you will see a setup error for the missing `price_basis` column. The screen now includes a **Retry opening main application** button and a repair option.
3. In the setup screen, choose `MYPOspreadsheetNEW_V3_3_Updated.xlsx` under **V3.3 updated workbook**. Make a Google Sheets backup first (**File → Download → Microsoft Excel (.xlsx)** in Google Sheets is one option); tick the backup/authorisation checkbox.
4. Click **Repair Ingredients.price_basis only**. Do not click the option to replace the entire Ingredients worksheet. The app patches only missing values keyed by ingredient ID, then refreshes and opens the main navigation tabs automatically.
5. If the four configuration tabs were *not* installed, leave the four configuration tabs selected and check **Also repair only missing Ingredients.price_basis values**, then click **Install selected tabs and open app**. This combines both changes in one pass.
6. If the screen still reports a problem, read the specific error displayed above the repair controls and use **Retry opening main application** after addressing it. A Sheets API 429 means a Google quota limit may have been reached; do not repeatedly refresh rapidly.

This recovery interface writes to your own live Google Sheet **only after explicit Admin actions**. It does not back up or modify the Sheet automatically. No live Google Sheets writing was tested during package creation.

## Source-of-truth tables

| Google Sheet | What it defines |
|---|---|
| `Ingredients` / `IngredientsTbl` | Ingredient ID, item, category, Bottle Size, unit, Source, Yield, case size, unit_price, price_basis |
| `Recipe` | Drink category in column A, drink name in B, ingredient ID matrix in subsequent columns |
| `PO_Rules` | Breakfast/lunch/dinner formulas, ingredient IDs, package choice and `quantity_basis` (`Individual` or `Purchase`) |
| `PO_Alcohol_Matrix` | Category/service/guest bands, `guide_unit`, `bottles_per_guide_unit` |
| `PO_Settings` | Guests per table, VAT, default juices, alcohol variant shares, company name |
| `PO_Supplier_Prices` | Optional prices per Source and ingredient, with `Pack` or `Single` price basis |
| `Vendor Data`, `Venue`, `Contacts`, `Users` | Supplier, delivery and login data |

Use **Admin Settings → How calculations work** to inspect the *current live values* for every category, along with formula symbols, case-size conversions, measured/portion garnish, rack/roll glassware, alcohol guide units and pricing. For editable formulas go to **Editable formula settings**.

## Quantities and formulas

- **Meal-based Water, Soft Drinks, Juices, Mixers**: each `PO_Rules.formula` is interpreted using its `quantity_basis` column. `Individual` means raw *individual bottles/items*, e.g. a table-water bottle count. `Purchase` means raw *fractional purchase units* (case/bottle/rack depending on Source/Case Size). For `Purchase`, raw individual demand = formula result × **PACK**; for `Individual`, raw individual demand = formula result. **PACK is derived from the ingredient's current case size and source, not a constant in Python.** This prevents accidentally treating bottles as cases or dividing twice.
- Formula variables: `GST` = meal guest count, `TBL` = meal tables, `PACK` = current purchasing-pack factor, `BOTTLE` = Bottle Size, `YIELD` = Yield, `B_GST` and `L_GST` = breakfast/lunch guests. Eligible formulas use numerical arithmetic, `min`, `max`, `ceil` and `round`; they are validated by a safe arithmetic interpreter.
- **Cocktail/mocktail liquids**: recipe amount × servings ÷ Bottle Size = individual bottles/packs. **Portion garnish**: recipe portions × servings ÷ Yield. **Glassware**: recipe glass count × servings = individual glasses; case size provides number of glasses per rack/roll.
- **Alcohol**: interpolate the configured guest-band guide values; multiply by `PO_Alcohol_Matrix.bottles_per_guide_unit` to obtain **individual bottles**, then apply current ingredient purchasing units. The supplied V3.3 workbook has wine/champagne guide values expressed in cases of 6, beer in cases of 24, and spirits/liqueurs in bottles. **Those numerical multipliers come from the Sheet, not Python.** Reception Only/Whole Evening and Table/Bar services are matched to the matrix. Unsupported alcohol categories require a manually entered number of bottles.
- **PO consolidation:** combine raw individual demand for the same ingredient across meals, cocktails and alcohol *before* rounding. Final PO Qty = `ceil(total singles / PACK)`. Source `Unit` generally orders individual items, but glassware ordered in racks/rolls uses its configured case size. If `case size = 1`, the unit is **Bottle** for bottled liquids or **Unit** for other products, not Case.
- **Pricing:** `PO_Supplier_Prices` override takes precedence for the matching `(Source, ingredient_id)`; otherwise the app uses `Ingredients.unit_price` and `price_basis`. VAT uses `PO_Settings.Default_VAT_Percent`. All costs are estimates until suppliers confirm them.

## V3.4 screens and workflow

1. **Recipe Book:** Search by name, filter by category, select a recipe, and edit its ingredient amounts **inline on the same screen** (Admins only). Every selected drink gets an online image *suggestion* from **Wikimedia Commons** where the Commons search returns a suitable photograph. The image is not guaranteed to exactly depict your recipe; check it before use. The image's source and licence are shown when available. Admins may save a suggested image, paste an HTTPS image URL, or upload their own photo to Google Drive for that recipe.
2. **Calculation:** The compact left column contains Guests & Table Planning and six cocktail/mocktail selections (three-digit servings inputs). The right column contains Alcohol Package selection and an **editable Meal-wise Breakdown**. The old separate `Live calculation · editable guide and quantities` section and the separate Alcohol tab are removed. Live, sheet-driven formulas remain editable through Admin Settings.
3. **Purchase Order:** Three source-wise preview columns (Supplier, Majestics, Unit), ingredient ordering grouped by Water, Juices, Soft Beverages, Mixers, Puree & Syrups, Wines, Beer, Spirits, Liqueurs and Others. Admins can override source and quantity for this order. **When Alcohol Package is disabled, alcoholic ingredients in cocktail recipes are omitted**, but their non-alcoholic mixers and garnishes remain. The Word PO shows individually **right-aligned Breakfast, Lunch, Dinner and bold Total columns**, plus Item, Unit and Remarks. Optional inventory pages are appended **only** to the relevant source Word PO when Alcohol Package is enabled; there is no separate inventory download.
4. **Admin Settings:** Source-wise pricing, data backup and import, editable calculation guides, local default logo, user administration and password migration. The `Users` sheet retains original usernames and roles. An Admin can hash all remaining legacy plaintext passwords without changing what users type at login, then individually reset/rotate passwords. Rotate exposed historical passwords even after migration.

## Recipe photo display size

Recipe photos are displayed in a fixed **2 cm × 2 cm square** (approximately **76 × 76 CSS pixels** at nominal 96 dpi), with the drink name above the image. The preview is center-cropped using `object-fit: cover` (online URLs) or Pillow (private Drive uploads); **original photos stored in Google Drive are not resized or modified**. Physical appearance can vary slightly across screens because CSS pixels are not physical centimetres.

## Recipe photo setup: recommended online images and editable Google Drive uploads

**Viewing images requires no setup.** The Recipe Book tries to find a Wikimedia Commons suggestion for the currently selected drink, using an online API with a 24-hour cache. If no match is found, a no-photo message appears rather than an invented image. Commons images often require attribution; always confirm the suggested image is relevant and observe its source licence. No image URLs are hardcoded for all recipes.

**To save/replace recipe images:**

1. For online images, open **Recipe Book**, select a drink and expand **Recipe picture**. Click **Use suggested online photo**, or supply an HTTPS image link.
2. For **your own uploads**, enable the **Google Drive API** in the Google Cloud project associated with the new service-account key. Create a dedicated image folder in Google Drive, share it with the service account as Editor, and copy the folder ID from its URL.
3. Open **Admin Settings → Recipe images · Google Drive folder setup**, enter that ID, and save it to `PO_Settings.Recipe_Image_Drive_Folder_ID`.
4. Return to **Recipe Book** and upload a PNG/JPG/WebP (max 8 MB). The application stores the Drive file ID in a separate `PO_Recipe_Images` worksheet, which it creates on first save. The Recipe matrix does not change.
5. The uploaded photo stays private. Streamlit downloads its bytes using the service account, so it works without making the Drive file public.

**Drive limitation:** Google service accounts generally cannot own new files in an individual's personal My Drive (insufficient storage quota). This implementation attempts to upload through the service account and is best suited to a properly configured **Google Workspace Shared Drive**. For personal My Drive, use the image URL option until user OAuth-based Drive uploads are available. The code reports an explicit upload error rather than claiming success. The app has not been authenticated against your Drive account in this environment.

## Password migration

From Admin Settings → **Users & diagnostics**, tick the acknowledgement and click **Hash all legacy passwords (preserve logins)**. This writes PBKDF2-SHA256 hashes back to `Users.password`, maintaining login with the same existing password. Subsequently use **Reset password and role** for each account to set a *new* strong password. Older shared/cached copies or revision histories of the spreadsheet may still expose the old passwords; restrict access and remove exposed copies where possible.

## Verification and caveats

Run `py -m pytest -q tests` from the extracted app directory. The packaged tests check sheet-driven guest rules, bottle/case/rack conversions, garnish yields, wine/beer/spirits multipliers, custom case sizes and supplier prices, and the live Admin calculation guide. No real supplier purchasing or live Google Sheets write has been performed in this build.

**Important:** For a `Purchase`-basis rule that already divides by `PACK`, the rule's output is *purchasing packs*. Do not divide it by PACK again in a downstream step. For an `Individual`-basis rule the output is *bottles/items*, divided by PACK only on consolidation. Inspect each rule's basis in **Admin Settings → How calculations work** before changing formulas.

## V3.5.2 — Colour theme and saved Google connection

The interface uses a soft navy/teal palette, pale category highlights and compact purchasing tables. To change the base colours, edit `.streamlit/config.toml`; page-specific accents are in `app.py`.

**One-time Google key configuration on Windows:** On the first connection screen, upload a newly generated service-account JSON and tick **Remember securely on this computer**. Subsequent launches automatically read the connection from the Windows OS Credential Manager via `keyring`. It remains there when you extract a newer app version as long as you use the same Windows profile. Do not save the private key inside Python source, commit it to git or include it in ZIPs. Use **Forget saved Google connection** to remove it. If the key expires or is revoked, reconnect with a new key.

---

## V3.6: Redesigned interface and all-recipes table

V3.6 keeps the same Streamlit/Python backend and Google Sheets as V3.5.2. The new navy/pastel style is implemented in `ui_theme.py` and `.streamlit/config.toml`. It is much closer to the Ragasaan visual reference while native Streamlit inputs and tabs can still differ from a pixel-perfect custom HTML/JS frontend.

**Recipe Book:** Every recipe in the Google Sheets `Recipe` tab is available in a searchable category-grouped 3-column table. Each ingredient and its quantity appear on a separate line. Drink photo sizes are fixed at 76×76 CSS pixels (approximately 2cm×2cm). Select 24, 48 or All rows to control page size. Existing saved/Drive images show automatically. To look up Commons suggestions for photos not yet saved, enable the toggle; this may take longer due to online image searches, so it is disabled by default.

**Recipe management:** All Add/Edit/Delete/Image operations now appear under **Admin Settings → Recipe Management**. Bartenders and other non-admins cannot edit recipes. When renaming or changing ingredients, only relevant Google Sheet matrix cells are modified; adding a recipe appends one row. Deletion deletes the selected Recipe worksheet row and related metadata, so **back up the Recipe sheet before deleting**. Image files in Google Drive are left untouched when an image reference or recipe is deleted.

**Purchase Order:** Choose Supplier, Majestics or Unit on the Purchase Order page. The wide table and right-side Word-style preview show that source; the three separate Word downloads remain on the same page. Event information has moved to the left sidebar and source/quantity overrides are collapsed by default. Preview totals and purchase quantities remain derived from the existing computation modules and live Sheets.

**Installation:** Extract the V3.6 archive into a **new folder** and run `start_windows.bat` (or `pip install -r requirements.txt` then `streamlit run app.py`). If your Google service-account key was saved via **Remember securely on this computer**, the new folder should read the same Windows Credential Manager entry. No additional worksheet sync or Excel upload is required for this visual update.

**Design preview:** `assets/V3_6_DESIGN_PREVIEW.html` (and PNG) shows the intended palette and general order layout with illustrative sample data; it is not a tested screenshot from a running Streamlit app.

**Default logo when upgrading:** New logo uploads are stored in `%LOCALAPPDATA%\\Ragasaan_PO\\assets` on Windows so they survive future ZIP upgrades. If your logo is only in the old V3.5.2 application folder, upload it again once under Admin Settings, or copy the existing `ragasaan_logo.png` file into V3.6 `assets/`.

## V3.6.1 display and document layout fixes

- Page titles are intentionally rendered in high-contrast cards on **Recipe Book**, **Calculation**, **Purchase Order**, and **Admin Settings**. Installing or launching Streamlit does not otherwise remove hidden headings; use this updated app version.
- **Calculation:** Meal-wise Breakdown is now below **Select - Cocktail/Mocktail** in the left column. The Alcohol Package remains on the right. The underlying guest-to-case and recipe formulas are unchanged.
- **Word PO:** Company logo and PURCHASE ORDER title are in a single header row. Breakfast, Lunch, Dinner, and Total stay separate right-aligned columns with reduced widths and cell padding.

This update does not change the Google Sheet schema or require another configuration workbook sync. Existing saved credentials continue to be used.

---

## Private Streamlit Community Cloud deployment

For cloud deployment use **`CLOUD_DEPLOYMENT.md`**. The cloud-ready application uses
`deployment_mode = "cloud"`, server-side Streamlit Secrets (no JSON upload in the
browser) and an optional private **Google Cloud Storage bucket** or **Google
Workspace Shared Drive** for durable recipe and company-logo photos. The previous
Windows startup and credential manager continue to work in local mode.
