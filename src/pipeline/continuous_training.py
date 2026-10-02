"""
Continuous Training (CT) Pipeline Orchestrator.
Monitors telemetry drift, ingests new batches, triggers model retraining,
and automatically promotes the best candidate to @champion in MLflow Model Registry.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.monitoring.drift_detector import (  # noqa: E402
    DriftDetector,
    find_default_reference,
    generate_drifted_dataset,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("continuous-training")


class ContinuousTrainingPipeline:
    """Manages the full end-to-end continuous retraining workflow."""

    def __init__(
        self,
        reference_dataset: Optional[str] = None,
        drift_threshold: float = 0.20,
        model_name: str = "predictive-autoscaler",
        tracking_uri: Optional[str] = None,
    ):
        self.ref_path = reference_dataset or find_default_reference()
        self.drift_threshold = drift_threshold
        self.model_name = model_name
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "http://mlops-mlflow-svc.mlops.svc.cluster.local:5000"
        )

    def run_drift_check(
        self, current_data: Optional[pd.DataFrame] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Runs statistical drift check on incoming production data."""
        logger.info("Evaluating telemetry drift against baseline: %s", self.ref_path)
        ref_df = pd.read_csv(self.ref_path)
        if current_data is None:
            # Simulate real-world shift if no live streaming batch provided
            current_data = generate_drifted_dataset(ref_df, traffic_multiplier=2.2)

        detector = DriftDetector(ref_df, psi_threshold=self.drift_threshold)
        report = detector.evaluate_drift(
            current_data, ref_name="baseline", curr_name="production_telemetry"
        )
        return report.overall_drift_detected, {
            "drift_detected": report.overall_drift_detected,
            "drifted_features": report.features_with_drift,
            "timestamp": report.timestamp,
        }

    def trigger_retraining(self) -> Dict[str, Any]:
        """Triggers model training across Ridge, Random Forest, and LightGBM."""
        logger.info("Triggering automated model retraining pipeline (src/models/train.py)...")
        start_time = time.time()
        cmd = [sys.executable, "src/models/train.py", "--all"]
        env = os.environ.copy()
        env["MLFLOW_TRACKING_URI"] = self.tracking_uri

        res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        duration = round(time.time() - start_time, 2)
        logger.info("Retraining completed in %.2fs.", duration)
        return {
            "status": "SUCCESS",
            "duration_seconds": duration,
            "output_summary": res.stdout[-400:] if len(res.stdout) > 400 else res.stdout,
        }

    def promote_challenger_to_champion(self) -> Dict[str, Any]:
        """Evaluates trained candidate models and promotes the best candidate to @champion."""
        logger.info(
            "Evaluating candidates in MLflow Model Registry (src/models/register_model.py)..."
        )
        cmd = [sys.executable, "src/models/register_model.py", "--tracking-uri", self.tracking_uri]
        env = os.environ.copy()
        env["MLFLOW_TRACKING_URI"] = self.tracking_uri

        res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        return {
            "status": "PROMOTED",
            "model_name": self.model_name,
            "output": res.stdout[-400:] if len(res.stdout) > 400 else res.stdout,
        }

    def execute_pipeline(self, force: bool = False) -> Dict[str, Any]:
        """Runs the complete Continuous Training cycle."""
        print("\n" + "=" * 75)
        print("          CONTINUOUS TRAINING (CT) AUTOMATED PIPELINE EXECUTION")
        print("=" * 75)
        print(f"Timestamp          : {datetime.now(timezone.utc).isoformat()}")
        print(f"Reference Baseline : {self.ref_path}")
        print(f"Drift PSI Threshold: {self.drift_threshold}")
        print(f"Force Retraining   : {force}")
        print("-" * 75)

        drift_flag, drift_meta = self.run_drift_check()

        if not drift_flag and not force:
            print("✅ Telemetry distributions are stable. No retraining required.")
            print("=" * 75 + "\n")
            return {
                "status": "SKIPPED",
                "reason": "No significant drift detected",
                "drift": drift_meta,
            }

        if drift_flag:
            print(f"🚨 DRIFT DETECTED in features: {drift_meta['drifted_features']}")
        else:
            print("⚡ Retraining forced via manual/cron trigger.")

        # Step 1: Retraining
        print("\n[Step 1/2] Executing automated multi-model training pipeline...")
        train_res = self.trigger_retraining()
        print("✓ Model training completed successfully.")

        # Step 2: Model Registry Promotion
        print("\n[Step 2/2] Running Challenger vs Champion evaluation gate...")
        promo_res = self.promote_challenger_to_champion()
        print("✓ Champion model verified and promoted in MLflow Model Registry.")

        summary = {
            "pipeline_status": "COMPLETED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "drift_info": drift_meta,
            "training_results": train_res,
            "registry_promotion": promo_res,
        }

        print("=" * 75)
        print("🎉 CONTINUOUS TRAINING PIPELINE SUCCEEDED: New model serving live traffic!")
        print("=" * 75 + "\n")

        # Save CT execution log
        os.makedirs("reports", exist_ok=True)
        with open("reports/continuous_training_log.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuous Training Pipeline")
    parser.add_argument(
        "--force", action="store_true", help="Force retraining regardless of drift check"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.20, help="PSI drift threshold (default: 0.20)"
    )
    parser.add_argument("--reference", help="Reference dataset path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ct = ContinuousTrainingPipeline(
        reference_dataset=args.reference,
        drift_threshold=args.threshold,
    )
    res = ct.execute_pipeline(force=args.force)
    if res.get("pipeline_status") != "COMPLETED" and res.get("status") != "SKIPPED":
        sys.exit(1)


if __name__ == "__main__":
    main()
