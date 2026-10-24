# Why the old V3.3 app did not advance

The V3.3 loader requires `Ingredients.price_basis` for every ingredient, but the default configuration import installs only PO_Rules, PO_Alcohol_Matrix, PO_Settings and PO_Supplier_Prices. When the original Ingredients master has no price_basis column, the loader raises an exception and calls st.stop(), hiding all five main tabs.

This patch exposes the specific error and adds a safe, ID-matched repair that updates only missing Ingredients.price_basis cells. Existing product names, formulas, units, sources, bottle size, yield, case size and prices remain untouched. If any live ingredient ID has no corresponding row in the updated workbook, it stops without writing.

After a successful configuration/price_basis repair, the app invalidates its cached Google Sheets data and calls st.rerun(), displaying the main navigation tabs. It also offers a manual Retry button.

Files affected: app.py, startup_repair.py, sheet_store.py, README.md, tests/test_v33.py.

Security: service account remains in OS keyring/Streamlit secrets. No credentials or live spreadsheet data bundled.
