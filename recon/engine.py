"""Reconcile an accounting ledger against a bank statement.

Steps, in order (each row is decided once, by the first step that matches it):
  1. clean     normalise references, amounts and dates; rows that fail checks -> 'invalid'
  2. dedupe    references that appear more than once on one side -> 'duplicate'
  3. exact     same reference on both sides -> 'matched', or 'amount_mismatch' if amounts differ
  4. fuzzy     no shared reference, but same amount within a few days -> 'matched_fuzzy'
  5. leftovers -> 'missing_in_bank' / 'missing_in_ledger'
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

COLUMNS = ["status", "ledger_ref", "bank_ref", "ledger_amount", "bank_amount",
           "ledger_date", "bank_date", "note"]


@dataclass
class Rules:
    amount_tolerance: float = 0.01
    date_window_days: int = 3


def clean(df: pd.DataFrame, side: str) -> tuple[pd.DataFrame, list[dict]]:
    df = df.rename(columns=str.lower).copy()
    missing = {"reference", "date", "amount"} - set(df.columns)
    if missing:
        raise ValueError(f"{side} file is missing columns: {sorted(missing)}")
    df["reference"] = df["reference"].astype("string").str.strip().str.upper()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").round(2)
    bad = df["date"].isna() | df["amount"].isna()
    invalid = [_row("invalid", side, r, note="unreadable date or amount") for r in df[bad].itertuples()]
    return df[~bad].reset_index(drop=True), invalid


def _row(status: str, side: str | None = None, r=None, other=None, note: str = "") -> dict:
    out = dict.fromkeys(COLUMNS)
    out.update(status=status, note=note)
    pairs = [(side, r), ("bank" if side == "ledger" else "ledger", other)] if side else []
    for s, rec in pairs:
        if rec is not None:
            ref = rec.reference
            out[f"{s}_ref"] = None if pd.isna(ref) else ref
            out[f"{s}_amount"] = rec.amount
            out[f"{s}_date"] = rec.date
    return out


def reconcile(ledger: pd.DataFrame, bank: pd.DataFrame, rules: Rules | None = None) -> pd.DataFrame:
    rules = rules or Rules()
    led, rows = clean(ledger, "ledger")
    bnk, bad_bank = clean(bank, "bank")
    rows += bad_bank

    # 2. duplicates
    for side, df in (("ledger", led), ("bank", bnk)):
        dup = df["reference"].notna() & df["reference"].duplicated(keep=False)
        rows += [_row("duplicate", side, r, note="reference appears more than once") for r in df[dup].itertuples()]
    led = led[~(led["reference"].notna() & led["reference"].duplicated(keep=False))]
    bnk = bnk[~(bnk["reference"].notna() & bnk["reference"].duplicated(keep=False))]

    # 3. exact reference match
    used_l, used_b = set(), set()
    b_by_ref = {r.reference: (i, r) for i, r in zip(bnk.index, bnk.itertuples()) if pd.notna(r.reference)}
    for i, r in zip(led.index, led.itertuples()):
        if pd.isna(r.reference) or r.reference not in b_by_ref:
            continue
        j, b = b_by_ref[r.reference]
        diff = round(b.amount - r.amount, 2)
        if abs(diff) <= rules.amount_tolerance:
            rows.append(_row("matched", "ledger", r, b))
        else:
            rows.append(_row("amount_mismatch", "ledger", r, b, note=f"bank - ledger = {diff:+.2f}"))
        used_l.add(i)
        used_b.add(j)

    # 4. fuzzy: equal amount, closest date within the window, one-to-one
    rest_l = led.drop(index=list(used_l))
    rest_b = bnk.drop(index=list(used_b))
    candidates = []
    for i, r in zip(rest_l.index, rest_l.itertuples()):
        for j, b in zip(rest_b.index, rest_b.itertuples()):
            days = abs((b.date - r.date).days)
            if abs(b.amount - r.amount) <= rules.amount_tolerance and days <= rules.date_window_days:
                candidates.append((days, i, j, r, b))
    for days, i, j, r, b in sorted(candidates, key=lambda c: c[0]):
        if i in used_l or j in used_b:
            continue
        rows.append(_row("matched_fuzzy", "ledger", r, b, note=f"no shared reference; dates {days} day(s) apart"))
        used_l.add(i)
        used_b.add(j)

    # 5. leftovers
    rows += [_row("missing_in_bank", "ledger", r) for i, r in zip(led.index, led.itertuples()) if i not in used_l]
    rows += [_row("missing_in_ledger", "bank", r) for j, r in zip(bnk.index, bnk.itertuples()) if j not in used_b]
    return pd.DataFrame(rows, columns=COLUMNS)


def summary(result: pd.DataFrame) -> pd.DataFrame:
    s = result.groupby("status").agg(rows=("status", "size"),
                                     ledger_total=("ledger_amount", "sum"),
                                     bank_total=("bank_amount", "sum"))
    return s.round(2).sort_values("rows", ascending=False)
