"""Flags -- the review queue, filterable."""

import pandas as pd
import streamlit as st

from lib.style import fy_label


def render(ctx):
    st.header("Review queue")
    if ctx.manifest is None:
        st.error("cash_manifest not found.")
        return

    ok = ctx.manifest[ctx.manifest["parse_status"] == "OK"].copy()
    c1, c2 = st.columns([1, 2])
    tiers = c1.multiselect("Flag type", ["DATA", "TEMPLATE", "NAMING"], default=["DATA"])
    fy_f = c2.multiselect("Fiscal year", ctx.FYS, default=[ctx.fy], format_func=fy_label)

    if fy_f:
        ok = ok[ok["FiscalYearKey"].isin(fy_f)]
    # one row per flag: split the "; "-joined string and explode
    ok["Flag"] = ok["flags"].fillna("").astype(str).str.split("; ")
    fdf = ok.explode("Flag")
    fdf = fdf[fdf["Flag"].astype(str).str.strip().ne("")]
    fdf["Tier"] = fdf["Flag"].str.split(":").str[0]
    fdf = fdf[fdf["Tier"].isin(tiers)]
    if fdf.empty:
        st.success("No flags match this filter.")
        return

    out = pd.DataFrame({
        "Entity": fdf["ped_no"].map(ctx.label),
        "FY": fdf["FiscalYearKey"].map(fy_label),
        "Q": fdf["PeriodOrder"],
        "Flag": fdf["Flag"],
        "File": fdf["source_file"],
    })
    st.caption(f"{len(out):,} flags on {out['Entity'].nunique()} entities.")

    st.subheader("Most common")
    norm = (out["Flag"].str.replace(r"\[.*?\]", "[...]", regex=True)
                       .str.replace(r"-?[\d,]+\.\d\d", "N", regex=True))
    top = norm.value_counts().head(15).reset_index()
    top.columns = ["Flag", "Count"]
    top["% of filings"] = (top["Count"] / max(len(ok), 1) * 100).round(1)
    st.dataframe(top, width="stretch", hide_index=True)
    st.caption("A flag on more than ~40% of filings is more likely a rule that needs "
               "loosening than a problem shared by every entity.")

    st.subheader("Detail")
    kw = st.text_input("Filter", placeholder="e.g. OPERATIONAL, variance, 27000")
    show = out[out["Flag"].str.contains(kw, case=False, na=False)] if kw else out
    st.dataframe(show, width="stretch", hide_index=True, height=460)
    st.download_button("Download this list", show.to_csv(index=False).encode("utf-8-sig"),
                       "cash_flags.csv", "text/csv")
