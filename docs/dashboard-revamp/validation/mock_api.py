import json
import math
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

state = "ready"
calls = []
lifecycle_active = False
lifecycle_completed = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        global lifecycle_active, lifecycle_completed
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        calls.append({"method": "POST", "path": self.path, "body": body})
        if state == "write_error":
            self.send_response(503)
            self.end_headers()
            return
        if self.path in ("/monitoring/retrain/trigger", "/monitoring/autonomous-scenario/start"):
            lifecycle_active = True
            lifecycle_completed = False
            value = {"status": "ACCEPTED", "operation_id": "qa-operation"}
        elif self.path == "/monitoring/autonomous-scenario/stop":
            lifecycle_active = False
            value = {"status": "ok", "stage": "STOPPED"}
        elif self.path == "/workload/trigger":
            value = {"status": "ok", "override_state": body.get("state")}
        else:
            value = {
                "status": "SUCCESS",
                "predicted_workload_rps_60s": 35,
                "recommended_replicas": 4,
                "inference_latency_ms": 1.7,
            }
        blob = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self):
        global state, lifecycle_active, lifecycle_completed
        path = urlparse(self.path).path
        if path == "/__state":
            state = parse_qs(urlparse(self.path).query).get("value", ["ready"])[0]
            if state == "completed":
                lifecycle_active = False
                lifecycle_completed = True
            else:
                lifecycle_active = False
                lifecycle_completed = False
            calls.clear()
            value = {"state": state}
        elif path == "/__calls":
            value = calls
        else:
            calls.append({"method": "GET", "path": path})
            now = datetime.now(timezone.utc)
            start = now - timedelta(minutes=14, seconds=45)
            rows = [
                {
                    "timestamp": (start + timedelta(seconds=i * 15)).isoformat(),
                    "input_rps": round(60 + i * 2 + math.sin(i / 4) * 35, 2),
                    "predicted_rps_60s": round(70 + i * 2.5, 2),
                    "current_replicas": 2 if i < 16 else (4 if i < 40 else 3),
                    "desired_replicas": 4,
                    "input_p95_ms": 23.9 + i * 0.2,
                    "input_cpu": 0.2,
                    "latency_ms": 12.3,
                    "action": "SCALE_UP",
                    "synthetic": True,
                }
                for i in range(60)
            ][::-1]
            data = {
                "/health": {
                    "status": "healthy",
                    "model_ready": True,
                    "model_version": "qa-v7",
                    "model_name": "QA model",
                    "model_alias": "champion",
                    "model_algorithm": "QA fixture model",
                    "target_rps_per_pod": 65,
                    "replica_bounds": {"min": 1, "max": 8},
                    "load_time_ms": 18.4,
                },
                "/scaling/decisions": rows,
                "/telemetry/live-sample": rows[:5],
                "/scaling/actions": [
                    {
                        "timestamp": (now - timedelta(minutes=2)).isoformat(),
                        "action": "SCALE_DOWN",
                        "from_replicas": 4,
                        "to_replicas": 3,
                        "status": "applied",
                        "synthetic": True,
                    }
                ],
                "/operations/audit": {
                    "retraining": {
                        "latest": {
                            "version": "qa-v7",
                            "algorithm": "QA fixture model",
                            "val_mae": "0.4 req/s",
                        }
                    },
                    "last_ingestion": {
                        "records_count": 60,
                        "window_minutes": 15,
                        "status": "synthetic QA",
                        "md5": "synthetic",
                        "timestamp": now.isoformat(),
                    },
                },
                "/monitoring/drift": {"psi_score": 0.08, "threshold": 0.2, "evaluated_cycles": 60},
                "/workload/status": {
                    "daemon_alive": True,
                    "daemon_current_state": "STEADY_NORMAL",
                    "daemon_vus": 6,
                    "last_heartbeat_seconds_ago": 2,
                    "daemon_remaining_s": 450,
                    "override_state": None,
                },
                "/monitoring/autonomous-status": {
                    "active": lifecycle_active,
                    "stage": "COMPLETED"
                    if lifecycle_completed
                    else ("TRAINING" if lifecycle_active else "IDLE"),
                    "stage_index": 5 if lifecycle_completed else 3,
                    "progress_pct": 100 if lifecycle_completed else 60,
                    "champion_version": "qa-v8",
                    "quality_gate": "PASSED",
                    "hot_reload": "SUCCESS",
                    "timeline": [],
                },
                "/cluster/status": {
                    "timestamp": now.isoformat(),
                    "scope": ["mlops", "monitoring", "titipin"],
                    "source": "Synthetic QA Kubernetes fixture",
                    "nodes": [
                        {
                            "name": name,
                            "role": "control-plane" if i == 0 else "worker",
                            "ready": i != 2,
                            "capacity": {"cpu": "2", "memory": "4000000Ki"},
                            "allocatable": {"cpu": "1900m", "memory": "3500000Ki", "pods": "110"},
                            "info": {
                                "kubeletVersion": "v1.33-QA",
                                "osImage": "QA Linux",
                                "containerRuntimeVersion": "containerd://QA",
                            },
                            "conditions": [
                                {
                                    "type": "Ready",
                                    "status": "True" if i != 2 else "False",
                                    "reason": "QACondition",
                                }
                            ],
                        }
                        for i, name in enumerate(["qa-cp", "qa-worker-1", "qa-worker-2"])
                    ],
                    "pods": [
                        {
                            "name": name,
                            "namespace": ns,
                            "node": node,
                            "phase": phase,
                            "ready": ready,
                            "containers": 2 if "inference" in name else 1,
                            "restarts": 3 if not ready else 0,
                            "created_at": now.isoformat(),
                            "labels": {"app": "mlops-inference" if "inference" in name else name},
                            "owner": [
                                {
                                    "kind": "Job" if phase == "Succeeded" else "ReplicaSet",
                                    "name": "qa-owner",
                                }
                            ],
                            "container_details": [
                                {
                                    "name": "qa-container",
                                    "ready": bool(ready),
                                    "requests": {"cpu": "100m", "memory": "64Mi"},
                                    "limits": {"cpu": "1", "memory": "256Mi"},
                                    "state": {"running": {}}
                                    if ready
                                    else {"waiting": {"reason": "CrashLoopBackOff"}},
                                }
                            ],
                        }
                        for name, ns, node, phase, ready in [
                            ("mlops-inference-qa", "mlops", "qa-worker-1", "Running", 2),
                            ("mlops-dashboard-qa", "mlops", "qa-worker-1", "Running", 1),
                            ("mlops-mlflow-qa", "mlops", "qa-worker-1", "Running", 1),
                            ("drift-retrain-qa", "mlops", "qa-worker-1", "Succeeded", 0),
                            ("laravel-backend-qa", "titipin", "qa-worker-2", "Running", 0),
                            ("minio-qa", "titipin", "qa-cp", "Running", 1),
                            ("monitoring-grafana-qa", "monitoring", "qa-cp", "Running", 1),
                            (
                                "monitoring-kube-prometheus-prometheus-qa",
                                "monitoring",
                                "qa-cp",
                                "Running",
                                1,
                            ),
                            (
                                "<img src=x onerror=window.clusterInjected=true>",
                                "mlops",
                                None,
                                "Pending",
                                0,
                            ),
                            *[
                                ("qa-extra-" + str(i), "mlops", "qa-worker-1", "Running", 1)
                                for i in range(5)
                            ],
                        ]
                    ],
                    "services": [
                        {
                            "name": "mlops-inference-svc",
                            "namespace": "mlops",
                            "type": "NodePort",
                            "selector": {"app": "mlops-inference"},
                            "ports": [
                                {
                                    "name": "http",
                                    "port": 8000,
                                    "targetPort": 8000,
                                    "nodePort": 30800,
                                    "protocol": "TCP",
                                }
                            ],
                        }
                    ],
                },
            }
            if state == "cluster_empty":
                data["/cluster/status"] = {
                    "nodes": [],
                    "pods": [],
                    "services": [],
                    "source": "Synthetic QA empty inventory",
                }
            if state == "cluster_error" and path == "/cluster/status":
                self.send_response(503)
                self.end_headers()
                return
            if state == "empty":
                data["/scaling/decisions"] = []
                data["/scaling/actions"] = []
            if state == "stale":
                for r in rows:
                    r["timestamp"] = "2020-01-01T00:00:00Z"
            if state == "invalid":
                data["/scaling/decisions"] = [{"input_rps": None}]
                data["/health"] = {"model_ready": False}
            if state == "error" and path == "/scaling/decisions":
                self.send_response(503)
                self.end_headers()
                return
            if state == "partial" and path == "/health":
                self.send_response(503)
                self.end_headers()
                return
            value = data.get(path, {})
        blob = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)


HTTPServer(("127.0.0.1", 18766), Handler).serve_forever()
