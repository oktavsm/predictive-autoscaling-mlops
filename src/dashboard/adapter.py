"""Read-only Overview inputs; missing evidence must never become healthy telemetry."""

import math
from datetime import datetime, timedelta, timezone

import requests


def number(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a measurement")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError("Expected a finite non-negative measurement")
    return result


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Observation timestamp needs a timezone")
    return result.astimezone(timezone.utc)


def normalize_decisions(rows):
    records = {}
    rejected = 0
    for row in rows:
        try:
            issued = timestamp(row["timestamp"])
            record = {
                "issued_at_utc": issued,
                "forecast_target_utc": issued + timedelta(seconds=60),
                "actual_rps": number(row["input_rps"]),
                "forecast_rps": number(row["predicted_rps_60s"]),
                "observed_replicas": number(row["current_replicas"]),
                "recommended_replicas": number(row["desired_replicas"]),
                "p95_latency_ms": number(row["input_p95_ms"]),
                "synthetic": row.get("synthetic", False) is not False,
            }
            for key in ("observed_replicas", "recommended_replicas"):
                if not record[key].is_integer():
                    raise ValueError("Replicas must be integers")
                record[key] = int(record[key])
            # First occurrence wins: the service buffer is newest-first.
            records.setdefault(issued, record)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            rejected += 1
    return sorted(records.values(), key=lambda row: row["issued_at_utc"]), rejected


def read_resource(base_url, path, expected_type, get=None):
    fetched = datetime.now(timezone.utc)
    get = get or requests.get
    try:
        response = get(f"{base_url.rstrip('/')}{path}", timeout=2.5)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, expected_type):
            raise ValueError("Unexpected response shape")
        return {"data": data, "error": None, "source": path, "fetched_at": fetched}
    except (requests.RequestException, ValueError, TypeError):
        return {
            "data": expected_type(),
            "error": "Source unavailable or invalid. Retry the read request.",
            "source": path,
            "fetched_at": fetched,
        }


def runtime_policy(health):
    try:
        capacity = number(health["target_rps_per_pod"])
        minimum = number(health["replica_bounds"]["min"])
        maximum = number(health["replica_bounds"]["max"])
        if capacity <= 0 or not minimum.is_integer() or not maximum.is_integer():
            return None
        if minimum < 1 or maximum < minimum:
            return None
        return {"capacity": capacity, "minimum": int(minimum), "maximum": int(maximum)}
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def decision_state(records, rejected, error, now, cadence):
    if error:
        return "error"
    if not records:
        return "error" if rejected else "empty"
    observed = records[-1]["issued_at_utc"]
    if observed > now + timedelta(seconds=cadence):
        return "error"
    if (now - observed).total_seconds() > max(3 * cadence, 45):
        return "stale"
    return "ready"
