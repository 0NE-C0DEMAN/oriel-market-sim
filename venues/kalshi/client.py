"""
kalshi_client.py — Hardened public REST client for Kalshi market data.

REST-only, no WebSockets, no authentication, no trading.
All network exceptions normalized into KalshiAPIError.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class KalshiAPIError(RuntimeError):
    """All Kalshi REST errors normalize here. No raw requests exceptions leak."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class KalshiClientConfig:
    base_url: str = field(default_factory=lambda: os.getenv(
        "KALSHI_API_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2"))
    fallback_base_url: str = field(default_factory=lambda: os.getenv(
        "KALSHI_API_BASE_URL_FALLBACK", "https://trading-api.kalshi.com/trade-api/v2"))
    timeout_seconds: float = field(default_factory=lambda: float(os.getenv("KALSHI_TIMEOUT_SECONDS", "20")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("KALSHI_MAX_RETRIES", "6")))
    # urllib3 backoff: sleep = backoff_seconds * (2 ** (attempt - 1))
    backoff_seconds: float = field(default_factory=lambda: float(os.getenv("KALSHI_BACKOFF_SECONDS", "0.9")))
    user_agent: str = field(default_factory=lambda: os.getenv("KALSHI_USER_AGENT", "oriel-v5/0.1"))
    # Close keep-alive to avoid stale TLS on some proxies
    close_connection: bool = field(default_factory=lambda: os.getenv("KALSHI_HTTP_CLOSE_CONNECTION", "true").lower() == "true")
    try_fallback_host: bool = field(default_factory=lambda: os.getenv("KALSHI_TRY_FALLBACK_HOST", "true").lower() == "true")


def _build_session(config: KalshiClientConfig) -> requests.Session:
    session = requests.Session()
    headers: Dict[str, str] = {"User-Agent": config.user_agent, "Accept": "application/json"}
    if config.close_connection:
        headers["Connection"] = "close"
    session.headers.update(headers)
    retry = Retry(
        total=config.max_retries,
        connect=config.max_retries,
        read=config.max_retries,
        backoff_factor=config.backoff_seconds,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class KalshiPublicClient:
    """
    Lightweight REST client for Kalshi public market-data endpoints.
    REST-only. All errors normalized to KalshiAPIError.
    Supports primary + optional fallback host with exponential backoff.
    """

    def __init__(self, config: Optional[KalshiClientConfig] = None,
                 session: Optional[requests.Session] = None) -> None:
        self.config = config or KalshiClientConfig()
        self.session = session or _build_session(self.config)

    def _candidate_bases(self) -> List[str]:
        primary = self.config.base_url.rstrip("/")
        bases = [primary]
        fb = (self.config.fallback_base_url or "").strip().rstrip("/")
        if self.config.try_fallback_host and fb and fb != primary:
            bases.append(fb)
        return bases

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        bases = self._candidate_bases()
        last_error: Optional[Exception] = None
        last_status: Optional[int] = None

        for i, base in enumerate(bases):
            url = f"{base}/{path.lstrip('/')}"
            try:
                resp = self.session.get(url, params=params, timeout=self.config.timeout_seconds)
                last_status = resp.status_code

                if resp.status_code == 429:
                    raise KalshiAPIError(f"Kalshi rate limit (429) — {url}", status_code=429)
                if resp.status_code >= 500:
                    raise KalshiAPIError(f"Kalshi server error ({resp.status_code}) — {url}", status_code=resp.status_code)
                if resp.status_code >= 400:
                    raise KalshiAPIError(f"Kalshi client error ({resp.status_code}) — {url}: {resp.text[:200]}", status_code=resp.status_code)

                try:
                    return resp.json()
                except ValueError as exc:
                    raise KalshiAPIError(f"Non-JSON response from {url}") from exc

            except KalshiAPIError:
                raise
            except requests.exceptions.Timeout as exc:
                last_error = exc
                logger.warning("Kalshi timeout %s (host %d/%d)", url, i + 1, len(bases))
            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                logger.warning("Kalshi connection error %s (host %d/%d)", url, i + 1, len(bases))
            except requests.exceptions.RequestException as exc:
                last_error = exc
                logger.warning("Kalshi request error %s: %s", url, exc)

            if i < len(bases) - 1:
                time.sleep(self.config.backoff_seconds)

        raise KalshiAPIError(
            f"Kalshi request failed for '{path}' on all hosts. Last: {last_error}",
            status_code=last_status,
        ) from last_error

    def iter_markets(self, *, series_ticker: str, status: str = "open",
                     limit: int = 200) -> Iterator[Dict[str, Any]]:
        """Yield all markets for a series ticker, handling pagination transparently."""
        cursor: Optional[str] = None
        while True:
            params: Dict[str, Any] = {
                "series_ticker": series_ticker,
                "status": status,
                "limit": min(limit, 200),
            }
            if cursor:
                params["cursor"] = cursor
            payload = self._request("markets", params=params)
            markets = payload.get("markets") or []
            for market in markets:
                yield market
            cursor = payload.get("cursor")
            if not cursor or not markets:
                break

    def get_market(self, ticker: str) -> Dict[str, Any]:
        """Fetch a single market by ticker."""
        return self._request(f"markets/{ticker}").get("market") or {}


def safe_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, default=str)
