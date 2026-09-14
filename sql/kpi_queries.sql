-- ==============================================================================
-- OPS-TWIN: Core Lending Operations 12 KPIs & Trend Delta Analytics
-- Production-grade SQL using CTEs, JOINs, and Window Functions
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUERY 1: Master Monthly KPI Rollup with Window Functions (MoM and YoY Trends)
-- Computes Core Portfolio, Risk, Collections, and Capacity Metrics by Month
-- ------------------------------------------------------------------------------
WITH MonthlyBase AS (
    SELECT
        l.issue_month,
        COUNT(l.loan_id) AS total_applications,
        SUM(l.loan_amnt) AS total_requested_volume,
        SUM(l.funded_amnt) AS total_funded_volume,
        ROUND(AVG(l.int_rate), 2) AS avg_interest_rate,
        -- KPI 1: Default / Charge-off Rate (%)
        ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS default_rate,
        -- KPI 2: Delinquency Rate 30+ DPD (%)
        ROUND(SUM(l.is_delinquent) * 100.0 / COUNT(l.loan_id), 2) AS delinquency_rate,
        -- KPI 4: Funding Fulfillment Rate (%)
        ROUND(SUM(l.funded_amnt) * 100.0 / NULLIF(SUM(l.loan_amnt), 0), 2) AS funding_fulfillment_rate,
        -- KPI 7: Historical Charge-Off Principal ($)
        ROUND(SUM(pr.charged_off_principal), 2) AS total_charged_off_prncp,
        -- KPI 8: Net Recovery Rate on Charged-Off Loans (%)
        ROUND(
            SUM(pr.recoveries) * 100.0 / NULLIF(SUM(pr.charged_off_principal), 0),
            2
        ) AS net_recovery_rate,
        -- KPI 9: Collection Cost Efficiency Ratio (%)
        ROUND(
            SUM(pr.collection_recovery_fee) * 100.0 / NULLIF(SUM(pr.recoveries), 0),
            2
        ) AS collection_cost_ratio,
        -- KPI 11: Verification Backlog Share (Capacity Proxy %)
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
        -- MoM Funded Volume Growth (%)
        ROUND(
            (total_funded_volume - LAG(total_funded_volume, 1) OVER (ORDER BY issue_month)) * 100.0
            / NULLIF(LAG(total_funded_volume, 1) OVER (ORDER BY issue_month), 0),
            2
        ) AS mom_volume_growth_pct,
        -- MoM Default Rate Delta (percentage points)
        ROUND(
            default_rate - LAG(default_rate, 1) OVER (ORDER BY issue_month),
            2
        ) AS mom_default_rate_delta,
        -- YoY Funded Volume Growth (%)
        ROUND(
            (total_funded_volume - LAG(total_funded_volume, 12) OVER (ORDER BY issue_month)) * 100.0
            / NULLIF(LAG(total_funded_volume, 12) OVER (ORDER BY issue_month), 0),
            2
        ) AS yoy_volume_growth_pct,
        -- YoY Default Rate Delta (percentage points)
        ROUND(
            default_rate - LAG(default_rate, 12) OVER (ORDER BY issue_month),
            2
        ) AS yoy_default_rate_delta,
        -- Rolling 3-Month Moving Average Funded Volume
        ROUND(
            AVG(total_funded_volume) OVER (
                ORDER BY issue_month
                ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
            ),
            2
        ) AS rolling_3m_avg_funded_volume
    FROM MonthlyBase
)
SELECT * FROM MonthlyWithTrends
ORDER BY metric_month ASC;


