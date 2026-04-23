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

- **Live venue ingestion**: Kalshi + Polymarket + ForecastEx, with sample fallback where needed
- **Cross-venue normalization**: all venue contracts are mapped onto a common implied YoY CPI basis before Oriel weighting
- **Front-end dislocation analytics**: venue-implied YoY vs Oriel reference, scatter + confidence scoring
- **Market-making backtest**: spread-based PnL loop with inventory tracking
- **Parameter sweep heatmap**: quoted spread vs launch notional vs backtest PnL
- **Interactive controls**: spread slider (bp), launch package selector ($MM), refresh toggle
- **Oriel design language**: full CSS injection, KPI strips, desk tables, gold-themed charts

## Normalization methodology (current FalconX branch)

- **Kalshi** front-end CPI thresholds are treated as monthly CPI thresholds and converted to annualized implied YoY CPI using:
  - `((1 + m)^12 - 1) * 100`, where `m` is monthly CPI in decimal form.
- **Polymarket** thresholds pass through when the contract language indicates YoY CPI.
- **ForecastEx** thresholds pass through unless contract language or scale implies monthly CPI, in which case the same compounded annualization is used.
- The common implied YoY point is then produced with the existing first-pass bridge:
  - `implied_yoy = normalized_threshold + (probability - 0.5) * 0.8`

## Architecture

```
app.py                          Standalone Streamlit entrypoint
falconx_sim_tab.py              Main renderer (KPI strip, charts, tables, heatmap)
oriel_hl_sim/
  common.py                     Dataclasses (VenueQuote, DislocationRow, etc.)
  config/markets.py             HarnessConfig (env-driven, frozen dataclass)
  ingestion.py                  Kalshi + Polymarket + ForecastEx ingest, normalization, Oriel reference
  simulation.py                 Backtest engine + parameter sweep
venues/                         Venue adapters (shared with core Oriel app)
data/hyperliquid_mvp/           Sample frontend quotes for offline demo
assets/oriel.css                Full Oriel dark theme CSS
ui/                             Shared UI infrastructure (tokens, charts, tables, theme)
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KALSHI_ENABLE_LIVE_CPI` | `false` | Enable live Kalshi feed (or use refresh toggle) |
| `ORIEL_SIM_MAX_FRONT_MONTHS` | `4` | Max front months to ingest |
| `ORIEL_SIM_BASE_SPREAD_BPS` | `18` | Default quoted spread |
| `ORIEL_SIM_LAUNCH_NOTIONAL_USD` | `3000000` | Default launch package |
| `ORIEL_SIM_INVENTORY_LIMIT_USD` | `750000` | Max inventory exposure |
| `POLYMARKET_REQUEST_TIMEOUT_SECONDS` | `3` | Polymarket request timeout |
| `FORECASTEX_REQUEST_TIMEOUT_SECONDS` | `3` | ForecastEx request timeout |

## Purpose

Clean extension layer for discussing architecture, quoting model, venue normalization, and a $3MM launch package with FalconX before hard-wiring the oracle publisher and deployer stack.
