# Ragasaan Purchase Order V3.6 — Interface redesign

## Visual redesign (Option A: Streamlit)
- Dark navy Ragasaan brand header and horizontally arranged icon navigation tabs.
- Cream/white cards on a muted lavender-grey background; pastel coloured purchase category groups.
- PO workspace now displays a wider source-wise table beside a compact Word-style on-screen preview.
- Delivery venue, delivery date/time, contact, VAT and saved logo appear in the left sidebar.
- The three supplier-specific Word downloads remain available. Existing calculations, Google Sheets, roles, inventory, case-size/yield logic and exports are unchanged.
- Supplier/source and final quantity changes remain accessible in the PO tab's optional "Adjust source or order quantity" expander.

## Recipe Book (read-only)
- All recipes are accessible through one **category-grouped, searchable 3-column table**.
- Columns: Drink Name + 2 cm × 2 cm Photo | Ingredients & Quantities | Garnish & Glassware.
- Each ingredient is shown on **its own line** with its matching quantity and unit.
- Select 24, 48, or All rows; pagination is used for performance.
- Admin and Bartenders see exactly the same read-only Recipe Book. Bartenders still cannot open other functional tabs.
- Previously saved image URLs and Drive images are displayed; optional "Show recommended Wikimedia Commons images" for visible missing photos avoids a slow online lookup for all 120+ recipes whenever the page opens.

## Admin Settings → Recipe Management
- All recipe editing, adding, deleting and image replacement moved out of the Recipe Book.
- Editing preserves the wide Google Sheet's Recipe matrix structure, including ingredient-ID header rows.
- Rename, category assignment, ingredient quantity changes, new recipe and additional Recipe-header ingredient IDs supported.
- Deleting a recipe deletes its worksheet row and associated note/image references, but does not remove uploaded Google Drive files. Back up the Recipe sheet before deletion.
- Admin image tools: select Commons suggestion, HTTPS URL, or private Google Drive upload.

## Compatibility & safety
- Reuses the same Google Sheet and saved Windows Credential Manager connection (no reupload needed after a normal upgrade).
- No Google Sheet schema migration is required to install V3.6 over V3.5.2.
- No credentials or real user passwords are bundled.
- `assets/V3_6_DESIGN_PREVIEW.html` and `.png` are **illustrative visual references with sample data**, not captures from a live Streamlit run.
- Production Google Sheets writes and exact Streamlit browser appearance require user-side testing; this build was statically compiled and regression-tested.

## Default company logo across future upgrades
- New logo uploads now go to `%LOCALAPPDATA%\\Ragasaan_PO\\assets` on Windows and are loaded at future launches, even when extracting V3.7/V3.8 into a different folder.
- V3.6 still reads a logo stored inside the current app's `assets` folder for backward compatibility.
- If your V3.5.2 logo exists only inside your **old** V3.5.2 folder, upload it once in V3.6 Admin Settings or copy it manually into V3.6 `assets/` before first run. Thereafter new uploads use the shared user location.
