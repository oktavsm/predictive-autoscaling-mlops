#!/usr/bin/env python3
"""
Export operational time-series metrics from Prometheus into a structured CSV dataset.

Usage:
    python scripts/export_dataset.py --minutes 30 --output src/data/raw/steady_01.csv
"""

import argparse
from datetime import datetime, timedelta, timezone
import os
import sys
import pandas as pd
import requests

PROM_URL = os.getenv("PROM_URL", "http://127.0.0.1:9090")

QUERIES = {
    "request_rate": """
        sum(
          rate(
            caddy_http_requests_total{
              host=~"api.titipin.me.*"
            }[1m]
          )
        )
    """,
    "php_cpu_cores": """
        sum(
          rate(
            container_cpu_usage_seconds_total{
              namespace="titipin",
              pod=~"laravel-backend-.*",
              container="php"
            }[1m]
          )
        )
    """,
    "php_memory_bytes": """
        sum(
          container_memory_working_set_bytes{
            namespace="titipin",
            pod=~"laravel-backend-.*",
            container="php"
          }
        )
    """,
    "replicas": """
        kube_deployment_status_replicas{
          namespace="titipin",
          deployment="laravel-backend"
        }
    """,
    "p95_latency_seconds": """
        histogram_quantile(
          0.95,
          sum by (le) (
            rate(
              caddy_http_request_duration_seconds_bucket{
                host=~"api.titipin.me.*"
              }[1m]
            )
          )
        )
    """,
}


def query_range(promql, start, end, step):
    try:
        response = requests.get(
            f"{PROM_URL}/api/v1/query_range",
            params={
                "query": promql,
                "start": start.timestamp(),
                "end": end.timestamp(),
                "step": step,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        result = data.get("result", [])
        if not result:
            return pd.Series(dtype=float)

        values = result[0]["values"]
        return pd.Series(
            {
                pd.to_datetime(float(ts), unit="s", utc=True): float(val)
                for ts, val in values
            }
        )
    except Exception as e:
        print(f"Warning on query: {e}")
        return pd.Series(dtype=float)


def main():
    parser = argparse.ArgumentParser(description="Export Prometheus metrics to CSV")
    parser.add_argument("--minutes", type=int, default=30, help="Minutes of history to export (default: 30)")
    parser.add_argument("--step", type=int, default=15, help="Step resolution in seconds (default: 15)")
    parser.add_argument("--output", type=str, default="src/data/raw/dataset.csv", help="Destination CSV path")
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=args.minutes)

    print(f"[*] Querying Prometheus at {PROM_URL}")
    print(f"[*] Window: {start.strftime('%Y-%m-%d %H:%M:%S UTC')} -> {end.strftime('%Y-%m-%d %H:%M:%S UTC')} ({args.minutes} min, step={args.step}s)")

    df = pd.DataFrame()
    for name, query in QUERIES.items():
        df[name] = query_range(query, start, end, args.step)

    df.index.name = "timestamp"
    df = df.sort_index()

    if df.empty:
        print("[!] Warning: No data points returned. Ensure Prometheus is accessible and port-forwarded.")
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    df.to_csv(args.output)

    print(f"\n[+] Successfully exported {len(df)} records to: {args.output}")
    print("\n--- Summary Statistics ---")
    print(df.describe().T[["count", "mean", "min", "max"]])
    print("\n--- Recent Records (Tail) ---")
    print(df.tail(10))


if __name__ == "__main__":
    main()
