"""
SBB Cash Explorer -- Streamlit front end for the cash report parquet.

    streamlit run app.py

Where the data comes from is decided entirely in lib/data.py (local folder or
Google Drive by file ID). This file wires the sidebar, loads the tables once,
and hands a context object to whichever view is selected.
"""

from types import SimpleNamespace

import streamlit as st

from lib import data, style
from views import coverage, entity, flags, fund_signs, portfolio

st.set_page_config(page_title="SBB Cash Explorer", layout="wide",
                   initial_sidebar_state="expanded")
style.inject()
style.sidebar_logo()
st.sidebar.caption("School Budget Bureau")

# ---------------------------------------------------------------- data

lines = data.load("cash_lines")
if lines is None or lines.empty:
    cfg = data.config()
    st.error(
        "No cash data found.\n\n"
        f"Source: **{cfg.source}**" + (f" · `{cfg.data_dir}`" if cfg.source == "local" else "")
        + "\n\nFor local data, point `CASH_DATA_DIR` at the folder publish.py writes "
        "(or the extractor's `cash_data/`). For a quick look without real data, run "
        "`python sample_data/make_sample.py`. For Google Drive, fill in "
        "`gdrive_manifest.json`.")
    st.stop()

manifest = data.load("cash_manifest")
coverage_df = data.load("cash_coverage")
bank = data.load("cash_bank")
expl = data.load("cash_explanations")

# entity label: newest name seen for each PED number
names = (lines.dropna(subset=["EntityKey"])
              .sort_values("FiscalYearKey")
              .drop_duplicates("EntityKey", keep="last")
              .set_index("EntityKey")["entity_name"].to_dict())


def label(ped):
    n = names.get(ped)
    return f"{n} ({ped})" if n else str(ped)


ENDING = lines[lines["line_no"] == 12]
FYS = sorted(int(x) for x in lines["FiscalYearKey"].dropna().unique())

# ---------------------------------------------------------------- sidebar

st.sidebar.title("Cash reports")
view = st.sidebar.radio("View", ["Portfolio", "Entity", "Fund signs", "Flags", "Coverage"],
                        label_visibility="collapsed")
st.sidebar.divider()
fy = st.sidebar.selectbox("Fiscal year", FYS, index=len(FYS) - 1, format_func=style.fy_label)
q = st.sidebar.selectbox("Quarter", [1, 2, 3, 4], index=2)

st.sidebar.divider()
st.sidebar.caption(f"{len(lines):,} rows · {lines['EntityKey'].nunique()} entities · "
                   f"{style.fy_label(min(FYS))}–{style.fy_label(max(FYS))}")
stamp = data.data_stamp()
pub = stamp.get("published_at") or stamp.get("extraction", {}).get("run_at")
if pub:
    st.sidebar.caption(f"Data as of {str(pub)[:16].replace('T', ' ')} UTC")
st.sidebar.caption(data.describe_source())
if st.sidebar.button("Refresh data"):
    data.clear_download_cache()
    st.cache_data.clear()
    st.rerun()

# ---------------------------------------------------------------- routing

sel = ENDING[(ENDING["FiscalYearKey"] == fy) & (ENDING["PeriodOrder"] == q)]
ctx = SimpleNamespace(lines=lines, ENDING=ENDING, sel=sel, manifest=manifest,
                      coverage=coverage_df, bank=bank, expl=expl, names=names,
                      label=label, fy=fy, q=q, FYS=FYS)

style.masthead("SBB Cash Explorer")
{"Portfolio": portfolio, "Entity": entity, "Fund signs": fund_signs,
 "Flags": flags, "Coverage": coverage}[view].render(ctx)
style.footer()
