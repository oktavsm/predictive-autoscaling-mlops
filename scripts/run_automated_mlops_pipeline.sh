#!/usr/bin/env bash
# ==============================================================================
# Master Automated End-to-End MLOps Simulation Script
# ==============================================================================
# Menjalankan seluruh siklus MLOps secara berurutan (Sequential & Hands-Free):
#   Tahap 1: Baseline Normal Workload (Trafik stabil, 1 replika pod)
#   Tahap 2: Heavy Traffic Surge & Predictive Autoscaling (Lonjakan ~100 RPS, scale ke 4 pod)
#   Tahap 3: Large Data Drift Injection & DVC Storage Versioning
#   Tahap 4: Automated Continuous Retraining & MLflow Champion Promotion
#   Tahap 5: Closed-Loop Live Workload Validation pada Model Champion Baru
#
# Cara Penggunaan:
#   bash scripts/run_automated_mlops_pipeline.sh
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

TARGET_API="https://api.titipin.me"
INFERENCE_API="https://model.titipin.me"
MLFLOW_URL="https://mlflow.titipin.me"
GRAFANA_URL="https://grafana.titipin.me"

TIMESTAMP_START=$(date +%s)
TIME_STR_START=$(date +"%Y-%m-%d %H:%M:%S WIB")

echo -e "${CYAN}${BOLD}"
echo "================================================================================"
echo "          END-TO-END MLOPS AUTOMATED WORKFLOW & SCALING SIMULATION             "
echo "================================================================================"
echo -e "${NC}"
echo -e "Waktu Mulai        : ${BOLD}${TIME_STR_START}${NC}"
echo -e "Target Backend API : ${GREEN}${TARGET_API}${NC}"
echo -e "Inference Engine   : ${GREEN}${INFERENCE_API}${NC}"
echo -e "MLflow Registry    : ${GREEN}${MLFLOW_URL}${NC}"
echo -e "Grafana Dashboard  : ${GREEN}${GRAFANA_URL}${NC}"
echo ""

# ------------------------------------------------------------------------------
# TAHAP 1: Baseline Normal Workload (30s)
# ------------------------------------------------------------------------------
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}${BOLD}[TAHAP 1/5] Menguji Kondisi Trafik Normal (Baseline Steady-State)...${NC}"
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Mengirimkan 5 Virtual Users selama 30 detik (~12 RPS steady traffic)..."

k6 run --vus 5 --duration 30s -e TARGET_URL="${TARGET_API}" workloads/k6/scenarios/spike.js > /dev/null 2>&1

echo -e "✓ Uji beban baseline selesai."
REPLICAS_BASE=$(kubectl get deploy laravel-backend -n titipin -o jsonpath='{.spec.replicas}')
echo -e "Status Pod Backend : ${GREEN}${REPLICAS_BASE} pod aktif${NC}"
LATEST_SCALER_LOG=$(kubectl logs -n mlops deploy/mlops-inference -c predictive-scaler --tail=1)
echo -e "Log Kontroler      : ${YELLOW}${LATEST_SCALER_LOG}${NC}"
echo ""

# ------------------------------------------------------------------------------
# TAHAP 2: Heavy Workload Surge & Predictive Scaling (60s)
# ------------------------------------------------------------------------------
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}${BOLD}[TAHAP 2/5] Memicu Lonjakan Trafik Masif (Predictive Autoscaling Active)...${NC}"
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Mengirimkan 60 Virtual Users secara agresif (~80-100 RPS) ke backend..."

# Jalankan k6 di background agar kita bisa live-monitor penskalaan pod
k6 run --vus 60 --duration 60s -e TARGET_URL="${TARGET_API}" workloads/k6/scenarios/spike.js > /dev/null 2>&1 &
K6_PID=$!

echo -e "Memantau reaksi Predictive Scaler secara real-time..."
PEAK_REPLICAS=1
for i in {1..8}; do
    sleep 7
    CURR_REPS=$(kubectl get deploy laravel-backend -n titipin -o jsonpath='{.spec.replicas}')
    if [ "$CURR_REPS" -gt "$PEAK_REPLICAS" ]; then
        PEAK_REPLICAS=$CURR_REPS
    fi
    echo -e "  [+$(($i * 7))s] Pod Replicas: ${BOLD}${CURR_REPS}${NC} | Scaler Log: $(kubectl logs -n mlops deploy/mlops-inference -c predictive-scaler --tail=1 | grep -o '{"cycle".*}')"
done

wait $K6_PID
echo -e "✓ Puncak trafik selesai. Replika puncak tercatat: ${GREEN}${PEAK_REPLICAS} Pods${NC}"
echo ""

# ------------------------------------------------------------------------------
# TAHAP 3: Large Data Drift Generation & DVC Storage Sync
# ------------------------------------------------------------------------------
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}${BOLD}[TAHAP 3/5] Injeksi Data Drift Masif & Versioning DVC MinIO...${NC}"
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Menghasilkan dataset telemetri flash-sale (traffic multiplier 3.5x, CPU surge)..."

python3 -c "
import csv, random

with open('data/processed/metrics_demo_processed.csv', 'r') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

drifted_rows = []
for r in rows:
    new_r = dict(r)
    for col in ['request_rate', 'rps_lag1', 'rps_lag2', 'rps_roll_mean_30s', 'rps_roll_mean_60s', 'target_rps_60s']:
        if r[col]:
            val = float(r[col]) * 3.5 + random.uniform(3.0, 7.0)
            new_r[col] = f'{val:.4f}'
    for col in ['php_cpu_cores', 'cpu_lag1', 'cpu_lag2']:
        if r[col]:
            val = float(r[col]) * 2.8 + random.uniform(0.08, 0.18)
            new_r[col] = f'{val:.4f}'
    if r['p95_latency_seconds']:
        val = float(r['p95_latency_seconds']) * 2.5
        new_r['p95_latency_seconds'] = f'{val:.4f}'
    drifted_rows.append(new_r)

