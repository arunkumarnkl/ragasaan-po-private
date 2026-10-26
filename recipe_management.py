"""Administrator-only Recipe Book management; never imported into bartender views.

Operations preserve the existing wide GitHub Recipe matrix:
row 1 holds ingredient IDs, row 2 their names, category/name are A/B.
"""
from __future__ import annotations
from collections import defaultdict
from io import BytesIO
from urllib.parse import urlsplit
import pandas as pd
from po_logic import number, identifier
from po_v35_features import split_recipe_ingredients
from recipe_thumbnail import RECIPE_IMAGE_PX, crop_thumbnail, safe_thumbnail_html
from persistent_images import PersistentImages
from recipe_images import (IMAGE_COLUMNS, image_record,
                           upsert_image_record, verify_upload)

NOTE_COLUMNS = ['recipe_name','remarks','garnish_notes']


def save_recipe_changes(store, rec, values, *, name, category, new_ingredient_id='', new_ingredient_qty=0,
                        matrix=None, notes=None, remarks='', garnish_notes='', image_rows=None):
    """Persist a recipe's editable cells, name/category and notes.

    Recipe table row indices are 1-based and come from parse_recipe_matrix.
    """
    if not store.writable:
        raise PermissionError('Live GitHub connection is required')
    name = str(name).strip()
    category = str(category).strip()
    if not name or not category:
        raise ValueError('Recipe name and category cannot be blank')
    if not matrix or len(matrix) < 2:
        raise ValueError('Recipe ingredient-ID header rows are missing')
    edits = [(int(rec['row']),1,category),(int(rec['row']),2,name)]
    for item in values:
        qty = number(item.get('Quantity'))
        if qty < 0:
            raise ValueError('Recipe quantities cannot be negative')
        edits.append((int(item['row']),int(item['col']),qty if qty else ''))
    if new_ingredient_id and number(new_ingredient_qty) > 0:
        iid = identifier(new_ingredient_id)
        col = next((index+1 for index, raw in enumerate(matrix[0]) if identifier(raw)==iid),None)
        if col is None:
            raise ValueError(f'Ingredient ID {iid} is not a Recipe sheet header. Add it there before using it in a recipe.')
        if col in {int(it['col']) for it in values}:
            raise ValueError('Ingredient is already in recipe. Edit its existing quantity instead.')
        edits.append((int(rec['row']),col,number(new_ingredient_qty)))
    store.update_cells('Recipe',edits)
    previous_name=str(rec['name'])
    updated_notes=[dict(row) for row in (notes or [])
                   if str(row.get('recipe_name','')).casefold()!=previous_name.casefold()
                   and str(row.get('recipe_name','')).casefold()!=name.casefold()]
    updated_notes.append({'recipe_name':name,'remarks':str(remarks),'garnish_notes':str(garnish_notes)})
    store.save_table('PO_Recipe_Notes',updated_notes,NOTE_COLUMNS)
    if previous_name.casefold()!=name.casefold():
        images = [dict(row) for row in (image_rows or [])]
        changed = False
        for row in images:
            if str(row.get('recipe_name','')).casefold() == previous_name.casefold():
                row['recipe_name']=name;changed=True
        if changed:
            store.save_table('PO_Recipe_Images',images,IMAGE_COLUMNS)


def delete_recipe(store, rec, notes, image_rows):
    """Delete the recipe matrix row by its absolute sheet row number.

    Deleting an entire GitHub database row preserves other recipe rows and header cells.
    Metadata rows keyed by that name are also removed.
    """
    if not store.writable:raise PermissionError('Live GitHub connection is required')
    if int(rec['row'])<3:raise ValueError('Cannot delete Recipe headers')
    store.delete_row('Recipe',int(rec['row']))
    name=str(rec['name']).casefold()
    new_notes=[r for r in notes if str(r.get('recipe_name','')).casefold()!=name]
    new_images=[r for r in image_rows if str(r.get('recipe_name','')).casefold()!=name]
    if len(new_notes)<len(notes):store.save_table('PO_Recipe_Notes',new_notes,NOTE_COLUMNS)
    if len(new_images)<len(image_rows):store.save_table('PO_Recipe_Images',new_images,IMAGE_COLUMNS)


def _make_editor_frame(rec):
    rows=[]
    for it in rec['ingredients']:
        rows.append({'Ingredient':str(it['name']), 'Quantity':float(it['qty']),
                     'Unit':str(it['unit']), 'ID':identifier(it['ingredient_id']),
                     'row':int(it['row']), 'col':int(it['col'])})
    return pd.DataFrame(rows,columns=['Ingredient','Quantity','Unit','ID','row','col'])


