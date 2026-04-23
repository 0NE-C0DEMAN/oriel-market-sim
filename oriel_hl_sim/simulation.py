from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import math
import numpy as np
import pandas as pd
from .config.markets import HarnessConfig

@dataclass
class BacktestResult:
    path: pd.DataFrame
    summary: dict


def _quote_prices(oriel_ref: float, spread_bps: float) -> tuple[float, float]:
    half = oriel_ref * spread_bps / 10000.0 / 2.0
    return oriel_ref - half, oriel_ref + half


def run_backtest(dislocations: pd.DataFrame, spread_bps: float | None = None, launch_notional_usd: float | None = None,
                 config: HarnessConfig | None = None, seed: int = 0) -> BacktestResult:
    cfg = config or HarnessConfig()
    spread_bps = float(spread_bps if spread_bps is not None else cfg.base_spread_bps)
    launch_notional_usd = float(launch_notional_usd if launch_notional_usd is not None else cfg.launch_notional_usd)

    rng = np.random.default_rng(seed)
    if dislocations.empty:
        empty = pd.DataFrame(columns=['step','release_month','venue','oriel_reference_yoy','market_implied_yoy','bid','ask','exec_side','exec_size_usd','inventory_usd','mtm_pnl_usd'])
        return BacktestResult(empty, {'total_pnl_usd': 0.0, 'fills': 0, 'quote_uptime_pct': 0.0, 'avg_abs_dislocation_bps': 0.0})

    inventory = 0.0
    cash = 0.0
    rows = []
    max_clip = min(max(cfg.taker_clip_usd, launch_notional_usd * 0.03), launch_notional_usd * 0.10)

    for step, row in enumerate(dislocations.sort_values(['release_month','venue']).itertuples(index=False), start=1):
        ref = float(row.oriel_reference_yoy)
        mkt = float(row.implied_yoy)
        bid, ask = _quote_prices(ref, spread_bps)
        edge_after_spread = max(0.0, abs(float(row.dislocation_bps)) - spread_bps / 2.0)
        fill_prob = min(0.95, max(0.03, edge_after_spread / 45.0))
        event_multiplier = 1.0 + min(1.5, edge_after_spread / 75.0)
        clip = min(max_clip * event_multiplier, launch_notional_usd * 0.15)
        exec_side = 'none'
        exec_price = None
        if mkt < bid and inventory < cfg.inventory_limit_usd and rng.random() < fill_prob:
            exec_side = 'buy'
            exec_price = mkt
            inventory += clip
            cash -= clip * exec_price / 100.0
        elif mkt > ask and inventory > -cfg.inventory_limit_usd and rng.random() < fill_prob:
            exec_side = 'sell'
            exec_price = mkt
            inventory -= clip
            cash += clip * exec_price / 100.0
        mtm = cash + inventory * ref / 100.0
        rows.append({
            'step': step,
            'release_month': row.release_month,
            'venue': row.venue,
            'oriel_reference_yoy': ref,
            'market_implied_yoy': mkt,
            'dislocation_bps': float(row.dislocation_bps),
            'bid': bid,
            'ask': ask,
            'exec_side': exec_side,
            'exec_price': exec_price,
            'exec_size_usd': clip if exec_side != 'none' else 0.0,
            'inventory_usd': inventory,
            'cash_usd': cash,
            'mtm_pnl_usd': mtm,
        })
    path = pd.DataFrame(rows)
    summary = {
        'total_pnl_usd': float(path['mtm_pnl_usd'].iloc[-1]) if not path.empty else 0.0,
        'fills': int((path['exec_side'] != 'none').sum()) if not path.empty else 0,
        'quote_uptime_pct': 100.0,
        'avg_abs_dislocation_bps': float(path['dislocation_bps'].abs().mean()) if not path.empty else 0.0,
        'max_inventory_usd': float(path['inventory_usd'].abs().max()) if not path.empty else 0.0,
        'launch_notional_usd': launch_notional_usd,
        'spread_bps': spread_bps,
    }
    return BacktestResult(path=path, summary=summary)


def run_parameter_sweep(dislocations: pd.DataFrame, spreads_bps: Iterable[float] = (8, 12, 16, 20, 24, 32),
                        launch_sizes_usd: Iterable[float] = (1_000_000, 2_000_000, 3_000_000, 5_000_000),
                        config: HarnessConfig | None = None) -> pd.DataFrame:
    cfg = config or HarnessConfig()
    rows = []
    for spread in spreads_bps:
        for launch_size in launch_sizes_usd:
            bt = run_backtest(dislocations, spread_bps=float(spread), launch_notional_usd=float(launch_size), config=cfg)
            rows.append({
                'spread_bps': float(spread),
                'launch_notional_usd': float(launch_size),
                'total_pnl_usd': bt.summary['total_pnl_usd'],
                'fills': bt.summary['fills'],
                'max_inventory_usd': bt.summary['max_inventory_usd'],
                'avg_abs_dislocation_bps': bt.summary['avg_abs_dislocation_bps'],
            })
    return pd.DataFrame(rows)
