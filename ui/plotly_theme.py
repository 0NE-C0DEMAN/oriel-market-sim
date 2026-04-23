"""
ui/plotly_theme.py — Plotly template and config for the Oriel institutional theme.
"""
from __future__ import annotations

from ui.tokens import (
    BG_ELEVATED, BG_SURFACE, BORDER, GRID_SOFT, TEXT_PRI, TEXT_SEC,
)

ORIEL_TEMPLATE = {
    "layout": {
        "paper_bgcolor": BG_SURFACE,
        "plot_bgcolor":  BG_SURFACE,
        "font": {"family": "Inter, DM Sans, sans-serif", "color": TEXT_PRI, "size": 12},
        "xaxis": {
            "showgrid": True, "gridcolor": GRID_SOFT, "gridwidth": 1,
            "linecolor": BORDER, "tickcolor": BORDER,
            "zeroline": False,
            "tickfont": {"color": TEXT_SEC},
        },
        "yaxis": {
            "showgrid": True, "gridcolor": GRID_SOFT, "gridwidth": 1,
            "linecolor": BORDER, "tickcolor": BORDER,
            "zeroline": False,
            "tickfont": {"color": TEXT_SEC},
        },
        "legend": {
            "orientation": "h", "yanchor": "bottom", "y": 1.02,
            "xanchor": "right", "x": 1,
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"color": TEXT_SEC},
        },
        "margin": {"l": 56, "r": 24, "t": 28, "b": 48},
        "hoverlabel": {
            "bgcolor": BG_ELEVATED,
            "bordercolor": "rgba(212,168,90,0.35)",
            "font": {"color": TEXT_PRI, "family": "Inter, DM Mono, monospace", "size": 12},
        },
    }
}

PLOTLY_CONFIG = {"displayModeBar": False, "displaylogo": False, "scrollZoom": False}


def apply_oriel_theme(fig) -> None:
    """Apply the Oriel dark theme to an existing Plotly figure."""
    fig.update_layout(
        paper_bgcolor=BG_SURFACE,
        plot_bgcolor=BG_SURFACE,
        font=dict(family="Inter, DM Sans, sans-serif", color=TEXT_PRI, size=12),
        xaxis=dict(showgrid=True, gridcolor=GRID_SOFT, linecolor=BORDER, tickcolor=BORDER,
                   zeroline=False, tickfont=dict(color=TEXT_SEC)),
        yaxis=dict(showgrid=True, gridcolor=GRID_SOFT, linecolor=BORDER, tickcolor=BORDER,
                   zeroline=False, tickfont=dict(color=TEXT_SEC)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_SEC)),
        hoverlabel=dict(bgcolor=BG_ELEVATED, bordercolor="rgba(212,168,90,0.35)",
                        font=dict(color=TEXT_PRI, size=12)),
        margin=dict(l=56, r=24, t=36, b=48),
    )
