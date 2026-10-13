"""Fresh container usage and a single-flight, timestamp-preserving inventory cache."""

import json
import math
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy


class SnapshotCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.value = None
        self.expires = 0.0
        self.created = 0.0

    def get(self, fetch, ttl: float = 8.0) -> dict:
        with self.lock:
            cached = self.value is not None and time.monotonic() < self.expires
            if not cached:
                value = fetch()
                self.value = deepcopy(value)
                self.created = time.monotonic()
                self.expires = self.created + ttl
            return {
                **deepcopy(self.value),
                "cached": cached,
                "cache_age_seconds": round(time.monotonic() - self.created, 3),
                "cache_ttl_seconds": ttl,
            }


def quantity(value) -> float | None:
    if value is None:
        return None
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([a-zA-Z]*)", str(value))
    if not match:
        return None
    scales = {
        "": 1,
        "n": 1e-9,
        "u": 1e-6,
        "m": 1e-3,
        "k": 1e3,
        "K": 1e3,
        "M": 1e6,
        "G": 1e9,
        "T": 1e12,
        "P": 1e15,
        "E": 1e18,
        **{s + "i": 2 ** (10 * i) for i, s in enumerate("KMGTPE", 1)},
    }
    try:
        result = float(match[1]) * scales[match[2]]
        return result if math.isfinite(result) and result >= 0 else None
    except (KeyError, OverflowError):
        return None


def query_usage(query: str) -> dict:
    base = os.getenv(
        "PROMETHEUS_URL",
        "http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090",
    ).rstrip("/")
    url = base + "/api/v1/query?" + urllib.parse.urlencode({"query": query})
    with urllib.request.urlopen(url, timeout=1.5) as response:
        data = json.load(response)
    if data.get("status") != "success" or data.get("data", {}).get("resultType") != "vector":
        raise ValueError("Prometheus vector unavailable")
    result = {}
    for row in data["data"].get("result", []):
        try:
            key = tuple(row["metric"][k] for k in ("namespace", "pod", "container"))
            stamp, value = row["value"]
            numeric = float(value)
            if math.isfinite(numeric) and numeric >= 0 and abs(time.time() - float(stamp)) <= 45:
                result[key] = numeric
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return result


def attach_usage(snapshot: dict) -> dict:
    selector = '{namespace=~"mlops|monitoring|titipin",container!="",container!="POD",image!=""}'
    grouping = "namespace,pod,container"
    cpu = "container_cpu_usage_seconds_total" + selector
    memory = "container_memory_working_set_bytes" + selector
    queries = {
        "cpu_cores": f"max by ({grouping}) (rate({cpu}[2m])) and on ({grouping}) (max by ({grouping}) (timestamp({cpu})) > time()-45)",
        "memory_bytes": f"max by ({grouping}) ({memory}) and on ({grouping}) (max by ({grouping}) (timestamp({memory})) > time()-45)",
    }
    metrics, errors = {}, []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {key: pool.submit(query_usage, query) for key, query in queries.items()}
        for key, future in futures.items():
            try:
                metrics[key] = future.result()
            except Exception:
                metrics[key] = {}
                errors.append(key)
    for pod in snapshot["pods"]:
        containers = pod["container_details"]
        for container in containers:
            key = (pod["namespace"], pod["name"], container["name"])
            container["usage"] = {name: values.get(key) for name, values in metrics.items()}
        usage = {}
        for name, resource in [("cpu_cores", "cpu"), ("memory_bytes", "memory")]:
            values = [c["usage"][name] for c in containers]
            covered = sum(v is not None for v in values)
            usage[name] = sum(values) if containers and covered == len(containers) else None
            usage[name + "_coverage"] = f"{covered}/{len(containers)}"
            limits = [quantity(c.get("limits", {}).get(resource)) for c in containers]
            limit = (
                sum(limits) if containers and all(v is not None and v > 0 for v in limits) else None
            )
            usage[resource + "_limit"] = limit
            usage[resource + "_limit_pct"] = (
                usage[name] / limit * 100 if limit and usage[name] is not None else None
            )
        pod["usage"] = usage
    snapshot["usage_source"] = {
        "source": "Prometheus /api/v1/query",
        "cpu_window_seconds": 120,
        "max_sample_age_seconds": 45,
        "status": "UNAVAILABLE"
        if not any(metrics.values())
        else "PARTIAL"
        if errors or not all(metrics.values())
        else "AVAILABLE",
        "unavailable_queries": errors,
        "queried_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return snapshot
