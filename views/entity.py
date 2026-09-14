"""Entity -- one LEA across all years: trend, fund detail, bank accounts."""

import streamlit as st

from lib.style import fy_label, section

LINE_ORDER = list(range(1, 13))


def render(ctx):
    lines, fy, q = ctx.lines, ctx.fy, ctx.q
    peds = sorted(lines["EntityKey"].dropna().unique(), key=ctx.label)
    ped = st.sidebar.selectbox("Entity", peds, format_func=ctx.label)

    st.header(ctx.label(ped))
    e = lines[lines["EntityKey"] == ped]

    folders = sorted(e["entity_folder"].dropna().unique())
    if len(folders) > 1:
        st.info("Filed under more than one SharePoint folder: " + ", ".join(map(str, folders)))
    seen = sorted(e["entity_name"].dropna().unique())
    if len(seen) > 1:
        st.caption("Names used across years: " + " · ".join(map(str, seen)))

    st.subheader("Ending cash by quarter")
    tr = (e[e["line_no"] == 12]
          .groupby(["FiscalYearKey", "PeriodOrder"], observed=True)["amount"].sum().reset_index())
    tr["Period"] = (tr["FiscalYearKey"].map(fy_label) + " Q"
                    + tr["PeriodOrder"].astype("Int64").astype(str))
    op = (e[(e["line_no"] == 12) & (e["fund_code"] == 11000)]
          .groupby(["FiscalYearKey", "PeriodOrder"], observed=True)["amount"].sum())
    tr["Operational"] = [op.get((r.FiscalYearKey, r.PeriodOrder), None)
                         for r in tr.itertuples()]
    chart = tr.set_index("Period")[["amount", "Operational"]].rename(columns={"amount": "All funds"})
    st.line_chart(chart)

    st.subheader(f"Fund detail · {fy_label(fy)} Q{q}")
    d = e[(e["FiscalYearKey"] == fy) & (e["PeriodOrder"] == q)]
    if d.empty:
        st.warning("No filing parsed for this entity and period.")
        return

    # Never sum across filings. If two workbooks land in the same
    # entity/year/period cell -- a report saved in the wrong FY folder --
    # aggfunc="sum" silently adds two years together and the numbers look
    # plausible. Show the choice instead.
    srcs = sorted(d["source_file"].dropna().unique())
    if len(srcs) > 1:
        st.warning(f"{len(srcs)} filings map to this entity, year and period. "
                   "Showing one at a time rather than summing them.")
        pick = st.selectbox("Source file", srcs)
        d = d[d["source_file"] == pick]
    piv = d.pivot_table(index="fund_code", columns="line_no", values="amount",
                        aggfunc="sum", observed=True)
    piv = piv.reindex(columns=[c for c in LINE_ORDER if c in piv.columns])
    piv.columns = [f"L{c}" for c in piv.columns]
    st.dataframe(piv.style.format("{:,.2f}"), width="stretch", height=430)
    st.caption("L1 prior-year balance · L2 revenue · L5 expenditures · L12 ending cash.")

    if ctx.bank is not None:
        b = ctx.bank[(ctx.bank["EntityKey"] == ped) & (ctx.bank["FiscalYearKey"] == fy)
                     & (ctx.bank["PeriodOrder"] == q)]
        if not b.empty:
            section("Bank accounts")
            cols = ["account_name", "bank", "statement_balance", "net_outstanding_items",
                    "adjusted_bank_balance", "adjustment_desc", "adjustment_amount"]
            st.dataframe(b[[c for c in cols if c in b.columns]], width="stretch", hide_index=True)

    if ctx.expl is not None:
        x = ctx.expl[(ctx.expl["EntityKey"] == ped) & (ctx.expl["FiscalYearKey"] == fy)
                     & (ctx.expl["PeriodOrder"] == q)]
        if not x.empty:
            section("Explanations")
            st.caption("Why transfers, adjustments and loans were recorded.")
            st.dataframe(x[["line_no", "fund_code", "amount", "explanation"]],
                         width="stretch", hide_index=True)

    if ctx.manifest is not None:
        mm = ctx.manifest[(ctx.manifest["ped_no"] == ped)
                          & (ctx.manifest["FiscalYearKey"] == fy)
                          & (ctx.manifest["PeriodOrder"] == q)]
        if not mm.empty:
            r = mm.iloc[0]
            with st.expander("Source file and flags"):
                st.code(str(r.get("source_path", r.get("source_file", ""))), language=None)
                fl = [f for f in str(r.get("flags") or "").split("; ") if f]
                if fl:
                    for f in fl:
                        st.write("- " + f)
                else:
                    st.write("No flags.")
