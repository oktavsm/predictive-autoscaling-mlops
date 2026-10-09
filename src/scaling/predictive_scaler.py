"""
Predictive Autoscaler Controller for Kubernetes Workloads.
Continuously queries Prometheus telemetry, computes next-minute workload forecasts
via the Inference API (or champion model), and proactively adjusts Kubernetes deployment
replicas before traffic spikes saturate the system.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any, Dict, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("predictive-scaler")


@dataclass
class TelemetrySnapshot:
    timestamp: float
    request_rate: float
    php_cpu_cores: float
    p95_latency_seconds: float
    php_memory_mb: float
    current_replicas: int


@dataclass
class ScalerMetrics:
    current_replicas: int = 1
    desired_replicas: int = 1
    predicted_workload_rps: float = 0.0
    cycles_total: int = 0
    scale_up_total: int = 0
    scale_down_total: int = 0
    last_scale_time: float = 0.0
    last_decision_reason: str = "init"


class MetricsHandler(BaseHTTPRequestHandler):
    """Exposes Prometheus metrics for the predictive autoscaler controller."""

    metrics_ref: Optional[ScalerMetrics] = None

    def do_GET(self) -> None:
        if self.path == "/healthz" or self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            return

        if self.path == "/metrics":
            m = self.metrics_ref or ScalerMetrics()
            body = (
                "# HELP predictive_scaler_current_replicas Current active replicas managed by autoscaler\n"
                "# TYPE predictive_scaler_current_replicas gauge\n"
                f"predictive_scaler_current_replicas {m.current_replicas}\n"
                "# HELP predictive_scaler_desired_replicas Desired replicas calculated by predictive model\n"
                "# TYPE predictive_scaler_desired_replicas gauge\n"
                f"predictive_scaler_desired_replicas {m.desired_replicas}\n"
                "# HELP predictive_scaler_predicted_workload_rps Predicted workload (RPS) 60 seconds ahead\n"
                "# TYPE predictive_scaler_predicted_workload_rps gauge\n"
                f"predictive_scaler_predicted_workload_rps {m.predicted_workload_rps:.4f}\n"
                "# HELP predictive_scaler_cycles_total Total scaling evaluation cycles executed\n"
                "# TYPE predictive_scaler_cycles_total counter\n"
                f"predictive_scaler_cycles_total {m.cycles_total}\n"
                "# HELP predictive_scaler_scale_events_total Total scale actions taken\n"
                "# TYPE predictive_scaler_scale_events_total counter\n"
                f'predictive_scaler_scale_events_total{{action="scale_up"}} {m.scale_up_total}\n'
                f'predictive_scaler_scale_events_total{{action="scale_down"}} {m.scale_down_total}\n'
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy HTTP access logs
        pass


class PrometheusClient:
    """Queries operational Prometheus instance."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def query_instant(self, query: str) -> Optional[float]:
        url = f"{self.base_url}/api/v1/query?query=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "success":
                    result = data.get("data", {}).get("result", [])
                    if result:
                        val = result[0].get("value", [0, "0"])[1]
                        return float(val)
        except Exception as exc:
            logger.debug("Prometheus query failed for %s: %s", query, exc)
        return None

    def fetch_telemetry(self, target_namespace: str = "titipin") -> TelemetrySnapshot:
        # 1. Request rate from Caddy or Nginx
        rps_query = 'sum(rate(caddy_http_requests_total{host=~"api.titipin.me.*"}[1m])) or sum(rate(nginx_http_requests_total[1m]))'
        rps = self.query_instant(rps_query)
        if rps is None or rps < 0:
            rps = 0.0

        # 2. CPU cores
        cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{target_namespace}", container=~"laravel.*|php.*"}}[1m]))'
        cpu = self.query_instant(cpu_query)
        if cpu is None:
            cpu = 0.05

        # 3. P95 latency (seconds)
        lat_query = 'histogram_quantile(0.95, sum by (le) (rate(caddy_http_request_duration_seconds_bucket{host=~"api.titipin.me.*"}[1m])))'
        lat = self.query_instant(lat_query)
        if lat is None or lat != lat:  # check NaN
            lat = 0.025

        # 4. Memory MB
        mem_query = f'sum(container_memory_working_set_bytes{{namespace="{target_namespace}", container=~"laravel.*|php.*"}}) / 1024 / 1024'
        mem = self.query_instant(mem_query)
        if mem is None:
            mem = 128.0

        return TelemetrySnapshot(
            timestamp=time.time(),
            request_rate=round(float(rps), 3),
            php_cpu_cores=round(float(cpu), 4),
            p95_latency_seconds=round(float(lat), 4),
            php_memory_mb=round(float(mem), 2),
            current_replicas=1,
        )


