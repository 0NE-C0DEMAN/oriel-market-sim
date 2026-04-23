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

# Hide Streamlit chrome
st.markdown("""
<style>
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

from falconx_sim_tab import render_falconx_sim_tab

st.markdown(
    "<h2 style='margin-bottom:2px;'>Oriel Market Simulation</h2>"
    "<p style='color:#6b7f94;font-size:0.85rem;margin-top:0;'>CPI Curve & Perp Pilot \u00b7 FalconX Discussion Layer</p>",
    unsafe_allow_html=True,
)

render_falconx_sim_tab()
