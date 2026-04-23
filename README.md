# Oriel Market Simulation — CPI Curve & Perp Pilot

Simulation + demo layer for the Hyperliquid CPI perp listing. Designed for the FalconX discussion — not a fork of the core Oriel app.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## What it does

- **Live venue ingestion**: Kalshi + Polymarket CPI contracts via existing adapters, with sample-data fallback
- **Front-end dislocation analytics**: venue-implied YoY vs Oriel reference, scatter + confidence scoring
- **Market-making backtest**: simple spread-based PnL loop with inventory tracking
- **Parameter sweep heatmap**: quoted spread vs launch notional vs backtest PnL
- **Interactive controls**: spread slider, launch package selector, live refresh toggle

## Architecture

```
app.py                          Standalone Streamlit entrypoint
falconx_sim_tab.py              Main renderer (metrics, charts, tables, heatmap)
oriel_hl_sim/
  common.py                     Dataclasses (VenueQuote, DislocationRow, etc.)
  config/markets.py             HarnessConfig (env-driven, frozen dataclass)
  ingestion.py                  Kalshi + Polymarket ingest, Oriel reference compute, dislocation calc
  simulation.py                 Backtest engine + parameter sweep
venues/                         Venue adapters (shared with core Oriel app)
data/hyperliquid_mvp/           Sample frontend quotes for offline demo
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KALSHI_ENABLE_LIVE_CPI` | `false` | Enable live Kalshi feed |
| `ORIEL_SIM_MAX_FRONT_MONTHS` | `4` | Max front months to ingest |
| `ORIEL_SIM_BASE_SPREAD_BPS` | `18` | Default quoted spread |
| `ORIEL_SIM_LAUNCH_NOTIONAL_USD` | `3000000` | Default launch package |
| `ORIEL_SIM_INVENTORY_LIMIT_USD` | `750000` | Max inventory exposure |

## Purpose

This is the clean extension layer that lets the team discuss the architecture, quoting model, and launch package with FalconX before hard-wiring the true oracle publisher and deployer stack.
