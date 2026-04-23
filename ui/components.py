"""
ui/components.py — Shared methodology step definitions and HTML helpers.
"""
from __future__ import annotations

HC_STEPS = [
    ("Contract prices as probabilities", 'Each bucket (e.g. "3.5\u20134.0%") is priced as the probability the outcome lands in that range. Prices normalized to sum to 1.'),
    ("Extract implied distribution", "Bucket midpoints are representative values. Expected value = probability-weighted average."),
    ("Compute forward points", "One expected value per settlement date \u2014 these become the curve anchor points."),
    ("Index normalization", "Front maturity = base 100. Later maturities expressed as ratios to this anchor."),
    ("Interpolation", "Off-grid dates linearly interpolated between adjacent anchor points."),
]

CPI_STEPS = [
    ("Threshold contracts as survival curve", "Kalshi markets quote P(CPI > k) for each threshold k, forming a non-increasing survival curve."),
    ("Monotonic repair", "Violations corrected by capping each price at the prior threshold\u2019s price."),
    ("Infer bucket probabilities", "Adjacent thresholds differenced to produce bucket probabilities. Tail buckets absorb mass at both ends."),
    ("Exact-outcome contracts", "Used directly as a discrete distribution. Expected value = probability-weighted sum."),
    ("Index normalization & publication", "Front anchor base 100, linear interpolation for off-grid dates, constituent-level transparency."),
]
