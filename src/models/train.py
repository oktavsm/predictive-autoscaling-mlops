#!/usr/bin/env python3
"""
Model Training & Experiment Tracking Pipeline — Predictive Autoscaling MLOps
=============================================================================
Melatih model pembelajaran mesin untuk peramalan beban kerja (request rate)
dengan horizon 60 detik ke depan, dan mencatat seluruh parameter, metrik,
serta artefak model ke MLflow Tracking Server.

Model Kandidat:
  1. Ridge Regression (Linear Model Baseline)
  2. Random Forest Regressor (Non-linear Tree Ensemble)
  3. LightGBM Regressor (Gradient Boosted Decision Trees - Default)
  4. LightGBM Tuned (Hyperparameter Tuned)

Metrik Evaluasi:
  - MAE (Mean Absolute Error)
  - RMSE (Root Mean Squared Error)
  - R² (Coefficient of Determination)
  - MAPE (Mean Absolute Percentage Error)
  - Latency (Rata-rata waktu inferensi per request dalam milidetik)

Usage:
    python src/models/train.py --all
    python src/models/train.py --model lightgbm
    python src/models/train.py --model ridge
    python src/models/train.py --model random_forest
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
import lightgbm as lgb
import mlflow
import mlflow.lightgbm
import mlflow.sklearn

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"
MODELS_DIR = REPO_ROOT / "models"
DEFAULT_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
EXPERIMENT_NAME = "predictive-autoscaling-workload"
PREDICTION_HORIZON_SECONDS = 60
RANDOM_STATE = 42

# Fitur-fitur prediktor (input) — 'replicas' sengaja dikeluarkan demi mencegah data leakage
FEATURE_COLUMNS: List[str] = [
    "request_rate",
    "php_cpu_cores",
    "p95_latency_seconds",
    "php_memory_mb",
    "rps_lag1",
    "rps_lag2",
    "cpu_lag1",
    "cpu_lag2",
    "rps_roll_mean_30s",
    "rps_roll_mean_60s",
    "rps_roll_std_60s",
    "rps_delta",
    "cpu_delta",
    "hour",
    "minute",
]
TARGET_COLUMN: str = "target_rps_60s"

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("train")


# ---------------------------------------------------------------------------
# Data Preparation
# ---------------------------------------------------------------------------
def load_and_prepare_dataset(
    processed_dir: Path,
    feature_cols: List[str],
    target_col: str,
    train_ratio: float = 0.85,
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Memuat seluruh dataset olahan dari data/processed/, menggabungkan secara kronologis,
    membersihkan baris dengan nilai kosong, dan membagi menjadi train & validation set.
    """
    csv_files = sorted(list(processed_dir.glob("*.csv")))
    if not csv_files:
        raise FileNotFoundError(
            f"Tidak ditemukan file dataset CSV di {processed_dir}. "
            "Pastikan telah menjalankan 'make dvc-pull' atau 'make preprocess'."
        )

    log.info("Memuat %d file processed dataset...", len(csv_files))
    dfs = []
    for f in csv_files:
        try:
            df_part = pd.read_csv(f)
            if "timestamp" in df_part.columns:
                df_part["timestamp"] = pd.to_datetime(df_part["timestamp"], utc=True)
                df_part = df_part.sort_values("timestamp")
            dfs.append(df_part)
        except Exception as e:
            log.warning("Gagal membaca berkas %s: %s", f.name, e)

    if not dfs:
        raise ValueError("Gagal mengurai dataset dari berkas yang tersedia.")

    combined_df = pd.concat(dfs, ignore_index=True)
    if "timestamp" in combined_df.columns:
        combined_df = combined_df.sort_values("timestamp").drop_duplicates(
            subset=["timestamp"], keep="last"
        )

    # Pastikan seluruh kolom yang dibutuhkan ada
    missing_cols = [c for c in feature_cols + [target_col] if c not in combined_df.columns]
    if missing_cols:
        raise KeyError(f"Kolom wajib tidak ditemukan dalam dataset: {missing_cols}")

    # Bersihkan baris yang mengandung NaN pada fitur maupun target
    cleaned_df = combined_df.dropna(subset=feature_cols + [target_col]).copy()
    total_samples = len(cleaned_df)
    log.info("Total data sampel bersih siap latih: %d baris", total_samples)

    if total_samples < 20:
        raise ValueError(
            f"Jumlah sampel terlalu sedikit ({total_samples} baris) untuk pelatihan model."
        )

    # Time-series chronological split (tanpa shuffle untuk menghindari lookahead bias)
    split_idx = int(total_samples * train_ratio)
    train_df = cleaned_df.iloc[:split_idx]
    val_df = cleaned_df.iloc[split_idx:]

    X_train = train_df[feature_cols].astype(float)
    y_train = train_df[target_col].astype(float)
    X_val = val_df[feature_cols].astype(float)
    y_val = val_df[target_col].astype(float)

    log.info(
        "Pemisahan data runtun waktu: %d baris Train (%.0f%%), %d baris Validasi (%.0f%%)",
        len(X_train),
        train_ratio * 100,
        len(X_val),
        (1 - train_ratio) * 100,
    )
    return X_train, y_train, X_val, y_val, cleaned_df


