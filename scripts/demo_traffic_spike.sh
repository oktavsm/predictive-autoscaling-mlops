#!/usr/bin/env bash
# ==============================================================================
# Demo Traffic Spike Script for Predictive Autoscaler Verification
# ==============================================================================
# Mensimulasikan lonjakan trafik HTTP yang eskalatif ke backend Laravel via k6
# untuk membuktikan kemampuan predictive autoscaler merespons SEBELUM lonjakan
# mencapai puncak (eliminasi scaling lag).
#
# Cara penggunaan:
#   bash scripts/demo_traffic_spike.sh
#   bash scripts/demo_traffic_spike.sh --target-url https://api.titipin.me
#
# Dependensi:
#   - k6 CLI (https://k6.io/docs/getting-started/installation/)
#   - kubectl (terautentikasi ke klaster K3s)
#   - curl
# ==============================================================================

set -euo pipefail

TARGET_URL="${1:-https://api.titipin.me}"
NAMESPACE_WATCH="mlops"
DEPLOY_WATCH="laravel-backend"
NAMESPACE_TARGET="titipin"
DEMO_DURATION_SECONDS=360

echo "================================================================================"
echo "       LIVE DEMO: Predictive Autoscaling Traffic Spike Simulation        "
echo "================================================================================"
echo "Target URL     : ${TARGET_URL}"
echo "Watch Namespace: ${NAMESPACE_WATCH}"
echo "Watch Deploy   : ${NAMESPACE_TARGET}/${DEPLOY_WATCH}"
echo "Demo Duration  : ${DEMO_DURATION_SECONDS}s (~6 menit)"
echo ""
echo "[INFO] Pastikan 2 terminal lain terbuka:"
echo "       Terminal 2: kubectl get pods -n ${NAMESPACE_TARGET} -w"
echo "       Terminal 3: Buka https://grafana.titipin.me (Dashboard MLOps Predictive)"
echo ""
echo "Tekan Enter untuk memulai demonstrasi..."
read -r

# ---- Phase 0: Show current state ----
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[FASE 0] Status pod saat ini (SEBELUM lonjakan trafik):"
kubectl get pods -n "${NAMESPACE_TARGET}" 2>/dev/null || echo "(kubectl tidak tersedia — jalankan di node klaster)"
echo ""
echo "[FASE 0] Status autoscaler controller:"
kubectl get deploy mlops-inference -n "${NAMESPACE_WATCH}" 2>/dev/null | tail -2 || true
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ---- Phase 1: Baseline warm-up (30 VU x 60s) ----
echo ""
echo "[FASE 1] Baseline Warm-Up (30 VU x 60 detik)..."
k6 run --vus 30 --duration 60s \
    -e TARGET_URL="${TARGET_URL}" \
    workloads/k6/scenarios/spike.js 2>&1 | tail -8 || \
    # Fallback jika k6 tidak tersedia: simulate dengan curl loop
    (echo "[FALLBACK] k6 tidak tersedia. Simulasi baseline dengan curl..."; \
     for _ in $(seq 1 30); do curl -s -o /dev/null "${TARGET_URL}/api/health" & done; wait)

echo ""
echo "[FASE 1] Status pod setelah warm-up:"
kubectl get pods -n "${NAMESPACE_TARGET}" 2>/dev/null | grep -E "NAME|laravel" || true

# ---- Phase 2: Spike escalation (60 → 200 VU x 180s) ----
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "[FASE 2] LONJAKAN TRAFIK ESKALATIF: 60 → 200 VU (3 menit)"
echo "         PERHATIKAN: Grafana harus menampilkan prediksi SEBELUM replika naik!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

k6 run \
    --stage 0s:60 \
    --stage 60s:120 \
    --stage 120s:200 \
    --stage 180s:200 \
    -e TARGET_URL="${TARGET_URL}" \
    workloads/k6/scenarios/spike.js 2>&1 | tail -15 || \
    # Fallback: simulasi lonjakan escalating dengan sleep
    (echo "[FALLBACK] k6 tidak tersedia. Simulasi escalation..."; \
     for batch in 60 100 140 200; do \
       echo "  -> Sending ${batch} concurrent requests..."; \
       for _ in $(seq 1 "${batch}"); do curl -s -o /dev/null "${TARGET_URL}/api/health" & done; \
       wait; sleep 30; \
     done)

echo ""
echo "[FASE 2] Status pod SETELAH lonjakan (idealnya sudah scale-up SEBELUM puncak):"
kubectl get pods -n "${NAMESPACE_TARGET}" 2>/dev/null | grep -E "NAME|laravel" || true

# ---- Phase 3: Cool-down (30 VU x 60s) ----
echo ""
echo "[FASE 3] Cool-Down (30 VU x 60 detik) — scaler akan menurunkan replika..."
k6 run --vus 30 --duration 60s \
    -e TARGET_URL="${TARGET_URL}" \
    workloads/k6/scenarios/spike.js 2>&1 | tail -5 || \
    (echo "[FALLBACK] Cool-down simulation..."; sleep 60)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEMO SELESAI!"
echo ""
echo "[FASE 4] Status pod AKHIR (cool-down selesai):"
kubectl get pods -n "${NAMESPACE_TARGET}" 2>/dev/null | grep -E "NAME|laravel" || true
echo ""
echo "Lihat Grafana Dashboard (https://grafana.titipin.me) untuk melihat:"
echo "  - Kurva 'Predicted RPS t+60s' naik SEBELUM 'Actual Request Rate'"
echo "  - Kurva 'Pod Replicas' naik proaktif, eliminasi scaling lag"
echo "  - Alert rule tidak terpicu (SLO terpenuhi)"
echo "================================================================================"
