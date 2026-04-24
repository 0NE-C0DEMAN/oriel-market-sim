from __future__ import annotations

import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from oriel_hl_sim.config.markets import HarnessConfig
from oriel_hl_sim.ingestion import load_front_end_market_snapshot, compute_venue_contribution_summary, build_normalization_audit_table
from oriel_hl_sim.simulation import run_backtest, run_parameter_sweep
from ui.charts import _layout, _xaxis, _yaxis
from ui.plotly_theme import PLOTLY_CONFIG
from ui.tables import _plotly_desk_table
from ui.tokens import (
    BG_ELEVATED, DESK_TABLE_HEADER_PX, DESK_TABLE_PAD_PX, DESK_TABLE_ROW_PX,
    GOLD, NEGATIVE, POSITIVE, SERIES2, SERIES_MUTE, TEXT_MUTED, TEXT_SEC, WARNING,
)

_CACHE_TTL_SECONDS = 60  # auto-refresh every 60s


def _fmt0(v):
    return f"${v:,.0f}"


def _score_color(score: float) -> str:
    """Traffic-light color for 0-100 stability/sustainability scores."""
    if score >= 70:
        return POSITIVE
    if score >= 50:
        return WARNING
    return NEGATIVE


def render_falconx_sim_tab():
    cfg = HarnessConfig()

    # ── Controls row ──────────────────────────────────────────────────────
    ctl1, ctl2, ctl3 = st.columns([1, 1, 1], gap="medium")
    with ctl1:
        st.markdown("<div class='ctrl-vd-label'>Quoted Spread (bp)</div>", unsafe_allow_html=True)
        spread_bps = st.slider("Spread", 4, 40, int(cfg.base_spread_bps), 2,
                               key="sim_spread", label_visibility="collapsed")
    with ctl2:
        st.markdown("<div class='ctrl-vd-label'>Launch Package ($MM)</div>", unsafe_allow_html=True)
        launch_notional_mm = st.select_slider("Launch", options=[1, 2, 3, 5], value=3,
                                              key="sim_launch", label_visibility="collapsed")
    with ctl3:
        st.markdown("<div class='ctrl-vd-label' style='margin-bottom:6px;'>&nbsp;</div>", unsafe_allow_html=True)
        refresh = st.checkbox("Refresh live venue snapshot", value=False, key="sim_refresh",
                              help="By default Streamlit cache is used for responsiveness.")

    import os
    os.environ["KALSHI_ENABLE_LIVE_CPI"] = "true"

    if refresh:
        st.cache_data.clear()

    # TTL bust: integer bucket changes every _CACHE_TTL_SECONDS so Streamlit
    # re-runs the ingestion automatically on the next interaction after expiry.
    ttl_bust = int(time.time() // _CACHE_TTL_SECONDS)
    front_df, dislocations, status = load_front_end_market_snapshot(cfg, _ttl_bust=ttl_bust)

    # ── Feed status badge ─────────────────────────────────────────────────
    feed_parts = status.split(" | ")
    badges = ""
    for part in feed_parts:
        if "LIVE" in part:
            badges += f"<span style='font-size:0.64rem;font-weight:700;padding:3px 8px;border-radius:4px;background:rgba(34,197,94,0.12);color:{POSITIVE};margin-right:6px;'>{part}</span>"
        elif "FALLBACK" in part or "AUGMENTED" in part:
            badges += f"<span style='font-size:0.64rem;font-weight:700;padding:3px 8px;border-radius:4px;background:rgba(245,158,11,0.12);color:{WARNING};margin-right:6px;'>{part}</span>"
        else:
            badges += f"<span style='font-size:0.64rem;font-weight:600;padding:3px 8px;border-radius:4px;background:rgba(30,45,66,0.5);color:{TEXT_MUTED};margin-right:6px;'>{part}</span>"
    st.markdown(f"<div style='margin:6px 0 10px;'>{badges}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.69rem;color:{TEXT_MUTED};margin:-2px 0 14px;line-height:1.55;'>"
        "Cross-venue view: <b>normalized implied YoY CPI</b>. Venue contracts are normalized onto a common annualized implied CPI basis for comparison. "
        "Kalshi monthly thresholds use compounded annualization ((1+m)^12 \u2212 1); Polymarket and ForecastEx pass through unless contract scale implies monthly normalization. "
        "Reference defaults to the Oriel core curve where available, with the local venue blend shown as a diagnostic. "
        f"<span style='color:{TEXT_SEC};'>PnL is indicative and nets spread, fee, and slippage buffers; this is an illustrative market-structure harness, not a production execution backtest.</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if front_df.empty:
        st.warning("No front-end venue data available. Check venue connectivity or fallback sample data.")
        return

    bt = run_backtest(dislocations, spread_bps=spread_bps,
                      launch_notional_usd=launch_notional_mm * 1_000_000, config=cfg)
    s = bt.summary

    # ── KPI strip (P2 liquidity upgrade: 7 cells incl. bp metrics) ────────
    pnl_col = POSITIVE if s["total_pnl_usd"] >= 0 else NEGATIVE
    stability_col = _score_color(s.get("market_stability_score", 0.0))
    sustain_col = _score_color(s.get("liquidity_self_sufficiency_score", 0.0))
    eff_spread_bp = s.get("effective_spread_bps", float(spread_bps))
    avg_disl_bp = s.get("avg_abs_dislocation_bps", 0.0)
    avg_net_edge_bp = s.get("avg_net_executable_edge_bps", 0.0)
    st.markdown(f"""
    <div class='kpi-strip-wrap' style='margin-bottom:10px'>
      <div class='kpi-strip-ribbon'>SIMULATION BACKTEST \u00b7 Quoted {spread_bps} bp \u2192 Effective {eff_spread_bp:.1f} bp \u00b7 ${launch_notional_mm}MM launch</div>
      <div class='kpi-strip' style='display:grid;grid-template-columns:repeat(8,minmax(0,1fr))'>
        <div class='kpi-cell'><div class='kpi-micro'>Backtest PnL</div>
          <div class='kpi-value kpi-value--lead' style='color:{pnl_col};'>{_fmt0(s["total_pnl_usd"])}</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Fills</div>
          <div class='kpi-value'>{s["fills"]:,}</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Fill Rate</div>
          <div class='kpi-value'>{s.get("fill_rate_pct", 0.0):.1f}%</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Avg Dislocation</div>
          <div class='kpi-value'>{avg_disl_bp:.1f}<span style='font-size:0.68em;color:{TEXT_MUTED};font-weight:500;margin-left:3px;'>bp</span></div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Net Edge After Costs</div>
          <div class='kpi-value'>{avg_net_edge_bp:.1f}<span style='font-size:0.68em;color:{TEXT_MUTED};font-weight:500;margin-left:3px;'>bp</span></div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Max Inventory</div>
          <div class='kpi-value'>{_fmt0(s["max_inventory_usd"])}</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Market Stability</div>
          <div class='kpi-value' style='color:{stability_col};'>{s.get("market_stability_score", 0.0):.0f}</div></div>
        <div class='kpi-cell'><div class='kpi-micro'>Liquidity Sustainability</div>
          <div class='kpi-value' style='color:{sustain_col};'>{s.get("liquidity_self_sufficiency_score", 0.0):.0f}</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Charts row ────────────────────────────────────────────────────────
    col_l, col_r = st.columns([1.2, 1], gap="medium")

    with col_l:
        st.markdown("<div class='shdr'>Venue Dislocations vs Oriel Reference</div>", unsafe_allow_html=True)
        fig = go.Figure()
        # Bright, high-contrast palette: gold (Kalshi exec), cyan (Polymarket), green (ForecastEx).
        # Polymarket gets a brighter cyan than SERIES2 so it's clearly distinct against the dark surface.
        venue_palette = [
            ("Kalshi",     GOLD),
            ("Polymarket", "#5CC8FF"),
            ("ForecastEx", "#22C55E"),
        ]
        for venue, color in venue_palette:
            sub = dislocations[dislocations["venue"] == venue]
            if sub.empty:
                continue
            # Size floor 11 so even zero-liquidity dots stay visually legible,
            # liquidity scaling adds up to ~14 more on top for depth cueing.
            sizes = sub["liquidity_score"].clip(lower=0.0, upper=1.0) * 14.0 + 11.0
            fig.add_trace(go.Scatter(
                x=sub["release_month"], y=sub["dislocation_bps"],
                mode="markers", name=venue,
                marker=dict(
                    color=color, size=sizes, opacity=0.7,
                    line=dict(color=color, width=1),
                ),
                hovertemplate=f"<b>{venue}</b><br>%{{x}}<br>Dislocation: <b>%{{y:.1f}} bp</b><extra></extra>",
            ))
        fig.add_hline(y=0, line_color=SERIES_MUTE, line_dash="dash", line_width=1)
        fig.update_layout(**_layout(
            height=340,
            margin=dict(l=78, r=32, t=32, b=72),
            xaxis=_xaxis(title=dict(text="Release Month", font=dict(color=TEXT_SEC, size=11), standoff=14),
                         automargin=True),
            yaxis=_yaxis(title=dict(text="Dislocation (bp)", font=dict(color=TEXT_SEC, size=11), standoff=14),
                         automargin=True),
        ))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="sim_disl")

    with col_r:
        st.markdown("<div class='shdr'>Backtest Path \u00b7 PnL + Inventory</div>", unsafe_allow_html=True)
        pnl_fig = go.Figure()
        pnl_fig.add_trace(go.Scatter(
            x=bt.path["step"], y=bt.path["mtm_pnl_usd"],
            mode="lines", name="MTM PnL",
            line=dict(color=GOLD, width=2),
            hovertemplate="Step %{x}<br>PnL: $%{y:,.0f}<extra></extra>",
        ))
        pnl_fig.add_trace(go.Scatter(
            x=bt.path["step"], y=bt.path["inventory_usd"],
            mode="lines", name="Inventory ($)", yaxis="y2",
            line=dict(color=SERIES2, width=1.5, dash="dash"),
            hovertemplate="Step %{x}<br>Inventory: $%{y:,.0f}<extra></extra>",
        ))
        pnl_fig.update_layout(**_layout(
            height=340,
            margin=dict(l=78, r=78, t=32, b=72),
            xaxis=_xaxis(title=dict(text="Step", font=dict(color=TEXT_SEC, size=11), standoff=14),
                         automargin=True),
            yaxis=_yaxis(title=dict(text="PnL ($)", font=dict(color=TEXT_SEC, size=11), standoff=14),
                         automargin=True),
        ))
        pnl_fig.update_layout(
            yaxis2=dict(
                title=dict(text="Inventory ($)", font=dict(color=TEXT_SEC, size=11), standoff=14),
                overlaying="y", side="right",
                showgrid=False, tickfont=dict(color=TEXT_SEC), automargin=True,
            ),
        )
        st.plotly_chart(pnl_fig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="sim_pnl")

    # ── Cross-venue contribution summary ─────────────────────────────────
    venue_summary = compute_venue_contribution_summary(
        front_df, dislocations[["release_month", "oriel_reference_yoy"]].drop_duplicates()
    )
    st.markdown("<div class='shdr oriel-section-gap'>Cross-Venue Contribution</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.69rem;color:{TEXT_MUTED};margin:-2px 0 8px;'>"
        "Shows how each venue contributes upstream to the Oriel reference by release month. "
        "The execution-facing ladder below remains Kalshi-native where available.</div>",
        unsafe_allow_html=True,
    )
    vshow_cols = ["release_month", "venue", "implied_yoy", "oriel_reference_yoy",
                  "weight_pct", "liquidity_score", "confidence_score"]
    vshow = venue_summary[vshow_cols].copy() if not venue_summary.empty else pd.DataFrame(columns=vshow_cols)
    for c in ["implied_yoy", "oriel_reference_yoy", "liquidity_score", "confidence_score"]:
        if c in vshow.columns:
            vshow[c] = vshow[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "\u2014")
    if "weight_pct" in vshow.columns:
        vshow["weight_pct"] = vshow["weight_pct"].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "\u2014")
    vtfig = _plotly_desk_table(vshow, gold_column="weight_pct")
    vcontent_h = DESK_TABLE_HEADER_PX + len(vshow) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    vviewport_h = DESK_TABLE_HEADER_PX + min(len(vshow), 6) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    vtfig.update_layout(height=vcontent_h)
    with st.container(height=vviewport_h, border=False, key="scroll_sim_venue_contrib"):
        st.plotly_chart(vtfig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="sim_venue_contrib_tbl")

    # ── Reference audit + normalization table (tabbed) ────────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Reference + Normalization Audit</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.69rem;color:{TEXT_MUTED};margin:-2px 0 8px;'>"
        "Designed to answer the first FalconX diligence question: is the dislocation real or a convention artifact?</div>",
        unsafe_allow_html=True,
    )
    ref_tab, norm_tab = st.tabs(["Reference Audit", "Normalization Audit"])

    _audit_viewport_h = DESK_TABLE_HEADER_PX + 6 * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX

    with ref_tab:
        st.markdown(
            f"<div style='font-size:0.69rem;color:{TEXT_MUTED};margin:6px 0 8px;'>"
            "Per-row comparison of the core Oriel reference, local venue blend, and leave-one-venue-out reference. "
            "Dislocation columns show how far each venue quote sits from each reference variant.</div>",
            unsafe_allow_html=True,
        )
        audit_cols = ["release_month", "venue", "reference_source", "implied_yoy", "oriel_reference_yoy",
                      "core_oriel_reference_yoy", "local_oriel_reference_yoy", "loo_oriel_reference_yoy",
                      "dislocation_bps", "core_dislocation_bps", "loo_dislocation_bps", "net_executable_edge_bps"]
        audit = dislocations[[c for c in audit_cols if c in dislocations.columns]].copy()
        st.dataframe(audit, use_container_width=True, hide_index=True, height=_audit_viewport_h)

    with norm_tab:
        st.markdown(
            f"<div style='font-size:0.69rem;color:{TEXT_MUTED};margin:6px 0 8px;'>"
            "Raw contract threshold, declared units, the normalized threshold used downstream, and the exact conversion method per contract. "
            "Verifies the math line by line for every ingested row.</div>",
            unsafe_allow_html=True,
        )
        norm = build_normalization_audit_table(front_df)
        norm_show_cols = ["release_month", "venue", "source_status", "raw_threshold", "threshold_units",
                          "normalized_threshold", "normalization_method", "mid", "implied_yoy", "market_id"]
        norm_show = norm[[c for c in norm_show_cols if c in norm.columns]].copy()
        st.dataframe(norm_show, use_container_width=True, hide_index=True, height=_audit_viewport_h)

    # ── Execution snapshot (Kalshi-native rows vs cross-venue reference) ──
    st.markdown("<div class='shdr oriel-section-gap'>Execution Snapshot</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:0.69rem;color:{TEXT_MUTED};margin:-2px 0 8px;'>"
        "Kalshi threshold rows shown against the cross-venue Oriel reference. "
        "Polymarket and ForecastEx are incorporated upstream in normalization and reference weighting.</div>",
        unsafe_allow_html=True,
    )
    show_cols = ["release_month", "venue", "implied_yoy", "oriel_reference_yoy",
                 "dislocation_bps", "liquidity_score", "confidence_score", "quote_age_seconds", "market_id"]
    show = dislocations[show_cols].copy()
    show = show[show["venue"].eq("Kalshi")] if (show["venue"] == "Kalshi").any() else show
    for c in ["implied_yoy", "oriel_reference_yoy", "dislocation_bps", "liquidity_score", "confidence_score"]:
        show[c] = show[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "\u2014")
    tfig = _plotly_desk_table(show, gold_column="dislocation_bps")
    content_h = DESK_TABLE_HEADER_PX + len(show) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    viewport_h = DESK_TABLE_HEADER_PX + min(len(show), 6) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    tfig.update_layout(height=content_h)
    with st.container(height=viewport_h, border=False, key="scroll_sim_snap"):
        st.plotly_chart(tfig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="sim_snap_tbl")

    # ── Heatmap (Blues colorscale matching Chris's original) ─────────────
    st.markdown("<div class='shdr oriel-section-gap'>Spread vs PnL \u00b7 Parameter Sweep</div>", unsafe_allow_html=True)
    sweep = run_parameter_sweep(dislocations, config=cfg)
    heat = sweep.pivot(index="launch_notional_usd", columns="spread_bps", values="total_pnl_usd")
    hfig = go.Figure(data=go.Heatmap(
        z=heat.values,
        x=[f"{int(c)} bp" for c in heat.columns],
        y=[f"${int(r/1e6)}MM" for r in heat.index],
        colorscale=[[0, "#0e1420"], [0.3, "#1a3050"], [0.6, "#2a5a8a"], [1.0, GOLD]],
        zmin=0,
        hovertemplate="Spread: %{x}<br>Launch: %{y}<br>PnL: $%{z:,.0f}<extra></extra>",
        texttemplate="$%{z:,.0f}",
        textfont=dict(size=11, color="#e6edf3", family="DM Mono, monospace"),
    ))
    hfig.update_layout(**_layout(
        height=320,
        margin=dict(l=92, r=44, t=32, b=72),
        xaxis=_xaxis(title=dict(text="Quoted Spread", font=dict(color=TEXT_SEC, size=11), standoff=14),
                     automargin=True),
        yaxis=_yaxis(title=dict(text="Launch Package", font=dict(color=TEXT_SEC, size=11), standoff=14),
                     automargin=True),
    ))
    st.plotly_chart(hfig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="sim_heat")

    # ── Dislocation compression sensitivity ──────────────────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Dislocation Compression Sensitivity</div>", unsafe_allow_html=True)
    comp_rows = []
    for pct in [1.00, 0.75, 0.50, 0.25]:
        d2 = dislocations.copy()
        if not d2.empty and "dislocation_bps" in d2.columns:
            d2["implied_yoy"] = d2["oriel_reference_yoy"] + ((d2["implied_yoy"] - d2["oriel_reference_yoy"]) * pct)
            d2["dislocation_bps"] = d2["dislocation_bps"] * pct
        bt2 = run_backtest(d2, spread_bps=spread_bps, launch_notional_usd=launch_notional_mm * 1_000_000, config=cfg)
        comp_rows.append({
            "Dislocation Retained": f"{pct*100:.0f}%",
            "Avg Dislocation": f"{bt2.summary.get('avg_abs_dislocation_bps', 0):.1f} bp",
            "Net Edge": f"{bt2.summary.get('avg_net_executable_edge_bps', 0):.1f} bp",
            "PnL": f"${bt2.summary.get('total_pnl_usd', 0):,.0f}",
            "Fills": f"{bt2.summary.get('fills', 0):,}",
            "Stability": f"{bt2.summary.get('market_stability_score', 0):.0f}",
        })
    comp = pd.DataFrame(comp_rows)
    cfig = _plotly_desk_table(comp, gold_column="PnL")
    cfig.update_layout(height=DESK_TABLE_HEADER_PX + len(comp) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX)
    st.plotly_chart(cfig, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="sim_compression_sensitivity")

    # ── Sweep table (scrollable, 6-row viewport) ─────────────────────────
    st.markdown("<div class='shdr oriel-section-gap'>Sweep Detail</div>", unsafe_allow_html=True)
    sweep_show = sweep.copy()
    sweep_show["total_pnl_usd"] = sweep_show["total_pnl_usd"].map(lambda x: f"${x:,.0f}")
    sweep_show["max_inventory_usd"] = sweep_show["max_inventory_usd"].map(lambda x: f"${x:,.0f}")
    sweep_show["launch_notional_usd"] = sweep_show["launch_notional_usd"].map(lambda x: f"${x/1e6:.0f}MM")
    sweep_show["spread_bps"] = sweep_show["spread_bps"].map(lambda x: f"{x:.0f} bp")
    sweep_show["avg_abs_dislocation_bps"] = sweep_show["avg_abs_dislocation_bps"].map(lambda x: f"{x:.1f}")
    tfig2 = _plotly_desk_table(sweep_show, gold_column="total_pnl_usd")
    content_h2 = DESK_TABLE_HEADER_PX + len(sweep_show) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    viewport_h2 = DESK_TABLE_HEADER_PX + min(len(sweep_show), 6) * DESK_TABLE_ROW_PX + DESK_TABLE_PAD_PX
    tfig2.update_layout(height=content_h2)
    with st.container(height=viewport_h2, border=False, key="scroll_sim_sweep"):
        st.plotly_chart(tfig2, use_container_width=True, config=PLOTLY_CONFIG, theme=None, key="sim_sweep_tbl")

    st.markdown(
        f"<div style='font-size:0.68rem;color:{TEXT_MUTED};margin-top:8px;'>"
        "Simulation layer for FalconX discussion. This branch adds explicit venue normalization, ForecastEx ingestion, and a common implied YoY CPI comparison framework. Not the final Hyperliquid production repo \u2014 "
        "designed to discuss architecture, quoting model, and launch package before hard-wiring the oracle publisher.</div>",
        unsafe_allow_html=True,
    )
