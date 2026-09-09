#!/usr/bin/env bash
set -e

# =============================================================================
# Automated Workload Sequence Runner
# Runs multiple k6 scenarios with cooldown periods and exports Prometheus datasets
# =============================================================================

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env.k6 ]; then
  echo "[!] .env.k6 file not found! Copy .env.k6.example to .env.k6 first."
  exit 1
fi

source .env.k6
export PATH="$HOME/.local/bin:$PATH"

K6_BIN=$(which k6 || echo "$HOME/.local/bin/k6")
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

wait_for_cooldown() {
  local max_wait=180
  local waited=0
  echo ""
  echo ">>> [Cooldown] Waiting for cluster pods to stabilize (target: 1 replica)..."
  while [ $waited -lt $max_wait ]; do
    local replicas
    replicas=$(kubectl get deployment laravel-backend -n titipin -o jsonpath='{.status.replicas}' 2>/dev/null || echo "1")
    if [ "$replicas" -le 1 ]; then
      echo ">>> [Cooldown] Pods cooled down to $replicas replica. Cluster ready!"
      sleep 15
      return 0
    fi
    echo "    Current replicas: $replicas. Waiting 15s... ($waited/$max_wait s)"
    sleep 15
    waited=$((waited + 15))
  done
  echo ">>> [Cooldown] Wait timeout reached. Proceeding anyway..."
}

export_metrics() {
  local minutes=$1
  local output_path=$2
  echo ""
  echo ">>> [Exporter] Exporting last ${minutes}m of Prometheus metrics to ${output_path}..."
  
  kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 > /dev/null 2>&1 &
  local pf_pid=$!
  
  for i in {1..10}; do
    if curl -s http://127.0.0.1:9090/-/healthy > /dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  
  $PYTHON_BIN scripts/export_dataset.py --minutes "$minutes" --output "$output_path"
  kill "$pf_pid" 2>/dev/null || true
}

echo "================================================================="
echo "  STARTING AUTOMATED MLOPS WORKLOAD GENERATION SEQUENCE"
echo "  Target URL: $BASE_URL"
echo "================================================================="

# Wait for current state to be clean
wait_for_cooldown

# -----------------------------------------------------------------------------
# Scenario 1: Periodic (Repeating waves — primary time-series ML scenario)
# -----------------------------------------------------------------------------
echo ""
echo "================================================================="
echo "  [1/2] RUNNING SCENARIO: PERIODIC (workloads/k6/scenarios/periodic.js)"
echo "================================================================="
RUN_ID="periodic-run-001" $K6_BIN run workloads/k6/scenarios/periodic.js
export_metrics 15 "src/data/raw/periodic_run_001.csv"

# Cooldown between scenarios
wait_for_cooldown

# -----------------------------------------------------------------------------
# Scenario 2: Gradual (Step-by-step ramp-up)
# -----------------------------------------------------------------------------
echo ""
echo "================================================================="
echo "  [2/2] RUNNING SCENARIO: GRADUAL (workloads/k6/scenarios/gradual.js)"
echo "================================================================="
RUN_ID="gradual-run-001" $K6_BIN run workloads/k6/scenarios/gradual.js
export_metrics 12 "src/data/raw/gradual_run_001.csv"

# -----------------------------------------------------------------------------
# Final Step: Merge all datasets into Master Training Dataset
# -----------------------------------------------------------------------------
echo ""
echo "================================================================="
echo "  MERGING ALL DATASETS INTO MASTER DATASET"
echo "================================================================="
$PYTHON_BIN scripts/merge_datasets.py

echo ""
echo "================================================================="
echo "  ALL SCENARIOS COMPLETED SUCCESSFULLY!"
echo "  Master training dataset is ready at src/data/raw/master_training_dataset.csv"
echo "================================================================="
