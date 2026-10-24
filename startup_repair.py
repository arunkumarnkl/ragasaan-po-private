"""Plan a *column-only* migration for Ingredients.price_basis.

All price-basis values come from the administrator-supplied V3.3 workbook;
no ingredient records, quantities, case sizes, yields, or prices are replaced.
The returned 1-based cells are suitable for GoogleStore.update_cells().
"""
from po_logic import identifier

ALLOWED_PRICE_BASIS = {"Pack", "Single"}


def plan_price_basis_repair(live_grid, template_rows):
    if not live_grid:
        raise ValueError("Live Ingredients worksheet is empty.")
    headers = [str(c).strip() for c in live_grid[0]]
    if 'id' not in headers:
        raise ValueError("Live Ingredients worksheet has no 'id' column.")
    if not template_rows:
        raise ValueError("Uploaded workbook has no Ingredients data.")

    from_template = {}
    for row in template_rows:
        id_value = row.get('id', '')
        iid = identifier(id_value) if str(id_value).strip() else ''
        if not iid:
            continue
        basis = str(row.get('price_basis', '')).strip().title()
        if basis not in ALLOWED_PRICE_BASIS:
            raise ValueError(f"Uploaded Ingredients ID {iid}: price_basis must be Pack or Single.")
        if iid in from_template:
            raise ValueError(f"Uploaded Ingredients contains duplicate ID {iid}.")
        from_template[iid] = basis

    id_col = headers.index('id')
    basis_exists = 'price_basis' in headers
    basis_col = headers.index('price_basis') if basis_exists else len(headers)
    changes = []
    if not basis_exists:
        changes.append((1, basis_col + 1, 'price_basis'))

    missing_ids = []
    repaired_ids = []
    seen = set()
    for rownum, row in enumerate(live_grid[1:], start=2):
        if id_col >= len(row) or not str(row[id_col]).strip():
            continue
        iid = identifier(row[id_col])
        if iid in seen:
            raise ValueError(f"Live Ingredients contains duplicate ID {iid}.")
        seen.add(iid)
        current = str(row[basis_col]).strip().title() if basis_col < len(row) else ''
        if current in ALLOWED_PRICE_BASIS:
            continue  # preserve all already-validated price bases
        if iid not in from_template:
            missing_ids.append(iid)
            continue
        changes.append((rownum, basis_col + 1, from_template[iid]))
        repaired_ids.append(iid)

    if missing_ids:
        sample = ', '.join(missing_ids[:12])
        raise ValueError(
            f"Cannot fill price_basis for {len(missing_ids)} live ingredient ID(s) "
            f"not in the uploaded template: {sample}. Add their Pack/Single values "
            "to the workbook Ingredients tab, then retry. Nothing was written."
        )
    return changes, repaired_ids
