# Oriel Market Simulation — CPI Curve & Perp Pilot

Simulation + demo layer for the Hyperliquid CPI perp listing. Designed for the FalconX discussion — not a fork of the core Oriel app.

**Live demo:** [oriel-market-sim.streamlit.app](https://oriel-market-sim.streamlit.app/)

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## What it does

- **Live Data toggle**: sample data by default, flip to live for real Kalshi + Polymarket ingestion
- **Front-end dislocation analytics**: venue-implied YoY vs Oriel reference, scatter + confidence scoring
- **Market-making backtest**: spread-based PnL loop with inventory tracking
- **Parameter sweep heatmap**: quoted spread vs launch notional vs backtest PnL
- **Interactive controls**: spread slider (bp), launch package selector ($MM), live data toggle
- **Oriel design language**: full CSS injection, KPI strips, desk tables, gold-themed charts

## Architecture

```
app.py                          Standalone Streamlit entrypoint
falconx_sim_tab.py              Main renderer (KPI strip, charts, tables, heatmap)
oriel_hl_sim/
  common.py                     Dataclasses (VenueQuote, DislocationRow, etc.)
  config/markets.py             HarnessConfig (env-driven, frozen dataclass)
  ingestion.py                  Kalshi + Polymarket ingest, Oriel reference, dislocations
  simulation.py                 Backtest engine + parameter sweep
venues/                         Venue adapters (shared with core Oriel app)
data/hyperliquid_mvp/           Sample frontend quotes for offline demo
assets/oriel.css                Full Oriel dark theme CSS
ui/                             Shared UI infrastructure (tokens, charts, tables, theme)
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KALSHI_ENABLE_LIVE_CPI` | `false` | Enable live Kalshi feed (or use Live Data toggle) |
| `ORIEL_SIM_MAX_FRONT_MONTHS` | `4` | Max front months to ingest |
| `ORIEL_SIM_BASE_SPREAD_BPS` | `18` | Default quoted spread |
| `ORIEL_SIM_LAUNCH_NOTIONAL_USD` | `3000000` | Default launch package |
| `ORIEL_SIM_INVENTORY_LIMIT_USD` | `750000` | Max inventory exposure |

## Purpose

Clean extension layer for discussing architecture, quoting model, and $3MM launch package with FalconX before hard-wiring the oracle publisher and deployer stack.
