"""
sample_data.py — Static demo datasets for Oriel Prediction Index Demo

Healthcare: scalar bucket contracts (probability mass over rate ranges)
CPI/Kalshi: binary threshold + exact outcome contracts
"""

from __future__ import annotations

from datetime import date

from engine import (
    BinaryThresholdContract,
    BucketContract,
    ContractObservation,
    ExactOutcomeContract,
    IndexMethodology,
    MaturitySnapshot,
    PriceSelection,
)
from datetime import datetime


# ---------------------------------------------------------------------------
# Healthcare trend demo (scalar buckets)
# ---------------------------------------------------------------------------

HEALTHCARE_METHODOLOGY = IndexMethodology(
    index_name="CareFi Healthcare Trend Forward Index",
    methodology_version="0.1.0",
    price_basis="probability_midpoint",
    interpolation_method="linear",
    weighting_rule="front_anchor_base_100",
    unit_label="%",
)

HEALTHCARE_SNAPSHOTS = [
    MaturitySnapshot(
        maturity=date(2026, 6, 30),
        scalar_buckets=[
            BucketContract("2.5–3.0%", 2.5, 3.0, 0.05,
                observation=ContractObservation(
                    contract_ticker="HC_JUN26_2.5_3.0", source_venue="demo",
                    snapshot_timestamp=datetime(2026, 3, 27, 12, 0),
                    settlement_label="Jun-2026", contract_type="scalar_bucket",
                    price_selection=PriceSelection(chosen_price=0.05, chosen_price_reason="demo_input"),
                )),
            BucketContract("3.0–3.5%", 3.0, 3.5, 0.14,
                observation=ContractObservation(
                    contract_ticker="HC_JUN26_3.0_3.5", source_venue="demo",
                    snapshot_timestamp=datetime(2026, 3, 27, 12, 0),
                    settlement_label="Jun-2026", contract_type="scalar_bucket",
                    price_selection=PriceSelection(chosen_price=0.14, chosen_price_reason="demo_input"),
                )),
            BucketContract("3.5–4.0%", 3.5, 4.0, 0.26),
            BucketContract("4.0–4.5%", 4.0, 4.5, 0.29),
            BucketContract("4.5–5.0%", 4.5, 5.0, 0.18),
            BucketContract("5.0–5.5%", 5.0, 5.5, 0.08),
        ],
    ),
    MaturitySnapshot(
        maturity=date(2026, 9, 30),
        scalar_buckets=[
            BucketContract("2.5–3.0%", 2.5, 3.0, 0.04),
            BucketContract("3.0–3.5%", 3.0, 3.5, 0.10),
            BucketContract("3.5–4.0%", 3.5, 4.0, 0.22),
            BucketContract("4.0–4.5%", 4.0, 4.5, 0.30),
            BucketContract("4.5–5.0%", 4.5, 5.0, 0.22),
            BucketContract("5.0–5.5%", 5.0, 5.5, 0.12),
        ],
    ),
    MaturitySnapshot(
        maturity=date(2026, 12, 31),
        scalar_buckets=[
            BucketContract("2.5–3.0%", 2.5, 3.0, 0.03),
            BucketContract("3.0–3.5%", 3.0, 3.5, 0.08),
            BucketContract("3.5–4.0%", 3.5, 4.0, 0.18),
            BucketContract("4.0–4.5%", 4.0, 4.5, 0.28),
            BucketContract("4.5–5.0%", 4.5, 5.0, 0.26),
            BucketContract("5.0–5.5%", 5.0, 5.5, 0.17),
        ],
    ),
]

# Contract observation table for healthcare
HEALTHCARE_CONTRACTS_TABLE = [
    {"Ticker": "HC_JUN26_2.5_3.0", "Type": "Scalar bucket", "Bucket": "2.5–3.0%", "Price": "0.05", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "HC_JUN26_3.0_3.5", "Type": "Scalar bucket", "Bucket": "3.0–3.5%", "Price": "0.14", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "HC_JUN26_3.5_4.0", "Type": "Scalar bucket", "Bucket": "3.5–4.0%", "Price": "0.26", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "HC_JUN26_4.0_4.5", "Type": "Scalar bucket", "Bucket": "4.0–4.5%", "Price": "0.29", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "HC_JUN26_4.5_5.0", "Type": "Scalar bucket", "Bucket": "4.5–5.0%", "Price": "0.18", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "HC_JUN26_5.0_5.5", "Type": "Scalar bucket", "Bucket": "5.0–5.5%", "Price": "0.08", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "HC_SEP26_3.5_4.0", "Type": "Scalar bucket", "Bucket": "3.5–4.0%", "Price": "0.22", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "HC_SEP26_4.0_4.5", "Type": "Scalar bucket", "Bucket": "4.0–4.5%", "Price": "0.30", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "HC_DEC26_4.5_5.0", "Type": "Scalar bucket", "Bucket": "4.5–5.0%", "Price": "0.26", "Method": "Midpoint", "Status": "Flagged"},
]


