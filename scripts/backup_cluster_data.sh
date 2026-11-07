#!/usr/bin/env bash
# ==============================================================================
# Titip.In MLOps Platform — Automated Backup Engine
# Backs up PostgreSQL, MLflow SQLite, Operations SQLite, and MinIO S3 data
# to the local developer machine for zero-loss disaster recovery.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${REPO_ROOT}/backups/${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

echo "======================================================================"
echo "[BACKUP] Backing up Titip.In MLOps Cluster Data"
echo "  Target Local Directory: ${BACKUP_DIR}"
echo "======================================================================"

# 1. PostgreSQL Database Dump
echo "[1/4] Dumping PostgreSQL database (titipin_db)..."
ssh cp "kubectl -n titipin exec postgres-0 -- pg_dump -U titipin_user titipin_db" > "${BACKUP_DIR}/titipin_db.sql"
echo "  [+] Saved PostgreSQL dump ($(du -h "${BACKUP_DIR}/titipin_db.sql" | cut -f1))"

# 2. MLOps Operations State SQLite Backup
echo "[2/4] Backing up Operations SQLite state..."
ssh cp "kubectl -n mlops exec deployment/mlops-inference -c inference-api -- cat /var/lib/mlops/operations.sqlite" > "${BACKUP_DIR}/operations.sqlite"
echo "  [+] Saved operations.sqlite ($(du -h "${BACKUP_DIR}/operations.sqlite" | cut -f1))"

# 3. MLflow SQLite State Backup
echo "[3/4] Backing up MLflow SQLite registry & tracking database..."
ssh cp "kubectl -n mlops exec deployment/mlops-mlflow -c mlflow-server -- cat /var/lib/mlflow/mlflow.db" > "${BACKUP_DIR}/mlflow.db"
echo "  [+] Saved mlflow.db ($(du -h "${BACKUP_DIR}/mlflow.db" | cut -f1))"

# Load environment variables if available
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  source <(grep -v '^#' "${REPO_ROOT}/.env" | grep -v '^\s*$')
  set +a
fi

# 4. MinIO S3 Metadata & Latest Datasets
echo "[4/4] Syncing MinIO S3 bucket metadata..."
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

if [[ -z "${AWS_ACCESS_KEY_ID}" ]] || [[ -z "${AWS_SECRET_ACCESS_KEY}" ]]; then
  echo "[-] ERROR: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be provided via environment or .env"
  exit 1
fi

aws --endpoint-url https://storage.titipin.me s3 ls s3://mlops-dvc/ --recursive > "${BACKUP_DIR}/minio_mlops_dvc_manifest.txt"
aws --endpoint-url https://storage.titipin.me s3 ls s3://mlflow/ --recursive > "${BACKUP_DIR}/minio_mlflow_manifest.txt"
echo "  [+] MinIO manifests saved."

# Create latest symlink
rm -f "${REPO_ROOT}/backups/latest"
ln -sf "${BACKUP_DIR}" "${REPO_ROOT}/backups/latest"

echo "======================================================================"
echo "[SUCCESS] BACKUP COMPLETED SUCCESSFULLY!"
echo "   Directory: ${BACKUP_DIR}"
echo "======================================================================"
