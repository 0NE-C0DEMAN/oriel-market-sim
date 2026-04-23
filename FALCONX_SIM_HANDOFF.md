# FalconX Simulation Harness Handoff

This package extends the uploaded Oriel repo with a developer-ready simulation harness for the FalconX conversation.

## Included in this refactor
1. Real **Kalshi** ingestion using the existing live CPI feed code.
2. Real **Polymarket** ingestion using the existing public adapter.
3. New **ForecastEx** ingestion using the existing best-effort adapter and sample fallback.
4. Explicit **venue normalization layer** before Oriel weighting:
   - Kalshi monthly CPI thresholds → compounded annualized implied YoY via `(1 + m)^12 - 1`
   - Polymarket / ForecastEx pass through unless contract scale implies monthly normalization.
5. Front-end dislocation visualization versus an Oriel-style reference.
6. Parameter sweep heatmap: quoted spread versus backtest PnL.
7. Streamlit tab for interactive screen-share, now with methodology note and normalization columns.

## How to run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## What changed in code
- `oriel_hl_sim/ingestion.py`
  - Added venue-specific normalization functions.
  - Switched Kalshi normalization from simple `m * 12` to compounded annualization.
  - Added ForecastEx ingestion and release-month harmonization.
  - Made normalization metadata explicit in the front-end DataFrame.
- `falconx_sim_tab.py`
  - Added ForecastEx to the dislocation chart.
  - Added normalization note to the UI.
  - Added normalization columns to the snapshot table.
- `tests/test_falconx_sim_harness.py`
  - Added tests for compounded Kalshi normalization and pass-through Polymarket normalization.

## Purpose
This is not the final Hyperliquid production repo. It is the clean extension layer that lets the team discuss the architecture, quoting model, normalization approach, and $3MM launch package with FalconX before hard-wiring the true oracle publisher and deployer stack.
