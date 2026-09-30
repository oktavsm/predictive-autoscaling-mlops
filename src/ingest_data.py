#!/usr/bin/env python3
"""
Automated Data Ingestion — Predictive Autoscaling MLOps
========================================================
Mengambil metrik operasional dari Prometheus HTTP API dan menyimpannya
ke folder data/raw/ dengan nama file berbasis timestamp (non-destructive).

Sumber data: Prometheus query_range API
  - request_rate (req/s) via Caddy metrics
  - php_cpu_cores (CPU cores) via container_cpu_usage_seconds_total
  - php_memory_bytes via container_memory_working_set_bytes
  - replicas (jumlah pod aktif) via kube_deployment_status_replicas
  - p95_latency_seconds (P95 latency) via caddy_http_request_duration_seconds_bucket

Usage:
    python src/ingest_data.py --minutes 30
    python src/ingest_data.py --start 2026-09-27T10:00:00Z --end 2026-09-27T10:30:00Z
    PROM_URL=http://localhost:9090 python src/ingest_data.py --minutes 15
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROM_URL = os.getenv("PROM_URL", "http://127.0.0.1:9090")
DEFAULT_STEP = 15  # resolusi data: 15 detik (sesuai interval HPA)
MAX_RETRIES = 3  # maksimum retry per query sebelum menyerah
RETRY_BACKOFF = 2.0  # faktor backoff eksponensial (detik)
REQUEST_TIMEOUT = 30  # timeout HTTP per request (detik)

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "raw",
)

# ---------------------------------------------------------------------------
# PromQL Queries
# (sama dengan scripts/export_dataset.py, dipertahankan sebagai modul mandiri)
# ---------------------------------------------------------------------------
QUERIES: dict[str, str] = {
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------
def query_range(
    metric_name: str,
    promql: str,
    start: datetime,
    end: datetime,
    step: int,
) -> pd.Series:
    """
    Eksekusi satu PromQL query_range terhadap Prometheus dengan retry eksponensial.

    Parameters
    ----------
    metric_name : str
        Nama metrik untuk keperluan logging.
    promql : str
        PromQL expression yang akan dieksekusi.
    start : datetime
        Awal window pengambilan data (timezone-aware UTC).
    end : datetime
        Akhir window pengambilan data (timezone-aware UTC).
    step : int
        Resolusi dalam detik.

    Returns
    -------
    pd.Series
        Series dengan index datetime UTC dan value float. Kosong jika gagal.
    """
    url = f"{PROM_URL}/api/v1/query_range"
    params = {
        "query": promql,
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": step,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            data = resp.json().get("data", {})
            result = data.get("result", [])

            if not result:
                log.warning("[%s] Query returned empty result", metric_name)
                return pd.Series(dtype=float)

            values = result[0]["values"]
            series = pd.Series(
                {pd.to_datetime(float(ts), unit="s", utc=True): float(val) for ts, val in values}
            )
            log.info("[%s] Fetched %d data points", metric_name, len(series))
            return series

        except requests.exceptions.ConnectionError:
            log.error(
                "[%s] Attempt %d/%d — Cannot connect to Prometheus at %s",
                metric_name,
                attempt,
                MAX_RETRIES,
                PROM_URL,
            )
        except requests.exceptions.Timeout:
            log.error(
                "[%s] Attempt %d/%d — Request timed out after %ds",
                metric_name,
                attempt,
                MAX_RETRIES,
                REQUEST_TIMEOUT,
            )
        except requests.exceptions.HTTPError as e:
            log.error("[%s] HTTP error: %s", metric_name, e)
        except Exception as e:  # noqa: BLE001
            log.error("[%s] Unexpected error: %s", metric_name, e)

        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF**attempt
            log.info("[%s] Retrying in %.1fs...", metric_name, wait)
            time.sleep(wait)

    log.error("[%s] All %d attempts failed. Skipping.", metric_name, MAX_RETRIES)
    return pd.Series(dtype=float)


def check_prometheus_health() -> bool:
    """Cek apakah Prometheus dapat dijangkau sebelum memulai ingestion."""
    try:
        resp = requests.get(f"{PROM_URL}/-/healthy", timeout=5)
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def ingest(start: datetime, end: datetime, step: int, output_path: str) -> int:
    """
    Orkestrasi utama: jalankan semua query, gabungkan, simpan ke CSV.

    Returns
    -------
    int
        Jumlah baris yang berhasil diekstrak. 0 jika gagal.
    """
    log.info("Prometheus URL : %s", PROM_URL)
    log.info(
        "Window         : %s → %s",
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    log.info("Step           : %ds | Output: %s", step, output_path)

    # Health check
    if not check_prometheus_health():
        log.error(
            "Prometheus tidak dapat dijangkau di %s. "
            "Jalankan port-forward terlebih dahulu:\n"
            "  kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090",
            PROM_URL,
        )
        return 0

    # Eksekusi semua query
    frames: dict[str, pd.Series] = {}
    for name, promql in QUERIES.items():
        frames[name] = query_range(name, promql, start, end, step)

    df = pd.DataFrame(frames)
    df.index.name = "timestamp"
    df = df.sort_index()

    if df.empty:
        log.error(
            "Tidak ada data yang dikembalikan. Pastikan Prometheus memiliki data untuk window ini."
        )
        return 0

    # Simpan ke CSV
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    df.to_csv(output_path)

    log.info("Berhasil menyimpan %d records ke: %s", len(df), output_path)
    log.info("\n%s", df.describe().T[["count", "mean", "min", "max"]].to_string())
    return len(df)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    """Parse argumen CLI."""
    parser = argparse.ArgumentParser(
        description="Ingest metrik operasional dari Prometheus ke data/raw/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/ingest_data.py --minutes 30
  python src/ingest_data.py --start 2026-09-27T10:00:00Z --end 2026-09-27T10:30:00Z
  PROM_URL=http://localhost:9090 python src/ingest_data.py --minutes 60 --step 30
        """,
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=None,
        help="Jumlah menit historis yang akan diambil (default: 30)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Awal window dalam format ISO 8601 UTC, misal: 2026-09-27T10:00:00Z",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="Akhir window dalam format ISO 8601 UTC (default: sekarang)",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=DEFAULT_STEP,
        help=f"Resolusi data dalam detik (default: {DEFAULT_STEP})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path output CSV. Jika tidak diisi, otomatis menggunakan timestamp.",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point utama."""
    args = parse_args()

    # Tentukan window waktu
    now = datetime.now(timezone.utc)

    if args.start:
        start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
    elif args.minutes:
        start = now - timedelta(minutes=args.minutes)
    else:
        start = now - timedelta(minutes=30)  # default 30 menit

    end = datetime.fromisoformat(args.end.replace("Z", "+00:00")) if args.end else now

    if start >= end:
        log.error("Waktu start (%s) harus lebih awal dari end (%s)", start, end)
        return 1

    # Tentukan output path — non-destructive dengan timestamp
    if args.output:
        output_path = args.output
    else:
        ts_str = now.strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(OUTPUT_DIR, f"metrics_{ts_str}.csv")

    # Jalankan ingestion
    n_records = ingest(start, end, args.step, output_path)
    return 0 if n_records > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
