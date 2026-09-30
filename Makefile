.PHONY: help venv install check lint test port-forward kill-pf workload-spike workload-sequence ingest preprocess preview minio-console train mlflow-ui clean

PYTHON ?= python3
VENV ?= .venv
BIN = $(VENV)/bin

help:
	@echo ""
	@echo "================================================================="
	@echo " Predictive Autoscaling MLOps — Automation Makefile"
	@echo "================================================================="
	@echo ""
	@echo "Environment & Setup:"
	@echo "  make venv               Create Python virtual environment (.venv)"
	@echo "  make install            Install all dependencies (runtime + dev: pandas, pytest, etc.)"
	@echo ""
	@echo "Code Quality & Tests:"
	@echo "  make lint               Run Ruff linter"
	@echo "  make test               Run Pytest automated quality gates"
	@echo "  make check              Run both linting and quality gate tests"
	@echo ""
	@echo "Telemetry & Ingestion Pipeline (LK-04):"
	@echo "  make port-forward       Start background tunnel to Prometheus (9090)"
	@echo "  make kill-pf            Stop the background Prometheus tunnel"
	@echo "  make ingest             Run data ingestion (last 15 minutes)"
	@echo "  make preprocess         Clean and feature-engineer latest raw data"
	@echo "  make preview            Print structured preview of latest processed data"
	@echo ""
	@echo "Data Versioning with DVC & MinIO (LK-05):"
	@echo "  make dvc-push           Push tracked datasets to MinIO S3 remote"
	@echo "  make dvc-pull           Pull latest datasets from MinIO S3 remote"
	@echo "  make dvc-status         Check DVC data status vs remote storage"
	@echo "  make dvc-diff           Inspect dataset changes and lineage diffs"
	@echo "  make minio-console      Tunnel MinIO Web UI to http://localhost:9001"
	@echo ""
	@echo "Experiment Tracking & Modeling (LK-06):"
	@echo "  make train              Train candidate forecasting models and log to MLflow"
	@echo "  make mlflow-ui          Start MLflow Tracking UI on http://localhost:5000"
	@echo ""
	@echo "Workload Generation (k6):"
	@echo "  make workload-spike     Run quick 6-minute spike scenario (HPA scale-up)"
	@echo "  make workload-sequence  Run full multi-scenario sequence (~70m)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean              Remove caches and temporary files"
	@echo "================================================================="

$(VENV)/bin/activate:
	@echo ">>> Creating virtual environment in $(VENV)..."
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

venv: $(VENV)/bin/activate

install: venv
	@echo ">>> Installing dependencies from requirements-dev.txt..."
	$(BIN)/pip install -r requirements-dev.txt
	@echo ">>> All dependencies (pandas, requests, pytest, ruff, etc.) successfully installed!"

lint: venv
	$(BIN)/ruff check .

test: venv
	$(BIN)/pytest -v tests/

check: lint test

port-forward:
	@echo ">>> Opening port-forward to Prometheus on port 9090..."
	@kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 &
	@sleep 2
	@echo ">>> Tunnel active on http://127.0.0.1:9090"

kill-pf:
	@echo ">>> Killing any active Prometheus port-forward processes..."
	@pkill -f "port-forward.*9090" 2>/dev/null || true
	@echo ">>> Done."

workload-spike:
	@bash -c "source .env.k6 2>/dev/null || true; k6 run workloads/k6/scenarios/spike.js"

workload-sequence:
	@bash scripts/run_workload_sequence.sh

ingest: venv
	$(BIN)/python src/ingest_data.py --minutes 15

preprocess: venv
	$(BIN)/python src/preprocess.py

preview: venv
	@$(BIN)/python -c "import pandas as pd, pathlib as p; files = list(p.Path('data/processed').glob('*.csv')); f = max(files, key=lambda x: x.stat().st_mtime) if files else None; df = pd.read_csv(f, index_col='timestamp') if f else None; print(f'=== DATASET PROCESSED: {f.name} ===\nDimensi: {len(df)} baris x {len(df.columns)} kolom\n' + df[['request_rate', 'php_cpu_cores', 'replicas', 'rps_lag1', 'rps_roll_mean_60s', 'target_rps_60s']].tail(8).to_string()) if df is not None else print('Belum ada file di data/processed/.')"

dvc-push: venv
	@echo ">>> Pushing tracked datasets to MinIO S3 (storage.titipin.me/mlops-dvc)..."
	@AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required $(BIN)/dvc push

dvc-pull: venv
	@echo ">>> Pulling datasets from MinIO S3 (storage.titipin.me/mlops-dvc)..."
	@AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required $(BIN)/dvc pull

dvc-status: venv
	@AWS_REQUEST_CHECKSUM_CALCULATION=when_required AWS_RESPONSE_CHECKSUM_VALIDATION=when_required $(BIN)/dvc status

dvc-diff: venv
	@$(BIN)/dvc diff

minio-console:
	@echo ">>> Membuka tunnel port-forward ke MinIO Web Console..."
	@echo ">>> Akses Browser -> http://127.0.0.1:9001"
	@echo ">>> Kredensial    -> Gunakan MINIO_ROOT_USER & MINIO_ROOT_PASSWORD dari .env.secrets"
	@echo ">>> Tekan Ctrl+C untuk menutup tunnel."
	@kubectl port-forward -n titipin svc/minio 9001:9001

train: venv
	@$(BIN)/python src/models/train.py --all

register: venv
	@$(BIN)/python src/models/register_model.py

verify-model: venv
	@$(BIN)/python src/models/register_model.py --verify-only

mlflow-ui: venv
	@echo ">>> Membuka MLflow Tracking UI pada http://127.0.0.1:5000..."
	@echo ">>> Tekan Ctrl+C untuk menutup server UI."
	@$(BIN)/mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000

compose-build:
	@docker compose build

compose-up:
	@docker compose up -d

compose-down:
	@docker compose down

compose-ps:
	@docker compose ps

k8s-apply:
	@echo ">>> Deploying MLOps infrastructure & predictive autoscaler to Kubernetes cluster..."
	@kubectl apply -k infrastructure/kubernetes/mlops/

k8s-status:
	@echo ">>> Status of resources in 'mlops' namespace:"
	@kubectl get all,servicemonitors -n mlops

k8s-logs:
	@echo ">>> Streaming logs from predictive-scaler controller in 'mlops' namespace..."
	@kubectl logs -n mlops deploy/mlops-inference -c predictive-scaler -f

k8s-dashboard:
	@echo ">>> Forwarding Streamlit dashboard to http://127.0.0.1:8501..."
	@kubectl port-forward -n mlops svc/mlops-dashboard-svc 8501:8501

k8s-inference:
	@echo ">>> Forwarding inference API to http://127.0.0.1:8000..."
	@kubectl port-forward -n mlops svc/mlops-inference-svc 8000:8000



clean:
	rm -rf .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo ">>> Cache cleaned."
