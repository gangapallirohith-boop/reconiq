"""
app.py
ReconIQ — AI Reconciliation Agent
Streamlit UI for the demo / pitch video.

Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import subprocess
import os

from reconcile import load_data, reconcile, summarize
from explain_exceptions import run as explain_run

st.set_page_config(page_title="ReconIQ", page_icon="🧮", layout="wide")

st.title("🧮 ReconIQ — AI Reconciliation Agent")
st.caption(
    "Matches Razorpay settlements ↔ bank statement ↔ internal order ledger, "
    "flags exceptions, and explains each one in plain English."
)

DATA_DIR = "data"

col_a, col_b = st.columns([1, 3])
with col_a:
    if st.button("🔄 Regenerate synthetic data"):
        subprocess.run(["python3", "generate_data.py"], check=True)
        st.success("New synthetic batch generated.")

with col_b:
    st.write("")

if not os.path.exists(f"{DATA_DIR}/razorpay_settlements.csv"):
    subprocess.run(["python3", "generate_data.py"], check=True)

settlements, bank, ledger = load_data(DATA_DIR)
recon_df = reconcile(settlements, bank, ledger)
recon_df.to_csv(f"{DATA_DIR}/reconciliation_report.csv", index=False)
summary = summarize(recon_df)

st.subheader("Batch summary")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total records", summary["total_records"])
m2.metric("Match rate", f"{summary['match_rate_pct']}%")
m3.metric("Matched", summary["matched"])
m4.metric("Exceptions", summary["exceptions"])
m5.metric("Unexplained variance (₹)", f"{summary['total_unexplained_variance']:,.2f}")

st.divider()

tab1, tab2, tab3 = st.tabs(["✅ Matched records", "⚠️ Exceptions (with AI explanations)", "📄 Raw sources"])

with tab1:
    matched = recon_df[recon_df["status"] == "MATCHED"]
    st.dataframe(matched, use_container_width=True, hide_index=True)

with tab2:
    st.write(
        "Every exception below is explained by an LLM using **only the structured fields "
        "already computed by the rules engine** — it never sees raw account data and never "
        "moves money. It only explains and suggests a next step."
    )
    if st.button("✨ Generate / refresh AI explanations"):
        with st.spinner("Calling LLM for exception explanations..."):
            explain_run(DATA_DIR)
        st.success("Explanations updated.")

    exc_path = f"{DATA_DIR}/exceptions_explained.csv"
    if os.path.exists(exc_path):
        exceptions = pd.read_csv(exc_path)
        for _, row in exceptions.iterrows():
            with st.expander(f"{row['txn_ref']} — {row['status']}"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.write(f"**Order amount:** ₹{row.get('order_amount', '-')}")
                    st.write(f"**Settlement net:** ₹{row.get('settlement_net', '-')}")
                    st.write(f"**Bank credit:** ₹{row.get('bank_credit', '-')}")
                    st.write(f"**Diff:** ₹{row.get('amount_diff', '-')}")
                with c2:
                    st.info(row["explanation"])
    else:
        st.write("Click the button above to generate explanations.")

with tab3:
    s1, s2, s3 = st.tabs(["Razorpay settlements", "Bank statement", "Internal ledger"])
    with s1:
        st.dataframe(settlements, use_container_width=True, hide_index=True)
    with s2:
        st.dataframe(bank, use_container_width=True, hide_index=True)
    with s3:
        st.dataframe(ledger, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Matching logic (rules engine) is 100% deterministic and auditable — amount tolerance ₹0.05, "
    "date tolerance 3 days. The LLM is used strictly downstream, only to explain already-classified "
    "exceptions — it has no authority to reclassify or resolve them."
)
