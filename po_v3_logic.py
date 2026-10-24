"""V3 purchasing engine. Raw demand is measured in individual bottles/items/glasses.
All purchasing decisions (source overrides and case rounding) happen after demand
from meals, cocktails and alcohol has been consolidated for an ingredient.
"""
from __future__ import annotations
from collections import defaultdict
from math import ceil
import re
from po_logic import (number, identifier, MEALS, evaluate_formula, UnsafeFormula,
                      interpolate_cases)
from po_v2_logic import category_label

SOURCE_CHOICES=("Supplier","Majestics","Unit")
MEASURED_UNITS={"ml","millilitre","milliliter","g","gram","grams","kg","l","litre","liter"}

def master_case_size(master):
    return number(master.get('case size',master.get('Case Size')))

def current_source(master, override=None):
    return (str(override or master.get('Source') or 'Supplier')).strip()

def rack_item(master):
    return str(master.get('unit','')).strip().casefold() in ('rack','racks')

def pack_factor(master, source=None):
    """Number of *individual* units in one purchasable unit for selected source."""
    source=current_source(master,source)
    case=master_case_size(master)
    if source.casefold()=='unit':
        if str(master.get('category','')).strip().casefold()=='glasses':
            return case if case>0 else 0.0
        return 1.0
    return case if case>0 else 0.0

def purchase_unit(master,source=None):
    source=current_source(master,source)
    if str(master.get('category','')).strip().casefold()=='glasses':
        if source.casefold()!='unit' and master_case_size(master)>1:return 'Case'
        if master_case_size(master)>1:return str(master.get('unit') or 'Pack').strip().title()
        return 'Unit'
    if source.casefold()!='unit' and master_case_size(master)>1:return 'Case'
    unit=str(master.get('unit','')).strip().casefold()
    # g/kg are packaged solids; ml/l are bottled liquids. Avoid calling coffee beans "Bottle".
    if unit in ('ml','millilitre','milliliter','l','litre','liter'):
        return 'Bottle'
    return 'Unit'

def migrate_rules(rows):
    """Legacy token migration only. The purchasing basis comes from PO_Rules,
    not ingredient IDs, product names, or hardcoded category conversions.
    """
    result=[]
    for original in rows:
        r=dict(original)
        r['formula']=re.sub(r'\bUNS\b','PACK',str(r.get('formula','0')),flags=re.I).strip()
        basis=str(r.get('quantity_basis','')).strip().casefold()
        if basis not in ('individual','purchase'):
            raise ValueError(f"PO_Rules row {r.get('rule_id')} needs quantity_basis = Individual or Purchase")
        result.append(r)
    return result

def effective_rules(rules, patches):
    """Apply calculation-table formula edits to active calculation only."""
    lookup={str(x.get('rule_id','')):x for x in patches}
    out=[]
    for r in rules:
        patch=lookup.get(str(r.get('rule_id','')),{})
        item=dict(r)
        if str(patch.get('Formula','')).strip():item['formula']=str(patch['Formula'])
        out.append(item)
    return out

def calculate_meal_detail(rules,ingredients,guests,tables,soft_package,mixer_package,juice_ids,small_water):
    """Return per-rule rows with unrounded demand in base units and purchasing units."""
    result=[];issues=[]
    for rule in migrate_rules(rules):
        meal=str(rule.get('meal','')).strip()
        if meal not in MEALS:continue
        rid=str(rule.get('rule_id',''))
        if str(rule.get('enabled','TRUE')).lower() in ('false','0','no','off'):continue
        group=str(rule.get('group',''))
        if rid!='small-water' and number(guests.get(meal))<=0:continue
        package=str(rule.get('package','Any'))
        if package not in ('Any',''):
            selected=soft_package if 'soft' in group.lower() else mixer_package
            if package!=selected:continue
        if rid=='small-water':
            if not small_water:continue
            meal=max(('Breakfast','Lunch'),key=lambda x:number(guests.get(x)))
            if number(guests.get(meal))<=0:continue
        iid=identifier(rule.get('ingredient_id',''))
        if iid=='TABLE_JUICE':iid=identifier(juice_ids.get(meal,''))
        m=ingredients.get(iid)
        if not m:
            issues.append(f"Rule {rid}: ingredient {iid} missing");continue
        pack=pack_factor(m)
        if pack<=0:
            issues.append(f"{m.get('item',iid)}: case size must be positive");continue
        variables={'GST':number(guests.get(meal)),'TBL':number(tables.get(meal)),
                   'PACK':pack,'BOTTLE':number(m.get('Bottle Size')),
                   'YIELD':number(m.get('Yield')),
                   'B_GST':number(guests.get('Breakfast')),'L_GST':number(guests.get('Lunch'))}
        try:q=evaluate_formula(rule.get('formula','0'),variables)
        except UnsafeFormula as e:
            issues.append(f"{rid}: {e}");continue
        result.append({'key':f'{rid}:{meal}:{iid}','Rule ID':rid,'Meal':meal,'Group':group,
                       'Ingredient':str(m.get('item',iid)),'Ingredient ID':iid,
                       'Formula':str(rule.get('formula','')),'Calculated':round(q/pack if str(rule.get('quantity_basis','')).casefold()=='individual' else q,5),
                       'Unit':purchase_unit(m),'Pack factor':pack,
                       'base_units':q if str(rule.get('quantity_basis','')).casefold()=='individual' else q*pack})
    return result,issues

