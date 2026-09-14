"""
OPS-TWIN: ETL & Normalization Pipeline
======================================
Loads the authentic raw LendingClub dataset into SQLite (data/processed/ops_twin.db).
Creates and populates normalized relational tables:
  1. borrowers (borrower dimension)
  2. loans (loan fact table)
  3. payments_recoveries (cash flows, recoveries, and collection costs)
  4. monthly_kpi_rollup (baseline monthly operations summary)
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FILE = BASE_DIR / "data" / "raw" / "lending_club_loans.csv"
DB_DIR = BASE_DIR / "data" / "processed"
DB_FILE = DB_DIR / "ops_twin.db"
SCHEMA_FILE = BASE_DIR / "sql" / "schema.sql"


def init_database(db_path, schema_path):
    """Initializes SQLite database using schema.sql."""
    print(f"[*] Initializing database schema at {db_path}...")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    cursor.executescript(schema_sql)
    conn.commit()
    conn.close()
    print("[+] Database schema successfully created.")


def parse_issue_date(val):
    """Parses LendingClub issue_d strings like 'Dec-2011' or 'Oct-2008' into (date_str, month_str, year_int)."""
    if pd.isna(val) or not str(val).strip():
        return None, None, None
    s = str(val).strip()
    try:
        dt = datetime.strptime(s, "%b-%Y")
        return dt.strftime("%Y-%m-01"), dt.strftime("%Y-%m"), dt.year
    except Exception:
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%Y-%m-01"), dt.strftime("%Y-%m"), dt.year
        except Exception:
            return None, None, None


def run_etl():
    print("=" * 70)
    print("  OPS-TWIN: Lending Operations ETL & Relational Loading")
    print("=" * 70)
    
    if not RAW_FILE.exists():
        print(f"[-] Raw dataset not found at {RAW_FILE}. Running data/download_data.py first...")
        from data.download_data import main as download_main
        download_main()
        
    print(f"[*] Reading raw loan dataset from {RAW_FILE}...")
    df = pd.read_csv(RAW_FILE, low_memory=False)
    print(f"    Raw records loaded: {len(df):,}")

    # Standardize & Clean Column Values
    print("[*] Cleaning and normalizing fields...")
    
    # 1. Clean Dates
    date_tuples = [parse_issue_date(x) for x in df["issue_d"]]
    df["issue_date"] = [t[0] for t in date_tuples]
    df["issue_month"] = [t[1] for t in date_tuples]
    df["issue_year"] = [t[2] for t in date_tuples]
    
    # Drop rows without valid issue_month
    valid_mask = df["issue_month"].notna()
    df = df[valid_mask].copy()
    print(f"    Valid date records: {len(df):,}")

    # 2. Clean Numerics
    numeric_cols = [
        "loan_amnt", "funded_amnt", "funded_amnt_inv", "int_rate", "installment",
        "annual_inc", "dti", "open_acc", "revol_bal", "revol_util", "total_acc",
        "total_pymnt", "total_rec_prncp", "total_rec_int", "total_rec_late_fee",
        "recoveries", "collection_recovery_fee", "last_pymnt_amnt"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace("$", "", regex=False).str.replace("%", "", regex=False).str.replace(",", "", regex=False).str.strip(), errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    # If funded_amnt is 0 or missing, fill from loan_amnt
    df["funded_amnt"] = np.where(df["funded_amnt"] > 0, df["funded_amnt"], df["loan_amnt"])
    df["funded_amnt_inv"] = np.where(df["funded_amnt_inv"] > 0, df["funded_amnt_inv"], df["funded_amnt"])

    # FICO Score Handling (FICO Range Low / High or synthetic grade proxy if missing in raw)
    if "fico_range_low" not in df.columns or df["fico_range_low"].isna().all():
        grade_fico_map = {"A": 740, "B": 700, "C": 670, "D": 640, "E": 610, "F": 580, "G": 550}
        df["fico_range_low"] = df["grade"].map(grade_fico_map).fillna(660)
        df["fico_range_high"] = df["fico_range_low"] + 4
    else:
        df["fico_range_low"] = pd.to_numeric(df["fico_range_low"], errors="coerce")
        grade_fico_map = {"A": 740, "B": 700, "C": 670, "D": 640, "E": 610, "F": 580, "G": 550}
        df["fico_range_low"] = df["fico_range_low"].fillna(df["grade"].map(grade_fico_map)).fillna(660)
        df["fico_range_high"] = df["fico_range_low"] + 4

    # 3. Identifiers & Foreign Keys
    df["loan_id"] = df["id"].astype(str)
    # Handle missing or empty loan IDs
    df["loan_id"] = np.where(df["loan_id"].str.strip().isin(["", "nan", "None", "0"]), [f"LN_{i+1:07d}" for i in range(len(df))], df["loan_id"])
    df["borrower_id"] = [f"BRW_{i+1:07d}" for i in range(len(df))]

    # 4. Status and KPI Flags
    # Default = 'Charged Off' or 'Default' or 'Does not meet the credit policy. Status:Charged Off'
    df["loan_status_clean"] = df["loan_status"].fillna("Unknown").astype(str).str.strip()
    df["is_default"] = df["loan_status_clean"].apply(
        lambda s: 1 if any(k in s.lower() for k in ["charged off", "default"]) else 0
    )
    df["is_delinquent"] = df["loan_status_clean"].apply(
        lambda s: 1 if any(k in s.lower() for k in ["late", "grace", "default"]) else 0
    )
    df["is_fully_funded"] = (df["funded_amnt"] >= df["loan_amnt"]).astype(int)

    # 5. Charged-Off Principal
    # For defaulted loans, loss principal = funded_amnt - total_rec_prncp
    df["charged_off_principal"] = np.where(
        df["is_default"] == 1,
        np.maximum(0.0, df["funded_amnt"] - df["total_rec_prncp"]),
        0.0
    )

    # Clean categorical text
    df["grade"] = df["grade"].fillna("C").astype(str).str.strip().str.upper()
    df["sub_grade"] = df["sub_grade"].fillna(df["grade"] + "1").astype(str).str.strip().str.upper()
    df["term"] = df["term"].fillna("36 months").astype(str).str.strip()
    df["home_ownership"] = df["home_ownership"].fillna("MORTGAGE").astype(str).str.strip().str.upper()
    df["verification_status"] = df["verification_status"].fillna("Not Verified").astype(str).str.strip()
    df["verification_status"] = df["verification_status"].replace({
        "VERIFIED - income": "Verified",
        "Source Verified": "Source Verified",
        "Verified": "Verified",
        "Not Verified": "Not Verified"
    })
    df["purpose"] = df["purpose"].fillna("debt_consolidation").astype(str).str.strip().str.lower()
    df["addr_state"] = df["addr_state"].fillna("CA").astype(str).str.strip().str.upper()
    df["emp_length"] = df["emp_length"].fillna("n/a").astype(str).str.strip()

    # Create Database & Insert
    init_database(DB_FILE, SCHEMA_FILE)
    conn = sqlite3.connect(str(DB_FILE))
    
    print("[*] Populating Borrowers dimension table...")
    borrowers_df = df[[
        "borrower_id", "emp_length", "home_ownership", "annual_inc",
        "verification_status", "addr_state", "dti", "fico_range_low",
        "fico_range_high", "open_acc", "revol_bal", "revol_util", "total_acc"
    ]].drop_duplicates(subset=["borrower_id"])
    borrowers_df.to_sql("borrowers", conn, if_exists="append", index=False)
    print(f"    -> Inserted {len(borrowers_df):,} borrowers.")

    print("[*] Populating Loans fact table...")
    loans_df = df[[
        "loan_id", "borrower_id", "issue_date", "issue_month", "issue_year",
        "loan_amnt", "funded_amnt", "funded_amnt_inv", "term", "int_rate",
        "installment", "grade", "sub_grade", "purpose", "loan_status_clean",
        "is_default", "is_delinquent", "is_fully_funded"
    ]].rename(columns={"loan_status_clean": "loan_status"})
    loans_df.to_sql("loans", conn, if_exists="append", index=False)
    print(f"    -> Inserted {len(loans_df):,} loans.")

    print("[*] Populating Payments and Recoveries table...")
    payments_df = df[[
        "loan_id", "total_pymnt", "total_rec_prncp", "total_rec_int",
        "total_rec_late_fee", "recoveries", "collection_recovery_fee",
        "last_pymnt_d", "last_pymnt_amnt", "charged_off_principal"
    ]]
    payments_df.to_sql("payments_recoveries", conn, if_exists="append", index=False)
    print(f"    -> Inserted {len(payments_df):,} payment/recovery records.")

    conn.commit()
    conn.close()
    
    print(f"\n[+] ETL pipeline finished successfully!")
    print(f"    SQLite Database: {DB_FILE} ({DB_FILE.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    run_etl()
