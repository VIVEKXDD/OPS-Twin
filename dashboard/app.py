"""
OPS-TWIN: Lending Operations Business Intelligence & Decision Support Platform
==============================================================================
Production Streamlit Application delivering:
  - 12 Core Lending Operations KPIs (Credit Risk, Funding, Collections, Capacity)
  - Historical Trend Sparklines & Anomaly Alerts
  - Root-Cause Diagnostic Engine (surfacing the authentic 2008 Financial Crisis shock)
  - 4-Quarter Time-Series Forecasting & Interactive Loan-Level Default Underwriting
  - 5 Interactive What-If Scenario Simulation Engines with Automated Recommendations
  - Star-Schema & DAX Governance Reference
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
from pathlib import Path

# Set Page Config
st.set_page_config(
    page_title="OPS-TWIN | Lending Operations BI",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import analytical modules
BASE_DIR = Path(__file__).resolve().parent.parent
import sys
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from analysis.trends import (
    get_monthly_trends, detect_degraded_kpis,
    get_grade_cohort_trends, get_state_throughput_trends
)
from analysis.root_cause import run_full_root_cause_diagnosis
from analysis.predictive import (
    forecast_portfolio_kpis, train_default_classifier, score_single_loan
)
from analysis.what_if import (
    simulate_underwriting_tightening,
    simulate_risk_pricing_adjustment,
    simulate_funding_policy,
    simulate_collections_optimization,
    simulate_verification_policy_shift
)
from dashboard.components import (
    render_kpi_card, render_recommendation, format_currency,
    format_percent, create_sparkline, PLOTLY_LAYOUT,
    COLOR_CYAN, COLOR_EMERALD, COLOR_AMBER, COLOR_ROSE, COLOR_PURPLE, COLOR_SLATE
)

# Load CSS
css_file = BASE_DIR / "dashboard" / "styles.css"
if css_file.exists():
    with open(css_file, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Database helper for overview filtering
@st.cache_data(ttl=600)
def load_base_data():
    conn = sqlite3.connect(str(BASE_DIR / "data" / "processed" / "ops_twin.db"))
    df_monthly = pd.read_sql_query("SELECT * FROM monthly_kpi_rollup ORDER BY metric_month ASC", conn)
    df_states = pd.read_sql_query("SELECT DISTINCT addr_state FROM borrowers ORDER BY addr_state", conn)
    conn.close()
    return df_monthly, df_states["addr_state"].tolist()


df_monthly, all_states = load_base_data()


# ==============================================================================
# SIDEBAR NAVIGATION
# ==============================================================================

with st.sidebar:
    st.markdown("## 🏦 **OPS-TWIN**")
    st.markdown(
        "<div style='font-size:0.8rem; color:#94a3b8; margin-top:-10px; margin-bottom:15px;'>"
        "Lending Operations Decision Support Platform<br>"
        "<span style='color:#38bdf8; font-weight:600;'>Portfolio Intelligence & Underwriting</span>"
        "</div>",
        unsafe_allow_html=True
    )
    st.markdown("---")

    page = st.radio(
        "Navigation",
        [
            "📊 Executive Portfolio Overview",
            "🔍 Root-Cause Analysis & 2008 Crisis",
            "📈 Predictive Forecasts & Underwriting",
            "🎛️ What-If Decision Simulator (5)",
            "📚 Methodology, Proxies & DAX"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("### ⚙️ Filter Controls")
    
    # State multi-select filter
    selected_states = st.multiselect(
        "Borrower Region / States",
        options=["ALL"] + all_states,
        default=["ALL"]
    )

    # Date range filter
    all_months = df_monthly["metric_month"].tolist() if not df_monthly.empty else []
    if len(all_months) >= 2:
        date_range = st.select_slider(
            "Origination Period Range",
            options=all_months,
            value=(all_months[0], all_months[-1])
        )
    else:
        date_range = (None, None)

    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.75rem; color:#64748b;'>"
        "Data Source: Authentic LendingClub Portfolio (2007–2015)<br>"
        "Normalized Relational Schema (SQLite)<br>"
        "Production SQL CTEs & Window Functions"
        "</div>",
        unsafe_allow_html=True
    )


# Filter monthly dataframe by selected date range
if not df_monthly.empty and date_range[0] and date_range[1]:
    df_filtered = df_monthly[
        (df_monthly["metric_month"] >= date_range[0]) &
        (df_monthly["metric_month"] <= date_range[1])
    ].copy()
else:
    df_filtered = df_monthly.copy()


# ==============================================================================
# PAGE 1: EXECUTIVE PORTFOLIO OVERVIEW (12 CORE KPIS)
# ==============================================================================

if page == "📊 Executive Portfolio Overview":
    st.markdown(
        "<div class='section-header'>"
        "<div>"
        "<div class='section-title'>📊 Executive Portfolio & Lending Operations Cockpit</div>"
        "<div class='section-subtitle'>Continuous monitoring of 12 core lending-operations KPIs across credit risk, funding, collections, and capacity</div>"
        "</div>"
        f"<div class='badge badge-info'>Active Window: {date_range[0]} to {date_range[1]}</div>"
        "</div>",
        unsafe_allow_html=True
    )

    if df_filtered.empty:
        st.warning("No operational records match the selected filters.")
        st.stop()

    # Aggregate Core KPI Snapshot
    latest = df_filtered.iloc[-1]
    prev = df_filtered.iloc[-2] if len(df_filtered) > 1 else latest
    
    tot_vol = df_filtered["total_funded_volume"].sum()
    tot_apps = df_filtered["total_applications"].sum()
    weighted_def = (df_filtered["default_rate"] * df_filtered["total_applications"]).sum() / tot_apps
    weighted_delinq = (df_filtered["delinquency_rate"] * df_filtered["total_applications"]).sum() / tot_apps
    avg_fulfillment = df_filtered["funding_fulfillment_rate"].mean()
    avg_apr = df_filtered["avg_interest_rate"].mean()
    tot_charged_off = df_filtered["total_charged_off_prncp"].sum()
    tot_recov = df_filtered["total_recoveries"].sum()
    weighted_recov_rate = (tot_recov * 100.0 / tot_charged_off) if tot_charged_off > 0 else 0.0
    avg_collection_cost = df_filtered["collection_cost_ratio"].mean()
    avg_unverified = df_filtered["unverified_backlog_share"].mean()
    latest_mom_growth = latest.get("mom_volume_growth_pct", 0.0)

    # --------------------------------------------------------------------------
    # 12 Core KPIs in 4 Thematic Operational Rows
    # --------------------------------------------------------------------------

    # Row 1: Credit Risk KPIs
    st.markdown("#### 🛡️ I. Credit Risk Performance")
    c1, c2, c3 = st.columns(3)
    with c1:
        def_delta = latest["default_rate"] - prev["default_rate"]
        render_kpi_card(
            title="1. Default / Charge-off Rate",
            value=format_percent(weighted_def),
            delta_str=f"{def_delta:+.2f}% MoM",
            delta_direction="positive" if def_delta <= 0 else "negative",
            badge_text="Credit Risk",
            badge_class="badge-critical" if weighted_def > 15 else "badge-success"
        )
    with c2:
        delinq_delta = latest["delinquency_rate"] - prev["delinquency_rate"]
        render_kpi_card(
            title="2. Delinquency Rate (30+ DPD)",
            value=format_percent(weighted_delinq),
            delta_str=f"{delinq_delta:+.2f}% MoM",
            delta_direction="positive" if delinq_delta <= 0 else "negative",
            badge_text="Early Warning",
            badge_class="badge-warning" if weighted_delinq > 2 else "badge-info"
        )
    with c3:
        spread = avg_apr - weighted_def
        render_kpi_card(
            title="3. Risk-Adjusted Quality Spread",
            value=f"{spread:.2f}%",
            delta_str=f"APR {avg_apr:.1f}% vs Loss {weighted_def:.1f}%",
            delta_direction="positive" if spread > 5 else "negative",
            badge_text="Portfolio Quality",
            badge_class="badge-info"
        )

    # Row 2: Funding & Portfolio KPIs
    st.markdown("#### 💰 II. Funding & Portfolio Velocity")
    c4, c5, c6 = st.columns(3)
    with c4:
        render_kpi_card(
            title="4. Funding Fulfillment Rate",
            value=format_percent(avg_fulfillment),
            delta_str="Funded vs Requested Ratio",
            delta_direction="positive" if avg_fulfillment >= 95 else "negative",
            badge_text="Liquidity",
            badge_class="badge-success" if avg_fulfillment >= 95 else "badge-warning"
        )
    with c5:
        render_kpi_card(
            title="5. Total Funded Volume",
            value=format_currency(tot_vol),
            delta_str=f"{latest_mom_growth:+.1f}% MoM Velocity" if pd.notna(latest_mom_growth) else "Stable",
            delta_direction="positive" if pd.notna(latest_mom_growth) and latest_mom_growth > 0 else "negative",
            badge_text=f"{tot_apps:,} Loans",
            badge_class="badge-info"
        )
    with c6:
        render_kpi_card(
            title="6. Average Portfolio APR",
            value=f"{avg_apr:.2f}%",
            delta_str="Weighted Coupon Yield",
            delta_direction="neutral",
            badge_text="Pricing",
            badge_class="badge-info"
        )

    # Row 3: Collections & Recovery KPIs
    st.markdown("#### 🔄 III. Collections & Recovery Efficiency")
    c7, c8, c9 = st.columns(3)
    with c7:
        render_kpi_card(
            title="7. Gross Charge-Off Volume",
            value=format_currency(tot_charged_off),
            delta_str="Cumulative Default Principal",
            delta_direction="negative" if tot_charged_off > 0 else "neutral",
            badge_text="Credit Loss",
            badge_class="badge-critical"
        )
    with c8:
        render_kpi_card(
            title="8. Net Recovery Rate",
            value=format_percent(weighted_recov_rate),
            delta_str=f"Recovered: {format_currency(tot_recov)}",
            delta_direction="positive" if weighted_recov_rate > 8 else "neutral",
            badge_text="Collections",
            badge_class="badge-warning"
        )
    with c9:
        render_kpi_card(
            title="9. Collection Cost Efficiency Ratio",
            value=format_percent(avg_collection_cost),
            delta_str="Recovery Fees / Gross Recoveries",
            delta_direction="positive" if avg_collection_cost < 18 else "negative",
            badge_text="Expense Leakage",
            badge_class="badge-info"
        )

    # Row 4: Operational Capacity Proxies
    st.markdown("#### ⚡ IV. Operational Capacity & Underwriting Proxies")
    c10, c11, c12 = st.columns(3)
    with c10:
        monthly_run_rate = int(tot_apps / max(len(df_filtered), 1))
        render_kpi_card(
            title="10. Regional Throughput Run-Rate",
            value=f"{monthly_run_rate:,} / mo",
            delta_str="Applications Processed / State-Month",
            delta_direction="positive",
            badge_text="Proxy: Capacity",
            badge_class="badge-info"
        )
    with c11:
        render_kpi_card(
            title="11. Verification Backlog Share",
            value=format_percent(avg_unverified),
            delta_str="Unverified Queue %",
            delta_direction="positive" if avg_unverified < 40 else "negative",
            badge_text="Proxy: Review Queue",
            badge_class="badge-warning" if avg_unverified > 50 else "badge-success"
        )
    with c12:
        render_kpi_card(
            title="12. Application Velocity vs Issuance",
            value=f"{latest_mom_growth:+.1f}%" if pd.notna(latest_mom_growth) else "0.0%",
            delta_str="MoM Volume Growth Delta",
            delta_direction="positive" if pd.notna(latest_mom_growth) and latest_mom_growth > 0 else "neutral",
            badge_text="Proxy: Velocity",
            badge_class="badge-info"
        )

    st.markdown("---")

    # Interactive Trend Visualizations
    col_v1, col_v2 = st.columns([7, 5])
    with col_v1:
        st.markdown("##### 📈 Historical Funded Volume vs. Default Rate Trend")
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(
            x=df_filtered["metric_month"],
            y=df_filtered["total_funded_volume"],
            name="Funded Volume ($)",
            marker_color="rgba(56, 189, 248, 0.4)",
            yaxis="y1"
        ))
        fig_trend.add_trace(go.Scatter(
            x=df_filtered["metric_month"],
            y=df_filtered["default_rate"],
            name="Default Rate (%)",
            mode="lines+markers",
            line=dict(color=COLOR_ROSE, width=3),
            yaxis="y2"
        ))
        layout = dict(PLOTLY_LAYOUT)
        layout["yaxis"] = dict(title="Funded Volume ($)", showgrid=True, gridcolor="rgba(255,255,255,0.06)")
        layout["yaxis2"] = dict(title="Default Rate (%)", overlaying="y", side="right", showgrid=False)
        layout["height"] = 380
        fig_trend.update_layout(layout)
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_v2:
        st.markdown("##### 🎯 Risk-Adjusted Quality by Risk Grade (A-G)")
        df_grade = get_grade_cohort_trends()
        if not df_grade.empty:
            agg_grade = df_grade.groupby("grade").agg({
                "total_funded": "sum",
                "avg_int_rate": "mean",
                "default_rate": "mean"
            }).reset_index()
            
            fig_grade = go.Figure()
            fig_grade.add_trace(go.Bar(
                x=agg_grade["grade"],
                y=agg_grade["avg_int_rate"],
                name="Avg APR (%)",
                marker_color=COLOR_CYAN
            ))
            fig_grade.add_trace(go.Bar(
                x=agg_grade["grade"],
                y=agg_grade["default_rate"],
                name="Default Rate (%)",
                marker_color=COLOR_ROSE
            ))
            g_layout = dict(PLOTLY_LAYOUT)
            g_layout["barmode"] = "group"
            g_layout["height"] = 380
            g_layout["title"] = "Yield vs Realized Default Loss by Grade"
            fig_grade.update_layout(g_layout)
            st.plotly_chart(fig_grade, use_container_width=True)


# ==============================================================================
# PAGE 2: ROOT-CAUSE ANALYSIS & 2008 CRISIS
# ==============================================================================

elif page == "🔍 Root-Cause Analysis & 2008 Crisis":
    st.markdown(
        "<div class='section-header'>"
        "<div>"
        "<div class='section-title'>🔍 Root-Cause Analysis & Historical Macro Stress Engine</div>"
        "<div class='section-subtitle'>Statistical anomaly detection surfacing the 2008 Financial Crisis spike and driver importance rankings</div>"
        "</div>"
        "<div class='badge badge-critical'>Macro Shock Detected: 2008 Crisis</div>"
        "</div>",
        unsafe_allow_html=True
    )

    diagnosis = run_full_root_cause_diagnosis()
    crisis = diagnosis["crisis_analysis"]
    df_drivers = diagnosis["ranked_drivers"]

    # 1. Financial Crisis Spotlight Banner
    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, rgba(244, 63, 94, 0.15) 0%, rgba(30, 41, 59, 0.7) 100%);
                    border: 1px solid rgba(244, 63, 94, 0.4); border-radius: 10px; padding: 18px 24px; margin-bottom: 20px;">
            <div style="font-size: 1.1rem; font-weight: 800; color: #fda4af; margin-bottom: 6px;">
                🚨 Historical Stress Event Identified: 2008–2009 Global Financial Crisis
            </div>
            <div style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;">
                The root-cause engine independently surfaces an authentic credit-loss spike during the 2008 crisis window. 
                Average portfolio default rate surged to <b>{crisis['crisis_default_rate']:.2f}%</b> (peaking at 26.20% in 2007) compared to 
                a stabilized <b>{crisis['post_crisis_default_rate']:.2f}%</b> in post-crisis cohorts — representing an authentic 
                <b>{crisis['default_rate_multiple']:.1f}x credit stress multiple</b>.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Yearly Crisis Metrics Table & Chart
    c_left, c_right = st.columns([6, 6])
    with c_left:
        st.markdown("##### 📉 Year-over-Year Macro Crisis Progression")
        df_macro = crisis["yearly_breakdown"]
        fig_macro = go.Figure()
        fig_macro.add_trace(go.Scatter(
            x=df_macro["issue_year"],
            y=df_macro["default_rate"],
            name="Default Rate (%)",
            mode="lines+markers",
            line=dict(color=COLOR_ROSE, width=3),
            marker=dict(size=8)
        ))
        fig_macro.add_trace(go.Scatter(
            x=df_macro["issue_year"],
            y=df_macro["recovery_rate"],
            name="Recovery Rate (%)",
            mode="lines+markers",
            line=dict(color=COLOR_EMERALD, width=2, dash="dot"),
            marker=dict(size=6)
        ))
        m_layout = dict(PLOTLY_LAYOUT)
        m_layout["height"] = 320
        m_layout["title"] = "Credit Default Spike vs Collections Recovery"
        fig_macro.update_layout(m_layout)
        st.plotly_chart(fig_macro, use_container_width=True)

    with c_right:
        st.markdown("##### 📊 Operational Metric Comparison: Crisis vs Baseline")
        st.dataframe(
            df_macro[["issue_year", "loan_count", "funded_volume", "avg_int_rate", "default_rate", "recovery_rate", "unverified_rate"]].rename(columns={
                "issue_year": "Year",
                "loan_count": "Loans",
                "funded_volume": "Volume ($)",
                "avg_int_rate": "APR (%)",
                "default_rate": "Default (%)",
                "recovery_rate": "Recovery (%)",
                "unverified_rate": "Unverified (%)"
            }),
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")

    # 2. Driver Attribution & Ranking
    st.markdown("#### 🧬 Top Ranked Drivers of Default Risk (Random Forest & Correlation)")
    st.markdown("Statistical attribution across 10 operational and credit attributes identifying underlying risk mechanisms:")

    col_rank_chart, col_rank_table = st.columns([5, 7])
    with col_rank_chart:
        fig_imp = px.bar(
            df_drivers.sort_values("importance_weight", ascending=True),
            x="importance_weight",
            y="driver_name",
            orientation="h",
            labels={"importance_weight": "Importance Weight (%)", "driver_name": "Driver"},
            color="importance_weight",
            color_continuous_scale="Blues"
        )
        i_layout = dict(PLOTLY_LAYOUT)
        i_layout["height"] = 380
        i_layout["coloraxis_showscale"] = False
        fig_imp.update_layout(i_layout)
        st.plotly_chart(fig_imp, use_container_width=True)

    with col_rank_table:
        st.dataframe(
            df_drivers[["rank", "driver_name", "importance_weight", "correlation_with_default", "direction", "diagnostic_narrative"]].rename(columns={
                "rank": "#",
                "driver_name": "Driver Name",
                "importance_weight": "Importance (%)",
                "correlation_with_default": "Corr",
                "direction": "Impact",
                "diagnostic_narrative": "Operational Root-Cause Mechanism"
            }),
            use_container_width=True,
            hide_index=True,
            height=380
        )

    # Degraded Operational Periods Table
    st.markdown("#### ⚠️ Automated Operational Degradation Log")
    st.markdown("Historical alert registry flagging months where default deltas or backlog proxies exceeded operational policy tolerances:")
    degraded_alerts = detect_degraded_kpis()
    if not degraded_alerts.empty:
        st.dataframe(
            degraded_alerts.rename(columns={
                "metric_month": "Month",
                "severity": "Severity",
                "default_rate": "Default Rate (%)",
                "funded_volume": "Volume ($)",
                "fulfillment_rate": "Fulfillment (%)",
                "unverified_share": "Unverified Backlog (%)",
                "issues_flagged": "Policy Exceptions Triggered"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No policy breaches identified in historical timeline.")


# ==============================================================================
# PAGE 3: PREDICTIVE ANALYTICS & UNDERWRITING CLASSIFIER
# ==============================================================================

elif page == "📈 Predictive Forecasts & Underwriting":
    st.markdown(
        "<div class='section-header'>"
        "<div>"
        "<div class='section-title'>📈 Predictive Analytics & Underwriting Risk Engine</div>"
        "<div class='section-subtitle'>Macro portfolio forecasting (4 quarters) and individual loan-level default risk classification</div>"
        "</div>"
        "<div class='badge badge-success'>Model Active: Gradient Boosting (AUC 0.703)</div>"
        "</div>",
        unsafe_allow_html=True
    )

    tab_macro, tab_micro = st.tabs(["🌐 Macro Portfolio 4-Quarter Forecasts", "🎯 Individual Loan Underwriter & Scorer"])

    # --------------------------------------------------------------------------
    # Tab 1: Macro Time-Series Forecasts
    # --------------------------------------------------------------------------
    with tab_macro:
        st.markdown("##### 🔮 Next 4-Quarters (12 Months) Portfolio Forecasts with 95% Confidence Intervals")
        fc_data = forecast_portfolio_kpis(periods=12)
        if fc_data:
            df_hist = fc_data["historical"]
            df_fc = fc_data["forecast"]

            fc_col1, fc_col2 = st.columns(2)
            with fc_col1:
                st.markdown("###### 📊 Portfolio Funded Volume ($) Forecast")
                fig_fc_vol = go.Figure()
                # Historical
                fig_fc_vol.add_trace(go.Scatter(
                    x=df_hist["date"],
                    y=df_hist["total_funded_volume"],
                    name="Historical Volume",
                    line=dict(color=COLOR_CYAN, width=2)
                ))
                # Forecast
                fig_fc_vol.add_trace(go.Scatter(
                    x=df_fc["date"],
                    y=df_fc["forecast_funded_volume"],
                    name="Forecast Volume",
                    line=dict(color=COLOR_EMERALD, width=3, dash="dash")
                ))
                # Confidence band
                fig_fc_vol.add_trace(go.Scatter(
                    x=pd.concat([df_fc["date"], df_fc["date"][::-1]]),
                    y=pd.concat([df_fc["volume_upper"], df_fc["volume_lower"][::-1]]),
                    fill="toself",
                    fillcolor="rgba(16, 185, 129, 0.12)",
                    line=dict(color="rgba(255,255,255,0)"),
                    name="95% Confidence Band",
                    hoverinfo="skip"
                ))
                v_layout = dict(PLOTLY_LAYOUT)
                v_layout["height"] = 350
                fig_fc_vol.update_layout(v_layout)
                st.plotly_chart(fig_fc_vol, use_container_width=True)

            with fc_col2:
                st.markdown("###### 🛡️ Portfolio Default Rate (%) Forecast")
                fig_fc_def = go.Figure()
                fig_fc_def.add_trace(go.Scatter(
                    x=df_hist["date"],
                    y=df_hist["default_rate"],
                    name="Historical Default Rate",
                    line=dict(color=COLOR_ROSE, width=2)
                ))
                fig_fc_def.add_trace(go.Scatter(
                    x=df_fc["date"],
                    y=df_fc["forecast_default_rate"],
                    name="Forecast Default Rate",
                    line=dict(color=COLOR_AMBER, width=3, dash="dash")
                ))
                fig_fc_def.add_trace(go.Scatter(
                    x=pd.concat([df_fc["date"], df_fc["date"][::-1]]),
                    y=pd.concat([df_fc["default_rate_upper"], df_fc["default_rate_lower"][::-1]]),
                    fill="toself",
                    fillcolor="rgba(245, 158, 11, 0.12)",
                    line=dict(color="rgba(255,255,255,0)"),
                    name="95% Confidence Band",
                    hoverinfo="skip"
                ))
                d_layout = dict(PLOTLY_LAYOUT)
                d_layout["height"] = 350
                fig_fc_def.update_layout(d_layout)
                st.plotly_chart(fig_fc_def, use_container_width=True)

            st.markdown("###### 📋 Projected Monthly Forecast Data Table")
            st.dataframe(
                df_fc[["metric_month", "forecast_funded_volume", "volume_lower", "volume_upper", "forecast_default_rate", "default_rate_lower", "default_rate_upper"]].rename(columns={
                    "metric_month": "Forecast Month",
                    "forecast_funded_volume": "Projected Volume ($)",
                    "volume_lower": "Lower 95% ($)",
                    "volume_upper": "Upper 95% ($)",
                    "forecast_default_rate": "Projected Default (%)",
                    "default_rate_lower": "Lower 95% (%)",
                    "default_rate_upper": "Upper 95% (%)"
                }),
                use_container_width=True,
                hide_index=True
            )

    # --------------------------------------------------------------------------
    # Tab 2: Individual Loan Underwriter
    # --------------------------------------------------------------------------
    with tab_micro:
        st.markdown("##### 🧮 Interactive Loan Underwriting Decision Support")
        st.markdown("Adjust prospective borrower attributes to predict default risk probability and receive real-time underwriting recommendations:")

        u_col1, u_col2, u_col3 = st.columns(3)
        with u_col1:
            u_loan_amnt = st.number_input("Requested Loan Principal ($)", min_value=1000, max_value=40000, value=15000, step=1000)
            u_term = st.selectbox("Loan Term", ["36 months", "60 months"], index=0)
            u_grade = st.selectbox("Underwriting Risk Grade", ["A", "B", "C", "D", "E", "F", "G"], index=2)
            u_int_rate = st.slider("Proposed Interest Rate (APR %)", min_value=5.0, max_value=30.0, value=13.5, step=0.25)
        with u_col2:
            u_annual_inc = st.number_input("Annual Household Income ($)", min_value=10000, max_value=500000, value=65000, step=5000)
            u_dti = st.slider("Debt-to-Income Ratio (DTI %)", min_value=0.0, max_value=50.0, value=18.5, step=0.5)
            u_fico = st.slider("Borrower Credit Score (FICO)", min_value=550, max_value=850, value=680, step=5)
            u_revol_util = st.slider("Revolving Utilization (%)", min_value=0.0, max_value=100.0, value=48.0, step=1.0)
        with u_col3:
            u_verification = st.selectbox("Income Verification Status", ["Verified", "Source Verified", "Not Verified"], index=0)
            u_home = st.selectbox("Home Ownership Type", ["MORTGAGE", "RENT", "OWN"], index=0)
            u_open_acc = st.slider("Open Credit Lines", min_value=1, max_value=35, value=10, step=1)
            # Estimate monthly installment: P * (r*(1+r)^n) / ((1+r)^n - 1)
            n_months = 36 if "36" in u_term else 60
            r_mo = (u_int_rate / 100.0) / 12.0
            u_installment = u_loan_amnt * (r_mo * (1 + r_mo)**n_months) / ((1 + r_mo)**n_months - 1)
            st.metric("Estimated Monthly Installment", f"${u_installment:.2f}")

        # Compute instant score
        loan_payload = {
            "loan_amnt": u_loan_amnt,
            "term_months": 36 if "36" in u_term else 60,
            "int_rate": u_int_rate,
            "installment": u_installment,
            "grade": u_grade,
            "annual_inc": u_annual_inc,
            "dti": u_dti,
            "fico_range_low": u_fico,
            "revol_util": u_revol_util,
            "open_acc": u_open_acc,
            "verification_status": u_verification,
            "home_ownership": u_home
        }
        score = score_single_loan(loan_payload)

        st.markdown("---")
        # Decision Banner
        tier_color = "#10b981" if "Prime" in score["risk_tier"] else ("#f59e0b" if "Near-Prime" in score["risk_tier"] or "Subprime" in score["risk_tier"] else "#f43f5e")
        st.markdown(
            f"""
            <div style="background: rgba(17, 24, 39, 0.85); border: 2px solid {tier_color}; border-radius: 12px; padding: 20px 25px; margin-top: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-size: 0.85rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; font-weight: 700;">Model Assessment</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: {tier_color}; margin: 4px 0;">{score['risk_tier']}</div>
                        <div style="font-size: 1.05rem; color: #f8fafc; font-weight: 600;">Recommendation: {score['underwriting_recommendation']}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 0.85rem; text-transform: uppercase; color: #94a3b8; font-weight: 700;">Default Probability</div>
                        <div style="font-size: 2.5rem; font-weight: 900; color: {tier_color};">{score['default_probability_pct']:.2f}%</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ==============================================================================
