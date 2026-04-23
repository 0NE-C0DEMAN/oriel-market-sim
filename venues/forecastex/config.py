from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ForecastExConfig:
    """Runtime configuration for the ForecastEx live adapter.

    Notes:
    - ForecastEx publicly states that daily and intraday CSV files are available
      from its data page. The pairs feed is refreshed every 10 minutes.
    - Exact file URLs can be supplied directly through environment variables.
      If they are omitted, the client will attempt to discover CSV links from
      the data page HTML.
    """

    data_page_url: str = os.getenv("FORECASTEX_DATA_PAGE_URL", "https://forecastex.com/data")
    intraday_pairs_url: Optional[str] = os.getenv("FORECASTEX_INTRADAY_PAIRS_URL")
    daily_prices_url: Optional[str] = os.getenv("FORECASTEX_DAILY_PRICES_URL")
    daily_summary_url: Optional[str] = os.getenv("FORECASTEX_DAILY_SUMMARY_URL")
    request_timeout_seconds: int = int(os.getenv("FORECASTEX_REQUEST_TIMEOUT_SECONDS", "20"))
    max_curve_points: int = int(os.getenv("FORECASTEX_MAX_CURVE_POINTS", "6"))
    min_volume: int = int(os.getenv("FORECASTEX_MIN_VOLUME", "1"))
    min_open_interest: int = int(os.getenv("FORECASTEX_MIN_OPEN_INTEREST", "0"))  # pairs feed has no OI column
    stale_after_minutes: int = int(os.getenv("FORECASTEX_STALE_AFTER_MINUTES", "20"))
    allow_sample_fallback: bool = os.getenv("FORECASTEX_ALLOW_SAMPLE_FALLBACK", "true").lower() == "true"
    coupon_bps_adjustment: float = float(os.getenv("FORECASTEX_COUPON_BPS_ADJUSTMENT", "0.0"))


DEFAULT_CONFIG = ForecastExConfig()