class KubernetesClient:
    """Manages deployment scaling via Kubernetes In-Cluster REST API or local kubectl fallback."""

    def __init__(self, in_cluster: Optional[bool] = None):
        self.sa_token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        self.sa_ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        self.k8s_api_host = os.getenv("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
        self.k8s_api_port = os.getenv("KUBERNETES_SERVICE_PORT", "443")

        if in_cluster is None:
            self.in_cluster = os.path.exists(self.sa_token_path)
        else:
            self.in_cluster = in_cluster

        self.token = ""
        if self.in_cluster:
            try:
                with open(self.sa_token_path, "r", encoding="utf-8") as f:
                    self.token = f.read().strip()
                logger.info(
                    "Kubernetes client initialized in-cluster (Host: %s:%s)",
                    self.k8s_api_host,
                    self.k8s_api_port,
                )
            except Exception as e:
                logger.warning(
                    "Failed to read ServiceAccount token: %s. Falling back to kubectl CLI.", e
                )
                self.in_cluster = False
        else:
            logger.info("Kubernetes client initialized with local kubectl fallback.")

    def get_replicas(self, namespace: str, deployment: str) -> int:
        if self.in_cluster:
            url = f"https://{self.k8s_api_host}:{self.k8s_api_port}/apis/apps/v1/namespaces/{namespace}/deployments/{deployment}/scale"
            import ssl

            ctx = ssl.create_default_context(
                cafile=self.sa_ca_path if os.path.exists(self.sa_ca_path) else None
            )
            ctx.check_hostname = False
            ctx.verify_mode = (
                ssl.CERT_NONE if not os.path.exists(self.sa_ca_path) else ssl.CERT_REQUIRED
            )
            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=5.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return int(data.get("spec", {}).get("replicas", 1))
            except Exception as e:
                logger.warning("In-cluster get scale failed: %s", e)

        # Fallback using kubectl
        try:
            cmd = [
                "kubectl",
                "get",
                f"deployment/{deployment}",
                "-n",
                namespace,
                "-o",
                "jsonpath={.spec.replicas}",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            val = res.stdout.strip()
            return int(val) if val else 1
        except Exception as e:
            logger.debug("kubectl get scale error: %s", e)
            return 1

    def scale_deployment(self, namespace: str, deployment: str, replicas: int) -> bool:
        if self.in_cluster:
            url = f"https://{self.k8s_api_host}:{self.k8s_api_port}/apis/apps/v1/namespaces/{namespace}/deployments/{deployment}/scale"
            import ssl

            ctx = ssl.create_default_context(
                cafile=self.sa_ca_path if os.path.exists(self.sa_ca_path) else None
            )
            ctx.check_hostname = False
            ctx.verify_mode = (
                ssl.CERT_NONE if not os.path.exists(self.sa_ca_path) else ssl.CERT_REQUIRED
            )
            patch_body = json.dumps({"spec": {"replicas": replicas}}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=patch_body,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/merge-patch+json",
                    "Accept": "application/json",
                },
                method="PATCH",
            )
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=5.0) as resp:
                    if resp.status in (200, 201):
                        return True
            except Exception as e:
                logger.warning("In-cluster scale patch failed: %s", e)

        # Fallback using kubectl
        try:
            cmd = [
                "kubectl",
                "scale",
                f"deployment/{deployment}",
                f"--replicas={replicas}",
                "-n",
                namespace,
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            return True
        except Exception as e:
            logger.error("kubectl scale command failed: %s", e)
            return False


class PredictiveScalerController:
    """Main control loop coordinating telemetry, model inference, and proactive scaling."""

    def __init__(
        self,
        prometheus_url: str = "http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090",
        inference_url: str = "http://mlops-inference-svc.mlops.svc.cluster.local:8000",
        target_namespace: str = "titipin",
        target_deployment: str = "laravel-backend",
        min_replicas: int = 1,
        max_replicas: int = 4,
        cooldown_seconds: int = 60,
        dry_run: bool = False,
    ):
        self.prometheus = PrometheusClient(prometheus_url)
        self.inference_url = inference_url.rstrip("/")
        self.target_namespace = target_namespace
        self.target_deployment = target_deployment
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.cooldown_seconds = cooldown_seconds
        self.dry_run = dry_run

        self.k8s = KubernetesClient()
        self.metrics = ScalerMetrics()
        self.last_scale_time: float = 0.0

    def query_inference_decision(self, snapshot: TelemetrySnapshot) -> Tuple[float, int, str]:
        """Queries the inference service endpoint /scale-decision."""
        url = f"{self.inference_url}/scale-decision"
        payload = {
            "request_rate": snapshot.request_rate,
            "php_cpu_cores": snapshot.php_cpu_cores,
            "p95_latency_seconds": snapshot.p95_latency_seconds,
            "php_memory_mb": snapshot.php_memory_mb,
            "current_replicas": snapshot.current_replicas,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pred_rps = float(data.get("predicted_workload_rps_60s", snapshot.request_rate))
                desired_replicas = int(
                    data.get("target_replicas", data.get("recommended_replicas", 1))
                )
                action = str(data.get("action", "maintain"))
                return pred_rps, desired_replicas, action
        except Exception as exc:
            logger.warning("Inference API query failed (%s). Using heuristic fallback.", exc)
            # Safe predictive fallback calculation
            pred_rps = snapshot.request_rate * 1.15
            if pred_rps > 30.0:
                desired = 4
            elif pred_rps > 18.0:
                desired = 3
            elif pred_rps > 8.0:
                desired = 2
            else:
                desired = 1
            return pred_rps, desired, "heuristic_fallback"

    def execute_cycle(self) -> Dict[str, Any]:
        """Runs one decision cycle."""
        self.metrics.cycles_total += 1
        current_reps = self.k8s.get_replicas(self.target_namespace, self.target_deployment)
        self.metrics.current_replicas = current_reps

        # 1. Ingest telemetry
        snap = self.prometheus.fetch_telemetry(self.target_namespace)
        snap.current_replicas = current_reps

        # 2. Query inference
        pred_rps, desired_reps, action_hint = self.query_inference_decision(snap)
        desired_reps = max(self.min_replicas, min(self.max_replicas, desired_reps))
        self.metrics.desired_replicas = desired_reps
        self.metrics.predicted_workload_rps = pred_rps

        now = time.time()
        decision = "MAINTAIN"
        scaled = False

        if desired_reps > current_reps:
            # Scale UP immediately! Proactive protection against lag.
            decision = f"SCALE_UP ({current_reps} -> {desired_reps})"
            if not self.dry_run:
                scaled = self.k8s.scale_deployment(
                    self.target_namespace, self.target_deployment, desired_reps
                )
                if scaled:
                    self.metrics.scale_up_total += 1
                    self.metrics.current_replicas = desired_reps
                    self.last_scale_time = now
            else:
                scaled = True
        elif desired_reps < current_reps:
            # Scale DOWN with cooldown window to prevent oscillation
            elapsed = now - self.last_scale_time
            if elapsed >= self.cooldown_seconds:
                decision = f"SCALE_DOWN ({current_reps} -> {desired_reps})"
                if not self.dry_run:
                    scaled = self.k8s.scale_deployment(
                        self.target_namespace, self.target_deployment, desired_reps
                    )
                    if scaled:
                        self.metrics.scale_down_total += 1
                        self.metrics.current_replicas = desired_reps
                        self.last_scale_time = now
                else:
                    scaled = True
            else:
                decision = f"HOLD_COOLDOWN (Remaining: {int(self.cooldown_seconds - elapsed)}s)"
        else:
            decision = f"MAINTAIN ({current_reps} replicas optimal)"

        self.metrics.last_decision_reason = decision

        if scaled and not self.dry_run and current_reps != desired_reps:
            try:
                event_payload = json.dumps(
                    {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "action": "SCALE_UP" if desired_reps > current_reps else "SCALE_DOWN",
                        "from_replicas": current_reps,
                        "to_replicas": desired_reps,
                        "predicted_rps": round(pred_rps, 2),
                        "reason": decision,
                    }
                ).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.inference_url}/scaling/action-record",
                    data=event_payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=1.0)
            except Exception:
                pass

        log_payload = {
            "cycle": self.metrics.cycles_total,
            "target": f"{self.target_namespace}/{self.target_deployment}",
            "current_replicas": current_reps,
            "predicted_rps_60s": round(pred_rps, 2),
            "desired_replicas": desired_reps,
            "decision": decision,
            "scaled": scaled,
            "dry_run": self.dry_run,
        }
        logger.info("Cycle %d Result: %s", self.metrics.cycles_total, json.dumps(log_payload))
        return log_payload


