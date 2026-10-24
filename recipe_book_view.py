"""Read-only, category-grouped three-column Recipe Book rendering.

The view accepts parsed Recipe-matrix records; it never writes or edits recipe data.
All user-controlled text/URLs are escaped and the 2 cm square thumbnail is retained.
"""
from __future__ import annotations
from html import escape
from collections import OrderedDict
from urllib.parse import urlsplit
import re
from recipe_thumbnail import RECIPE_IMAGE_PX
from po_v35_features import split_recipe_ingredients
from po_logic import number


def format_quantity(value):
    val = number(value)
    return f'{val:g}'


def ingredient_lines(items):
    """Return one HTML line per ingredient (never join ingredients in one sentence)."""
    if not items:
        return '<span class="rag-empty">—</span>'
    return ''.join(
        '<div class="rag-ingredient-line"><span class="rag-ing-name">'
        + escape(str(it.get('name', ''))) + '</span>'
        + '<span class="rag-ing-quantity">' + escape(format_quantity(it.get('qty')))
        + (' ' + escape(str(it.get('unit', '')).strip()) if it.get('unit') else '')
        + '</span></div>'
        for it in items
    )


def valid_https_image(url):
    v = str(url or '').strip()
    p = urlsplit(v)
    return v if p.scheme == 'https' and p.netloc and not p.username and not p.password else ''


def image_html(url, name):
    safe = valid_https_image(url)
    if not safe and isinstance(url,str) and len(url)<250000 and re.fullmatch(
            r'data:image/png;base64,[A-Za-z0-9+/=]+',url):
        safe=url  # server-generated 76x76 PNG; never accept SVG/HTML data URLs
    if not safe:
        return '<div class="rag-recipe-placeholder" aria-label="No image available" style="width:76px;height:76px">🍹</div>'
    return (f'<img src="{escape(safe, quote=True)}" alt="{escape(name, quote=True)}" '
            f'loading="lazy" width="{RECIPE_IMAGE_PX}" height="{RECIPE_IMAGE_PX}" '
            'class="rag-recipe-thumbnail" />')


def category_groups(recipes):
    groups: dict[str, list] = {}
    for rec in sorted(recipes, key=lambda r: (str(r.get('category') or 'Uncategorised').casefold(),
                                              str(r.get('name', '')).casefold())):
        category = str(rec.get('category') or 'Uncategorised').strip() or 'Uncategorised'
        groups.setdefault(category, []).append(rec)
    return groups


def render_recipe_table(recipes, image_urls=None, notes=None):
    """Render all supplied recipes in a single category-grouped HTML table.

    image_urls: mapping recipe name -> already validated remote URL or in-memory data URI.
    notes: mapping recipe name -> stored notes. Images are 76x76 CSS pixels (2 cm nominal).
    """
    image_urls = image_urls or {}
    notes = notes or {}
    parts = [
        '<div class="rag-recipe-scroll"><table class="rag-recipe-table">',
        '<colgroup><col style="width:22%"><col style="width:44%"><col style="width:34%"></colgroup>',
        '<thead><tr><th>Drink &amp; photo</th><th>Ingredients &amp; quantities</th><th>Garnish &amp; glassware</th></tr></thead><tbody>'
    ]
    for category, recs in category_groups(recipes).items():
        css = category.casefold()
        badge = 'mocktail' if 'mocktail' in css else 'cocktail'
        parts.append(f'<tr class="rag-group-head"><td colspan="3"><span class="rag-cat-pill {badge}">'
                     f'{escape(category)}</span><span class="rag-cat-count">{len(recs)} recipes</span></td></tr>')
        for rec in recs:
            name = str(rec.get('name') or '')
            standard, garnish = split_recipe_ingredients(rec)
            rec_note = notes.get(name, {})
            note_text = str(rec_note.get('garnish_notes') or '').strip()
            description = (f'<div class="rag-recipe-note">{escape(note_text)}</div>' if note_text else '')
            parts.append('<tr class="rag-recipe-row"><td class="rag-recipe-drink">'
                         f'<strong>{escape(name)}</strong><div class="rag-img-block">'
                         f'{image_html(image_urls.get(name),name)}</div></td>'
                         f'<td class="rag-recipe-ingredients">{ingredient_lines(standard)}</td>'
                         f'<td class="rag-recipe-garnish">{ingredient_lines(garnish)}{description}</td></tr>')
    if not recipes:
        parts.append('<tr><td colspan="3" class="rag-empty">No recipes match the selected filters.</td></tr>')
    parts.append('</tbody></table></div>')
    return ''.join(parts)
