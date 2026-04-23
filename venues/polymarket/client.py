from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from .config import PolymarketConfig
from .models import PolymarketContract

UTC = timezone.utc
MONTH_MAP = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr", "may": "May", "june": "Jun",
    "july": "Jul", "august": "Aug", "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
    "jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr", "jun": "Jun", "jul": "Jul", "aug": "Aug",
    "sep": "Sep", "sept": "Sep", "oct": "Oct", "nov": "Nov", "dec": "Dec",
}
_DIRECTION_RE = re.compile(r'(above|over|exceed|greater than|at least|below|under|less than|lower than)', re.I)


class PolymarketClient:
    def __init__(self, config: PolymarketConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "oriel-polymarket-adapter/0.3"})

    def fetch_contracts(self) -> tuple[list[PolymarketContract], str]:
        valuation_timestamp = datetime.now(UTC)
        try:
            markets = self._fetch_markets()
            contracts = self._normalize_markets(markets, valuation_timestamp)
            return contracts, "LIVE"
        except Exception:
            if not self.config.allow_sample_fallback:
                raise
            return self._sample_contracts(valuation_timestamp), "FALLBACK"

    def _fetch_markets(self) -> list[dict[str, Any]]:
        """Fetch markets from the Gamma API.

        Makes two calls: one general scan (trending markets) and one targeted
        scan using the Macro Indicators tag (tag_id=102000) where Polymarket
        lists CPI/inflation threshold contracts. Results are merged and
        deduplicated by market slug.
        """
        seen_slugs: set[str] = set()
        all_markets: list[dict[str, Any]] = []

        for params in [
            # Targeted: Macro Indicators tag — where CPI/inflation markets live
            {"limit": self.config.max_markets_scan, "closed": "false", "tag_id": self.config.macro_indicators_tag_id},
            # General trending scan (fallback for any CPI markets that aren't tagged)
            {"limit": self.config.max_markets_scan, "closed": "false"},
        ]:
            resp = self.session.get(
                f"{self.config.gamma_api_url}/markets",
                params=params,
                timeout=self.config.request_timeout_seconds,
            )
            resp.raise_for_status()
            payload = resp.json()
            markets: list[dict[str, Any]] = []
            if isinstance(payload, dict):
                for key in ("data", "markets"):
                    if isinstance(payload.get(key), list):
                        markets = payload[key]
                        break
            elif isinstance(payload, list):
                markets = payload

            for m in markets:
                slug = str(m.get("slug") or m.get("market_slug") or m.get("id") or "")
                if slug and slug not in seen_slugs:
                    seen_slugs.add(slug)
                    all_markets.append(m)

        if not all_markets:
            raise ValueError("Unexpected Polymarket markets payload — no markets returned from either scan")
        return all_markets


    def _normalize_markets(self, markets: list[dict[str, Any]], valuation_timestamp: datetime) -> list[PolymarketContract]:
        out: list[PolymarketContract] = []
        for market in markets:
            question = str(market.get("question") or market.get("title") or market.get("market_slug") or market.get("slug") or "")
            slug = str(market.get("slug") or market.get("market_slug") or "")
            text = f"{question} {slug}".lower()
            if not any(term in text for term in self.config.cpi_search_terms):
                continue

            # Skip non-US inflation markets (Argentina, Canada, UK, etc.)
            if any(country in text for country in self.config.exclude_country_keywords):
                continue

            threshold = self._extract_threshold(question) or self._extract_threshold(slug)
            release_month = self._extract_release_month(question) or self._extract_release_month(slug)
            end_date_str = str(market.get("endDate") or "")
            if release_month is None:
                # Fallback 1: month name without year (e.g. "in April?") + year from endDate
                month_only = self._extract_month_only(question) or self._extract_month_only(slug)
                if month_only and len(end_date_str) >= 4:
                    release_month = f"{month_only} {end_date_str[:4]}"
            if release_month is None:
                # Fallback 2: no month at all (e.g. "in 2026?") — derive from endDate directly
                # Annual markets that expire Dec 31 anchor to the December CPI release
                if len(end_date_str) >= 7:
                    try:
                        month_num = int(end_date_str[5:7])
                        month_name = datetime.strptime(str(month_num), "%m").strftime("%b")
                        release_month = f"{month_name} {end_date_str[:4]}"
                    except (ValueError, IndexError):
                        pass
            if threshold is None or release_month is None:
                continue

            active = self._truthy(market.get("active"), default=True)
            closed = self._truthy(market.get("closed"), default=False)
            archived = self._truthy(market.get("archived"), default=False)
            if self.config.require_active and (not active or closed or archived):
                continue

            outcome, outcome_price = self._extract_outcome_and_price(market)
            bid = self._safe_float(market.get("bestBid") or market.get("best_bid"))
            ask = self._safe_float(market.get("bestAsk") or market.get("best_ask"))
            last = self._safe_float(market.get("lastTradePrice") or market.get("last_trade_price") or market.get("price"))
            mid = self._midpoint(bid, ask, outcome_price if outcome_price is not None else last)
            spread = (ask - bid) if bid is not None and ask is not None and ask >= bid else None
            volume = self._safe_float(market.get("volume") or market.get("volumeNum") or market.get("volume24hr") or market.get("volume24hrClob"))
            open_interest = self._safe_float(market.get("openInterest") or market.get("open_interest") or market.get("liquidity") or market.get("liquidityClob"))
            last_updated = self._parse_datetime(market.get("updatedAt") or market.get("endDate") or market.get("acceptingOrdersTimestamp"))
            quote_age_seconds = None
            is_stale = False
            if last_updated is not None:
                quote_age_seconds = max(int((valuation_timestamp - last_updated).total_seconds()), 0)
                is_stale = quote_age_seconds > self.config.max_quote_age_seconds
            has_valid_quote = mid is not None
            depth_usd = open_interest
            has_depth = bool((depth_usd or 0) > 0)
            confidence = self._confidence_score(spread=spread, volume=volume, open_interest=open_interest)
            liquidity = self._liquidity_score(volume=volume, open_interest=open_interest)
            market_id = str(market.get("id") or market.get("conditionId") or slug or question)
            settlement_source = str(market.get("resolutionSource") or "BLS CPI release")
            out.append(PolymarketContract(
                venue="Polymarket",
                market_id=market_id,
                slug=slug,
                question=question,
                release_month=release_month,
                resolution_time=self._parse_datetime(market.get("endDate") or market.get("resolveDate") or market.get("resolutionTime")),
                threshold=threshold,
                outcome=outcome,
                outcome_price=outcome_price,
                bid=bid,
                ask=ask,
                last=last,
                mid=mid,
                spread=spread,
                volume=volume,
                open_interest=open_interest,
                liquidity_score=liquidity,
                confidence_score=confidence,
                settlement_source=settlement_source,
                valuation_timestamp=valuation_timestamp,
                last_updated=last_updated,
                has_valid_quote=has_valid_quote,
                has_depth=has_depth,
                depth_usd=depth_usd,
                quote_age_seconds=quote_age_seconds,
                is_stale=is_stale,
                raw=market,
            ))
        return out

    def _extract_outcome_and_price(self, market: dict[str, Any]) -> tuple[str, Optional[float]]:
        outcomes = market.get("outcomes")
        prices = market.get("outcomePrices") or market.get("outcome_prices")
        if isinstance(outcomes, str):
            outcomes = self._parse_jsonish_list(outcomes)
        if isinstance(prices, str):
            parsed = self._parse_jsonish_list(prices)
            prices = [self._safe_float(item) for item in parsed]
        if isinstance(outcomes, list) and isinstance(prices, list) and outcomes and prices:
            pairs = []
            for idx, outcome in enumerate(outcomes):
                price = self._safe_float(prices[idx]) if idx < len(prices) else None
                pairs.append((str(outcome), price))
            # Prefer YES if present, otherwise first populated outcome.
            yes_pair = next((pair for pair in pairs if pair[0].strip().lower() == "yes"), None)
            if yes_pair is not None:
                return yes_pair
            first = next((pair for pair in pairs if pair[1] is not None), None)
            if first is not None:
                return first
        return "YES", self._safe_float(market.get("price"))

    @staticmethod
    def _parse_jsonish_list(value: str) -> list[Any]:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            return [item.strip().strip('"') for item in value.split(",") if item.strip()]

    @staticmethod
    def _extract_threshold(text: str) -> Optional[float]:
        if not text:
            return None
        match = re.search(r'(?:above|over|exceed|greater than|at least|below|under|less than|lower than)\s+([0-9]+(?:\.[0-9]+)?)%?', text, re.I)
        if match:
            return float(match.group(1))
        match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*%', text)
        return float(match.group(1)) if match else None

    @staticmethod
    def extract_threshold_direction(text: str) -> str:
        if not text:
            return "above"
        match = _DIRECTION_RE.search(text)
        if not match:
            return "above"
        direction = match.group(1).lower()
        return "below" if direction in {"below", "under", "less than", "lower than"} else "above"

    @staticmethod
    def _extract_release_month(text: str, fallback_dt: Optional[datetime] = None) -> Optional[str]:
        if not text:
            return None
        lowered = text.lower()
        match = re.search(r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(20\d{2})', lowered)
        if match:
            return f"{MONTH_MAP[match.group(1)]} {match.group(2)}"
        match = re.search(r'(20\d{2})[-_/](\d{2})', lowered)
        if match:
            year, month_num = match.groups()
            try:
                month_name = datetime.strptime(month_num, '%m').strftime('%b')
                return f"{month_name} {year}"
            except Exception:
                return None
        month_only = PolymarketClient._extract_month_only(text)
        if month_only and fallback_dt is not None:
            return f"{month_only} {fallback_dt.year}"
        return None

    @staticmethod
    def _extract_month_only(text: str) -> Optional[str]:
        """Extract a bare month name without a year (e.g. 'in April?' → 'Apr')."""
        if not text:
            return None
        match = re.search(
            r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b',
            text.lower(),
        )
        if match:
            return MONTH_MAP.get(match.group(1))
        return None

    @staticmethod
    def _safe_float(value: object) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _midpoint(bid: Optional[float], ask: Optional[float], fallback: Optional[float]) -> Optional[float]:
        if bid is not None and ask is not None and ask >= bid:
            return round((bid + ask) / 2.0, 4)
        return round(float(fallback), 4) if fallback is not None else None

    @staticmethod
    def _parse_datetime(value: object) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        try:
            import pandas as pd
            dt = pd.to_datetime(value, utc=True)
            return dt.to_pydatetime()
        except Exception:
            return None

    @staticmethod
    def _truthy(value: object, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y", "on"}:
                return True
            if lowered in {"false", "0", "no", "n", "off"}:
                return False
        return bool(value)

    @staticmethod
    def _liquidity_score(volume: Optional[float], open_interest: Optional[float]) -> float:
        volume_score = min(float(volume or 0) / 1000.0, 1.0)
        oi_score = min(float(open_interest or 0) / 5000.0, 1.0)
        return round(volume_score * 0.5 + oi_score * 0.5, 3)

    @staticmethod
    def _confidence_score(spread: Optional[float], volume: Optional[float], open_interest: Optional[float]) -> float:
        spread_component = 100.0 if spread is None else max(0.0, 100.0 - min(spread * 10000.0, 100.0))
        volume_component = min(float(volume or 0) / 10.0, 100.0)
        oi_component = min(float(open_interest or 0) / 10.0, 100.0)
        return round(0.5 * spread_component + 0.25 * volume_component + 0.25 * oi_component, 1)

    def _sample_contracts(self, valuation_timestamp: datetime) -> list[PolymarketContract]:
        # Sample spreads stay comfortably inside the Polymarket render gate so fallback mode always produces a full demo curve.
        rows = [
            ("poly-cpi-mar-26", "Will March 2026 inflation be above 2.8%?", "Mar 2026", 2.8, 0.58, 0.579, 0.581, 820.0, 1600.0),
            ("poly-cpi-apr-26", "Will April 2026 inflation be above 2.6%?", "Apr 2026", 2.6, 0.54, 0.539, 0.541, 760.0, 1450.0),
            ("poly-cpi-may-26", "Will May 2026 inflation be above 2.5%?", "May 2026", 2.5, 0.50, 0.499, 0.501, 640.0, 1320.0),
            ("poly-cpi-jun-26", "Will June 2026 inflation be above 2.4%?", "Jun 2026", 2.4, 0.48, 0.479, 0.481, 590.0, 1240.0),
            ("poly-cpi-jul-26", "Will July 2026 inflation be above 2.5%?", "Jul 2026", 2.5, 0.52, 0.519, 0.521, 510.0, 1180.0),
            ("poly-cpi-aug-26", "Will August 2026 inflation be above 2.6%?", "Aug 2026", 2.6, 0.55, 0.549, 0.551, 455.0, 1090.0),
        ]
        contracts: list[PolymarketContract] = []
        for market_id, question, release_month, threshold, mid, bid, ask, volume, open_interest in rows:
            spread = ask - bid
            contracts.append(PolymarketContract(
                venue="Polymarket",
                market_id=market_id,
                slug=market_id,
                question=question,
                release_month=release_month,
                resolution_time=None,
                threshold=threshold,
                outcome="YES",
                outcome_price=mid,
                bid=bid,
                ask=ask,
                last=mid,
                mid=mid,
                spread=spread,
                volume=volume,
                open_interest=open_interest,
                liquidity_score=self._liquidity_score(volume, open_interest),
                confidence_score=self._confidence_score(spread, volume, open_interest),
                settlement_source="BLS CPI release",
                valuation_timestamp=valuation_timestamp,
                last_updated=valuation_timestamp,
                has_valid_quote=True,
                has_depth=True,
                depth_usd=open_interest,
                quote_age_seconds=0,
                is_stale=False,
                raw={"sample": True},
            ))
        return contracts
