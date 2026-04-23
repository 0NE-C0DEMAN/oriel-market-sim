from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from oriel_hl_sim.ingestion import load_front_end_market_snapshot
from oriel_hl_sim.simulation import run_backtest, run_parameter_sweep

def test_falconx_harness_runs_with_live_or_fallback_data():
    front, dis, status = load_front_end_market_snapshot()
    assert len(front) > 0
    assert len(dis) > 0
    bt = run_backtest(dis)
    assert 'total_pnl_usd' in bt.summary
    sweep = run_parameter_sweep(dis)
    assert not sweep.empty
    assert {'spread_bps', 'launch_notional_usd', 'total_pnl_usd'}.issubset(set(sweep.columns))
