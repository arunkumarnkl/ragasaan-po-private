"""V3.4 pure policies for source ordering and cocktail-alcohol handling."""
from po_v2_logic import category_label

def purchase_category(name):
    """Fixed DISPLAY order only; ingredient identity and quantity stay sheet-driven."""
    rank = {'Water': 0, 'Juices': 1, 'Soft Beverages': 2, 'Mixers': 3,
            'Puree & Syrups': 4, 'Wines': 5, 'Beer': 6, 'Spirits': 7,
            'Liqueur': 8, 'Others': 9}
    return rank.get(str(name), 99)


def is_alcohol_master(master, alcohol_matrix):
    category = str(master.get('category', '')).strip().casefold()
    categories = {str(r.get('category', '')).strip().casefold() for r in alcohol_matrix}
    return (category in categories or category == 'prosecco' or
            category_label(master) in {'Wines', 'Beer', 'Spirits', 'Liqueur'})


def omit_alcohol_recipe_ingredients(raw, names, ingredients, matrix, package_enabled):
    """Keep non-alcoholic cocktail mixers and garnishes if package is disabled."""
    if package_enabled:
        return raw, names, []
    filtered = {iid: val for iid, val in raw.items()
                if not is_alcohol_master(ingredients.get(iid, {}), matrix)}
    retained_names = {iid: nm for iid, nm in names.items() if iid in filtered}
    excluded = [ingredients[iid]['item'] for iid in raw if iid not in filtered and iid in ingredients]
    return filtered, retained_names, excluded