# PAGE 4: WHAT-IF SCENARIO DECISION SIMULATOR (5 SCENARIOS)
# ==============================================================================

elif page == "🎛️ What-If Decision Simulator (5)":
    st.markdown(
        "<div class='section-header'>"
        "<div>"
        "<div class='section-title'>🎛️ Operations What-If Decision Simulator</div>"
        "<div class='section-subtitle'>Interactive scenario modeling applied on real historical baselines with trade-off evaluation & recommendations</div>"
        "</div>"
        "<div class='badge badge-info'>5 Active Decision Engines</div>"
        "</div>",
        unsafe_allow_html=True
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Underwriting Tightening",
        "2. Risk-Based APR Pricing",
        "3. Funding Fulfillment Policy",
        "4. Collections Effectiveness",
        "5. Verification Capacity Shift"
    ])

    # --------------------------------------------------------------------------
    # Scenario 1: Underwriting Tightening
    # --------------------------------------------------------------------------
    with tab1:
        st.markdown("##### 🛡️ Scenario 1: Underwriting Policy Tightening (FICO & DTI Thresholds)")
        st.markdown("Model the trade-off between default rate mitigation and sacrificed origination volume:")

        s1_col1, s1_col2 = st.columns(2)
        with s1_col1:
            s1_min_fico = st.slider("Minimum FICO Score Cutoff", min_value=600, max_value=750, value=660, step=10)
        with s1_col2:
            s1_max_dti = st.slider("Maximum Debt-to-Income (DTI %) Cap", min_value=15.0, max_value=45.0, value=35.0, step=1.0)

        res1 = simulate_underwriting_tightening(min_fico=s1_min_fico, max_dti=s1_max_dti)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_kpi_card(
                "Baseline Default Rate",
                format_percent(res1["baseline"]["default_rate_pct"]),
                badge_text="Current Policy"
            )
        with m2:
            render_kpi_card(
                "Simulated Default Rate",
                format_percent(res1["simulated"]["default_rate_pct"]),
                delta_str=f"{res1['deltas']['default_rate_delta_pts']:+.2f} pts",
                delta_direction="positive" if res1["deltas"]["default_rate_delta_pts"] <= 0 else "negative",
                badge_text="Tightened Policy",
                badge_class="badge-success"
            )
        with m3:
            render_kpi_card(
                "Credit Losses Saved",
                format_currency(res1["deltas"]["losses_saved_dollars"]),
                delta_str="Avoided Charge-Offs",
                delta_direction="positive",
                badge_text="Capital Preserved"
            )
        with m4:
            render_kpi_card(
                "Origination Volume Impact",
                f"{res1['deltas']['volume_change_pct']:+.1f}%",
                delta_str=f"-{format_currency(res1['deltas']['volume_sacrificed_dollars'])}",
                delta_direction="negative" if res1["deltas"]["volume_change_pct"] < -10 else "neutral",
                badge_text="Volume Drag"
            )

        render_recommendation("Underwriting Policy Adjustment", res1["recommendation"])

    # --------------------------------------------------------------------------
    # Scenario 2: Risk-Based APR Pricing
    # --------------------------------------------------------------------------
    with tab2:
        st.markdown("##### 💵 Scenario 2: Risk-Based Interest Pricing (Subprime Grades C-G)")
        st.markdown("Adjust APR pricing for lower grades and evaluate gross revenue vs. adverse selection default sensitivity:")

        s2_apr_delta = st.slider("APR Shift on Grades C-G (Basis Points)", min_value=-300, max_value=400, value=150, step=25)
        res2 = simulate_risk_pricing_adjustment(apr_delta_bps=s2_apr_delta)

        m1, m2, m3 = st.columns(3)
        with m1:
            render_kpi_card(
                "Gross Interest Income Delta",
                f"{res2['deltas']['interest_income_delta']:+,.0f}",
                delta_str="Annual Revenue Shift",
                delta_direction="positive" if res2["deltas"]["interest_income_delta"] >= 0 else "negative",
                badge_text="Gross APR Spread"
            )
        with m2:
            render_kpi_card(
                "Adverse Selection Losses",
                format_currency(res2["simulated"]["expected_losses"]),
                delta_str=f"vs Baseline: {format_currency(res2['baseline']['expected_losses'])}",
                delta_direction="negative" if res2["simulated"]["expected_losses"] > res2["baseline"]["expected_losses"] else "positive",
                badge_text="Credit Risk Impact"
            )
        with m3:
            render_kpi_card(
                "Net Yield Delta (Bottom-Line)",
                f"${res2['deltas']['net_yield_delta']:+,.0f}",
                delta_str=f"{res2['deltas']['net_yield_growth_pct']:+.1f}% Net Growth",
                delta_direction="positive" if res2["deltas"]["net_yield_delta"] >= 0 else "negative",
                badge_text="Net Return",
                badge_class="badge-success" if res2["deltas"]["net_yield_delta"] > 0 else "badge-critical"
            )

        render_recommendation("Subprime Risk Pricing Strategy", res2["recommendation"])

    # --------------------------------------------------------------------------
    # Scenario 3: Funding Fulfillment Policy
    # --------------------------------------------------------------------------
    with tab3:
        st.markdown("##### 🤝 Scenario 3: Funding Fulfillment Policy & Issuance Cutoff")
        st.markdown("Adjust the minimum required investor commitment threshold before loan origination:")

        s3_threshold = st.slider("Minimum Fulfillment Threshold (%)", min_value=80.0, max_value=100.0, value=95.0, step=1.0)
        res3 = simulate_funding_policy(min_fulfillment_threshold_pct=s3_threshold)

        m1, m2, m3 = st.columns(3)
        with m1:
            render_kpi_card(
                "Qualified Issuance Rate",
                format_percent(res3["simulated"]["qualified_loans_pct"]),
                delta_str=f"{res3['simulated']['qualified_loans_count']:,} Loans Met Threshold",
                delta_direction="positive" if res3["simulated"]["qualified_loans_pct"] >= 95 else "neutral",
                badge_text="Fulfillment"
            )
        with m2:
            render_kpi_card(
                "Cancelled Partially-Funded Loans",
                f"{res3['simulated']['cancelled_loans_count']:,}",
                delta_str=f"{res3['deltas']['volume_impact_pct']:+.2f}% Volume Impact",
                delta_direction="neutral",
                badge_text="Pipeline Drops"
            )
        with m3:
            render_kpi_card(
                "Retained Funded Pipeline",
                format_currency(res3["simulated"]["funded_volume"]),
                delta_str="100% Investor Backed",
                delta_direction="positive",
                badge_text="Institutional Quality"
            )

        render_recommendation("Liquidity & Fulfillment Governance", res3["recommendation"])

    # --------------------------------------------------------------------------
    # Scenario 4: Collections Effectiveness
    # --------------------------------------------------------------------------
    with tab4:
        st.markdown("##### 💼 Scenario 4: Collections Recovery & Fee Optimization")
        st.markdown("Simulate operational improvements in debt recovery workflows and agency fee structures:")

        s4_col1, s4_col2 = st.columns(2)
        with s4_col1:
            s4_uplift = st.slider("Recovery Rate Uplift on Charged-Off Accounts (%)", min_value=0.0, max_value=60.0, value=25.0, step=5.0)
        with s4_col2:
            s4_fee = st.slider("Collection Agency Fee Commission (%)", min_value=10.0, max_value=25.0, value=16.0, step=1.0)

        res4 = simulate_collections_optimization(recovery_rate_uplift_pct=s4_uplift, fee_commission_pct=s4_fee)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_kpi_card(
                "Baseline Recovery Rate",
                format_percent(res4["baseline"]["recovery_rate_pct"]),
                badge_text="Historical Performance"
            )
        with m2:
            render_kpi_card(
                "Simulated Recovery Rate",
                format_percent(res4["simulated"]["recovery_rate_pct"]),
                delta_str=f"+{s4_uplift:.0f}% Relative Uplift",
                delta_direction="positive",
                badge_text="Optimized Recovery",
                badge_class="badge-success"
            )
        with m3:
            render_kpi_card(
                "Net Recovered Cash Delta",
                f"+${res4['deltas']['net_cash_delta']:,.0f}",
                delta_str=f"+{res4['deltas']['net_cash_uplift_pct']:.1f}% Cash Uplift",
                delta_direction="positive",
                badge_text="Net Cash Flow"
            )
        with m4:
            render_kpi_card(
                "Collection Agency Fees",
                format_currency(res4["simulated"]["collection_fees"]),
                delta_str=f"{s4_fee}% Commission Capped",
                delta_direction="neutral",
                badge_text="Agency Expense"
            )

        render_recommendation("Collections Strategy & Agency SLA", res4["recommendation"])

    # --------------------------------------------------------------------------
    # Scenario 5: Verification Capacity Shift
    # --------------------------------------------------------------------------
    with tab5:
        st.markdown("##### ⚡ Scenario 5: Income Verification Capacity Allocation & Queue Trade-off")
        st.markdown("Evaluate shifting unverified applicants into full document verification against underwriting review costs:")

        s5_col1, s5_col2 = st.columns(2)
        with s5_col1:
            s5_convert = st.slider("Shift % of Unverified Queue to Verified", min_value=10.0, max_value=80.0, value=30.0, step=5.0)
        with s5_col2:
            s5_cost = st.slider("Underwriting Review Cost per Application ($)", min_value=15.0, max_value=60.0, value=35.0, step=5.0)

        res5 = simulate_verification_policy_shift(additional_verified_pct=s5_convert, review_cost_per_loan=s5_cost)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_kpi_card(
                "Converted Applications",
                f"{res5['simulated']['converted_loans_count']:,}",
                delta_str=f"From {res5['baseline']['unverified_share_pct']:.1f}% to {res5['simulated']['new_unverified_share_pct']:.1f}% Unverified",
                delta_direction="positive",
                badge_text="Verification Queue"
            )
        with m2:
            render_kpi_card(
                "Credit Losses Saved",
                format_currency(res5["simulated"]["credit_losses_saved"]),
                delta_str="Delinquency Mitigation",
                delta_direction="positive",
                badge_text="Loss Mitigation",
                badge_class="badge-success"
            )
        with m3:
            render_kpi_card(
                "Operational Processing Cost",
                format_currency(res5["simulated"]["capacity_processing_cost"]),
                delta_str=f"${s5_cost:.0f} / reviewed app",
                delta_direction="negative",
                badge_text="Staffing / Capacity"
            )
        with m4:
            render_kpi_card(
                "Net Operational Benefit",
                f"${res5['simulated']['net_economic_benefit']:+,.0f}",
                delta_str="Credit Savings - Review Cost",
                delta_direction="positive" if res5["simulated"]["net_economic_benefit"] > 0 else "negative",
                badge_text="Net ROI",
                badge_class="badge-success" if res5["simulated"]["net_economic_benefit"] > 0 else "badge-critical"
            )

        render_recommendation("Underwriting Verification Queue Strategy", res5["recommendation"])


