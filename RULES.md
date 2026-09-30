# Repository Rules & AI Agent Operational Guidelines

> **Target Audience:** All AI Coding Assistants (Antigravity, Claude Code, Cursor, Copilot) & Contributors  
> **Repository:** `oktavsm/predictive-autoscaling-mlops`  
> **Status:** Mandatory (Strict Enforcement)

---

## 1. Golden Rule: Always Consult Existing Documentation First

Before generating code, refactoring architecture, or proposing solutions, **the AI Agent MUST read and reference the existing technical documentation**. Do not guess architecture, invent new conventions, or write speculative code.

### 📚 Documentation Reference Map

| Domain / Topic | Primary Documentation File to Consult |
|---|---|
| **System Architecture & Data Flows** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| **Telemetry & ETL Pipeline Design** | [`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md) |
| **Ingestion & Preprocessing Code Guide (LK-04)** | [`docs/DATA_INGESTION_AND_PREPROCESSING.md`](docs/DATA_INGESTION_AND_PREPROCESSING.md) |
| **Data Versioning & DVC Remote (LK-05)** | [`docs/DATA_VERSIONING_DVC.md`](docs/DATA_VERSIONING_DVC.md) |
| **MLflow Experiment Tracking & Modeling (LK-06)**| [`docs/EXPERIMENT_TRACKING_MLFLOW.md`](docs/EXPERIMENT_TRACKING_MLFLOW.md) |
| **Cloudflare Domains & Caddy UI Setup** | [`docs/CLOUDFLARE_DOMAIN_SETUP.md`](docs/CLOUDFLARE_DOMAIN_SETUP.md) |
| **Workload Generation (k6 Scenarios & Runbook)**| [`docs/WORKLOAD_GENERATION.md`](docs/WORKLOAD_GENERATION.md) |
| **CI/CD & Continuous Training (CT) Strategy** | [`docs/CICD_DESIGN.md`](docs/CICD_DESIGN.md) |
| **Architecture Decision Records (ADRs & Horizon)**| [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| **Infrastructure Deployment & K3s Cluster** | [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) |
| **Codespaces Environment Setup** | [`docs/CODESPACE_SETUP.md`](docs/CODESPACE_SETUP.md) |
| **Division of Work: Human vs. Agent (LK-05 - LK-14)**| [`docs/internal/LK_WORK_DIVISION_GUIDE.md`](docs/internal/LK_WORK_DIVISION_GUIDE.md) |
| **Directory & File Dictionary** | [`docs/internal/PROJECT_FILE_DICTIONARY.md`](docs/internal/PROJECT_FILE_DICTIONARY.md) |

---

## 2. Infrastructure Truth: Use Real Systems, Never Mock

This repository is backed by a **live 3-node Kubernetes (K3s) cluster on AWS**. Never introduce dummy/mock services when real infrastructure components already exist:

1. **Telemetry:** Ingestion MUST query the live Prometheus server at `http://127.0.0.1:9090` (tunneled via `kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090`).
2. **Object Storage:** Remote dataset storage MUST target the live MinIO S3 cluster at `https://storage.titipin.me` (bucket: `mlops-dvc`).
3. **Target Workload Application:** Target backend is live at `https://api.titipin.me` (PHP-FPM + Nginx sidecar on namespace `titipin`).
4. **Monitoring:** Dashboards live at `https://grafana.titipin.me`.
5. **Prediction Horizon:** Fixed at **60 seconds (4 steps @ 15s)**. This is empirically grounded by measured container scale-up latency (~45s). Do not change horizon length arbitrarily.

---

## 3. Privacy, Security & Sanitization Rules

1. **NO RAW SERVER IPs IN PUBLIC DOCS:**  
   Never write raw AWS public IPs in public markdown files or commit messages. Always use standard placeholders:
   * `<CONTROL_PLANE_IP>`
   * `<WORKER_1_IP>`
   * `<WORKER_2_IP>`
2. **NO HARDCODED SECRETS:**  
   Credentials and tokens belong exclusively in `.env.secrets` (which is strictly gitignored) or Kubernetes secrets. Never commit AWS keys, MinIO root credentials, or API tokens to public Git tracking.
3. **COURSEWORK & INTERNAL DOCS BOUNDARY:**  
   * `docs/internal/` and `docs/coursework/` are gitignored to protect academic assessment integrity and personal infrastructure notes. Preserve these boundaries.

---

## 4. Git Flow & Branching Conventions

* **Branch Per Milestone:** Never commit directly to `main`. Always work on dedicated feature branches:
  * `feat/lk04-ingestion`
  * `feat/lk05-dvc`
  * `feat/lk06-mlflow-training`
  * `feat/lk07-model-registry`
  * ...up to `feat/lk14-final-demo`
* **Conventional Commits:** Every commit message must follow standard semantic format:
  * `feat(scope): ...`
  * `fix(scope): ...`
  * `docs(scope): ...`
  * `test(scope): ...`
  * `chore(scope): ...`

---

## 5. Code Quality & Pre-Commit Verification

Before concluding any implementation task:
1. Always run `make check` (or `.venv/bin/ruff check .` and `.venv/bin/pytest -v tests/`).
2. All 8 smoke tests in [`tests/test_dataset.py`](tests/test_dataset.py) must pass without warnings.
3. Zero linter errors allowed (`ruff check .` must output `All checks passed!`).
4. Preserve existing comments and docstrings. Follow PEP 8 style with explicit type hints.

---

## 6. Division of Work: Human vs. Agent

Always consult [`docs/internal/LK_WORK_DIVISION_GUIDE.md`](docs/internal/LK_WORK_DIVISION_GUIDE.md) when executing assignments:
* **Agent Automates:** Writing scripts, configs, tests, Dockerfiles, K8s manifests, DVC/MLflow setup, Makefile targets, and drafting comprehensive reports.
* **Agent Prepares for Human:** Whenever an action requires user intervention (e.g. running k6 load test, opening browser to take screenshots, submitting PDF to university LMS), the agent MUST provide **clean, copy-pasteable terminal commands** and explain exactly **what to screenshot and why**.

---

## 7. Documentation Integrity

* Every new feature, script, or pipeline stage MUST be documented in both the relevant `docs/` file and referenced in the main [`README.md`](README.md) Documentation Index.
* Always use **clickable GitHub markdown links with `file://` scheme** when referring to files and line ranges in responses.
