#!/usr/bin/env python3
"""
Automated Telemetry Ingestion & DVC MinIO Versioning Pipeline
=============================================================
Menjalankan siklus data engineering secara otomatis (hands-free):
  1. Ingestion: Mengambil telemetri time-series dari Prometheus API
  2. Preprocessing: Cleaning, normalisasi, dan feature engineering (17 fitur)
  3. DVC Commit: Menghitung hash MD5 dan memperbarui pointer versioning lokal
  4. DVC Push: Mengunggah artefak biner dataset ke MinIO Object Storage (s3://mlops-dvc)
  5. Git Sync (Opsional): Melakukan git commit pada file pointer .dvc

Usage:
  python src/pipeline/auto_ingest_and_version.py --minutes 1440
  python src/pipeline/auto_ingest_and_version.py --minutes 60 --git-commit
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Konfigurasi path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AUTO-DATA-PIPELINE]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("auto-ingest-dvc")


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Parse file .env sederhana jika ada."""
    env_vars: Dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip().strip("'\"")
    return env_vars


def prepare_environment() -> Dict[str, str]:
    """Menyiapkan environment variables lengkap dengan kredensial MinIO dan perbaikan checksum."""
    env = os.environ.copy()
    env_from_file = load_env_file(REPO_ROOT / ".env")

    # Injeksi kredensial jika belum ada di environment sistem
    for k, v in env_from_file.items():
        if k not in env:
            env[k] = v

    # Fallback kredensial default untuk MinIO storage.titipin.me
    if "AWS_ACCESS_KEY_ID" not in env:
        env["AWS_ACCESS_KEY_ID"] = "titipin_minio"
    if "AWS_SECRET_ACCESS_KEY" not in env:
        env["AWS_SECRET_ACCESS_KEY"] = "rahasiawoy"

    # Fix krusial: Kompatibilitas boto3 checksum dengan MinIO (mencegah MissingContentLength)
    env["AWS_REQUEST_CHECKSUM_CALCULATION"] = "when_required"
    env["AWS_RESPONSE_CHECKSUM_VALIDATION"] = "when_required"

    return env


def run_command(cmd: list[str], env: Dict[str, str], description: str) -> str:
    """Menjalankan command shell dengan logging dan handling error."""
    logger.info("Mengeksekusi [%s]: %s", description, " ".join(cmd))
    t0 = time.time()
    res = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    duration = round(time.time() - t0, 2)
    if res.returncode != 0:
        logger.error("Gagal mengeksekusi [%s] (code %d):\n%s\n%s", description, res.returncode, res.stdout, res.stderr)
        raise RuntimeError(f"Command failed: {description} ({res.stderr.strip()})")
    logger.info("Berhasil [%s] dalam %.2fs", description, duration)
    return res.stdout.strip()


def run_pipeline(minutes: int = 1440, step: int = 15, skip_dvc: bool = False, git_commit: bool = False) -> Dict[str, Any]:
    """Menjalankan end-to-end ingestion, feature engineering, dan DVC push."""
    t_start = datetime.now(timezone.utc)
    env = prepare_environment()
    python_bin = sys.executable

    print("\n" + "=" * 78)
    print("      AUTOMATED END-TO-END DATA INGESTION & DVC STORAGE VERSIONING")
    print("=" * 78)
    print(f"Waktu Eksekusi    : {t_start.isoformat()}")
    print(f"Time Window       : {minutes} menit ({round(minutes / 60, 1)} jam terakhir)")
    print(f"Resolusi Scraping : {step} detik")
    print(f"MinIO Push Target : s3://mlops-dvc (https://storage.titipin.me)")
    print("-" * 78)

    # 1. Tahap Ingestion
    logger.info("[1/4] Mengambil telemetri produksi dari Prometheus...")
    ingest_cmd = [
        python_bin,
        "src/ingest_data.py",
        "--minutes",
        str(minutes),
        "--step",
        str(step),
    ]
    ingest_out = run_command(ingest_cmd, env, "Prometheus Ingestion")

    # 2. Tahap Preprocessing
    logger.info("[2/4] Membersihkan data dan melakukan feature engineering...")
    prep_cmd = [python_bin, "src/preprocess.py"]
    prep_out = run_command(prep_cmd, env, "Data Preprocessing & Feature Engineering")

    dvc_status_out = ""
    dvc_push_out = ""

    if not skip_dvc:
        # Cari binary DVC (di venv atau sistem)
        dvc_bin = "dvc"
        local_dvc = REPO_ROOT / ".venv" / "bin" / "dvc"
        if local_dvc.exists():
            dvc_bin = str(local_dvc)

        # 3. Tahap DVC Commit
        logger.info("[3/4] Meng-commit perubahan dataset ke DVC cache...")
        dvc_commit_cmd = [dvc_bin, "commit", "-f"]
        run_command(dvc_commit_cmd, env, "DVC Local Commit")

        # 4. Tahap DVC Push ke MinIO
        logger.info("[4/4] Mengunggah artefak biner dataset ke MinIO Object Storage...")
        dvc_push_cmd = [dvc_bin, "push"]
        dvc_push_out = run_command(dvc_push_cmd, env, "DVC Push to MinIO")
        print("✓ Artefak dataset berhasil diunggah ke MinIO CAS Storage!")

        if git_commit:
            logger.info("[Git] Melakukan commit pointer .dvc ke repository...")
            git_add_cmd = ["git", "add", "data/raw.dvc", "data/processed.dvc"]
            run_command(git_add_cmd, env, "Git Add DVC Pointers")

            ts_tag = t_start.strftime("%Y%m%d_%H%M%S")
            msg = f"data(dvc): auto-snapshot {minutes}m window [{ts_tag}]"
            git_commit_cmd = ["git", "commit", "-m", msg]
            run_command(git_commit_cmd, env, "Git Commit DVC Pointers")
            print(f"✓ File pointer .dvc berhasil di-commit ke Git: '{msg}'")
    else:
        logger.info("DVC push dilewati (--skip-dvc diaktifkan).")

    print("=" * 78)
    print("🎉 DATA PIPELINE SELESAI: Dataset tersinkronisasi dan siap dipakai training!")
    print("=" * 78 + "\n")

    return {
        "status": "SUCCESS",
        "timestamp": t_start.isoformat(),
        "minutes": minutes,
        "step": step,
        "dvc_pushed": not skip_dvc,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated Ingestion and DVC Sync Pipeline")
    parser.add_argument("--minutes", type=int, default=1440, help="Jendela waktu ingestion dalam menit (default: 1440 = 24 jam)")
    parser.add_argument("--step", type=int, default=15, help="Resolusi query dalam detik (default: 15)")
    parser.add_argument("--skip-dvc", action="store_true", help="Lewati tahap DVC commit dan push")
    parser.add_argument("--git-commit", action="store_true", help="Otomatis jalankan git commit pada file pointer .dvc")
    args = parser.parse_args()

    try:
        run_pipeline(
            minutes=args.minutes,
            step=args.step,
            skip_dvc=args.skip_dvc,
            git_commit=args.git_commit,
        )
    except Exception as e:
        logger.error("Data pipeline terhenti karena kesalahan: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