def recipe_demand(selected,recipes_by_name,ingredients):
    """Return raw demand in single bottles, single garnish packs or single glasses."""
    needed=defaultdict(float);names=defaultdict(set);issues=[]
    for name,servings in selected:
        if number(servings)<=0:continue
        rec=recipes_by_name.get(name)
        if not rec:issues.append(f'Missing drink {name}');continue
        for row in rec['ingredients']:
            iid=identifier(row['ingredient_id']);m=ingredients.get(iid)
            if not m:issues.append(f'{name}: missing ingredient {iid}');continue
            count=number(row['qty'])*number(servings)
            cat=str(m.get('category','')).casefold().strip()
            unit=str(m.get('unit','')).casefold().strip()
            if cat=='glasses':divisor=1 # Recipe expresses individual glasses, racks are applied on ordering
            elif cat=='garnish' and unit not in MEASURED_UNITS:
                divisor=number(m.get('Yield')) # portions per fruit/pack
            else:
                divisor=number(m.get('Bottle Size')) # ml/g used per recipe -> bottles/packs
            if divisor<=0:
                issues.append(f'{name} / {m.get("item",iid)}: invalid bottle size or yield');continue
            needed[iid]+=count/divisor
            names[iid].add(name)
    return dict(needed),{k:', '.join(sorted(v)) for k,v in names.items()},issues

def alcohol_demand(selected,matrix,ingredients,guests,shares=None):
    """Convert alcohol guide quantities into single bottles, *once*.

    Wine and sparkling wine: guide/override values are CASES OF SIX bottles.
    Spirits and liqueurs: guide/override values are individual BOTTLES.
    Beer: guide/override values are CASES OF 24 bottles. Actual
    supplier case-size rounding happens later in ``order_from_demand``.
    A category lacking a guide requires an explicit manual override; it must
    not silently disappear from the purchase order.
    """
    from po_v2_logic import alcohol_calc
    matrix_categories={str(x.get('category','')).strip().casefold() for x in matrix}
    adapted={};valid=[];warnings=[];manual=[];seen=set()
    for entry in selected:
        iid=identifier(entry.get('id',''))
        if iid not in ingredients:
            warnings.append(f'Alcohol ID {iid}: not found in IngredientsTbl')
            continue
        if iid in seen:
            warnings.append(f'{ingredients[iid].get("item",iid)} was selected more than once; using its first entry')
            continue
        seen.add(iid)
        master=ingredients[iid]
        category=str(master.get('category','')).strip()
        # A Prosecco entry is a sparkling wine even if the ingredient master
        # lists it in a separate 'Prosecco' category.
        normalized=('Sparkling Wine / Champagne' if category.casefold()=='prosecco' else category)
        adapted[iid]={**master,'category':normalized}
        if normalized.casefold() in matrix_categories:
            valid.append(entry)
        else:
            manual.append(entry)
    _,rows,guide_warnings=alcohol_calc(valid,matrix,adapted,guests,shares)
    warnings.extend(guide_warnings)
    override_by_id={identifier(x['id']):x.get('override') for x in valid}
    guide_by_code={str(x.get('code','')).upper():x for x in matrix}
    raw={};updated=[]
    for row in rows:
        iid=identifier(row.get('ingredient_id'))
        master=ingredients[iid]
        guide=guide_by_code.get(str(row.get('Guide code','')).upper(),{})
        # Guide-to-single conversion is defined exclusively in the Google Sheet.
        multiplier=number(guide.get('bottles_per_guide_unit'))
        if multiplier<=0:
            warnings.append(f"Alcohol matrix {row.get('Guide code')} has no valid bottles_per_guide_unit")
            continue
        unit=str(guide.get('guide_unit','Guide units'))
        guide_qty=number(row.get('Guide cases'))
        override=override_by_id.get(iid)
        final_qty=(guide_qty if override is None or str(override).strip()==''
                   else max(0.,number(override)))
        bottles=final_qty*multiplier
        raw[iid]=raw.get(iid,0)+bottles
        updated.append({**row,'Guide quantity':round(guide_qty,3),
                        'Final quantity':round(final_qty,3),
                        'Guide unit':unit,'Required bottles':round(bottles,3),
                        'PO unit':purchase_unit(master)})
    for entry in manual:
        iid=identifier(entry['id']);master=ingredients[iid]
        cat=str(master.get('category',''))
        override=entry.get('override')
        if override is None or str(override).strip()=='':
            warnings.append(f'{master.get("item",iid)} ({cat}) has no alcohol guide. Enter a manual quantity in bottles.')
            continue
        # Unguided items are entered explicitly in BOTTLES, not inferred packs.
        bottles=max(0.,number(override))
        raw[iid]=raw.get(iid,0)+bottles
        updated.append({'ingredient_id':iid,'Category':cat,'Ingredient':master.get('item',iid),
                        'Service':'Bar','Guide code':'Manual','Guide quantity':None,
                        'Final quantity':bottles,'Required bottles':round(bottles,3),
                        'Guide unit':'Bottles', 'PO unit':purchase_unit(master)})
        warnings.append(f'{master.get("item",iid)} has no guest-based alcohol guide; the manual bottle quantity was used.')
    return raw,updated,warnings