def render_recipe_management(*, recipes, ingredients, matrix, store, grid, records,
                             settings, recipe_suggestion, after_save, image_bucket=""):
    import streamlit as st
    st.markdown('#### Recipe Management')
    st.caption('Administrator-only edits to the existing GitHub Recipe matrix. '
               'The public Recipe Book is entirely read-only, including for Bartenders.')
    by_name={r['name']:r for r in recipes}
    categories=sorted({str(r.get('category') or 'Uncategorised') for r in recipes},key=str.casefold)
    image_rows=records('PO_Recipe_Images')
    note_rows=records('PO_Recipe_Notes')
    tab_edit, tab_add, tab_remove, tab_images=st.tabs(['✏️ Edit recipe','＋ Add recipe','🗑️ Delete','🖼️ Images & Storage'])
    with tab_edit:
        if not recipes:st.info('There are no recipes to edit.')
        else:
            sel_col, cat_col=st.columns([2,1],gap='small')
            with cat_col:
                category_filter=st.selectbox('Category', ['All categories']+categories,key='admin_recipe_category')
            filtered=[rec for rec in recipes if category_filter=='All categories' or rec['category']==category_filter]
            with sel_col:
                selected=st.selectbox('Recipe to edit',[r['name'] for r in filtered],key='admin_recipe_name')
            rec=by_name[selected]
            current_notes=next((r for r in note_rows if str(r.get('recipe_name'))==selected),{})
            columns=st.columns([2,1],gap='small')
            with columns[0]:
                name_input=st.text_input('Recipe name',value=rec['name'],key=f'admin_rec_name_{rec["row"]}')
            with columns[1]:
                category_input=st.selectbox('Recipe category',categories+['New category'],
                    index=categories.index(rec['category']) if rec['category'] in categories else 0,
                    key=f'admin_rec_group_{rec["row"]}')
            if category_input=='New category':
                category_input=st.text_input('New category name',key=f'admin_new_cat_{rec["row"]}')
            frame=_make_editor_frame(rec)
            st.caption('One ingredient per line. Edit quantities in the table; zero removes an ingredient.')
            edited=st.data_editor(frame,hide_index=True,use_container_width=True,
                disabled=['Ingredient','Unit','ID','row','col'],key=f'admin_rec_editor_{rec["row"]}',
                column_config={'Ingredient':st.column_config.TextColumn(width='large'),
                               'Unit':st.column_config.TextColumn(width='small'),
                               'Quantity':st.column_config.NumberColumn(min_value=0,step=.5,width='small'),
                               'ID':None,'row':None,'col':None})
            available=[iid for iid in ingredients if iid not in {it['ingredient_id'] for it in rec['ingredients']}
                       and any(identifier(v)==iid for v in matrix[0][2:])]
            add_a,add_b=st.columns([3,1],gap='small')
            with add_a:
                new_id=st.selectbox('Add another ingredient',['']+available,
                    format_func=lambda i:ingredients[i]['item'] if i else 'None',
                    key=f'admin_rec_new_ing_{rec["row"]}')
            with add_b:
                new_qty=st.number_input('New quantity',min_value=0.0,step=.5,
                    key=f'admin_rec_new_qty_{rec["row"]}')
            remarks=st.text_input('Remarks',value=str(current_notes.get('remarks','')),
                                  key=f'admin_rec_rem_{rec["row"]}')
            garnish_notes=st.text_input('Garnish notes',value=str(current_notes.get('garnish_notes','')),
                                        key=f'admin_rec_gar_{rec["row"]}')
            if st.button('Save recipe changes',type='primary',key='admin_save_rec_v36'):
                if name_input.strip().casefold()!=selected.casefold() and any(
                    name_input.strip().casefold()==r['name'].casefold() for r in recipes):
                    st.error('A recipe with that name already exists.')
                else:
                    try:
                        save_recipe_changes(store,rec,edited.to_dict('records'),
                            name=name_input,category=category_input,new_ingredient_id=new_id,
                            new_ingredient_qty=new_qty,matrix=matrix,notes=note_rows,
                            remarks=remarks,garnish_notes=garnish_notes,image_rows=image_rows)
                        after_save('Recipe updated in GitHub')
                    except Exception as exc:st.error(f'Could not save recipe: {exc}')
    with tab_add:
        with st.form('admin_add_recipe_v36'):
            name=st.text_input('New recipe name')
            cat=st.selectbox('Category',categories+['New category'],key='admin_create_category')
            if cat=='New category':cat=st.text_input('New category',key='admin_create_category_new')
            choices=[identifier(v) for v in matrix[0][2:] if identifier(v) in ingredients]
            ids=st.multiselect('Ingredients',choices,format_func=lambda i:ingredients[i]['item'])
            qtys={iid:st.number_input(f'{ingredients[iid]["item"]} · qty',min_value=0.0,step=.5,
                                       key=f'admin_create_qty_{iid}') for iid in ids}
            add_clicked=st.form_submit_button('Add recipe to GitHub',type='primary')
        if add_clicked:
            if not store.writable:st.error('Connect GitHub before adding a recipe')
            elif not name.strip() or not str(cat).strip():st.error('Provide a name and category')
            elif any(name.strip().casefold()==r['name'].casefold() for r in recipes):st.error('A recipe with that name exists')
            elif not any(x>0 for x in qtys.values()):st.error('Add one or more ingredient quantities')
            else:
                new_row=[cat.strip(),name.strip()]+[qtys.get(identifier(v),'') for v in matrix[0][2:]]
                store.append_rows('Recipe',[new_row]);after_save('New recipe added')
    with tab_remove:
        st.warning('Deleting a recipe removes its row from GitHub, plus its notes and image references. '
                   'It does not delete photos from private GitHub.')
        selected=st.selectbox('Recipe to delete',['']+[r['name'] for r in recipes],key='admin_del_recipe')
        acknowledged=st.checkbox('I have backed up the Recipe sheet and want to delete this recipe',
                                key='admin_confirm_del_recipe')
        if st.button('Delete selected recipe',disabled=not(bool(selected) and acknowledged),key='admin_delete_recipe_v36'):
            try:
                delete_recipe(store,by_name[selected],note_rows,image_rows)
                after_save('Recipe deleted')
            except Exception as exc:st.error(f'Could not delete recipe: {exc}')
    with tab_images:
        if not recipes:st.info('Add a recipe first.')
        else:
            sel=st.selectbox('Recipe picture to manage',[r['name'] for r in recipes],key='admin_image_recipe_v36')
            rec=by_name[sel]
            stored=image_record(image_rows,sel)
            col_preview,col_manage=st.columns([1,2],gap='large')
            with col_preview:
                st.markdown('**Current image**')
                if stored.get('image_url'):
                    try:st.markdown(safe_thumbnail_html(str(stored['image_url']),sel),unsafe_allow_html=True)
                    except ValueError:st.warning('Saved image URL is invalid')
                elif stored.get('drive_file_id'):
                    try:
                        raw=PersistentImages(store.credentials,bucket=image_bucket).read(stored['drive_file_id'])
                        st.image(crop_thumbnail(raw),width=RECIPE_IMAGE_PX)
                    except Exception:st.warning('GitHub photo currently unavailable')
                else:st.caption('No saved override. The Recipe Book can suggest an online photo.')
                if stored.get('attribution'):st.caption(str(stored['attribution']))
            with col_manage:
                suggestion=None
                if st.button('Find Wikimedia Commons suggestion',key='admin_suggest_image'):
                    st.session_state[f'admin_img_sugg_{sel}']=recipe_suggestion(rec['name'],rec['category'])
                suggestion=st.session_state.get(f'admin_img_sugg_{sel}')
                if suggestion:
                    st.markdown(safe_thumbnail_html(suggestion['url'],sel),unsafe_allow_html=True)
                    st.caption(suggestion.get('attribution','Wikimedia Commons'))
                    st.link_button('Source / licence',suggestion['page'])
                    if st.button('Use suggestion for this recipe',key='admin_save_suggestion'):
                        if not store.writable:st.error('Connect GitHub to save')
                        else:
                            store.save_table('PO_Recipe_Images',upsert_image_record(image_rows,sel,
                               image_url=suggestion['url'],source=suggestion['page'],
                               attribution=suggestion.get('attribution','')),IMAGE_COLUMNS)
                            after_save('Suggested image saved')
                new_url=st.text_input('Or use HTTPS image URL',key=f'admin_img_url_{sel}')
                if st.button('Save image URL',key='admin_save_img_url'):
                    parsed=urlsplit(new_url.strip())
                    if parsed.scheme!='https' or not parsed.netloc:st.error('Only HTTPS image URLs are accepted')
                    elif not store.writable:st.error('Connect GitHub to save')
                    else:
                        store.save_table('PO_Recipe_Images',upsert_image_record(image_rows,sel,
                            image_url=new_url.strip(),source='Admin image URL',
                            attribution='User-supplied photo'),IMAGE_COLUMNS)
                        after_save('Image URL saved')
                photo=st.file_uploader('Upload new recipe image (private persistent storage)',type=['png','jpg','jpeg','webp'],
                                       key=f'admin_image_file_{sel}')
                if st.button('Upload and use photo',disabled=photo is None,key='admin_image_upload'):
                    try:
                        if not store.writable:raise PermissionError('Connect GitHub to save')
                        mime,filename=verify_upload(photo.getvalue(),photo.name)
                        folder=''  # Images go directly into private GitHub assets/recipes/

                        fid=PersistentImages(store.credentials,bucket=image_bucket).upload(folder,filename,photo.getvalue(),mime)
                        store.save_table('PO_Recipe_Images',upsert_image_record(image_rows,sel,
                            drive_file_id=fid,source=('Private Cloud Storage' if image_bucket else 'Private private GitHub'),
                            attribution='User-provided photo'),IMAGE_COLUMNS)
                        after_save('New image uploaded and linked')
                    except Exception as exc:st.error(f'Unable to upload: {exc}')
                if stored and st.button('Reset to suggested image',key='admin_reset_image'):
                    if not store.writable:st.error('Connect GitHub to save')
                    else:
                        remaining=[r for r in image_rows if str(r.get('recipe_name','')).casefold()!=sel.casefold()]
                        store.save_table('PO_Recipe_Images',remaining,IMAGE_COLUMNS)
                        after_save('Image override removed')
