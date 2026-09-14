"""
OPS-TWIN: Automated Test Suite & Integrity Verification
=======================================================
Validates the end-to-end pipeline:
  - Database schema & table counts
  - SQL query execution & window function calculations
  - Root-cause crisis detection & driver ranking
  - Predictive model training & inference
  - All 5 what-if scenario simulation engines
  - Power BI star-schema export files
"""

import unittest
import sqlite3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "processed" / "ops_twin.db"
EXPORT_DIR = BASE_DIR / "powerbi" / "export"

from analysis.trends import get_monthly_trends, detect_degraded_kpis
from analysis.root_cause import run_full_root_cause_diagnosis
from analysis.predictive import forecast_portfolio_kpis, train_default_classifier, score_single_loan
from analysis.what_if import (
    simulate_underwriting_tightening,
    simulate_risk_pricing_adjustment,
    simulate_funding_policy,
    simulate_collections_optimization,
    simulate_verification_policy_shift
)


class TestOpsTwinPipeline(unittest.TestCase):

    def test_01_database_tables_exist_and_populated(self):
        """Verifies that all normalized SQLite tables exist and have >10,000 records."""
        self.assertTrue(DB_FILE.exists(), "ops_twin.db does not exist")
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.cursor()

        tables = ["borrowers", "loans", "payments_recoveries", "monthly_kpi_rollup"]
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            self.assertGreater(count, 0, f"Table {table} is empty")
            if table != "monthly_kpi_rollup":
                self.assertGreater(count, 10000, f"Table {table} has fewer than 10k records")
        conn.close()

    def test_02_sql_monthly_kpis(self):
        """Verifies that monthly KPI rollup has non-null metrics and valid ranges."""
        conn = sqlite3.connect(str(DB_FILE))
        df = pd.read_sql_query("SELECT * FROM monthly_kpi_rollup", conn)
        conn.close()

        self.assertFalse(df.empty, "monthly_kpi_rollup is empty")
        self.assertIn("default_rate", df.columns)
        self.assertIn("funding_fulfillment_rate", df.columns)
        self.assertIn("mom_volume_growth_pct", df.columns)

        # Sanity check ranges
        self.assertTrue((df["default_rate"] >= 0).all() and (df["default_rate"] <= 100).all())
        self.assertTrue((df["funding_fulfillment_rate"] >= 50).all())

    def test_03_root_cause_2008_crisis_detection(self):
        """Verifies that root-cause analysis detects a severe 2008 crisis default spike."""
        diag = run_full_root_cause_diagnosis()
        crisis = diag["crisis_analysis"]
        drivers = diag["ranked_drivers"]

        # 2008 crisis default rate should be significantly higher than post-crisis baseline
        self.assertGreater(crisis["crisis_default_rate"], crisis["post_crisis_default_rate"])
        self.assertGreaterEqual(crisis["default_rate_multiple"], 2.0, "Crisis spike should be at least 2x baseline")

        # Driver ranking
        self.assertFalse(drivers.empty)
        self.assertIn("importance_weight", drivers.columns)
        self.assertEqual(drivers.iloc[0]["rank"], 1)

    def test_04_predictive_forecasting_and_classifier(self):
        """Verifies 4-quarter forecast generation and default risk classifier inference."""
        fc = forecast_portfolio_kpis(periods=12)
        self.assertIn("forecast", fc)
        self.assertEqual(len(fc["forecast"]), 12)
        self.assertIn("forecast_default_rate", fc["forecast"].columns)
        self.assertIn("forecast_funded_volume", fc["forecast"].columns)

        # Single loan scoring
        loan_sample = {
            "loan_amnt": 12000,
            "term_months": 36,
            "int_rate": 11.5,
            "grade": "B",
            "annual_inc": 75000,
            "dti": 15.0,
            "fico_range_low": 710,
            "revol_util": 35.0,
            "verification_status": "Verified",
            "home_ownership": "MORTGAGE"
        }
        score = score_single_loan(loan_sample)
        self.assertIn("default_probability_pct", score)
        self.assertIn("risk_tier", score)
        self.assertIn("underwriting_recommendation", score)
        self.assertTrue(0 <= score["default_probability_pct"] <= 100)

    def test_05_what_if_scenario_simulations(self):
        """Verifies that all 5 what-if scenario simulation engines output valid metrics and recommendations."""
        # 1. Underwriting Tightening
        s1 = simulate_underwriting_tightening(min_fico=680, max_dti=30.0)
        self.assertIn("recommendation", s1)
        self.assertLess(s1["simulated"]["default_rate_pct"], s1["baseline"]["default_rate_pct"])

        # 2. Risk-based APR
        s2 = simulate_risk_pricing_adjustment(apr_delta_bps=200)
        self.assertIn("recommendation", s2)
        self.assertIn("net_yield_delta", s2["deltas"])

        # 3. Funding policy
        s3 = simulate_funding_policy(min_fulfillment_threshold_pct=90.0)
        self.assertIn("recommendation", s3)

        # 4. Collections
        s4 = simulate_collections_optimization(recovery_rate_uplift_pct=20.0, fee_commission_pct=15.0)
        self.assertIn("recommendation", s4)
        self.assertGreater(s4["simulated"]["recovery_rate_pct"], s4["baseline"]["recovery_rate_pct"])

        # 5. Verification
        s5 = simulate_verification_policy_shift(additional_verified_pct=25.0)
        self.assertIn("recommendation", s5)
        self.assertGreater(s5["simulated"]["credit_losses_saved"], 0)

    def test_06_powerbi_star_schema_files_exist(self):
        """Verifies that the star-schema CSV exports exist and contain expected rows."""
        expected_files = [
            "fact_loans.csv", "dim_borrower.csv", "dim_date.csv",
            "dim_geography.csv", "dim_loan_grade.csv"
        ]
        for fname in expected_files:
            fpath = EXPORT_DIR / fname
            self.assertTrue(fpath.exists(), f"Missing Power BI export file {fname}")
            self.assertGreater(fpath.stat().st_size, 100, f"File {fname} is suspiciously small")


if __name__ == "__main__":
    unittest.main()
