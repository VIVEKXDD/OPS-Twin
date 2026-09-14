"""
OPS-TWIN: Predictive Analytics & Forecasting Engine
==================================================
Delivers dual predictive capabilities for lending operations:
  1. Portfolio-Level Macro Time-Series Forecasts (4 Quarters / 12 Months):
     - Forecasts Default Rate (%) and Monthly Funded Volume ($) with 95% confidence bands
     - Uses statsmodels Exponential Smoothing / ARIMA time-series models.
  2. Loan-Level Default Risk Classifier:
     - Machine Learning model trained on real loan & borrower attributes
     - Predicts individual loan default probability (0-100%)
     - Computes ROC-AUC, PR-AUC, confusion matrix, and feature importances
     - Provides instant interactive inference for underwriting decision support.
"""

import sqlite3
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.arima.model import ARIMA

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "processed" / "ops_twin.db"
MODEL_FILE = BASE_DIR / "data" / "processed" / "default_classifier.joblib"


def get_db_connection():
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found at {DB_FILE}")
    return sqlite3.connect(str(DB_FILE))


# ==============================================================================
# 1. PORTFOLIO-LEVEL TIME SERIES FORECASTING (4 QUARTERS / 12 MONTHS)
# ==============================================================================

def forecast_portfolio_kpis(periods=12):
    """
    Forecasts future quarters (12 months) for:
      - Default Rate (%)
      - Monthly Funded Volume ($)
    Returns historical data combined with forecasts and 95% confidence intervals.
    """
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT metric_month, total_funded_volume, default_rate FROM monthly_kpi_rollup ORDER BY metric_month ASC", conn)
    conn.close()

    if df.empty or len(df) < 10:
        return {}

    # Sort and clean index
    df["date"] = pd.to_datetime(df["metric_month"] + "-01")
    df = df.sort_values("date").reset_index(drop=True)

    # 1. Forecast Default Rate
    ts_default = df["default_rate"].values
    try:
        # Fit Holt-Winters or ARIMA
        model_def = ExponentialSmoothing(ts_default, trend="add", seasonal=None, damped_trend=True).fit()
        fc_default = model_def.forecast(periods)
    except Exception:
        # Robust fallback using polynomial/linear trend
        x = np.arange(len(ts_default))
        z = np.polyfit(x, ts_default, 1)
        p = np.poly1d(z)
        fc_default = p(np.arange(len(ts_default), len(ts_default) + periods))
    
    # Clip default forecast to non-negative
    fc_default = np.clip(fc_default, 0.5, 30.0)
    std_default = np.std(ts_default[-12:]) if len(ts_default) >= 12 else np.std(ts_default)
    upper_default = fc_default + 1.96 * std_default
    lower_default = np.maximum(0.0, fc_default - 1.96 * std_default)

    # 2. Forecast Funded Volume
    ts_vol = df["total_funded_volume"].values
    try:
        model_vol = ExponentialSmoothing(ts_vol, trend="add", seasonal=None, damped_trend=True).fit()
        fc_vol = model_vol.forecast(periods)
    except Exception:
        x = np.arange(len(ts_vol))
        z = np.polyfit(x, ts_vol, 1)
        p = np.poly1d(z)
        fc_vol = p(np.arange(len(ts_vol), len(ts_vol) + periods))
    
    fc_vol = np.maximum(1000000.0, fc_vol)
    std_vol = np.std(ts_vol[-12:]) if len(ts_vol) >= 12 else np.std(ts_vol)
    upper_vol = fc_vol + 1.96 * std_vol
    lower_vol = np.maximum(0.0, fc_vol - 1.96 * std_vol)

    # Generate future dates
    last_date = df["date"].iloc[-1]
    future_dates = [last_date + pd.DateOffset(months=i+1) for i in range(periods)]
    future_months = [d.strftime("%Y-%m") for d in future_dates]

    forecast_df = pd.DataFrame({
        "metric_month": future_months,
        "date": future_dates,
        "forecast_default_rate": np.round(fc_default, 2),
        "default_rate_lower": np.round(lower_default, 2),
        "default_rate_upper": np.round(upper_default, 2),
        "forecast_funded_volume": np.round(fc_vol, 2),
        "volume_lower": np.round(lower_vol, 2),
        "volume_upper": np.round(upper_vol, 2)
    })

    return {
        "historical": df,
        "forecast": forecast_df
    }


