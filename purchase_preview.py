"""Safe, compact document-style HTML purchase order preview (no data changes)."""
from __future__ import annotations
from html import escape
from math import ceil
from po_logic import number
from po_v2_logic import category_label, ORDER_CATEGORIES


def document_preview_html(items, meta):
    vendor = 'UNIT' if str(meta.get('source','')).casefold()=='unit' else str(meta.get('vendor',''))
    rows = [
        '<div class="rag-doc-preview"><h4>🍸 Ragasaan</h4>',
        '<p>PURCHASE ORDER · '+escape(str(meta.get('po_date','')) )+'</p>',
        '<div style="display:flex;justify-content:space-between;gap:8px;font-size:10px;margin-bottom:12px">',
        '<div><strong>Supplier</strong><div>'+escape(vendor)+'</div>',
        ('<div>Party No: __________</div>' if str(meta.get('source','')).casefold()=='unit' else ''),
        '</div><div style="text-align:right"><strong>Delivery</strong><div>'+escape(str(meta.get('venue','')))+'</div>',
        '<div>'+escape(str(meta.get('delivery_date','')))+' · '+escape(str(meta.get('delivery_time','')))+'</div></div></div>',
        '<table><thead><tr><th>ID</th><th>Item</th><th>BF</th><th>LU</th><th>DI</th><th>Total</th><th>Unit</th></tr></thead><tbody>'
    ]
    last = None
    for it in items:
        original_category = str(it.get('Category') or 'Others')
        category = original_category if original_category in ORDER_CATEGORIES else category_label({'category':original_category})
        if category != last:
            rows.append('<tr><td colspan="7" style="background:#ecf2fc;color:#394f78;font-weight:700">'
                        +escape(str(category))+'</td></tr>')
            last=category
        meal=it.get('Meal display',{})
        cells=[escape(str(it.get('ingredient_id',''))),escape(str(it.get('Ingredient','')))]
        for key in ('Breakfast','Lunch','Dinner'):
            qty=number(meal.get(key))
            cells.append(str(ceil(qty-1e-10)) if qty>0 else '—')
        cells.append(str(ceil(number(it.get('Quantity'))-1e-10)))
        cells.append(escape(str(it.get('Unit',''))))
        rows.append('<tr>'+''.join('<td>'+cell+'</td>' for cell in cells)+'</tr>')
    if not items:rows.append('<tr><td colspan="7">No items currently selected.</td></tr>')
    rows.append('</tbody></table><p style="margin-top:10px;text-align:right">Draft preview · Download Word for final document</p></div>')
    return ''.join(rows)
