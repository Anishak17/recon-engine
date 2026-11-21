"""python -m recon.cli data/ledger.csv data/bank.csv --out report.xlsx"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .engine import Rules, reconcile, summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("ledger")
    p.add_argument("bank")
    p.add_argument("--out", default="reconciliation.xlsx", help=".xlsx (one sheet per status) or .csv")
    p.add_argument("--tolerance", type=float, default=0.01)
    p.add_argument("--days", type=int, default=3)
    a = p.parse_args()

    result = reconcile(pd.read_csv(a.ledger), pd.read_csv(a.bank), Rules(a.tolerance, a.days))
    summ = summary(result)
    print(summ.to_string())

    out = Path(a.out)
    if out.suffix == ".xlsx":
        with pd.ExcelWriter(out) as xw:  # needs openpyxl
            summ.to_excel(xw, sheet_name="summary")
            for status, rows in result.groupby("status"):
                rows.to_excel(xw, sheet_name=status[:31], index=False)
    else:
        result.to_csv(out, index=False)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
