"""
OPS-TWIN Data Acquisition Script
=================================
Fetches authentic LendingClub Loan Datasets covering the 2007-2015 credit cycle.
Downloads real loan-level data from the canonical LendingClub public archives:
  - LoanStats3a (2007–2011): Covers early platform operations & the 2008 Financial Crisis
  - LoanStats3d (2015): Covers scaled modern portfolio & underwriting operations
Combined, this produces a multi-year portfolio (~85,000+ real loans)
with authentic credit risk, funding fulfillment, collections, and capacity dynamics.

Constraint: Strictly uses REAL lending data — no synthetic generation.
"""

import os
import sys
import csv
import urllib.request
import re
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
COMBINED_RAW_FILE = RAW_DIR / "lending_club_loans.csv"

# Canonical public LendingClub archive sources (H2O test data S3 mirror)
URL_2007_2011 = "https://s3.amazonaws.com/h2o-public-test-data/bigdata/laptop/lending-club/LoanStats3a.csv"
URL_2015 = "https://s3.amazonaws.com/h2o-public-test-data/bigdata/laptop/lending-club/LoanStats3d.csv"

# Target normalized columns across datasets
TARGET_COLUMNS = [
    "id", "loan_amnt", "funded_amnt", "funded_amnt_inv", "term", "int_rate",
    "installment", "grade", "sub_grade", "emp_length", "home_ownership",
    "annual_inc", "verification_status", "issue_d", "loan_status", "purpose",
    "addr_state", "dti", "open_acc", "revol_bal", "revol_util", "total_acc",
    "total_pymnt", "total_rec_prncp", "total_rec_int", "total_rec_late_fee",
    "recoveries", "collection_recovery_fee", "last_pymnt_d", "last_pymnt_amnt"
]


def check_existing_data():
    """Checks if valid LendingClub data is already present locally."""
    if COMBINED_RAW_FILE.exists() and COMBINED_RAW_FILE.stat().st_size > 20 * 1024 * 1024:
        print(f"[*] Valid authentic dataset already present: {COMBINED_RAW_FILE} ({COMBINED_RAW_FILE.stat().st_size / 1024 / 1024:.2f} MB)")
        return True
    return False


def download_file_with_progress(url, dest_path, description=""):
    """Downloads a file over HTTP with console progress reporting."""
    print(f"[*] Downloading {description} from:\n    {url}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    
    req = urllib.request.Request(url, headers={"User-Agent": "OPS-Twin-BI/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out_f:
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        block_size = 1024 * 512
        while True:
            chunk = resp.read(block_size)
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            if total_size > 0:
                percent = downloaded * 100 / total_size
                print(f"\r    -> {downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB ({percent:.1f}%)", end="", flush=True)
            else:
                print(f"\r    -> {downloaded / 1024 / 1024:.1f} MB downloaded", end="", flush=True)
        print()
    print(f"[+] Finished downloading {dest_path.name} ({dest_path.stat().st_size / 1024 / 1024:.2f} MB)")


def merge_and_clean_datasets(files_to_merge, out_file):
    """Parses, unifies headers, and merges the datasets into a clean raw CSV."""
    print(f"[*] Processing and unifying datasets into {out_file.name}...")
    total_written = 0
    years_seen = set()
    
    with open(out_file, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=TARGET_COLUMNS)
        writer.writeheader()
        
        for file_path in files_to_merge:
            print(f"    Processing {file_path.name}...")
            with open(file_path, "r", encoding="utf-8", errors="ignore") as in_f:
                # Some LendingClub files have 1 or 2 preamble header lines
                first_line = in_f.readline()
                if "id" not in first_line.lower() and "loan_amnt" not in first_line.lower():
                    # Read second line as header
                    header_line = in_f.readline()
                else:
                    header_line = first_line
                
                # Parse header
                header_cols = [c.strip(' \n\r\"') for c in next(csv.reader([header_line]))]
                header_map = {c.lower(): idx for idx, c in enumerate(header_cols)}
                
                reader = csv.reader(in_f)
                file_count = 0
                for row in reader:
                    if not row or len(row) < 5:
                        continue
                    
                    row_dict = {}
                    for col in TARGET_COLUMNS:
                        col_idx = header_map.get(col.lower())
                        if col_idx is not None and col_idx < len(row):
                            row_dict[col] = row[col_idx].strip(' \n\r\"')
                        else:
                            row_dict[col] = ""
                    
                    # Validate critical fields: loan_amnt, int_rate, and issue_d
                    loan_amnt_raw = row_dict["loan_amnt"].replace("$", "").replace(",", "")
                    int_rate_raw = row_dict["int_rate"].replace("%", "").strip()
                    issue_d = row_dict["issue_d"]
                    
                    try:
                        float(loan_amnt_raw)
                        float(int_rate_raw)
                    except ValueError:
                        continue
                        
                    if not issue_d or not re.match(r"[A-Za-z]{3}-\d{4}", issue_d):
                        continue
                    
                    # Store cleaned values
                    row_dict["loan_amnt"] = loan_amnt_raw
                    row_dict["int_rate"] = int_rate_raw
                    if row_dict["funded_amnt"]:
                        row_dict["funded_amnt"] = row_dict["funded_amnt"].replace("$", "").replace(",", "")
                    if row_dict["dti"]:
                        row_dict["dti"] = row_dict["dti"].replace("%", "").strip()
                    if row_dict["revol_util"]:
                        row_dict["revol_util"] = row_dict["revol_util"].replace("%", "").strip()
                        
                    writer.writerow(row_dict)
                    total_written += 1
                    file_count += 1
                    yr = issue_d.split("-")[-1]
                    years_seen.add(yr)
                    
            print(f"    -> Extracted {file_count:,} valid loan records from {file_path.name}")
            
    print(f"\n[+] Unified dataset generated successfully!")
    print(f"    Total authentic loans: {total_written:,}")
    print(f"    Years spanned: {sorted(list(years_seen))}")
    print(f"    Output path: {out_file} ({out_file.stat().st_size / 1024 / 1024:.2f} MB)")


def main():
    print("=" * 70)
    print("  OPS-TWIN: Lending Operations Data Acquisition Pipeline")
    print("=" * 70)
    
    if check_existing_data():
        print("[+] Authentic dataset already present locally. Ready for ETL.")
        return
        
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    f_2007_2011 = RAW_DIR / "LoanStats3a_2007_2011.csv"
    f_2015 = RAW_DIR / "LoanStats3d_2015.csv"
    
    # 1. Download 2007-2011 (crisis window)
    if not f_2007_2011.exists() or f_2007_2011.stat().st_size < 1024 * 1024:
        download_file_with_progress(URL_2007_2011, f_2007_2011, "LendingClub 2007-2011 (Crisis Window)")
    else:
        print(f"[*] Found cached {f_2007_2011.name}")

    # 2. Download 2015 (modern expansion)
    if not f_2015.exists() or f_2015.stat().st_size < 1024 * 1024:
        download_file_with_progress(URL_2015, f_2015, "LendingClub 2015 (Modern Scale)")
    else:
        print(f"[*] Found cached {f_2015.name}")

    # 3. Merge and clean
    merge_and_clean_datasets([f_2007_2011, f_2015], COMBINED_RAW_FILE)


if __name__ == "__main__":
    main()
