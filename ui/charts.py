"""
ui/charts.py — Shared chart builders for the Oriel institutional theme.

Contains: axis helpers, forward curve builder, distribution chart builder,
bucket parsers, skewness calculator, and maturity label formatter.
"""
from __future__ import annotations

import math
import re

import pandas as pd
import plotly.graph_objects as go

from ui.tokens import (
    BG_APP, BG_ELEVATED, BG_SURFACE, BORDER, BORDER_STR,
    GOLD, GOLD_LIGHT, GRID_SOFT, POSITIVE_MUTED, SERIES_MUTE,
    TEXT_PRI, TEXT_SEC, TEXT_MUTED,
    ORIEL_INDEX_TAB_CHART_HEIGHT_PX,
)

def _prior_curve_demo(evs: list) -> list:
    """Simulate a prior-day curve by shifting current values slightly."""
    import random
    random.seed(42)
    return [round(v * (1 + random.uniform(-0.012, 0.008)), 4) for v in evs]


# ── Shared axis styles (no spreading, no conflicts) ───────────────────────────
def _xaxis(**kwargs):
    base = dict(showgrid=True, gridwidth=1, gridcolor=GRID_SOFT, linecolor=BORDER, tickcolor=BORDER,
                zeroline=False, tickfont=dict(color=TEXT_SEC))
    base.update(kwargs)
    return base

def _yaxis(**kwargs):
    base = dict(showgrid=True, gridwidth=1, gridcolor=GRID_SOFT, linecolor=BORDER, tickcolor=BORDER,
                zeroline=False, tickfont=dict(color=TEXT_SEC))
    base.update(kwargs)
    return base

def _layout(**kwargs):
    base = dict(
        paper_bgcolor=BG_SURFACE, plot_bgcolor=BG_SURFACE,
        font=dict(family="Inter, DM Sans, sans-serif", color=TEXT_PRI, size=12),
        margin=dict(l=60, r=28, t=28, b=58),
        hoverlabel=dict(bgcolor=BG_ELEVATED, bordercolor=BORDER_STR,
                        font=dict(color=TEXT_PRI, family="Inter, DM Mono, monospace")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, bgcolor="rgba(0,0,0,0)",
                    font=dict(color=TEXT_SEC)),
    )
    base.update(kwargs)
    return base


def _parse_bucket_mid(label: str) -> float | None:
    """Approximate numeric center of a bucket label for EV/skew alignment."""
    s = label.replace("–", "-").strip()
    try:
        if s.startswith("<"):
            m = re.search(r"([\d.]+)", s)
            return float(m.group(1)) - 0.25 if m else None
        if s.startswith(">"):
            m = re.search(r"([\d.]+)", s)
            return float(m.group(1)) + 0.25 if m else None
        if "-" in s:
            parts = re.split(r"-", s, 1)
            nums = []
            for part in parts:
                mm = re.search(r"([\d.]+)", part)
                if mm:
                    nums.append(float(mm.group(1)))
            if len(nums) >= 2:
                return (nums[0] + nums[1]) / 2.0
        m = re.search(r"([\d.]+)", s)
        return float(m.group(1)) if m else None
    except (ValueError, TypeError):
        return None


def _parse_bucket_edges(label: str) -> tuple[float, float] | None:
    """Return (low, high) inclusive-ish range for bar width on a linear x-axis.

    Handles positive ranges ("0.4-0.5%"), negative ranges ("-0.1-0.0%",
    "-0.2--0.1%"), and open-ended overflow buckets ("<-0.1%", ">1.0%").
    """
    s = label.replace("–", "-").replace("—", "-").strip()
    try:
        if s.startswith("<"):
            m = re.search(r"(-?\d+\.?\d*)", s[1:])
            if m:
                hi = float(m.group(1))
                return (hi - 0.1, hi)
            return None
        if s.startswith(">"):
            m = re.search(r"(-?\d+\.?\d*)", s[1:])
            if m:
                lo = float(m.group(1))
                return (lo, lo + 0.1)
            return None
        # Match "a-b%" including cases where a and/or b are negative
        # First group greedily matches an optional leading minus + number
        m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*%?\s*$", s)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            return (min(a, b), max(a, b))
        return None
    except (ValueError, TypeError):
        return None


