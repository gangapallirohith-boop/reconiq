"""
test_reconcile.py
Lightweight tests for the matching engine using hand-crafted edge cases
(not the random synthetic batch) so the matching LOGIC itself is verified,
not just "it ran without crashing".

Run: python test_reconcile.py
"""

import pandas as pd
from reconcile import reconcile, summarize


def test_clean_match():
    ledger = pd.DataFrame([{"order_id": "o1", "txn_ref": "pay_1", "order_date": "2026-08-01", "order_amount": 1000, "customer": "A"}])
    settlements = pd.DataFrame([{"settlement_id": "s1", "txn_ref": "pay_1", "settlement_date": "2026-08-02", "gross_amount": 1000, "fee": 23.6, "net_amount": 976.4}])
    bank = pd.DataFrame([{"bank_ref": "u1", "value_date": "2026-08-02", "credit_amount": 976.4, "narration": "NEFT-RAZORPAY-pay_1"}])
    result = reconcile(settlements, bank, ledger)
    assert result.iloc[0]["status"] == "MATCHED", "Clean match should be MATCHED"
    print("test_clean_match: PASS")


def test_rounding_tolerance():
    ledger = pd.DataFrame([{"order_id": "o1", "txn_ref": "pay_1", "order_date": "2026-08-01", "order_amount": 1000, "customer": "A"}])
    settlements = pd.DataFrame([{"settlement_id": "s1", "txn_ref": "pay_1", "settlement_date": "2026-08-02", "gross_amount": 1000, "fee": 23.6, "net_amount": 976.40}])
    bank = pd.DataFrame([{"bank_ref": "u1", "value_date": "2026-08-02", "credit_amount": 976.41, "narration": "NEFT-RAZORPAY-pay_1"}])  # 1 paisa off
    result = reconcile(settlements, bank, ledger)
    assert result.iloc[0]["status"] == "MATCHED", "1-paisa rounding noise should still be MATCHED"
    print("test_rounding_tolerance: PASS")


def test_missing_bank():
    ledger = pd.DataFrame([{"order_id": "o1", "txn_ref": "pay_1", "order_date": "2026-08-01", "order_amount": 1000, "customer": "A"}])
    settlements = pd.DataFrame([{"settlement_id": "s1", "txn_ref": "pay_1", "settlement_date": "2026-08-02", "gross_amount": 1000, "fee": 23.6, "net_amount": 976.4}])
    bank = pd.DataFrame(columns=["bank_ref", "value_date", "credit_amount", "narration"])
    result = reconcile(settlements, bank, ledger)
    assert result.iloc[0]["status"] == "MISSING_BANK"
    print("test_missing_bank: PASS")


def test_partial_match_beyond_tolerance():
    ledger = pd.DataFrame([{"order_id": "o1", "txn_ref": "pay_1", "order_date": "2026-08-01", "order_amount": 1000, "customer": "A"}])
    settlements = pd.DataFrame([{"settlement_id": "s1", "txn_ref": "pay_1", "settlement_date": "2026-08-02", "gross_amount": 1000, "fee": 23.6, "net_amount": 976.4}])
    bank = pd.DataFrame([{"bank_ref": "u1", "value_date": "2026-08-02", "credit_amount": 950.0, "narration": "NEFT-RAZORPAY-pay_1"}])  # 26.4 off
    result = reconcile(settlements, bank, ledger)
    assert result.iloc[0]["status"] == "PARTIAL_MATCH"
    print("test_partial_match_beyond_tolerance: PASS")


def test_unsettled_order():
    ledger = pd.DataFrame([{"order_id": "o1", "txn_ref": "pay_1", "order_date": "2026-08-01", "order_amount": 1000, "customer": "A"}])
    settlements = pd.DataFrame(columns=["settlement_id", "txn_ref", "settlement_date", "gross_amount", "fee", "net_amount"])
    bank = pd.DataFrame(columns=["bank_ref", "value_date", "credit_amount", "narration"])
    result = reconcile(settlements, bank, ledger)
    assert result.iloc[0]["status"] == "UNSETTLED"
    print("test_unsettled_order: PASS")


def test_summary_math():
    ledger = pd.DataFrame([
        {"order_id": "o1", "txn_ref": "pay_1", "order_date": "2026-08-01", "order_amount": 1000, "customer": "A"},
        {"order_id": "o2", "txn_ref": "pay_2", "order_date": "2026-08-01", "order_amount": 500, "customer": "B"},
    ])
    settlements = pd.DataFrame([
        {"settlement_id": "s1", "txn_ref": "pay_1", "settlement_date": "2026-08-02", "gross_amount": 1000, "fee": 23.6, "net_amount": 976.4},
        {"settlement_id": "s2", "txn_ref": "pay_2", "settlement_date": "2026-08-02", "gross_amount": 500, "fee": 11.8, "net_amount": 488.2},
    ])
    bank = pd.DataFrame([
        {"bank_ref": "u1", "value_date": "2026-08-02", "credit_amount": 976.4, "narration": "NEFT-RAZORPAY-pay_1"},
    ])  # pay_2 never lands in bank
    result = reconcile(settlements, bank, ledger)
    summary = summarize(result)
    assert summary["total_records"] == 2
    assert summary["matched"] == 1
    assert summary["match_rate_pct"] == 50.0
    print("test_summary_math: PASS")


if __name__ == "__main__":
    test_clean_match()
    test_rounding_tolerance()
    test_missing_bank()
    test_partial_match_beyond_tolerance()
    test_unsettled_order()
    test_summary_math()
    print("\nAll tests passed.")
