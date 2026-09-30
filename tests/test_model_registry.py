"""
Tests for MLflow Model Registry and Inference Readiness (LK-07).
================================================================
Verifies that:
1. Champion model metadata file exists and contains valid metrics.
2. Model registry manifest exists and conforms to expected structure.
3. Model can be loaded from registry and provides valid predictions.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
CHAMPION_META = REPO_ROOT / "models" / "champion_model_metadata.json"
REGISTRY_MANIFEST = REPO_ROOT / "models" / "model_registry_manifest.yaml"


def test_champion_metadata_exists():
    """Champion model metadata file should exist and have required fields."""
    assert CHAMPION_META.exists(), f"Metadata not found at {CHAMPION_META}"
    with open(CHAMPION_META, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "champion_run_id" in data
    assert "champion_run_name" in data
    assert "metrics" in data
    assert "val_mae" in data["metrics"]
    assert data["metrics"]["val_mae"] < 5.0, "Champion MAE should be within acceptable threshold"


def test_registry_manifest_exists():
    """Model registry manifest must exist and contain both versions and deployment policy."""
    assert REGISTRY_MANIFEST.exists(), f"Manifest not found at {REGISTRY_MANIFEST}"
    with open(REGISTRY_MANIFEST, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    assert manifest["model_name"] == "predictive-autoscaler"
    assert "versions" in manifest
    assert "version_1" in manifest["versions"]
    assert "version_2" in manifest["versions"]

    # Version 2 must be champion / production
    v2 = manifest["versions"]["version_2"]
    assert v2["alias"] == "champion"
    assert v2["stage"] == "Production"

    # Deployment policy
    policy = manifest["deployment_policy"]
    assert policy["inference_readiness_status"] == "PASSED"
    assert policy["min_replicas"] == 1
    assert policy["max_replicas"] == 4


def test_inference_readiness_verification():
    """Test verify_inference_readiness logic from register_model module."""
    try:
        from src.models.register_model import verify_inference_readiness
    except ImportError:
        pytest.skip("register_model cannot be imported in this environment")

    # Only test if sqlite mlflow.db exists
    db_file = REPO_ROOT / "mlflow.db"
    if not db_file.exists():
        pytest.skip("mlflow.db not present for registry inference check")

    success, avg_latency, details = verify_inference_readiness(
        tracking_uri="sqlite:///mlflow.db",
        model_name="predictive-autoscaler",
        alias="champion",
    )
    assert success is True
    assert avg_latency < 100.0, f"Average inference latency too high: {avg_latency} ms"
    assert len(details["scenarios"]) == 3
