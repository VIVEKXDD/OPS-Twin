"""
OPS-TWIN: Interactive What-If Scenario Simulation Engine
========================================================
Implements 5 parameterized decision-support simulations layered on real historical baselines:
  1. Underwriting Tightening: Min FICO & Max DTI adjustments vs volume sacrifice
  2. Risk-Based Pricing: APR basis point shifts on grades C-G vs net interest return
  3. Funding Fulfillment Policy: Minimum investor commitment threshold vs funded pipeline
  4. Collections Optimization: Recovery rate improvement vs net loss and agency fees
  5. Verification Capacity Reallocation: Income verification shift vs underwriting queue cost

Each scenario calculates dynamic before/after metrics and auto-generates
executive decision recommendations.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "processed" / "ops_twin.db"


def get_db_connection():
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found at {DB_FILE}")
    return sqlite3.connect(str(DB_FILE))


# ==============================================================================
# SCENARIO 1: TIGHTEN UNDERWRITING CRITERIA
# ==============================================================================

def simulate_underwriting_tightening(min_fico=660, max_dti=35.0):
    """
    Simulates raising the minimum FICO score cutoff and/or capping maximum DTI.
    Evaluates:
      - Reduction in default rate
      - Volume sacrificed ($ and %)
      - Net credit losses saved
    """
    conn = get_db_connection()
    query = """
    SELECT
        l.loan_id,
        l.loan_amnt,
        l.funded_amnt,
        l.is_default,
        pr.charged_off_principal,
        b.fico_range_low,
        b.dti
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    JOIN payments_recoveries pr ON l.loan_id = pr.loan_id
    WHERE l.loan_status IN ('Fully Paid', 'Charged Off', 'Default')
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    total_loans = len(df)
    baseline_volume = df["funded_amnt"].sum()
    baseline_defaults = df["is_default"].sum()
    baseline_default_rate = (baseline_defaults / total_loans) * 100.0
    baseline_losses = df["charged_off_principal"].sum()

    # Apply tightened criteria
    approved_mask = (df["fico_range_low"] >= min_fico) & (df["dti"] <= max_dti)
    df_sim = df[approved_mask]

    sim_loans = len(df_sim)
    sim_volume = df_sim["funded_amnt"].sum()
    sim_defaults = df_sim["is_default"].sum()
    sim_default_rate = (sim_defaults / sim_loans * 100.0) if sim_loans > 0 else 0.0
    sim_losses = df_sim["charged_off_principal"].sum()

    volume_change_pct = ((sim_volume - baseline_volume) / baseline_volume) * 100.0
    default_rate_delta = sim_default_rate - baseline_default_rate
    losses_saved = baseline_losses - sim_losses
    volume_sacrificed = baseline_volume - sim_volume

    # Recommendation logic
    if abs(volume_change_pct) < 10.0 and default_rate_delta <= -1.0:
        rec = f"Highly Recommended: Tightening to FICO >= {min_fico} & DTI <= {max_dti}% reduces default rate by {abs(default_rate_delta):.2f} pts and saves ${losses_saved:,.0f} in credit losses while sacrificing only {abs(volume_change_pct):.1f}% of origination volume."
    elif abs(volume_change_pct) > 25.0:
        rec = f"Caution (Severe Volume Drag): Tightening eliminates {abs(volume_change_pct):.1f}% of origination volume (${volume_sacrificed:,.0f}). Although default rate drops by {abs(default_rate_delta):.2f} pts, the revenue loss outweighs credit loss mitigation."
    else:
        rec = f"Moderate Trade-off: Saves ${losses_saved:,.0f} in gross charge-offs with a {abs(volume_change_pct):.1f}% reduction in originations. Consider phased implementation."

    return {
        "scenario_name": "Underwriting Tightening (FICO / DTI)",
        "inputs": {"min_fico": min_fico, "max_dti": max_dti},
        "baseline": {
            "loan_count": int(total_loans),
            "funded_volume": round(float(baseline_volume), 2),
            "default_rate_pct": round(float(baseline_default_rate), 2),
            "credit_losses": round(float(baseline_losses), 2)
        },
        "simulated": {
            "loan_count": int(sim_loans),
            "funded_volume": round(float(sim_volume), 2),
            "default_rate_pct": round(float(sim_default_rate), 2),
            "credit_losses": round(float(sim_losses), 2)
        },
        "deltas": {
            "volume_change_pct": round(float(volume_change_pct), 2),
            "default_rate_delta_pts": round(float(default_rate_delta), 2),
            "losses_saved_dollars": round(float(losses_saved), 2),
            "volume_sacrificed_dollars": round(float(volume_sacrificed), 2)
        },
        "recommendation": rec
    }


