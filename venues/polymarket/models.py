from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PolymarketContract:
    venue: str
    market_id: str
    slug: str
    question: str
    release_month: str
    resolution_time: Optional[datetime]
    threshold: Optional[float]
    outcome: str
    outcome_price: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]
    mid: Optional[float]
    spread: Optional[float]
    volume: Optional[float]
    open_interest: Optional[float]
    liquidity_score: float
    confidence_score: float
    settlement_source: Optional[str]
    valuation_timestamp: datetime
    expected_value: Optional[float] = None
    publishable: bool = False
    publishability_reason: str = "unscored"
    last_updated: Optional[datetime] = None
    has_valid_quote: bool = True
    has_depth: bool = False
    depth_usd: Optional[float] = None
    quote_age_seconds: Optional[int] = None
    is_stale: bool = False
    raw: dict = field(default_factory=dict)


@dataclass
class PolyCurvePoint:
    label: str
    release_month: str
    implied_yoy: float
    lower_band: float
    upper_band: float
    prior_curve_yoy: Optional[float]
    volume: float
    open_interest: float
    spread_bp: Optional[float]
    confidence_score: float
    publishable: bool
    market_id: str


@dataclass
class PolyCurvePackage:
    valuation_timestamp: datetime
    points: list[PolyCurvePoint]
    contracts: list[PolymarketContract]
    source_status: str
    publishable: bool
    publishability_reason: str
    venue: str = "Polymarket"
    methodology: str = "v0.1.1-polymarket-live"
    sample_mode: bool = False
    venue_role: str = "Diagnostic / Supplemental Venue"
    venue_status: str = "insufficient"
    reference_status: str = "not_eligible"
    counts_toward_oriel_blend: bool = False
