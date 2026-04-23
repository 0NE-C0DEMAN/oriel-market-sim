from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class VenueQuote:
    venue: str
    release_month: str
    threshold: float
    bid: Optional[float]
    ask: Optional[float]
    mid: Optional[float]
    spread: Optional[float]
    volume: Optional[float]
    open_interest: Optional[float]
    quote_age_seconds: Optional[int]
    liquidity_score: float
    confidence_score: float
    market_id: str
    question: str
    source_status: str = "LIVE"
    raw_threshold: Optional[float] = None
    normalized_threshold: Optional[float] = None
    threshold_units: str = "yoy_pct"
    normalization_method: str = "pass_through"
    methodology_note: Optional[str] = None

@dataclass
class OrielFrontEndPoint:
    release_month: str
    venue: str
    implied_yoy: float
    confidence_score: float
    liquidity_score: float
    quote_age_seconds: Optional[int]
    market_id: str

@dataclass
class DislocationRow:
    release_month: str
    venue: str
    implied_yoy: float
    oriel_reference_yoy: float
    dislocation_bps: float
    confidence_score: float
    liquidity_score: float
    quote_age_seconds: Optional[int]
    market_id: str
