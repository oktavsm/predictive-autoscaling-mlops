#!/usr/bin/env bash
# ==============================================================================
# Automated DVC Remote Synchronization Script (Headless / VM / CI)
# ==============================================================================
# Menjalankan sinkronisasi dataset DVC dengan MinIO S3 Object Storage
# secara otomatis tanpa hardcoding kredensial.
#
# Penggunaan:
#   ./scripts/sync_dvc_remote.sh pull     # Tarik dataset dari MinIO S3
#   ./scripts/sync_dvc_remote.sh push     # Unggah dataset baru ke MinIO S3
#   ./scripts/sync_dvc_remote.sh status   # Cek sinkronisasi data terhadap remote
#
# Variabel Lingkungan (Opsional - jika .dvc/config.local belum ada):
#   export MINIO_ACCESS_KEY="<access_key>"
#   export MINIO_SECRET_KEY="<secret_key>"
# ==============================================================================

set -euo pipefail

ACTION="${1:-status}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Kompatibilitas AWS SDK checksum dengan gateway MinIO
export AWS_REQUEST_CHECKSUM_CALCULATION=when_required
export AWS_RESPONSE_CHECKSUM_VALIDATION=when_required

# Cek apakah DVC terpasang di environment
DVC_BIN="dvc"
if ! command -v dvc &> /dev/null; then
    if [ -f "${REPO_ROOT}/.venv/bin/dvc" ]; then
        DVC_BIN="${REPO_ROOT}/.venv/bin/dvc"
    else
        echo "❌ Error: DVC tidak ditemukan. Aktifkan venv atau jalankan: pip install 'dvc[s3]'"
        exit 1
    fi
fi

# Konfigurasi kredensial otomatis dari Environment Variables jika belum ada .dvc/config.local
if [ ! -f "${REPO_ROOT}/.dvc/config.local" ]; then
    if [ -n "${MINIO_ACCESS_KEY:-}" ] && [ -n "${MINIO_SECRET_KEY:-}" ]; then
        echo "ℹ️  Mengonfigurasi kredensial DVC sementara dari environment variables..."
        "$DVC_BIN" config --local remote.minio.access_key_id "$MINIO_ACCESS_KEY"
        "$DVC_BIN" config --local remote.minio.secret_access_key "$MINIO_SECRET_KEY"
    fi
fi

case "$ACTION" in
    pull)
        echo "📥 [DVC] Mengunduh dataset dari MinIO S3 (s3://mlops-dvc)..."
        "$DVC_BIN" pull
        echo "✓ Dataset berhasil disinkronkan ke lokal (data/raw dan data/processed)."
        ;;
    push)
        echo "📤 [DVC] Mengunggah dataset ke MinIO S3 (s3://mlops-dvc)..."
        "$DVC_BIN" push
        echo "✓ Dataset berhasil diunggah ke MinIO S3."
        ;;
    status)
        echo "🔍 [DVC] Memeriksa status dataset terhadap remote MinIO S3..."
        "$DVC_BIN" status
        ;;
    diff)
        TAG1="${2:-v1.0-data}"
        TAG2="${3:-v2.0-data}"
        echo "📊 [DVC] Memeriksa perbedaan dataset antara ${TAG1} dan ${TAG2}..."
        "$DVC_BIN" diff "$TAG1" "$TAG2"
        ;;
    *)
        echo "Penggunaan: $0 {pull|push|status|diff [tag1] [tag2]}"
        exit 1
        ;;
esac
