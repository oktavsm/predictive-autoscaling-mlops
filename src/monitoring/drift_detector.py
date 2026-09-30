"""
Data Drift Detection Module for Telemetry & Feature Distributions.
Calculates Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) tests
between baseline training data and production workloads to trigger Continuous Training (CT).
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("drift-detector")

MONITORED_FEATURES = [
    "request_rate",
    "php_cpu_cores",
    "p95_latency_seconds",
    "php_memory_mb",
    "rps_roll_mean_60s",
]


@dataclass
class FeatureDriftResult:
    feature_name: str
    psi_score: float
    ks_statistic: float
    ks_pvalue: float
    drift_level: str  # "NO_DRIFT", "MODERATE_DRIFT", "SIGNIFICANT_DRIFT"
    has_drift: bool
    ref_mean: float
    curr_mean: float
    ref_std: float
    curr_std: float


@dataclass
class DriftReport:
    timestamp: str
    reference_dataset: str
    current_dataset: str
    reference_samples: int
    current_samples: int
    overall_drift_detected: bool
    features_analyzed: int
    features_with_drift: List[str]
    details: Dict[str, FeatureDriftResult]


def calculate_psi(
    expected: np.ndarray,
    actual: np.ndarray,
    num_bins: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """Calculates the Population Stability Index (PSI) between two continuous distributions.

    PSI < 0.1   : No significant shift (Stable)
    0.1 <= PSI < 0.2: Moderate shift (Monitor closely)
    PSI >= 0.2  : Significant distribution shift (Drift detected)
    """
    if len(expected) == 0 or len(actual) == 0:
        return 0.0

    # Determine quantile bin edges based on expected reference distribution
    percentiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(expected, percentiles)
    # Ensure strictly increasing edges by adding tiny epsilon if values are tied
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 2:
        # Uniform or single-valued distribution
        bin_edges = np.array([expected.min() - 1e-5, expected.max() + 1e-5])

    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    # Calculate frequency counts in each bin
    expected_counts, _ = np.histogram(expected, bins=bin_edges)
    actual_counts, _ = np.histogram(actual, bins=bin_edges)

    # Convert to relative proportions with smoothing epsilon
    expected_pct = expected_counts / len(expected) + epsilon
    actual_pct = actual_counts / len(actual) + epsilon

    # Normalize proportions so they sum to 1.0
    expected_pct /= expected_pct.sum()
    actual_pct /= actual_pct.sum()

    # PSI formula: sum((actual - expected) * ln(actual / expected))
    psi_val = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(max(0.0, psi_val))


def assess_feature_drift(
    ref_series: pd.Series,
    curr_series: pd.Series,
    feature_name: str,
    psi_threshold: float = 0.20,
    ks_alpha: float = 0.01,
) -> FeatureDriftResult:
    """Evaluates PSI and KS 2-sample statistical test on a specific feature."""
    ref_clean = ref_series.dropna().to_numpy(dtype=float)
    curr_clean = curr_series.dropna().to_numpy(dtype=float)

    if len(ref_clean) == 0 or len(curr_clean) == 0:
        return FeatureDriftResult(
            feature_name=feature_name,
            psi_score=0.0,
            ks_statistic=0.0,
            ks_pvalue=1.0,
            drift_level="NO_DRIFT",
            has_drift=False,
            ref_mean=0.0,
            curr_mean=0.0,
            ref_std=0.0,
            curr_std=0.0,
        )

    psi_score = calculate_psi(ref_clean, curr_clean)
    ks_stat, ks_pval = stats.ks_2samp(ref_clean, curr_clean)

    # Classify drift level
    if psi_score >= psi_threshold or ks_pval < ks_alpha:
        level = "SIGNIFICANT_DRIFT"
        has_drift = True
    elif psi_score >= 0.10:
        level = "MODERATE_DRIFT"
        has_drift = False
    else:
        level = "NO_DRIFT"
        has_drift = False

    return FeatureDriftResult(
        feature_name=feature_name,
        psi_score=round(psi_score, 4),
        ks_statistic=round(float(ks_stat), 4),
        ks_pvalue=round(float(ks_pval), 6),
        drift_level=level,
        has_drift=has_drift,
        ref_mean=round(float(np.mean(ref_clean)), 3),
        curr_mean=round(float(np.mean(curr_clean)), 3),
        ref_std=round(float(np.std(ref_clean)), 3),
        curr_std=round(float(np.std(curr_clean)), 3),
    )


class DriftDetector:
    """Orchestrates multi-feature drift analysis between reference and production datasets."""

    def __init__(
        self,
        reference_data: pd.DataFrame,
        psi_threshold: float = 0.20,
        features: Optional[List[str]] = None,
    ):
        self.ref_df = reference_data.copy()
        self.psi_threshold = psi_threshold
        self.features = features or [f for f in MONITORED_FEATURES if f in self.ref_df.columns]

    def evaluate_drift(
        self,
        current_data: pd.DataFrame,
        ref_name: str = "reference_baseline",
        curr_name: str = "current_production",
    ) -> DriftReport:
        details: Dict[str, FeatureDriftResult] = {}
        drifted_features: List[str] = []

        for feat in self.features:
            if feat not in current_data.columns:
                logger.warning("Feature '%s' missing from current dataset. Skipping.", feat)
                continue

            result = assess_feature_drift(
                ref_series=self.ref_df[feat],
                curr_series=current_data[feat],
                feature_name=feat,
                psi_threshold=self.psi_threshold,
            )
            details[feat] = result
            if result.has_drift:
                drifted_features.append(feat)

        overall_drift = len(drifted_features) > 0
        from datetime import datetime, timezone

        report = DriftReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            reference_dataset=ref_name,
            current_dataset=curr_name,
            reference_samples=len(self.ref_df),
            current_samples=len(current_data),
            overall_drift_detected=overall_drift,
            features_analyzed=len(details),
            features_with_drift=drifted_features,
            details=details,
        )
        return report


def generate_drifted_dataset(
    base_df: pd.DataFrame,
    traffic_multiplier: float = 2.4,
    cpu_multiplier: float = 2.1,
) -> pd.DataFrame:
    """Generates synthetic production dataset with injected traffic shift (useful for verification/tests)."""
    drifted = base_df.copy()
    if "request_rate" in drifted.columns:
        drifted["request_rate"] = drifted["request_rate"] * traffic_multiplier + np.random.normal(
            5.0, 1.5, len(drifted)
        )
        drifted["request_rate"] = drifted["request_rate"].clip(lower=0.0)
    if "php_cpu_cores" in drifted.columns:
        drifted["php_cpu_cores"] = drifted["php_cpu_cores"] * cpu_multiplier
    if "rps_roll_mean_60s" in drifted.columns:
        drifted["rps_roll_mean_60s"] = drifted["rps_roll_mean_60s"] * traffic_multiplier
    if "p95_latency_seconds" in drifted.columns:
        drifted["p95_latency_seconds"] = drifted["p95_latency_seconds"] * 1.8
    return drifted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Data Drift Detection Engine")
    parser.add_argument("--reference", help="Path to reference baseline CSV")
    parser.add_argument(
        "--current", help="Path to current production CSV (or omit to simulate shift)"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.20, help="PSI drift threshold (default: 0.20)"
    )
    parser.add_argument(
        "--output", default="reports/drift_report_latest.json", help="Path to save report JSON"
    )
    parser.add_argument(
        "--simulate-drift", action="store_true", help="Simulate a workload surge drift scenario"
    )
    parser.add_argument(
        "--fail-on-drift", action="store_true", help="Exit with code 1 if drift is detected"
    )
    return parser.parse_args()


def find_default_reference() -> str:
    files = sorted(glob.glob("data/processed/*_processed.csv"))
    if files:
        return files[0]
    return "data/processed/metrics_20260930_123000_processed.csv"


def main() -> None:
    args = parse_args()
    ref_path = args.reference or find_default_reference()
    if not os.path.exists(ref_path):
        logger.error("Reference dataset not found at: %s", ref_path)
        sys.exit(2)

    logger.info("Loading reference dataset: %s", ref_path)
    ref_df = pd.read_csv(ref_path)

    if args.current and os.path.exists(args.current):
        logger.info("Loading current production dataset: %s", args.current)
        curr_df = pd.read_csv(args.current)
        curr_name = os.path.basename(args.current)
    elif args.simulate_drift:
        logger.info("Generating synthetic drifted production workload (Workload Surge x2.4)...")
        curr_df = generate_drifted_dataset(ref_df, traffic_multiplier=2.4)
        curr_name = "simulated_workload_surge_drift"
    else:
        # Default: if multiple processed files exist, use latest as current
        files = sorted(glob.glob("data/processed/*_processed.csv"))
        if len(files) > 1 and files[-1] != ref_path:
            logger.info("Using latest batch as current: %s", files[-1])
            curr_df = pd.read_csv(files[-1])
            curr_name = os.path.basename(files[-1])
        else:
            logger.info("Evaluating baseline against simulated drift scenario...")
            curr_df = generate_drifted_dataset(ref_df, traffic_multiplier=2.2)
            curr_name = "simulated_drift_evaluation"

    detector = DriftDetector(ref_df, psi_threshold=args.threshold)
    report = detector.evaluate_drift(
        curr_df, ref_name=os.path.basename(ref_path), curr_name=curr_name
    )

    # Display clean formatted terminal report
    print("\n" + "=" * 70)
    print("      MLOps PRODUCTION TELEMETRY DATA DRIFT REPORT (PSI & KS-TEST)")
    print("=" * 70)
    print(f"Reference Baseline : {report.reference_dataset} ({report.reference_samples} rows)")
    print(f"Current Telemetry  : {report.current_dataset} ({report.current_samples} rows)")
    print(f"PSI Threshold      : {args.threshold}")
    print("-" * 70)
    print(f"{'Feature Name':<22} | {'PSI Score':<9} | {'KS p-val':<10} | {'Status':<18}")
    print("-" * 70)

    for feat, res in report.details.items():
        status_icon = (
            "🔴 DRIFT"
            if res.has_drift
            else ("🟡 WARN" if res.drift_level == "MODERATE_DRIFT" else "🟢 STABLE")
        )
        print(
            f"{feat:<22} | {res.psi_score:<9.4f} | {res.ks_pvalue:<10.6f} | {status_icon} ({res.drift_level})"
        )

    print("=" * 70)
    if report.overall_drift_detected:
        print(f"🚨 STATUS: DRIFT DETECTED! Features affected: {report.features_with_drift}")
        print("💡 RECOMMENDATION: Trigger Continuous Training (CT) pipeline to retrain models.")
    else:
        print("✅ STATUS: DISTRIBUTIONS STABLE. No continuous retraining required.")
    print("=" * 70 + "\n")

    # Save JSON report
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    report_dict = asdict(report)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)
    logger.info("Drift evaluation report saved to: %s", args.output)

    if args.fail_on_drift and report.overall_drift_detected:
        sys.exit(1)


if __name__ == "__main__":
    main()
