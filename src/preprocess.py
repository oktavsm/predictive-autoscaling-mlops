#!/usr/bin/env python3
"""
Data Preprocessing — Predictive Autoscaling MLOps
==================================================
Membersihkan data mentah hasil ingestion dan melakukan feature engineering
agar dataset siap digunakan untuk pelatihan model prediksi skala (ML-ready).

Tahapan pemrosesan:
  1. Load CSV dari data/raw/ (file terbaru atau path eksplisit)
  2. Normalisasi timestamp & pengurutan kronologis
  3. Deduplikasi berdasarkan timestamp
  4. Penanganan missing values (ffill + interpolasi linear)
  5. Konversi satuan (php_memory_bytes → MB)
  6. Feature engineering (lag, rolling stats, delta, temporal)
  7. Pembuatan target variable (request_rate t+60s)
  8. Simpan ke data/processed/ dengan nama file berbasis timestamp

Usage:
    python src/preprocess.py
    python src/preprocess.py --input data/raw/metrics_20260927_180000.csv
    python src/preprocess.py --input data/raw/metrics_20260927_180000.csv --output data/processed/out.csv
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# Kolom metrik yang diharapkan dari Prometheus ingestion
EXPECTED_COLS = [
    "request_rate",
    "php_cpu_cores",
    "php_memory_bytes",
    "replicas",
    "p95_latency_seconds",
]

# Horizon prediksi: 60 detik ke depan (4 langkah × 15 detik)
PREDICTION_HORIZON_STEPS = 4

# Rolling window dalam jumlah baris (1 baris = 15 detik)
ROLL_WINDOW_30S = 2   # 2 baris × 15s = 30 detik
ROLL_WINDOW_60S = 4   # 4 baris × 15s = 60 detik

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
# Helper Functions
# ---------------------------------------------------------------------------
def find_latest_raw_file(raw_dir: Path) -> Path | None:
    """
    Temukan file CSV terbaru di direktori raw berdasarkan waktu modifikasi.

    Parameters
    ----------
    raw_dir : Path
        Direktori tempat file CSV mentah disimpan.

    Returns
    -------
    Path or None
        Path ke file terbaru, atau None jika tidak ada file CSV.
    """
    csv_files = list(raw_dir.glob("*.csv"))
    # Kecualikan file khusus yang bukan hasil ingestion
    csv_files = [f for f in csv_files if not f.name.startswith("master_")]
    if not csv_files:
        return None
    return max(csv_files, key=lambda f: f.stat().st_mtime)


def load_raw(input_path: Path) -> pd.DataFrame:
    """
    Muat CSV mentah dan parse kolom timestamp sebagai index datetime UTC.

    Parameters
    ----------
    input_path : Path
        Path ke file CSV mentah.

    Returns
    -------
    pd.DataFrame
        DataFrame dengan DatetimeIndex UTC.

    Raises
    ------
    SystemExit
        Jika file tidak ditemukan atau format tidak sesuai.
    """
    if not input_path.exists():
        log.error("File tidak ditemukan: %s", input_path)
        sys.exit(1)

    log.info("Memuat data dari: %s", input_path)
    df = pd.read_csv(input_path, index_col="timestamp", parse_dates=True)

    # Pastikan index adalah DatetimeIndex dengan timezone UTC
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    log.info("Data dimuat: %d baris, %d kolom", len(df), len(df.columns))
    return df


def validate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Periksa keberadaan kolom yang diharapkan. Kolom yang hilang diisi NaN.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame input.

    Returns
    -------
    pd.DataFrame
        DataFrame dengan semua kolom yang diharapkan.
    """
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        log.warning("Kolom berikut tidak ditemukan dan akan diisi NaN: %s", missing)
        for col in missing:
            df[col] = float("nan")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tahap pembersihan data:
      - Urutkan index secara kronologis (ascending)
      - Hapus baris duplikat berdasarkan timestamp
      - Konversi php_memory_bytes → php_memory_mb
      - Isi missing values: ffill untuk p95_latency_seconds,
        interpolasi linear untuk metrik lainnya

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame mentah yang sudah divalidasi kolom-kolomnya.

    Returns
    -------
    pd.DataFrame
        DataFrame yang sudah bersih.
    """
    # 1. Urutkan secara kronologis
    df = df.sort_index()
    n_before = len(df)

    # 2. Deduplikasi — pertahankan baris terakhir jika ada duplikat timestamp
    df = df[~df.index.duplicated(keep="last")]
    n_removed = n_before - len(df)
    if n_removed > 0:
        log.info("Deduplikasi: dihapus %d baris duplikat", n_removed)

    # 3. Konversi satuan memory: bytes → megabytes (2 desimal)
    if "php_memory_bytes" in df.columns:
        df["php_memory_mb"] = (df["php_memory_bytes"] / 1_048_576).round(2)
        df = df.drop(columns=["php_memory_bytes"])
        log.info("Konversi: php_memory_bytes → php_memory_mb")

    # 4. Penanganan missing values
    # p95_latency_seconds: ffill — saat tidak ada traffic, latensi sebelumnya dipertahankan
    if "p95_latency_seconds" in df.columns:
        before = df["p95_latency_seconds"].isna().sum()
        df["p95_latency_seconds"] = df["p95_latency_seconds"].ffill()
        after = df["p95_latency_seconds"].isna().sum()
        if before > 0:
            log.info("ffill p95_latency_seconds: mengisi %d nilai kosong", before - after)

    # Metrik lainnya: interpolasi linear untuk gap kecil (≤5 baris)
    interp_cols = [c for c in ["request_rate", "php_cpu_cores", "php_memory_mb", "replicas"] if c in df.columns]
    for col in interp_cols:
        n_na = df[col].isna().sum()
        if n_na > 0:
            df[col] = df[col].interpolate(method="linear", limit=5)
            remaining = df[col].isna().sum()
            log.info("Interpolasi %s: mengisi %d/%d nilai kosong", col, n_na - remaining, n_na)

    log.info("Setelah cleaning: %d baris valid", len(df))
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Feature engineering untuk prediksi beban kerja:
      - Lag features: t-1 dan t-2 untuk request_rate dan php_cpu_cores
      - Rolling mean (30s, 60s) dan rolling std (60s) untuk request_rate
      - Delta features: perubahan request_rate dan cpu antar langkah
      - Temporal features: jam dan menit dari timestamp (UTC)
      - Target variable: request_rate yang digeser 4 langkah ke depan (t+60s)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame yang sudah dibersihkan.

    Returns
    -------
    pd.DataFrame
        DataFrame dengan fitur tambahan dan target variable.
    """
    # Lag features
    df["rps_lag1"] = df["request_rate"].shift(1)
    df["rps_lag2"] = df["request_rate"].shift(2)
    df["cpu_lag1"] = df["php_cpu_cores"].shift(1)
    df["cpu_lag2"] = df["php_cpu_cores"].shift(2)

    # Rolling features untuk request_rate
    df["rps_roll_mean_30s"] = df["request_rate"].rolling(window=ROLL_WINDOW_30S, min_periods=1).mean().round(4)
    df["rps_roll_mean_60s"] = df["request_rate"].rolling(window=ROLL_WINDOW_60S, min_periods=1).mean().round(4)
    df["rps_roll_std_60s"] = df["request_rate"].rolling(window=ROLL_WINDOW_60S, min_periods=1).std().round(4)

    # Delta features (laju perubahan antar langkah)
    df["rps_delta"] = df["request_rate"].diff().round(4)
    df["cpu_delta"] = df["php_cpu_cores"].diff().round(4)

    # Temporal features
    df["hour"] = df.index.hour
    df["minute"] = df.index.minute

    # Target variable: request_rate di t+60s (digeser 4 langkah ke belakang)
    df["target_rps_60s"] = df["request_rate"].shift(-PREDICTION_HORIZON_STEPS)

    log.info("Feature engineering selesai: %d kolom total", len(df.columns))
    return df