def _discrete_skewness(mids: list[float], probs: list[float]) -> float | None:
    """Pearson skewness for a discrete distribution (probs sum to 1)."""
    if not mids or len(mids) != len(probs):
        return None
    sp = sum(probs)
    if sp <= 0:
        return None
    p = [x / sp for x in probs]
    mu = sum(mi * pi for mi, pi in zip(mids, p))
    var = sum(pi * (mi - mu) ** 2 for mi, pi in zip(mids, p))
    if var <= 1e-14:
        return None
    sd = math.sqrt(var)
    return sum(pi * ((mi - mu) / sd) ** 3 for mi, pi in zip(mids, p))


# ── Chart builders ─────────────────────────────────────────────────────────────
def make_forward_curve(
    mats, evs, stds, y_label, show_prior=True, *, stretch=False, chart_height: int | None = None
):
    fig = go.Figure()

    y_hi = [e + s for e, s in zip(evs, stds)]
    y_lo = [e - s for e, s in zip(evs, stds)]
    y_mid = list(evs)

    # Two-layer ±σ fill: subtle transparent-gold gradient (stronger toward tails, softer at EV)
    fig.add_trace(go.Scatter(
        x=list(mats) + list(mats[::-1]),
        y=y_lo + y_mid[::-1],
        fill="toself", fillcolor="rgba(212,168,90,0.16)",
        line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip", showlegend=True, name="±1σ Band",
    ))
    fig.add_trace(go.Scatter(
        x=list(mats) + list(mats[::-1]),
        y=y_mid + y_hi[::-1],
        fill="toself", fillcolor="rgba(212,168,90,0.10)",
        line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip", showlegend=False, name="_band_hi",
    ))

    if show_prior:
        y_prev = _prior_curve_demo(list(evs))
        fig.add_trace(go.Scatter(
            x=mats, y=y_prev, mode="lines",
            name="Prior Curve (T-1)",
            line=dict(color=SERIES_MUTE, width=1.5, dash="dash"),
            hovertemplate="<b>%{x|%b %Y}</b><br>Prior: %{y:.4f}%<extra></extra>",
        ))

    # Glow — soft halo behind sharp markers
    fig.add_trace(go.Scatter(
        x=mats, y=evs, mode="markers",
        marker=dict(size=20, color="rgba(212,168,90,0.22)", line=dict(width=0)),
        hoverinfo="skip", showlegend=False, name="_glow",
    ))
    fig.add_trace(go.Scatter(
        x=mats, y=evs, mode="lines+markers",
        name="Expected Value",
        line=dict(color=GOLD, width=2.5),
        marker=dict(
            size=6, color=GOLD,
            line=dict(color=BG_APP, width=1.5),
            symbol="circle",
        ),
        hovertemplate="<b>%{x|%b %Y}</b><br>Expected: <b>%{y:.4f}%</b><extra></extra>",
    ))

    _single = len(list(mats)) == 1
    if _single:
        # Single-point: draw a horizontal reference line so it reads as an anchor, not a stray dot
        fig.add_hline(
            y=float(evs[0]), line_width=1.2, line_dash="dot",
            line_color="rgba(212,168,90,0.45)",
        )
        fig.add_annotation(
            x=list(mats)[0], y=float(evs[0]),
            text=f"  {float(evs[0]):.4f}%",
            showarrow=False, xanchor="left",
            font=dict(color=GOLD, size=12, family="DM Mono, monospace"),
        )
        # Larger marker for single-point view
        fig.data[-1].update(marker=dict(size=12, color=GOLD, line=dict(color=BG_APP, width=2)))
        x_pad = pd.Timedelta(days=45)
    else:
        x_pad = pd.Timedelta(days=10)

    _curve_layout = dict(
        margin=dict(l=52, r=12, t=28, b=48),
        xaxis=_xaxis(
            tickformat="%b %Y", tickmode="array",
            tickvals=list(mats),
            ticktext=[m.strftime("%b %Y") for m in mats],
            range=[mats.min() - x_pad, mats.max() + x_pad],
        ),
        yaxis=_yaxis(title=dict(text=y_label, font=dict(color=TEXT_SEC, size=11))),
    )
    _h = chart_height if chart_height is not None else 322
    if stretch:
        fig.update_layout(**_layout(autosize=True, **_curve_layout))
    else:
        fig.update_layout(**_layout(height=_h, **_curve_layout))
    return fig