def start_metrics_server(port: int, metrics: ScalerMetrics) -> HTTPServer:
    MetricsHandler.metrics_ref = metrics
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info("Metrics exporter listening on http://0.0.0.0:%d/metrics", port)
    return server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predictive Autoscaler Controller")
    parser.add_argument(
        "--prometheus-url",
        default=os.getenv(
            "PROMETHEUS_URL",
            "http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090",
        ),
    )
    parser.add_argument(
        "--inference-url",
        default=os.getenv(
            "INFERENCE_URL", "http://mlops-inference-svc.mlops.svc.cluster.local:8000"
        ),
    )
    parser.add_argument("--target-namespace", default=os.getenv("TARGET_NAMESPACE", "titipin"))
    parser.add_argument(
        "--target-deployment", default=os.getenv("TARGET_DEPLOYMENT", "laravel-backend")
    )
    parser.add_argument(
        "--interval", type=int, default=int(os.getenv("SCALE_INTERVAL_SECONDS", "15"))
    )
    parser.add_argument("--min-replicas", type=int, default=int(os.getenv("MIN_REPLICAS", "1")))
    parser.add_argument("--max-replicas", type=int, default=int(os.getenv("MAX_REPLICAS", "4")))
    parser.add_argument(
        "--cooldown-seconds", type=int, default=int(os.getenv("COOLDOWN_SECONDS", "60"))
    )
    parser.add_argument("--port", type=int, default=int(os.getenv("EXPORTER_PORT", "9102")))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.getenv("DRY_RUN", "false").lower() in ("true", "1"),
    )
    parser.add_argument("--once", action="store_true", help="Execute single cycle and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("Starting Predictive Autoscaler Controller...")
    logger.info(
        "Config: Prometheus=%s, Inference=%s, Target=%s/%s, Interval=%ds",
        args.prometheus_url,
        args.inference_url,
        args.target_namespace,
        args.target_deployment,
        args.interval,
    )

    controller = PredictiveScalerController(
        prometheus_url=args.prometheus_url,
        inference_url=args.inference_url,
        target_namespace=args.target_namespace,
        target_deployment=args.target_deployment,
        min_replicas=args.min_replicas,
        max_replicas=args.max_replicas,
        cooldown_seconds=args.cooldown_seconds,
        dry_run=args.dry_run,
    )

    if not args.once:
        start_metrics_server(args.port, controller.metrics)

    if args.once:
        res = controller.execute_cycle()
        print(json.dumps(res, indent=2))
        return

    try:
        while True:
            controller.execute_cycle()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Autoscaler controller stopped by user.")


if __name__ == "__main__":
    main()
