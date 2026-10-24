# V3.5 change log

- Recipe Book: name/category above photo in first column, liquid/ingredient quantities in second, Garnish & Glasses in third. Admin edits save to the original Recipe matrix cells.
- Users: added **Bartenders** role (read-only Recipe Book, no other functional tabs); added Admin-create-user form with hashed password; role can also be set through the password reset form.
- Alcohol Package: 20 initial rows; + Add Item preserved; category preferences sourced from the connected Sheet.
- PO preview: one grouped table per Source, category-heading rows inside the table; no repeated Item headers.
- Word PO Inventory: includes every ordered alcohol item from that supplier's order, not merely items appearing in the alcohol guide; beer, sparkling and still wines, whisky, vodka, rum, gin, tequila, cognac and liqueur groups. Table Grid borders for manual entries; opening stock is current PO supply in bottles.
- All existing calculation/recipe units, source overrides, Word PO and Google Sheets configuration retained.

## Operational caveats

Inventory lists products that are present in the current source-specific PO, **not** every product in the ingredient master that was not ordered. If an item is not on the PO, it is not appended as an inventory line. No purchasing multipliers were hardcoded in this release.

## Validation

Run `py -m pytest -q tests`. Sample source-specific Word PO was rendered and visually inspected. Live Google Sheets writes and actual web UI interactions need verification on deployment.
