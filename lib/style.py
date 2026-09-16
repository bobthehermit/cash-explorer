"""
lib/style.py -- the NMPED look, shared with the other SBB Streamlit apps.

Palette (institutional-clarity pass, Jun 2026):
  Primary teal #245d62   Dark teal #1a474b   Gold #edc872   Coral #c64c43
Teal is the structural accent, gold is hairline dividers, coral is reserved
strictly for the alert state. The [theme] block in .streamlit/config.toml
covers the widgets; this module covers what the theme cannot reach.
"""

import base64
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

TEAL, TEAL_DARK, GOLD, CORAL = "#245d62", "#1a474b", "#edc872", "#c64c43"
MUTED = "#8a8a82"

ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT / "assets" / "nmped_logo.jpg"
LOGO_LINK = "https://web.ped.nm.gov/bureaus/school-budget-bureau/"
DISCLAIMER = (
        "This tool was built by Lorenzo Dominguez, pulling from official NMPED "
        "data sources — it isn't an official department publication itself, and "
        "hasn't been exhaustively tested. If something looks off, verify against "
        "source records and let me know: "
        "[lorenzo.dominguez@ped.nm.gov](mailto:lorenzo.dominguez@ped.nm.gov)."
        )

CSS = """
<style>
.block-container { padding-top: 1.1rem !important; max-width: 1240px; }
h1, h2, h3, h4 { color: #245d62; font-weight: 600; }

.ped-eyebrow { font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
               color: #7a8a86; font-weight: 600; }
.ped-title   { font-family: Georgia, "Times New Roman", serif; font-size: 2rem;
               color: #245d62; font-weight: 600; margin: .15rem 0 .6rem; line-height: 1.1; }
.ped-rule    { display: flex; height: 3px; margin-bottom: 1.3rem; }
.ped-rule .g { width: 46px; background: #edc872; }
.ped-rule .t { flex: 1; background: #245d62; }

.section-label { font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
                 color: #245d62; font-weight: 600; padding-bottom: 6px;
                 border-bottom: 1px solid #edc872; margin: 16px 0 10px; }

.pill { font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; }
.pill-ok    { color: #1a474b; background: #e1efe9; }
.pill-alert { color: #993c1d; background: #faece7; }
.pill-warn  { color: #7a5c12; background: #fbf3dd; }
.badge { font-size: 12px; color: #5f5e5a; background: #f1efe8; padding: 3px 9px; border-radius: 6px; }

a { color: #245d62; text-decoration: none; }
a:hover { color: #1a474b; text-decoration: underline; }

.stDownloadButton button { width: 100%; background: #245d62; color: #fff !important; border: none; }
.stDownloadButton button:hover { background: #1a474b; }
.stDownloadButton button p, .stDownloadButton button span { color: #fff !important; }

[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] { background: #245d62 !important; }
[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] span { color: #fff !important; }
[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] svg  { fill: #fff !important; }
[data-testid="stExpander"] { border: 0.5px solid #ececec; border-radius: 8px; }
</style>
"""


def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def masthead(title, eyebrow="New Mexico PED · School Budget Bureau"):
    st.markdown(
        f'<div class="ped-eyebrow">{eyebrow}</div>'
        f'<div class="ped-title">{title}</div>'
        '<div class="ped-rule"><span class="g"></span><span class="t"></span></div>',
        unsafe_allow_html=True)


def section(label):
    st.markdown(f'<div class="section-label">{label}</div>', unsafe_allow_html=True)


def metric_card(label, value, alert=False, note=None):
    """HTML for one summary card. Coral accent only when alert is True."""
    if alert:
        border = "border:0.5px solid #ecc9c1;border-left:3px solid #c64c43;"
        lab, val = "#a8584c", CORAL
    else:
        border = "border:0.5px solid #e3e3dd;"
        lab, val = MUTED, TEAL
    note_html = (f'<div style="font-size:11px;color:{MUTED};margin-top:2px;">{note}</div>'
                 if note else "")
    return (f'<div style="{border}border-radius:8px;padding:13px 15px;">'
            f'<div style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;'
            f'color:{lab};">{label}</div>'
            f'<div style="font-size:1.7rem;font-weight:600;color:{val};">{value}</div>'
            f'{note_html}</div>')


def metrics(cards):
    """cards: list of (label, value, alert, note) laid out in one row."""
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        col.markdown(metric_card(*card), unsafe_allow_html=True)
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)


def sidebar_logo():
    if not LOGO_PATH.exists():
        return
    try:
        from PIL import Image
        buf = BytesIO()
        Image.open(LOGO_PATH).save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        st.sidebar.markdown(
            f'<a href="{LOGO_LINK}" target="_blank"><img src="data:image/png;base64,{b64}" '
            f'style="max-height:90px;height:auto;max-width:100%"></a>',
            unsafe_allow_html=True)
    except Exception:
        pass


def footer():
    st.markdown("---")
    st.info(DISCLAIMER)
    st.caption("New Mexico Public Education Department · School Budget Bureau")


# ---------------------------------------------------------------- formatters

def money(x, decimals=0):
    if x is None or pd.isna(x):
        return "--"
    return f"${x:,.{decimals}f}"


def fy_label(fy):
    """2026 -> 'FY26'."""
    return f"FY{int(fy) % 100:02d}"