# ---------------------------------------------------------------------------
# Metric Calculation & Evaluation
# ---------------------------------------------------------------------------
def calculate_metrics(y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Menghitung metrik performa regresi standar industri.
    """
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    r2 = float(r2_score(y_true, y_pred))

    # MAPE dengan proteksi pembagian nol (epsilon = 1e-4)
    epsilon = 1e-4
    mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), epsilon))) * 100)

    return {
        "val_mae": round(mae, 4),
        "val_rmse": round(rmse, 4),
        "val_r2": round(r2, 4),
        "val_mape": round(mape, 4),
    }


def measure_inference_latency(
    model: Any, sample_input: pd.DataFrame, n_iterations: int = 100
) -> float:
    """
    Mengukur rata-rata latensi inferensi per request dalam milidetik (ms).
    """
    single_row = sample_input.iloc[[0]]
    # Warmup
    for _ in range(5):
        _ = model.predict(single_row)

    start_time = time.perf_counter()
    for _ in range(n_iterations):
        _ = model.predict(single_row)
    total_time = time.perf_counter() - start_time

    avg_latency_ms = (total_time / n_iterations) * 1000.0
    return round(avg_latency_ms, 3)


# ---------------------------------------------------------------------------
# Visualization & Plotting Artifacts
# ---------------------------------------------------------------------------
def generate_and_log_plots(
    model_name: str,
    y_true: pd.Series,
    y_pred: np.ndarray,
    feature_names: List[str],
    feature_importances: np.ndarray | None,
    output_dir: Path,
) -> List[Path]:
    """
    Membuat grafik komparasi Prediksi vs Aktual dan Feature Importance,
    kemudian menyimpannya ke disk untuk dicatat sebagai artefak MLflow.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_plots = []

    # 1. Plot Prediksi vs Aktual pada Validation Set
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(
        range(len(y_true)),
        y_true.values,
        label="Aktual (Ground Truth)",
        color="#1f77b4",
        linewidth=2.0,
    )
    ax.plot(
        range(len(y_pred)),
        y_pred,
        label=f"Prediksi ({model_name})",
        color="#ff7f0e",
        linestyle="--",
        linewidth=2.0,
    )
    ax.set_title(
        f"Evaluasi Horizon 60s: Aktual vs Prediksi — {model_name}", fontsize=12, fontweight="bold"
    )
    ax.set_xlabel("Langkah Waktu Uji (Interval 15s)", fontsize=10)
    ax.set_ylabel("Request Rate (RPS)", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")
    plt.tight_layout()

    pred_plot_path = output_dir / f"{model_name}_pred_vs_actual.png"
    plt.savefig(pred_plot_path, dpi=150)
    plt.close(fig)
    generated_plots.append(pred_plot_path)

    # 2. Plot Feature Importance (jika didukung arsitektur model)
    if feature_importances is not None and len(feature_importances) == len(feature_names):
        fig, ax = plt.subplots(figsize=(8, 5))
        indices = np.argsort(feature_importances)
        ax.barh(range(len(indices)), feature_importances[indices], align="center", color="#2ca02c")
        ax.set_yticks(range(len(indices)))
        ax.set_yticklabels([feature_names[i] for i in indices])
        ax.set_title(f"Feature Importance — {model_name}", fontsize=12, fontweight="bold")
        ax.set_xlabel("Nilai Kontribusi Fitur", fontsize=10)
        ax.grid(True, axis="x", linestyle=":", alpha=0.6)
        plt.tight_layout()

        importance_plot_path = output_dir / f"{model_name}_feature_importance.png"
        plt.savefig(importance_plot_path, dpi=150)
        plt.close(fig)
        generated_plots.append(importance_plot_path)

    return generated_plots


# ---------------------------------------------------------------------------
# Training Orchestration
# ---------------------------------------------------------------------------
def train_single_model(
    model_type: str,
    params: Dict[str, Any],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    artifact_dir: Path,
) -> Dict[str, Any]:
    """
    Melatih satu instans model dengan parameter spesifik dan mencatat ke MLflow.
    """
    run_name = params.get("run_name", f"{model_type}-experiment")
    log.info("=" * 60)
    log.info("Memulai eksperimen: %s (Tipe: %s)", run_name, model_type)

    feature_importances = None

    if model_type == "ridge":
        alpha = params.get("alpha", 1.0)
        model = Ridge(alpha=alpha, random_state=RANDOM_STATE)
        model.fit(X_train, y_train)
        if hasattr(model, "coef_"):
            feature_importances = np.abs(model.coef_)

    elif model_type == "random_forest":
        n_estimators = params.get("n_estimators", 100)
        max_depth = params.get("max_depth", 6)
        model = RandomForestRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        feature_importances = model.feature_importances_

    elif model_type in ["lightgbm", "lightgbm_tuned"]:
        learning_rate = params.get("learning_rate", 0.05)
        n_estimators = params.get("n_estimators", 150)
        max_depth = params.get("max_depth", 5)
        num_leaves = params.get("num_leaves", 31)

        model = lgb.LGBMRegressor(
            learning_rate=learning_rate,
            n_estimators=n_estimators,
            max_depth=max_depth,
            num_leaves=num_leaves,
            random_state=RANDOM_STATE,
            verbosity=-1,
        )
        model.fit(X_train, y_train)
        feature_importances = model.feature_importances_

    else:
        raise ValueError(f"Tipe model '{model_type}' tidak dikenali.")

    # 1. Prediksi & Evaluasi Metrik
    y_train_pred = model.predict(X_train)
    y_val_pred = model.predict(X_val)

    train_mae = round(float(mean_absolute_error(y_train, y_train_pred)), 4)
    metrics = calculate_metrics(y_val, y_val_pred)
    metrics["train_mae"] = train_mae

    # 2. Uji Benchmark Latensi Inferensi
    latency_ms = measure_inference_latency(model, X_val)
    metrics["latency_ms"] = latency_ms

    log.info(
        "Hasil Evaluasi [%s] ➔ Val MAE: %.4f | Val RMSE: %.4f | Val R²: %.4f | Latency: %.2f ms",
        run_name,
        metrics["val_mae"],
        metrics["val_rmse"],
        metrics["val_r2"],
        metrics["latency_ms"],
    )

    # 3. Catat Seluruh Parameter, Metrik & Artefak ke MLflow Run
    with mlflow.start_run(run_name=run_name) as run:
        run_id = run.info.run_id

        # Log parameters
        mlflow.log_param("model_type", model_type)
        mlflow.log_param("horizon_seconds", PREDICTION_HORIZON_SECONDS)
        mlflow.log_param("train_samples", len(X_train))
        mlflow.log_param("val_samples", len(X_val))
        for p_key, p_val in params.items():
            if p_key != "run_name":
                mlflow.log_param(p_key, p_val)

        # Log metrics
        for m_key, m_val in metrics.items():
            mlflow.log_metric(m_key, m_val)

        # Generate & log plots
        plots = generate_and_log_plots(
            model_name=run_name,
            y_true=y_val,
            y_pred=y_val_pred,
            feature_names=list(X_train.columns),
            feature_importances=feature_importances,
            output_dir=artifact_dir,
        )
        for plot_path in plots:
            mlflow.log_artifact(str(plot_path), artifact_path="evaluation_plots")

        # Log model artifact with signature & example
        input_example = X_val.head(2)
        if model_type in ["lightgbm", "lightgbm_tuned"]:
            mlflow.lightgbm.log_model(
                lgb_model=model,
                name="model",
                input_example=input_example,
            )
        else:
            mlflow.sklearn.log_model(
                sk_model=model,
                name="model",
                input_example=input_example,
                serialization_format="cloudpickle",
            )

        log.info("MLflow Run berhasil disimpan! Run ID: %s", run_id)

    return {
        "model_type": model_type,
        "run_name": run_name,
        "run_id": run_id,
        "metrics": metrics,
        "params": params,
        "model": model,
    }


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pelatihan Model Prediksi Autoscaling dengan Tracking MLflow (LK-06)"
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=["ridge", "random_forest", "lightgbm", "lightgbm_tuned"],
        help="Latih model spesifik tunggal",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Jalankan seluruh variasi model (Ridge, Random Forest, LightGBM, LightGBM Tuned)",
    )
    parser.add_argument(
        "--tracking-uri",
        type=str,
        default=DEFAULT_TRACKING_URI,
        help=f"MLflow Tracking URI (default: {DEFAULT_TRACKING_URI})",
    )
    args = parser.parse_args()

    # Siapkan direktori artefak lokal
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    plot_artifact_dir = REPO_ROOT / "docs" / "images"
    plot_artifact_dir.mkdir(parents=True, exist_ok=True)

    # Inisialisasi MLflow
    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)
    log.info("MLflow Tracking URI aktif: %s", args.tracking_uri)
    log.info("MLflow Experiment Name : %s", EXPERIMENT_NAME)

    # Muat dataset terproses
    X_train, y_train, X_val, y_val, _ = load_and_prepare_dataset(
        processed_dir=PROCESSED_DATA_DIR,
        feature_cols=FEATURE_COLUMNS,
        target_col=TARGET_COLUMN,
    )

    # Definisikan variasi eksperimen
    experiment_configs = [
        {
            "model_type": "ridge",
            "params": {"run_name": "ridge-linear-baseline", "alpha": 1.0},
        },
        {
            "model_type": "random_forest",
            "params": {
                "run_name": "random-forest-default",
                "n_estimators": 100,
                "max_depth": 6,
            },
        },
        {
            "model_type": "lightgbm",
            "params": {
                "run_name": "lightgbm-default",
                "learning_rate": 0.05,
                "n_estimators": 150,
                "max_depth": 5,
                "num_leaves": 31,
            },
        },
        {
            "model_type": "lightgbm_tuned",
            "params": {
                "run_name": "lightgbm-tuned",
                "learning_rate": 0.03,
                "n_estimators": 200,
                "max_depth": 4,
                "num_leaves": 15,
            },
        },
    ]

    # Filter variasi yang akan dieksekusi
    if args.model:
        selected_configs = [c for c in experiment_configs if c["model_type"] == args.model]
    else:
        # Default jika tidak ada argumen atau diberikan --all: jalankan seluruh 4 eksperimen
        selected_configs = experiment_configs

    results = []
    for cfg in selected_configs:
        res = train_single_model(
            model_type=cfg["model_type"],
            params=cfg["params"],
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            artifact_dir=plot_artifact_dir,
        )
        results.append(res)

    # -----------------------------------------------------------------------
    # Champion Selection (Pemilihan Model Terbaik Berdasarkan Val MAE)
    # -----------------------------------------------------------------------
    log.info("\n" + "=" * 70)
    log.info("RINGKASAN HASIL PERBANDINGAN EKSPERIMEN (LEMBAR KERJA LK-06)")
    log.info("=" * 70)

    summary_table = []
    best_candidate = None
    lowest_mae = float("inf")

    for r in results:
        mae = r["metrics"]["val_mae"]
        rmse = r["metrics"]["val_rmse"]
        r2 = r["metrics"]["val_r2"]
        lat = r["metrics"]["latency_ms"]
        name = r["run_name"]

        summary_table.append(
            {
                "Run Name": name,
                "Tipe Model": r["model_type"],
                "Val MAE": mae,
                "Val RMSE": rmse,
                "Val R²": r2,
                "Latency (ms)": lat,
                "Run ID": r["run_id"],
            }
        )

        if mae < lowest_mae:
            lowest_mae = mae
            best_candidate = r

    summary_df = pd.DataFrame(summary_table)
    print("\n" + summary_df.to_string(index=False) + "\n")

    if best_candidate:
        log.info(
            "🌟 MODEL TERBAIK (CHAMPION CANDIDATE): '%s' dengan Val MAE = %.4f RPS",
            best_candidate["run_name"],
            lowest_mae,
        )

        # Simpan metadata model terbaik ke file JSON untuk konsumsi LK-07 (Model Registry)
        metadata = {
            "champion_run_name": best_candidate["run_name"],
            "champion_run_id": best_candidate["run_id"],
            "champion_model_type": best_candidate["model_type"],
            "horizon_seconds": PREDICTION_HORIZON_SECONDS,
            "parameters": best_candidate["params"],
            "metrics": best_candidate["metrics"],
            "features": FEATURE_COLUMNS,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        metadata_file = MODELS_DIR / "champion_model_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        log.info("Metadata model champion tersimpan di: %s", metadata_file)

        # Simpan objek model langsung untuk fallback lokal
        try:
            import joblib
            joblib.dump(best_candidate["model"], MODELS_DIR / "champion_model.joblib")
            log.info("Objek model champion tersimpan di: %s", MODELS_DIR / "champion_model.joblib")
        except Exception as e:
            log.warning("Gagal menyimpan champion_model.joblib: %s", e)

    log.info("Pelatihan & Logging ke MLflow selesai dengan sempurna!")


if __name__ == "__main__":
    main()
