#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT=9090
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus ${PORT}:${PORT} > /dev/null 2>&1 &
PF_PID=$!

cleanup() {
  kill "$PF_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for i in {1..15}; do
  if curl -s http://127.0.0.1:${PORT}/-/healthy > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

"$REPO_ROOT/.venv/bin/python" scripts/export_dataset.py --minutes "${1:-20}" --output "${2:-src/data/raw/dataset.csv}"
