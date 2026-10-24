"""V3.6 navy-and-pastel design system for the existing Streamlit application.

Presentation-only: no business calculations, Google credentials, or permissions.
"""
from __future__ import annotations
from html import escape

CSS = r"""
<style>
:root{--rag-navy:#202f57;--rag-navy2:#314271;--rag-indigo:#6358cb;--rag-periwinkle:#e9e8ff;--rag-ink:#273654;--rag-muted:#60708c;--rag-surface:#ffffff;--rag-bg:#f4f6fc;--rag-border:#dfe6f2}
.stApp{background:var(--rag-bg)!important;color:var(--rag-ink)!important;font-family:Inter, 'Segoe UI', sans-serif}
.block-container{max-width:1860px;padding:0.5rem 1.2rem 2.5rem!important}
section[data-testid="stSidebar"]{background:#edf0fa!important;border-right:1px solid #d8def0}
section[data-testid="stSidebar"]>div{padding-top:.85rem}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#5c6885}
section[data-testid="stSidebar"] button{border-color:#d5ddec;background:#fff;border-radius:.65rem}
.stApp h1,.stApp h2,.stApp h3{color:#263861!important;line-height:1.2;font-weight:750!important;letter-spacing:-.018em}
.stApp h2{font-size:1.28rem!important}.stApp h3{font-size:1.05rem!important}
.stApp p,.stApp label{font-size:.81rem}
.stApp [data-testid="stVerticalBlock"]{gap:.45rem}
.stApp [data-testid="stHorizontalBlock"]{gap:.56rem}
.stApp [data-testid="stWidgetLabel"]{margin-bottom:.05rem}
.stApp [data-testid="stWidgetLabel"] p{color:#4b5b77;font-size:.77rem;font-weight:550}
.stApp [data-baseweb="input"],.stApp [data-baseweb="select"]>div,.stApp textarea{border-color:#d7dfef!important;border-radius:.54rem!important;background:#fff!important}
.stApp [data-baseweb="input"] input{padding:.23rem .42rem!important}
.stApp [data-testid="stNumberInput"] input{font-variant-numeric:tabular-nums;min-width:0!important}
.stApp [data-testid="stNumberInput"] button{min-width:1.2rem!important}
.stApp [data-testid="stSelectbox"] div[data-baseweb="select"]{min-height:2rem!important}
.stApp [data-testid="stButton"] button,.stApp [data-testid="stDownloadButton"] button{border-radius:.58rem!important;min-height:2.05rem;padding:.18rem .68rem!important;font-size:.8rem;transition:background .1s ease}
.stApp [data-testid="stButton"] button[kind="primary"],.stApp [data-testid="stDownloadButton"] button[kind="primary"]{background:#5b57c8!important;border:1px solid #5b57c8!important;color:white!important}
.stApp [data-testid="stButton"] button:not([kind="primary"]),.stApp [data-testid="stDownloadButton"] button:not([kind="primary"]){background:#fff!important;color:#34467b;border:1px solid #d2dbed!important}
.stApp [data-testid="stButton"] button:hover{border-color:#8e88df!important}
.stApp [data-testid="stMetric"]{background:#fff!important;border:1px solid #dfe6f2!important;border-radius:.75rem;padding:.7rem .9rem!important;box-shadow:0 2px 8px rgba(43,60,108,.04)}
.stApp [data-testid="stMetricValue"]{color:#343d74;font-size:1.55rem}
.stApp [data-testid="stExpander"]{background:#fff!important;border:1px solid #dfe5f0;border-radius:.75rem;box-shadow:0 1px 5px rgba(42,56,99,.025)}
.stApp [data-testid="stAlert"]{border-radius:.6rem}
.stApp [data-testid="stForm"]{background:#fff;border:1px solid #e2e8f4;border-radius:.8rem}
.stApp [data-testid="stDataFrame"]{border:1px solid #e0e6f1;border-radius:.65rem;overflow:hidden;box-shadow:0 1px 3px rgba(55,68,99,.03)}
.stApp [data-testid="stDataFrame"] [role="columnheader"]{background:#eef1fc!important;color:#2d4167!important;font-weight:650}
.stApp [data-testid="stDataFrame"] div[role="columnheader"]{white-space:normal!important}
.stApp [data-testid="stDataEditor"]{border-radius:.65rem;overflow:hidden}
.stTabs [data-baseweb="tab-list"]{background:linear-gradient(105deg,#24335e,#364679)!important;border:1px solid #334578!important;border-radius:.8rem!important;min-height:3.5rem!important;gap:.28rem;overflow-x:auto;box-shadow:0 2px 6px rgba(25,41,87,.12);padding:.37rem!important}
.stTabs [data-baseweb="tab"]{min-height:2.7rem!important;background:rgba(255,255,255,.055)!important;border-radius:.6rem!important;padding:.47rem 1.08rem!important;white-space:normal;color:#eff0ff!important;font-size:.87rem!important;font-weight:620!important;border:none!important}
.stTabs [data-baseweb="tab"]:hover{background:rgba(255,255,255,.12)!important}
.stTabs [aria-selected="true"]{background:#eeebff!important;color:#35328f!important;box-shadow:0 1px 5px rgba(0,0,0,.08)}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none!important}
/* Fixed-size, read-only Recipe Book table */
.rag-recipe-scroll{width:100%;max-height:74vh;overflow:auto;border:1px solid #dce4f2;border-radius:12px;background:#fff;box-shadow:0 3px 12px rgba(36,54,101,.04)}
.rag-recipe-table{border-collapse:separate;border-spacing:0;width:100%;font-size:12.5px;table-layout:fixed}
.rag-recipe-table th{text-align:left;position:sticky;top:0;z-index:3;background:#e9edfb;color:#27385d;padding:12px 13px;font-weight:750;border-bottom:1px solid #d5e0f0}
.rag-recipe-table td{vertical-align:top;padding:12px 13px;border-bottom:1px solid #e8edf5;overflow-wrap:anywhere}
.rag-recipe-row:nth-of-type(even){background:#fbfcff}
.rag-recipe-row:hover{background:#f4f7ff}
.rag-recipe-drink strong{display:block;font-size:13.5px;color:#293c69;margin-bottom:7px}
.rag-recipe-thumbnail,.rag-recipe-placeholder{width:76px!important;height:76px!important;max-width:76px!important;min-width:76px!important;border-radius:7px;object-fit:cover;display:block;border:1px solid #dbe4ef;background:#f3f5fb}
.rag-recipe-placeholder{display:grid;place-items:center;font-size:32px}
.rag-ingredient-line{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding:3px 0;border-bottom:1px dotted #edf0f6}
.rag-ingredient-line:last-child{border-bottom:none}
.rag-ing-name{color:#32445c;flex:1;min-width:0}
.rag-ing-quantity{font-weight:700;text-align:right;white-space:nowrap;color:#394f87;min-width:55px}
.rag-group-head td{background:#e9f0fc!important;border-bottom:1px solid #dbe6f6!important;padding:10px 13px!important}
.rag-cat-pill{display:inline-block;border-radius:5px;color:#385a90;background:#dce8fb;font-size:11px;font-weight:750;padding:4px 9px;letter-spacing:.03em}
.rag-cat-pill.mocktail{background:#def3e9;color:#297255}
.rag-cat-count{font-size:11px;color:#647390;margin-left:12px}
.rag-empty{color:#8792aa}
.rag-recipe-note{margin-top:8px;color:#6b7487;font-style:italic;font-size:11px}
/* Highly visible headings are independent of native Streamlit heading colours.
   Installing the app does not change browser CSS; these must be in the UI. */
.rag-page-heading{background:#fff!important;border-left:5px solid #665fce!important;
  border-radius:8px!important;padding:9px 14px!important;margin:5px 0 12px!important;
  box-shadow:0 1px 5px rgba(36,54,101,.06)!important;display:block!important;
  visibility:visible!important;opacity:1!important}
.rag-page-title{display:block!important;color:#24365f!important;font-size:21px!important;
  line-height:1.35!important;font-weight:800!important;visibility:visible!important;opacity:1!important}
.rag-page-subtitle{display:block!important;color:#5a6a88!important;font-size:12px!important;
  line-height:1.35!important;margin-top:2px!important;visibility:visible!important}
/* Brand ribbon mimics the supplied 2026 dashboard preview. */
.rag-hero{background:linear-gradient(115deg,#202e58 0%,#344375 100%);border-radius:13px;color:#fff;padding:13px 19px;margin:0 0 11px;display:flex;align-items:center;justify-content:space-between;gap:16px;box-shadow:0 4px 12px rgba(27,37,76,.1)}
.rag-brand{display:flex;gap:12px;align-items:center}
.rag-logo{font-size:32px;line-height:1}
.rag-brand-title{font-size:21px;line-height:1.2;font-weight:800;color:#fff}
.rag-brand-caption{font-size:11px;color:#d9e0ff;letter-spacing:.08em;text-transform:uppercase}
.rag-user-chip{color:#eff0fd;border:1px solid rgba(255,255,255,.25);padding:8px 12px;border-radius:22px;font-size:12px;background:rgba(255,255,255,.07)}
.rag-section-line{display:flex;align-items:center;gap:8px;margin:8px 0 12px;color:#31477b;font-weight:800;font-size:15px}
.rag-section-line:before{content:'';width:5px;height:19px;background:#6b64d4;border-radius:4px}
.rag-summary{display:flex;gap:9px;flex-wrap:wrap;margin:0 0 11px}
.rag-stat{background:white;border:1px solid #dfe5f3;padding:8px 14px;border-radius:9px;color:#3e5472;font-size:12px}
.rag-stat strong{color:#35358e;font-size:14px}
.rag-doc-preview{background:#fff;border:8px solid #e5e8f0;border-radius:6px;box-shadow:0 3px 9px #dce1ed;padding:15px;max-height:500px;overflow:auto}
.rag-doc-preview h4{margin:0 0 4px;text-align:center;color:#293a69;font-size:14px}
.rag-doc-preview p{font-size:10px;margin:0 0 7px;text-align:center;color:#65718a}
.rag-doc-preview table{font-size:10px;border-collapse:collapse;width:100%}
.rag-doc-preview th{background:#f0f3fc;text-align:left;color:#394a6b}
.rag-doc-preview th,.rag-doc-preview td{padding:5px 4px;border:1px solid #e0e4ed;overflow-wrap:anywhere}
.rag-doc-preview tr:nth-child(even){background:#fcfdff}
@media(max-width:900px){.rag-hero{padding:11px}.rag-user-chip{display:none}.rag-recipe-table{font-size:11px}.rag-recipe-table th,.rag-recipe-table td{padding:8px}}
</style>
"""


def inject_theme():
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)


def hero(username,role):
    import streamlit as st
    user=escape(str(username or 'Guest'))
    role=escape(str(role or ''))
    st.markdown(
        '<div class="rag-hero"><div class="rag-brand"><div class="rag-logo">🍸</div>'
        '<div><div class="rag-brand-title">Ragasaan</div><div class="rag-brand-caption">Purchase Order · Live Google Sheets</div></div>'
        '</div><div class="rag-user-chip">● &nbsp;'+user+' · '+role+'</div></div>',
        unsafe_allow_html=True,
    )


def category_caption(title, icon='▣'):
    import streamlit as st
    st.markdown(f'<div class="rag-section-line">{escape(icon)} &nbsp;{escape(title)}</div>',
                unsafe_allow_html=True)


def page_heading(title, subtitle=''):
    """High-contrast section heading, visible regardless of Streamlit heading theme."""
    import streamlit as st
    heading=escape(str(title))
    detail=(f'<div class="rag-page-subtitle">{escape(str(subtitle))}</div>'
            if subtitle else '')
    st.markdown(f'<div class="rag-page-heading"><div class="rag-page-title">{heading}</div>'
                f'{detail}</div>', unsafe_allow_html=True)
