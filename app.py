"""
Oriel Market Simulation — CPI Curve & Perp Pilot
Standalone Streamlit instance for FalconX demo.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Oriel Market Simulation \u2014 CPI Curve & Perp Pilot",
    page_icon="\u25c8",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ui.css import inject_css
inject_css()

from falconx_sim_tab import render_falconx_sim_tab

st.markdown("""
<div class='oriel-page-head'>
  <span class='oriel-page-title'>Oriel Market Simulation</span>
  <span class='version-chip'>CPI Curve & Perp Pilot</span>
</div>""", unsafe_allow_html=True)

st.markdown(
    "<div style='font-size:0.75rem;color:#6b7f94;margin:4px 0 10px;'>"
    "Simulation + demo layer for Hyperliquid CPI perp listing. Live venue ingestion, dislocation analytics, backtest engine.</div>",
    unsafe_allow_html=True,
)

render_falconx_sim_tab()