-- ------------------------------------------------------------------------------
-- QUERY 2: Risk-Adjusted Portfolio Quality by Risk Grade (KPI 3 & KPI 6)
-- Measures APR pricing vs default loss spread across risk tiers A through G
-- ------------------------------------------------------------------------------
SELECT
    l.grade,
    COUNT(l.loan_id) AS total_loans,
    ROUND(SUM(l.funded_amnt), 2) AS total_funded_amount,
    ROUND(AVG(l.int_rate), 2) AS avg_interest_rate,
    ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS default_rate,
    ROUND(SUM(l.is_delinquent) * 100.0 / COUNT(l.loan_id), 2) AS delinquency_rate,
    -- Net Interest Margin Spread Proxy: Average Interest Rate minus Realized Default Loss Rate
    ROUND(AVG(l.int_rate) - (SUM(l.is_default) * 100.0 / COUNT(l.loan_id)), 2) AS risk_adjusted_net_spread,
    ROUND(AVG(b.dti), 2) AS avg_dti,
    ROUND(AVG(b.fico_range_low), 1) AS avg_fico
FROM loans l
JOIN borrowers b ON l.borrower_id = b.borrower_id
GROUP BY l.grade
ORDER BY l.grade ASC;


-- ------------------------------------------------------------------------------
-- QUERY 3: Collections & Recovery Performance (KPI 7, 8, 9)
-- Evaluates recovery amounts and fee leakages on mature charged-off loans
-- ------------------------------------------------------------------------------
SELECT
    l.grade,
    COUNT(CASE WHEN l.is_default = 1 THEN 1 END) AS charged_off_loans,
    ROUND(SUM(pr.charged_off_principal), 2) AS gross_charged_off_principal,
    ROUND(SUM(pr.recoveries), 2) AS total_recoveries,
    ROUND(SUM(pr.collection_recovery_fee), 2) AS total_collection_fees,
    ROUND(
        SUM(pr.recoveries) * 100.0 / NULLIF(SUM(pr.charged_off_principal), 0),
        2
    ) AS recovery_rate_pct,
    ROUND(
        SUM(pr.collection_recovery_fee) * 100.0 / NULLIF(SUM(pr.recoveries), 0),
        2
    ) AS collection_cost_fee_ratio_pct,
    ROUND(
        (SUM(pr.recoveries) - SUM(pr.collection_recovery_fee)),
        2
    ) AS net_recovered_cash
FROM loans l
JOIN payments_recoveries pr ON l.loan_id = pr.loan_id
GROUP BY l.grade
ORDER BY l.grade ASC;


-- ------------------------------------------------------------------------------
-- QUERY 4: Operational Underwriting Throughput & Capacity Proxies (KPI 10, 11, 12)
-- Analyzes loan velocity and verification backlog across state jurisdictions
-- ------------------------------------------------------------------------------
WITH StateVolume AS (
    SELECT
        b.addr_state,
        COUNT(l.loan_id) AS total_loans_processed,
        ROUND(SUM(l.funded_amnt), 2) AS total_funded_volume,
        ROUND(AVG(l.int_rate), 2) AS avg_interest_rate,
        ROUND(SUM(l.is_default) * 100.0 / COUNT(l.loan_id), 2) AS state_default_rate,
        -- Backlog Proxy: % Not Verified
        ROUND(
            SUM(CASE WHEN b.verification_status = 'Not Verified' THEN 1 ELSE 0 END) * 100.0 / COUNT(l.loan_id),
            2
        ) AS unverified_rate_pct,
        -- Funding fulfillment rate
        ROUND(SUM(l.funded_amnt) * 100.0 / NULLIF(SUM(l.loan_amnt), 0), 2) AS funding_fulfillment_rate
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    GROUP BY b.addr_state
)
SELECT
    addr_state,
    total_loans_processed,
    total_funded_volume,
    avg_interest_rate,
    state_default_rate,
    unverified_rate_pct,
    funding_fulfillment_rate,
    -- Rank states by operational throughput volume
    DENSE_RANK() OVER (ORDER BY total_loans_processed DESC) AS volume_rank
FROM StateVolume
ORDER BY total_loans_processed DESC;


-- ------------------------------------------------------------------------------
-- QUERY 5: 2008 Financial Crisis Impact Analysis (Root Cause Stress Period)
-- Isolates default spike and credit quality degradation during 2007-2009 macro shock
-- ------------------------------------------------------------------------------
SELECT
    l.issue_year,
    COUNT(l.loan_id) AS annual_volume,
    ROUND(SUM(l.funded_amnt), 2) AS annual_funded_amount,
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