def make_distribution(
    dlabels, dprobs, expected_value=None, *, stretch=False, chart_height: int | None = None
):
    # Linear x = bucket position so EV vline can sit at exact numeric value (e.g. 4.08)
    rows: list[tuple[float, float, float, str]] = []
    for lb, p in zip(dlabels or [], dprobs or []):
        e = _parse_bucket_edges(lb)
        if e:
            lo, hi = e[0], e[1]
            xc = (lo + hi) / 2.0
            w = max(hi - lo, 0.05)
        else:
            mid = _parse_bucket_mid(lb)
            xc = float(mid) if mid is not None else 0.0
            w = 0.5
        rows.append((xc, w, float(p), lb))
    rows.sort(key=lambda r: r[0])
    if not rows:
        fig = go.Figure()
        _empty_h = chart_height if chart_height is not None else 322
        fig.update_layout(
            **_layout(
                height=_empty_h,
                margin=dict(l=52, r=12, t=40, b=48),
                paper_bgcolor=BG_SURFACE,
                plot_bgcolor=BG_SURFACE,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
            )
        )
        return fig
    xs = [r[0] for r in rows]
    widths = [r[1] for r in rows]
    dprobs = [r[2] for r in rows]
    dlabels = [r[3] for r in rows]

    mx = max(dprobs) if dprobs else 1.0
    # Keep the existing color scheme (GOLD for peak, SERIES_MUTE for others), but
    # apply a soft transparent fill with a solid outline — matches the CMS / OTC
    # Parity bar treatment for a unified institutional look.
    _peak_fill = "rgba(212,168,90,0.55)"   # GOLD with alpha
    _other_fill = "rgba(75,91,112,0.55)"   # SERIES_MUTE with alpha
    fill_colors = [_peak_fill if p == mx else _other_fill for p in dprobs]
    line_colors = [GOLD if p == mx else SERIES_MUTE for p in dprobs]

    n_bars = len(xs)
    # More buckets → wider visual gap + thinner strokes so bars do not become a solid slab
    _bar_gap = 0.14 if n_bars <= 10 else min(0.38, 0.14 + 0.028 * (n_bars - 10))
    _min_w = 0.028 if n_bars > 16 else 0.04
    widths = [max(w * (1.0 - _bar_gap), _min_w) for w in widths]
    _bar_line_w = 1.2 if n_bars <= 12 else (0.9 if n_bars <= 20 else 0.6)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=xs,
        y=dprobs,
        width=widths,
        customdata=dlabels,
        marker=dict(color=fill_colors, line=dict(color=line_colors, width=_bar_line_w)),
        hovertemplate="<b>%{customdata}</b><br>Probability: <b>%{y:.1f}%</b><extra></extra>",
        name="Probability",
    ))

    annotations = []
    mids = [_parse_bucket_mid(l) for l in dlabels] if dlabels else []
    if mids and all(m is not None for m in mids) and dprobs:
        pfrac = [p / 100.0 for p in dprobs]
        sk = _discrete_skewness([m for m in mids], pfrac)
        if sk is not None:
            annotations.append(dict(
                text=f"Skew {sk:+.2f}",
                xref="paper", yref="paper", x=0.99, y=0.98,
                xanchor="right", yanchor="top", showarrow=False,
                font=dict(size=10, color=TEXT_SEC),
            ))

    x_lo = min(x - w / 2 for x, w in zip(xs, widths)) if xs else 0.0
    x_hi = max(x + w / 2 for x, w in zip(xs, widths)) if xs else 1.0
    if expected_value is not None:
        x_lo = min(x_lo, expected_value)
        x_hi = max(x_hi, expected_value)
    pad = max(0.02 * (x_hi - x_lo), 0.05)

    # X ticks: show every bar when few; subsample when many (hover still has full label via customdata)
    _max_ticks = 13
    if n_bars <= _max_ticks:
        tick_x, tick_lbl = list(xs), list(dlabels)
    else:
        step = max(1, (n_bars + _max_ticks - 1) // _max_ticks)
        idxs = list(range(0, n_bars, step))
        if idxs[-1] != n_bars - 1:
            idxs.append(n_bars - 1)
        tick_x = [xs[i] for i in idxs]
        tick_lbl = [dlabels[i] for i in idxs]
    _tick_angle = 0 if n_bars <= 8 else (-32 if n_bars <= 14 else -48)
    _tick_fs = 11 if n_bars <= 12 else (10 if n_bars <= 20 else 9)
    _b_margin = 50 + (28 if _tick_angle else 0) + (10 if n_bars > 16 else 0)
    _plot_h = 220 if n_bars <= 14 else min(280, 220 + int((n_bars - 14) * 2.2))

    if expected_value is not None and dlabels and dprobs and xs:
        y_top = mx * 1.12 if mx else 1.0
        x_ev = float(expected_value)
        fig.add_shape(
            type="line",
            x0=x_ev,
            x1=x_ev,
            y0=0,
            y1=y_top,
            xref="x",
            yref="y",
            line=dict(color=GOLD_LIGHT, width=2, dash="dot"),
            layer="above",
        )
        # Two-line EV label (no box): subtitle + modest % — % color ties to guide, not peak gold
        _ev_common = dict(
            x=x_ev,
            xref="x",
            y=y_top,
            yref="y",
            showarrow=False,
            xanchor="center",
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            borderpad=0,
        )
        annotations.append(
            dict(
                **_ev_common,
                text="Expected Value (EV)",
                yshift=44,
                font=dict(size=11, color=TEXT_SEC, family="Inter, sans-serif"),
            )
        )
        annotations.append(
            dict(
                **_ev_common,
                text=f"<b>{expected_value:.2f}%</b>",
                yshift=20,
                font=dict(size=14, color=GOLD_LIGHT, family="Inter, sans-serif"),
            )
        )

    _dist_layout = dict(
        bargap=0.14,
        margin=dict(l=52, r=12, t=40, b=_b_margin),
        showlegend=False,
        annotations=annotations or None,
        xaxis=_xaxis(
            showgrid=False,
            type="linear",
            tickmode="array",
            tickvals=tick_x,
            ticktext=tick_lbl,
            range=[x_lo - pad, x_hi + pad],
            tickangle=_tick_angle,
            automargin=True,
            tickfont=dict(size=_tick_fs, color=TEXT_SEC),
        ),
        yaxis=_yaxis(
            title=dict(text="Probability (%)", font=dict(color=TEXT_SEC, size=11)),
            ticksuffix="%",
        ),
    )
    _h = chart_height if chart_height is not None else _plot_h
    if stretch:
        fig.update_layout(**_layout(autosize=True, **_dist_layout))
    else:
        fig.update_layout(**_layout(height=_h, **_dist_layout))
    return fig


def _maturity_label(m) -> str:
    if hasattr(m, "strftime"):
        return m.strftime("%b %Y")
    return str(m)

