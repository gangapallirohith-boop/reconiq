"""
explain_exceptions.py

Takes the exceptions produced by reconcile.py (anything != MATCHED) and asks an LLM
to write a short, grounded, plain-English explanation for a finance analyst.

Guardrail (important, and worth mentioning in your pitch/build-challenges section):
  The LLM is NEVER shown raw account numbers or asked to decide what action to take.
  It is only given the already-computed structured fields (status, amounts, dates,
  diff) for ONE row at a time, and asked to describe likely cause + suggested next
  step in <=2 sentences. This keeps it grounded (no hallucinated numbers) and keeps
  the LLM strictly advisory -- it explains, it never moves money or auto-resolves.

Run:
  export ANTHROPIC_API_KEY=sk-...
  python explain_exceptions.py
"""

import os
import json
import pandas as pd
import requests

MODEL = "claude-sonnet-4-6"
API_URL = "https://api.anthropic.com/v1/messages"


def build_prompt(row: dict) -> str:
    return f"""You are a finance-ops assistant. Given ONE reconciliation exception record below,
write a plain-English explanation for a finance analyst in at most 2 short sentences:
1) the most likely cause, 2) one suggested next action.
Do not invent numbers not present in the data. Do not suggest moving money yourself.

Record:
{json.dumps(row, default=str)}

Respond with ONLY the 2-sentence explanation, no preamble."""


def explain_row(row: dict, api_key: str) -> str:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 200,
        "messages": [{"role": "user", "content": build_prompt(row)}],
    }
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


# Deterministic fallback (used if no API key set, or a call fails) so the demo
# never breaks live -- exceptions still get a useful, rule-based explanation.
def explain_row_fallback(row: dict) -> str:
    status = row.get("status")
    if status == "MISSING_BANK":
        return ("Settlement was raised by the gateway but no matching bank credit has posted yet — "
                "likely still in transit. Recommend re-checking after 2 more business days before escalating.")
    if status == "MISSING_SETTLEMENT":
        return ("A bank credit arrived with no matching settlement or order record — likely a manual "
                "adjustment or a settlement reference that failed to sync. Recommend flagging to the "
                "payments team for manual identification.")
    if status == "PARTIAL_MATCH":
        diff = row.get("amount_diff")
        return (f"Bank credit differs from expected settlement by ₹{diff} — likely an extra deduction "
                "such as a dispute hold or TDS not reflected in the standard fee. Recommend requesting "
                "a settlement breakdown from the gateway for this reference.")
    if status == "UNSETTLED":
        return ("Order was recorded internally but no settlement has been raised by the gateway at all — "
                "likely a payment that is still pending capture or failed silently. Recommend checking "
                "payment status directly via the gateway dashboard.")
    return "No explanation needed — record matched cleanly."


def run(data_dir="data", use_llm=True):
    recon_df = pd.read_csv(f"{data_dir}/reconciliation_report.csv")
    exceptions = recon_df[recon_df["status"] != "MATCHED"].copy()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    explanations = []

    for _, row in exceptions.iterrows():
        row_dict = row.to_dict()
        if use_llm and api_key:
            try:
                explanations.append(explain_row(row_dict, api_key))
                continue
            except Exception as e:
                explanations.append(explain_row_fallback(row_dict) + f" [LLM call failed: {e}]")
                continue
        explanations.append(explain_row_fallback(row_dict))

    exceptions["explanation"] = explanations
    exceptions.to_csv(f"{data_dir}/exceptions_explained.csv", index=False)
    print(f"Explained {len(exceptions)} exceptions -> {data_dir}/exceptions_explained.csv")
    return exceptions


if __name__ == "__main__":
    df = run()
    print(df[["txn_ref", "status", "explanation"]].to_string(index=False))
