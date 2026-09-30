"""
Unit tests for Data Drift Detector and Continuous Training.
Verifies Population Stability Index (PSI) calculations, Kolmogorov-Smirnov test,
and drift classification logic.
"""

import numpy as np
import pandas as pd
import pytest

from src.monitoring.drift_detector import (
    DriftDetector,
    assess_feature_drift,
    calculate_psi,
    generate_drifted_dataset,
)


def test_calculate_psi_identical_distributions() -> None:
    np.random.seed(42)
    dist1 = np.random.normal(20.0, 5.0, 1000)
    dist2 = dist1.copy()

    psi = calculate_psi(dist1, dist2)
    assert psi == pytest.approx(0.0, abs=1e-3)


def test_calculate_psi_shifted_distribution() -> None:
    np.random.seed(42)
    ref = np.random.normal(15.0, 3.0, 1000)
    # Substantial distribution shift
    curr = np.random.normal(35.0, 8.0, 1000)

    psi = calculate_psi(ref, curr)
    assert psi > 0.25


def test_assess_feature_drift_classification() -> None:
    ref = pd.Series(np.random.normal(10.0, 2.0, 500))
    # Identical distribution
    res_stable = assess_feature_drift(ref, ref, feature_name="request_rate")
    assert res_stable.drift_level == "NO_DRIFT"
    assert res_stable.has_drift is False

    # Shifted distribution
    curr_shifted = pd.Series(np.random.normal(30.0, 5.0, 500))
    res_drift = assess_feature_drift(ref, curr_shifted, feature_name="request_rate")
    assert res_drift.drift_level == "SIGNIFICANT_DRIFT"
    assert res_drift.has_drift is True


def test_drift_detector_dataframe_evaluation() -> None:
    ref_df = pd.DataFrame(
        {
            "request_rate": np.random.normal(15.0, 2.0, 200),
            "php_cpu_cores": np.random.normal(0.4, 0.05, 200),
            "p95_latency_seconds": np.random.normal(0.03, 0.005, 200),
            "php_memory_mb": np.random.normal(120.0, 5.0, 200),
            "rps_roll_mean_60s": np.random.normal(15.0, 2.0, 200),
        }
    )

    detector = DriftDetector(ref_df, psi_threshold=0.20)
    drifted_df = generate_drifted_dataset(ref_df, traffic_multiplier=2.5)

    report = detector.evaluate_drift(drifted_df)
    assert report.overall_drift_detected is True
    assert len(report.features_with_drift) > 0
    assert "request_rate" in report.features_with_drift
