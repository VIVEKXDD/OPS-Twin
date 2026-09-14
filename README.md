# OPS-TWIN — Business Intelligence & Operations Decision Support Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![SQL](https://img.shields.io/badge/SQL-SQLite%20CTEs%20%26%20Window%20Functions-003B57.svg)](https://www.sqlite.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.55.0-FF4B4B.svg)](https://streamlit.io/)
[![Power BI](https://img.shields.io/badge/Power%20BI-Star--Schema%20%26%20DAX-F2C811.svg)](https://powerbi.microsoft.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)



## 📌 Executive Overview

**OPS-TWIN** is an end-to-end Business Intelligence and Operations Decision Support platform engineered for a credit/lending operations function inside a financial institution (commercial bank, NBFC, or fintech balance-sheet lender). 

Unlike fraud monitoring or payment anomaly systems, **OPS-TWIN focuses entirely on loan book performance, credit cycle dynamics, and internal operational trade-offs**:
1. **12 Core Lending Operations KPIs**: Analyzes the end-to-end credit lifecycle across **Credit Risk**, **Funding & Portfolio**, **Collections & Recovery**, and **Operational Capacity** (proxies).
2. **Production SQL Analytics Engine**: Normalized relational schema in SQLite with production CTEs, JOINs, and Window Functions (`LAG()`, moving averages, MoM/YoY deltas).
3. **Automated Root-Cause Diagnostic**: Statistical anomaly detection that independently surfaces the authentic **2008 Global Financial Crisis** default spike and ranks candidate drivers using Random Forest Gini importance and correlation.
4. **Dual Predictive Analytics**:
   - Macro time-series forecasting (4 quarters / 12 months) for portfolio funded volume and default rates with 95% confidence bands.
   - Micro loan-level default risk classifier (Gradient Boosting, **ROC-AUC: 0.703**) with interactive decision support.
5. **5 Parameterized What-If Scenario Simulations**: Layered on authentic historical baselines with real-time recalculation of downstream trade-offs and auto-generated plain-language recommendations.
6. **Interactive Streamlit Cockpit**: High-aesthetic, glassmorphic executive control center with sparklines, drilldowns, and interactive sliders.
7. **Power BI Star-Schema Handoff**: Turnkey export containing fact/dimension CSVs and a complete guide with 12 DAX measures for rapid dashboard assembly.

---

## 📊 The 12 Core Lending Operations KPIs

| # | Operational Category | Metric Name | Mathematical / SQL Definition | Authentic Data Mapping |
| :-: | :--- | :--- | :--- | :--- |
| **1** | **Credit Risk** | **Default / Charge-Off Rate** | `SUM(is_default) / COUNT(*) * 100` | `% of loans Charged Off or in Default` |
| **2** | **Credit Risk** | **Delinquency Rate (30+ DPD)** | `SUM(is_delinquent) / COUNT(*) * 100` | `% of loans Late (31-120 days) or Late (16-30 days)` |
| **3** | **Credit Risk** | **Risk-Adjusted Portfolio Quality** | `AVG(int_rate) - Default Rate by Grade` | `Net interest spread over realized default losses` |
| **4** | **Funding & Portfolio** | **Funding Fulfillment Rate** | `SUM(funded_amnt) / SUM(loan_amnt) * 100` | `Ratio of investor funded amount to requested principal` |
| **5** | **Funding & Portfolio** | **Monthly Funded Volume & Velocity** | `SUM(funded_amnt)` with `LAG()` MoM/YoY deltas | `Monthly capital deployment and origination velocity` |
| **6** | **Funding & Portfolio** | **Average Interest Rate by Grade** | `AVG(int_rate) GROUP BY grade` | `Risk-based coupon pricing tiers (Grades A through G)` |
| **7** | **Collections & Recovery** | **Gross Charged-Off Principal** | `SUM(funded_amnt - total_rec_prncp)` | `Unrecovered principal balance on charged-off loans` |
| **8** | **Collections & Recovery** | **Net Recovery Rate** | `SUM(recoveries) / SUM(charged_off_prncp) * 100` | `Percentage of charged-off balance recovered` |
| **9** | **Collections & Recovery** | **Collection Cost Efficiency Ratio** | `SUM(collection_fee) / SUM(recoveries) * 100` | `Third-party recovery fees as % of gross recoveries` |
| **10** | **Capacity (Proxy)** | **Regional Processing Throughput** | `COUNT(loan_id) by addr_state per month` | `Underwriting throughput run-rate across jurisdictions` |
| **11** | **Capacity (Proxy)** | **Verification Backlog Share** | `% of applications with Not Verified status` | `Operational review queue and verification backlog proxy` |
| **12** | **Capacity (Proxy)** | **Volume vs. Issuance Velocity** | `MoM volume growth % vs fulfillment spread` | `Underwriting capacity friction under volume surges` |

> [!NOTE]
> **Operational Capacity Proxy Disclosure**: LendingClub's public dataset contains no internal loan officer headcount or hourly timecard tables. As is standard in credit operations modeling, capacity metrics are constructed as documented operational proxies (state-level monthly throughput, unverified queue share, and fulfillment latency).

---

## 🔍 Key Findings from the Real LendingClub Dataset

The platform was executed on **126,812 authentic LendingClub loans** spanning the 2007–2015 credit cycle. The empirical results demonstrate:

### 1. Independent Discovery of the 2008 Financial Crisis Spike
The root-cause analysis engine independently surfaced a severe macro stress event during 2007–2009:
- **Crisis Period Default Rate (2007–2009)**: **`16.64%`** (peaked at **`26.20%`** in 2007 and **`20.73%`** in 2008).
- **Post-Crisis Baseline Default Rate (2010–2015)**: **`4.10%`**.
- **Credit Loss Multiplier**: **`4.1x macro shock spike`** during the crisis window.
- **Collections Impact**: Recovery rate collapsed from **`9.70%`** in 2007 to **`6.63%`** in 2008 as secondary recovery markets dried up.

### 2. Ranked Root-Cause Drivers of Default Risk
Using a Random Forest Gini feature-importance model combined with Pearson/Spearman correlation against 10 borrower and loan candidate attributes:
1. **Loan Interest Rate (APR %)**: **`22.74%`** importance (`+0.192` corr) — Compounding debt burden accelerates default velocity.
2. **Annual Household Income ($)**: **`15.05%`** importance (`-0.052` corr) — Lower income tiers lack liquidity reserves during economic contractions.
3. **Revolving Credit Utilization (%)**: **`12.01%`** importance (`+0.101` corr) — High card utilization signals severe credit dependence.
4. **Debt-to-Income Ratio (DTI %)**: **`11.79%`** importance (`+0.023` corr) — High fixed monthly obligations limit cashflow elasticity.
5. **Borrower Credit Score (FICO)**: **`10.35%`** importance (`-0.193` corr) — Strong historical predictor of repayment delinquency.

### 3. Predictive Machine Learning Performance
- **Loan-Level Default Classifier**: Gradient Boosting trained on 40,000 real loans achieved **`0.703 ROC-AUC`** and **`0.287 PR-AUC`** on a stratified 20% holdout test set.
- **Macro 4-Quarter Forecast**: Holt-Winters Exponential Smoothing projected funded volume stabilizing above **`$450M/quarter`** with an expected default rate stabilizing under **`4.5%`**.

---

## 🎛️ The 5 What-If Scenario Simulations

All simulations execute dynamically on the real portfolio baseline with empirical recalculation:

```
                                WHAT-IF DECISION ENGINE
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │ 1. Underwriting Tightening      Min FICO >= 680, DTI <= 35%                     │
  │    -> Saves $126.2M in credit losses at a 29.7% origination volume sacrifice.   │
  ├─────────────────────────────────────────────────────────────────────────────────┤
  │ 2. Risk-Based APR Repricing     +150 bps APR on Subprime Grades (C-G)           │
  │    -> Generates +$3.18M in gross interest; nets +$2.66M after adverse selection.│
  ├─────────────────────────────────────────────────────────────────────────────────┤
  │ 3. Funding Fulfillment Policy   95% Minimum Commitment Threshold                │
  │    -> Qualifies 98.5% of pipeline; drops 1,935 partial/unfunded loans ($24.5M). │
  ├─────────────────────────────────────────────────────────────────────────────────┤
  │ 4. Collections Effectiveness    +25% Recovery Uplift & 16% Fee Commission Cap   │
  │    -> Recovers +$778K in gross delinquent debt; yields +$541K in net cash.      │
  ├─────────────────────────────────────────────────────────────────────────────────┤
  │ 5. Verification Queue Shift     Convert 30% of Unverified Applicants            │
  │    -> Saves $690K in credit losses against $438K review cost (+ $252K Net ROI). │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📸 Dashboard Visual Tour

### 1. Executive Portfolio Cockpit
*All 12 core lending-operations KPIs with directional delta badges, dual-axis historical trend chart, and risk-adjusted quality spread by Grade:*
![Executive Overview Cockpit](docs/screenshots/01_executive_overview.png)

### 2. Root-Cause Analysis & 2008 Financial Crisis Drilldown
*Historical macro crisis identification banner, crisis progression chart, and ranked driver feature-importance table:*
![Root-Cause Analysis](docs/screenshots/02_root_cause_crisis.png)

### 3. Predictive Analytics & Loan Underwriter
*4-Quarter portfolio forecasting with 95% confidence bands and interactive loan underwriting decision calculator:*
![Predictive Underwriting](docs/screenshots/03_predictive_underwriting.png)

### 4. Interactive What-If Decision Simulator
*Parameterized simulation tabs with sliders, before/after KPI comparison cards, and automated operational recommendations:*
![What-If Decision Simulator](docs/screenshots/04_what_if_simulator.png)

---

## 🏗️ Repository Architecture

```
OPS-Twin/
├── data/
│   ├── download_data.py          # Real LendingClub data ingestion (2007-2015 crisis cycle)
│   ├── process_data.py           # ETL pipeline normalizing raw data into SQLite
│   ├── raw/                      # Raw authentic dataset (gitignored)
│   └── processed/
│       ├── ops_twin.db           # Normalized SQLite database (126,812 loans, gitignored)
│       └── default_classifier.joblib  # Trained Gradient Boosting risk model
├── sql/
│   ├── schema.sql                # Normalized schema (borrowers, loans, payments, rollups)
│   ├── kpi_queries.sql           # Pure SQL CTEs & Window Functions computing all 12 KPIs
│   └── execute_kpis.py           # Verification script executing SQL against SQLite
├── analysis/
│   ├── trends.py                 # Rolling averages, MoM/YoY deltas, degraded KPI alerts
│   ├── root_cause.py             # 2008 crisis detection & Random Forest driver ranking
│   ├── predictive.py             # 4-quarter ARIMA/ETS forecasts & default risk classifier
│   └── what_if.py                # 5 interactive scenario simulation engines & recommendations
├── dashboard/
│   ├── app.py                    # Master 5-page interactive Streamlit BI cockpit
│   ├── components.py             # Reusable KPI cards, Plotly dark theme, sparklines
│   └── styles.css                # Polished glassmorphic fintech CSS styling
├── powerbi/
│   ├── export/                   # Star-schema CSV exports (fact & dimensions)
│   ├── export_powerbi_data.py    # Exporter script creating Kimball star-schema CSVs
│   └── README.md                 # Star schema diagram, 12 DAX measures & assembly guide
├── docs/
│   └── screenshots/              # High-resolution screenshots of verified dashboard
├── tests/
│   └── test_pipeline.py          # Automated end-to-end integration & unit test suite
├── .gitignore
├── requirements.txt
└── README.md
```

---

## ⚡ Quickstart Guide

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Git

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/VIVEKXDD/OPS-Twin.git
cd OPS-Twin
pip install -r requirements.txt
```

### 2. Download Real Data & Build SQLite Database
The dataset is downloaded directly from canonical public LendingClub archives (~72 MB compressed):
```bash
# 1. Download authentic 2007-2011 (crisis) and 2015 (expansion) loans
python data/download_data.py

# 2. Run ETL pipeline to create normalized SQLite relational database
python data/process_data.py

# 3. Execute pure SQL KPI queries and populate monthly rollups
python sql/execute_kpis.py
```

### 3. Run Automated Test Suite
```bash
python -m unittest tests/test_pipeline.py
```
*Expected output: `Ran 6 tests in ~2.4s — OK`.*

### 4. Launch the Interactive Dashboard
```bash
streamlit run dashboard/app.py
```
Open your browser at `http://localhost:8501` to access the full decision support cockpit.

---

## 💼 Power BI Handoff

Since Power BI Desktop requires a local client, the data model and measures are pre-packaged for zero-friction report creation in under 45 minutes:
1. Run `python powerbi/export_powerbi_data.py` to generate the 5 star-schema CSVs in `powerbi/export/`.
2. Review [`powerbi/README.md`](powerbi/README.md) for:
   - Kimball Star-Schema relationship diagram.
   - Exact DAX code for all 12 KPIs (with time intelligence `MoM %` and `YoY %`).
   - Step-by-step 3-page visual report layout guide.

---

## 📜 Acceptance Criteria Checklist

- [x] **Real Data Source**: Strictly uses authentic LendingClub loan data (126,812 loans across 2007–2015); zero synthetic data.
- [x] **12 Core KPIs**: Computed directly in SQL covering Credit Risk, Funding, Collections, and Capacity.
- [x] **Production SQL Layer**: Normalized SQLite tables with CTEs, JOINs, and window functions (`LAG()`, rolling windows).
- [x] **2008 Crisis Root-Cause Detection**: Independently surfaced a genuine 4.1x default rate spike (16.64% crisis vs 4.10% baseline) with ranked driver attributions.
- [x] **Dual Predictive Analytics**: Macro 4-quarter ARIMA/ETS time-series forecasts + micro loan default classifier (ROC-AUC: 0.703).
- [x] **5 What-If Scenarios**: Fully parameterized simulations recalculating downstream trade-offs with actionable executive recommendations.
- [x] **Interactive Dashboard**: Modern, glassmorphic Streamlit application with sparklines, dynamic filters, and underwriter calculator.
- [x] **Power BI Package**: Star-schema CSV exports + complete DAX formulas and report design guide.
- [x] **Documented Proxies**: Capacity metrics clearly disclosed and explained as operational proxies.
- [x] **Automated Tests**: Comprehensive test suite verifying all modules (`Ran 6 tests — OK`).

---

## 📄 License
This project is open-source under the [MIT License](LICENSE).
