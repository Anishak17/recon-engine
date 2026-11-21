import pandas as pd

from recon.engine import reconcile
from recon.generate import make


def df(rows):
    return pd.DataFrame(rows, columns=["reference", "date", "amount"])


def statuses(result):
    return sorted(result["status"])


def test_exact_and_mismatch():
    led = df([("A1", "2026-01-01", 100.0), ("A2", "2026-01-02", 50.0)])
    bnk = df([("a1 ", "2026-01-02", 100.0), ("A2", "2026-01-02", 49.5)])
    r = reconcile(led, bnk)
    assert statuses(r) == ["amount_mismatch", "matched"]
    assert r.loc[r.status == "amount_mismatch", "note"].item() == "bank - ledger = -0.50"


def test_fuzzy_match_respects_date_window():
    led = df([("A1", "2026-01-01", 75.0), ("A2", "2026-01-01", 80.0)])
    bnk = df([(None, "2026-01-03", 75.0), (None, "2026-01-20", 80.0)])
    assert statuses(reconcile(led, bnk)) == ["matched_fuzzy", "missing_in_bank", "missing_in_ledger"]


def test_fuzzy_match_is_one_to_one_and_prefers_closest_date():
    led = df([("A1", "2026-01-05", 10.0)])
    bnk = df([(None, "2026-01-07", 10.0), (None, "2026-01-05", 10.0)])
    r = reconcile(led, bnk)
    assert statuses(r) == ["matched_fuzzy", "missing_in_ledger"]
    assert r.loc[r.status == "matched_fuzzy", "bank_date"].item() == pd.Timestamp("2026-01-05")


def test_duplicates_and_invalid_rows():
    led = df([("A1", "2026-01-01", 10.0), ("A1", "2026-01-01", 10.0), ("A3", "nope", 5.0)])
    bnk = df([("A1", "2026-01-01", 10.0)])
    assert statuses(reconcile(led, bnk)) == ["duplicate", "duplicate", "invalid", "missing_in_ledger"]


def test_generated_data_matches_expected_counts():
    led, bnk, expected = make()
    counts = reconcile(led, bnk)["status"].value_counts().to_dict()
    assert {k: v for k, v in expected.items() if v} == counts
