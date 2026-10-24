"""Live source-aware purchasing / alcohol logic for Ragasaan."""
from collections import defaultdict
from math import ceil
from po_logic import number,identifier,MEALS,interpolate_cases

ORDER_CATEGORIES=['Water','Juices','Soft Beverages','Mixers','Wines','Beer','Spirits','Liqueur','Puree & Syrups','Others']

def source_name(master):
    return str(master.get('Source') or 'Supplier').strip()

def individual(master):
    return source_name(master).lower()=='unit'

def category_label(master):
    c=str(master.get('category','')).lower()
    if c=='water':return 'Water'
    if 'juice' in c:return 'Juices'
    if 'soft' in c:return 'Soft Beverages'
    if 'mixer' in c:return 'Mixers'
    if 'wine' in c or 'champagne' in c or 'prosecco' in c:return 'Wines'
    if 'beer' in c:return 'Beer'
    if any(x in c for x in ('whisky','vodka','rum','gin','cognac','tequila','brandy')):return 'Spirits'
    if 'liqueur' in c or 'appretif' in c:return 'Liqueur'
    if 'puree' in c or 'syrup' in c:return 'Puree & Syrups'
    return 'Others'

def alcohol_calc(selected, matrix, ingredients, guests, shares=None):
    """All guides, service choices and guest values are read from matrix rows.

    The service string comes from PO_Alcohol_Matrix, except the user-facing
    "Bar" option. When two variants exist, split shares are from PO_Settings.
    """
    shares=shares or (1.0,0.0)
    groups=defaultdict(list);warnings=[]
    for entry in selected:
        iid=identifier(entry.get('id'))
        if iid not in ingredients:continue
        master=ingredients[iid]
        category=str(master.get('category','')).strip().casefold()
        if category=='prosecco':category='sparkling wine / champagne'
        service=str(entry.get('service','Bar')).strip().casefold()
        if service=='bar':service='bar'
        matches=[x for x in matrix if str(x.get('category','')).strip().casefold()==category and
                 str(x.get('service','')).strip().casefold()==service]
        if not matches:
            warnings.append(f'No alcohol matrix entry for {master.get("item")} ({service})')
            continue
        groups[(category,service)].append((iid,entry,matches))
    demand=defaultdict(float);display=[]
    for (category,service),items in groups.items():
        if len(items)>2:warnings.append(f'{category} ({service}): more than two variants. Check manual quantities.')
        for index,(iid,entry,matches) in enumerate(items):
            guide=matches[min(index,len(matches)-1)]
            code=str(guide.get('code','')).strip()
            base=interpolate_cases(guide,guests)
            share=(number(shares[min(index,1)]) if len(items)==2 and index<2 else 1.0)
            target=base*share
            override=entry.get('override')
            final=target if override is None or str(override).strip()=='' else max(0.,number(override))
            demand[iid]+=final
            display.append({'ingredient_id':iid,'Category':ingredients[iid].get('category',''),
                            'Ingredient':ingredients[iid].get('item',''),'Service':service,
                            'Guide code':code,'Guide cases':round(target,3),
                            'Final cases':round(final,3)})
    return dict(demand),display,warnings
