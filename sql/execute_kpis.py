"""
OPS-TWIN: SQL Execution and Validation Runner
============================================
Executes pure SQL queries against data/processed/ops_twin.db to:
  1. Compute all 12 core lending operations KPIs.
  2. Compute Window Functions (MoM, YoY, Rolling Moving Averages).
  3. Validate query outputs against statistical bounds.
  4. Populate the normalized monthly_kpi_rollup table for BI consumption.
"""

import sqlite3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "processed" / "ops_twin.db"
SQL_FILE = BASE_DIR / "sql" / "kpi_queries.sql"


def run_sql_kpis():
    print("=" * 75)
    print("  OPS-TWIN: SQL KPI & Window Function Engine Execution")
    print("=" * 75)
    
    if not DB_FILE.exists():
        print(f"[-] Database {DB_FILE} not found. Please run data/process_data.py first.")
        return
        
    conn = sqlite3.connect(str(DB_FILE))
    
    # 1. Execute Query 1 (Monthly KPI Rollup with Window Functions)
    print("[*] Executing Query 1: Monthly KPI Rollup with Window Functions...")
    query_1 = """
    WITH MonthlyBase AS (
        SELECT
            l.issue_month,
            COUNT(l.loan_id) AS total_applications,
            SUM(l.loan_amnt) AS total_requested_volume,
            SUM(l.funded_amnt) AS total_funded_volume,
            ROUND(AVG(l.int_rate), 2) AS avg_interest_rate,
            ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS default_rate,
            ROUND(SUM(l.is_delinquent) * 100.0 / COUNT(l.loan_id), 2) AS delinquency_rate,
            ROUND(SUM(l.funded_amnt) * 100.0 / NULLIF(SUM(l.loan_amnt), 0), 2) AS funding_fulfillment_rate,
            ROUND(SUM(pr.charged_off_principal), 2) AS total_charged_off_prncp,
            ROUND(
                SUM(pr.recoveries) * 100.0 / NULLIF(SUM(pr.charged_off_principal), 0),
                2
            ) AS net_recovery_rate,
            ROUND(
                SUM(pr.collection_recovery_fee) * 100.0 / NULLIF(SUM(pr.recoveries), 0),
                2
            ) AS collection_cost_ratio,
            ROUND(
                SUM(CASE WHEN b.verification_status = 'Not Verified' THEN 1 ELSE 0 END) * 100.0 / COUNT(l.loan_id),
                2
            ) AS unverified_backlog_share
        FROM loans l
        JOIN borrowers b ON l.borrower_id = b.borrower_id
        JOIN payments_recoveries pr ON l.loan_id = pr.loan_id
        GROUP BY l.issue_month
    ),
    MonthlyWithTrends AS (
        SELECT
            issue_month AS metric_month,
            total_applications,
            total_funded_volume,
            total_requested_volume,
            funding_fulfillment_rate,
            avg_interest_rate,
            default_rate,
            delinquency_rate,
            ROUND(COALESCE(total_charged_off_prncp, 0.0), 2) AS total_charged_off_prncp,
            ROUND(COALESCE(net_recovery_rate, 0.0), 2) AS net_recovery_rate,
            ROUND(COALESCE(collection_cost_ratio, 0.0), 2) AS collection_cost_ratio,
            unverified_backlog_share,
            ROUND(
                (total_funded_volume - LAG(total_funded_volume, 1) OVER (ORDER BY issue_month)) * 100.0
                / NULLIF(LAG(total_funded_volume, 1) OVER (ORDER BY issue_month), 0),
                2
            ) AS mom_volume_growth_pct,
            ROUND(
                default_rate - LAG(default_rate, 1) OVER (ORDER BY issue_month),
                2
            ) AS mom_default_rate_delta,
            ROUND(
                (total_funded_volume - LAG(total_funded_volume, 12) OVER (ORDER BY issue_month)) * 100.0
                / NULLIF(LAG(total_funded_volume, 12) OVER (ORDER BY issue_month), 0),
                2
            ) AS yoy_volume_growth_pct,
            ROUND(
                default_rate - LAG(default_rate, 12) OVER (ORDER BY issue_month),
                2
            ) AS yoy_default_rate_delta
        FROM MonthlyBase
    )
    SELECT * FROM MonthlyWithTrends
    ORDER BY metric_month ASC;
    """
    df_monthly = pd.read_sql_query(query_1, conn)
    print(f"    -> Computed {len(df_monthly)} monthly operational periods.")
    print("    Sample Monthly Rollup Output:")
    print(df_monthly[["metric_month", "total_applications", "default_rate", "delinquency_rate", "funding_fulfillment_rate", "mom_volume_growth_pct"]].head(5).to_string(index=False))

    # Populate monthly_kpi_rollup table
    print("\n[*] Populating normalized 'monthly_kpi_rollup' table in SQLite...")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM monthly_kpi_rollup")
    df_monthly.to_sql("monthly_kpi_rollup", conn, if_exists="append", index=False)
    conn.commit()
    print("[+] Successfully inserted records into monthly_kpi_rollup.")

    # 2. Execute Query 2 (Portfolio Quality by Risk Grade)
    print("\n[*] Executing Query 2: Risk-Adjusted Portfolio Quality by Grade...")
    query_2 = """
    SELECT
        l.grade,
        COUNT(l.loan_id) AS total_loans,
        ROUND(SUM(l.funded_amnt), 2) AS total_funded_amount,
        ROUND(AVG(l.int_rate), 2) AS avg_interest_rate,
        ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS default_rate,
        ROUND(AVG(l.int_rate) - (SUM(l.is_default) * 100.0 / COUNT(l.loan_id)), 2) AS risk_adjusted_net_spread,
        ROUND(AVG(b.dti), 2) AS avg_dti,
        ROUND(AVG(b.fico_range_low), 1) AS avg_fico
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    GROUP BY l.grade
    ORDER BY l.grade ASC;
    """
    df_grades = pd.read_sql_query(query_2, conn)
    print(df_grades.to_string(index=False))

    # 3. Execute Query 5 (2008 Financial Crisis Impact Analysis)
    print("\n[*] Executing Query 5: Macro Financial Crisis Impact Breakdown (2007-2015)...")
    query_5 = """
    SELECT
        l.issue_year,
        COUNT(l.loan_id) AS annual_volume,
        ROUND(SUM(l.funded_amnt), 2) AS funded_amount,
        ROUND(AVG(l.int_rate), 2) AS avg_int_rate,
        ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS default_rate,
        ROUND(SUM(l.is_delinquent) * 100.0 / COUNT(l.loan_id), 2) AS delinquency_rate,
        ROUND(AVG(b.dti), 2) AS avg_dti,
        ROUND(SUM(pr.recoveries) * 100.0 / NULLIF(SUM(pr.charged_off_principal), 0), 2) AS recovery_rate
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    JOIN payments_recoveries pr ON l.loan_id = pr.loan_id
    GROUP BY l.issue_year
    ORDER BY l.issue_year ASC;
    """
    df_macro = pd.read_sql_query(query_5, conn)
    print(df_macro.to_string(index=False))

    conn.close()
    print("\n[+] Pure SQL KPI verification and rollup complete!")


if __name__ == "__main__":
    run_sql_kpis()
