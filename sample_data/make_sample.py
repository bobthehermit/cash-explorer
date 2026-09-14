#!/usr/bin/env python3
"""
make_sample.py -- fabricate a small cash_data set in the shape publish.py writes.

    python sample_data/make_sample.py          # -> sample_data/cash_data/

Nothing here is real. Twelve invented entities, FY22-FY26, four quarters each,
a plausible fund mix, and a sprinkling of the same flag wordings the extractor
emits so every view has something to show. Use it to run the app on a machine
with no access to the real parquet, and to demo the app without exposing
anyone's numbers.
"""

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cash_data")
rng = np.random.default_rng(42)

ENTITIES = [  # (ped_no, name, folder, size multiplier)
    ("001-000", "ALBUQUERQUE PUBLIC SCHOOLS", "Albuquerque", 40),
    ("006-000", "BELEN CONSOLIDATED SCHOOLS", "Belen", 4),
    ("017-000", "LAS CRUCES PUBLIC SCHOOLS", "Las Cruces", 20),
    ("030-000", "MORA INDEPENDENT SCHOOLS", "Mora", 0.6),
    ("043-000", "QUEMADO INDEPENDENT SCHOOLS", "Quemado", 0.3),
    ("071-000", "SANTA FE PUBLIC SCHOOLS", "Santa Fe", 12),
    ("580-001", "21ST CENTURY PUBLIC ACADEMY", "21st century public Academy", 0.5),
    ("001-090", "ABQ CHARTER ACADEMY", "ABQ Charter Academy", 0.4),
    ("563-001", "SOUTH VALLEY PREPARATORY", "South Valley Prep", 0.3),
    ("517-001", "ALMA D'ARTE CHARTER", "ALMA D'ARTE CHARTER", 0.3),
    ("545-001", "ACE LEADERSHIP HIGH SCHOOL", "ACE Leadership High School", 0.4),
    ("552-001", "ANANSI CHARTER SCHOOL", "Anansi Charter School", 0.2),
]
FYS = [2022, 2023, 2024, 2025, 2026]
QS = [1, 2, 3, 4]
# fund -> (typical ending balance in $M for multiplier 1, sign tendency)
FUNDS = {
    11000: (2.0, +1), 13000: (0.15, +1), 14000: (0.08, +1), 21000: (0.05, +1),
    22000: (0.03, +1), 23000: (0.04, +1), 24101: (0.10, -1), 24106: (0.06, -1),
    24154: (0.03, -1), 25153: (0.05, +1), 26107: (0.02, +1), 27107: (0.04, -1),
    27502: (0.02, -1), 28211: (0.03, +1), 29102: (0.01, +1), 31100: (1.5, +1),
    31200: (0.3, +1), 31600: (0.6, +1), 31700: (0.2, +1), 31900: (0.8, +1),
    41000: (0.05, +1),
}
LINE_LABELS = {1: "Beginning cash", 2: "Revenue", 3: "Transfers in", 4: "Subtotal",
               5: "Expenditures", 6: "Transfers out", 7: "Subtotal", 8: "Adjustments",
               9: "Loans", 10: "Subtotal", 11: "Permanent cash transfers", 12: "Ending cash"}
# entities with a structurally negative operational fund in the last two years
TROUBLED = {"043-000", "552-001"}


def one_filing(ped, name, folder, mult, fy, q):
    lines, expl = [], []
    src = f"{folder} FY{fy % 100} Q{q} Cash Report {ped}.xlsx"
    for fund, (base, sign) in FUNDS.items():
        scale = base * mult * 1e6
        begin = sign * abs(rng.normal(scale, scale * 0.3))
        rev = abs(rng.normal(scale * 0.4, scale * 0.15))
        exp = abs(rng.normal(scale * 0.4, scale * 0.15))
        t_in = abs(rng.normal(0, scale * 0.02)) if rng.random() < 0.15 else 0.0
        t_out = abs(rng.normal(0, scale * 0.02)) if rng.random() < 0.15 else 0.0
        adj = rng.normal(0, scale * 0.01) if rng.random() < 0.1 else 0.0
        if fund == 11000 and ped in TROUBLED and fy >= 2025:
            begin, exp = begin * 0.2, exp * 1.6
        l4 = begin + rev + t_in
        l7 = l4 - exp - t_out
        l10 = l7 + adj
        l12 = l10
        vals = {1: begin, 2: rev, 3: t_in, 4: l4, 5: -exp, 6: -t_out, 7: l7,
                8: adj, 9: 0.0, 10: l10, 11: 0.0, 12: l12}
        for ln, amt in vals.items():
            lines.append(dict(EntityKey=ped, ped_no=ped, entity_name=name,
                              entity_folder=folder, FiscalYearKey=fy,
                              FiscalYear=f"{fy % 100 - 1:02d}{fy % 100:02d}",
                              PeriodOrder=q, PeriodKey=fy * 10 + q, fund_code=fund,
                              line_no=ln, line_label=LINE_LABELS[ln],
                              amount=round(float(amt), 2), source_file=src))
        for ln in (3, 6, 8):
            if vals[ln] and fy >= 2024:
                expl.append(dict(EntityKey=ped, FiscalYearKey=fy, PeriodOrder=q,
                                 line_no=ln, fund_code=fund, amount=round(float(vals[ln]), 2),
                                 explanation=rng.choice([
                                     "Transfer to cover payroll timing",
                                     "Correction of prior quarter posting",
                                     "Grant reimbursement received late"])))
    total = sum(r["amount"] for r in lines if r["line_no"] == 12)
    op = next(r["amount"] for r in lines if r["line_no"] == 12 and r["fund_code"] == 11000)
    return lines, expl, total, op, src


