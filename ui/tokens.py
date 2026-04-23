"""
ui/tokens.py — Oriel design tokens.

Single source of truth for all colors, radii, table dimensions, and toggle keys.
Every UI module imports from here. No circular dependencies.
"""
from __future__ import annotations

from pathlib import Path

# Project root (parent of ui/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Core palette ──────────────────────────────────────────────────────────────
BG_APP      = "#0B0F14"
BG_SURFACE  = "#121821"
BG_SURFACE2 = "#161f2b"
BG_ELEVATED = "#1b2532"
BG_HOVER    = "#202c3b"
BORDER      = "#223042"
BORDER_STR  = "#2c3b4d"
GRID        = "#2A3441"
GRID_SOFT   = "rgba(42,52,65,0.52)"
TEXT_PRI    = "#E6EDF3"
TEXT_SEC    = "#B0BEC9"
TEXT_MUTED  = "#8EA4B5"
GOLD        = "#D4A85A"
GOLD2       = "#b98a3d"
GOLD_LIGHT  = "#E8D4A8"
POSITIVE    = "#22C55E"
POSITIVE_MUTED = "#1CA84F"
NEGATIVE    = "#FF6B6B"
WARNING     = "#f59e0b"
INFO        = "#3B82F6"
SERIES2     = "#7aa2f7"
SERIES_MUTE = "#4b5b70"

# ── Radii ─────────────────────────────────────────────────────────────────────
RADIUS_SM = 8
RADIUS_MD = 10
RADIUS_LG = 12

# ── Table stripe / desk table ─────────────────────────────────────────────────
TABLE_STRIPE_A   = "#111820"
TABLE_STRIPE_B   = "#182131"
TABLE_HEADER_BG  = "#1b2634"
TABLE_GRID_LINE  = "rgba(34,48,66,0.5)"
TABLE_FLAGGED_BG = "rgba(245,158,11,0.15)"
TABLE_SIGMA_BG   = "#243348"

DESK_TABLE_HEADER_PX    = 34
DESK_TABLE_ROW_PX       = 30
DESK_TABLE_PAD_PX       = 16
DESK_TABLE_VIEWPORT_ROWS = 5
ORIEL_INDEX_TAB_CHART_HEIGHT_PX = 395

# ── Widget keys ───────────────────────────────────────────────────────────────
LIVE_TOGGLE_WIDGET_KEY = "live_toggle_cpi"
FX_LIVE_TOGGLE_KEY     = "forecastex_live_toggle"
POLY_LIVE_TOGGLE_KEY   = "polymarket_live_toggle"


def tokens_dict() -> dict[str, str | int]:
    """All design tokens as a flat dict for CSS template interpolation.

    Includes pre-computed expressions that the CSS template references by name
    (replacing inline f-string arithmetic).
    """
    return {
        "BG_APP": BG_APP,
        "BG_SURFACE": BG_SURFACE,
        "BG_SURFACE2": BG_SURFACE2,
        "BG_ELEVATED": BG_ELEVATED,
        "BG_HOVER": BG_HOVER,
        "BORDER": BORDER,
        "BORDER_STR": BORDER_STR,
        "GRID": GRID,
        "GRID_SOFT": GRID_SOFT,
        "TEXT_PRI": TEXT_PRI,
        "TEXT_SEC": TEXT_SEC,
        "TEXT_MUTED": TEXT_MUTED,
        "GOLD": GOLD,
        "GOLD2": GOLD2,
        "GOLD_LIGHT": GOLD_LIGHT,
        "POSITIVE": POSITIVE,
        "POSITIVE_MUTED": POSITIVE_MUTED,
        "NEGATIVE": NEGATIVE,
        "WARNING": WARNING,
        "INFO": INFO,
        "SERIES2": SERIES2,
        "SERIES_MUTE": SERIES_MUTE,
        "RADIUS_SM": RADIUS_SM,
        "RADIUS_MD": RADIUS_MD,
        "RADIUS_LG": RADIUS_LG,
        "TABLE_STRIPE_A": TABLE_STRIPE_A,
        "TABLE_STRIPE_B": TABLE_STRIPE_B,
        "TABLE_HEADER_BG": TABLE_HEADER_BG,
        "TABLE_GRID_LINE": TABLE_GRID_LINE,
        "TABLE_FLAGGED_BG": TABLE_FLAGGED_BG,
        "TABLE_SIGMA_BG": TABLE_SIGMA_BG,
        "DESK_TABLE_HEADER_PX": DESK_TABLE_HEADER_PX,
        "DESK_TABLE_ROW_PX": DESK_TABLE_ROW_PX,
        "DESK_TABLE_PAD_PX": DESK_TABLE_PAD_PX,
        # Pre-computed CSS expressions (replace inline arithmetic in oriel.css)
        "CSS_TBL_6ROW_13": DESK_TABLE_HEADER_PX + 6 * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX + 13,
        "CSS_TBL_3ROW_108": DESK_TABLE_HEADER_PX + 3 * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX + 108,
        "CSS_TBL_6ROW": DESK_TABLE_HEADER_PX + 6 * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX,
    }
