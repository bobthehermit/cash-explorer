"""Portfolio -- statewide totals and trend, entities ranked by ending cash."""

import streamlit as st

from lib.style import money, metrics, fy_label


def render(ctx):
    fy, q, sel, ENDING = ctx.fy, ctx.q, ctx.sel, ctx.ENDING
    st.header(f"Statewide cash position · {fy_label(fy)} Q{q}")

    if sel.empty:
        st.warning(f"No filings parsed for {fy_label(fy)} Q{q}.")
        return

    # Guard the statewide totals against two filings landing in one
    # entity/year/period cell: they would be summed and overstate the total.
    per_ent = sel.groupby("EntityKey", observed=True)["source_file"].nunique()
    dup_ents = per_ent[per_ent > 1]
    if len(dup_ents):
        st.warning(f"{len(dup_ents)} entities have more than one filing for "
                   f"{fy_label(fy)} Q{q}; their figures are summed below and will "
                   "be overstated. Re-run the extractor to supersede the duplicates.")

    op_rows = sel[sel["fund_code"] == 11000]
    tot = sel["amount"].sum()
    op = op_rows["amount"].sum()
    n_ent = sel["EntityKey"].nunique()
    neg_op = op_rows[op_rows["amount"] < 0]["EntityKey"].nunique()

    metrics([
        ("Total ending cash", money(tot), False, "all funds, all filers"),
        ("Operational (11000)", money(op), False, None),
        ("Entities reporting", f"{n_ent}", False, None),
        ("Negative operational", f"{neg_op}", neg_op > 0,
         "11000 ending cash below zero"),
    ])

    st.subheader("Trend")
    at_q = ENDING[ENDING["PeriodOrder"] == q]
    trend = at_q.groupby("FiscalYearKey", observed=True)["amount"].sum().rename("All funds")
    trend_op = (at_q[at_q["fund_code"] == 11000]
                .groupby("FiscalYearKey", observed=True)["amount"].sum().rename("Operational"))
    t = trend.to_frame().join(trend_op)
    t.index = [fy_label(i) for i in t.index]
    st.line_chart(t)
    st.caption(f"Statewide ending cash at Q{q}, all entities that filed.")

    st.subheader("By fund")
    byfund = (sel.groupby("fund_code", observed=True)["amount"].agg(["sum", "count"])
                 .sort_values("sum", ascending=False).reset_index())
    byfund.columns = ["Fund", "Ending cash", "Entities"]
    byfund["Ending cash"] = byfund["Ending cash"].map(money)
    st.dataframe(byfund, width="stretch", hide_index=True, height=340)

    st.subheader("Entities by total ending cash")
    ent = (sel.groupby("EntityKey", observed=True)["amount"].sum()
              .sort_values(ascending=False).reset_index())
    ent["Entity"] = ent["EntityKey"].map(ctx.label)
    ent["Ending cash"] = ent["amount"].map(money)
    ent["Operational"] = ent["EntityKey"].map(
        op_rows.groupby("EntityKey", observed=True)["amount"].sum()).map(money)
    st.dataframe(ent[["Entity", "Ending cash", "Operational"]], width="stretch",
                 hide_index=True, height=420)
