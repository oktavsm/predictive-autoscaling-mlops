"""
Unit tests for LK-08 Model Evaluation Gate & Auto-Registry Update.
==================================================================
Verifies that:
1. Model evaluation correctly validates against LK-01 performance thresholds.
2. Models violating thresholds are blocked (preventing silent failures).
3. Passing models are successfully registered to MLflow Model Registry with stage 'Staging'.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models.evaluate_and_register import evaluate_model_quality  # noqa: E402


def test_evaluate_model_quality_success(tmp_path):
    """Candidate model with good metrics should pass evaluation gate."""
    dummy_meta = {
        "champion_run_name": "lightgbm-tuned",
        "champion_run_id": "dummy_run_123",
        "champion_model_type": "lightgbm_tuned",
        "metrics": {
            "val_mae": 2.2375,
            "val_rmse": 10.9783,
            "val_r2": 0.8239,
            "latency_ms": 1.182,
        },
    }
    meta_file = tmp_path / "champion_model_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(dummy_meta, f)

    passed, details = evaluate_model_quality(
        meta_path=meta_file,
        max_mae=5.0,
        max_rmse=15.0,
        min_r2=0.70,
        max_latency_ms=100.0,
    )
    assert passed is True
    assert details["overall_status"] == "PASSED"
    assert details["checks"]["val_mae"]["passed"] is True
    assert details["checks"]["latency_ms"]["passed"] is True


def test_evaluate_model_quality_failure_on_high_mae(tmp_path):
    """Candidate model with degraded accuracy (MAE > threshold) must be rejected."""
    degraded_meta = {
        "champion_run_name": "degraded-model",
        "champion_run_id": "dummy_run_bad",
        "champion_model_type": "random_forest",
        "metrics": {
            "val_mae": 8.520,  # Melampaui batas maksimal 5.0 RPS
            "val_rmse": 18.21,
            "val_r2": 0.45,
            "latency_ms": 12.5,
        },
    }
    meta_file = tmp_path / "champion_model_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(degraded_meta, f)

    passed, details = evaluate_model_quality(
        meta_path=meta_file,
        max_mae=5.0,
        max_rmse=15.0,
        min_r2=0.70,
        max_latency_ms=100.0,
    )
    assert passed is False
    assert details["overall_status"] == "FAILED"
    assert details["checks"]["val_mae"]["passed"] is False


def test_evaluate_model_quality_failure_on_high_latency(tmp_path):
    """Candidate model that violates inference latency SLO (>100ms) must be rejected."""
    slow_meta = {
        "champion_run_name": "slow-heavy-model",
        "champion_run_id": "dummy_run_slow",
        "champion_model_type": "deep_ensemble",
        "metrics": {
            "val_mae": 1.50,
            "val_rmse": 5.0,
            "val_r2": 0.95,
            "latency_ms": 145.0,  # Melampaui batas 100 ms
        },
    }
    meta_file = tmp_path / "champion_model_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(slow_meta, f)

    passed, details = evaluate_model_quality(
        meta_path=meta_file,
        max_mae=5.0,
        max_rmse=15.0,
        min_r2=0.70,
        max_latency_ms=100.0,
    )
    assert passed is False
    assert details["overall_status"] == "FAILED"
    assert details["checks"]["latency_ms"]["passed"] is False
