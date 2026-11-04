#!/usr/bin/env python3
"""
Model Evaluation Gate & Automated Staging Registry (LK-08: Code as a Trigger).
=============================================================================
Memvalidasi metrik performa model hasil pelatihan otomatis terhadap ambang batas
(SLO LK-01). Jika lolos kriteria evaluasi (Evaluation Gate PASSED), model akan
secara otomatis didaftarkan ke MLflow Model Registry dengan status 'Staging'.

Tahap dalam MLOps Automation Pipeline:
  - Tahap 3: Model Evaluation & Validation (memeriksa MAE, RMSE, R², Latency)
  - Tahap 4: Auto-Registry Update (mendaftarkan versi ke stage 'Staging')

Usage:
    python src/models/evaluate_and_register.py --all
    python src/models/evaluate_and_register.py --eval-only
    python src/models/evaluate_and_register.py --register-staging
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import mlflow
from mlflow.tracking import MlflowClient

# ---------------------------------------------------------------------------
# Constants & Defaults (Berdasarkan Target SLO LK-01)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = REPO_ROOT / "models"
REPORTS_DIR = REPO_ROOT / "reports"
CHAMPION_META_FILE = MODELS_DIR / "champion_model_metadata.json"
DEFAULT_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
REGISTERED_MODEL_NAME = "predictive-autoscaler"

# Ambang Batas Kualitas Model (Performance Thresholds)
DEFAULT_MAX_MAE = 5.0  # MAE toleransi maksimal: 5.0 RPS (setengah kapasitas 1 Pod)
DEFAULT_MAX_RMSE = 15.0  # RMSE toleransi maksimal: 15.0 RPS
DEFAULT_MIN_R2 = 0.70  # Koefisien determinasi minimum: 0.70 (kemampuan jelajah variansi)
DEFAULT_MAX_LATENCY_MS = 100.0  # Batas latensi inferensi: 100 ms (SLO autoscaler K8s)

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("eval_registry")


# ---------------------------------------------------------------------------
# Tahap 3: Model Evaluation & Threshold Validation
# ---------------------------------------------------------------------------
def evaluate_model_quality(
    meta_path: Path,
    max_mae: float = DEFAULT_MAX_MAE,
    max_rmse: float = DEFAULT_MAX_RMSE,
    min_r2: float = DEFAULT_MIN_R2,
    max_latency_ms: float = DEFAULT_MAX_LATENCY_MS,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Membandingkan metrik model hasil training otomatis dengan ambang batas kualitas (Quality Gate).
    Mengembalikan (passed, evaluation_details).
    """
    if not meta_path.exists():
        raise FileNotFoundError(
            f"File metadata model tidak ditemukan di: {meta_path}. "
            "Pastikan Tahap 2 (Automated Training) telah dijalankan terlebih dahulu."
        )

    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    metrics = meta_data.get("metrics", {})
    val_mae = float(metrics.get("val_mae", float("inf")))
    val_rmse = float(metrics.get("val_rmse", float("inf")))
    val_r2 = float(metrics.get("val_r2", -1.0))
    latency_ms = float(metrics.get("latency_ms", float("inf")))

    checks = {
        "val_mae": {
            "name": "Validation MAE (RPS)",
            "value": val_mae,
            "threshold": f"<= {max_mae}",
            "passed": val_mae <= max_mae,
        },
        "val_rmse": {
            "name": "Validation RMSE",
            "value": val_rmse,
            "threshold": f"<= {max_rmse}",
            "passed": val_rmse <= max_rmse,
        },
        "val_r2": {
            "name": "Validation R² Score",
            "value": val_r2,
            "threshold": f">= {min_r2}",
            "passed": val_r2 >= min_r2,
        },
        "latency_ms": {
            "name": "Inference Latency (ms)",
            "value": latency_ms,
            "threshold": f"<= {max_latency_ms} ms",
            "passed": latency_ms <= max_latency_ms,
        },
    }

    all_passed = all(c["passed"] for c in checks.values())

    log.info("=" * 70)
    log.info("TAHAP 3: MODEL EVALUATION & QUALITY GATE VALIDATION")
    log.info("=" * 70)
    log.info("Model Candidate : %s", meta_data.get("champion_run_name", "unknown"))
    log.info("Run ID          : %s", meta_data.get("champion_run_id", "unknown"))
    log.info("Model Type      : %s", meta_data.get("champion_model_type", "unknown"))
    log.info("-" * 70)
    log.info("%-25s | %-12s | %-15s | %s", "Metrik Pengujian", "Nilai Terukur", "Ambang Batas", "Status")
    log.info("-" * 70)
    for k, v in checks.items():
        status_str = "PASSED" if v["passed"] else "FAILED"
        val_str = f"{v['value']:.4f}" if isinstance(v['value'], float) else str(v['value'])
        log.info("%-25s | %-12s | %-15s | %s", v["name"], val_str, v["threshold"], status_str)
    log.info("-" * 70)
    log.info(
        "HASIL EVALUASI GATE : %s",
        "PASSED (Lolos Ambang Batas)" if all_passed else "FAILED (Melanggar Ambang Batas)",
    )
    log.info("=" * 70)

    # Simpan laporan evaluasi ke direktori reports/
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / "model_evaluation_gate.json"
    eval_summary = {
        "candidate_run_name": meta_data.get("champion_run_name"),
        "candidate_run_id": meta_data.get("champion_run_id"),
        "model_type": meta_data.get("champion_model_type"),
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_status": "PASSED" if all_passed else "FAILED",
        "checks": checks,
    }
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)

    return all_passed, eval_summary


