#!/usr/bin/env python3
"""
Automated Alerting & Incident Management Dispatcher
===================================================
Dispatches production alerts and MLOps incident notifications to
Discord Webhooks, Telegram Bots, and audit log trails.

Supports:
- Data / Concept Drift alerts (PSI > 0.25)
- SLO Latency Breaches (P95 > 200ms or 5xx > 1%)
- Automated Retraining Lifecycle & Model Promotion notifications
- Scaling Saturation / Pod Limit warnings
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [ALERT-DISPATCHER]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("alert-dispatcher")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
AUDIT_LOG_FILE = os.getenv("ALERT_AUDIT_LOG", "logs/alerts_history.jsonl")


class AlertDispatcher:
    """Dispatches MLOps incident notifications to configured channels."""

    def __init__(
        self,
        discord_url: Optional[str] = None,
        telegram_token: Optional[str] = None,
        telegram_chat: Optional[str] = None,
        audit_file: Optional[str] = None,
    ):
        self.discord_url = discord_url or DISCORD_WEBHOOK_URL
        self.telegram_token = telegram_token or TELEGRAM_BOT_TOKEN
        self.telegram_chat = telegram_chat or TELEGRAM_CHAT_ID
        self.audit_file = audit_file or AUDIT_LOG_FILE

        if self.audit_file:
            os.makedirs(
                os.path.dirname(self.audit_file) if os.path.dirname(self.audit_file) else ".",
                exist_ok=True,
            )

    def _log_audit(self, event_type: str, title: str, details: Dict[str, Any]) -> None:
        """Appends alert to structured JSONL audit trail."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "title": title,
            "details": details,
        }
        try:
            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.warning("Failed to write to audit log: %s", e)

    def dispatch_discord(
        self, title: str, description: str, color_hex: int, fields: List[Dict[str, str]]
    ) -> bool:
        """Sends rich embed message to Discord Webhook."""
        if not self.discord_url:
            logger.debug("Discord webhook URL not configured; skipping Discord dispatch.")
            return False

        payload = {
            "username": "Titipin MLOps Guardian",
            "avatar_url": "https://raw.githubusercontent.com/kubernetes/kubernetes/master/logo/logo.png",
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": color_hex,
                    "fields": fields,
                    "footer": {
                        "text": f"Cluster: AWS K3s • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    },
                }
            ],
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.discord_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Titipin-MLOps-AlertBot/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status in (200, 204):
                    logger.info("Discord alert delivered: %s", title)
                    return True
        except Exception as exc:
            logger.warning("Failed to dispatch Discord alert: %s", exc)
        return False

    def dispatch_telegram(self, text: str) -> bool:
        """Sends HTML/Markdown message to Telegram Bot."""
        if not (self.telegram_token and self.telegram_chat):
            logger.debug("Telegram credentials not configured; skipping Telegram dispatch.")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            data = urllib.parse.urlencode(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    logger.info("Telegram alert delivered successfully.")
                    return True
        except Exception as exc:
            logger.warning("Failed to dispatch Telegram alert: %s", exc)
        return False

    # -------------------------------------------------------------------------
    # Specialized High-Level Alert Methods
    # -------------------------------------------------------------------------
    def notify_data_drift(
        self,
        psi_score: float,
        threshold: float = 0.25,
        drift_features: Optional[List[str]] = None,
        auto_retrain_triggered: bool = True,
    ) -> None:
        """Triggered when telemetry distribution shifts significantly."""
        title = "🚨 [INCIDENT] High Data Drift Detected (PSI Alert)"
        desc = (
            f"Population Stability Index (PSI) has crossed critical threshold: "
            f"**`{psi_score:.4f}`** (Threshold: `{threshold:.2f}`)."
        )
        features_str = (
            ", ".join(drift_features) if drift_features else "request_rate, php_cpu_cores"
        )
        color = 0xFF5722  # Deep Orange

        fields = [
            {"name": "📊 PSI Score", "value": f"`{psi_score:.4f}`", "inline": True},
            {
                "name": "⚠️ Drift Level",
                "value": "Major Distribution Shift" if psi_score > 0.25 else "Moderate Drift",
                "inline": True,
            },
            {"name": "🧬 Affected Features", "value": f"`{features_str}`", "inline": False},
            {
                "name": "🔄 Automated Action",
                "value": "✅ Retraining Triggered"
                if auto_retrain_triggered
                else "⏸️ Manual Approval Needed",
                "inline": True,
            },
            {
                "name": "🔗 Observability",
                "value": "[Grafana MLOps](https://grafana.titipin.me)",
                "inline": True,
            },
        ]

        # Audit & Console
        logger.warning("DATA DRIFT ALERT: PSI=%.4f (Features: %s)", psi_score, features_str)
        self._log_audit(
            "DATA_DRIFT",
            title,
            {"psi": psi_score, "threshold": threshold, "features": drift_features},
        )

        # Dispatches
        self.dispatch_discord(title, desc, color, fields)
        tg_text = (
            f"🚨 *[INCIDENT] High Data Drift Detected*\n\n"
            f"• *PSI Score:* `{psi_score:.4f}` (Threshold: `{threshold:.2f}`)\n"
            f"• *Features:* `{features_str}`\n"
            f"• *Action:* {'Triggering Autonomous Retraining...' if auto_retrain_triggered else 'Investigate via Grafana'}\n"
            f"• *Dashboard:* https://grafana.titipin.me"
        )
        self.dispatch_telegram(tg_text)

    def notify_slo_violation(self, p95_latency_ms: float, error_rate_pct: float = 0.0) -> None:
        """Triggered when latency or error rate exceeds SLO."""
        title = "⚠️ [SLO BREACH] Service Degradation Warning"
        desc = f"Incoming workload latency exceeded the SLO ceiling (P95: **`{p95_latency_ms:.1f}ms`** > 100ms)."
        color = 0xF44336  # Red

        fields = [
            {"name": "⏱️ P95 Latency", "value": f"`{p95_latency_ms:.1f} ms`", "inline": True},
            {"name": "❌ HTTP 5xx Rate", "value": f"`{error_rate_pct:.2f}%`", "inline": True},
            {"name": "🎯 Target Deployment", "value": "`titipin/laravel-backend`", "inline": True},
            {
                "name": "🛡️ Remediation",
                "value": "Predictive Scaler auto-scaling pod ceiling.",
                "inline": False,
            },
        ]

        logger.warning(
            "SLO BREACH ALERT: P95=%.1fms, Errors=%.2f%%", p95_latency_ms, error_rate_pct
        )
        self._log_audit(
            "SLO_BREACH", title, {"p95_latency_ms": p95_latency_ms, "error_rate": error_rate_pct}
        )

        self.dispatch_discord(title, desc, color, fields)
        tg_text = (
            f"⚠️ *[SLO BREACH] Latency Spike Detected*\n\n"
            f"• *P95 Latency:* `{p95_latency_ms:.1f} ms`\n"
            f"• *Error Rate:* `{error_rate_pct:.2f}%`\n"
            f"• *Cluster Action:* Scaling up pod replicas.\n"
            f"• *Live Metrics:* https://grafana.titipin.me"
        )
        self.dispatch_telegram(tg_text)

    def notify_retraining_promotion(
        self,
        model_name: str,
        new_version: str,
        new_mae: float,
        champion_mae: float,
        promoted: bool = True,
    ) -> None:
        """Triggered when continuous training finishes evaluation."""
        delta = champion_mae - new_mae
        pct_improvement = (delta / max(0.001, champion_mae)) * 100.0
        title = (
            "🎉 [CT-PIPELINE] New Champion Model Promoted"
            if promoted
            else "ℹ️ [CT-PIPELINE] Challenger Model Evaluated"
        )
        desc = (
            f"Continuous training job evaluated **`{model_name} (v{new_version})`**. "
            f"Validation MAE improved by **`{pct_improvement:.1f}%`**."
        )
        color = 0x4CAF50 if promoted else 0x2196F3  # Green / Blue

        fields = [
            {"name": "📦 Model Name", "value": f"`{model_name}`", "inline": True},
            {"name": "🏷️ Version", "value": f"`v{new_version}`", "inline": True},
            {
                "name": "👑 Stage Status",
                "value": "`@champion (Production)`" if promoted else "`@challenger (Staging)`",
                "inline": True,
            },
            {"name": "📉 New MAE", "value": f"`{new_mae:.4f} RPS`", "inline": True},
            {"name": "📊 Previous MAE", "value": f"`{champion_mae:.4f} RPS`", "inline": True},
            {
                "name": "⚡ Serving Reload",
                "value": "Hot-Reloaded via API" if promoted else "N/A",
                "inline": True,
            },
        ]

        logger.info("RETRAINING PROMOTION: %s (v%s) Promoted=%s", model_name, new_version, promoted)
        self._log_audit(
            "RETRAIN_PROMOTION",
            title,
            {"model": model_name, "version": new_version, "new_mae": new_mae, "promoted": promoted},
        )

        self.dispatch_discord(title, desc, color, fields)
        tg_text = (
            f"🎉 *[CT-PIPELINE] Model Lifecycle Updated*\n\n"
            f"• *Model:* `{model_name}` (v{new_version})\n"
            f"• *Validation MAE:* `{new_mae:.4f} RPS` (Improvement: `{pct_improvement:.1f}%`)\n"
            f"• *Status:* {'Promoted to @champion & Hot-Reloaded' if promoted else 'Stored as @challenger'}\n"
            f"• *MLflow Registry:* https://mlflow.titipin.me"
        )
        self.dispatch_telegram(tg_text)

    def notify_capacity_saturation(self, current_replicas: int, max_replicas: int) -> None:
        """Triggered when pods hit the maximum infrastructure boundary."""
        title = "⚡ [CAPACITY] Cluster Max Pod Bounds Reached"
        desc = f"Deployment has scaled to the maximum configured ceiling (`{current_replicas}/{max_replicas}` Pods)."
        color = 0xFFC107  # Amber

        fields = [
            {"name": "☸️ Current Pods", "value": f"`{current_replicas}`", "inline": True},
            {"name": "🛡️ Max Limit", "value": f"`{max_replicas}`", "inline": True},
            {
                "name": "💡 Note",
                "value": "Node hardware capacity stable; consider raising bounds if traffic persists.",
                "inline": False,
            },
        ]

        logger.warning("CAPACITY SATURATION: %d/%d Pods", current_replicas, max_replicas)
        self._log_audit(
            "CAPACITY_SATURATION", title, {"current": current_replicas, "max": max_replicas}
        )
        self.dispatch_discord(title, desc, color, fields)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test and trigger MLOps alerts")
    parser.add_argument("--test", action="store_true", help="Send test alert to channels")
    parser.add_argument("--discord-url", default=None)
    parser.add_argument("--telegram-token", default=None)
    parser.add_argument("--telegram-chat", default=None)
    parser.add_argument("--drift-psi", type=float, default=None)
    parser.add_argument("--p95-ms", type=float, default=None)
    args = parser.parse_args()

    dispatcher = AlertDispatcher(
        discord_url=args.discord_url,
        telegram_token=args.telegram_token,
        telegram_chat=args.telegram_chat,
    )

    if args.test:
        logger.info("Executing test alert dispatch...")
        dispatcher.notify_data_drift(
            psi_score=0.284,
            threshold=0.25,
            drift_features=["request_rate", "php_cpu_cores", "p95_latency_seconds"],
        )
        dispatcher.notify_slo_violation(p95_latency_ms=138.5, error_rate_pct=0.0)
        dispatcher.notify_retraining_promotion(
            "predictive-autoscaler", "8", new_mae=0.0241, champion_mae=0.0295, promoted=True
        )
        logger.info("Test dispatch finished. Audit logged to %s", dispatcher.audit_file)
        return

    if args.drift_psi is not None:
        dispatcher.notify_data_drift(args.drift_psi)
    elif args.p95_ms is not None:
        dispatcher.notify_slo_violation(args.p95_ms)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
