"""Coverage -- who has not filed."""

import streamlit as st

from lib.style import fy_label


def render(ctx):
    st.header("Who has not filed")
    cov = ctx.coverage
    if cov is None:
        st.error("cash_coverage not found.")
        return

    g = cov.groupby("FiscalYearKey")["filed"].agg(["sum", "count"])
    g["pct"] = (g["sum"] / g["count"] * 100).round(1)
    g.columns = ["Filed", "Expected", "% filed"]
    g.index = [fy_label(i) for i in g.index]
    st.dataframe(g.reset_index(names="Fiscal year"), width="stretch", hide_index=True)

    st.subheader(f"Missing filings · {fy_label(ctx.fy)}")
    miss = cov[(cov["FiscalYearKey"] == ctx.fy) & (~cov["filed"].astype(bool))]
    if miss.empty:
        st.success(f"Every entity filed all four quarters of {fy_label(ctx.fy)}.")
        return
    st.caption(f"{len(miss)} missing filings across {miss['ped_no'].nunique()} entities.")
    by_q = miss.groupby("PeriodOrder").size().reset_index()
    by_q.columns = ["Quarter", "Missing"]
    st.bar_chart(by_q.set_index("Quarter"))

    pivot = (miss.assign(x="missing")
                 .pivot_table(index=["entity_name", "ped_no"], columns="PeriodOrder",
                              values="x", aggfunc="first")
                 .fillna("").reset_index())
    pivot.columns = [f"Q{int(c)}" if isinstance(c, (int, float)) else c for c in pivot.columns]
    st.dataframe(pivot, width="stretch", hide_index=True, height=460)
    st.caption("Only years in which the entity actually filed are counted, so a charter "
               "that opened in FY24 shows no gaps before that.")
