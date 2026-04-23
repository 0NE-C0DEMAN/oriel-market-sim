from __future__ import annotations
import sys
sys.path.insert(0, '.')
from oriel_hl_sim.ingestion import load_front_end_market_snapshot
from oriel_hl_sim.simulation import run_backtest, run_parameter_sweep

front, dis, status = load_front_end_market_snapshot()
print('Feed status:', status)
print('Front-end rows:', len(front))
print('Dislocation rows:', len(dis))
print('Backtest summary:', run_backtest(dis).summary)
print(run_parameter_sweep(dis).to_string(index=False))
