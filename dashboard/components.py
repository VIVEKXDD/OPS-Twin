"""
OPS-TWIN: Dashboard Reusable UI Components & Plotly Theming
===========================================================
Provides polished visual widgets:
  - Glassmorphic KPI metric cards with directional delta badges
  - Mini inline trend sparklines
  - Pre-configured Plotly dark charts with custom colorways
  - Clean currency and ratio formatters
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# Color tokens
COLOR_CYAN = "#38bdf8"
COLOR_EMERALD = "#10b981"
COLOR_AMBER = "#f59e0b"
COLOR_ROSE = "#f43f5e"
COLOR_PURPLE = "#a855f7"
COLOR_SLATE = "#64748b"
BG_CARD = "rgba(17, 24, 39, 0.75)"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Plus Jakarta Sans, sans-serif", color="#cbd5e1", size=12),
    margin=dict(l=20, r=20, t=35, b=20),
    xaxis=dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.06)",
        linecolor="rgba(255,255,255,0.1)",
        tickcolor="rgba(255,255,255,0.1)"
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.06)",
        linecolor="rgba(255,255,255,0.1)",
        tickcolor="rgba(255,255,255,0.1)"
    ),
    legend=dict(
        bgcolor="rgba(15,23,42,0.6)",
        bordercolor="rgba(255,255,255,0.08)",
        borderwidth=1
    ),
    hovermode="x unified"
)


def format_currency(val):
    """Formats numeric values into clean financial abbreviations ($1.2M, $450K)."""
    if val is None or pd.isna(val):
        return "$0"
    v = float(val)
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B"
    elif abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    elif abs(v) >= 1_000:
        return f"${v / 1_000:.1f}K"
    else:
        return f"${v:.2f}"


def format_percent(val):
    if val is None or pd.isna(val):
        return "0.00%"
    return f"{float(val):.2f}%"


def render_kpi_card(title, value, delta_str=None, delta_direction="neutral", badge_text=None, badge_class="badge-info"):
    """Renders a glassmorphism metric card with optional delta badge."""
    badge_html = f'<span class="badge {badge_class}">{badge_text}</span>' if badge_text else ""
    delta_html = ""
    if delta_str:
        delta_class = f"kpi-delta {delta_direction}"
        arrow = "▲" if delta_direction == "positive" else ("▼" if delta_direction == "negative" else "•")
        delta_html = f'<div class="{delta_class}">{arrow} {delta_str}</div>'

    html = f"""
    <div class="kpi-card">
        <div class="kpi-label">
            <span>{title}</span>
            {badge_html}
        </div>
        <div class="kpi-value">{value}</div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def create_sparkline(y_series, line_color=COLOR_CYAN, height=45):
    """Generates a compact sparkline chart for table or card embedding."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=y_series,
        mode="lines",
        line=dict(color=line_color, width=2),
        hoverinfo="skip"
    ))
    fig.update_layout(
        showlegend=False,
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig


def render_recommendation(title, text):
    """Renders a styled executive recommendation box."""
    html = f"""
    <div class="recommendation-box">
        <div class="recommendation-title">💡 Operational Recommendation: {title}</div>
        <div class="recommendation-text">{text}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
