from __future__ import annotations
from dataclasses import dataclass, field
import os

@dataclass(frozen=True)
class HarnessConfig:
    kalshi_series_ticker: str = field(default_factory=lambda: os.getenv('KALSHI_CPI_SERIES_TICKER', 'KXCPI'))
    max_front_months: int = field(default_factory=lambda: int(os.getenv('ORIEL_SIM_MAX_FRONT_MONTHS', '4')))
    min_confidence: float = field(default_factory=lambda: float(os.getenv('ORIEL_SIM_MIN_CONFIDENCE', '0.10')))
    fallback_sample_csv: str = field(default_factory=lambda: os.getenv('ORIEL_SIM_SAMPLE_CSV', 'data/hyperliquid_mvp/sample_frontend_quotes.csv'))
    launch_notional_usd: float = field(default_factory=lambda: float(os.getenv('ORIEL_SIM_LAUNCH_NOTIONAL_USD', '3000000')))
    quote_size_usd: float = field(default_factory=lambda: float(os.getenv('ORIEL_SIM_QUOTE_SIZE_USD', '100000')))
    taker_clip_usd: float = field(default_factory=lambda: float(os.getenv('ORIEL_SIM_TAKER_CLIP_USD', '50000')))
    base_spread_bps: float = field(default_factory=lambda: float(os.getenv('ORIEL_SIM_BASE_SPREAD_BPS', '18')))
    inventory_limit_usd: float = field(default_factory=lambda: float(os.getenv('ORIEL_SIM_INVENTORY_LIMIT_USD', '750000')))
    maker_fee_bps: float = field(default_factory=lambda: float(os.getenv('ORIEL_SIM_MAKER_FEE_BPS', '0')))
    taker_fee_bps: float = field(default_factory=lambda: float(os.getenv('ORIEL_SIM_TAKER_FEE_BPS', '0')))
