"""
OPS-TWIN: KPI Trend Analysis & Degradation Detection Engine
==========================================================
Analyzes performance trends across the 12 core lending operations KPIs:
  - Rolling moving averages (3-month, 6-month)
  - Period-over-Period (MoM, YoY) percentage deltas
  - Automated anomaly / degradation flagging when KPIs drift into danger zones
  - Cohort trend breakdown by Risk Grade and Regional State
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "processed" / "ops_twin.db"


def get_db_connection():
    """Returns a connection to the SQLite operational database."""
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found at {DB_FILE}. Please run data/process_data.py first.")
    return sqlite3.connect(str(DB_FILE))


def get_monthly_trends():
    """
    Retrieves full monthly time-series rollups, calculating 3-month and 6-month
    rolling moving averages and directional momentum flags.
    """
    conn = get_db_connection()
    query = """
    SELECT * FROM monthly_kpi_rollup
    ORDER BY metric_month ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        return df

    # Calculate additional rolling smoothing
    df["rolling_3m_default_rate"] = df["default_rate"].rolling(window=3, min_periods=1).mean().round(2)
    df["rolling_6m_default_rate"] = df["default_rate"].rolling(window=6, min_periods=1).mean().round(2)
    df["rolling_3m_volume"] = df["total_funded_volume"].rolling(window=3, min_periods=1).mean().round(2)

    return df


def detect_degraded_kpis(threshold_mom_default=2.0, threshold_fulfillment=95.0, threshold_unverified=60.0):
    """
    Scans the historical timeline and flags periods where core lending operations
    KPIs degraded beyond policy tolerances:
      - Default rate spiked significantly (MoM delta > threshold_mom_default percentage points)
      - Funding fulfillment rate slipped below threshold_fulfillment %
      - Unverified backlog proxy climbed above threshold_unverified %
    """
    df = get_monthly_trends()
    if df.empty:
        return pd.DataFrame()

    alerts = []
    for _, row in df.iterrows():
        month = row["metric_month"]
        flags = []
        severity = "NORMAL"

        # Check Default Rate Spikes
        if pd.notna(row["mom_default_rate_delta"]) and row["mom_default_rate_delta"] >= threshold_mom_default:
            flags.append(f"Default rate surged +{row['mom_default_rate_delta']:.2f}% MoM (reached {row['default_rate']}%)")
            severity = "CRITICAL" if row["mom_default_rate_delta"] > 5.0 else "WARNING"

        # Check Absolute Default Severity (Crisis level > 18%)
        if row["default_rate"] >= 18.0:
            flags.append(f"Severe credit stress: Default rate at {row['default_rate']:.2f}%")
            severity = "CRITICAL"

        # Check Fulfillment Slippage
        if pd.notna(row["funding_fulfillment_rate"]) and row["funding_fulfillment_rate"] < threshold_fulfillment:
            flags.append(f"Funding fulfillment fell to {row['funding_fulfillment_rate']:.1f}% (target >= {threshold_fulfillment}%)")
            if severity == "NORMAL":
                severity = "WARNING"

        # Check Unverified Backlog Proxy
        if pd.notna(row["unverified_backlog_share"]) and row["unverified_backlog_share"] > threshold_unverified:
            flags.append(f"Verification backlog high: {row['unverified_backlog_share']:.1f}% unverified applications")
            if severity == "NORMAL":
                severity = "INFO"

        if flags:
            alerts.append({
                "metric_month": month,
                "severity": severity,
                "default_rate": row["default_rate"],
                "funded_volume": row["total_funded_volume"],
                "fulfillment_rate": row["funding_fulfillment_rate"],
                "unverified_share": row["unverified_backlog_share"],
                "issues_flagged": "; ".join(flags)
            })

    return pd.DataFrame(alerts)


def get_grade_cohort_trends():
    """Returns loan performance trends segmented by risk grade."""
    conn = get_db_connection()
    query = """
    SELECT
        l.grade,
        l.issue_year,
        COUNT(l.loan_id) AS total_loans,
        ROUND(SUM(l.funded_amnt), 2) AS total_funded,
        ROUND(AVG(l.int_rate), 2) AS avg_int_rate,
        ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS default_rate,
        ROUND(SUM(l.is_delinquent) * 100.0 / COUNT(l.loan_id), 2) AS delinquency_rate
    FROM loans l
    GROUP BY l.grade, l.issue_year
    ORDER BY l.grade ASC, l.issue_year ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_state_throughput_trends(top_n=10):
    """Returns loan throughput and risk metrics segmented by top geographic states."""
    conn = get_db_connection()
    query = f"""
    SELECT
        b.addr_state,
        COUNT(l.loan_id) AS total_loans,
        ROUND(SUM(l.funded_amnt), 2) AS total_funded_volume,
        ROUND(AVG(l.int_rate), 2) AS avg_int_rate,
        ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS default_rate,
        ROUND(
            SUM(CASE WHEN b.verification_status = 'Not Verified' THEN 1 ELSE 0 END) * 100.0 / COUNT(l.loan_id),
            2
        ) AS unverified_share
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    GROUP BY b.addr_state
    ORDER BY total_loans DESC
    LIMIT {top_n}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


if __name__ == "__main__":
    print("OPS-TWIN Trend Detection Test:")
    degraded = detect_degraded_kpis()
    print(f"Detected {len(degraded)} degraded/alert operational periods.")
    if not degraded.empty:
        print(degraded.head(10)[["metric_month", "severity", "default_rate", "issues_flagged"]].to_string(index=False))