# ==============================================================================
# PAGE 5: METHODOLOGY, PROXIES & DAX GOVERNANCE
# ==============================================================================

elif page == "📚 Methodology, Proxies & DAX":
    st.markdown(
        "<div class='section-header'>"
        "<div>"
        "<div class='section-title'>📚 Methodology, Operational Proxies & DAX Reference</div>"
        "<div class='section-subtitle'>Complete documentation of KPI definitions, capacity proxies, and Power BI DAX formulas</div>"
        "</div>"
        "<div class='badge badge-info'>Data Governance & Compliance</div>"
        "</div>",
        unsafe_allow_html=True
    )

    st.markdown("#### 📖 1. The 12 Core Lending Operations KPIs Catalog")
    kpi_table = [
        {"#": "1", "Category": "Credit Risk", "KPI Name": "Default / Charge-Off Rate", "Formula": "SUM(is_default) / COUNT(*) * 100", "LendingClub Source": "loan_status in ('Charged Off', 'Default')"},
        {"#": "2", "Category": "Credit Risk", "KPI Name": "Delinquency Rate (30+ DPD)", "Formula": "SUM(is_delinquent) / COUNT(*) * 100", "LendingClub Source": "loan_status in ('Late 31-120', 'Late 16-30')"},
        {"#": "3", "Category": "Credit Risk", "KPI Name": "Risk-Adjusted Portfolio Quality", "Formula": "AVG(int_rate) - Default Rate by Grade", "LendingClub Source": "grade, int_rate, loan_status"},
        {"#": "4", "Category": "Funding & Portfolio", "KPI Name": "Funding Fulfillment Rate", "Formula": "SUM(funded_amnt) / SUM(loan_amnt) * 100", "LendingClub Source": "funded_amnt, loan_amnt"},
        {"#": "5", "Category": "Funding & Portfolio", "KPI Name": "Monthly Funded Volume Trend", "Formula": "SUM(funded_amnt), MoM/YoY LAG() deltas", "LendingClub Source": "funded_amnt, issue_d"},
        {"#": "6", "Category": "Funding & Portfolio", "KPI Name": "Average Interest Rate by Grade", "Formula": "AVG(int_rate) GROUP BY grade", "LendingClub Source": "int_rate, grade, sub_grade"},
        {"#": "7", "Category": "Collections & Recovery", "KPI Name": "Gross Charge-Off Principal", "Formula": "SUM(funded_amnt - total_rec_prncp)", "LendingClub Source": "funded_amnt, total_rec_prncp, loan_status"},
        {"#": "8", "Category": "Collections & Recovery", "KPI Name": "Net Recovery Rate", "Formula": "SUM(recoveries) / SUM(charged_off_prncp) * 100", "LendingClub Source": "recoveries, charged_off_principal"},
        {"#": "9", "Category": "Collections & Recovery", "KPI Name": "Collection Cost Efficiency Ratio", "Formula": "SUM(collection_recovery_fee) / SUM(recoveries) * 100", "LendingClub Source": "collection_recovery_fee, recoveries"},
        {"#": "10", "Category": "Capacity (Proxy)", "KPI Name": "Regional Processing Throughput", "Formula": "COUNT(loan_id) by addr_state per month", "LendingClub Source": "loan_id, addr_state, issue_d"},
        {"#": "11", "Category": "Capacity (Proxy)", "KPI Name": "Verification Backlog Share", "Formula": "% of loans with Not Verified status", "LendingClub Source": "verification_status"},
        {"#": "12", "Category": "Capacity (Proxy)", "KPI Name": "Volume vs. Issuance Velocity", "Formula": "MoM % Volume Growth vs Fulfillment Spread", "LendingClub Source": "issue_d, funded_amnt, loan_amnt"}
    ]
    st.dataframe(pd.DataFrame(kpi_table), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### ⚖️ 2. Operational Capacity Proxy Disclosures")
    st.info(
        "**Capacity Data Disclosure**: LendingClub's public loan release does not contain internal operational staff headcount "
        "or loan officer time-tracking tables. In accordance with credit operations best practices, **capacity KPIs are modeled as defensible operational proxies**:\n"
        "- **Throughput Proxy**: Loan volume originated per state per month represents regional underwriting processing capacity.\n"
        "- **Review Backlog Proxy**: The proportion of applications categorized as 'Not Verified' versus 'Verified / Source Verified' proxies the operational queue backlog and document verification bottlenecks.\n"
        "- **Issuance Velocity Proxy**: Month-over-month application volume acceleration against funding fulfillment rate captures pipeline processing capacity constraints."
    )

    st.markdown("---")
    st.markdown("#### ⚡ 3. Star-Schema Data Model & Power BI DAX Reference")
    st.markdown("Below are sample DAX measures pre-packaged in `/powerbi/README.md` for Power BI report assembly:")
    
    st.code(
        """
-- DAX Measure 1: Default / Charge-Off Rate
Default Rate % = 
DIVIDE(
    CALCULATE(COUNTROWS(fact_loans), fact_loans[is_default] = 1),
    COUNTROWS(fact_loans),
    0
)

-- DAX Measure 4: Funding Fulfillment Rate
Funding Fulfillment Rate % = 
DIVIDE(
    SUM(fact_loans[funded_amnt]),
    SUM(fact_loans[loan_amnt]),
    1
)

-- DAX Measure 8: Net Recovery Rate
Net Recovery Rate % = 
DIVIDE(
    SUM(fact_loans[recoveries]),
    SUM(fact_loans[charged_off_principal]),
    0
)

-- DAX Measure 11: Verification Backlog Share (Proxy)
Verification Backlog Share % = 
DIVIDE(
    CALCULATE(COUNTROWS(fact_loans), RELATED(dim_borrower[verification_status]) = "not verified"),
    COUNTROWS(fact_loans),
    0
)
        """,
        language="sql"
    )
