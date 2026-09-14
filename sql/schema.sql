-- ==============================================================================
-- OPS-TWIN: Lending Operations Business Intelligence Database Schema (SQLite)
-- Normalized relational model: Borrowers, Loans, Payments/Recoveries, Monthly Rollup
-- ==============================================================================

PRAGMA foreign_keys = ON;

-- 1. Borrowers Dimension Table
CREATE TABLE IF NOT EXISTS borrowers (
    borrower_id VARCHAR(32) PRIMARY KEY,
    emp_length VARCHAR(20),
    home_ownership VARCHAR(20),
    annual_inc REAL,
    verification_status VARCHAR(30),
    addr_state VARCHAR(5),
    dti REAL,
    fico_range_low REAL,
    fico_range_high REAL,
    open_acc INTEGER,
    revol_bal REAL,
    revol_util REAL,
    total_acc INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Loans Fact Table
CREATE TABLE IF NOT EXISTS loans (
    loan_id VARCHAR(32) PRIMARY KEY,
    borrower_id VARCHAR(32) NOT NULL,
    issue_date DATE,
    issue_month VARCHAR(7) NOT NULL,    -- Format: YYYY-MM
    issue_year INTEGER NOT NULL,
    loan_amnt REAL NOT NULL,
    funded_amnt REAL NOT NULL,
    funded_amnt_inv REAL,
    term VARCHAR(20) NOT NULL,
    int_rate REAL NOT NULL,             -- Annual interest rate (percentage, e.g. 11.5)
    installment REAL NOT NULL,
    grade VARCHAR(2) NOT NULL,          -- A through G
    sub_grade VARCHAR(4) NOT NULL,      -- A1 through G5
    purpose VARCHAR(50),
    loan_status VARCHAR(50) NOT NULL,
    is_default INTEGER DEFAULT 0,       -- 1 if Charged Off or Default, else 0
    is_delinquent INTEGER DEFAULT 0,    -- 1 if Late (16-30), Late (31-120), or Default, else 0
    is_fully_funded INTEGER DEFAULT 0,  -- 1 if funded_amnt >= loan_amnt, else 0
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (borrower_id) REFERENCES borrowers(borrower_id)
);

-- 3. Payments and Collections Recoveries Table
CREATE TABLE IF NOT EXISTS payments_recoveries (
    loan_id VARCHAR(32) PRIMARY KEY,
    total_pymnt REAL DEFAULT 0.0,
    total_rec_prncp REAL DEFAULT 0.0,
    total_rec_int REAL DEFAULT 0.0,
    total_rec_late_fee REAL DEFAULT 0.0,
    recoveries REAL DEFAULT 0.0,
    collection_recovery_fee REAL DEFAULT 0.0,
    last_pymnt_d VARCHAR(10),
    last_pymnt_amnt REAL DEFAULT 0.0,
    charged_off_principal REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id)
);

-- 4. Monthly KPI Rollup Table (Analytical Aggregates with Trend Windows)
CREATE TABLE IF NOT EXISTS monthly_kpi_rollup (
    metric_month VARCHAR(7) PRIMARY KEY, -- YYYY-MM
    total_applications INTEGER NOT NULL,
    total_funded_volume REAL NOT NULL,
    total_requested_volume REAL NOT NULL,
    funding_fulfillment_rate REAL,       -- SUM(funded_amnt) / SUM(loan_amnt) * 100
    avg_interest_rate REAL,              -- AVG(int_rate)
    default_rate REAL,                   -- Default/Charge-off count / total count * 100
    delinquency_rate REAL,               -- 30+ DPD count / total count * 100
    total_recoveries REAL,               -- SUM(recoveries)
    total_charged_off_prncp REAL,        -- SUM(charged_off_principal)
    net_recovery_rate REAL,              -- recoveries / charged-off principal * 100
    collection_cost_ratio REAL,          -- collection fees / recoveries * 100
    unverified_backlog_share REAL,       -- % Not Verified (Operational Capacity Proxy)
    mom_volume_growth_pct REAL,          -- MoM % change in funded volume
    mom_default_rate_delta REAL,         -- MoM bps delta in default rate
    yoy_volume_growth_pct REAL,          -- YoY % change in funded volume
    yoy_default_rate_delta REAL,         -- YoY bps delta in default rate
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for high-performance BI queries
CREATE INDEX IF NOT EXISTS idx_loans_issue_month ON loans(issue_month);
CREATE INDEX IF NOT EXISTS idx_loans_grade ON loans(grade);
CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(loan_status);
CREATE INDEX IF NOT EXISTS idx_borrowers_state ON borrowers(addr_state);
CREATE INDEX IF NOT EXISTS idx_borrowers_verification ON borrowers(verification_status);