# ==============================================================================
# SCENARIO 2: ADJUST RISK-BASED INTEREST PRICING (GRADES C-G)
# ==============================================================================

def simulate_risk_pricing_adjustment(apr_delta_bps=150):
    """
    Simulates adjusting APR pricing by +/- X basis points for lower grades (C, D, E, F, G).
    Evaluates:
      - Gross interest income impact
      - Modeled adverse selection / default sensitivity
      - Default-adjusted net yield
    """
    conn = get_db_connection()
    query = """
    SELECT
        l.grade,
        l.funded_amnt,
        l.int_rate,
        l.is_default,
        pr.charged_off_principal
    FROM loans l
    JOIN payments_recoveries pr ON l.loan_id = pr.loan_id
    WHERE l.loan_status IN ('Fully Paid', 'Charged Off', 'Default')
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    baseline_interest_income = (df["funded_amnt"] * df["int_rate"] / 100.0).sum()
    baseline_losses = df["charged_off_principal"].sum()
    baseline_net_yield = baseline_interest_income - baseline_losses

    # Apply APR shift to grades C, D, E, F, G
    subprime_mask = df["grade"].isin(["C", "D", "E", "F", "G"])
    df["sim_int_rate"] = df["int_rate"]
    df.loc[subprime_mask, "sim_int_rate"] = df.loc[subprime_mask, "int_rate"] + (apr_delta_bps / 100.0)

    # Elasticity / adverse selection: higher rates slightly increase subprime default probability (+0.08% per 100 bps)
    elasticity_factor = 1.0 + (apr_delta_bps / 100.0) * 0.008
    sim_interest_income = (df["funded_amnt"] * df["sim_int_rate"] / 100.0).sum()
    sim_losses = baseline_losses * (elasticity_factor if apr_delta_bps > 0 else max(0.9, elasticity_factor))
    sim_net_yield = sim_interest_income - sim_losses

    delta_income = sim_interest_income - baseline_interest_income
    delta_net_yield = sim_net_yield - baseline_net_yield

    if delta_net_yield > 0:
        rec = f"Positive Net Return: Adjusting lower-grade pricing by {apr_delta_bps:+d} bps increases annual interest revenue by ${delta_income:,.0f}, yielding a net bottom-line gain of ${delta_net_yield:,.0f} after accounting for adverse selection."
    else:
        rec = f"Negative Trade-off: Rate adjustment of {apr_delta_bps:+d} bps results in a net yield reduction of ${abs(delta_net_yield):.0f} due to elevated borrower default sensitivity."

    return {
        "scenario_name": "Risk-Based APR Repricing (Grades C-G)",
        "inputs": {"apr_delta_bps": apr_delta_bps},
        "baseline": {
            "gross_interest_income": round(float(baseline_interest_income), 2),
            "expected_losses": round(float(baseline_losses), 2),
            "net_yield": round(float(baseline_net_yield), 2)
        },
        "simulated": {
            "gross_interest_income": round(float(sim_interest_income), 2),
            "expected_losses": round(float(sim_losses), 2),
            "net_yield": round(float(sim_net_yield), 2)
        },
        "deltas": {
            "interest_income_delta": round(float(delta_income), 2),
            "net_yield_delta": round(float(delta_net_yield), 2),
            "net_yield_growth_pct": round(float((delta_net_yield / abs(baseline_net_yield)) * 100.0), 2)
        },
        "recommendation": rec
    }


# ==============================================================================
# SCENARIO 3: FUNDING FULFILLMENT POLICY & THRESHOLD
# ==============================================================================

def simulate_funding_policy(min_fulfillment_threshold_pct=95.0):
    """
    Simulates requiring a minimum investor funding threshold (e.g. 95% vs 100%)
    before issuing a loan. Loans below threshold are cancelled or delayed.
    """
    conn = get_db_connection()
    query = """
    SELECT
        loan_id,
        loan_amnt,
        funded_amnt,
        (funded_amnt * 100.0 / NULLIF(loan_amnt, 0)) AS fulfillment_pct,
        is_default
    FROM loans
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    total_loans = len(df)
    baseline_fully_funded = (df["fulfillment_pct"] >= 99.9).sum()
    baseline_fully_funded_pct = (baseline_fully_funded / total_loans) * 100.0
    baseline_total_funded = df["funded_amnt"].sum()

    # Policy threshold
    funded_under_policy = df[df["fulfillment_pct"] >= min_fulfillment_threshold_pct]
    cancelled_loans = total_loans - len(funded_under_policy)
    sim_fully_funded_pct = (len(funded_under_policy) / total_loans) * 100.0
    sim_funded_volume = funded_under_policy["funded_amnt"].sum()
    volume_drop_pct = ((sim_funded_volume - baseline_total_funded) / baseline_total_funded) * 100.0

    rec = (
        f"Policy Threshold at {min_fulfillment_threshold_pct}%: Qualifies {sim_fully_funded_pct:.1f}% of origination pipeline. "
        f"Drops {cancelled_loans:,} partially funded applications (${abs(sim_funded_volume - baseline_total_funded):,.0f} volume impact). "
        f"Guarantees near-complete investor backing and eliminates partial-origination servicing friction."
    )

    return {
        "scenario_name": "Funding Fulfillment Policy Threshold",
        "inputs": {"min_fulfillment_threshold_pct": min_fulfillment_threshold_pct},
        "baseline": {
            "total_applications": total_loans,
            "qualified_loans_pct": round(float(baseline_fully_funded_pct), 2),
            "funded_volume": round(float(baseline_total_funded), 2)
        },
        "simulated": {
            "qualified_loans_count": len(funded_under_policy),
            "qualified_loans_pct": round(float(sim_fully_funded_pct), 2),
            "funded_volume": round(float(sim_funded_volume), 2),
            "cancelled_loans_count": int(cancelled_loans)
        },
        "deltas": {
            "volume_impact_pct": round(float(volume_drop_pct), 2),
            "cancelled_applications": int(cancelled_loans)
        },
        "recommendation": rec
    }


