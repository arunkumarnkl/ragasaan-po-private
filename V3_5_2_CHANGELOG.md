# V3.5.2 — Softer Colour Theme and Compact Order Display

- Muted navy headings, soft teal buttons, pale table headers, and pastel category-group rows. Theme settings are in `.streamlit/config.toml` and CSS in `app.py`.
- PO preview quantities displayed as whole purchasing units; underlying consumption and costing are **not rounded prematurely**.
- Word PO output begins with the Google Sheets Ingredient ID, followed by Item Name, Breakfast, Lunch, Dinner, Total, Unit, Remarks. Purchase-order body has no coloured shading/borders. Alcohol inventory grid remains lined for manual stock counts.
- Alcohol entry retains its 20 default rows and + Add item, but hides the redundant Bottles and PO Qty display columns, giving more space to Item and Manual Qty.
- One-time Windows OS Credential Manager saving of the service-account JSON was already supported and remains available. Keep the key in the vault, not app source or shared archives.
