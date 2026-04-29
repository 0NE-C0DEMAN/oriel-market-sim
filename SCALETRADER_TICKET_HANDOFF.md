# ScaleTrader Ticket Generator Handoff

## What changed

Added a demo-only ScaleTrader parameter generator below the existing **Execution Snapshot** dislocation table.

The card is labeled:

> Illustrative ScaleTrader Ticket — Not Routed

It uses the selected dislocation row and produces a ticket-style view with:

- side: Buy YES / Sell YES
- start price
- price increment
- levels
- clip size
- max exposure
- profit-taker offset
- Oriel edge
- Oriel fair value
- contract market price
- liquidity / confidence
- disable conditions

## Files added / modified

- `oriel_hl_sim/scaletrader.py` — pure ticket-generation logic, no routing.
- `falconx_sim_tab.py` — UI card below the Execution Snapshot table.
- `tests/test_falconx_sim_harness.py` — unit tests for Buy YES / Sell YES direction and ticket sizing.

## Direction convention

- Negative dislocation: venue-implied CPI is below Oriel FV → contract treated as cheap → **Buy YES**.
- Positive dislocation: venue-implied CPI is above Oriel FV → contract treated as rich → **Sell YES**.

## Safety / demo guardrail

This is intentionally not wired to IBKR/TWS. It does not authenticate, route, submit, amend, or cancel orders. It only generates an illustrative ScaleTrader-style ticket from Oriel dislocation rows.
