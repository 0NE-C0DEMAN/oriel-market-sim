from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math
import pandas as pd


@dataclass(frozen=True)
class ScaleTraderTicket:
    """Illustrative ScaleTrader-style ticket derived from a dislocation row.

    This module deliberately does not route orders. It translates the existing
    Oriel dislocation row into UI-ready ladder parameters for demo purposes.
    """

    selected_venue_contract: str
    venue: str
    release_month: str
    side: str
    oriel_fair_value: float
    contract_market_price: float
    liquidity_score: float
    confidence_score: float
    start_price: float
    increment: float
    levels: int
    clip_size: int
    max_exposure: int
    profit_taker_offset: float
    disable_conditions: str
    edge_probability_points: float


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _round_to_cent(value: float) -> float:
    return round(_clamp(value, 0.01, 0.99), 2)


def generate_scaletrader_ticket(
    row: pd.Series | dict[str, Any],
    *,
    max_position: int = 2_000,
    target_ladder_depth: int = 8,
) -> ScaleTraderTicket:
    """Generate an illustrative ScaleTrader ticket from one dislocation row.

    Direction convention:
      - Negative dislocation means the venue-implied CPI level is below Oriel FV,
        so the CPI-above/YES contract is treated as cheap -> Buy YES.
      - Positive dislocation means the contract is rich to Oriel FV -> Sell YES.

    Price convention:
      - Uses the row's binary-contract mid when available; falls back to 0.50.
      - Keeps prices in dollars/probability space (0.01 to 0.99), matching the
        ForecastTrader / binary contract UI convention used elsewhere in the demo.
    """

    data = dict(row)
    venue = str(data.get("venue", "—"))
    release_month = str(data.get("release_month", "—"))
    market_id = str(data.get("market_id", "—"))
    selected = f"{venue} · {release_month} · {market_id}"

    oriel_fv = _as_float(data.get("oriel_reference_yoy"))
    market_implied = _as_float(data.get("implied_yoy"))
    dislocation_bps = _as_float(data.get("dislocation_bps"), (market_implied - oriel_fv) * 100.0)
    edge_pp = abs(dislocation_bps) / 100.0

    market_price = _as_float(data.get("mid"), 0.50)
    if market_price > 1.0:
        market_price = market_price / 100.0
    market_price = _clamp(market_price, 0.01, 0.99)

    liquidity = _clamp(_as_float(data.get("liquidity_score"), 0.50), 0.0, 1.0)
    confidence = _clamp(_as_float(data.get("confidence_score"), 0.50), 0.0, 1.0)

    levels = int(_clamp(float(target_ladder_depth), 3.0, 20.0))
    max_position = max(1, int(max_position))

    # Confidence/liquidity controls the aggressiveness of the initial ladder.
    increment = 0.01 if liquidity >= 0.65 else 0.02
    clip_size = max(1, int(math.floor(max_position / levels)))
    max_exposure = clip_size * levels

    if dislocation_bps < 0:
        side = "Buy YES"
        # Start around current market, slightly less aggressive when confidence is weak.
        start_price = market_price if confidence >= 0.55 else market_price - increment
        profit_taker_offset = 0.03 if edge_pp >= 0.05 else 0.02
    else:
        side = "Sell YES"
        start_price = market_price if confidence >= 0.55 else market_price + increment
        profit_taker_offset = -0.03 if edge_pp >= 0.05 else -0.02

    # Avoid ladders that would immediately run out of binary contract bounds.
    if side == "Buy YES":
        start_price = _round_to_cent(start_price)
        max_start = 0.99 - increment * max(levels - 1, 0)
        start_price = _round_to_cent(min(start_price, max_start))
    else:
        start_price = _round_to_cent(start_price)
        min_start = 0.01 + increment * max(levels - 1, 0)
        start_price = _round_to_cent(max(start_price, min_start))

    disable_conditions = (
        "Disable if Oriel edge < 2.0pp, confidence < 55%, "
        "liquidity < 35%, or the selected contract is within print-lockout window."
    )

    return ScaleTraderTicket(
        selected_venue_contract=selected,
        venue=venue,
        release_month=release_month,
        side=side,
        oriel_fair_value=oriel_fv,
        contract_market_price=market_price,
        liquidity_score=liquidity,
        confidence_score=confidence,
        start_price=start_price,
        increment=increment,
        levels=levels,
        clip_size=clip_size,
        max_exposure=max_exposure,
        profit_taker_offset=round(profit_taker_offset, 2),
        disable_conditions=disable_conditions,
        edge_probability_points=edge_pp,
    )
