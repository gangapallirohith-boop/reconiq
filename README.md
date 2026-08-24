ReconIQ — AI Reconciliation Agent
----- AI Finance Controller -----

What it solves
Finance teams reconcile three things that should agree but rarely do cleanly: what the order system says was sold, what the payment gateway says it settled, and what actually landed in the bank. Today this is a manual, spreadsheet-driven, VLOOKUP-and-squint process — slow, error-prone, and it scales linearly with headcount, not with transaction volume.

ReconIQ automatically reconciles all three sources across a batch, classifies every transaction into a clear status, and uses an LLM — strictly downstream, strictly advisory — to explain why each exception happened in plain English, so an analyst can act on it in seconds instead of digging through raw rows.

What it does not do (on purpose)
It does not let the LLM decide matches. All match/exception classification is deterministic, rule-based, and reproducible — the same batch always produces the same result.
It does not let the LLM move money or auto-resolve exceptions. It only explains a decision that's already been made by the rules engine.
It never re-computes numbers the LLM might hallucinate — the LLM is fed only the pre-computed structured fields for one exception at a time.
This satisfies the track's bar: "Throughput plus measured accuracy plus an honest exception list."

Architecture
generate_data.py
   └─> data/razorpay_settlements.csv   (what the gateway paid out)
   └─> data/bank_statement.csv         (what actually hit the bank)
   └─> data/internal_ledger.csv        (what was sold, per order system)
              │
              ▼
reconcile.py  (deterministic rules engine)
   - joins all 3 sources on txn_ref
   - amount tolerance: ₹0.05 (absorbs paise rounding)
   - date tolerance: 3 days (absorbs settlement→bank posting drift)
   - classifies every record: MATCHED / PARTIAL_MATCH / MISSING_BANK /
     MISSING_SETTLEMENT / UNSETTLED
              │
              ▼
   data/reconciliation_report.csv  (full audit trail, every record, every status)
              │
              ▼
explain_exceptions.py  (LLM, downstream only)
   - takes rows where status != MATCHED
   - sends ONE row at a time, structured fields only, to Claude
   - asks for: likely cause + suggested next action, ≤2 sentences
   - falls back to deterministic rule-based explanations if no API key /
     the call fails, so the demo never breaks live
              │
              ▼
   data/exceptions_explained.csv
              │
              ▼
app.py  (Streamlit dashboard)
   - batch summary metrics (match rate, exceptions, unexplained ₹ variance)
   - matched records table
   - exception cards with AI explanations
   - raw source tabs for auditability
Setup
pip install -r requirements.txt

# optional — enables live LLM explanations, otherwise uses rule-based fallback
export ANTHROPIC_API_KEY=sk-ant-...

python generate_data.py        # creates synthetic batch (62 records, >50 required)
python reconcile.py            # runs matching, prints summary, writes report
python explain_exceptions.py   # explains exceptions
python test_reconcile.py       # runs the test suite (6 edge-case tests)

streamlit run app.py           # launches the dashboard
Sample output (one run)
total_records: 62
matched: 52
match_rate_pct: 83.9
exceptions: 10
missing_bank: 6
partial_match: 4
missing_settlement: 0
total_unexplained_variance: ₹2,105.57
Build challenges & technical obstacles
False exceptions from paise-level rounding. Early version flagged any amount mismatch as an exception, which buried real problems under rounding noise. Fixed by adding an explicit amount tolerance (₹0.05) instead of exact-equality matching — but the tolerance had to be tight enough that it wouldn't silently swallow a genuine partial settlement (see next point).

Distinguishing "just rounding" from "a real partial deduction." A ₹0.02 gap and a ₹400 gap are very different problems, but both are technically "amount doesn't match." Solved by tiering the classification: anything within tolerance auto-matches, anything beyond it becomes PARTIAL_MATCH with the exact diff surfaced — never silently absorbed, never silently flagged as fully broken.

Bank statements don't cleanly key to a transaction ID. Real bank statements only give free-text narrations (e.g. NEFT-RAZORPAY-pay_100003), not a clean foreign key to the settlement table. Had to write a narration parser to extract the embedded reference before any join could happen — this is closer to what a real reconciliation job looks like than a clean-keys toy dataset would be.

Keeping the LLM from becoming a source of financial error. The obvious naive design is "give the LLM all three CSVs and ask it to reconcile them" — but that makes matching non-deterministic and unauditable, which fails the track's explainability bar outright. Solved by fully separating concerns: matching is 100% rules-based Python, and the LLM is only ever shown one already-classified exception's structured fields, asked to explain — never to decide.

Demo reliability without a live API key at pitch time. Didn't want the video to depend on a network call succeeding on the first try. Built a deterministic rule-based fallback explainer that activates automatically if ANTHROPIC_API_KEY isn't set or a call fails, so the app always produces a complete, sensible-looking output either way.

Tech stack
Python (pandas) — synthetic data generation + deterministic matching engine
Anthropic API (Claude) — downstream exception explanation only
Streamlit — dashboard / demo UI
pytest-style assertions in test_reconcile.py — matching logic verification