def drop_incomplete_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hapus baris yang tidak memiliki target variable (baris akhir setelah shift)
    atau yang masih memiliki terlalu banyak NaN di kolom fitur.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame setelah feature engineering.

    Returns
    -------
    pd.DataFrame
        DataFrame dengan baris yang siap untuk pelatihan model.
    """
    n_before = len(df)
    # Hapus baris tanpa target (PREDICTION_HORIZON_STEPS baris terakhir)
    df = df.dropna(subset=["target_rps_60s"])
    n_dropped = n_before - len(df)
    if n_dropped > 0:
        log.info("Dihapus %d baris tanpa target variable (horizon window)", n_dropped)
    return df


def save_processed(df: pd.DataFrame, output_path: Path) -> None:
    """
    Simpan DataFrame yang sudah diproses ke file CSV.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame hasil preprocessing.
    output_path : Path
        Lokasi penyimpanan output CSV.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path)
    log.info("Dataset processed disimpan: %s (%d baris, %d kolom)", output_path, len(df), len(df.columns))


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    """Parse argumen CLI."""
    parser = argparse.ArgumentParser(
        description="Preprocess data mentah Prometheus untuk ML training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/preprocess.py
  python src/preprocess.py --input data/raw/metrics_20260927_180000.csv
  python src/preprocess.py --input data/raw/metrics_20260927_180000.csv --output data/processed/out.csv
        """,
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path ke file CSV mentah. Jika tidak diisi, file terbaru di data/raw/ akan digunakan.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path output CSV hasil preprocessing. Default: data/processed/metrics_processed_TIMESTAMP.csv",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point utama preprocessing pipeline."""
    args = parse_args()

    # Tentukan input file
    if args.input:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = REPO_ROOT / input_path
    else:
        input_path = find_latest_raw_file(RAW_DIR)
        if input_path is None:
            log.error(
                "Tidak ada file CSV ditemukan di %s. "
                "Jalankan ingestion terlebih dahulu:\n"
                "  python src/ingest_data.py --minutes 30",
                RAW_DIR,
            )
            return 1
        log.info("Menggunakan file terbaru: %s", input_path)

    # Tentukan output path — non-destructive dengan timestamp
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
    else:
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = PROCESSED_DIR / f"metrics_processed_{ts_str}.csv"

    # Pipeline preprocessing
    df = load_raw(input_path)
    df = validate_columns(df)
    df = clean(df)
    df = engineer_features(df)
    df = drop_incomplete_rows(df)

    if df.empty:
        log.error("Dataset kosong setelah preprocessing. Periksa kualitas data input.")
        return 1

    save_processed(df, output_path)

    # Summary output
    log.info("\n=== Ringkasan Dataset Processed ===")
    log.info("Kolom : %s", list(df.columns))
    log.info("Shape : %s", df.shape)
    log.info("Periode: %s → %s", df.index.min(), df.index.max())
    return 0


if __name__ == "__main__":
    sys.exit(main())
