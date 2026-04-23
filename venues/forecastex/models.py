from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ForecastExContract:
    venue: str
    contract_id: str
    product_code: str
    event_question: str
    release_month: str
    resolution_time: Optional[datetime]
    threshold: Optional[float]
    side: Optional[str]
    bid: Optional[float]
    ask: Optional[float]
    last: Optional[float]
    mid: Optional[float]
    open_interest: Optional[int]
    volume: Optional[int]
    coupon_rate: Optional[float]
    settlement_source: Optional[str]
    valuation_timestamp: datetime
    expected_value: Optional[float] = None
    liquidity_score: float = 0.0
    publishable: bool = False
    publishability_reason: str = "unscored"
    raw: dict = field(default_factory=dict)


@dataclass
class CurvePoint:
    label: str
    release_month: str
    implied_yoy: float
    lower_band: float
    upper_band: float
    prior_curve_yoy: Optional[float]
    volume: int
    open_interest: int
    publishable: bool


@dataclass
class CurvePackage:
    valuation_timestamp: datetime
    points: list[CurvePoint]
    source_status: str
    publishable: bool
    publishability_reason: str
    venue: str = "ForecastEx"
    methodology: str = "v0.3.0-forecastex-live"
    sample_mode: bool = False