with open('data/processed/metrics_flashsale_drifted.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(drifted_rows)
"

# Menjalankan evaluasi drift (PSI Score)
python3 scripts/calculate_drift.py data/processed/metrics_demo_processed.csv data/processed/metrics_flashsale_drifted.csv

# Mengunggah snapshot dataset ke MinIO Object Storage
echo -e "Sinkronisasi artefak dataset ke MinIO S3 (s3://mlops-dvc)..."
MINIO_POD=$(kubectl get pods -n titipin -l app=minio -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n titipin "${MINIO_POD}" -- mkdir -p /data/mlops-dvc/processed > /dev/null 2>&1 || true
kubectl cp data/processed/metrics_flashsale_drifted.csv "titipin/${MINIO_POD}:/data/mlops-dvc/processed/metrics_flashsale_drifted.csv" > /dev/null 2>&1
NEW_MD5=$(md5sum data/processed/metrics_flashsale_drifted.csv | cut -d' ' -f1)
echo -e "✓ Dataset terunggah ke MinIO. Hash DVC MD5: ${BOLD}${NEW_MD5}${NC}"
echo ""

# ------------------------------------------------------------------------------
# TAHAP 4: Automated Continuous Retraining & MLflow Promotion
# ------------------------------------------------------------------------------
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}${BOLD}[TAHAP 4/5] Memicu Continuous Retraining Pipeline di Klaster K3s...${NC}"
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Memperbarui ConfigMap mlops-training-data dengan dataset baru..."
kubectl create configmap mlops-training-data \
  --from-file=metrics_demo_processed.csv=data/processed/metrics_flashsale_drifted.csv \
  -n mlops --dry-run=client -o yaml | kubectl apply -f - > /dev/null 2>&1

JOB_NAME="auto-retrain-$(date +%s)"
echo -e "Meluncurkan Job Retraining Kubernetes: ${BOLD}${JOB_NAME}${NC}..."
kubectl create job --from=cronjob/mlops-continuous-training "${JOB_NAME}" -n mlops > /dev/null 2>&1

echo -e "Menunggu pipeline pelatihan (multi-model training, evaluasi, logging MLflow)..."
kubectl wait --for=condition=complete "job/${JOB_NAME}" -n mlops --timeout=90s > /dev/null 2>&1

echo -e "${GREEN}✓ Job Pelatihan selesai dengan sukses!${NC}"
echo ""
echo -e "${BOLD}Status Model Registry Terbaru di MLflow:${NC}"
curl -s "https://mlflow.titipin.me/api/2.0/mlflow/registered-models/get?name=predictive-autoscaler" | python3 -c "
import json, sys
d = json.load(sys.stdin)['registered_model']
print(f'Model Name: {d[\"name\"]}')
print(f'Active Aliases: {dict([(a[\"alias\"], \"v\"+str(a[\"version\"])) for a in d[\"aliases\"]])}')
for v in d['latest_versions']:
    print(f'  • Versi {v[\"version\"]}: [{v[\"current_stage\"]:11s}] Run ID: {v[\"run_id\"][:8]} | {v[\"description\"][:50]}')
"
echo ""

# ------------------------------------------------------------------------------
# TAHAP 5: Closed-Loop Validation pada Model Baru
# ------------------------------------------------------------------------------
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}${BOLD}[TAHAP 5/5] Closed-Loop Validation: Menguji Model Champion Baru...${NC}"
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Memanggil endpoint /model/reload untuk memuat bobot model baru..."
curl -s -X POST "${INFERENCE_API}/model/reload" > /dev/null 2>&1 || true

echo -e "Menguji inferensi peramalan beban flash-sale (65 RPS)..."
INFER_RESP=$(curl -s -X POST "${INFERENCE_API}/scale-decision" -H "Content-Type: application/json" -d '{
  "request_rate": 65.0,
  "php_cpu_cores": 0.95,
  "p95_latency_seconds": 0.14,
  "php_memory_mb": 190.0,
  "current_replicas": 1
}')

echo -e "Respon Keputusan Autoscaling:"
echo "$INFER_RESP" | python3 -m json.tool | head -n 25

TIMESTAMP_END=$(date +%s)
TIME_STR_END=$(date +"%Y-%m-%d %H:%M:%S WIB")
DURATION_TOTAL=$((TIMESTAMP_END - TIMESTAMP_START))

echo ""
echo -e "${GREEN}${BOLD}================================================================================"
echo "          🎉 SIMULASI END-TO-END MLOPS SELESAI SECARA SEMPURNA!               "
echo "================================================================================${NC}"
echo -e "Waktu Selesai      : ${BOLD}${TIME_STR_END}${NC} (Durasi: ${DURATION_TOTAL} detik)"
echo -e "Grafana Monitoring : ${CYAN}${GRAFANA_URL}/d/titipin-mlops-predictive-autoscaler/5b6dab5?from=${TIMESTAMP_START}000&to=${TIMESTAMP_END}000${NC}"
echo -e "VM Health (Nodes)  : ${CYAN}${GRAFANA_URL}/d/7d57716318ee0dddbac5a7f451fb7753/node-exporter-nodes?from=${TIMESTAMP_START}000&to=${TIMESTAMP_END}000${NC}"
echo -e "MLflow Registry    : ${CYAN}${MLFLOW_URL} (Model: predictive-autoscaler)${NC}"
echo -e "MinIO Storage      : ${CYAN}https://minio.titipin.me (Bucket: mlops-dvc/processed)${NC}"
echo -e "================================================================================"
echo ""
