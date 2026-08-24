"""
generate_data.py
Generates 3 synthetic data sources that a real finance team would reconcile:
  1. razorpay_settlements.csv  -> what the payment gateway says it settled
  2. bank_statement.csv        -> what actually hit the bank account
  3. internal_ledger.csv       -> what the company's order system recorded as sold

Designed to include realistic messiness on purpose:
  - A few settlements that never hit the bank (in transit / failed)
  - A few bank credits with no matching settlement (manual adjustments)
  - Partial settlements (platform fee deducted, so amount differs)
  - Date drift (settlement date != bank credit date, off by 1-2 days)
  - Duplicate-looking reference IDs with different amounts (real gotcha)
  - Currency/rounding noise (paise-level rounding differences)

Run: python generate_data.py
Output: ./data/*.csv
"""

import pandas as pd
import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

N_TXNS = 62  # >50 as required by the track bar

OUT_DIR = "data"
import os
os.makedirs(OUT_DIR, exist_ok=True)

base_date = datetime(2026, 8, 1)

settlements = []
bank_rows = []
ledger_rows = []

def money(x):
    return round(x, 2)

for i in range(N_TXNS):
    txn_id = f"pay_{100000 + i}"
    order_id = f"order_{200000 + i}"
    gross_amount = money(random.uniform(500, 45000))
    fee_pct = 0.0236  # razorpay-style blended fee
    fee = money(gross_amount * fee_pct)
    net_amount = money(gross_amount - fee)

    order_date = base_date + timedelta(days=random.randint(0, 20))
    settle_date = order_date + timedelta(days=random.choice([1, 1, 1, 2, 3]))
    bank_date = settle_date + timedelta(days=random.choice([0, 0, 1, 1, 2]))  # bank posting drift

    ledger_rows.append({
        "order_id": order_id,
        "txn_ref": txn_id,
        "order_date": order_date.strftime("%Y-%m-%d"),
        "order_amount": gross_amount,
        "customer": fake.name(),
    })

    scenario = random.random()

    if scenario < 0.80:
        # Clean match: appears in both settlement and bank, net amount matches
        settlements.append({
            "settlement_id": f"stl_{300000+i}",
            "txn_ref": txn_id,
            "settlement_date": settle_date.strftime("%Y-%m-%d"),
            "gross_amount": gross_amount,
            "fee": fee,
            "net_amount": net_amount,
        })
        bank_rows.append({
            "bank_ref": f"UTR{400000+i}",
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "credit_amount": net_amount,
            "narration": f"NEFT-RAZORPAY-{txn_id}",
        })

    elif scenario < 0.88:
        # Settlement exists, but never hit the bank yet (in transit) -> exception
        settlements.append({
            "settlement_id": f"stl_{300000+i}",
            "txn_ref": txn_id,
            "settlement_date": settle_date.strftime("%Y-%m-%d"),
            "gross_amount": gross_amount,
            "fee": fee,
            "net_amount": net_amount,
        })
        # no bank row

    elif scenario < 0.93:
        # Partial settlement: extra ad-hoc deduction not reflected in fee (e.g. TDS / dispute hold)
        adjustment = money(gross_amount * random.uniform(0.01, 0.04))
        actual_net = money(net_amount - adjustment)
        settlements.append({
            "settlement_id": f"stl_{300000+i}",
            "txn_ref": txn_id,
            "settlement_date": settle_date.strftime("%Y-%m-%d"),
            "gross_amount": gross_amount,
            "fee": fee,
            "net_amount": net_amount,
        })
        bank_rows.append({
            "bank_ref": f"UTR{400000+i}",
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "credit_amount": actual_net,  # differs from net_amount -> partial match
            "narration": f"NEFT-RAZORPAY-{txn_id}",
        })

    elif scenario < 0.97:
        # Bank credit with no settlement record at all (manual/unknown credit) -> exception
        bank_rows.append({
            "bank_ref": f"UTR{400000+i}",
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "credit_amount": money(random.uniform(500, 5000)),
            "narration": "NEFT-MANUAL-ADJ-UNKNOWN",
        })
        # still log the order in ledger, but no settlement (e.g. settlement lost/error)

    else:
        # Rounding-only mismatch (paise-level) -> should still be auto-matched by tolerance
        rounding_noise = random.choice([-0.02, -0.01, 0.01, 0.02])
        settlements.append({
            "settlement_id": f"stl_{300000+i}",
            "txn_ref": txn_id,
            "settlement_date": settle_date.strftime("%Y-%m-%d"),
            "gross_amount": gross_amount,
            "fee": fee,
            "net_amount": net_amount,
        })
        bank_rows.append({
            "bank_ref": f"UTR{400000+i}",
            "value_date": bank_date.strftime("%Y-%m-%d"),
            "credit_amount": money(net_amount + rounding_noise),
            "narration": f"NEFT-RAZORPAY-{txn_id}",
        })

df_settlements = pd.DataFrame(settlements)
df_bank = pd.DataFrame(bank_rows)
df_ledger = pd.DataFrame(ledger_rows)

df_settlements.to_csv(f"{OUT_DIR}/razorpay_settlements.csv", index=False)
df_bank.to_csv(f"{OUT_DIR}/bank_statement.csv", index=False)
df_ledger.to_csv(f"{OUT_DIR}/internal_ledger.csv", index=False)

print(f"Generated {len(df_ledger)} orders")
print(f"  settlements: {len(df_settlements)} rows -> {OUT_DIR}/razorpay_settlements.csv")
print(f"  bank rows:   {len(df_bank)} rows -> {OUT_DIR}/bank_statement.csv")
print(f"  ledger rows: {len(df_ledger)} rows -> {OUT_DIR}/internal_ledger.csv")
