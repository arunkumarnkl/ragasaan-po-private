"""V3.5 view and inventory policies. No purchasing quantities are hardcoded here.

Ingredient identity, categories, pack factors and costs remain sourced from Sheets.
"""
from collections import defaultdict
from po_v2_logic import category_label
from po_v34_features import purchase_category

RECIPE_ONLY_ROLES = frozenset({'bartenders', 'bartender'})


def recipe_only_role(role):
    return str(role or '').strip().casefold() in RECIPE_ONLY_ROLES


def may_edit_recipe(role):
    return str(role or '').strip().casefold() == 'admin'


def split_recipe_ingredients(recipe):
    """Separate base recipe ingredients from the sheet's Garnish/Glasses categories."""
    body, garnish_glasses = [], []
    for item in recipe.get('ingredients', []):
        category = str(item.get('category') or '').strip().casefold()
        (garnish_glasses if ('garnish' in category or 'glass' in category) else body).append(item)
    return body, garnish_glasses


def initial_alcohol_categories(categories, lines=20):
    """Exactly 20 starter rows, representing each available Sheet category when possible."""
    if lines < 0:
        raise ValueError('lines must be non-negative')
    result=[]
    for category in categories:
        if len(result) >= lines:break
        result.append(category)
    for category in categories:
        if len(result) >= lines:break
        result.append(category)
    return result + [''] * (lines-len(result))


def grouped_preview_rows(rows):
    """One table per source, grouped using in-table category headers (no repeated Item titles)."""
    grouped=defaultdict(list)
    for row in rows:
        group=str(row.get('Category') or 'Others').strip() or 'Others'
        grouped[group].append(row)
    output=[]
    for category in sorted(grouped,key=lambda c:(purchase_category(c),c.casefold())):
        output.append({'Name':category.upper(), 'Qty':None, 'Unit':'', 'Remarks':'', '_heading':True})
        for row in sorted(grouped[category],key=lambda r:str(r.get('Ingredient','')).casefold()):
            output.append({'Name':str(row.get('Ingredient','')),
                           'Qty':row.get('Quantity'), 'Unit':row.get('Unit',''),
                           'Remarks':row.get('Remarks',''), '_heading':False})
    return output


def inventory_group(item, master):
    """Classify alcohol using the sheet category, not a selected alcohol-guide code.

    Do not mistake ginger beer / non-alcoholic ingredients for alcohol by searching
    the ingredient name; only the structured category field is used.
    """
    category=str(master.get('category') or item.get('Category') or '').strip().casefold()
    label=category_label({'category':category})
    if label=='Beer' or category in ('beers',):return 'Beer'
    if label=='Wines' or any(x in category for x in ('sparkling','champagne','prosecco')):
        return 'Wine & Sparkling'
    if label in ('Spirits','Liqueur') or any(x in category for x in
        ('whiskey','whisky','vodka','rum','gin','tequila','cognac','liqueur','liqueure','aperitif','appretif','brandy','spirit')):
        return 'Spirits & Liqueurs'
    return None


def inventory_items_for_source(order, ingredients):
    """Include ALL ordered alcohol within this source, whether guided, manually added or recipe-based."""
    groups=defaultdict(list)
    seen=set()
    for item in order:
        iid=str(item.get('ingredient_id','')).strip()
        if not iid or iid in seen:continue
        master=ingredients.get(iid, {})
        group=inventory_group(item,master)
        if group:
            groups[group].append(item)
            seen.add(iid)
    return [(group,sorted(groups[group],key=lambda r:str(r.get('Ingredient','')).casefold()))
            for group in ('Beer','Wine & Sparkling','Spirits & Liqueurs') if groups[group]]
