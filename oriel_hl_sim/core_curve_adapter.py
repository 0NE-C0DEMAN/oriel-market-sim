from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_release_month(value: object) -> str:
    """Normalize date/month values to the app's display key, e.g. Apr 2026."""
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return str(value)
    return dt.strftime("%b %Y")


def load_core_curve_reference(path: Optional[str | Path] = None) -> pd.DataFrame:
    """Load the Oriel core forward-curve output used as the sim's reference.

    Expected default file: data/oriel_curve_current.csv copied/exported from the
    core Oriel repo. The adapter intentionally accepts several common schema
    names so the sim remains a drop-in against the current core app.
    """
    curve_path = Path(path) if path else _repo_root() / "data" / "oriel_curve_current.csv"
    if not curve_path.exists():
        return pd.DataFrame(columns=[
            "release_month", "core_oriel_reference_yoy", "core_index_level",
            "core_std_dev_pct", "core_curve_source"
        ])

    df = pd.read_csv(curve_path)
    if df.empty:
        return pd.DataFrame(columns=[
            "release_month", "core_oriel_reference_yoy", "core_index_level",
            "core_std_dev_pct", "core_curve_source"
        ])

    month_col = next((c for c in ["release_month", "target_month", "maturity", "month"] if c in df.columns), None)
    value_col = next((c for c in ["expected_yoy_pct", "oriel_reference_yoy", "expected_value", "yoy_pct"] if c in df.columns), None)
    if month_col is None or value_col is None:
        return pd.DataFrame(columns=[
            "release_month", "core_oriel_reference_yoy", "core_index_level",
            "core_std_dev_pct", "core_curve_source"
        ])

    out = pd.DataFrame({
        "release_month": df[month_col].map(normalize_release_month),
        "core_oriel_reference_yoy": pd.to_numeric(df[value_col], errors="coerce"),
        "core_index_level": pd.to_numeric(df.get("index_level"), errors="coerce") if "index_level" in df.columns else pd.NA,
        "core_std_dev_pct": pd.to_numeric(df.get("std_dev_pct"), errors="coerce") if "std_dev_pct" in df.columns else pd.NA,
        "core_curve_source": str(curve_path),
    }).dropna(subset=["release_month", "core_oriel_reference_yoy"])

    return out.drop_duplicates(subset=["release_month"], keep="last").reset_index(drop=True)
