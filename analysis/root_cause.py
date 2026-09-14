"""
OPS-TWIN: Root-Cause Analysis & Diagnostic Engine
=================================================
Performs root-cause analysis on lending operations degradations:
  1. Detects historical degraded periods (specifically isolating the 2008 financial crisis shock).
  2. Runs correlation and tree-based feature importance against real candidate drivers:
     - Grade/Sub-grade
     - Debt-to-Income (DTI)
     - Annual Income
     - Home Ownership
     - Verification Status
     - Revolving Utilization
     - Loan Purpose
     - FICO Score
  3. Produces a ranked 'Likely Drivers' diagnostic table with plain-language attributions.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "processed" / "ops_twin.db"


def get_db_connection():
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found at {DB_FILE}")
    return sqlite3.connect(str(DB_FILE))


def analyze_crisis_period():
    """
    Isolates the 2008-2009 Global Financial Crisis period and compares core credit
    and operations metrics against the stabilized baseline (2010-2015).
    """
    conn = get_db_connection()
    query = """
    SELECT
        l.issue_year,
        COUNT(l.loan_id) AS loan_count,
        ROUND(SUM(l.funded_amnt), 2) AS funded_volume,
        ROUND(AVG(l.int_rate), 2) AS avg_int_rate,
        ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS default_rate,
        ROUND(SUM(l.is_delinquent) * 100.0 / COUNT(l.loan_id), 2) AS delinquency_rate,
        ROUND(AVG(b.dti), 2) AS avg_dti,
        ROUND(AVG(b.annual_inc), 2) AS avg_annual_inc,
        ROUND(AVG(b.fico_range_low), 1) AS avg_fico,
        ROUND(
            SUM(pr.recoveries) * 100.0 / NULLIF(SUM(pr.charged_off_principal), 0),
            2
        ) AS recovery_rate,
        ROUND(
            SUM(CASE WHEN b.verification_status = 'Not Verified' THEN 1 ELSE 0 END) * 100.0 / COUNT(l.loan_id),
            2
        ) AS unverified_rate
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    JOIN payments_recoveries pr ON l.loan_id = pr.loan_id
    GROUP BY l.issue_year
    ORDER BY l.issue_year ASC;
    """
    df_years = pd.read_sql_query(query, conn)
    conn.close()

    # Define crisis window (2007-2009) vs post-crisis recovery (2010-2015)
    crisis_mask = df_years["issue_year"].isin([2007, 2008, 2009])
    crisis_stats = {
        "crisis_default_rate": round(
            df_years.loc[crisis_mask, "loan_count"].dot(df_years.loc[crisis_mask, "default_rate"])
            / df_years.loc[crisis_mask, "loan_count"].sum(),
            2
        ),
        "post_crisis_default_rate": round(
            df_years.loc[~crisis_mask, "loan_count"].dot(df_years.loc[~crisis_mask, "default_rate"])
            / df_years.loc[~crisis_mask, "loan_count"].sum(),
            2
        ),
        "crisis_recovery_rate": round(df_years.loc[crisis_mask, "recovery_rate"].mean(), 2),
        "post_crisis_recovery_rate": round(df_years.loc[~crisis_mask, "recovery_rate"].mean(), 2),
        "yearly_breakdown": df_years
    }
    
    crisis_stats["default_rate_multiple"] = round(
        crisis_stats["crisis_default_rate"] / max(crisis_stats["post_crisis_default_rate"], 0.01),
        2
    )
    return crisis_stats


def compute_driver_importances(sample_size=30000):
    """
    Runs statistical correlation and Random Forest feature importance against
    real loan candidate drivers to determine the root causes of credit defaults.
    """
    conn = get_db_connection()
    # Pull relevant resolved loans (Fully Paid, Charged Off, Default)
    query = f"""
    SELECT
        l.loan_id,
        l.is_default,
        l.loan_amnt,
        l.funded_amnt,
        l.int_rate,
        l.grade,
        l.purpose,
        b.annual_inc,
        b.dti,
        b.fico_range_low,
        b.revol_util,
        b.home_ownership,
        b.verification_status,
        b.addr_state
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    WHERE l.loan_status IN ('Fully Paid', 'Charged Off', 'Default')
    ORDER BY RANDOM()
    LIMIT {sample_size}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty or len(df["is_default"].unique()) < 2:
        return pd.DataFrame()

    # Preprocess Features
    # 1. Ordinal Grade
    grade_order = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7}
    df["grade_encoded"] = df["grade"].map(grade_order).fillna(4)

    # 2. Categorical Encodings
    le_purpose = LabelEncoder()
    df["purpose_encoded"] = le_purpose.fit_transform(df["purpose"].astype(str))

    le_home = LabelEncoder()
    df["home_encoded"] = le_home.fit_transform(df["home_ownership"].astype(str))

    # Binary unverified flag
    df["is_unverified"] = (df["verification_status"] == "Not Verified").astype(int)

    feature_cols = [
        "grade_encoded", "int_rate", "dti", "fico_range_low",
        "annual_inc", "revol_util", "loan_amnt", "is_unverified",
        "home_encoded", "purpose_encoded"
    ]

    feature_labels = {
        "grade_encoded": "Credit Risk Grade (A-G Tier)",
        "int_rate": "Loan Interest Rate (APR %)",
        "dti": "Debt-to-Income Ratio (DTI %)",
        "fico_range_low": "Borrower Credit Score (FICO)",
        "annual_inc": "Annual Household Income ($)",
        "revol_util": "Revolving Credit Utilization (%)",
        "loan_amnt": "Requested Loan Principal ($)",
        "is_unverified": "Income Documentation (Unverified Backlog)",
        "home_encoded": "Home Ownership Type (Rent vs Own)",
        "purpose_encoded": "Loan Stated Purpose Category"
    }

    X = df[feature_cols].copy().fillna(0)
    y = df["is_default"].astype(int)

    # Train Random Forest to extract Gini importance
    rf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
    rf.fit(X, y)

    # Compute correlation with target
    correlations = {}
    for col in feature_cols:
        correlations[col] = df[col].corr(df["is_default"])

    importances = rf.feature_importances_
    results = []
    
    # Contextual diagnostic narratives
    narratives = {
        "grade_encoded": "Subprime grade tiers (D-G) exhibit significantly higher default velocity. Primary driver of aggregate portfolio loss.",
        "int_rate": "Higher interest burden elevates monthly debt obligations, compounding borrower default probability.",
        "dti": "Excessive debt-to-income limits borrower cashflow cushion during income interruptions or macro distress.",
        "fico_range_low": "Lower FICO scores correlate strongly with prior delinquency history and vulnerability to macro shocks.",
        "annual_inc": "Lower income tiers lack liquidity reserves; defaults spike when income drops below debt service capacity.",
        "revol_util": "High credit card utilization indicates revolving credit dependency and liquidity strain.",
        "loan_amnt": "Larger balances carry heavier monthly installments, magnifying loss severity upon charge-off.",
        "is_unverified": "Unverified income applications carry elevated misstatement risk and higher delinquency rates.",
        "home_encoded": "Renters demonstrate slightly higher mobility and default rates than mortgage holders.",
        "purpose_encoded": "Small business loans and emergency consolidations show higher default dispersion than consumer debt."
    }

    for col, imp in zip(feature_cols, importances):
        results.append({
            "driver_key": col,
            "driver_name": feature_labels[col],
            "importance_weight": round(float(imp) * 100, 2),
            "correlation_with_default": round(float(correlations.get(col, 0.0)), 4),
            "direction": "Positive (+)" if correlations.get(col, 0.0) >= 0 else "Negative (-)",
            "diagnostic_narrative": narratives.get(col, "Identified as a statistically significant risk factor.")
        })

    df_ranked = pd.DataFrame(results).sort_values(by="importance_weight", ascending=False).reset_index(drop=True)
    df_ranked["rank"] = df_ranked.index + 1
    return df_ranked


def run_full_root_cause_diagnosis():
    """Returns the complete Root-Cause diagnostic package."""
    crisis = analyze_crisis_period()
    drivers = compute_driver_importances()
    return {
        "crisis_analysis": crisis,
        "ranked_drivers": drivers
    }


if __name__ == "__main__":
    print("=" * 70)
    print("  OPS-TWIN: Root-Cause Analysis Engine Run")
    print("=" * 70)
    diagnosis = run_full_root_cause_diagnosis()
    
    crisis = diagnosis["crisis_analysis"]
    print(f"\n[*] 2008 Financial Crisis Detection:")
    print(f"    Crisis Window Default Rate (2007-2009): {crisis['crisis_default_rate']:.2f}%")
    print(f"    Post-Crisis Default Rate (2010-2015):    {crisis['post_crisis_default_rate']:.2f}%")
    print(f"    Crisis Default Rate Multiple:           {crisis['default_rate_multiple']:.1f}x spike")
    
    print("\n[*] Top 5 Ranked Root-Cause Drivers:")
    print(diagnosis["ranked_drivers"][["rank", "driver_name", "importance_weight", "correlation_with_default"]].head(5).to_string(index=False))
