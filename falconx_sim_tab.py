from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from oriel_hl_sim.config.markets import HarnessConfig
from oriel_hl_sim.ingestion import load_front_end_market_snapshot
from oriel_hl_sim.simulation import run_backtest, run_parameter_sweep
from ui.plotly_theme import apply_oriel_theme


def _metric_row(summary: dict):
    c1, c2, c3, c4 = st.columns(4, gap='medium')
    c1.metric('Backtest PnL', f"${summary['total_pnl_usd']:,.0f}")
    c2.metric('Fills', f"{summary['fills']:,}")
    c3.metric('Max inventory', f"${summary['max_inventory_usd']:,.0f}")
    c4.metric('Avg abs dislocation', f"{summary['avg_abs_dislocation_bps']:.1f} bp")


def render_falconx_sim_tab():
    st.markdown("<div class='shdr shdr-major oriel-section-gap'>FalconX Simulation Harness</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='note-box'>Live venue ingestion for Kalshi + Polymarket, front-end dislocation analytics, "
        "spread-vs-PnL parameter sweep, and a simple market-making/backtest loop designed for the FalconX discussion.</div>",
        unsafe_allow_html=True,
    )

    cfg = HarnessConfig()
    ctl1, ctl2, ctl3 = st.columns([1,1,1], gap='medium')
    with ctl1:
        spread_bps = st.slider('Quoted spread (bp)', 4, 40, int(cfg.base_spread_bps), 2)
    with ctl2:
        launch_notional_mm = st.select_slider('Launch package ($MM)', options=[1,2,3,5], value=3)
    with ctl3:
        refresh = st.checkbox('Refresh live venue snapshot', value=False, help='By default Streamlit cache is used for responsiveness.')

    if refresh:
        st.cache_data.clear()

    front_df, dislocations, status = load_front_end_market_snapshot(cfg)
    st.caption(f"Feed status: {status}")

    if front_df.empty:
        st.warning('No front-end venue data available. Check venue connectivity or fallback sample data.')
        return

    bt = run_backtest(dislocations, spread_bps=spread_bps, launch_notional_usd=launch_notional_mm * 1_000_000, config=cfg)
    _metric_row(bt.summary)

    col_l, col_r = st.columns([1.2, 1], gap='medium')
    with col_l:
        fig = px.scatter(
            dislocations,
            x='release_month', y='dislocation_bps', color='venue', size='liquidity_score',
            hover_data=['market_id','question','implied_yoy','oriel_reference_yoy','quote_age_seconds'],
            title='Front-end venue dislocations vs Oriel reference (bp)'
        )
        apply_oriel_theme(fig)
        fig.add_hline(y=0, line_dash='dash')
        st.plotly_chart(fig, width='stretch', theme=None)
    with col_r:
        pnl_fig = go.Figure()
        pnl_fig.add_trace(go.Scatter(x=bt.path['step'], y=bt.path['mtm_pnl_usd'], mode='lines', name='MTM PnL'))
        pnl_fig.add_trace(go.Scatter(x=bt.path['step'], y=bt.path['inventory_usd'], mode='lines', name='Inventory ($)', yaxis='y2'))
        pnl_fig.update_layout(
            title='Backtest path: PnL + inventory',
            yaxis=dict(title='PnL ($)'),
            yaxis2=dict(title='Inventory ($)', overlaying='y', side='right'),
        )
        apply_oriel_theme(pnl_fig)
        st.plotly_chart(pnl_fig, width='stretch', theme=None)

    st.markdown("<div class='shdr'>Venue snapshot</div>", unsafe_allow_html=True)
    show_cols = ['release_month','venue','implied_yoy','oriel_reference_yoy','dislocation_bps','liquidity_score','confidence_score','quote_age_seconds','market_id']
    st.dataframe(dislocations[show_cols], width='stretch', hide_index=True)

    st.markdown("<div class='shdr'>Spread vs PnL heatmap</div>", unsafe_allow_html=True)
    sweep = run_parameter_sweep(dislocations, config=cfg)
    heat = sweep.pivot(index='launch_notional_usd', columns='spread_bps', values='total_pnl_usd')
    hfig = px.imshow(
        heat,
        text_auto='.0f',
        aspect='auto',
        labels=dict(x='Spread (bp)', y='Launch package ($)', color='PnL ($)'),
        title='Parameter sweep: spread vs PnL'
    )
    apply_oriel_theme(hfig)
    st.plotly_chart(hfig, width='stretch', theme=None)

    st.markdown("<div class='shdr'>Sweep table</div>", unsafe_allow_html=True)
    st.dataframe(sweep, width='stretch', hide_index=True)
