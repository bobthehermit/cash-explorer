"""Fund signs -- the FUND_EXPECTATION calibration screen."""

import streamlit as st

from lib.style import money


def render(ctx):
    st.header("Fund sign expectations")
    st.write("Each fund family should normally carry cash or normally sit negative. "
             "This screen shows what the data actually does, so the expectations in "
             "`FUND_EXPECTATION` can be set from evidence rather than assumption.")

    scope = st.radio("Scope", ["This quarter", "All periods"], horizontal=True)
    src = ctx.sel if scope == "This quarter" else ctx.ENDING

    g = src.groupby("fund_code", observed=True)["amount"].agg(
        filings="count",
        negative=lambda s: int((s < -1000).sum()),
        positive=lambda s: int((s > 1000).sum()),
        median="median",
    ).reset_index()
    g["% negative"] = (g["negative"] / g["filings"] * 100).round(1)
    g = g[g["filings"] >= 10].sort_values("% negative", ascending=False)

    st.caption("Materiality $1,000 -- smaller balances are ignored as rounding or "
               "trailing draws. Funds with fewer than 10 filings are hidden.")
    show = g.copy()
    show["median"] = show["median"].map(money)
    show.columns = ["Fund", "Filings", "Negative", "Positive", "Median", "% negative"]
    st.dataframe(show, width="stretch", hide_index=True, height=560)

    st.subheader("Reading this")
    st.markdown(
        "- A fund that is negative in most filings is behaving on a reimbursement "
        "basis, whatever its code says.\n"
        "- A fund that is negative in roughly half is either mixed or misclassified "
        "-- 27xxx funds that are funded up front arguably belong in 28xxx.\n"
        "- A fund that should never go negative (22000 athletics, 13000 transportation, "
        "31100/31900 bond) showing any negatives is a finding, not a calibration problem.")
