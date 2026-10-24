"""Read-only administrator explanations derived from live sheet rules/master records.

No recipes, guest ratios, bottle multipliers, or case sizes live here.
Values are supplied by Ingredients, PO_Rules, PO_Alcohol_Matrix and PO_Settings.
"""
from __future__ import annotations
from po_logic import identifier, number
from po_v3_logic import pack_factor, purchase_unit

RULE_GROUPS = ('Water', 'Soft Drinks', 'Juices', 'Mixers', 'Other')


def rule_category(group):
    group = str(group).casefold()
    if 'water' in group: return 'Water'
    if 'soft' in group: return 'Soft Drinks'
    if 'juice' in group: return 'Juices'
    if 'mixer' in group: return 'Mixers'
    return 'Other'


def variables_from_master(master):
    """Explain the actual expression variables; live values come from sheet rows."""
    return {
        'GST': 'Guest count for the rule meal',
        'TBL': 'Number of tables for the rule meal (guest count / Tables_Per_Guests, editable)',
        'B_GST': 'Breakfast guests',
        'L_GST': 'Lunch guests',
        'PACK': 'Purchase pack factor from the selected Source and Ingredients.case size',
        'BOTTLE': 'Ingredients.Bottle Size in Ingredients.unit',
        'YIELD': 'Ingredients.Yield (garnish portions produced by one item/pack)',
    }


def describe_rule_rows(rules, ingredients, settings):
    """One row per sheet rule, with item-dependent unit and conversion disclosed."""
    out=[]
    for r in rules:
        meal=str(r.get('meal','')).strip()
        iid=identifier(r.get('ingredient_id'))
        if iid == 'TABLE_JUICE':
            iid=identifier(settings.get(f'{meal}_Juice_ID',''))
        master=ingredients.get(iid,{})
        factor=pack_factor(master) if master else 0
        basis=str(r.get('quantity_basis','')).strip().casefold()
        if basis=='individual':
            result='Individual bottles/items'
            conversion='Formula result ÷ PACK → fractional purchase packs'
        elif basis=='purchase':
            result='Purchase packs (cases/bottles/units)'
            conversion='Formula result × PACK → individual demand'
        else:
            result='INVALID quantity_basis'
            conversion='Correct PO_Rules.quantity_basis (Individual or Purchase)'
        out.append({
            'Category':rule_category(r.get('group','')),
            'Meal':meal,
            'Package':str(r.get('package','Any')),
            'Ingredient':str(master.get('item','MISSING MASTER ID '+iid)),
            'Formula':str(r.get('formula','')),
            'Returns':result,
            'Conversion':conversion,
            'PO unit':purchase_unit(master) if master else '—',
            'PACK':factor,
            'Bottle Size':master.get('Bottle Size','—'),
            'Measure':str(master.get('unit','—')),
            'Yield':master.get('Yield','—'),
            'Case Size':master.get('case size','—'),
            'Source':str(master.get('Source','—')),
            'Enabled':str(r.get('enabled','TRUE')),
            'Rule ID':str(r.get('rule_id','')),
        })
    return out


def describe_alcohol_rows(matrix):
    """Guest bands & bottle multipliers read directly from the matrix."""
    guest_cols=sorted((str(k) for r in matrix for k in r.keys() if str(k).isdigit()),key=int)
    guest_cols=list(dict.fromkeys(guest_cols))
    output=[]
    for r in matrix:
        multiplier=number(r.get('bottles_per_guide_unit'))
        row={
            'Category':str(r.get('category','')),
            'Service':str(r.get('service','')),
            'Code':str(r.get('code','')),
            'Guide unit':str(r.get('guide_unit','')),
            'Bottles / guide unit':multiplier,
            'Conversion':f'Interpolated guide × {multiplier:g} → bottles' if multiplier>0 else 'Invalid matrix multiplier',
        }
        for c in guest_cols:row[c+' guests']=r.get(c,'')
        output.append(row)
    return output


def describe_recipe_master(ingredients):
    """Show actual garnish and glass pack conversions without inventing examples."""
    output=[]
    for iid,m in ingredients.items():
        cat=str(m.get('category','')).strip().casefold()
        if cat not in ('garnish','glasses'):continue
        measure=str(m.get('unit','')).strip().casefold()
        if cat=='glasses':
            consume='Recipe glass quantity = individual glasses'
        elif measure in ('ml','millilitre','milliliter','g','gram','grams','kg','l','litre','liter'):
            consume='Recipe amount × servings ÷ Bottle Size'
        else:
            consume='Recipe portions × servings ÷ Yield'
        output.append({
            'Ingredient':str(m.get('item','')),
            'Category':m.get('category',''),
            'Consumption':consume,
            'Bottle Size':m.get('Bottle Size',''),
            'Yield':m.get('Yield',''),
            'Case Size':m.get('case size',''),
            'Source':m.get('Source',''),
            'Purchase unit':purchase_unit(m),
            'Order conversion':'Round up combined individual demand ÷ PACK',
            'PACK':pack_factor(m),
        })
    return output
