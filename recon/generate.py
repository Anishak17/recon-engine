"""Synthetic ledger and bank files with known problems planted in them.

    python -m recon.generate data/      # writes ledger.csv, bank.csv, expected.json
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


def make(n: int = 200, seed: int = 3) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = random.Random(seed)
    ledger, bank = [], []
    expected = {"matched": 0, "amount_mismatch": 0, "matched_fuzzy": 0, "missing_in_bank": 0,
                "missing_in_ledger": 0, "duplicate": 0, "invalid": 0}
    start = date(2026, 1, 1)
    for k in range(n):
        ref = f"PAY-{10000 + k}"
        d = start + timedelta(days=rng.randrange(180))
        amt = round(rng.uniform(50, 5000), 2)
        bank_d = d + timedelta(days=rng.choice([0, 0, 1, 2]))  # bank books a bit later
        roll = rng.random()
        if roll < 0.80:
            ledger.append((ref, d, amt))
            bank.append((ref, bank_d, amt))
            expected["matched"] += 1
        elif roll < 0.85:
            ledger.append((ref, d, amt))
            bank.append((ref, bank_d, round(amt - rng.choice([0.5, 10, 100]), 2)))  # fee or typo
            expected["amount_mismatch"] += 1
        elif roll < 0.90:
            ledger.append((ref, d, amt))
            bank.append((None, bank_d, amt))  # bank lost the reference
            expected["matched_fuzzy"] += 1
        elif roll < 0.94:
            ledger.append((ref, d, amt))
            expected["missing_in_bank"] += 1
        else:
            bank.append((f"BNK-{k}", bank_d, amt))
            expected["missing_in_ledger"] += 1
    # a duplicate booking and two unreadable rows
    dup = ledger[0]
    ledger.append(dup)
    expected["matched"] -= 1          # its bank row is now unmatched...
    expected["missing_in_ledger"] += 1  # ...because both ledger copies are flagged instead
    expected["duplicate"] += 2
    ledger.append(("PAY-BAD1", "not a date", 10.0))
    bank.append(("PAY-BAD2", date(2026, 2, 1), "12,x"))
    expected["invalid"] += 2
    cols = ["reference", "date", "amount"]
    return pd.DataFrame(ledger, columns=cols), pd.DataFrame(bank, columns=cols), expected


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
    out.mkdir(parents=True, exist_ok=True)
    led, bnk, exp = make()
    led.to_csv(out / "ledger.csv", index=False)
    bnk.to_csv(out / "bank.csv", index=False)
    (out / "expected.json").write_text(json.dumps(exp, indent=2))
    print(f"wrote {len(led)} ledger rows and {len(bnk)} bank rows to {out}/")