# ---------------------------------------------------------------------------
# Tahap 4: Auto-Registry Update (Staging Promotion)
# ---------------------------------------------------------------------------
def register_candidate_to_staging(
    client: MlflowClient,
    model_name: str,
    meta_path: Path,
) -> Tuple[bool, str]:
    """
    Mendaftarkan model kandidat baru ke MLflow Model Registry dan menetapkan status 'Staging'.
    """
    log.info("\n" + "=" * 70)
    log.info("TAHAP 4: AUTO-REGISTRY UPDATE TO STAGING")
    log.info("=" * 70)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    run_id = meta_data["champion_run_id"]
    run_name = meta_data.get("champion_run_name", "candidate-model")
    metrics = meta_data.get("metrics", {})

    # 1. Pastikan registered model tersedia
    try:
        client.get_registered_model(model_name)
    except Exception:
        log.info("Membuat Registered Model baru di MLflow: '%s'...", model_name)
        client.create_registered_model(
            name=model_name,
            description="Predictive autoscaler workload forecasting models managed via automated CI/CD pipeline.",
        )

    # 2. Daftarkan model version baru dari Run ID
    model_uri = f"runs:/{run_id}/model"
    log.info("Mendaftarkan model version dari Run URI: %s...", model_uri)
    mv = client.create_model_version(
        name=model_name,
        source=model_uri,
        run_id=run_id,
        description=(
            f"Automated CI/CD Model Candidate: {run_name} — "
            f"Val MAE: {metrics.get('val_mae', 'N/A')}, Val RMSE: {metrics.get('val_rmse', 'N/A')}. "
            "Didaftarkan otomatis melalui pemicu kode GitHub Actions (LK-08)."
        ),
        tags={
            "trigger": "code_push_github_actions",
            "evaluation_gate": "PASSED",
            "model_type": meta_data.get("champion_model_type", "lightgbm"),
            "val_mae": str(metrics.get("val_mae", "N/A")),
            "val_rmse": str(metrics.get("val_rmse", "N/A")),
            "val_r2": str(metrics.get("val_r2", "N/A")),
            "latency_ms": str(metrics.get("latency_ms", "N/A")),
            "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    new_version = str(mv.version)
    log.info("Model berhasil terdaftar sebagai Versi: %s (Status: %s)", new_version, mv.status)

    # 3. Transisikan stage ke 'Staging'
    log.info("Mengalihkan stage Versi %s ke 'Staging'...", new_version)
    client.transition_model_version_stage(
        name=model_name,
        version=new_version,
        stage="Staging",
        archive_existing_versions=False,
    )

    # 4. Sematkan alias @staging dan @challenger
    try:
        client.set_registered_model_alias(name=model_name, alias="staging", version=new_version)
        client.set_registered_model_alias(name=model_name, alias="challenger", version=new_version)
        log.info("Alias '@staging' dan '@challenger' berhasil disematkan pada Versi %s.", new_version)
    except Exception as e:
        log.warning("Penyematan alias registry: %s", e)

    log.info("=" * 70)
    log.info("RINGKASAN REGISTRASI OTOMATIS (STAGING)")
    log.info("=" * 70)
    log.info("Registered Model Name : %s", model_name)
    log.info("Registered Version    : Versi %s", new_version)
    log.info("Operational Stage     : Staging")
    log.info("Active Aliases        : @staging, @challenger")
    log.info("Status Registrasi     : SUKSES (Tersedia untuk Pengujian Inferensi Staging)")
    log.info("=" * 70)

    return True, new_version


# ---------------------------------------------------------------------------
# Main CLI Orchestrator
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="LK-08: Model Evaluation Gate and Automated Staging Registry"
    )
    parser.add_argument(
        "--tracking-uri",
        type=str,
        default=DEFAULT_TRACKING_URI,
        help=f"MLflow Tracking URI (default: {DEFAULT_TRACKING_URI})",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=REGISTERED_MODEL_NAME,
        help=f"Registered model name (default: {REGISTERED_MODEL_NAME})",
    )
    parser.add_argument(
        "--meta-file",
        type=Path,
        default=CHAMPION_META_FILE,
        help=f"Path to candidate metadata JSON (default: {CHAMPION_META_FILE})",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Hanya jalankan evaluasi ambang batas performa tanpa registrasi",
    )
    parser.add_argument(
        "--register-staging",
        action="store_true",
        help="Hanya jalankan registrasi model ke stage Staging",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Jalankan evaluasi gate lengkap dan daftarkan ke Staging bila lulus",
    )
    parser.add_argument(
        "--max-mae",
        type=float,
        default=DEFAULT_MAX_MAE,
        help=f"Ambang batas maksimum MAE (default: {DEFAULT_MAX_MAE})",
    )
    parser.add_argument(
        "--max-rmse",
        type=float,
        default=DEFAULT_MAX_RMSE,
        help=f"Ambang batas maksimum RMSE (default: {DEFAULT_MAX_RMSE})",
    )
    parser.add_argument(
        "--min-r2",
        type=float,
        default=DEFAULT_MIN_R2,
        help=f"Ambang batas minimum R2 (default: {DEFAULT_MIN_R2})",
    )
    parser.add_argument(
        "--max-latency",
        type=float,
        default=DEFAULT_MAX_LATENCY_MS,
        help=f"Ambang batas maksimum latensi ms (default: {DEFAULT_MAX_LATENCY_MS})",
    )
    args = parser.parse_args()

    # 1. Jalankan Tahap 3 (Evaluation Gate) jika diminta
    if args.eval_only or args.all or (not args.register_staging):
        passed, details = evaluate_model_quality(
            meta_path=args.meta_file,
            max_mae=args.max_mae,
            max_rmse=args.max_rmse,
            min_r2=args.min_r2,
            max_latency_ms=args.max_latency,
        )
        if not passed:
            log.error("❌ Model gagal memenuhi ambang batas kualitas! Pipeline dihentikan.")
            sys.exit(1)

        if args.eval_only:
            log.info("Evaluasi mandiri selesai. Model lolos seluruh ambang batas.")
            sys.exit(0)

    # 2. Jalankan Tahap 4 (Auto-Registry Update to Staging)
    if args.register_staging or args.all:
        mlflow.set_tracking_uri(args.tracking_uri)
        client = MlflowClient(args.tracking_uri)
        success, version = register_candidate_to_staging(
            client=client,
            model_name=args.model_name,
            meta_path=args.meta_file,
        )
        if not success:
            log.error("❌ Registrasi ke Staging gagal.")
            sys.exit(1)

        log.info("Tahap 4 selesai dengan sukses. Model Versi %s siap di Staging.", version)


if __name__ == "__main__":
    main()
