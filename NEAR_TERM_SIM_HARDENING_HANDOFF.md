# Oriel Market Sim — Near-Term Demo Hardening Patch

## Purpose
This patch hardens the illustrative FalconX / ForecastTrader market-simulation demo without converting it into a full production execution backtest.

It addresses six near-term credibility fixes:

1. Methodology / caveat box in the UI.
2. Core Oriel curve wiring via `data/oriel_curve_current.csv`.
3. Core-vs-local reference separation.
4. Leave-one-venue-out dislocation diagnostics.
5. Normalization audit table for raw thresholds, units, and conversion method.
6. Net executable edge and dislocation-compression sensitivity.

## Files changed / added

### Added
- `oriel_hl_sim/core_curve_adapter.py`
  - Loads core Oriel curve output from `data/oriel_curve_current.csv` or `ORIEL_CORE_CURVE_CSV`.
  - Normalizes `target_month` / `release_month` into the sim's month key.
  - Exposes `core_oriel_reference_yoy`, `core_index_level`, `core_std_dev_pct`, and `core_curve_source`.

### Modified
- `oriel_hl_sim/config/markets.py`
  - Adds:
    - `core_curve_csv`
    - `reference_mode` (`core` default; `local_blend` optional)
    - `slippage_buffer_bps`
    - `fee_buffer_bps`

- `oriel_hl_sim/ingestion.py`
  - Builds a reference table with:
    - `core_oriel_reference_yoy`
    - `local_oriel_reference_yoy`
    - selected `oriel_reference_yoy`
    - `reference_source`
  - Adds leave-one-venue-out reference:
    - `loo_oriel_reference_yoy`
    - `loo_dislocation_bps`
  - Adds local/core dislocation fields:
    - `local_dislocation_bps`
    - `core_dislocation_bps`
  - Adds normalization audit helper:
    - `build_normalization_audit_table()`
  - Adjusts Kalshi unit inference so contract text that clearly says YoY is not forced into monthly annualization. This prevents sample/demo YoY rows from being over-annualized.

- `oriel_hl_sim/simulation.py`
  - Uses fee/slippage buffers in simulated executable edge.
  - Adds `net_executable_edge_bps` at path and summary level.

- `falconx_sim_tab.py`
  - Adds methodology caveat box.
  - Adds `Net Edge After Costs` KPI.
  - Adds reference + normalization audit sections.
  - Adds compression sensitivity table for retained dislocation at 100%, 75%, 50%, and 25%.

## Environment variables

Optional overrides:

```bash
ORIEL_CORE_CURVE_CSV=data/oriel_curve_current.csv
ORIEL_SIM_REFERENCE_MODE=core        # core | local_blend
ORIEL_SIM_SLIPPAGE_BUFFER_BPS=8
ORIEL_SIM_FEE_BUFFER_BPS=2
```

## Important positioning
The UI now makes clear that this is an illustrative market-structure harness. It should not be represented as a final production-grade execution backtest.

Suggested investor / allocator language:

> The demo separates normalized venue dislocation from reference-construction artifacts. It defaults to the core Oriel curve where available, shows the local venue blend and leave-one-venue-out diagnostics, and reports net edge after conservative cost buffers. The purpose is to show why a liquidity bootstrap is worth diligence, not to claim the full gross dislocation is directly capturable.

## Developer QA checklist

1. Confirm `data/oriel_curve_current.csv` is exported from the current core Oriel app and has one of:
   - `target_month` + `expected_yoy_pct`
   - `release_month` + `oriel_reference_yoy`
2. Run the app locally:
   ```bash
   streamlit run app.py
   ```
3. Confirm the UI shows:
   - Methodology caveat box
   - Net Edge After Costs KPI
   - Reference + Normalization Audit
   - Dislocation Compression Sensitivity
4. Validate the audit table before FalconX demos. If `reference_source` is `local_blend_fallback`, the core curve file does not include that month.
5. Confirm whether core curve `expected_yoy_pct` is true YoY, annualized MoM, or index-level derived; if not true YoY, rename the core field before relying on bp comparisons.
