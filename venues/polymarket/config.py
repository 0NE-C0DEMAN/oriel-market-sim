from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PolymarketConfig:
    gamma_api_url: str = os.getenv("POLYMARKET_GAMMA_API_URL", "https://gamma-api.polymarket.com")
    data_api_url: str = os.getenv("POLYMARKET_DATA_API_URL", "https://data-api.polymarket.com")
    request_timeout_seconds: int = int(os.getenv("POLYMARKET_REQUEST_TIMEOUT_SECONDS", "20"))
    max_markets_scan: int = int(os.getenv("POLYMARKET_MAX_MARKETS_SCAN", "250"))
    max_curve_points: int = int(os.getenv("POLYMARKET_MAX_CURVE_POINTS", "6"))

    # Discovery / parsing
    macro_indicators_tag_id: int = int(os.getenv("POLYMARKET_MACRO_INDICATORS_TAG_ID", "102000"))
    exclude_country_keywords: tuple[str, ...] = (
        "argentina",
        "canada",
        "uk",
        "united kingdom",
        "britain",
        "eurozone",
        "euro zone",
        "china",
        "japan",
        "australia",
        "mexico",
        "brazil",
        "france",
        "germany",
        "india",
        "turkey",
        "korea",
        "south africa",
        "nigeria",
        "colombia",
    )
    cpi_search_terms: tuple[str, ...] = (
        "cpi",
        "inflation",
        "consumer price index",
    )

    # Render gates for diagnostic venue tab
    min_maturities_render: int = int(os.getenv("POLYMARKET_MIN_MATURITIES_RENDER", "2"))
    max_spread_bp_render: float = float(os.getenv("POLYMARKET_MAX_SPREAD_BP_RENDER", "500"))
    preferred_spread_bp: float = float(os.getenv("POLYMARKET_PREFERRED_SPREAD_BP", "250"))

    # Official publication gates
    min_maturities_publish: int = int(os.getenv("POLYMARKET_MIN_MATURITIES_PUBLISH", "4"))
    max_spread_bp_publish: float = float(os.getenv("POLYMARKET_MAX_SPREAD_BP_PUBLISH", "150"))
    counts_toward_oriel_blend: bool = os.getenv("POLYMARKET_COUNTS_TOWARD_ORIEL_BLEND", "false").lower() == "true"

    # Hygiene / operational gates
    min_volume: float = float(os.getenv("POLYMARKET_MIN_VOLUME", "25"))
    min_open_interest: float = float(os.getenv("POLYMARKET_MIN_OPEN_INTEREST", "25"))
    min_depth_required: bool = os.getenv("POLYMARKET_MIN_DEPTH_REQUIRED", "false").lower() == "true"
    max_quote_age_seconds: int = int(os.getenv("POLYMARKET_MAX_QUOTE_AGE_SECONDS", "900"))
    stale_after_hours: int = int(os.getenv("POLYMARKET_STALE_AFTER_HOURS", "36"))
    allow_sample_fallback: bool = os.getenv("POLYMARKET_ALLOW_SAMPLE_FALLBACK", "true").lower() == "true"
    require_active: bool = os.getenv("POLYMARKET_REQUIRE_ACTIVE", "true").lower() == "true"

    # Legacy compatibility alias used by earlier scoring paths
    max_spread_bp: float = float(os.getenv("POLYMARKET_MAX_SPREAD_BP", "500"))

    # Confidence scoring weights
    weight_spread: float = float(os.getenv("POLYMARKET_WEIGHT_SPREAD", "0.45"))
    weight_depth: float = float(os.getenv("POLYMARKET_WEIGHT_DEPTH", "0.15"))
    weight_freshness: float = float(os.getenv("POLYMARKET_WEIGHT_FRESHNESS", "0.20"))
    weight_maturity: float = float(os.getenv("POLYMARKET_WEIGHT_MATURITY", "0.20"))


DEFAULT_CONFIG = PolymarketConfig()