# ==============================================================================
# 2. LOAN-LEVEL DEFAULT RISK CLASSIFIER
# ==============================================================================

GRADE_MAP = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7}
TERM_MAP = {"36 months": 36, "60 months": 60}


def prepare_loan_dataset(sample_size=50000):
    """Loads and preprocesses real loan data for default classification."""
    conn = get_db_connection()
    query = f"""
    SELECT
        l.loan_id,
        l.is_default,
        l.loan_amnt,
        l.term,
        l.int_rate,
        l.installment,
        l.grade,
        b.annual_inc,
        b.dti,
        b.fico_range_low,
        b.revol_util,
        b.open_acc,
        b.total_acc,
        b.verification_status,
        b.home_ownership
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    WHERE l.loan_status IN ('Fully Paid', 'Charged Off', 'Default')
    ORDER BY RANDOM()
    LIMIT {sample_size}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Feature transformations
    df["grade_code"] = df["grade"].map(GRADE_MAP).fillna(4)
    df["term_months"] = df["term"].map(TERM_MAP).fillna(36)
    df["is_unverified"] = (df["verification_status"] == "Not Verified").astype(int)
    df["is_homeowner"] = df["home_ownership"].isin(["OWN", "MORTGAGE"]).astype(int)
    df["dti"] = df["dti"].clip(0, 50)
    df["revol_util"] = df["revol_util"].clip(0, 120)
    df["annual_inc"] = np.log1p(df["annual_inc"].clip(5000, 500000))

    feature_cols = [
        "loan_amnt", "term_months", "int_rate", "installment",
        "grade_code", "annual_inc", "dti", "fico_range_low",
        "revol_util", "open_acc", "is_unverified", "is_homeowner"
    ]
    
    X = df[feature_cols].fillna(0)
    y = df["is_default"].astype(int)
    return X, y, feature_cols


def train_default_classifier(force_retrain=False):
    """
    Trains and evaluates the loan default risk classifier.
    Caches model artifact to disk for instant dashboard inference.
    """
    if MODEL_FILE.exists() and not force_retrain:
        print(f"[*] Loading cached default classifier from {MODEL_FILE}...")
        return joblib.load(MODEL_FILE)

    print("[*] Training loan-level default risk classifier on authentic loan data...")
    X, y, feature_cols = prepare_loan_dataset(sample_size=40000)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Train Gradient Boosting Classifier
    clf = GradientBoostingClassifier(
        n_estimators=120,
        learning_rate=0.08,
        max_depth=4,
        random_state=42
    )
    clf.fit(X_train, y_train)

    # Predictions & Metrics
    y_pred_proba = clf.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.25).astype(int) # Underwriting decision threshold

    roc_auc = roc_auc_score(y_test, y_pred_proba)
    pr_auc = average_precision_score(y_test, y_pred_proba)
    cm = confusion_matrix(y_test, y_pred)

    print(f"    -> ROC-AUC: {roc_auc:.4f}")
    print(f"    -> PR-AUC:  {pr_auc:.4f}")
    print(f"    -> Confusion Matrix:\n{cm}")

    # Package model metadata
    model_bundle = {
        "model": clf,
        "feature_cols": feature_cols,
        "roc_auc": round(float(roc_auc), 4),
        "pr_auc": round(float(pr_auc), 4),
        "test_sample_size": len(y_test),
        "default_prior": round(float(y.mean() * 100), 2),
        "feature_importances": dict(zip(feature_cols, [round(float(v) * 100, 2) for v in clf.feature_importances_]))
    }

    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_bundle, MODEL_FILE)
    print(f"[+] Model saved to {MODEL_FILE}")
    return model_bundle


def score_single_loan(loan_input_dict):
    """
    Scores an individual loan application.
    Returns:
      - default_prob_pct: Estimated default probability (0 - 100%)
      - risk_tier: 'Low', 'Moderate', 'Elevated', 'High', 'Critical'
      - recommendation: 'Approve (Fast-Track)', 'Approve (Standard)', 'Manual Review / Counter-Offer', 'Decline'
    """
    bundle = train_default_classifier()
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]

    # Preprocess incoming dict
    row = {
        "loan_amnt": float(loan_input_dict.get("loan_amnt", 10000)),
        "term_months": int(loan_input_dict.get("term_months", 36)),
        "int_rate": float(loan_input_dict.get("int_rate", 12.0)),
        "installment": float(loan_input_dict.get("installment", 330.0)),
        "grade_code": GRADE_MAP.get(loan_input_dict.get("grade", "C"), 3),
        "annual_inc": np.log1p(max(float(loan_input_dict.get("annual_inc", 65000)), 1000)),
        "dti": float(loan_input_dict.get("dti", 18.0)),
        "fico_range_low": float(loan_input_dict.get("fico_range_low", 690)),
        "revol_util": float(loan_input_dict.get("revol_util", 45.0)),
        "open_acc": int(loan_input_dict.get("open_acc", 10)),
        "is_unverified": 1 if loan_input_dict.get("verification_status") == "Not Verified" else 0,
        "is_homeowner": 1 if loan_input_dict.get("home_ownership") in ["OWN", "MORTGAGE"] else 0
    }

    X_single = pd.DataFrame([row])[feature_cols]
    prob = float(model.predict_proba(X_single)[0, 1]) * 100.0

    if prob < 5.0:
        tier = "Prime (Low Risk)"
        rec = "Approve (Fast-Track Automated Issuance)"
    elif prob < 12.0:
        tier = "Near-Prime (Moderate Risk)"
        rec = "Approve (Standard Underwriting Terms)"
    elif prob < 22.0:
        tier = "Subprime (Elevated Risk)"
        rec = "Manual Underwriting / Require Income Verification"
    elif prob < 35.0:
        tier = "High Risk"
        rec = "Counter-Offer (Lower Principal / Higher APR / Co-signer)"
    else:
        tier = "Critical Default Risk"
        rec = "Decline Application (Credit Policy Breach)"

    return {
        "default_probability_pct": round(prob, 2),
        "risk_tier": tier,
        "underwriting_recommendation": rec
    }


if __name__ == "__main__":
    print("=" * 70)
    print("  OPS-TWIN: Predictive Analytics Engine Test")
    print("=" * 70)
    
    # 1. Test Forecast
    fc = forecast_portfolio_kpis(periods=12)
    if "forecast" in fc:
        print("\n[*] 4-Quarter (12-Month) Forecast:")
        print(fc["forecast"][["metric_month", "forecast_default_rate", "forecast_funded_volume"]].head(6).to_string(index=False))

    # 2. Test Model Training
    bundle = train_default_classifier(force_retrain=True)
    print(f"\n[*] Model Trained. ROC-AUC: {bundle['roc_auc']}, PR-AUC: {bundle['pr_auc']}")

    # 3. Test Single Loan Inference
    test_loan = {
        "loan_amnt": 15000,
        "term_months": 36,
        "int_rate": 14.5,
        "grade": "C",
        "annual_inc": 55000,
        "dti": 24.5,
        "fico_range_low": 660,
        "revol_util": 68.0,
        "verification_status": "Not Verified",
        "home_ownership": "RENT"
    }
    score = score_single_loan(test_loan)
    print(f"\n[*] Sample Underwriting Decision:")
    print(f"    Default Probability: {score['default_probability_pct']}%")
    print(f"    Risk Tier:          {score['risk_tier']}")
    print(f"    Action:             {score['underwriting_recommendation']}")
