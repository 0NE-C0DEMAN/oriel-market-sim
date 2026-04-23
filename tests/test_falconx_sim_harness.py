from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oriel_hl_sim.ingestion import (
    _annualize_monthly_pct_to_yoy,
    _normalize_threshold,
    load_front_end_market_snapshot,
)
from oriel_hl_sim.simulation import run_backtest, run_parameter_sweep


def test_kalshi_monthly_normalization_uses_compounding():
    out = _annualize_monthly_pct_to_yoy(0.3)
    assert round(out, 4) == round(((1 + 0.003) ** 12 - 1) * 100, 4)
    assert out > 3.6  # should be slightly above simple *12 annualization


def test_polymarket_yoy_passes_through():
    norm, units, method, _ = _normalize_threshold('Polymarket', 2.8, 'Will US CPI exceed 2.8% in Apr 2026?')
    assert norm == 2.8
    assert units == 'yoy_pct'
    assert method == 'pass_through'


def test_falconx_harness_runs_with_live_or_fallback_data():
    front, dis, status = load_front_end_market_snapshot()
    assert len(front) > 0
    assert len(dis) > 0
    assert {'Kalshi', 'Polymarket'}.issubset(set(front['venue'].unique()))
    assert 'normalization_method' in front.columns
    assert 'threshold_units' in front.columns
    bt = run_backtest(dis)
    assert 'total_pnl_usd' in bt.summary
    sweep = run_parameter_sweep(dis)
    assert not sweep.empty
    assert {'spread_bps', 'launch_notional_usd', 'total_pnl_usd'}.issubset(set(sweep.columns))