def order_from_demand(meal_details,recipe_raw,alcohol_raw,ingredients,recipe_names=None,
                      source_overrides=None,qty_overrides=None,supplier_prices=None):
    """Consolidate individual consumption first; then convert, round once and price."""
    base=defaultdict(float);recipe_names=recipe_names or {}
    source_overrides=source_overrides or {};qty_overrides=qty_overrides or {}
    supplier_prices=supplier_prices or {}
    for r in meal_details:base[identifier(r['Ingredient ID'])]+=number(r['base_units'])
    for vals in (recipe_raw,alcohol_raw):
        for iid,qty in vals.items():base[identifier(iid)]+=number(qty)
    result=[]
    for iid,raw in base.items():
        m=ingredients.get(iid)
        if not m or raw<=0:continue
        source=current_source(m,source_overrides.get(iid))
        factor=pack_factor(m,source)
        if factor<=0:continue
        computed=ceil(raw/factor-1e-10)
        final=qty_overrides.get(iid)
        qty=computed if final is None else max(0,ceil(number(final)-1e-10))
        if qty==0:continue
        original_factor=pack_factor(m)
        price_basis=str(m.get('price_basis','Pack')).strip().casefold()
        initial_price=number(m.get('unit_price'))
        per_single=initial_price if price_basis=='single' else initial_price/original_factor
        override_price=supplier_prices.get((source.casefold(),iid))
        if override_price:
            price=number(override_price.get('net_price'))
            override_basis=str(override_price.get('price_basis','Pack')).strip().casefold()
            estimated_unit_price=price*factor if override_basis=='single' else price
        else:
            estimated_unit_price=per_single*factor
        result.append({'ingredient_id':iid,'Source':source,'Category':category_label(m),
                       'Ingredient':str(m.get('item',iid)),'Quantity':qty,
                       'Unit':purchase_unit(m,source),'Net':round(qty*estimated_unit_price,2),
                       'Remarks':recipe_names[iid] if iid in recipe_names else '',
                       'Raw demand':round(raw,5),'Computed':computed,'Case size':master_case_size(m)})
    return sorted(result,key=lambda x:(x['Source'].casefold(),x['Ingredient'].casefold()))

def pivot_meals(details,ingredients):
    data=defaultdict(lambda:defaultdict(float))
    for r in details:
        data[identifier(r['Ingredient ID'])][r['Meal']]+=number(r['base_units'])
    out=[]
    for iid,rows in data.items():
        m=ingredients[iid];factor=pack_factor(m)
        rec={'ID':iid,'Ingredient':m['item'],'Unit':purchase_unit(m)}
        for meal in MEALS:rec[meal]=round(rows[meal]/factor,4)
        rec['Total']=round(sum(rec[meal] for meal in MEALS),4)
        out.append(rec)
    return sorted(out,key=lambda x:x['Ingredient'].casefold())