# ==============================================================================
# SCENARIO 4: IMPROVE COLLECTIONS RECOVERY EFFECTIVENESS
# ==============================================================================

def simulate_collections_optimization(recovery_rate_uplift_pct=25.0, fee_commission_pct=16.0):
    """
    Simulates operational improvements in collections and recovery workflows:
      - Uplift in recoveries on charged-off loans (+X%)
      - Negotiated collection agency fee commission (e.g. 16% vs baseline ~18%)
    """
    conn = get_db_connection()
    query = """
    SELECT
        pr.loan_id,
        pr.charged_off_principal,
        pr.recoveries,
        pr.collection_recovery_fee
    FROM payments_recoveries pr
    JOIN loans l ON pr.loan_id = l.loan_id
    WHERE l.is_default = 1 AND pr.charged_off_principal > 0
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    baseline_recoveries = df["recoveries"].sum()
    baseline_fees = df["collection_recovery_fee"].sum()
    baseline_net_cash = baseline_recoveries - baseline_fees
    baseline_loss_principal = df["charged_off_principal"].sum()
    baseline_recovery_rate = (baseline_recoveries / baseline_loss_principal) * 100.0

    # Apply uplift
    sim_recoveries = baseline_recoveries * (1.0 + recovery_rate_uplift_pct / 100.0)
    sim_fees = sim_recoveries * (fee_commission_pct / 100.0)
    sim_net_cash = sim_recoveries - sim_fees
    sim_recovery_rate = (sim_recoveries / baseline_loss_principal) * 100.0

    net_cash_delta = sim_net_cash - baseline_net_cash
    fee_savings = (sim_recoveries * 0.18) - sim_fees # comparing against 18% standard fee

    rec = (
        f"Collections Enhancement (+{recovery_rate_uplift_pct}% recovery uplift, {fee_commission_pct}% fee cap): "
        f"Recovers an additional ${sim_recoveries - baseline_recoveries:,.0f} in delinquent balances, yielding ${net_cash_delta:,.0f} in net cash after fees. "
        f"Increases portfolio recovery rate from {baseline_recovery_rate:.2f}% to {sim_recovery_rate:.2f}%."
    )

    return {
        "scenario_name": "Collections Recovery & Fee Optimization",
        "inputs": {
            "recovery_rate_uplift_pct": recovery_rate_uplift_pct,
            "fee_commission_pct": fee_commission_pct
        },
        "baseline": {
            "gross_recoveries": round(float(baseline_recoveries), 2),
            "collection_fees": round(float(baseline_fees), 2),
            "net_recovered_cash": round(float(baseline_net_cash), 2),
            "recovery_rate_pct": round(float(baseline_recovery_rate), 2)
        },
        "simulated": {
            "gross_recoveries": round(float(sim_recoveries), 2),
            "collection_fees": round(float(sim_fees), 2),
            "net_recovered_cash": round(float(sim_net_cash), 2),
            "recovery_rate_pct": round(float(sim_recovery_rate), 2)
        },
        "deltas": {
            "net_cash_delta": round(float(net_cash_delta), 2),
            "net_cash_uplift_pct": round(float((net_cash_delta / max(baseline_net_cash, 1)) * 100.0), 2)
        },
        "recommendation": rec
    }


# ==============================================================================
# SCENARIO 5: VERIFICATION POLICY SHIFT & CAPACITY QUEUE TRADE-OFF
# ==============================================================================

def simulate_verification_policy_shift(additional_verified_pct=30.0, review_cost_per_loan=35.0):
    """
    Simulates shifting X% of 'Not Verified' applicants into mandatory documentation verification.
    Evaluates:
      - Credit loss mitigation from documentation verification
      - Underwriting processing backlog & capacity cost trade-off
      - Net economic benefit
    """
    conn = get_db_connection()
    query = """
    SELECT
        l.loan_id,
        l.funded_amnt,
        l.is_default,
        pr.charged_off_principal,
        b.verification_status
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    JOIN payments_recoveries pr ON l.loan_id = pr.loan_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    total_loans = len(df)
    unverified_mask = df["verification_status"].astype(str).str.lower().str.contains("not verified")
    unverified_loans = unverified_mask.sum()
    baseline_unverified_share = (unverified_loans / total_loans) * 100.0

    # Historical default rate spread: unverified loans carry ~18% higher default frequency
    unverified_df = df[unverified_mask]
    baseline_unverified_losses = unverified_df["charged_off_principal"].sum()

    # Model shifting additional_verified_pct into verification
    loans_to_verify = int(unverified_loans * (additional_verified_pct / 100.0))
    # Verification reduces unverified default loss by ~16% on verified cohort
    credit_losses_saved = (baseline_unverified_losses / max(unverified_loans, 1)) * loans_to_verify * 0.16
    operational_processing_cost = loans_to_verify * review_cost_per_loan
    net_economic_benefit = credit_losses_saved - operational_processing_cost
    sim_unverified_share = ((unverified_loans - loans_to_verify) / total_loans) * 100.0

    if net_economic_benefit > 0:
        rec = (
            f"Profitable Capacity Allocation: Converting {additional_verified_pct}% of unverified pipeline ({loans_to_verify:,} loans) "
            f"saves ${credit_losses_saved:,.0f} in credit losses against ${operational_processing_cost:,.0f} in verification review costs, "
            f"delivering a net operational gain of ${net_economic_benefit:,.0f}."
        )
    else:
        rec = (
            f"Capacity Warning: Verification costs (${operational_processing_cost:,.0f}) exceed the credit losses saved (${credit_losses_saved:,.0f}). "
            f"Target verification strictly on higher loan amounts (> $20k) or risk grades C-G."
        )

    return {
        "scenario_name": "Verification Policy & Capacity Trade-off",
        "inputs": {
            "additional_verified_pct": additional_verified_pct,
            "review_cost_per_loan": review_cost_per_loan
        },
        "baseline": {
            "unverified_loans_count": int(unverified_loans),
            "unverified_share_pct": round(float(baseline_unverified_share), 2),
            "total_portfolio_loans": int(total_loans)
        },
        "simulated": {
            "converted_loans_count": int(loans_to_verify),
            "new_unverified_share_pct": round(float(sim_unverified_share), 2),
            "credit_losses_saved": round(float(credit_losses_saved), 2),
            "capacity_processing_cost": round(float(operational_processing_cost), 2),
            "net_economic_benefit": round(float(net_economic_benefit), 2)
        },
        "recommendation": rec
    }


def run_all_scenarios():
    """Runs all 5 scenario simulations with default calibrated parameters."""
    return [
        simulate_underwriting_tightening(),
        simulate_risk_pricing_adjustment(),
        simulate_funding_policy(),
        simulate_collections_optimization(),
        simulate_verification_policy_shift()
    ]


if __name__ == "__main__":
    print("=" * 75)
    print("  OPS-TWIN: 5 What-If Scenario Simulations on Real Baseline")
    print("=" * 75)
    scenarios = run_all_scenarios()
    for i, sc in enumerate(scenarios, 1):
        print(f"\n[{i}] {sc['scenario_name']}:")
        print(f"    Recommendation: {sc['recommendation']}")
