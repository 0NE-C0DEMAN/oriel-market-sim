"""
ui/tables.py — Plotly desk table builder and height helpers.

Shared across all tab renderers. Uses design tokens from ui.tokens.
"""
from __future__ import annotations

import math
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from ui.tokens import (
    BG_APP, GOLD, TEXT_PRI, TEXT_SEC,
    TABLE_STRIPE_A, TABLE_STRIPE_B, TABLE_HEADER_BG,
    TABLE_GRID_LINE, TABLE_FLAGGED_BG, TABLE_SIGMA_BG,
    DESK_TABLE_HEADER_PX, DESK_TABLE_ROW_PX, DESK_TABLE_PAD_PX,
)


def _fmt_desk_cell(val) -> str:
    try:
        if val is None or pd.isna(val):
            return "\u2014"
    except (TypeError, ValueError):
        pass
    if isinstance(val, pd.Timestamp):
        return val.strftime("%b %Y")
    if isinstance(val, date):
        return val.strftime("%b %Y")
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, float):
        if math.isnan(val):
            return "\u2014"
        return f"{val:.4f}"
    if isinstance(val, int):
        return str(val)
    return str(val).strip()


def _desk_table_col_widths(df: pd.DataFrame) -> list[float]:
    """Relative column widths for Plotly Table (long text cols wider)."""
    out: list[float] = []
    for c in df.columns:
        n = str(c).lower()
        # Very long text columns
        if n in ("check", "description", "criterion"):
            out.append(3.5)
        elif "fallback_level" in n or "fallback_reason" in n or "reason_codes" in n:
            out.append(3.6)
        elif n == "run_id":
            out.append(2.8)
        elif "timestamp" in n or "source_timestamp" in n:
            out.append(2.8)
        elif "instrument" in n:
            out.append(2.2)
        elif "exclusion" in n or "reason" in n:
            out.append(3.0)
        # Moderate-length columns
        elif "threshold" in n or "bucket" in n:
            out.append(2.6)
        elif n in ("ticker", "source"):
            out.append(1.8)
        elif "maturity" in n or "exp" in n or "value" in n:
            out.append(2.0)
        elif n in ("type", "method", "status"):
            out.append(2.2)
        elif "decision" in n or "publication" in n:
            out.append(1.8)
        elif "score" in n or "implied" in n or "reference" in n:
            out.append(1.8)
        elif "index" in n:
            out.append(1.5)
        elif n == "key":
            out.append(1.05)
        elif n in ("price", "flag", "std"):
            out.append(1.1)
        elif "ttm" in n:
            out.append(1.2)
        else:
            out.append(1.8)
    return out


def _plotly_desk_table(
    df: pd.DataFrame,
    *,
    flagged_rows: set[int] | None = None,
    gold_column: str | None = None,
    sigma_highlight_row: int | None = None,
    row_height: int | None = None,
) -> go.Figure:
    """
    Full-width desk table (Plotly go.Table). Dark desk UI with alternating row bands.
    """
    n = len(df)
    m = len(df.columns)
    if n == 0 or m == 0:
        return go.Figure().update_layout(
            paper_bgcolor=BG_APP, plot_bgcolor=BG_APP, height=80, margin=dict(l=8, r=8, t=8, b=8),
        )

    cols = list(df.columns)
    kv_pair = (
        m == 2
        and str(cols[0]).lower() == "key"
        and str(cols[1]).lower() == "value"
    )
    _line = dict(color=TABLE_GRID_LINE, width=1)

    values: list[list[str]] = []
    fills: list[list[str]] = []

    for j, col in enumerate(cols):
        col_vals: list[str] = []
        col_fill: list[str] = []
        for i in range(n):
            col_vals.append(_fmt_desk_cell(df.iloc[i, j]))
            if flagged_rows and i in flagged_rows:
                col_fill.append(TABLE_FLAGGED_BG)
            elif sigma_highlight_row is not None and i == sigma_highlight_row:
                col_fill.append(TABLE_SIGMA_BG)
            else:
                col_fill.append(TABLE_STRIPE_A if i % 2 == 0 else TABLE_STRIPE_B)
        values.append(col_vals)
        fills.append(col_fill)

    font_colors: list[list[str]] = []
    for col in cols:
        if gold_column and str(col) == gold_column:
            font_colors.append([GOLD] * n)
        elif kv_pair and str(col).lower() == "key":
            font_colors.append([TEXT_SEC] * n)
        else:
            font_colors.append([TEXT_PRI] * n)

    aligns: list[str] = []
    for col in cols:
        nl = str(col).lower()
        ser = df[col]
        if pd.api.types.is_numeric_dtype(ser):
            aligns.append("right")
        elif nl in ("price",) or "level" in nl or "dev" in nl or "threshold" in nl or "mid" in nl:
            aligns.append("right")
        elif "value" in nl:
            aligns.append("right" if pd.api.types.is_numeric_dtype(ser) else "left")
        else:
            aligns.append("left")

    row_h = row_height if row_height is not None else 30
    header_h = 34
    fig_h = min(520, header_h + n * row_h + 24)

    header_fill = [TABLE_HEADER_BG] * m

    _tbl_header_font = dict(
        color=TEXT_SEC, size=11, family="Inter, sans-serif", weight=400,
    )
    _tbl_cell_font = dict(
        color=font_colors, size=10, family="DM Mono, monospace", weight=400,
    )

    fig = go.Figure(
        data=[
            go.Table(
                columnwidth=_desk_table_col_widths(df),
                header=dict(
                    values=[str(c) for c in cols],
                    fill_color=header_fill,
                    font=_tbl_header_font,
                    align=aligns,
                    line=dict(color=TABLE_GRID_LINE, width=1),
                    height=header_h,
                ),
                cells=dict(
                    values=values,
                    fill_color=fills,
                    font=_tbl_cell_font,
                    align=aligns,
                    line=_line,
                    height=row_h,
                ),
            )
        ]
    )
    fig.update_layout(
        paper_bgcolor=BG_APP,
        plot_bgcolor=BG_APP,
        margin=dict(l=0, r=0, t=0, b=0),
        height=fig_h,
    )
    return fig


def desk_table_content_height_px(n_rows: int) -> int:
    return DESK_TABLE_HEADER_PX + max(0, n_rows) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX


def desk_table_viewport_height_px(fig: go.Figure, max_visible_rows: int | None) -> int:
    """Streamlit container height: cap tall tables so inner content scrolls."""
    raw = fig.layout.height
    full = int(raw) if raw is not None else 200
    if max_visible_rows is None:
        return full
    cap = desk_table_content_height_px(max_visible_rows)
    return min(full, cap)
