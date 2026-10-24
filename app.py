"""Ragasaan Purchase Order | Streamlit + Google Sheets.

Run with: streamlit run app.py
All inventory, recipes and contacts come from the connected spreadsheet.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from io import BytesIO
import json
import base64
from html import escape as html_escape
from ui_theme import inject_theme, hero, category_caption, page_heading
from recipe_book_view import render_recipe_table, valid_https_image
from recipe_management import render_recipe_management
from purchase_preview import document_preview_html
from logo_store import load_default_logo, save_logo, clear_logo, saved_logo_path
from cloud_storage import fetch_cloud_logo, save_cloud_logo, clear_cloud_logo
from recipe_images import (IMAGE_COLUMNS, image_record, suggested_image, upsert_image_record, verify_upload)
from persistent_images import PersistentImages
from recipe_thumbnail import RECIPE_IMAGE_PX, crop_thumbnail, safe_thumbnail_html
from po_word import create_docx
from po_v35_features import (recipe_only_role, split_recipe_ingredients,
    initial_alcohol_categories, grouped_preview_rows, inventory_items_for_source)
from po_auth import authenticate, password_hash
import hashlib
import hmac
import math
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from docx import Document
from docx.shared import Inches, Pt

from po_logic import (MEALS, ingredient_index, table_to_records,
                      parse_recipe_matrix, number, identifier, verify_recipe_ids)
from po_v2_logic import category_label
from po_v34_features import purchase_category, is_alcohol_master, omit_alcohol_recipe_ingredients
from calculation_guide import RULE_GROUPS, describe_rule_rows, describe_alcohol_rows, describe_recipe_master, variables_from_master
from startup_repair import plan_price_basis_repair
from po_v3_logic import (SOURCE_CHOICES, pack_factor, purchase_unit, master_case_size,
                         migrate_rules, calculate_meal_detail, recipe_demand, alcohol_demand,
                         order_from_demand, pivot_meals)
from sheet_store import (SHEET_ID, GoogleStore, ExcelPreview,
                         credentials_from_secrets, load_saved_connection, save_connection_to_keyring, clear_saved_connection)

st.set_page_config(page_title="Ragasaan | Purchase Order",page_icon="🍸",layout="wide",
                   initial_sidebar_state="expanded")
inject_theme()

SHEET_NAMES={"users":"Users","ingredients":"Ingredients","recipe":"Recipe",
             "vendors":"Vendor Data","venue":"Venue","contacts":"Contacts",
             "rules":"PO_Rules","alcohol":"PO_Alcohol_Matrix","notes":"PO_Recipe_Notes",
             "settings":"PO_Settings","prices":"PO_Supplier_Prices", "images":"PO_Recipe_Images"}
RULE_COLUMNS=["rule_id","meal","group","package","ingredient_id","formula","enabled","quantity_basis"]
ALCOHOL_REQUIRED_COLUMNS=["code","category","service","bottles_per_guide_unit","guide_unit"]
PRICE_COLUMNS=["Source","ingredient_id","net_price","price_basis","updated_at"]
NOTE_COLUMNS=["recipe_name","remarks","garnish_notes"]


@st.cache_data(ttl=86400, show_spinner=False)
def recipe_suggestion(name, category):
    return suggested_image(name, category)


def secrets_value(name,default=None):
    try:return st.secrets.get(name,default)
    except (FileNotFoundError, OSError, KeyError):return default


# Cloud credentials are configured server-side in Streamlit Cloud's Secrets UI.
# On the cloud never expose a service-account JSON upload field to visitors.
CLOUD_MODE = str(secrets_value('deployment_mode','local')).strip().casefold() == 'cloud'


@st.cache_resource(show_spinner=False)
def connect_gsheet(sheet_id,credential_str):
    import json
    return GoogleStore(sheet_id,json.loads(credential_str))


@st.cache_data(ttl=60,show_spinner=False)
def read_grid(_store,title,refresh):
    return _store.read(title)


def grid(title):
    return read_grid(st.session_state.store,title,st.session_state.get("refresh_count",0))


def records(title):return table_to_records(grid(title))


def refresh():
    st.session_state.refresh_count=st.session_state.get("refresh_count",0)+1
    read_grid.clear()


def after_save(message):
    refresh();st.toast(message,icon="✅");st.rerun()


def admin():return str(st.session_state.get("role","")).strip().casefold()=="admin"


def load_app_data():
    ingredient_grid=grid(SHEET_NAMES['ingredients'])
    ingredient_rows=table_to_records(ingredient_grid)
    if not ingredient_rows:raise ValueError('Ingredients master is missing or empty')
    live_headers=[str(c).strip() for c in ingredient_grid[0]]
    if 'price_basis' not in live_headers:
        raise ValueError('Ingredients is missing the required price_basis column (Pack or Single). '
                         'Use Repair Ingredients price_basis on this setup screen; no other columns need replacing.')
    ingredients=ingredient_index(ingredient_rows)
    invalid_basis=[iid for iid,item in ingredients.items()
                   if str(item.get('price_basis','')).strip().title() not in ('Pack','Single')]
    if invalid_basis:
        raise ValueError(f'Ingredients has {len(invalid_basis)} missing/invalid price_basis values, '
                         f'including ID {invalid_basis[0]}. Use Repair Ingredients price_basis below.')
    for iid,item in ingredients.items():
        if number(item.get('case size'))<=0 or number(item.get('Bottle Size'))<=0:
            raise ValueError(f'Ingredients ID {iid}: Bottle Size and case size must be positive')
    recipe_matrix=grid(SHEET_NAMES['recipe'])
    recipes,issues=parse_recipe_matrix(recipe_matrix,ingredients)
    raw_rules=records(SHEET_NAMES['rules'])
    raw_matrix=records(SHEET_NAMES['alcohol'])
    raw_settings=records(SHEET_NAMES['settings'])
    if not raw_rules or not raw_matrix or not raw_settings:
        missing=[x for x,v in [('PO_Rules',raw_rules),('PO_Alcohol_Matrix',raw_matrix),('PO_Settings',raw_settings)] if not v]
        raise ValueError('Missing required Google Sheets: '+', '.join(missing)+'. Admin must sync the revised workbook.')
    rules=migrate_rules(raw_rules)
    for r in raw_matrix:
        if number(r.get('bottles_per_guide_unit'))<=0:
            raise ValueError(f"Alcohol matrix {r.get('code')} has no bottles_per_guide_unit")
    settings={str(r.get('Setting','')).strip():str(r.get('Value','')).strip() for r in raw_settings}
    prices={}
    for row in records(SHEET_NAMES['prices']):
        src=str(row.get('Source','')).strip().casefold()
        iid=identifier(row.get('ingredient_id'))
        if src and iid and str(row.get('net_price','')).strip()!='':
            prices[(src,iid)]=row
    return ingredients,recipes,issues,rules,raw_matrix,recipe_matrix,settings,prices

def compact_columns(frame, overrides=None):
    """Narrow numerical cells to approx. four digits; keep readable item names.

    Streamlit's canvas grid doesn't wrap its headers reliably across versions,
    so long captions are short and the explanatory headings remain outside it.
    """
    cfg={}
    for c in frame.columns:
        name=str(c)
        if name in ('_key','row','col'):
            cfg[name]=None
        elif pd.api.types.is_numeric_dtype(frame[c]):
            cfg[name]=st.column_config.NumberColumn(width=72)
        elif name.casefold() in ('formula','ingredient','ingredient name','item','remarks','name'):
            cfg[name]=st.column_config.TextColumn(width=200 if name.lower()!='formula' else 150)
        elif name.casefold() in ('category','source','wine service','service'):
            cfg[name]=st.column_config.TextColumn(width=108)
        else:
            cfg[name]=st.column_config.TextColumn(width=86)
    cfg.update(overrides or {})
    return cfg


def editor_table(title,display_title,headers,help_text=""):
    st.subheader(display_title)
    if help_text:st.caption(help_text)
    original=records(title)
    if not original:
        st.info("No rows currently found in this sheet.")
    source=pd.DataFrame(original,columns=headers)
    edited=st.data_editor(source,num_rows="dynamic",use_container_width=True,hide_index=True,
                          column_config=compact_columns(source),key="editor_"+title)
    if st.button("Save to Google Sheets",key="save_"+title,type="primary"):
        if not st.session_state.store.writable:
            st.error("Connect Google Sheets to save. The Excel preview is read-only.");return
        cleaned=[]
        for r in edited.fillna("").to_dict("records"):
            if any(str(v).strip() for v in r.values()):cleaned.append(r)
        st.session_state.store.save_table(title,cleaned,headers)
        after_save(display_title+" saved")


def form_number(label,key,default=0,min_value=0.0,step=1.0):
    if key not in st.session_state:st.session_state[key]=default
    return st.number_input(label,min_value=min_value,step=step,key=key)


def lookup_select(label, rows, name_field, key):
    options=[""]+[str(r.get(name_field,"")) for r in rows if r.get(name_field)]
    name=st.selectbox(label,options,key=key)
    return next((r for r in rows if str(r.get(name_field,""))==name),{})


# CONNECTION: automatically try Streamlit secrets, environment, then OS credential vault.
if "store" not in st.session_state:
    saved=None if CLOUD_MODE else load_saved_connection()
    creds=credentials_from_secrets(st.secrets)
    sheet_id=secrets_value("gsheet_id",SHEET_ID)
    if not creds and saved:
        creds=saved.get('credentials');sheet_id=saved.get('sheet_id',SHEET_ID)
    if creds:
        try:
            import json
            st.session_state.store=connect_gsheet(sheet_id,json.dumps(creds,sort_keys=True))
            st.session_state.pop('connect_error',None)
        except Exception:
            st.session_state.connect_error="Cannot connect using stored credentials. Verify service-account access."

if "store" not in st.session_state and CLOUD_MODE:
    st.error("Cloud Google Sheets connection is not configured or failed. Add a valid [gcp_service_account] and gsheet_id in the app's Streamlit Community Cloud Secrets settings. The JSON key cannot be uploaded through this web page.")
    st.info("Check Google Sheets API access, the Spreadsheet ID and sharing permission for the service-account email. See CLOUD_DEPLOYMENT.md.")
    st.stop()

if "store" not in st.session_state:
    st.title("Ragasaan Purchase Order · First-time connection")
    st.info("No Excel upload is needed. The app loads directly from Google Sheets once a service account is configured.")
    if st.session_state.get('connect_error'):st.error(st.session_state.connect_error)
    st.caption("One-time setup: create a NEW service-account key, share your Google Sheet with its email as Editor, then upload the JSON here. On Windows it can be remembered in Credential Manager.")
    with st.form('first_connection_form'):
        sheet_id=st.text_input('Google Spreadsheet ID',value=SHEET_ID)
        key_file=st.file_uploader('NEW service-account JSON key',type=['json'])
        remember=st.checkbox('Remember securely on this computer (Windows Credential Manager / OS keyring)',value=True)
        submit=st.form_submit_button('Connect to Google Sheets',type='primary')
    if submit:
        try:
            import json
            if not key_file:raise ValueError('Select the JSON key')
            creds=json.loads(key_file.getvalue().decode('utf-8'))
            if creds.get('type')!='service_account' or not creds.get('private_key') or not creds.get('client_email'):
                raise ValueError('Not a valid service-account JSON')
            connection=connect_gsheet(sheet_id.strip(),json.dumps(creds,sort_keys=True))
            if not connection.read(SHEET_NAMES['users']):raise ValueError('Users sheet not found or empty')
            st.session_state.store=connection
            if remember:
                try:save_connection_to_keyring(sheet_id.strip(),creds)
                except Exception:
                    st.warning('Connected, but OS keyring storage failed. Configure secrets.toml once for automatic startup.')
            st.rerun()
        except Exception as exc:
            st.error(f'Unable to connect: {type(exc).__name__}. Check the key, Sheet sharing and Spreadsheet ID.')
    st.stop()

store=st.session_state.store
with st.sidebar:
    st.markdown('### 🍸 Ragasaan PO')
    st.caption('🟢 Google Sheets · Live connection')
    if st.button("Refresh spreadsheet data",use_container_width=True):refresh();st.rerun()
    if not CLOUD_MODE and st.session_state.get('role', '').strip().casefold() == 'admin':
        if st.button('Forget saved Google connection',use_container_width=True):
            clear_saved_connection()
            st.info('Saved connection cleared from OS keyring. Streamlit server secrets, if configured, remain unaffected.')


if not st.session_state.get("username"):
    st.title("Sign in")
    st.caption("Accounts are read from the workbook's Users sheet. Passwords are not kept in app source code.")
    with st.form("login_form"):
        uname=st.text_input("Username")
        pwd=st.text_input("Password",type="password")
        submitted=st.form_submit_button("Log in",type="primary")
    if submitted:
        user=authenticate(uname,pwd,records(SHEET_NAMES["users"]))
        if not user:st.error("Incorrect username or password")
        else:
            st.session_state.username=str(user["username"])
            st.session_state.role=str(user.get("role", "Standard user"))
            st.rerun()
    st.stop()

with st.sidebar:
    st.success(f"{st.session_state.username} · {st.session_state.role}")
    if st.button("Log out",use_container_width=True):
        for k in ("username","role","meal_overrides","garnish_overrides"):st.session_state.pop(k,None)
        st.rerun()

try:
    ingredients, recipes, recipe_issues, rules, alcohol_matrix, recipe_matrix, po_settings, supplier_prices=load_app_data()
except Exception as exc:
    st.error(f"The main tabs cannot open because some required Google Sheets data is incomplete: {exc}")
    st.info("The app automatically opens the main tabs once all required fields are available. "
            "The connected Google Sheet and your Admin login are already working. "
            "You do not need to reconnect your Google account.")
    err_text=str(exc).casefold()
    if '429' in err_text or 'quota' in err_text:
        st.warning("Google Sheets read quota may be exhausted. Allow the quota to recover "
                   "before selecting Retry; repeated rapid refreshes can make this worse.")
    if st.button('Retry opening main application',key='startup_retry'):
        refresh()
        st.rerun()
    if admin() and store.writable:
        st.markdown('#### One-time configuration repair (Admin only)')
        st.caption('Upload the V3.3 updated workbook below. The default installation replaces only '
                   'the four configuration tabs, not Recipe, Users, Vendors, Venue or Contacts. '
                   'The separate ingredient repair updates only the price_basis column by ingredient ID.')
        initialize_upload=st.file_uploader('V3.3 updated workbook (.xlsx)',type=['xlsx'],key='init_v33')
        selected_init=st.multiselect('Configuration tabs to install',
            ['PO_Rules','PO_Alcohol_Matrix','PO_Settings','PO_Supplier_Prices'],
            default=['PO_Rules','PO_Alcohol_Matrix','PO_Settings','PO_Supplier_Prices'],
            key='install_tabs_v33')
        fix_basis=st.checkbox('Also repair only missing Ingredients.price_basis values (recommended; does not replace Ingredients)',value=True,key='init_repair_basis_v33')
        confirmed_init=st.checkbox('I backed up my live Google Sheet and approve these configuration changes',key='confirm_init_v33')

        def read_install_workbook():
            if not initialize_upload:
                raise ValueError('Choose the updated V3.3 .xlsx workbook first.')
            incoming=pd.read_excel(BytesIO(initialize_upload.getvalue()),sheet_name=None,
                                   dtype=object,keep_default_na=False)
            return {k:v.fillna('') for k,v in incoming.items()}

        if st.button('Install selected tabs and open app',
                     disabled=not(initialize_upload and confirmed_init and selected_init),type='primary',
                     key='startup_install_v33'):
            try:
                incoming=read_install_workbook()
                for title in selected_init:
                    if title not in incoming:
                        raise ValueError(f'Uploaded workbook is missing {title}. No data was changed.')
                basis_changes=[];basis_ids=[]
                if fix_basis:
                    if 'Ingredients' not in incoming:
                        raise ValueError('Uploaded workbook has no Ingredients tab for the price_basis repair.')
                    basis_changes,basis_ids=plan_price_basis_repair(
                        grid('Ingredients'),incoming['Ingredients'].to_dict('records'))
                completed=[]
                for title in selected_init:
                    frame=incoming[title]
                    store.save_table(title,frame.to_dict('records'),list(frame.columns))
                    completed.append(title)
                if basis_changes:
                    store.update_cells('Ingredients',basis_changes)
                    completed.append(f'Ingredients.price_basis ({len(basis_ids)} IDs)')
                st.session_state['startup_notice_v33']=('Installed: '+', '.join(completed)+'.')
                after_save('Configuration updated. Opening main tabs')
            except Exception as install_exc:
                st.error('Setup was not completed: '+str(install_exc))
                st.caption('If any earlier tabs were saved, they remain in Google Sheets. '
                           'Repair or retry; do not replace the entire Ingredients worksheet.')

        if initialize_upload:
            st.markdown('##### Repair only the Ingredients pricing column')
            st.caption('Choose this if the four configuration tabs were already synced. '
                       'Only missing/invalid price_basis cells are populated from the workbook. '
                       'All ingredient names, units, prices, yields and case sizes remain unchanged.')
            if st.button('Repair Ingredients.price_basis only',
                         disabled=not confirmed_init,key='startup_basis_only_v33'):
                try:
                    incoming=read_install_workbook()
                    if 'Ingredients' not in incoming:
                        raise ValueError('Uploaded workbook has no Ingredients worksheet.')
                    changes,ids=plan_price_basis_repair(grid('Ingredients'),
                        incoming['Ingredients'].to_dict('records'))
                    if changes:store.update_cells('Ingredients',changes)
                    st.session_state['startup_notice_v33']=(
                        f'Ingredients.price_basis repaired for {len(ids)} ingredient(s).')
                    after_save('Ingredients pricing column repaired. Opening main tabs')
                except Exception as repair_exc:
                    st.error('Price-basis repair was not completed: '+str(repair_exc))
    st.stop()

by_name={r["name"]:r for r in recipes}
with st.sidebar:
    st.caption(f"{len(ingredients)} ingredients · {len(recipes)} recipes")


bartender_view = recipe_only_role(st.session_state.get('role'))
hero(st.session_state.get('username'),st.session_state.get('role'))
if st.session_state.get('startup_notice_v33'):
    st.success(st.session_state.pop('startup_notice_v33'))
if bartender_view:
    # No calculation, PO, pricing, or admin tab is constructed for Bartenders.
    page_recipe=st.container()
else:
    page_recipe,page_calc,page_po,page_admin=st.tabs([
        "📒 Recipe Book", "🧮 Calculation",
        "🛒 Purchase Order", "⚙️ Admin Settings"])

# -------- Recipe Book: all recipes in a read-only, grouped table --------
with page_recipe:
    page_heading('Recipe Book', 'Browse all recipes by category · Read-only catalogue')
    category_caption('Category-wise catalogue', '📒')
    filter_col, cat_col, size_col = st.columns([1.6,1.0,.8],gap='small')
    with filter_col:
        filter_text=st.text_input('Search drinks or ingredients',placeholder='Search by drink, ingredient, or ID',
                                  key='recipe_catalogue_search_v36')
    categories=sorted({str(r.get('category') or 'Uncategorised') for r in recipes},key=str.casefold)
    with cat_col:
        category_filter=st.selectbox('Recipe category',['All categories']+categories,
                                      key='recipe_catalogue_category_v36')
    with size_col:
        rows_choice=st.selectbox('Rows per page',[24,48,'All'],key='recipe_catalogue_pagesize_v36')
    selected=[]
    search=filter_text.strip().casefold()
    for rec in recipes:
        if category_filter!='All categories' and str(rec.get('category'))!=category_filter:continue
        if search and not (search in str(rec.get('name','')).casefold()
          or search in str(rec.get('category','')).casefold()
          or any(search in str(it.get('name','')).casefold() or search==str(it.get('ingredient_id','')).casefold()
                  for it in rec.get('ingredients',[]))):
            continue
        selected.append(rec)
    selected.sort(key=lambda r:(str(r.get('category','')).casefold(),str(r.get('name','')).casefold()))
    page_size=len(selected) or 1 if rows_choice=='All' else int(rows_choice)
    pages=max(1,math.ceil(len(selected)/page_size))
    page_num=1
    if pages>1:
        prev,nav=st.columns([2.4,1],gap='small')
        with nav:
            page_num=st.number_input('Page',min_value=1,max_value=pages,value=1,step=1,
                                     key=f'recipe_cat_page_{category_filter}_{rows_choice}')
    visible=selected[(page_num-1)*page_size:page_num*page_size]
    st.markdown('<div class="rag-summary"><div class="rag-stat"><strong>'+
        str(len(recipes))+'</strong> total recipes</div><div class="rag-stat"><strong>'+
        str(len(categories))+'</strong> categories</div><div class="rag-stat">Showing <strong>'+
        str(len(visible))+'</strong> matching recipes'+(f' · page {page_num}/{pages}' if pages>1 else '')+
        '</div><div class="rag-stat">Read-only · Edit in Admin Settings</div></div>',unsafe_allow_html=True)
    # Load only selected page's saved image overrides. A public URL is loaded
    # lazily by the browser. Private Drive thumbnails are cached in session memory.
    # Expensive Wikimedia suggestion lookups are opt-in, preventing 120 API calls
    # whenever the user merely opens Recipe Book.
    suggest_online=st.toggle('Show recommended Wikimedia Commons images for missing photos',value=False,
        key='recipe_catalogue_suggestions_v36',
        help='Optional online lookup for visible recipes only. Source and licence can be managed in Admin Settings.')
    image_rows=records(SHEET_NAMES['images'])
    note_rows=records(SHEET_NAMES['notes'])
    saved_index={str(r.get('recipe_name','')).strip().casefold():r for r in image_rows}
    note_index={str(r.get('recipe_name','')).strip().casefold():r for r in note_rows}
    image_urls={}
    st.session_state.setdefault('recipe_drive_cache_v36',{})
    drive_cache=st.session_state.recipe_drive_cache_v36
    for rec in visible:
        name=rec['name'];override=saved_index.get(name.casefold(),{})
        external=valid_https_image(override.get('image_url',''))
        if external:
            image_urls[name]=external
        elif override.get('drive_file_id') and getattr(store,'credentials',None):
            file_id=str(override['drive_file_id'])
            if file_id not in drive_cache:
                try:
                    buf=BytesIO()
                    thumb=crop_thumbnail(PersistentImages(store.credentials,bucket=str(secrets_value('gcs_image_bucket',''))).read(file_id))
                    thumb.save(buf,format='PNG')
                    drive_cache[file_id]='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')
                except Exception:
                    drive_cache[file_id]=''
            if drive_cache[file_id]:image_urls[name]=drive_cache[file_id]
        elif suggest_online:
            suggested=recipe_suggestion(name,rec['category'])
            if suggested and valid_https_image(suggested.get('url','')):
                image_urls[name]=suggested['url']
    st.markdown(render_recipe_table(visible,image_urls,
        {r['name']:note_index.get(r['name'].casefold(),{}) for r in visible}),
        unsafe_allow_html=True)
    st.caption('Each ingredient is on a separate line with its quantity. Thumbnails are fixed at 2 cm × 2 cm. '
               'Recipe management and image uploads are restricted to Admin Settings.')

# Stop rendering at Recipe Book for Bartenders (view-only).
if bartender_view:
    st.stop()

# -------- Calculation, compact planning and drinks left; alcohol + meals right --------
with page_calc:
    page_heading('Calculation', 'Guest planning, cocktail selection, alcohol and meal quantities')
    calc_left,calc_right=st.columns([1.4,1.6],gap='small')
    with calc_left:
        st.subheader('Guests & table planning')
        guests={};tables={}
        for meal in MEALS:
            c1,c2=st.columns(2,gap='small')
            with c1:
                guests[meal]=int(st.number_input(f'{meal} guests',min_value=0,step=1,key=f'gst_{meal}'))
            with c2:
                table_key=f'tbl_{meal}'
                auto=math.ceil(guests[meal]/number(po_settings['Tables_Per_Guests'])) if guests[meal] else 0
                previous=st.session_state.get('_auto_'+meal,None)
                if table_key not in st.session_state or (previous is not None and st.session_state[table_key]==previous):
                    st.session_state[table_key]=auto
                st.session_state['_auto_'+meal]=auto
                tables[meal]=int(st.number_input(f'{meal} tables',min_value=0,step=1,key=table_key))
        small_water=st.checkbox('Small water for breakfast/lunch',value=False,
            disabled=not(guests['Breakfast'] or guests['Lunch']))
        c1,c2=st.columns(2,gap='small')
        with c1:soft_package=st.selectbox('Soft drinks',["Regular","Glass","Canned"],disabled=guests['Dinner']==0)
        with c2:mixer_package=st.selectbox('Mixers',["Regular","Glass","Canned"],disabled=guests['Dinner']==0)
        juice_choices=sorted((str(i) for i,v in ingredients.items()
             if str(v.get('category','')).strip().casefold()=='juices'),
             key=lambda i:str(ingredients[i].get('item','')).casefold())
        juice_ids={}
        for meal in MEALS:
            if guests[meal] and juice_choices:
                preferred=identifier(po_settings.get(f'{meal}_Juice_ID',''))
                juice_ids[meal]=st.selectbox(f'{meal} table juice',juice_choices,
                    index=juice_choices.index(preferred) if preferred in juice_choices else 0,
                    format_func=lambda i:ingredients[i]['item'],key='juice_'+meal)
            else:juice_ids[meal]=identifier(po_settings.get(f'{meal}_Juice_ID',''))
        st.subheader('Select - Cocktail/Mocktail')
        chosen_recipes=[]
        for n in range(6):
            selector,amount=st.columns([4,1.05],gap='small')
            with selector:
                selected_name=st.selectbox(f'Drink {n+1}', ['']+list(by_name),
                    key=f'drink_{n}',label_visibility='collapsed',
                    format_func=lambda x:x if x else f'Drink {n+1} · Choose')
            with amount:
                servings=int(st.number_input(f'Qty {n+1}',min_value=0,max_value=999,step=1,
                    key=f'drink_qty_{n}',label_visibility='collapsed',help='Up to three digits'))
            if selected_name and servings:chosen_recipes.append((selected_name,servings))
        st.caption('Cocktail alcohol is omitted from the PO when Alcohol Package is off; mixers and garnishes remain.')

    # Admin owns the editable formula guides; only the meal totals are editable on this page.
    live_rules=rules
    meal_details,calc_issues=calculate_meal_detail(live_rules,ingredients,guests,tables,
        soft_package,mixer_package,juice_ids,small_water)


# -------- Meal-wise breakdown: LEFT, below Select - Cocktail/Mocktail --------
with calc_left:
    st.divider();st.subheader('Meal-wise Breakdown')
    st.caption('One ingredient per row: Breakfast, Lunch, Dinner and Total. Edits here override meal-rule totals and immediately update the purchase orders.')
    pivot=pivot_meals(meal_details,ingredients)
    st.session_state.setdefault('meal_override_v3',{})
    meal_edits=st.session_state.meal_override_v3
    for r in pivot:
        for meal in MEALS:r[meal]=meal_edits.get((r['ID'],meal),r[meal])
        r['Total']=round(sum(number(r[meal]) for meal in MEALS),4)
    base_pivot=pivot_meals(meal_details,ingredients)
    sig=hashlib.sha256(repr([(r['ID'],r['Ingredient']) for r in pivot]).encode()).hexdigest()[:10]
    if True:
        editor=st.data_editor(pd.DataFrame(pivot,columns=['ID','Breakfast','Lunch','Dinner','Ingredient','Total','Unit']),
            hide_index=True,use_container_width=True,key=f'meal_v3_{sig}_{st.session_state.get("meal_reset_v3",0)}',
            disabled=['ID','Ingredient','Total','Unit'],column_config={
              'ID':None,
              'Ingredient':st.column_config.TextColumn(width=165),
              'Total':st.column_config.NumberColumn(width=65,format='%.2f'),
              **{m:st.column_config.NumberColumn(label=m[:2].upper(),min_value=0,step=.1,format='%.2f',width=60) for m in MEALS}})
    st.caption('Totals are in purchasing packs; edited quantities update the PO. Pack sizes come from Google Sheets.')
    # Reconstruct meal demands from the pivot so manual per-meal overrides take precedence.
    meal_final=[]
    by_auto={r['ID']:r for r in base_pivot}
    for rec in editor.to_dict('records'):
        iid=identifier(rec['ID']);m=ingredients[iid];factor=pack_factor(m)
        for meal in MEALS:
            q=number(rec.get(meal));auto=number(by_auto.get(iid,{}).get(meal))
            if abs(q-auto)>1e-8:meal_edits[(iid,meal)]=q
            else:meal_edits.pop((iid,meal),None)
            if q>0:meal_final.append({'Ingredient ID':iid,'Meal':meal,'base_units':q*factor})
    if st.button('Reset meal edits',key='reset_meals_v3'):
        st.session_state.meal_override_v3={}
        st.session_state.meal_reset_v3=st.session_state.get('meal_reset_v3',0)+1
        st.rerun()


# -------- Alcohol Package: RIGHT column --------
def alcohol_choices(master, matrix):
    """Category-first list. Prosecco is grouped with sparkling wine."""
    eligible={str(x.get('category','')).strip().casefold() for x in matrix}
    eligible.update({str(v.get('category','')).strip().casefold() for v in master.values() if category_label(v) in ('Wines','Beer','Spirits','Liqueur')})
    display={}
    for iid, m in master.items():
        cat=str(m.get('category','')).strip()
        if cat.casefold() not in eligible:
            continue
        grouped='Sparkling Wine / Champagne' if cat.casefold()=='prosecco' else cat
        display.setdefault(grouped,[]).append(iid)
    # Display categories in Google matrix order, then additional master categories.
    matrix_order=list(dict.fromkeys('Sparkling Wine / Champagne' if str(x.get('category','')).casefold()=='prosecco' else str(x.get('category','')) for x in matrix))
    ordered=[x for x in matrix_order if x in display]+sorted(set(display)-set(matrix_order))
    for cat in display:
        display[cat]=sorted(display[cat],key=lambda iid:str(master[iid].get('item','')).casefold())
    return ordered,display


def alcohol_services(category,matrix):
    guide_category=('Sparkling Wine / Champagne' if str(category).casefold()=='prosecco' else category)
    choices=list(dict.fromkeys(str(row.get('service','')).strip() for row in matrix
                               if str(row.get('category','')).strip().casefold()==guide_category.casefold()
                               and str(row.get('service','')).strip()))
    return choices or ['Bar']


with calc_right:
    st.subheader('Alcohol Package')
    include_alcohol=st.checkbox('Alcohol Package by Ragasaan?',value=False,
                                 disabled=guests['Dinner']==0,key='include_alcohol_v3')
    alcohol_raw={};alcohol_issues=[]
    if include_alcohol and guests['Dinner']:
        st.caption('Alcohol guide units and bottles per guide unit are read from PO_Alcohol_Matrix. ' 
                   'Override the guide quantity in the same row; updated PO quantities appear in Purchase Order preview.')
        categories, category_items=alcohol_choices(ingredients,alcohol_matrix)
        if 'alcohol_rows_v32' not in st.session_state:
            # 20 initial lines arranged by category; Add Item remains below.
            starters=initial_alcohol_categories(categories,20)
            st.session_state.alcohol_rows_v32=list(range(1,len(starters)+1))
            st.session_state.alcohol_next_v32=len(st.session_state.alcohol_rows_v32)+1
            for rid,category in enumerate(starters,start=1):
                st.session_state[f'alcohol_cat_v32_{rid}']=category
        row_ids=st.session_state.alcohol_rows_v32
        # Resolve all current selections BEFORE drawing rows: each widget update
        # already exists in session_state at the beginning of Streamlit's rerun.
        chosen=[]
        for rid in row_ids:
            cat_key=f'alcohol_cat_v32_{rid}'; item_key=f'alcohol_item_v32_{rid}'
            cat=st.session_state.get(cat_key,'')
            previous=f'alcohol_prev_cat_v32_{rid}'
            if cat!=st.session_state.get(previous,cat):
                st.session_state.pop(item_key,None)
                st.session_state.pop(f'alcohol_override_v32_{rid}',None)
                st.session_state.pop(f'alcohol_service_v32_{rid}',None)
            st.session_state[previous]=cat
            allowed=category_items.get(cat,[])
            iid=str(st.session_state.get(item_key,'') or '')
            if iid not in allowed:
                st.session_state.pop(item_key,None)
                continue
            services=alcohol_services(cat,alcohol_matrix)
            service=st.session_state.get(f'alcohol_service_v32_{rid}',services[0])
            if service not in services:service=services[0]
            override=st.session_state.get(f'alcohol_override_v32_{rid}')
            chosen.append({'id':iid,'service':service,'override':override})
        alcohol_raw,alcohol_guide,alcohol_issues=alcohol_demand(chosen,alcohol_matrix,ingredients,guests['Dinner'],(number(po_settings['Alcohol_First_Variant_Share']),number(po_settings['Alcohol_Second_Variant_Share'])))
        summaries={str(x.get('ingredient_id')):x for x in alcohol_guide}
        # Keep inputs and guide on the same line. The resulting purchase quantity
        # is still calculated for the PO, but is not duplicated in this table.
        headers=['Category','Ingredient','Service','Guide','Manual','Guide unit','']
        widths=[1.6,4.6,1.25,.72,1.05,1.15,.34]
        cols=st.columns(widths,gap='small')
        for col,heading in zip(cols,headers):
            with col:st.markdown(f'<div style="font-size:.71rem;font-weight:600;line-height:1.1;white-space:normal">{heading}</div>',unsafe_allow_html=True)
        removed_id=None
        for rid in row_ids:
            cols=st.columns(widths,gap='small')
            with cols[0]:
                cat=st.selectbox('Category',['']+categories,key=f'alcohol_cat_v32_{rid}',
                                 label_visibility='collapsed',format_func=lambda x:x or 'Select category')
            ids=category_items.get(cat,[])
            item_key=f'alcohol_item_v32_{rid}'
            if st.session_state.get(item_key,'') not in ['']+ids:
                st.session_state.pop(item_key,None)
            with cols[1]:
                iid=st.selectbox('Ingredient',['']+ids,key=item_key,label_visibility='collapsed',
                                 format_func=lambda v:ingredients[v]['item'] if v else 'Select ingredient')
            services=alcohol_services(cat,alcohol_matrix)
            service_key=f'alcohol_service_v32_{rid}'
            if st.session_state.get(service_key) not in services:
                st.session_state.pop(service_key,None)
            with cols[2]:
                if len(services)>1:
                    st.selectbox('Service',services,key=service_key,label_visibility='collapsed')
                else:
                    st.markdown('<div style="padding-top:.48rem;font-size:.75rem">Bar</div>',unsafe_allow_html=True)
            summary=summaries.get(str(iid),{})
            with cols[3]:
                val=summary.get('Guide quantity')
                st.markdown(f'<div style="padding-top:.48rem;font-size:.79rem;text-align:right">{val:,.2f}</div>' if isinstance(val,(int,float)) else '—',unsafe_allow_html=True)
            with cols[4]:
                st.number_input('Manual quantity',min_value=0.,value=None,step=1.,format='%.1f',
                                key=f'alcohol_override_v32_{rid}',label_visibility='collapsed',
                                help='Leave blank to use the guide value. Conversion is read from PO_Alcohol_Matrix.')
            with cols[5]:
                unit=str(summary.get('Guide unit','—'))
                shorten={}
                st.markdown(f'<div style="padding-top:.48rem;font-size:.75rem">{shorten.get(unit,unit)}</div>',unsafe_allow_html=True)
            with cols[6]:
                if st.button('×',key=f'alcohol_remove_v32_{rid}',help='Remove alcohol row'):
                    removed_id=rid
        if removed_id is not None:
            st.session_state.alcohol_rows_v32=[x for x in row_ids if x!=removed_id]
            st.rerun()
        if st.button('＋ Add alcohol item',key='alcohol_add_row_v32'):
            rid=st.session_state.alcohol_next_v32
            st.session_state.alcohol_next_v32=rid+1
            st.session_state.alcohol_rows_v32.append(rid)
            st.rerun()
        st.caption('Guide and Manual use the guide units from Google Sheets; final bottles/cases are calculated in the Purchase Order preview using the current Case Size.')
        for issue in alcohol_issues:st.warning(issue)
    else:st.caption('Enter dinner guests in Calculation to enable this section.')

# -------- Purchase Order and Downloads --------
with page_po:
    page_heading('Purchase Order', 'Source-wise purchasing preview and Word downloads')
    recipe_raw,cocktail_names,drink_issues=recipe_demand(chosen_recipes,by_name,ingredients)
    recipe_raw,cocktail_names,excluded_alcohol=omit_alcohol_recipe_ingredients(
        recipe_raw,cocktail_names,ingredients,alcohol_matrix,include_alcohol)
    if excluded_alcohol:
        st.info('Alcohol Package is disabled: cocktail alcoholic ingredients excluded: '+', '.join(sorted(set(excluded_alcohol))))
    st.subheader('Purchase Order — source-wise preview')
    st.session_state.setdefault('source_overrides_v3',{})
    st.session_state.setdefault('po_qty_overrides_v3',{})
    preliminary=order_from_demand(meal_final,recipe_raw,alcohol_raw,ingredients,cocktail_names,
                                st.session_state.source_overrides_v3,st.session_state.po_qty_overrides_v3,supplier_prices)
    st.caption('Change an ingredient’s Source or final order quantity here. Cases are rounded UP after consolidating demand for the same ingredient. Source=Unit orders individual bottles/items (or racks for glassware). Source changes are only for this PO.')
    with st.expander('⚙️ Adjust source or order quantity (optional)',expanded=False):
        row_options=[{'ID':row['ingredient_id'],'Item':row['Ingredient'],'Source':row['Source'],
                      'Calculated':row['Computed'],'Qty override':st.session_state.po_qty_overrides_v3.get(row['ingredient_id'],None),
                      'Unit':row['Unit']} for row in preliminary]
        sig=hashlib.sha256(repr([(x['ID'],x['Source']) for x in row_options]).encode()).hexdigest()[:10]
        changed=st.data_editor(pd.DataFrame(row_options,columns=['ID','Item','Source','Calculated','Qty override','Unit']),
              hide_index=True,use_container_width=True,key=f'source_editor_v3_{sig}',
              disabled=['ID','Item','Calculated','Unit'],
              column_config=compact_columns(pd.DataFrame(row_options),{
                             'ID':None,'Source':st.column_config.SelectboxColumn(options=list(SOURCE_CHOICES),width=105),
                             'Qty override':st.column_config.NumberColumn(min_value=0,step=1,width=72)}))
        switched=False
        for r in changed.to_dict('records'):
            iid=identifier(r['ID']);src=str(r.get('Source') or '')
            if src in SOURCE_CHOICES:
                if src!=st.session_state.source_overrides_v3.get(iid,ingredients[iid].get('Source')):
                    st.session_state.source_overrides_v3[iid]=src
                    st.session_state.po_qty_overrides_v3.pop(iid,None)
                    switched=True
            qty=r.get('Qty override')
            if qty is None or pd.isna(qty) or str(qty).strip()=='':
                st.session_state.po_qty_overrides_v3.pop(iid,None)
            else:st.session_state.po_qty_overrides_v3[iid]=number(qty)
        if switched:st.rerun()
        if st.button('Reset PO source and quantity changes',key='reset_po_changes_v3'):
            st.session_state.source_overrides_v3={};st.session_state.po_qty_overrides_v3={};st.rerun()
    order=order_from_demand(meal_final,recipe_raw,alcohol_raw,ingredients,cocktail_names,
                         st.session_state.source_overrides_v3,st.session_state.po_qty_overrides_v3,supplier_prices)
    vendors=records(SHEET_NAMES['vendors']);venues=records(SHEET_NAMES['venue']);contacts=records(SHEET_NAMES['contacts'])
    # The original design places compact event/delivery fields in the left rail.
    # These are the same Streamlit session keys used in earlier versions.
    with st.sidebar:
        with st.expander('📅 Event & delivery information',expanded=True):
            venue=lookup_select('Delivery venue',venues,'name','po_venue')
            delivery_date=st.date_input('Delivery date',key='po_delivery_date')
            contact=lookup_select('Contact on day',contacts,'name','po_contact')
            delivery_time=st.time_input('Delivery time',key='po_delivery_time',step=900)
            vat=st.number_input('VAT %',value=float(number(po_settings['Default_VAT_Percent'])),
                                min_value=0.,max_value=100.,step=.5)
            venue_name=str(venue.get('name',''))
            if st.session_state.get('_last_venue')!=venue_name:
                st.session_state['po_address']=str(venue.get('address',''))
                st.session_state._last_venue=venue_name
            address=st.text_input('Delivery address',key='po_address')
            if CLOUD_MODE:
                logo_bytes=fetch_cloud_logo(po_settings,store.credentials,bucket=str(secrets_value('gcs_image_bucket','')))
            else:
                logo_bytes=load_default_logo()
            if logo_bytes:
                st.image(BytesIO(logo_bytes),width=85,caption='Company logo')
            else:
                st.caption('Company logo can be added under Admin Settings.')
    meta={'po_date':datetime.now(ZoneInfo('Europe/London')).strftime('%d/%m/%Y'),
          'venue':venue_name,'address':address,'delivery_date':delivery_date.strftime('%d/%m/%Y'),
          'delivery_time':delivery_time.strftime('%H:%M'),
          'contact':f"{contact.get('name','')} · {contact.get('phone','')}"}
    st.caption('Choose a source to view its complete order beside a Word-style preview. '
               'All three source-specific Word downloads remain available below.')
    inventory_for_po=st.checkbox('Include alcohol inventory page in relevant Word PO',value=True,
                                 disabled=not bool(include_alcohol and alcohol_raw))
    source_preview=st.radio('Select purchase-order source',SOURCE_CHOICES,
        horizontal=True,key='po_source_preview_v36')
    purchase_left,purchase_right=st.columns([2.15,1.0],gap='medium')
    downloadable=[]
    # Build all orders and Word files from the same shared calculation results.
    for src in SOURCE_CHOICES:
        subset=sorted([r.copy() for r in order if r['Source'].casefold()==src.casefold()],
            key=lambda x:(purchase_category(x.get('Category')),str(x['Ingredient']).casefold()))
        meal_breakdown={}
        for item in meal_final:
            iid=identifier(item['Ingredient ID']);key=(iid,item['Meal'])
            meal_breakdown[key]=meal_breakdown.get(key,0)+number(item['base_units'])
        for item in subset:
            unit_factor=pack_factor(ingredients[item['ingredient_id']],item['Source'])
            item['Meal display']={meal:round(meal_breakdown.get((item['ingredient_id'],meal),0)/unit_factor,2)
                                  for meal in MEALS}
        vendor_name='UNIT'
        if src!='Unit':
            options=[str(v.get('vendor_name','')) for v in vendors if v.get('vendor_name')]
            if not options:options=['Unassigned supplier']
            default=next((i for i,x in enumerate(options)
                if (src=='Majestics' and 'majestic' in x.casefold())
                or (src=='Supplier' and 'timesaver' in x.casefold())),0)
            if src==source_preview:
                with purchase_left:
                    vendor_name=st.selectbox(f'Supplier for {src}',options,index=default,key='vendor_source_'+src)
            else:
                vendor_name=st.session_state.get('vendor_source_'+src,options[default])
                if vendor_name not in options:vendor_name=options[default]
        source_meta={**meta,'vendor':vendor_name,'source':src,'vat':vat,
                     'company':po_settings.get('Company_Name','Ragasaan')}
        downloadable.append((src,subset,source_meta))
        if src!=source_preview:continue
        with purchase_left:
            category_caption(f'{src.upper() if src=="Unit" else src} · {len(subset)} items','▣')
            grouped_rows=grouped_preview_rows(subset)
            df=pd.DataFrame([{k:r[k] for k in ('Name','Qty','Unit','Remarks')}
                             for r in grouped_rows],columns=['Name','Qty','Unit','Remarks'])
            if not df.empty:
                df['Qty']=pd.to_numeric(df['Qty'],errors='coerce').apply(
                    lambda v:math.ceil(v-1e-10) if pd.notna(v) else pd.NA).astype('Int64')
                heading_positions={i for i,r in enumerate(grouped_rows) if r['_heading']}
                def preview_style(row):
                    if row.name not in heading_positions:return ['' for _ in row]
                    category=str(grouped_rows[row.name]['Name']);key=category.casefold()
                    if any(x in key for x in ('water','juice','soft')):bg='#e4efff';fg='#315f92'
                    elif 'mixer' in key:bg='#e5f3ea';fg='#317151'
                    elif any(x in key for x in ('puree','purée','syrup')):bg='#fff0de';fg='#9d602c'
                    elif any(x in key for x in ('wine','sparkling','champagne')):bg='#fbe7ed';fg='#8e4e70'
                    elif 'beer' in key:bg='#eae5fc';fg='#574da6'
                    elif any(x in key for x in ('spirit','liqueur','alcohol')):bg='#f9efdc';fg='#8c6834'
                    else:bg='#edf1fa';fg='#3e5f83'
                    return [f'font-weight:750;background-color:{bg};color:{fg}' for _ in row]
                preview_table=df.style.apply(preview_style,axis=1)
            else:preview_table=df
            st.dataframe(preview_table,hide_index=True,use_container_width=True,height=515,
                column_config=compact_columns(df,{
                    'Name':st.column_config.TextColumn('Item / Category',width=290),
                    'Qty':st.column_config.NumberColumn('Qty',width=68,format='%d'),
                    'Unit':st.column_config.TextColumn(width=84),
                    'Remarks':st.column_config.TextColumn(width=190)}))
        with purchase_right:
            st.markdown('**📄 Word purchase-order preview**')
            st.markdown(document_preview_html(subset,source_meta),unsafe_allow_html=True)
            st.caption('Visual approximation; download the Word file for the final printable PO.')
    st.markdown('**Download purchase orders**')
    download_cols=st.columns(3,gap='small')
    for (src,subset,source_meta),col in zip(downloadable,download_cols):
        with col:
            st.download_button(f'⬇ {src} Word PO',data=create_docx(subset,source_meta,logo_bytes,
                subset if inventory_for_po and inventory_items_for_source(subset,ingredients) else None,
                subset,ingredients),
                file_name=f'Ragasaan_PO_{src}.docx',
                mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                key='word_po_v36_'+src,use_container_width=True)

    net=sum(x['Net'] for x in order)
    mcols=st.columns(3)
    mcols[0].metric('Estimated Net',f'£{net:,.2f}')
    mcols[1].metric('Estimated VAT',f'£{net*vat/100:,.2f}')
    mcols[2].metric('Estimated Gross',f'£{net*(1+vat/100):,.2f}')
    with st.expander('Verify bottle-to-case conversions'):
        audit=[{'Item':r['Ingredient'],'Source':r['Source'],
                'Required bottles/items':round(r['Raw demand'],3),
                'Case/rack size':int(r['Case size']) if r['Case size'] else 1,
                'Order qty':r['Quantity'],'Order unit':r['Unit'],
                'Supplied singles':round(r['Quantity']*(pack_factor(ingredients[r['ingredient_id']],r['Source'])),3)}
               for r in order]
        audit_frame=pd.DataFrame(audit)
        st.dataframe(audit_frame,hide_index=True,use_container_width=True,
                     column_config=compact_columns(audit_frame))
    st.caption('Prices are estimates based on PO_Supplier_Prices for the chosen source where present; otherwise Ingredients.unit_price using Ingredients.price_basis. Verify all quotations before ordering.')
    all_issues=calc_issues+drink_issues+alcohol_issues
    if all_issues:
        with st.expander(f'Calculation warnings ({len(all_issues)})'):
            for issue in all_issues:st.warning(issue)
    if recipe_issues:st.caption(f'Recipe ID mismatches: {len(recipe_issues)} · see Admin Settings')

# -------- Admin --------
with page_admin:
    page_heading('Admin Settings', 'Manage recipes, master data, calculations and users')
    if not admin():
        st.warning("Admin-only area. Recipe modifications and master data are protected.")
    else:
        st.subheader("Administrator settings")
        st.caption("Changes are written directly to Google Sheets and may affect all users. Download a Google Sheet backup before saving.")
        if CLOUD_MODE:
            with st.expander('Company logo — persistent Google Drive storage'):
                st.caption('Save the logo in a Google Workspace Shared Drive folder. It persists across cloud restarts and redeploys.')
                current_logo=fetch_cloud_logo(po_settings,store.credentials,bucket=str(secrets_value('gcs_image_bucket','')))
                if current_logo:st.image(BytesIO(current_logo),width=170)
                drive_folder=str(po_settings.get('Recipe_Image_Drive_Folder_ID','')).strip()
                cloud_bucket=str(secrets_value('gcs_image_bucket','')).strip()
                if not drive_folder and not cloud_bucket:st.warning('Configure a Shared Drive folder below, or set gcs_image_bucket in Streamlit Cloud Secrets.')
                logo_upload=st.file_uploader('Upload permanent logo (PNG or JPG)',type=['png','jpg','jpeg'],key='cloud_company_logo')
                if st.button('Save permanent company logo',disabled=not bool(logo_upload and (drive_folder or cloud_bucket)),key='cloud_save_logo'):
                    try:
                        save_cloud_logo(store,records(SHEET_NAMES['settings']),drive_folder,logo_upload.name,logo_upload.getvalue(),bucket=cloud_bucket)
                        after_save('Company logo saved in private Google Drive')
                    except Exception:
                        st.error('Could not upload logo. Check the Shared Drive write permission or private Cloud Storage bucket access.')
                if st.button('Remove cloud logo reference',key='cloud_clear_logo'):
                    clear_cloud_logo(store,records(SHEET_NAMES['settings']))
                    after_save('Cloud logo reference removed; the file remains in Drive')
            st.info('Google credentials are stored only in Streamlit Community Cloud Secrets; they cannot be uploaded in the web app.')
        else:
            with st.expander('Company logo — automatically load on every startup'):
                st.caption('Upload the Ragasaan logo once. It is saved locally in the application assets folder and reused in PO previews and Word downloads. The logo is not stored in Google Sheets. If no local logo exists, the app tries the previously supplied Google Drive image URL when first opened.')
                existing_logo=load_default_logo()
                if existing_logo:st.image(BytesIO(existing_logo),width=170)
                candidate=st.file_uploader('Set default logo (PNG or JPG)',type=['png','jpg','jpeg'],key='admin_default_logo')
                logo_actions=st.columns(2)
                with logo_actions[0]:
                    if st.button('Save as default company logo',key='save_default_logo',disabled=candidate is None):
                        try:
                            save_logo(candidate.getvalue())
                            st.success('Company logo saved for future launches.');st.rerun()
                        except (ValueError,OSError) as exc:st.error(str(exc))
                with logo_actions[1]:
                    if st.button('Remove local logo',key='remove_default_logo'):
                        clear_logo();st.rerun()
            with st.expander("Connect Google Sheets using JSON upload", expanded=not store.writable):
                st.write("Upload a newly generated Google service-account JSON key. The key is kept in server session memory, not saved to disk.")
                st.caption("Share the spreadsheet with the service-account email as Editor first. Do not reuse the exposed old key.")
                with st.form("admin_google_connection"):
                    target_id=st.text_input("Google Spreadsheet ID",value=SHEET_ID)
                    key_file=st.file_uploader("Service-account JSON file",type=["json"])
                    remember_admin=st.checkbox('Remember key in OS credential vault for automatic startup',value=True)
                    connect_clicked=st.form_submit_button("Connect Google Sheets",type="primary")
                if connect_clicked:
                    try:
                        import json
                        if key_file is None:raise ValueError("Select a JSON file")
                        payload=json.loads(key_file.getvalue().decode("utf-8"))
                        if payload.get("type")!="service_account" or not payload.get("client_email") or not payload.get("private_key"):
                            raise ValueError("Not a valid service-account JSON")
                        connected=connect_gsheet(target_id.strip(),json.dumps(payload,sort_keys=True))
                        if not connected.read("Users"):raise ValueError("Users worksheet not found")
                        st.session_state.store=connected
                        if remember_admin:
                            try:save_connection_to_keyring(target_id.strip(),payload)
                            except Exception:st.warning('Connected, but OS keyring storage was unavailable.')
                        st.session_state.pop("preview_sha",None)
                        st.session_state["refresh_count"]=st.session_state.get("refresh_count",0)+1
                        read_grid.clear()
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Connection failed ({type(exc).__name__}). Check your key, spreadsheet ID, API access and sharing permissions.")
                if store.writable:st.success("Live Google Sheets connected")
        with st.expander('Recipe images · Shared Drive / Cloud Storage setup'):
            st.caption('Suggested images come from Wikimedia Commons. For private uploads use a Google Workspace Shared Drive folder or configure a Cloud Storage bucket in Streamlit Secrets (useful for personal Gmail accounts).')
            folder=st.text_input('Recipe Image Drive Folder ID',
                  value=str(po_settings.get('Recipe_Image_Drive_Folder_ID','')),
                  help='Use a folder within a Google Workspace Shared Drive, or set gcs_image_bucket in Streamlit Cloud Secrets instead (no folder needed for GCS).')
            if st.button('Save Recipe image folder',key='save_recipe_drive_folder'):
                settings_rows=records(SHEET_NAMES['settings'])
                remaining=[r for r in settings_rows if str(r.get('Setting',''))!='Recipe_Image_Drive_Folder_ID']
                remaining.append({'Setting':'Recipe_Image_Drive_Folder_ID','Value':folder.strip()})
                store.save_table(SHEET_NAMES['settings'],remaining,['Setting','Value'])
                after_save('Recipe image Drive folder saved')
            st.caption('Image references are stored in PO_Recipe_Images. Private uploads remain in Shared Drive or Cloud Storage; Streamlit fetches them using the service account.')
        maintenance,master,recipe_admin,calc_settings,guide_help,account=st.tabs([
            "📦 Vendors & Venues", "🥫 Ingredients Master", "📒 Recipe Management",
            "🧮 Editable formulas", "📖 Calculation Guide", "🔐 Users & diagnostics"])
        with recipe_admin:
            render_recipe_management(recipes=recipes,ingredients=ingredients,matrix=recipe_matrix,
                store=store,grid=grid,records=records,settings=po_settings,
                recipe_suggestion=recipe_suggestion,after_save=after_save,
                image_bucket=str(secrets_value('gcs_image_bucket','')))
        with maintenance:
            maintenance_cols=st.columns(2,gap='small')
            for ix,(key,col) in enumerate([("vendors","Vendor Data"),("venue","Venue Data"),("contacts","Ragasaan Contacts")]):
                with maintenance_cols[ix%2]:
                    sheet=SHEET_NAMES[key]
                    with st.expander(col):
                        headers=[str(h) for h in grid(sheet)[0]] if grid(sheet) else []
                        editor_table(sheet,col,headers)
        with maintenance:
            st.subheader('Supplier-specific price upload & Google Sheets backup')
            st.caption('Upload CSV/Excel with Source, ingredient_id, net_price, price_basis (Pack or Single). Missing supplier prices fall back to Ingredients.unit_price.')
            uploaded_prices=st.file_uploader('Supplier pricing CSV / Excel',type=['csv','xlsx'],key='price_upload_v33')
            if uploaded_prices is not None:
                price_frame=(pd.read_csv(uploaded_prices,dtype=str).fillna('') if uploaded_prices.name.lower().endswith('.csv') else pd.read_excel(uploaded_prices,dtype=str,keep_default_na=False).fillna(''))
                needed={'Source','ingredient_id','net_price','price_basis'}
                if not needed.issubset(set(price_frame.columns)):
                    st.error('Required columns: '+', '.join(sorted(needed)))
                else:
                    st.dataframe(price_frame.head(25),hide_index=True,use_container_width=True)
                    if st.button('Merge supplier prices to Google Sheets',key='merge_prices_v33',type='primary'):
                        existing=records(SHEET_NAMES['prices'])
                        indexed={(str(r.get('Source','')).casefold(),identifier(r.get('ingredient_id'))):dict(r) for r in existing}
                        errors=[]
                        for row in price_frame.to_dict('records'):
                            src=str(row['Source']).strip();iid=identifier(row['ingredient_id'])
                            try:price=float(row['net_price'])
                            except (ValueError,TypeError):errors.append(f'{src} {iid}: price invalid');continue
                            basis=str(row['price_basis']).strip().title()
                            if src not in SOURCE_CHOICES or iid not in ingredients or price<0 or basis not in ('Pack','Single'):
                                errors.append(f'{src} {iid}: unrecognised source/ID/price/basis');continue
                            indexed[(src.casefold(),iid)]={**row,'Source':src,'ingredient_id':iid,'net_price':price,'price_basis':basis,'updated_at':datetime.now(ZoneInfo('Europe/London')).isoformat(timespec='seconds')}
                        if errors:st.error('No prices saved. Issues: '+', '.join(errors[:15]))
                        else:
                            store.save_table(SHEET_NAMES['prices'],list(indexed.values()),PRICE_COLUMNS)
                            after_save(f'{len(price_frame)} supplier prices merged')
            from zipfile import ZipFile, ZIP_DEFLATED
            import csv
            def backup_workbook_csv_zip():
                buffer=BytesIO()
                with ZipFile(buffer,'w',ZIP_DEFLATED) as archive:
                    for ws in store.book.worksheets():
                        values=ws.get_all_values(value_render_option='FORMULA')
                        output=BytesIO();stream=__import__('io').TextIOWrapper(output,encoding='utf-8-sig',newline='',write_through=True)
                        writer=csv.writer(stream);writer.writerows(values);stream.flush()
                        archive.writestr(ws.title.replace('/','_')+'.csv',output.getvalue())
                return buffer.getvalue()
            if st.button('Prepare Google Sheets backup (all tabs)',key='backup_v33'):
                try:st.session_state['backup_data_v33']=backup_workbook_csv_zip()
                except Exception as exc:st.error('Backup failed. Try refreshing or check Sheets read quota: '+type(exc).__name__)
            if st.session_state.get('backup_data_v33'):
                st.download_button('Download Google Sheets backup ZIP',st.session_state.backup_data_v33,
                  'Ragasaan_Google_Sheets_Backup.zip',mime='application/zip',key='backup_down_v33')
            st.subheader('Sync revised calculation workbook')
            st.caption('Back up your LIVE Google Sheet first. Only the selected tabs are replaced. Selecting Ingredients (optional) replaces the ENTIRE ingredient master, including existing prices, so compare current live data before importing. Recipe, Users, Vendors, Contacts and Venue are never overwritten.')
            sync_upload=st.file_uploader('Updated rule workbook (.xlsx)',type=['xlsx'],key='sync_v33')
            sync_names=st.multiselect('Sheets to sync (select Ingredients only if you intend to replace the entire master)',['PO_Rules','PO_Alcohol_Matrix','PO_Settings','PO_Supplier_Prices','Ingredients'],default=['PO_Rules','PO_Alcohol_Matrix','PO_Settings','PO_Supplier_Prices'],key='sync_tabs_v33')
            sync_confirm=st.checkbox('I confirm I want to overwrite selected Google Sheets tabs',key='sync_confirm_v33')
            if st.button('Sync selected configuration tabs',type='primary',key='sync_execute_v33',disabled=not(sync_upload and sync_confirm and sync_names)):
                import_frame=pd.read_excel(BytesIO(sync_upload.getvalue()),sheet_name=None,dtype=object,keep_default_na=False)
                if any(n not in import_frame for n in sync_names):st.error('Some selected tabs are missing in the workbook')
                else:
                    for n in sync_names:
                        df_up=import_frame[n].fillna('')
                        store.save_table(n,df_up.to_dict('records'),list(df_up.columns))
                    after_save('Configuration tabs synced from workbook')
        with master:
            st.caption("Source of truth: ingredient ID, name, Bottle Size, unit, Source, Yield, case size and unit_price.")
            headers=[str(h) for h in grid("Ingredients")[0]] if grid("Ingredients") else []
            editor_table("Ingredients","Ingredients Master",headers)
            st.info("The Recipe Book is read-only. Use Admin Settings → Recipe Management to edit, add, delete, or manage recipe images. A new ingredient ID must first exist in the Recipe matrix header.")
        with guide_help:
            st.subheader("Calculation Guide — live rules and units")
            st.caption("These explanations are generated from the connected Ingredients, PO_Rules, "
                       "PO_Alcohol_Matrix and PO_Settings sheets. No ingredient bottle, case, "
                       "yield, alcohol multiplier or guest ratio is embedded in this guide. "
                       "Refresh spreadsheet data after changing a rule.")
            st.markdown("**Formula symbols**")
            st.dataframe(pd.DataFrame([{'Symbol':k,'Meaning':v} for k,v in variables_from_master(ingredients).items()]),
                         hide_index=True,use_container_width=True)
            st.info("**Purchasing:** First combine demand from Breakfast, Lunch, Dinner, cocktails and alcohol "
                    "as individual bottles/items/glasses for each ingredient. Then convert once: "
                    "PO Qty = ceil(total individual demand ÷ PACK), where PACK comes from "
                    "Ingredients.case size and Source. For Unit glassware, this produces "
                    "complete racks/rolls. An ingredient with Case Size = 1 is displayed as "
                    "Bottle or Unit, not Case.")
            st.caption("For an Individual-basis rule, the formula returns bottles/items; "
                       "for a Purchase-basis rule, the formula already returns fractional purchase packs. "
                       "See each rule's Returns and Conversion columns below. Do not divide Purchase "
                       "formulas by Case Size a second time.")
            guide_rows=describe_rule_rows(rules,ingredients,po_settings)
            rule_panels=st.columns(2,gap='small')
            for index,label in enumerate(RULE_GROUPS):
                group_rows=[r for r in guide_rows if r['Category']==label]
                if not group_rows:continue
                with rule_panels[index%2]:
                    with st.expander(f"{label} — {len(group_rows)} live formulas",expanded=(index==0)):
                        display_cols=['Meal','Package','Ingredient','Formula','Returns','Conversion',
                                      'PO unit','PACK','Bottle Size','Measure','Yield','Case Size','Source','Enabled','Rule ID']
                        frame=pd.DataFrame(group_rows,columns=['Category']+display_cols)[display_cols]
                        st.dataframe(frame,hide_index=True,use_container_width=True,
                                     column_config=compact_columns(frame))
            st.divider()
            st.subheader("Alcohol Package — guide band to PO conversion")
            st.caption("Guest anchors and guide quantities are taken from PO_Alcohol_Matrix. "
                       "An event guest count between two anchors is interpolated. "
                       "The resulting guide quantity is multiplied by that row's "
                       "bottles_per_guide_unit; complete supplier packs are ordered using the "
                       "selected ingredient's current Case Size and Source. This is why wine, "
                       "beer and spirits can have different guide units without code changes.")
            ar=describe_alcohol_rows(alcohol_matrix)
            if ar:
                af=pd.DataFrame(ar)
                st.dataframe(af,hide_index=True,use_container_width=True,column_config=compact_columns(af))
            else:st.error("No PO_Alcohol_Matrix rows available")
            st.divider()
            st.subheader("Cocktails, Mocktails, Garnish Yield & Glassware")
            st.markdown("**Liquids and measured ingredients:** recipe quantity per drink × servings "
                        "÷ Ingredients.Bottle Size = individual bottles/packs required. "
                        "**Portion garnish:** recipe portions × servings ÷ Ingredients.Yield = "
                        "individual fruits/packs. **Glassware:** recipe glass count × servings "
                        "= individual glasses; order complete racks/rolls using case size.")
            rec_rows=describe_recipe_master(ingredients)
            if rec_rows:
                rf=pd.DataFrame(rec_rows)
                st.dataframe(rf,hide_index=True,use_container_width=True,column_config=compact_columns(rf))
            st.divider()
            st.subheader("Cost, source changes & final totals")
            st.markdown("Source-specific **PO_Supplier_Prices** (if available) take precedence. "
                        "Otherwise cost is based on **Ingredients.unit_price** and "
                        "**Ingredients.price_basis** (`Pack` or `Single`). "
                        "Source changes recalculate the PO pack quantity; price basis is "
                        "converted to the new pack factor. VAT uses "
                        "`PO_Settings.Default_VAT_Percent`, not a rate embedded in the program. "
                        "All item values are estimates until suppliers confirm them.")
            st.caption("Read-only explanation. To edit formulas use **Editable formula settings**; "
                       "to update Bottle Size, Case Size, Yield or cost use **Ingredients & Recipes**; "
                       "to update alcohol guide quantities use the Alcohol Package matrix.")
        with calc_settings:
            st.subheader("Editable calculation guides")
            st.caption("PO_Rules.quantity_basis states whether each formula gives an Individual count or Purchase pack count. PACK and YIELD come from Ingredients. Never enter hardcoded ingredient pack conversions in the Python code.")
            original_rules=records(SHEET_NAMES["rules"])
            all_rules=migrate_rules(original_rules)
            if not original_rules:
                st.info("Using in-app guide formulas. Save a category below to create the PO_Rules Google worksheet; no manual worksheet setup needed.")
            if original_rules != all_rules:
                st.warning('PO_Rules contains outdated UNS references and/or Hildon table-water bottle formulas. The app corrects these in memory. Save migrated rules to update the Google Sheet.')
                if st.button('Save corrected case-based PO_Rules',type='primary'):
                    if not store.writable:st.error('Connect Google Sheets to save')
                    else:
                        store.save_table(SHEET_NAMES['rules'],all_rules,RULE_COLUMNS)
                        after_save('PO_Rules case-size corrections saved')
            def group_for_rule(row):
                group=str(row.get("group", "")).lower()
                if "water" in group:return "Water"
                if "soft" in group:return "Soft Drinks"
                if "juice" in group:return "Juices"
                if "mixer" in group:return "Mixers"
                return "Other"
            guide_cols=st.columns(2,gap='small')
            for group_index,group in enumerate(("Water","Soft Drinks","Juices","Mixers")):
                with guide_cols[group_index%2]:
                    items=[r for r in all_rules if group_for_rule(r)==group]
                    with st.expander(f"{group} — {len(items)} rules",expanded=(group=="Water")):
                        display=[]
                        for rule in items:
                            entry=dict(rule)
                            master_rec=ingredients.get(identifier(entry.get("ingredient_id", "")),{})
                            entry["Ingredient name"]=master_rec.get("item", "Selected table juice" if entry.get("ingredient_id")=="TABLE_JUICE" else "Unmatched ID")
                            entry["Bottle Size"]=master_rec.get("Bottle Size", "")
                            entry["Yield"]=master_rec.get("Yield", "")
                            entry["case size"]=master_rec.get("case size", "")
                            entry["Source"]=master_rec.get("Source", "")
                            display.append(entry)
                        extra_fields=["Ingredient name","Bottle Size","Yield","case size","Source"]
                        frame=pd.DataFrame(display,columns=RULE_COLUMNS+extra_fields).fillna("")
                        changed=st.data_editor(frame,num_rows="dynamic",hide_index=True,
                            use_container_width=True,key="rule_category_editor_"+group,
                            disabled=extra_fields,
                            column_config=compact_columns(frame,{"meal":st.column_config.SelectboxColumn("Meal",options=list(MEALS),width=85),
                                "package":st.column_config.SelectboxColumn("Package",options=["Any","Regular","Glass","Canned"],width=90),
                                "formula":st.column_config.TextColumn("Formula",width=170),
                                "Ingredient name":st.column_config.TextColumn("Ingredient",width=180)}))
                        if st.button("Save "+group+" rules to Google Sheets",key="save_rules_"+group,type="primary"):
                            if not store.writable:st.error("Connect Google Sheets to save changes")
                            else:
                                modified=[{k:r.get(k,"") for k in RULE_COLUMNS} for r in changed.fillna("").to_dict("records")
                                          if str(r.get("formula","")).strip() and str(r.get("ingredient_id","")).strip()]
                                for n,r in enumerate(modified):
                                    if not str(r.get("rule_id","")).strip():r["rule_id"]=f"{group[:2].upper()}-{r.get('meal','')}-{n+1}"
                                remaining=[r for r in all_rules if group_for_rule(r)!=group]
                                store.save_table(SHEET_NAMES["rules"],remaining+modified,RULE_COLUMNS)
                                after_save(group+" formula guide updated")
            others=[r for r in all_rules if group_for_rule(r)=="Other"]
            if others:
                with st.expander("Other formulas"):
                    frame_other=pd.DataFrame(others)
                    st.dataframe(frame_other,hide_index=True,use_container_width=True,
                                 column_config=compact_columns(frame_other))
            st.divider()
            st.subheader("Alcohol Package — guest band matrix")
            alcohol_records=records(SHEET_NAMES["alcohol"])
            alcohol_cols=[str(c) for c in grid(SHEET_NAMES['alcohol'])[0]] if grid(SHEET_NAMES['alcohol']) else ALCOHOL_REQUIRED_COLUMNS
            if not alcohol_records:st.error('PO_Alcohol_Matrix missing. Import the updated workbook.')
            edited_alcohol=st.data_editor(pd.DataFrame(alcohol_records,columns=alcohol_cols),
                num_rows="dynamic",hide_index=True,use_container_width=True,key="alcohol_matrix_admin_v2",
                column_config=compact_columns(pd.DataFrame(alcohol_records,columns=alcohol_cols)))
            if st.button("Save alcohol matrix to Google Sheets",type="primary"):
                if not store.writable:st.error("Connect Google Sheets to save")
                else:
                    store.save_table(SHEET_NAMES["alcohol"],edited_alcohol.fillna("").to_dict("records"),alcohol_cols)
                    after_save("Alcohol guide updated")
            st.divider()
            st.subheader("Garnish Yield")
            garnish_data=[{"ID":iid,"Ingredient":v.get("item"),"Source":v.get("Source"),
                           "Bottle Size":number(v.get("Bottle Size")),"case size":number(v.get("case size")),
                           "Yield":number(v.get("Yield"))}
                          for iid,v in ingredients.items() if str(v.get("category","")).lower() in ("garnish","glasses")]
            edited_yield=st.data_editor(pd.DataFrame(garnish_data),hide_index=True,use_container_width=True,
                key="garnish_yield_admin_v2",disabled=["ID","Ingredient","Source"],
                column_config=compact_columns(pd.DataFrame(garnish_data),{
                               "ID":None,"Yield":st.column_config.NumberColumn(min_value=.0001,step=1.,width=72),
                               "Bottle Size":st.column_config.NumberColumn(min_value=.0001,step=1.,width=72),
                               "case size":st.column_config.NumberColumn(min_value=1,step=1.,width=72)}))
            if st.button("Save garnish yields to Google Sheets",type="primary"):
                if not store.writable:st.error("Connect Google Sheets to save")
                else:
                    grid_ingredients=grid(SHEET_NAMES["ingredients"])
                    header=list(grid_ingredients[0]);ids={identifier(row[0]):i for i,row in enumerate(grid_ingredients[1:],start=2) if row}
                    updates=[]
                    for row in edited_yield.to_dict("records"):
                        idx=ids.get(identifier(row["ID"]))
                        if not idx:continue
                        for key in ("Yield","Bottle Size","case size"):
                            col=header.index(key)+1
                            updates.append((idx,col,number(row[key])))
                    store.update_cells(SHEET_NAMES["ingredients"],updates)
                    after_save("Garnish measures updated")

        with account:
            st.caption("Logins are read from Users. Existing plaintext passwords can be migrated to PBKDF2 hashes.")
            all_users=records(SHEET_NAMES["users"])
            user_frame=pd.DataFrame([{"username":u.get("username"),"role":u.get("role"),
                                        "password_format":"Hashed" if str(u.get("password", "")).startswith("pbkdf2_sha256$") else "Legacy plaintext"} for u in all_users])
            st.dataframe(user_frame,hide_index=True,use_container_width=True,
                         column_config=compact_columns(user_frame))
            st.warning("The supplied workbook contains plaintext passwords. Rotate them and migrate them to hashes. Never publish the workbook or Google service-account key.")
            legacy_users=[r for r in all_users if str(r.get('password','')).strip()
                          and not str(r.get('password','')).startswith('pbkdf2_sha256$')]
            if legacy_users:
                st.warning(f'{len(legacy_users)} account(s) still have legacy plaintext passwords.')
                acknowledge=st.checkbox('I understand old passwords should also be rotated after hashing',
                                        key='ack_legacy_hash_v34')
                if st.button('Hash all legacy passwords (preserve logins)',
                             disabled=not acknowledge,key='migrate_passwords_v34'):
                    if not store.writable:st.error('Connect live Google Sheets first')
                    else:
                        current=records(SHEET_NAMES['users'])
                        for r in current:
                            plain=str(r.get('password',''))
                            if plain and not plain.startswith('pbkdf2_sha256$'):
                                r['password']=password_hash(plain)
                        headers=list(grid(SHEET_NAMES['users'])[0])
                        store.save_table(SHEET_NAMES['users'],current,headers)
                        after_save('All legacy logins migrated to hashed passwords; existing passwords still work')
            else:st.success('All accounts have hashed passwords.')
            with st.form("password_reset_form"):
                target=st.selectbox("Username to update",[str(x.get("username", "")) for x in all_users])
                new_password=st.text_input("New password",type="password")
                new_role=st.selectbox("Role",["Admin","Standard user","Bartenders"])
                confirmed=st.form_submit_button("Reset password and role")
            if confirmed:
                if not store.writable:st.error("Connect Google Sheets to save")
                elif len(new_password)<10:st.error("Use at least 10 characters")
                else:
                    user_rows=records(SHEET_NAMES["users"])
                    for u in user_rows:
                        if str(u.get("username"))==target:
                            u["password"]=password_hash(new_password);u["role"]=new_role
                    store.save_table(SHEET_NAMES["users"],user_rows,list(grid(SHEET_NAMES["users"])[0]))
                    after_save("Password and role updated")
            with st.form('create_user_v35'):
                st.markdown('**Add new user**')
                u1,u2,u3=st.columns([1.1,1.2,1.0],gap='small')
                with u1:username_new=st.text_input('New username')
                with u2:new_user_password=st.text_input('Temporary password',type='password')
                with u3:new_user_role=st.selectbox('New user role',['Bartenders','Standard user','Admin'])
                add_account=st.form_submit_button('Create user')
            if add_account:
                if not store.writable:st.error('Connect live Google Sheets to create users')
                elif not username_new.strip() or len(new_user_password)<10:
                    st.error('Provide a username and a temporary password of at least 10 characters.')
                elif any(str(x.get('username','')).strip().casefold()==username_new.strip().casefold() for x in all_users):
                    st.error('This username already exists.')
                else:
                    fields=list(grid(SHEET_NAMES['users'])[0])
                    record={k:'' for k in fields}
                    record.update({'username':username_new.strip(),
                        'password':password_hash(new_user_password),'role':new_user_role})
                    store.save_table(SHEET_NAMES['users'],all_users+[record],fields)
                    after_save('New user created; ask the user to change their temporary password')
            st.subheader("Workbook checks")
            issues=recipe_issues[:35]
            missing=verify_recipe_ids(recipes,ingredients)
            st.write(f"Ingredients: {len(ingredients)} | Drinks: {len(recipes)} | Missing recipe IDs: {len(missing)}")
            if issues:
                for issue in issues:st.warning(issue)
            else:st.success("All ingredient IDs used by recipe cells match the Ingredients master.")
            st.caption("Data sheets: "+", ".join(SHEET_NAMES.values()))
