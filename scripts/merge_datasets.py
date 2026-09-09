#!/usr/bin/env python3
"""
Merge and deduplicate all CSV datasets in src/data/raw/ into a unified master dataset.
"""

import glob
import os
import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "../src/data/raw")
MASTER_FILE = os.path.join(RAW_DIR, "master_training_dataset.csv")
DEMO_FILE = os.path.join(os.path.dirname(__file__), "../src/data/demo_metrics.csv")


def main():
    csv_files = [
        f for f in sorted(glob.glob(os.path.join(RAW_DIR, "*.csv")))
        if not os.path.basename(f).startswith("master_")
    ]

    if not csv_files:
        print("[!] No CSV files found to merge.")
        return

    print(f"[*] Found {len(csv_files)} datasets to merge:")
    for f in csv_files:
        print(f"    - {os.path.basename(f)}")

    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f, index_col="timestamp", parse_dates=True)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            print(f"[!] Error reading {f}: {e}")

    if not dfs:
        print("[!] No valid dataframes loaded.")
        return

    combined = pd.concat(dfs)
    combined = combined.sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]

    combined.to_csv(MASTER_FILE)
    combined.to_csv(DEMO_FILE)

    print(f"\n[+] Master dataset saved to: {MASTER_FILE}")
    print(f"[+] Demo metrics updated at: {DEMO_FILE}")
    print(f"[+] Total unique records: {len(combined)}")
    print("\n--- Summary Statistics ---")
    print(combined.describe().T[["count", "mean", "min", "max"]])


if __name__ == "__main__":
    main()
