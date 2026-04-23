"""
phase2_config.py — Runtime metadata for the live Kalshi CPI feed.

Exposes feed parameters for UI diagnostics display.
No transformation logic here.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from .live_data import DEFAULT_CACHE_SECONDS, LiveFeedConfig
from .client import KalshiClientConfig


def live_feed_runtime_config() -> Dict[str, Any]:
    """
    Return a flat dict of all live feed parameters for UI display.
    Merges feed config + client config + transport metadata.
    """
    feed_cfg   = LiveFeedConfig()
    client_cfg = KalshiClientConfig()

    payload: Dict[str, Any] = asdict(feed_cfg)

    # Client transport settings
    payload["cache_seconds"]    = DEFAULT_CACHE_SECONDS
    payload["transport"]        = "REST polling (public, no auth)"
    payload["primary_host"]     = client_cfg.base_url
    payload["fallback_host"]    = client_cfg.fallback_base_url if client_cfg.try_fallback_host else "disabled"
    payload["timeout_seconds"]  = client_cfg.timeout_seconds
    payload["max_retries"]      = client_cfg.max_retries
    payload["websocket"]        = "not implemented"

    return payload
