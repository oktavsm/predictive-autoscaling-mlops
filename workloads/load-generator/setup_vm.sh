#!/usr/bin/env bash
# ==============================================================================
# Remote VM Setup & Installation Script for Titipin Synthetic Traffic Generator
# ==============================================================================
# Digunakan untuk melakukan instalasi dan registrasi service generator beban
# sintetis otomatis pada remote VM (misal: cp-bcc pada Ubuntu/Debian).
#
# Prasyarat:
#   - User memiliki hak sudo
#   - Koneksi internet aktif untuk mengunduh k6
#
# Penggunaan:
#   bash setup_vm.sh
# ==============================================================================

set -euo pipefail

INSTALL_DIR="${HOME}/titipin-traffic-generator"
SERVICE_NAME="titipin-traffic-generator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [1/4] Memeriksa & Menginstal Dependensi Sistem ==="
if ! command -v k6 &> /dev/null; then
    echo "Mengunduh k6 load generator..."
    sudo gpg -k 2>/dev/null || true
    sudo mkdir -p -m 755 /etc/apt/keyrings
    wget -q -O - https://dl.k6.io/key.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/k6.gpg --yes
    echo "deb [signed-by=/etc/apt/keyrings/k6.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
    sudo apt-get update -y
    sudo apt-get install -y k6 python3
else
    echo "✓ k6 dan python3 sudah terpasang."
fi

echo "=== [2/4] Menyiapkan Direktori Kerja di ${INSTALL_DIR} ==="
mkdir -p "${INSTALL_DIR}"
cp "${SCRIPT_DIR}/traffic_daemon.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/k6_scenario.js" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/manage_generator.sh" "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/traffic_daemon.py" "${INSTALL_DIR}/manage_generator.sh"

echo "=== [3/4] Mendaftarkan Systemd Service (${SERVICE_NAME}) ==="
# Template unit file dengan substitusi user dan direktori aktual
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=Titipin Continuous Synthetic Traffic Generator (MLOps Workload Simulator)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/traffic_daemon.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1
Environment=TARGET_URL=https://api.titipin.me

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "=== [4/4] Verifikasi Status Service ==="
sudo systemctl status "${SERVICE_NAME}" --no-pager | head -n 12

echo ""
echo "🎉 Instalasi selesai! Generator beban sekarang berjalan otomatis 24/7 di VM ini."
echo "Untuk mengelola service, gunakan: ${INSTALL_DIR}/manage_generator.sh {status|logs|trigger|stop|restart}"