# ---------------------------------------------------------------------------
# CPI / Kalshi-style demo (binary threshold + exact outcome)
# ---------------------------------------------------------------------------

CPI_METHODOLOGY = IndexMethodology(
    index_name="Oriel CPI Forward Index",
    methodology_version="0.1.0",
    price_basis="probability_midpoint",
    interpolation_method="linear",
    weighting_rule="front_anchor_base_100",
    unit_label="%",
)

CPI_SNAPSHOTS = [
    MaturitySnapshot(
        maturity=date(2026, 3, 31),
        binary_thresholds=[
            BinaryThresholdContract("Above 2.5%", 2.5, 0.99),
            BinaryThresholdContract("Above 3.0%", 3.0, 0.81),
            BinaryThresholdContract("Above 3.2%", 3.2, 0.80),
            BinaryThresholdContract("Above 3.3%", 3.3, 0.48),
            BinaryThresholdContract("Above 3.4%", 3.4, 0.39),
            BinaryThresholdContract("Above 3.5%", 3.5, 0.12),
            BinaryThresholdContract("Above 3.8%", 3.8, 0.01),
        ],
    ),
    MaturitySnapshot(
        maturity=date(2026, 4, 30),
        exact_outcomes=[
            ExactOutcomeContract("Exactly 2.8%", 2.8, 0.09),
            ExactOutcomeContract("Exactly 3.2%", 3.2, 0.15),
            ExactOutcomeContract("Exactly 3.3%", 3.3, 0.17),
            ExactOutcomeContract("Exactly 3.4%", 3.4, 0.14),
            ExactOutcomeContract("Exactly 3.5%", 3.5, 0.10),
        ],
    ),
    MaturitySnapshot(
        maturity=date(2026, 5, 31),
        exact_outcomes=[
            ExactOutcomeContract("Exactly 3.1%", 3.1, 0.09),
            ExactOutcomeContract("Exactly 3.2%", 3.2, 0.12),
            ExactOutcomeContract("Exactly 3.4%", 3.4, 0.10),
            ExactOutcomeContract("Exactly 3.5%", 3.5, 0.08),
        ],
    ),
    MaturitySnapshot(
        maturity=date(2026, 6, 30),
        exact_outcomes=[
            ExactOutcomeContract("Exactly 2.6%", 2.6, 0.13),
            ExactOutcomeContract("Exactly 3.0%", 3.0, 0.09),
            ExactOutcomeContract("Exactly 3.4%", 3.4, 0.11),
            ExactOutcomeContract("Exactly 3.5%", 3.5, 0.12),
        ],
    ),
]

# Contract observation table for CPI
CPI_CONTRACTS_TABLE = [
    {"Ticker": "KXCPI-26MAR-ABOVE2.5", "Type": "Binary threshold", "Threshold/Value": ">2.5%", "Price": "0.99", "Method": "Monotonic repair", "Status": "Included"},
    {"Ticker": "KXCPI-26MAR-ABOVE3.0", "Type": "Binary threshold", "Threshold/Value": ">3.0%", "Price": "0.81", "Method": "Monotonic repair", "Status": "Included"},
    {"Ticker": "KXCPI-26MAR-ABOVE3.3", "Type": "Binary threshold", "Threshold/Value": ">3.3%", "Price": "0.48", "Method": "Monotonic repair", "Status": "Included"},
    {"Ticker": "KXCPI-26MAR-ABOVE3.5", "Type": "Binary threshold", "Threshold/Value": ">3.5%", "Price": "0.12", "Method": "Monotonic repair", "Status": "Included"},
    {"Ticker": "KXCPI-26APR-3.2", "Type": "Exact outcome", "Threshold/Value": "3.2%", "Price": "0.15", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "KXCPI-26APR-3.3", "Type": "Exact outcome", "Threshold/Value": "3.3%", "Price": "0.17", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "KXCPI-26MAY-3.2", "Type": "Exact outcome", "Threshold/Value": "3.2%", "Price": "0.12", "Method": "Midpoint", "Status": "Included"},
    {"Ticker": "KXCPI-26JUN-3.5", "Type": "Exact outcome", "Threshold/Value": "3.5%", "Price": "0.12", "Method": "Last available", "Status": "Flagged"},
]
