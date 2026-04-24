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

- **Three-venue live ingestion (US headline CPI only)**: Kalshi (`KXCPI` series), Polymarket (Gamma API, non-US inflation markets excluded via `exclude_country_keywords`), ForecastEx (CSV pairs feed, `CPIY_` product prefix — filters out Canada/HK/Japan/India/Spain/Singapore/Germany/US-Core)
- **Core Oriel curve wiring (default reference)**: the sim loads `data/oriel_curve_current.csv` exported from the core Oriel app and uses it as the reference for venue dislocation. Local venue-blend is still computed and shown as a diagnostic alongside the core curve so the dislocation can be decomposed into *real market-structure* versus *reference-construction artifact*.
- **Cross-venue normalization** onto a common **normalized implied YoY CPI** basis before Oriel weighting. Kalshi YoY-labeled rows now bypass monthly annualization so sample/demo YoY contracts are not double-counted.
- **Leave-one-venue-out dislocation diagnostics**: each venue's dislocation is also reported against a reference rebuilt without that venue's contribution, so single-venue skew is visible instead of hidden in the blend.
- **Reference + Normalization Audit (tabbed)**: two `st.tabs` under one section so both diligence views share a single header without visual clutter. *Reference Audit* tab shows `reference_source` (core vs local fallback), local / core / LOO references per row, with the three dislocation variants. *Normalization Audit* tab shows raw threshold, units, normalized threshold, and the exact conversion method for every ingested contract so a FalconX diligence review can verify the math line by line. Both tabs render with the gold-accent Oriel desk-table styling to match the rest of the page.
- **Liquidity / stability simulation loop**: spread capture vs directional PnL split, liquidity multiplier, effective spread tightening, inventory mean-reversion. Executable edge subtracts both `slippage_buffer_bps` and `fee_buffer_bps` from the raw dislocation.
- **Net edge after costs (bp)**: reported on every path row and in the KPI strip so gross dislocation vs realistically capturable edge is never conflated.
- **Dislocation compression sensitivity**: sweeps dislocation retained at 100% / 75% / 50% / 25% and reports PnL, Fills, Net Edge, and Stability at each level so the demo directly answers "what if only half of the visible dislocation is real?"
- **Methodology caveat** folded into the existing methodology note above the KPI strip (one muted paragraph, no modal/banner) so the page makes clear this is an illustrative market-structure harness without visually dominating the first screen.
- **Cross-venue contribution panel**: per-month weight breakdown showing how each venue feeds the local Oriel reference (still useful for the venue-blend narrative even when the default reference is the core curve).
- **Execution snapshot**: Kalshi-native threshold ladder vs the cross-venue Oriel reference
- **Front-end dislocation analytics**: venue-implied YoY vs Oriel reference, high-contrast scatter (gold / cyan / green) with liquidity-weighted marker sizes, 11px floor so low-liquidity venues stay visually legible
- **Market-making backtest**: 8-cell KPI strip (PnL, Fills, Fill Rate, Avg Dislocation bp, Net Edge After Costs bp, Max Inventory, Market Stability, Liquidity Sustainability) with ribbon showing `Quoted XX bp → Effective YY bp` so the liquidity tightening/widening is visible at every launch size
- **Parameter sweep heatmap**: quoted spread vs launch notional vs backtest PnL
- **Oriel design language**: full CSS injection, KPI strips, desk tables, gold-themed charts, `automargin` axis titles for clean separation from curves and container walls

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
falconx_sim_tab.py              Main renderer (KPI strip, charts, audit tables, compression sensitivity, heatmap)
oriel_hl_sim/
  common.py                     Dataclasses (VenueQuote, DislocationRow, etc.)
  config/markets.py             HarnessConfig (env-driven, frozen dataclass) incl. core_curve_csv, reference_mode, slippage_buffer_bps, fee_buffer_bps
  core_curve_adapter.py         Loads the core Oriel curve export (data/oriel_curve_current.csv)
  ingestion.py                  Kalshi + Polymarket + ForecastEx ingest, normalization, core-vs-local reference, LOO diagnostics, audit builder
  simulation.py                 Backtest engine + parameter sweep, net executable edge after buffers
venues/                         Venue adapters (shared with core Oriel app)
data/oriel_curve_current.csv    Core Oriel curve export — used as the default reference when present
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
| `ORIEL_CORE_CURVE_CSV` | `data/oriel_curve_current.csv` | Path to the core Oriel curve export used as the sim reference |
| `ORIEL_SIM_REFERENCE_MODE` | `core` | `core` uses the core curve with local blend as fallback; `local_blend` flips the priority |
| `ORIEL_SIM_SLIPPAGE_BUFFER_BPS` | `8` | Slippage deducted from raw dislocation when computing net executable edge |
| `ORIEL_SIM_FEE_BUFFER_BPS` | `2` | Fee deducted from raw dislocation when computing net executable edge |

## Purpose

Clean extension layer for discussing architecture, quoting model, venue normalization, and a $3MM launch package with FalconX before hard-wiring the oracle publisher and deployer stack.
