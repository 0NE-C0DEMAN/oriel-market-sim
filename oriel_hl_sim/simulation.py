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


def _stability_score(fill_rate_pct: float, inventory_vol_ratio: float,
                     max_inventory_ratio: float, pnl_quality_score: float) -> float:
    fill_component = min(1.0, fill_rate_pct / 35.0)
    inv_component = max(0.0, 1.0 - min(1.0, inventory_vol_ratio / 0.45))
    cap_component = max(0.0, 1.0 - min(1.0, max_inventory_ratio / 0.85))
    pnl_component = max(0.0, min(1.0, pnl_quality_score))
    score = 100.0 * (0.30 * fill_component + 0.30 * inv_component + 0.20 * cap_component + 0.20 * pnl_component)
    return float(score)


def run_backtest(
    dislocations: pd.DataFrame,
    spread_bps: float | None = None,
    launch_notional_usd: float | None = None,
    config: HarnessConfig | None = None,
    seed: int = 42,
) -> BacktestResult:
    cfg = config or HarnessConfig()
    spread_bps = float(spread_bps if spread_bps is not None else cfg.base_spread_bps)
    launch_notional_usd = float(launch_notional_usd if launch_notional_usd is not None else cfg.launch_notional_usd)

    rng = np.random.default_rng(seed)
    if dislocations.empty:
        empty = pd.DataFrame(columns=[
            'step','release_month','venue','oriel_reference_yoy','market_implied_yoy','bid','ask',
            'exec_side','exec_size_usd','inventory_usd','mtm_pnl_usd','spread_capture_pnl_usd',
            'directional_pnl_usd','liquidity_multiplier','fill_prob','quote_width_bps'
        ])
        return BacktestResult(empty, {
            'total_pnl_usd': 0.0,
            'fills': 0,
            'quote_uptime_pct': 0.0,
            'avg_abs_dislocation_bps': 0.0,
            'fill_rate_pct': 0.0,
            'inventory_turnover': 0.0,
            'inventory_volatility_usd': 0.0,
            'market_stability_score': 0.0,
            'liquidity_self_sufficiency_score': 0.0,
            'pnl_quality_score': 0.0,
        })

    inventory = 0.0
    cash = 0.0
    rows = []
    max_clip = min(max(cfg.taker_clip_usd, launch_notional_usd * 0.03), launch_notional_usd * 0.10)
    liquidity_scale = max(0.5, launch_notional_usd / max(1.0, cfg.launch_notional_usd))
    liquidity_multiplier = 0.85 + 0.45 * math.sqrt(liquidity_scale)
    quote_tightening = max(0.75, 1.0 - 0.06 * math.log(max(liquidity_scale, 1e-9), 2))
    effective_spread_bps = max(4.0, spread_bps * quote_tightening)
    spread_capture_pnl = 0.0
    directional_pnl = 0.0
    prev_ref = None

    ordered = dislocations.sort_values(['release_month', 'venue']).reset_index(drop=True)
    total_quote_events = len(ordered)

    for step, row in enumerate(ordered.itertuples(index=False), start=1):
        ref = float(row.oriel_reference_yoy)
        mkt = float(row.implied_yoy)
        bid, ask = _quote_prices(ref, effective_spread_bps)
        edge_after_spread = max(0.0, abs(float(row.dislocation_bps)) - effective_spread_bps / 2.0)

        base_fill = 0.02 + min(0.55, edge_after_spread / 65.0)
        confidence_bonus = 0.15 * float(getattr(row, 'confidence_score', 0.5) or 0.5)
        liquidity_bonus = 0.12 * float(getattr(row, 'liquidity_score', 0.5) or 0.5) * min(1.25, liquidity_multiplier)
        inventory_penalty = min(0.25, abs(inventory) / max(launch_notional_usd, 1.0) * 0.60)
        fill_prob = min(0.95, max(0.03, base_fill + confidence_bonus + liquidity_bonus - inventory_penalty))

        event_multiplier = 1.0 + min(1.5, edge_after_spread / 75.0)
        clip = min(max_clip * event_multiplier * min(1.4, liquidity_multiplier), launch_notional_usd * 0.18)

        exec_side = 'none'
        exec_price = None
        prev_inventory = inventory

        if mkt < bid and inventory < cfg.inventory_limit_usd and rng.random() < fill_prob:
            exec_side = 'buy'
            exec_price = mkt
            inventory += clip
            cash -= clip * exec_price / 100.0
            spread_capture_pnl += clip * max(ref - exec_price, 0.0) / 100.0
        elif mkt > ask and inventory > -cfg.inventory_limit_usd and rng.random() < fill_prob:
            exec_side = 'sell'
            exec_price = mkt
            inventory -= clip
            cash += clip * exec_price / 100.0
            spread_capture_pnl += clip * max(exec_price - ref, 0.0) / 100.0

        # Simple inventory mean-reversion if the reference moves against the current book.
        if prev_ref is not None:
            ref_change = ref - prev_ref
            directional_pnl += prev_inventory * ref_change / 100.0
            if abs(inventory) > launch_notional_usd * 0.10:
                inventory_reversion = min(abs(inventory), launch_notional_usd * 0.025)
                if inventory > 0 and ref_change < 0 and rng.random() < 0.45:
                    inventory -= inventory_reversion
                    cash += inventory_reversion * ref / 100.0
                elif inventory < 0 and ref_change > 0 and rng.random() < 0.45:
                    inventory += inventory_reversion
                    cash -= inventory_reversion * ref / 100.0
        prev_ref = ref

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
            'spread_capture_pnl_usd': spread_capture_pnl,
            'directional_pnl_usd': directional_pnl,
            'liquidity_multiplier': liquidity_multiplier,
            'fill_prob': fill_prob,
            'quote_width_bps': effective_spread_bps,
        })

    path = pd.DataFrame(rows)
    fills = int((path['exec_side'] != 'none').sum()) if not path.empty else 0
    fill_rate_pct = 100.0 * fills / max(total_quote_events, 1)
    inventory_volatility_usd = float(path['inventory_usd'].std(ddof=0)) if len(path) > 1 else 0.0
    max_inventory_usd = float(path['inventory_usd'].abs().max()) if not path.empty else 0.0
    inventory_turnover = float(path['exec_size_usd'].sum() / max(launch_notional_usd, 1.0))
    inventory_vol_ratio = inventory_volatility_usd / max(launch_notional_usd, 1.0)
    max_inventory_ratio = max_inventory_usd / max(launch_notional_usd, 1.0)
    total_pnl_usd = float(path['mtm_pnl_usd'].iloc[-1]) if not path.empty else 0.0
    spread_capture_final = float(path['spread_capture_pnl_usd'].iloc[-1]) if not path.empty else 0.0
    directional_final = float(path['directional_pnl_usd'].iloc[-1]) if not path.empty else 0.0
    pnl_quality_score = abs(spread_capture_final) / max(abs(total_pnl_usd), 1.0)
    pnl_quality_score = float(max(0.0, min(1.0, pnl_quality_score)))
    liquidity_self_sufficiency_score = 100.0 * min(
        1.0,
        0.40 * (fill_rate_pct / 30.0) +
        0.30 * min(1.0, inventory_turnover / 1.6) +
        0.30 * max(0.0, 1.0 - inventory_vol_ratio / 0.40)
    )
    market_stability_score = _stability_score(fill_rate_pct, inventory_vol_ratio, max_inventory_ratio, pnl_quality_score)

    summary = {
        'total_pnl_usd': total_pnl_usd,
        'fills': fills,
        'quote_uptime_pct': 100.0,
        'avg_abs_dislocation_bps': float(path['dislocation_bps'].abs().mean()) if not path.empty else 0.0,
        'max_inventory_usd': max_inventory_usd,
        'launch_notional_usd': launch_notional_usd,
        'spread_bps': spread_bps,
        'effective_spread_bps': effective_spread_bps,
        'fill_rate_pct': fill_rate_pct,
        'inventory_turnover': inventory_turnover,
        'inventory_volatility_usd': inventory_volatility_usd,
        'spread_capture_pnl_usd': spread_capture_final,
        'directional_pnl_usd': directional_final,
        'pnl_quality_score': pnl_quality_score,
        'market_stability_score': market_stability_score,
        'liquidity_self_sufficiency_score': float(liquidity_self_sufficiency_score),
        'liquidity_multiplier': float(liquidity_multiplier),
    }
    return BacktestResult(path=path, summary=summary)


def run_parameter_sweep(
    dislocations: pd.DataFrame,
    spreads_bps: Iterable[float] = (8, 12, 16, 20, 24, 32),
    launch_sizes_usd: Iterable[float] = (1_000_000, 2_000_000, 3_000_000, 5_000_000),
    config: HarnessConfig | None = None,
) -> pd.DataFrame:
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
                'fill_rate_pct': bt.summary['fill_rate_pct'],
                'max_inventory_usd': bt.summary['max_inventory_usd'],
                'inventory_turnover': bt.summary['inventory_turnover'],
                'inventory_volatility_usd': bt.summary['inventory_volatility_usd'],
                'avg_abs_dislocation_bps': bt.summary['avg_abs_dislocation_bps'],
                'market_stability_score': bt.summary['market_stability_score'],
                'liquidity_self_sufficiency_score': bt.summary['liquidity_self_sufficiency_score'],
                'pnl_quality_score': bt.summary['pnl_quality_score'],
            })
    return pd.DataFrame(rows)
