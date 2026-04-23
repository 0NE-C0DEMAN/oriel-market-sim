# FalconX Simulation Harness Handoff

This package extends the uploaded Oriel repo with a developer-ready simulation harness for the FalconX conversation.

## Included
1. Real Kalshi ingestion using existing live CPI feed code.
2. Real Polymarket ingestion using existing public adapter.
3. Front-end dislocation visualization versus an Oriel-style reference.
4. Parameter sweep heatmap: quoted spread versus backtest PnL.
5. Streamlit tab for interactive screen-share.

## How to run
```bash
pip install -r requirements.txt
streamlit run app.py
```
Open the new **FalconX Simulation Harness** tab.

## Purpose
This is not the final Hyperliquid production repo. It is the clean extension layer that lets the team discuss the architecture, quoting model, and $3MM launch package with FalconX before hard-wiring the true oracle publisher and deployer stack.
