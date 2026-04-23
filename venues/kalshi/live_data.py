"""
phase2_live_data.py — Kalshi CPI market → engine MaturitySnapshot transformation.

Sole transformation layer. No UI logic here.
All Kalshi parsing, quote selection, liquidity filtering, and maturity grouping lives here.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional, Tuple

from engine import (
    BinaryThresholdContract,
    ContractObservation,
    ExactOutcomeContract,
    IndexMethodology,
    MaturitySnapshot,
    PriceSelection,
)
from .client import KalshiAPIError, KalshiPublicClient

logger = logging.getLogger(__name__)

# ── Defaults (all overridable via env / .env) ─────────────────────────────────

DEFAULT_CPI_SERIES_TICKER     = os.getenv("KALSHI_CPI_SERIES_TICKER", "KXCPI")
DEFAULT_PRICE_MODE            = os.getenv("KALSHI_PRICE_MODE", "mid")
DEFAULT_OPEN_INTEREST_MIN     = float(os.getenv("KALSHI_MIN_OPEN_INTEREST", "25"))
DEFAULT_VOLUME_MIN            = float(os.getenv("KALSHI_MIN_VOLUME", "10"))
DEFAULT_MAX_WIDE_SPREAD       = float(os.getenv("KALSHI_MAX_WIDE_SPREAD", "0.20"))
DEFAULT_MIN_CONTRACTS         = int(os.getenv("KALSHI_MIN_CONTRACTS_PER_MATURITY", "2"))
DEFAULT_CACHE_SECONDS         = int(os.getenv("KALSHI_CACHE_SECONDS", "60"))
DEFAULT_MAX_MATURITIES        = int(os.getenv("KALSHI_MAX_MATURITIES", "6"))


@dataclass(frozen=True)
class LiveFeedConfig:
    series_ticker: str             = field(default_factory=lambda: DEFAULT_CPI_SERIES_TICKER)
    price_mode: str                = field(default_factory=lambda: DEFAULT_PRICE_MODE)
    min_open_interest: float       = field(default_factory=lambda: DEFAULT_OPEN_INTEREST_MIN)
    min_volume: float              = field(default_factory=lambda: DEFAULT_VOLUME_MIN)
    max_wide_spread: float         = field(default_factory=lambda: DEFAULT_MAX_WIDE_SPREAD)
    min_contracts_per_maturity: int = field(default_factory=lambda: DEFAULT_MIN_CONTRACTS)
    max_maturities: int            = field(default_factory=lambda: DEFAULT_MAX_MATURITIES)


# ── Month name lookup ─────────────────────────────────────────────────────────

_MONTH_MAP: Dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


# ── Date helpers ──────────────────────────────────────────────────────────────

def _first_of_month(year: int, month: int) -> date:
    return date(year, month, 1)


def _shift_month(d: date, months: int) -> date:
    """Shift a date by N months, returning the 1st of the target month."""
    total = d.month - 1 + months
    year  = d.year + total // 12
    month = total % 12 + 1
    return date(year, month, 1)


def _parse_date(v: Any) -> Optional[date]:
    if not v:
        return None
    text = str(v).replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(text[:19], fmt[:len(text[:19])]).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text).date()
    except Exception:
        return None


def _coalesce(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── Reference month extraction ────────────────────────────────────────────────

def _extract_reference_cpi_month(market: Dict[str, Any]) -> Optional[date]:
    """
    Extract the CPI *reference* month (not the release/expiry month).

    Priority:
    1. Explicit month-year tokens in ticker / title / subtitle / event fields
    2. strike_date / reference_month explicit fields
    3. Release-date heuristic: CPI for month M is released in month M+1,
       so expiry date maps to prior month.
    """
    event = market.get("event") or {}

    text_fields = [
        str(market.get(k, ""))
        for k in ("ticker", "event_ticker", "title", "subtitle", "rulebook_variables")
    ]
    text_fields += [
        str(event.get(k, ""))
        for k in ("ticker", "event_ticker", "title", "subtitle", "rulebook_variables")
    ]
    blob = " | ".join(text_fields)

    # Patterns in priority order
    patterns = [
        r"(?<!\d)(20\d{2})[-/ ]?(0[1-9]|1[0-2])(?!\d)",             # 2026-04, 202604
        r"(?<!\d)(20\d{2})[-/ ]?([A-Za-z]{3,9})(?![A-Za-z])",       # 2026APR, 2026 April
        r"(?<![A-Za-z])([A-Za-z]{3,9})[-/ ]?(20\d{2})(?!\d)",       # APR2026, April 2026
        r"(?<!\d)(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)(?![A-Za-z])",  # 26APR
        r"(?<![A-Za-z])(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)[-/ ]?(\d{2})(?!\d)",  # APR26
    ]

    for pat in patterns:
        for m in re.finditer(pat, blob, flags=re.IGNORECASE):
            a, b = m.group(1), m.group(2)
            if a.isdigit() and len(a) == 4 and b.isdigit():
                return _first_of_month(int(a), int(b))
            if a.isdigit() and len(a) == 4:
                mo = _MONTH_MAP.get(b.lower())
                if mo:
                    return _first_of_month(int(a), mo)
            if b.isdigit() and len(b) == 4:
                mo = _MONTH_MAP.get(a.lower())
                if mo:
                    return _first_of_month(int(b), mo)
            if len(a) == 2 and a.isdigit():
                mo = _MONTH_MAP.get(b.lower())
                if mo:
                    return _first_of_month(2000 + int(a), mo)
            if len(b) == 2 and b.isdigit():
                mo = _MONTH_MAP.get(a.lower())
                if mo:
                    return _first_of_month(2000 + int(b), mo)

    # Explicit date fields
    for src in (market, event):
        for key in ("strike_date", "reference_month", "reference_date"):
            parsed = _parse_date(src.get(key))
            if parsed:
                return _first_of_month(parsed.year, parsed.month)

    # Release-date heuristic: expiry month → prior CPI month
    for key in ("expiration_time", "close_time", "settlement_time", "settlement_ts", "expiration_date"):
        parsed = _parse_date(market.get(key))
        if parsed:
            return _shift_month(_first_of_month(parsed.year, parsed.month), -1)
    for key in ("settlement_time", "expiration_time"):
        parsed = _parse_date(event.get(key))
        if parsed:
            return _shift_month(_first_of_month(parsed.year, parsed.month), -1)

    return None


# ── Strike value extraction ───────────────────────────────────────────────────

def _extract_value_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1))
    return None


def _extract_strike_value(market: Dict[str, Any]) -> Optional[float]:
    strike = market.get("strike")
    if isinstance(strike, dict):
        for key in ("value", "value_dollars", "strike_price", "floor_strike", "cap_strike"):
            val = _to_float(strike.get(key))
            if val is not None:
                return val

    custom = market.get("custom_strike")
    if isinstance(custom, dict):
        for val in custom.values():
            fv = _to_float(val)
            if fv is not None:
                return fv

    for key in ("subtitle", "title", "rulebook_variables"):
        val = _extract_value_from_text(str(market.get(key, "")))
        if val is not None:
            return val

    return None


# ── Quote selection ───────────────────────────────────────────────────────────

def _best_yes_bid(market: Dict[str, Any]) -> Optional[float]:
    return _to_float(_coalesce(market.get("yes_bid_dollars"), market.get("yes_bid")))


def _best_yes_ask(market: Dict[str, Any]) -> Optional[float]:
    return _to_float(_coalesce(market.get("yes_ask_dollars"), market.get("yes_ask")))


def _last_trade_price(market: Dict[str, Any]) -> Optional[float]:
    return _to_float(_coalesce(
        market.get("last_price_dollars"),
        market.get("last_price"),
        market.get("previous_price_dollars"),
    ))


def _choose_probability(
    market: Dict[str, Any],
    *,
    price_mode: str,
) -> Tuple[Optional[float], PriceSelection]:
    """
    Quote selection waterfall:
    1. YES mid (bid+ask)/2          — preferred, tightest spread
    2. Synthetic mid via NO side    — when only one side has both legs
    3. Last trade price             — stale but usable
    4. YES bid alone                — floor fallback
    5. None                         — excluded

    Returns (probability, PriceSelection).
    """
    yes_bid = _best_yes_bid(market)
    yes_ask = _best_yes_ask(market)
    no_bid  = _to_float(_coalesce(market.get("no_bid_dollars"), market.get("no_bid")))
    no_ask  = _to_float(_coalesce(market.get("no_ask_dollars"), market.get("no_ask")))
    last    = _last_trade_price(market)

    # 1. YES mid
    if yes_bid is not None and yes_ask is not None and yes_ask >= yes_bid:
        mid = (yes_bid + yes_ask) / 2.0
        chosen = yes_bid if price_mode == "bid" else yes_ask if price_mode == "ask" else mid
        reason = f"yes_{price_mode}"
        return chosen, PriceSelection(chosen_price=chosen, chosen_price_reason=reason,
                                      bid=yes_bid, ask=yes_ask, last=last)

    # 2. Synthetic mid via NO side
    if yes_bid is not None and no_bid is not None:
        synthetic = (yes_bid + (1.0 - no_bid)) / 2.0
        return synthetic, PriceSelection(chosen_price=synthetic,
                                         chosen_price_reason="cross_side_synthetic_mid",
                                         bid=yes_bid, ask=(1.0 - no_bid), last=last)

    # 3. Last trade
    if last is not None:
        return last, PriceSelection(chosen_price=last, chosen_price_reason="last_trade_fallback",
                                    bid=yes_bid, ask=yes_ask, last=last)

    # 4. YES bid only
    if yes_bid is not None:
        return yes_bid, PriceSelection(chosen_price=yes_bid, chosen_price_reason="yes_bid_only_fallback",
                                       bid=yes_bid, ask=yes_ask, last=last)

    # 5. No usable price
    return None, PriceSelection(chosen_price=0.0, chosen_price_reason="no_usable_price",
                                 bid=yes_bid, ask=yes_ask, last=last)


# ── Liquidity metrics ─────────────────────────────────────────────────────────

def _liquidity_metrics(market: Dict[str, Any]) -> Tuple[float, float, Optional[float]]:
    """Return (open_interest, volume, spread). spread=None if not computable."""
    oi  = _to_float(_coalesce(market.get("open_interest_fp"), market.get("open_interest"))) or 0.0
    vol = _to_float(_coalesce(market.get("volume_fp"), market.get("volume"))) or 0.0
    bid = _best_yes_bid(market)
    ask = _best_yes_ask(market)
    spread = (ask - bid) if (bid is not None and ask is not None and ask >= bid) else None
    return oi, vol, spread


# ── Contract classification ───────────────────────────────────────────────────

def _contract_type(market: Dict[str, Any]) -> str:
    strike_type = str(market.get("strike_type", "")).lower()
    blob = " ".join(str(market.get(k, "")) for k in ("title", "subtitle", "ticker")).lower()

    if any(t in strike_type for t in ("greater", "less", "above", "below")):
        return "binary_threshold"
    if any(t in blob for t in ("above", "below", ">", "<")):
        return "binary_threshold"
    return "exact_outcome"


def _threshold_direction(market: Dict[str, Any]) -> str:
    strike_type = str(market.get("strike_type", "")).lower()
    blob = " ".join(str(market.get(k, "")) for k in ("title", "subtitle", "ticker")).lower()
    if any(t in strike_type for t in ("less", "below")) or any(t in blob for t in ("below", "under", "<")):
        return "below"
    return "above"


def _build_observation(market: Dict[str, Any], selection: PriceSelection, contract_type: str) -> ContractObservation:
    ts = datetime.utcnow()
    ts_raw = _coalesce(market.get("last_updated_time"), market.get("updated_time"), market.get("close_time"))
    try:
        if ts_raw:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        pass

    return ContractObservation(
        contract_ticker=str(market.get("ticker", "")),
        source_venue="kalshi",
        snapshot_timestamp=ts,
        settlement_label=str(_coalesce(market.get("event_ticker"), market.get("subtitle"), market.get("title"), "")),
        contract_type=contract_type,
        open_interest=_to_float(_coalesce(market.get("open_interest_fp"), market.get("open_interest"))),
        volume=_to_float(_coalesce(market.get("volume_fp"), market.get("volume"))),
        price_selection=selection,
    )


# ── Main feed builder ─────────────────────────────────────────────────────────

def build_live_cpi_feed(
    config: Optional[LiveFeedConfig] = None,
    client: Optional[KalshiPublicClient] = None,
) -> Tuple[IndexMethodology, List[MaturitySnapshot], List[Dict[str, str]], Dict[str, Any]]:
    """
    Fetch live Kalshi CPI markets and transform into engine-ready inputs.

    Returns:
        (methodology, snapshots, contracts_table, stats)

    Raises:
        KalshiAPIError — on network/API failure (caller handles fallback)
        ValueError     — if no valid snapshots could be built
    """
    cfg    = config or LiveFeedConfig()
    client = client or KalshiPublicClient()

    grouped: Dict[date, Dict[str, list]] = {}
    contracts_table: List[Dict[str, str]] = []

    stats: Dict[str, Any] = {
        "series_ticker":             cfg.series_ticker,
        "price_mode":                cfg.price_mode,
        "markets_scanned":           0,
        "markets_included":          0,
        "markets_filtered_maturity": 0,
        "markets_filtered_strike":   0,
        "markets_filtered_pricing":  0,
        "markets_filtered_liquidity": 0,
        "maturities_built":          0,
        "min_open_interest":         cfg.min_open_interest,
        "min_volume":                cfg.min_volume,
        "max_wide_spread":           cfg.max_wide_spread,
    }

    for market in client.iter_markets(series_ticker=cfg.series_ticker, status="open"):
        stats["markets_scanned"] += 1

        # 1. Reference month
        maturity = _extract_reference_cpi_month(market)
        if maturity is None:
            stats["markets_filtered_maturity"] += 1
            continue

        # 2. Strike value
        strike_value = _extract_strike_value(market)
        if strike_value is None:
            stats["markets_filtered_strike"] += 1
            continue

        # 3. Liquidity filter
        oi, vol, spread = _liquidity_metrics(market)
        spread_ok = spread is None or spread <= cfg.max_wide_spread
        if oi < cfg.min_open_interest or vol < cfg.min_volume or not spread_ok:
            stats["markets_filtered_liquidity"] += 1
            contracts_table.append({
                "Ticker": str(market.get("ticker", "")),
                "Type":   "Excluded",
                "Threshold/Value": f"{strike_value:.2f}%",
                "Price":  "",
                "Method": f"liquidity_filter(oi={oi:.0f},vol={vol:.0f},spread={'n/a' if spread is None else f'{spread:.3f}'})",
                "Status": "Excluded",
            })
            continue

        # 4. Quote selection
        probability, selection = _choose_probability(market, price_mode=cfg.price_mode)
        if probability is None:
            stats["markets_filtered_pricing"] += 1
            continue
        probability = max(min(float(probability), 1.0), 0.0)

        # 5. Classify and group
        ct          = _contract_type(market)
        observation = _build_observation(market, selection, ct)
        bucket      = grouped.setdefault(maturity, {"binary_thresholds": [], "exact_outcomes": []})

        if ct == "binary_threshold":
            direction = _threshold_direction(market)
            p_above   = probability if direction == "above" else 1.0 - probability
            bucket["binary_thresholds"].append(BinaryThresholdContract(
                label=str(_coalesce(market.get("title"), market.get("ticker"))),
                threshold=strike_value,
                price=max(min(p_above, 1.0), 0.0),
                observation=observation,
            ))
            display_type = f"Binary threshold ({direction})"
        else:
            bucket["exact_outcomes"].append(ExactOutcomeContract(
                label=str(_coalesce(market.get("title"), market.get("ticker"))),
                value=strike_value,
                price=probability,
                observation=observation,
            ))
            display_type = "Exact outcome"

        stats["markets_included"] += 1
        contracts_table.append({
            "Ticker":          str(market.get("ticker", "")),
            "Type":            display_type,
            "Threshold/Value": f"{strike_value:.2f}%",
            "Price":           f"{probability:.4f}",
            "Method":          selection.chosen_price_reason,
            "Status":          "Included",
        })

    # 6. Build MaturitySnapshot objects
    snapshots: List[MaturitySnapshot] = []
    for maturity in sorted(grouped)[: cfg.max_maturities]:
        binary = sorted(grouped[maturity]["binary_thresholds"], key=lambda x: x.threshold)
        exact  = sorted(grouped[maturity]["exact_outcomes"],   key=lambda x: x.value)
        total  = len(binary) + len(exact)

        if total < cfg.min_contracts_per_maturity:
            logger.debug("Skipping maturity %s — only %d contracts (min %d)", maturity, total, cfg.min_contracts_per_maturity)
            continue

        if len(binary) >= max(2, cfg.min_contracts_per_maturity):
            snapshots.append(MaturitySnapshot(maturity=maturity, binary_thresholds=binary))
        elif len(exact) >= cfg.min_contracts_per_maturity:
            snapshots.append(MaturitySnapshot(maturity=maturity, exact_outcomes=exact))

    stats["maturities_built"] = len(snapshots)

    if not snapshots:
        raise ValueError(
            f"No valid CPI maturities built from {stats['markets_included']} included markets "
            f"({stats['markets_scanned']} scanned). "
            f"Filtered: maturity={stats['markets_filtered_maturity']}, "
            f"strike={stats['markets_filtered_strike']}, "
            f"pricing={stats['markets_filtered_pricing']}, "
            f"liquidity={stats['markets_filtered_liquidity']}."
        )

    methodology = IndexMethodology(
        index_name="Oriel CPI Forward Index",
        methodology_version="0.2.0-phase2-live",
        price_basis=f"kalshi_rest_{cfg.price_mode}",
        interpolation_method="linear",
        weighting_rule="front_anchor_base_100",
        smoothing_rule="isotonic_monotone_survival",
        stale_market_rule="cached_rest_polling",
        fallback_rule="sample_data_on_live_failure",
        publication_frequency=f"poll_{DEFAULT_CACHE_SECONDS}s",
        unit_label="%",
    )

    return methodology, snapshots, contracts_table, stats
