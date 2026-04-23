# Oriel Hyperliquid MVP Simulation Harness

This package upgrades the FalconX discussion harness beyond a toy simulator.

## What it adds
- Real Kalshi ingestion via the existing `venues.kalshi.live_data` stack
- Real Polymarket ingestion via the existing `venues.polymarket.client` adapter
- Front-end dislocation analytics vs an Oriel-style governed reference
- Market-making / quoting backtest loop parameterized by spread and launch package size
- Streamlit dashboard tab for live discussion with FalconX

## Files
- `oriel_hl_sim/ingestion.py` — venue normalization + front-end reference/dislocation view
- `oriel_hl_sim/simulation.py` — quoting loop, inventory/PnL path, parameter sweep
- `tabs/falconx_sim_tab.py` — interactive Streamlit dashboard

## Notes
- This is intentionally modular so the production Hyperliquid market adapter, oracle publisher, and market-ops console can be wired in after FalconX feedback.
- When live venue endpoints are unavailable, the dashboard falls back to `data/hyperliquid_mvp/sample_frontend_quotes.csv`.