def main():
    L, B, E, M, C = [], [], [], [], []
    for ped, name, folder, mult in ENTITIES:
        for fy in FYS:
            if ped == "552-001" and fy < 2024:      # opened in FY24
                continue
            for q in QS:
                filed = not (fy == 2026 and q == 4) and rng.random() > 0.04
                C.append(dict(ped_no=ped, entity_name=name, FiscalYearKey=fy,
                              PeriodOrder=q, filed=filed))
                if not filed:
                    continue
                lines, expl, total, op, src = one_filing(ped, name, folder, mult, fy, q)
                L += lines
                E += expl
                n_acct = 2 if mult < 1 else 4
                for i in range(n_acct):
                    B.append(dict(EntityKey=ped, FiscalYearKey=fy, PeriodOrder=q,
                                  account_name=["Operating", "Payroll", "Bond", "Activity"][i],
                                  bank=rng.choice(["Wells Fargo", "US Bank", "First American"]),
                                  statement_balance=round(total / n_acct * 1.02, 2),
                                  net_outstanding_items=round(-total / n_acct * 0.02, 2),
                                  adjusted_bank_balance=round(total / n_acct, 2),
                                  adjustment_desc="", adjustment_amount=0.0))
                flags = []
                if op < 0:
                    flags.append(f"DATA: negative ending cash in OPERATIONAL (11000): {op:,.2f}")
                if rng.random() < 0.08:
                    flags.append("DATA: bank-to-book variance 1,204.50 != 0")
                if rng.random() < 0.05:
                    flags.append("NAMING: filename PED no. [006-00] != workbook PED no. [006-000]")
                if rng.random() < 0.04:
                    flags.append("TEMPLATE: Summary tab missing (expected FY24+)")
                if fy >= 2024 and rng.random() < 0.03:
                    flags.append("DATA: Line 4 != L1+L2+L3 in fund 31100")
                M.append(dict(source_file=src,
                              source_path=f"raw\\{folder}\\Shared Documents\\FY{fy % 100}\\Financial Reporting\\Q{q}\\{src}",
                              entity_folder=folder, fy_folder=f"FY{fy % 100}", ped_no=ped,
                              ped_no_raw=ped, entity_name=name, EntityKey=ped,
                              FiscalYearKey=fy, PeriodOrder=q, period_label=f"Q{q}",
                              parse_status="OK", flags="; ".join(flags),
                              has_data_flag=any(f.startswith("DATA") for f in flags),
                              has_template_flag=any(f.startswith("TEMPLATE") for f in flags),
                              has_naming_flag=any(f.startswith("NAMING") for f in flags),
                              grand_total_line12=round(total, 2),
                              parser_version="sample"))

    os.makedirs(OUT, exist_ok=True)
    tables = {"cash_lines": pd.DataFrame(L), "cash_bank": pd.DataFrame(B),
              "cash_explanations": pd.DataFrame(E), "cash_manifest": pd.DataFrame(M),
              "cash_coverage": pd.DataFrame(C)}
    info = {}
    for name, df in tables.items():
        p = os.path.join(OUT, f"{name}.parquet")
        df.to_parquet(p, index=False)
        info[name] = {"file": f"{name}.parquet", "rows": len(df), "bytes": os.path.getsize(p)}
        print(f"  {name:<18} {len(df):>8,} rows")
    with open(os.path.join(OUT, "publish_manifest.json"), "w") as f:
        json.dump({"published_at": datetime.now(timezone.utc).isoformat(),
                   "extraction": {"parser_version": "sample", "root": "fabricated"},
                   "tables": info}, f, indent=2)
    print(f"\nSample data written to {OUT}\nRun:  streamlit run app.py")


if __name__ == "__main__":
    main()
