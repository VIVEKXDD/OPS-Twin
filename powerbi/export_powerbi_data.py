"""
OPS-TWIN: Power BI Star-Schema Data Model Exporter
=================================================
Extracts normalized tables from data/processed/ops_twin.db and generates
clean, star-schema CSV tables optimized for Power BI Desktop 'Get Data':
  1. fact_loans.csv
  2. dim_borrower.csv
  3. dim_date.csv
  4. dim_geography.csv
  5. dim_loan_grade.csv
"""

import sqlite3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = BASE_DIR / "data" / "processed" / "ops_twin.db"
EXPORT_DIR = BASE_DIR / "powerbi" / "export"


US_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia"
}

REGION_MAP = {
    "CA": "West", "OR": "West", "WA": "West", "NV": "West", "AZ": "West", "ID": "West", "MT": "West", "WY": "West", "CO": "West", "UT": "West", "NM": "West", "AK": "West", "HI": "West",
    "NY": "Northeast", "PA": "Northeast", "NJ": "Northeast", "MA": "Northeast", "CT": "Northeast", "RI": "Northeast", "VT": "Northeast", "NH": "Northeast", "ME": "Northeast",
    "IL": "Midwest", "OH": "Midwest", "MI": "Midwest", "IN": "Midwest", "WI": "Midwest", "MN": "Midwest", "MO": "Midwest", "IA": "Midwest", "KS": "Midwest", "NE": "Midwest", "SD": "Midwest", "ND": "Midwest",
    "TX": "South", "FL": "South", "GA": "South", "NC": "South", "VA": "South", "TN": "South", "MD": "South", "SC": "South", "AL": "South", "LA": "South", "KY": "South", "OK": "South", "AR": "South", "MS": "South", "WV": "South", "DE": "South", "DC": "South"
}


def export_powerbi_star_schema():
    print("=" * 75)
    print("  OPS-TWIN: Power BI Star-Schema Data Model Export")
    print("=" * 75)
    
    if not DB_FILE.exists():
        raise FileNotFoundError(f"Database not found at {DB_FILE}")
        
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))

    # 1. Fact Table: fact_loans
    print("[*] Generating fact_loans.csv...")
    query_fact = """
    SELECT
        l.loan_id,
        l.borrower_id,
        l.issue_date,
        l.issue_month,
        l.issue_year,
        l.grade,
        b.addr_state,
        l.loan_amnt,
        l.funded_amnt,
        CAST(SUBSTR(l.term, 1, 3) AS INTEGER) AS term_months,
        l.int_rate,
        l.installment,
        l.purpose,
        l.loan_status,
        l.is_default,
        l.is_delinquent,
        l.is_fully_funded,
        pr.total_pymnt,
        pr.total_rec_prncp,
        pr.total_rec_int,
        pr.recoveries,
        pr.collection_recovery_fee,
        pr.charged_off_principal
    FROM loans l
    JOIN borrowers b ON l.borrower_id = b.borrower_id
    JOIN payments_recoveries pr ON l.loan_id = pr.loan_id
    """
    df_fact = pd.read_sql_query(query_fact, conn)
    fact_path = EXPORT_DIR / "fact_loans.csv"
    df_fact.to_csv(fact_path, index=False)
    print(f"    -> Exported {len(df_fact):,} rows ({fact_path.stat().st_size / 1024 / 1024:.2f} MB)")

    # 2. Dimension Table: dim_borrower
    print("[*] Generating dim_borrower.csv...")
    query_borrower = """
    SELECT
        borrower_id,
        emp_length,
        home_ownership,
        annual_inc,
        LOWER(verification_status) AS verification_status,
        dti,
        fico_range_low,
        revol_util,
        open_acc,
        total_acc
    FROM borrowers
    """
    df_borrower = pd.read_sql_query(query_borrower, conn)
    borrower_path = EXPORT_DIR / "dim_borrower.csv"
    df_borrower.to_csv(borrower_path, index=False)
    print(f"    -> Exported {len(df_borrower):,} rows ({borrower_path.stat().st_size / 1024 / 1024:.2f} MB)")

    # 3. Dimension Table: dim_date
    print("[*] Generating dim_date.csv...")
    unique_dates = df_fact["issue_date"].dropna().unique()
    date_records = []
    for d_str in sorted(unique_dates):
        dt = pd.to_datetime(d_str)
        date_records.append({
            "date": d_str,
            "year": dt.year,
            "quarter": f"Q{dt.quarter}",
            "quarter_year": f"Q{dt.quarter}-{dt.year}",
            "month_name": dt.strftime("%B"),
            "month_year": dt.strftime("%b-%Y"),
            "month_number": dt.month,
            "year_month": dt.strftime("%Y-%m")
        })
    df_date = pd.DataFrame(date_records)
    date_path = EXPORT_DIR / "dim_date.csv"
    df_date.to_csv(date_path, index=False)
    print(f"    -> Exported {len(df_date):,} dates ({date_path.stat().st_size / 1024:.1f} KB)")

    # 4. Dimension Table: dim_geography
    print("[*] Generating dim_geography.csv...")
    states_in_fact = df_fact["addr_state"].dropna().unique()
    geo_records = []
    for st_code in sorted(states_in_fact):
        geo_records.append({
            "addr_state": st_code,
            "state_name": US_STATE_NAMES.get(st_code, st_code),
            "region": REGION_MAP.get(st_code, "Other")
        })
    df_geo = pd.DataFrame(geo_records)
    geo_path = EXPORT_DIR / "dim_geography.csv"
    df_geo.to_csv(geo_path, index=False)
    print(f"    -> Exported {len(df_geo):,} states ({geo_path.stat().st_size / 1024:.1f} KB)")

    # 5. Dimension Table: dim_loan_grade
    print("[*] Generating dim_loan_grade.csv...")
    grades = [
        {"grade": "A", "grade_name": "Grade A - Prime Super", "risk_tier": "Prime", "subprime_flag": 0},
        {"grade": "B", "grade_name": "Grade B - Prime Standard", "risk_tier": "Prime", "subprime_flag": 0},
        {"grade": "C", "grade_name": "Grade C - Near Prime", "risk_tier": "Near-Prime", "subprime_flag": 0},
        {"grade": "D", "grade_name": "Grade D - Core Subprime", "risk_tier": "Subprime", "subprime_flag": 1},
        {"grade": "E", "grade_name": "Grade E - Moderate Subprime", "risk_tier": "Subprime", "subprime_flag": 1},
        {"grade": "F", "grade_name": "Grade F - Speculative Subprime", "risk_tier": "Subprime", "subprime_flag": 1},
        {"grade": "G", "grade_name": "Grade G - Deep Subprime", "risk_tier": "Subprime", "subprime_flag": 1}
    ]
    df_grade = pd.DataFrame(grades)
    grade_path = EXPORT_DIR / "dim_loan_grade.csv"
    df_grade.to_csv(grade_path, index=False)
    print(f"    -> Exported {len(df_grade):,} grade tiers ({grade_path.stat().st_size / 1024:.1f} KB)")

    conn.close()
    print(f"\n[+] Power BI Star-Schema Export completed successfully!")
    print(f"    Directory: {EXPORT_DIR}")


if __name__ == "__main__":
    export_powerbi_star_schema()
