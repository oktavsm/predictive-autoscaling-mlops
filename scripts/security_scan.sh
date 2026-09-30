#!/usr/bin/env bash
# ==============================================================================
# Security Scan Pipeline — Trivy Container Vulnerability & Secret Audit
# ==============================================================================
# Memindai image Docker untuk mendeteksi kerentanan CVE tingkat HIGH/CRITICAL
# serta memverifikasi bahwa tidak ada rahasia/kredensial yang bocor di filesystem image.
# ==============================================================================
set -euo pipefail

IMAGE_NAME="${1:-oktaavsm/predictive-autoscaler:latest}"
REPORT_DIR="reports"
OUTPUT_JSON="${REPORT_DIR}/trivy_scan_report.json"
OUTPUT_TXT="${REPORT_DIR}/trivy_scan_summary.txt"

mkdir -p "${REPORT_DIR}"

echo "================================================================================"
echo "         CONTAINER SECURITY & VULNERABILITY AUDIT (AQUASEC TRIVY)               "
echo "================================================================================"
echo "Target Image : ${IMAGE_NAME}"
echo "Output JSON  : ${OUTPUT_JSON}"
echo "Output Text  : ${OUTPUT_TXT}"
echo "--------------------------------------------------------------------------------"

# Cek apakah trivy binary terpasang atau gunakan container aquasec/trivy
if command -v trivy >/dev/null 2>&1; then
    TRIVY_CMD="trivy"
else
    echo "[INFO] Trivy CLI lokal tidak ditemukan. Menjalankan via Docker container (aquasec/trivy:latest)..."
    TRIVY_CMD="docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v $(pwd)/reports:/reports aquasec/trivy:latest"
fi

echo "[1/2] Menjalankan pemindaian kerentanan OS & dependensi Python..."
if command -v trivy >/dev/null 2>&1; then
    trivy image --severity HIGH,CRITICAL --format json -o "${OUTPUT_JSON}" "${IMAGE_NAME}" || true
    trivy image --severity HIGH,CRITICAL "${IMAGE_NAME}" | tee "${OUTPUT_TXT}"
else
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$(pwd)/reports:/reports" \
        aquasec/trivy:latest image --severity HIGH,CRITICAL --format json -o /reports/trivy_scan_report.json "${IMAGE_NAME}" || true
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
        aquasec/trivy:latest image --severity HIGH,CRITICAL "${IMAGE_NAME}" | tee "${OUTPUT_TXT}"
fi

echo "--------------------------------------------------------------------------------"
echo "[2/2] Verifikasi audit keamanan rahasia (Secret Scanning)..."
if command -v trivy >/dev/null 2>&1; then
    trivy image --scanners secret "${IMAGE_NAME}"
else
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
        aquasec/trivy:latest image --scanners secret "${IMAGE_NAME}"
fi

echo "================================================================================"
echo "✅ AUDIT KEAMANAN KONTAINER SELESAI"
echo "  - Laporan JSON: ${OUTPUT_JSON}"
echo "  - Laporan Teks: ${OUTPUT_TXT}"
echo "================================================================================"
