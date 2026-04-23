from __future__ import annotations

import io
import re
from dataclasses import asdict
from datetime import datetime, timezone; UTC = timezone.utc
from typing import Iterable, Optional
from urllib.parse import urljoin

import pandas as pd
import requests

from .config import ForecastExConfig
from .models import ForecastExContract

# Matches direct .csv hrefs AND ForecastEx API download links (/api/download?type=...&date=YYYYMMDD)
CSV_LINK_PATTERN = re.compile(
    r'href=["\'](?P<href>[^"\']*?(?:\.csv|/api/download\?[^"\']*?))["\']',
    re.IGNORECASE,
)
# Matches both YYYY-MM-DD and YYYYMMDD date formats
DATE_PATTERN = re.compile(r'(20\d{2})-?(\d{2})-?(\d{2})')


class ForecastExClient:
    """Best-effort ForecastEx client.

    The live path supports two modes:
    1. Explicit CSV URLs supplied by environment variables.
    2. Discovery from the public ForecastEx data page.

    This implementation is designed for developer handoff. Depending on the
    exact deployment environment, the developer may want to swap this for a
    direct exchange feed or a more tightly validated CSV schema.
    """

    def __init__(self, config: ForecastExConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "oriel-forecastex-adapter/0.3"})

    def fetch_contracts(self) -> tuple[list[ForecastExContract], str]:
        valuation_timestamp = datetime.now(UTC)

        try:
            pairs_df = self._fetch_pairs_frame()
            contracts = self._normalize_pairs_frame(pairs_df, valuation_timestamp)
            status = "LIVE"
            return contracts, status
        except Exception:
            if not self.config.allow_sample_fallback:
                raise
            return self._sample_contracts(valuation_timestamp), "FALLBACK"

    def _fetch_pairs_frame(self) -> pd.DataFrame:
        pairs_url = self.config.intraday_pairs_url or self._discover_latest_csv(kind="pairs")
        response = self.session.get(pairs_url, timeout=self.config.request_timeout_seconds)
        response.raise_for_status()
        return pd.read_csv(io.StringIO(response.text))

    def _discover_latest_csv(self, kind: str) -> str:
        response = self.session.get(self.config.data_page_url, timeout=self.config.request_timeout_seconds)
        response.raise_for_status()
        html = response.text

        discovered_links = [
            urljoin(self.config.data_page_url, match.group("href").replace("&amp;", "&"))
            for match in CSV_LINK_PATTERN.finditer(html)
        ]
        if not discovered_links:
            raise ValueError("No CSV links found on ForecastEx data page")

        kind_matches = [link for link in discovered_links if kind.lower() in link.lower()]
        if not kind_matches:
            raise ValueError(f"No discovered CSV links matched kind={kind!r}")

        def sort_key(link: str) -> tuple[str, str]:
            date_match = DATE_PATTERN.search(link)
            if date_match:
                y, m, d = date_match.groups()
                return (f"{y}-{m}-{d}", link)
            return ("0000-00-00", link)

        return sorted(kind_matches, key=sort_key, reverse=True)[0]

    def _normalize_pairs_frame(self, df: pd.DataFrame, valuation_timestamp: datetime) -> list[ForecastExContract]:
        if df.empty:
            return []

        normalized_columns = {c: self._slug(c) for c in df.columns}
        df = df.rename(columns=normalized_columns)

        def first_present(row: pd.Series, names: Iterable[str]) -> Optional[object]:
            for name in names:
                if name in row and pd.notna(row[name]):
                    return row[name]
            return None

        contracts: list[ForecastExContract] = []
        for _, row in df.iterrows():
            product_code = str(first_present(row, ["product_code", "product", "symbol", "instrument", "contract", "event_contract"]) or "")
            event_question = str(first_present(row, ["event_question", "question", "market_question", "description"]) or "")
            text = f"{product_code} {event_question}".upper()

            # Keep the filter broad enough to survive schema variation but narrow enough
            # to focus on CPI-style products.
            if "CPI" not in text:
                continue
            # US YoY headline CPI only — matches Kalshi (KXCPI, US) and Polymarket (US CPI).
            # Excludes CACPI (Canada), HKCPI (Hong Kong), CPIJP (Japan), CPIIN (India),
            # CPISP (Spain), SGCPI (Singapore), CPIGE (Germany), CPIC (US Core — different series).
            pc_upper = product_code.upper().strip()
            if not pc_upper.startswith("CPIY_"):
                continue

            release_month = self._extract_release_month(text) or "Unknown"
            threshold = self._extract_threshold(event_question) or self._extract_threshold(product_code)
            contract_id = str(first_present(row, ["contract_id", "instrument_id", "id", "market_id", "pair_id"]) or product_code or event_question)
            bid = self._safe_float(first_present(row, ["bid", "best_bid", "yes_bid"]))
            ask = self._safe_float(first_present(row, ["ask", "best_ask", "yes_ask"]))
            last = self._safe_float(first_present(row, ["last", "last_trade", "trade_price", "yes_last", "yes_price"]))
            mid = self._midpoint(bid, ask, last)
            volume = self._safe_int(first_present(row, ["volume", "qty", "quantity"])) or 0
            open_interest = self._safe_int(first_present(row, ["open_interest", "oi"])) or 0
            resolution_time = self._parse_datetime(first_present(row, ["resolution_time", "expiry", "expiration", "event_time", "expiration_date"]))
            side = str(first_present(row, ["side", "position"]) or "YES")
            coupon_rate = self._safe_float(first_present(row, ["coupon_rate", "incentive_coupon", "coupon"]))

            contract = ForecastExContract(
                venue="ForecastEx",
                contract_id=contract_id,
                product_code=product_code,
                event_question=event_question,
                release_month=release_month,
                resolution_time=resolution_time,
                threshold=threshold,
                side=side,
                bid=bid,
                ask=ask,
                last=last,
                mid=mid,
                open_interest=open_interest,
                volume=volume,
                coupon_rate=coupon_rate,
                settlement_source="BLS CPI initial release",
                valuation_timestamp=valuation_timestamp,
                raw=row.to_dict(),
            )
            contracts.append(contract)

        return contracts

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

    @staticmethod
    def _safe_float(value: object) -> Optional[float]:
        try:
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _safe_int(value: object) -> Optional[int]:
        try:
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return None
            return int(float(value))
        except Exception:
            return None

    @staticmethod
    def _midpoint(bid: Optional[float], ask: Optional[float], last: Optional[float]) -> Optional[float]:
        if bid is not None and ask is not None and ask >= bid:
            return (bid + ask) / 2.0
        return last

    @staticmethod
    def _extract_threshold(text: str) -> Optional[float]:
        # Primary (Chris): number followed by '%' (e.g. "Will CPI exceed 4%?")
        match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*%', text)
        if match:
            return float(match.group(1))
        # Fallback: product-code format CPIY_MMYY_N (e.g. CPIY_0526_4, CPIY_0626_4.8).
        # Live pairs feed uses this when event_question is empty.
        match = re.search(r'_\d{4}_(\d+(?:\.\d+)?)$', text)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _extract_release_month(text: str) -> Optional[str]:
        match = re.search(
            r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*(20\d{2})',
            text,
        )
        if match:
            month = match.group(1).title()
            return f"{month} {match.group(2)}"

        # \b fails when next char is underscore (word char); use lookahead for non-digit instead
        match = re.search(r'_(\d{2})(\d{2})(?=\D|$)', text)
        if match:
            mm, yy = match.groups()
            month_name = datetime.strptime(mm, '%m').strftime('%b')
            return f"{month_name} 20{yy}"
        return None

    @staticmethod
    def _parse_datetime(value: object) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            dt = pd.to_datetime(value, utc=True)
            return dt.to_pydatetime()
        except Exception:
            return None

    def _sample_contracts(self, valuation_timestamp: datetime) -> list[ForecastExContract]:
        sample_rows = [
            ("CPIY_0326", "Will the year-over-year change in the US Consumer Price Index exceed 0.9% in Mar 2026?", "Mar 2026", 0.91, 1200, 6400),
            ("CPIY_0426", "Will the year-over-year change in the US Consumer Price Index exceed 0.7% in Apr 2026?", "Apr 2026", 0.67, 980, 5200),
            ("CPIY_0526", "Will the year-over-year change in the US Consumer Price Index exceed 0.3% in May 2026?", "May 2026", 0.32, 870, 4800),
            ("CPIY_0626", "Will the year-over-year change in the US Consumer Price Index exceed 0.2% in Jun 2026?", "Jun 2026", 0.21, 720, 3900),
            ("CPIY_0726", "Will the year-over-year change in the US Consumer Price Index exceed 0.2% in Jul 2026?", "Jul 2026", 0.24, 690, 3600),
            ("CPIY_0826", "Will the year-over-year change in the US Consumer Price Index exceed 0.2% in Aug 2026?", "Aug 2026", 0.22, 650, 3400),
        ]
        return [
            ForecastExContract(
                venue="ForecastEx",
                contract_id=cid,
                product_code=cid,
                event_question=question,
                release_month=release_month,
                resolution_time=None,
                threshold=value,
                side="YES",
                bid=value,
                ask=value,
                last=value,
                mid=value,
                open_interest=oi,
                volume=volume,
                coupon_rate=None,
                settlement_source="BLS CPI initial release",
                valuation_timestamp=valuation_timestamp,
                raw={"sample": True},
            )
            for cid, question, release_month, value, volume, oi in sample_rows
        ]
