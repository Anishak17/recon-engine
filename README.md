# recon-engine

Reconciles an accounting ledger against a bank statement and tells you exactly which
payments match, which don't, and why. Finance teams often do this by hand in Excel every
month; this does it in seconds and produces an Excel report with one sheet per problem type.

## How it decides

Each row is decided once, by the first step that applies:

| Step | Rule | Status |
|---|---|---|
| 1. Clean | normalise references (trim, upper-case), parse dates and amounts | unreadable rows → `invalid` |
| 2. Dedupe | a reference that appears twice on one side is a double booking | `duplicate` |
| 3. Exact | same reference on both sides | `matched`, or `amount_mismatch` with the difference |
| 4. Fuzzy | no shared reference, same amount (±0.01), dates ≤ 3 days apart; closest date wins, one-to-one | `matched_fuzzy` |
| 5. Leftovers | nothing matched | `missing_in_bank` / `missing_in_ledger` |

Why this order: exact rules first so fuzzy matching can't "steal" a row that has a real match,
and duplicates are removed before matching so one bank payment can't match two bookings.

## Results on the synthetic data

`python -m recon.generate` creates 193 ledger and 194 bank rows with planted problems
(bank fees, lost references, missing payments, a double booking, unreadable values).
Every planted problem is found; a test checks the counts:

| Status | Rows |
|---|---|
| matched | 152 |
| matched_fuzzy | 19 |
| amount_mismatch | 12 |
| missing_in_ledger | 10 |
| missing_in_bank | 7 |
| duplicate | 2 |
| invalid | 2 |

## Run it

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q

python -m recon.generate data/
python -m recon.cli data/ledger.csv data/bank.csv --out report.xlsx
open report.xlsx
```

Input: two CSV files with columns `reference, date, amount`. Options: `--tolerance 0.01`, `--days 3`.

## Next steps

- Many-to-one matching (one bank payment settling several invoices).
- Learn matching rules from past manual decisions.
- Run on a schedule and post the summary to Slack/Teams.
