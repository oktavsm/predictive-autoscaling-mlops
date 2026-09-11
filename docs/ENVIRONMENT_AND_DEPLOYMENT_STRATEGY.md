# Environment and Deployment Strategy

> Repository: `oktavsm/predictive-autoscaling-mlops`
>
> Purpose: GitHub Codespaces/LK setup, environment boundaries, and the target VPS/K3s MLOps deployment
>
> Last reviewed against the repository: 2026-09-11

## 1. Executive Decision

GitHub Codespaces is the project's **reproducible development environment**. It is used to edit code, run notebooks, install the same Python dependencies, execute tests, and preview development services. It is not the production runtime and is not expected to remain online.

The environment boundary is:

```text
Local laptop                    GitHub Codespaces                 VPS / K3s cluster
-------------                   -----------------                 -----------------
Daily development               Reproducible development          Long-running system
SSH and operator access         LK evidence                       Real metrics and state
External k6 workloads           EDA / tests / local previews      Prometheus + Grafana
Optional local notebooks        Same Python/tool versions         DVC/MLflow services
                                No production ownership            Inference + scaler
                                                                   Drift + retraining
```

The recommended ML-facing web interface is a **small Streamlit dashboard backed by FastAPI** at `mlops.titipin.me`. Grafana remains responsible for infrastructure and application telemetry. The ML dashboard is responsible for model, prediction, drift, and scaler context.

The target deployment is still an experimental production-like environment. It must not be described as proven production-grade until reliability, security, backup, and failure recovery have been tested.

## 2. Current Repository Baseline

The following observations come from the repository at the review date:

- `main` contains the K3s manifests, monitoring configuration, Caddy/Grafana documentation, k6 workload scenarios, Prometheus exporters, and a merged demo dataset.
- `src/data/demo_metrics.csv` contains 284 observations plus a header with `request_rate`, PHP CPU, PHP memory, replica count, and p95 latency.
- The local development environment uses Python 3.12.
- `.devcontainer/devcontainer.json` and a committed Python dependency manifest do not exist yet.
- The branch `feat/initial-eda` does not exist yet.
- DVC, MLflow, FastAPI inference, predictive scaling, drift monitoring, and retraining are planned but not yet represented as completed services in the repository.
- `README.md` still describes an earlier project phase in its status section; implementation evidence and recent commits are newer than that status text.

This document therefore treats the Codespaces configuration and the later MLOps services as **recommended implementation**, not as already completed work.

Related project documents:

- [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`MODELING.md`](MODELING.md)
- [`DECISIONS.md`](DECISIONS.md)
- [`NEXT_STEPS.md`](NEXT_STEPS.md)
- [`SETUP_GUIDE_DEMO_READY.md`](SETUP_GUIDE_DEMO_READY.md)

## 3. Environment Boundaries

### 3.1 Responsibility matrix

| Responsibility | Local laptop | GitHub Codespaces | VPS / K3s cluster |
|---|---:|---:|---:|
| Edit code and documentation | Yes | Yes | No |
| Git commits and GitHub Flow | Yes | Yes | No |
| Run lint and unit tests | Yes | Yes | CI may repeat them |
| Run Jupyter notebooks / EDA | Yes | Yes, recommended for LK | Only as a scheduled job when required |
| Preview FastAPI and Streamlit | Yes | Yes, private forwarded ports | Yes, as deployed services |
| Build container images | Optional | Optional | CI builds; cluster only pulls images |
| Operate `kubectl` / Helm | Yes, operator workstation | Optional and restricted | Control plane owns cluster state |
| Generate controlled k6 load | Yes, recommended | Smoke only, not benchmark evidence | No; load must originate outside the cluster |
| Store authoritative metrics | No | No | Prometheus on VPS/K3s |
| Store authoritative datasets/artifacts | DVC cache only | DVC cache only | DVC remote / object storage |
| Run MLflow tracking server | Local preview only | Local preview only | Yes |
| Serve the selected model | Local preview only | Local preview only | Yes |
| Apply replica changes | No, except explicit operator action | No by default | Yes, through the scaler's limited service account |
| Detect drift continuously | No | No | Yes |
| Schedule ingestion/retraining | Manual development runs | Manual validation runs | Kubernetes CronJob and/or GitHub Actions |
| Hold secrets | Local untracked files/keyring | Codespaces secrets | Kubernetes/GitHub secrets |

### 3.2 Local laptop

The laptop is the primary operator and external experiment client. It should contain:

- Git and GitHub CLI;
- Python 3.12 when working outside the dev container;
- SSH configuration for the VPS nodes;
- `kubectl` and Helm when cluster administration is required;
- k6 for externally generated workloads;
- Docker only when local image testing is useful;
- local, ignored `.env.*` files containing non-committed configuration.

The laptop is the preferred k6 host for the current project because it is outside the target cluster and already matches the client-to-Caddy path. A dedicated load-generator VPS can replace it later if network stability and unattended runs become experimental requirements.

### 3.3 GitHub Codespaces

Codespaces exists to prove that a fresh environment can reproduce development without relying on laptop-specific setup. It should support:

- opening the repository in a fresh codespace;
- Python 3.12;
- deterministic dependency installation;
- Jupyter notebooks and initial EDA;
- linting and tests;
- execution of repository scripts against committed sample data;
- local FastAPI and Streamlit previews through private forwarded ports;
- optional manifest validation with `kubectl` and Helm.

Codespaces must not own:

- the public domain;
- authoritative Prometheus data;
- the production MLflow database or artifact store;
- DVC's only copy of a dataset;
- a persistent inference API;
- the predictive scaler;
- drift monitoring;
- cron/scheduler duties;
- a production kubeconfig committed to the repository.

Codespaces can stop, rebuild, or be deleted. Forwarded URLs are development URLs, not stable service endpoints. This is why Codespaces must not be used as the production runtime.

### 3.4 VPS / K3s cluster

The three VPS/VM nodes remain the production-experiment environment:

| Node | Role | Long-running responsibility |
|---|---|---|
| VM-01 | K3s control plane | Kubernetes control plane, Caddy, Prometheus, Grafana, and lightweight MLOps control services when capacity permits |
| VM-02 | K3s worker | Laravel backend and deployable MLOps workloads |
| VM-03 | K3s worker | Laravel backend and deployable MLOps workloads |

Training must not destabilize the control plane. If training competes with Prometheus, Grafana, or Kubernetes, run it as a resource-limited worker job, during a controlled window, or outside the cluster. That execution location must be recorded in MLflow.

## 4. GitHub Codespaces Setup for the LK Assignment

### 4.1 What must be reproducible

A fresh Codespace should reproduce these items from Git:

1. the Python major/minor version;
2. system and CLI tools required by every contributor;
3. Python dependencies and their versions;
4. VS Code extensions used for Python, notebooks, and configuration files;
5. repository structure;
6. commands for tests, EDA, FastAPI, and Streamlit previews;
7. example environment variable names without secret values;
8. a small committed dataset or fixture that lets validation run without VPS access.

The following are intentionally not reproduced inside the Codespace image:

- VPS credentials and SSH private keys;
- production Kubernetes secrets;
- live MLflow/DVC credentials;
- large datasets and model binaries;
- the whole three-node cluster;
- real benchmark results produced by a shared Codespaces machine.

### 4.2 Recommended files

```text
predictive-autoscaling-mlops/
├── .devcontainer/
│   └── devcontainer.json
├── .github/
│   └── workflows/
│       └── ci.yml
├── data/                         # Dataset artifacts; DVC-managed
│   ├── raw/
│   ├── interim/
│   └── processed/
├── models/                       # Model artifacts; DVC/MLflow-managed
├── notebooks/
│   └── 01_initial_eda.ipynb
├── src/
│   ├── data/                     # Data ingestion/validation code
│   ├── features/
│   ├── models/                   # Training/evaluation code
│   ├── inference/
│   └── scaling/
├── api/
├── pipelines/
│   ├── ingestion/
│   ├── training/
│   └── retraining/
├── configs/                      # Existing repository convention
├── infrastructure/
├── tests/
├── workloads/k6/
├── requirements.txt              # Runtime dependencies
├── requirements-dev.txt          # Runtime + notebook/test tools
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

The current repository stores dataset files under `src/data/`. For the lowest rubric risk, move data artifacts to top-level `data/` when DVC is initialized, while keeping ingestion code in `src/data/`. Likewise, model code stays in `src/models/`, while model artifacts go to top-level `models/`. Do not perform the move without updating and testing the existing exporter/merge scripts.

`configs/` is already established and serves the assignment's `config/` responsibility. Creating both `config/` and `configs/` would add ambiguity without adding capability.

### 4.3 Recommended `devcontainer.json`

Create `.devcontainer/devcontainer.json` on `feat/initial-eda`:

```jsonc
{
  "name": "predictive-autoscaling-mlops",
  "image": "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm",

  "features": {
    "ghcr.io/devcontainers/features/common-utils:2": {},
    "ghcr.io/devcontainers/features/kubectl-helm-minikube:1": {
      "version": "latest",
      "helm": "latest",
      "minikube": "none"
    }
  },

  "postCreateCommand": "python -m pip install --upgrade pip && python -m pip install -r requirements-dev.txt",

  "forwardPorts": [8000, 8501],
  "portsAttributes": {
    "8000": {
      "label": "FastAPI development preview",
      "onAutoForward": "notify",
      "visibility": "private"
    },
    "8501": {
      "label": "Streamlit development preview",
      "onAutoForward": "notify",
      "visibility": "private"
    }
  },

  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-toolsai.jupyter",
        "charliermarsh.ruff",
        "redhat.vscode-yaml"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "python.testing.pytestEnabled": true,
        "editor.formatOnSave": true,
        "[python]": {
          "editor.defaultFormatter": "charliermarsh.ruff"
        }
      }
    }
  },

  "remoteUser": "vscode"
}
```

Why this baseline:

- Python 3.12 matches the repository's current local environment.
- Bookworm provides a stable Debian base.
- Jupyter, Pylance, Ruff, and YAML support cover the current development work.
- `kubectl` and Helm are available for client-side validation and explicit operator work; Minikube is omitted because the real cluster already exists.
- only FastAPI and Streamlit development ports are forwarded, and both default to private.

Docker-in-Docker is not necessary for the initial LK/EDA branch. Add the following feature only when Codespaces must build or run containers:

```jsonc
"ghcr.io/devcontainers/features/docker-in-docker:4": {}
```

It adds startup time, storage use, and a privileged nested daemon, so it should not be installed merely because the production system uses containers.

A custom `.devcontainer/Dockerfile` is also unnecessary at this stage. Use one only when a required OS package cannot be expressed cleanly through the base image, a Dev Container Feature, or Python requirements.

### 4.4 Dependency strategy

Use two small dependency files:

```text
# requirements.txt — code used by scripts/services
pandas==3.0.5
requests==2.34.2
```

The two versions above match the environment used by the repository's existing ingestion scripts at the review date.

```text
# requirements-dev.txt — include runtime dependencies first
-r requirements.txt

# Add exact tested versions on feat/initial-eda:
jupyterlab==<tested-version>
matplotlib==<tested-version>
seaborn==<tested-version>
scikit-learn==<tested-version>
pytest==<tested-version>
ruff==<tested-version>
```

Do not leave `<tested-version>` placeholders in the merged file. Resolve the versions inside the Python 3.12 Codespace, run the EDA/test checks, and commit the exact working versions in the same pull request.

Add later dependencies only when their component exists:

| Phase | Dependency examples | Reason to defer |
|---|---|---|
| DVC | `dvc[s3]` | Needs an agreed remote and credential strategy |
| Training/registry | `mlflow`, model library, `joblib` | Depends on the selected baseline/candidate model |
| Inference | `fastapi`, `uvicorn` | API contract is still open before EDA |
| ML dashboard | `streamlit` | Dashboard should consume a real status contract |
| Drift | selected statistical package, if needed | Drift method remains evidence-dependent |

This avoids making every Codespace install the whole future production stack before that code exists.

### 4.5 Sensible CLI tools

| Tool | Codespaces status | Use |
|---|---|---|
| `git` | Required | GitHub Flow and history |
| `gh` | Useful | Pull requests and repository operations |
| `curl` | Required | Health/API checks |
| `jq` | Useful | Inspect JSON responses |
| `make` | Optional | Stable project command aliases once a Makefile exists |
| `kubectl` | Optional but included above | Validate manifests; access the real cluster only with explicit credentials |
| Helm | Optional but included above | Validate/deploy charts when required |
| Docker | Deferred | Add only when Codespaces must build/run images |
| k6 | Not required in the base Codespace | Use laptop/dedicated external runner for measurements; Codespaces may run a smoke check only |
| DVC | Phase-specific Python dependency | Pull/push versioned datasets |
| MLflow CLI | Phase-specific Python dependency | Local experiment or server commands |

### 4.6 Secrets and configuration

Commit only templates such as:

```text
.env.example
.env.k6.example
.env.secrets.example
```

Use these locations for real values:

| Secret type | Correct location |
|---|---|
| Local development | ignored `.env.*`, SSH agent, or local keyring |
| Codespaces | GitHub Codespaces secrets scoped to this repository |
| CI/CD | GitHub Actions environment/repository secrets |
| K3s runtime | Kubernetes Secret or an external secret store |

Never commit a kubeconfig, GitHub token, DVC access key, MLflow credential, database password, or MinIO secret. Codespaces secrets become environment variables; their names may be documented, but their values must not be printed in notebooks or logs.

Suggested non-secret variable names:

```text
PROM_URL
MLFLOW_TRACKING_URI
DVC_REMOTE_NAME
MODEL_STATUS_URL
INFERENCE_API_URL
SCALER_MODE
```

### 4.7 Fresh Codespace validation

After creating or rebuilding the Codespace:

```bash
python --version
python -m pip check
python -c "import pandas, requests; print('python dependencies: OK')"
pytest -q
ruff check .
```

For the first EDA notebook, run it against a committed sample dataset, not directly against private Prometheus. A fresh Codespace should be able to reproduce the notebook output without VPS credentials.

Development previews, once those files exist:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
```

## 5. GitHub Flow for `feat/initial-eda`

The assignment requires GitHub Flow and a dedicated initial experiment branch. For a solo project, use one short-lived branch and one pull request:

```text
main
  └── feat/initial-eda
        ├── .devcontainer/devcontainer.json
        ├── requirements*.txt
        ├── notebooks/01_initial_eda.ipynb
        ├── reproducibility notes
        └── validation results
                 ↓
              Pull Request
                 ↓
       checks pass + results reviewed
                 ↓
          squash merge to main
```

Suggested commands:

```bash
git switch main
git pull --ff-only
git switch -c feat/initial-eda

# Add Codespaces configuration and the initial EDA.
git add .devcontainer requirements.txt requirements-dev.txt notebooks README.md
git commit -m "feat: add reproducible Codespaces EDA environment"
git push -u origin feat/initial-eda
```

The pull request should record:

- the dataset/commit used;
- the successful fresh-Codespace checks;
- missing-value and timestamp checks;
- basic distributions and correlations;
- observed scale-up/pod-startup timing if available;
- the proposed target, sample interval, feature window, and horizon;
- which conclusions are observations and which remain hypotheses.

Merge only after the notebook runs from top to bottom and the result is coherent. Delete the branch after merge. Keep later experiments in short-lived `experiment/<name>` branches and merge only selected code/configuration, not every generated artifact.

## 6. README Instructions Required by the LK

The repository README should contain, at minimum:

1. project purpose;
2. high-level architecture;
3. repository structure;
4. how to create and validate a Codespace;
5. how to run the initial EDA;
6. GitHub Flow convention;
7. a clear statement that Codespaces is not production;
8. links to the detailed documents.

Suggested README section:

````markdown
## Development with GitHub Codespaces

GitHub Codespaces provides the reproducible development environment for this
project. Production-experiment services run on the VPS/K3s cluster; a Codespace
is not used as a persistent runtime.

1. Open this repository on GitHub.
2. Select **Code → Codespaces → Create codespace on main**.
3. Wait for the `postCreateCommand` dependency installation to finish.
4. Validate the environment:

   ```bash
   python --version
   python -m pip check
   pytest -q
   ruff check .
   ```

5. Open `notebooks/01_initial_eda.ipynb`, select the Python 3.12 kernel, and run
   all cells against the committed sample dataset.

Use GitHub Flow for changes:

```bash
git switch -c feat/<short-name>
git push -u origin feat/<short-name>
```

Open a pull request, validate the result, and merge it into `main`. The required
initial EDA branch is `feat/initial-eda`.

Do not commit `.env` files, tokens, kubeconfigs, datasets managed by DVC, or
generated model artifacts.
````

## 7. Full VPS/K3s Deployment Architecture

### 7.1 End-to-end architecture

```text
                           EXTERNAL ENVIRONMENT

 React / Android users                     Laptop or dedicated k6 runner
          │                                             │
          └──────────────────┬──────────────────────────┘
                             │ HTTPS
                             ▼
                      api.titipin.me
                             │
                           Caddy
                             │
                             ▼
                    Kubernetes Service
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
             Laravel pod(s)     Laravel pod(s)
                 Worker 1           Worker 2
                    └────────┬────────┘
                             │ metrics
                             ▼
                        Prometheus
                ┌────────────┼──────────────┐
                │            │              │
                ▼            ▼              ▼
             Grafana    Ingestion Job   Feature/actual store
                                  │              │
                                  ▼              │
                         Validate + partition     │
                                  │              │
                                  ▼              │
                            DVC metadata          │
                                  │              │
                                  ▼              │
                       DVC remote / MinIO         │
                                  │              │
                                  ▼              │
                      Scheduled Training Job      │
                                  │              │
                                  ▼              │
                              MLflow              │
                    ┌─────────────┴──────────┐    │
                    ▼                        ▼    │
              Metadata database       Artifact store
                    │                        │
                    └─────────────┬──────────┘
                                  │ selected model alias/version
                                  ▼
                         FastAPI Inference
                                  │ forecast
                                  ▼
                    Predictive Scaler Service
                      shadow → manual → active
                                  │ limited RBAC
                                  ▼
                    Deployment `/scale` subresource
                                  │
                                  └──────────► Laravel replicas

 Prometheus ──► Drift/Error Monitor ──► Retraining decision ──► Training Job
      │                   │
      │                   └────────► drift/error metrics
      │
      ├────────► Grafana (infra/application/scaling)
      │
      └────────► FastAPI status endpoint ──► Streamlit ML dashboard
                                                │
                                                ▼
                                         mlops.titipin.me
```

### 7.2 Component responsibilities

| Component | Input | Output | Execution model |
|---|---|---|---|
| Caddy | Public HTTPS | Kubernetes backend/UI routes | Long-running |
| Laravel backend | Client/k6 requests | API responses and metrics | Long-running, scaled target |
| Prometheus | Scrape targets | Operational time series | Long-running |
| Grafana | Prometheus queries | Infrastructure/application dashboards | Long-running |
| Ingestion | Prometheus range queries | Validated, timestamped partitions | Scheduled job |
| DVC | Dataset paths and metadata | Dataset versions in object storage | CLI/job, not a server |
| MLflow | Training runs | Run metadata, metrics, artifacts, registered versions | Long-running tracking service plus client library |
| Training pipeline | Versioned data/config/code | Candidate model and evaluation | On-demand/scheduled job |
| FastAPI inference | Recent feature vector | Forecast, horizon, model version | Long-running |
| Predictive scaler | Forecast + capacity policy + current state | Recommended/applied replicas | Long-running |
| Drift/error monitor | Predictions, later actuals, reference window | Drift state, rolling error, retraining signal | Long-running or frequent CronJob |
| Retraining pipeline | Trigger + versioned data | Candidate model; promote/reject decision | Scheduled/on-demand job |
| Streamlit dashboard | Read-only status/history APIs | ML/scaler operator UI | Long-running for demo/operations |
| k6 | Scenario config | External controlled traffic and summary | On-demand outside cluster |
| GitHub Actions | Push/tag/manual/schedule event | Test, image build, deploy or job trigger | Event/schedule-driven |

### 7.3 Data and model traceability

Every model run should be traceable through:

```text
Git commit
  + dataset DVC revision
  + workload scenario / RUN_ID
  + Prometheus collection window
  + preprocessing and feature configuration
  + target and horizon
  + model parameters
  + evaluation metrics
  = MLflow run and registered model version
```

The inference response and dashboard must expose the selected model version and horizon. The scaler decision log must include the forecast, policy configuration, current replicas, recommended replicas, applied replicas, mode, and timestamp.

### 7.4 Scheduler and CI boundary

Use each scheduler for the job it can execute reliably:

- Kubernetes CronJob: ingestion, drift/error calculation, retention/cleanup, and cluster-local scheduled jobs.
- GitHub Actions: lint, tests, image builds, manifest validation, and controlled deployment triggers.
- Manual workflow dispatch: initial training, candidate promotion, and final experiment runs until automation is proven safe.

Do not make GitHub Actions the only owner of a high-frequency production loop. Do not make a Codespace responsible for any schedule.

### 7.5 Storage recommendation

Use separate logical storage even if one MinIO installation is shared initially:

```text
MinIO
├── titipin-app/             # Existing application objects
├── mlops-dvc/               # Versioned datasets
└── mlops-mlflow-artifacts/  # Models, plots, run artifacts
```

MLflow metadata belongs in a database, not only on a pod filesystem. DVC and MLflow objects must not live exclusively on worker ephemeral storage. Define retention, backup, and restore checks before calling the environment production-grade.

## 8. Development-Only vs Long-Running

### 8.1 Development-only or on-demand

- Codespaces and its forwarded ports;
- JupyterLab and notebooks;
- Ruff, pytest, interactive Python, and exploratory scripts;
- local FastAPI/Streamlit with reload enabled;
- `kubectl`/Helm clients on laptop or Codespaces;
- Docker builds and smoke containers;
- k6 workload runs;
- one-off DVC pull/push commands;
- EDA, training, evaluation, and promotion commands;
- database migration jobs.

### 8.2 Long-running services

- K3s control plane and workers;
- Caddy;
- Laravel backend and its required production dependencies;
- Prometheus and exporters;
- Grafana;
- MLflow tracking server and its metadata/artifact backends;
- FastAPI inference service;
- predictive scaler after shadow validation;
- model/scaler status API;
- Streamlit dashboard when the public/private operations UI is required;
- drift/error monitor if implemented as a service.

### 8.3 Scheduled rather than long-running

- Prometheus-to-dataset ingestion;
- dataset validation/partitioning;
- retraining trigger checks;
- training/retraining;
- cleanup and backups;
- repeatable comparison experiments.

## 9. ML Operations UI Design

### 9.1 Recommendation

Start with:

```text
FastAPI
├── /health       readiness/liveness only
├── /predict      internal inference contract
└── /status       read-only aggregate for the dashboard

Streamlit
└── renders /status plus short history queries
```

The Streamlit application must not load a second copy of business/scaling logic. It should render data returned by the API/Prometheus/MLflow adapters. This keeps the displayed recommendation identical to the scaler's recommendation.

Choose React only when the UI demonstrably needs richer routing, stronger frontend testing, complex authentication, or a polished multi-user interface. The current academic/demo scope does not justify a separate React build pipeline.

### 9.2 Dashboard layout

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Predictive Autoscaling                                             │
│ Mode: SHADOW   Model: workload-forecast v3   Updated: 12 s ago     │
├────────────┬────────────┬─────────────┬────────────┬────────────────┤
│ Prediction │ Actual     │ Horizon     │ Recent MAE │ Drift          │
│ 14.2 req/s │ 13.8 req/s │ 60 seconds  │ 1.1 req/s  │ Stable         │
├────────────┴────────────┴─────────────┴────────────┴────────────────┤
│ Actual vs predicted workload (time series)                         │
│                                                                     │
├──────────────────────────────────┬──────────────────────────────────┤
│ Recommended vs actual replicas   │ Latest scaler decision           │
│                                  │ current: 2, recommended: 3       │
│                                  │ applied: no (shadow mode)         │
├──────────────────────────────────┴──────────────────────────────────┤
│ Experiment / run                                                    │
│ RUN_ID, MLflow run, dataset version, Git commit, scenario           │
└─────────────────────────────────────────────────────────────────────┘
```

Example values above are illustrative only. The target and horizon remain open until EDA and startup-time measurements support a decision.

### 9.3 Required fields

| Field | Meaning | Source |
|---|---|---|
| Current prediction | Forecast for `issued_at + horizon` | Inference service |
| Actual | Observed value at the forecast target time; `null` until available | Prometheus/evaluation store |
| Actual vs predicted | Correctly time-aligned series | Evaluation store |
| Model version | Registered model name, alias/version, and load time | MLflow + inference |
| Horizon | Seconds between issue time and target time | Model metadata/config |
| Recent error | Rolling MAE/RMSE over completed forecasts | Error monitor |
| Drift status | `insufficient_data`, `stable`, `warning`, or `drifted` | Drift monitor |
| Recommended replicas | Policy output before mutation | Scaler |
| Actual replicas | Ready and desired replicas | Kubernetes/Prometheus |
| Scaler mode | `shadow`, `manual`, `active`, or `disabled` | Scaler config/status |
| Experiment/run | Workload `RUN_ID`, MLflow run, DVC revision, Git commit | Run metadata |
| Freshness | Age of latest metric, prediction, and decision | Each data source |

### 9.4 Suggested status contract

```json
{
  "observed_at": "2026-09-11T10:15:00Z",
  "target": "request_rate",
  "prediction": {
    "value": 14.2,
    "issued_at": "2026-09-11T10:14:00Z",
    "target_time": "2026-09-11T10:15:00Z",
    "horizon_seconds": 60
  },
  "actual": {
    "value": 13.8,
    "observed_at": "2026-09-11T10:15:00Z"
  },
  "model": {
    "name": "workload-forecast",
    "version": "3",
    "alias": "production",
    "mlflow_run_id": "example-run-id"
  },
  "quality": {
    "recent_mae": 1.1,
    "drift_status": "stable",
    "last_checked_at": "2026-09-11T10:15:00Z"
  },
  "scaling": {
    "mode": "shadow",
    "current_replicas": 2,
    "ready_replicas": 2,
    "recommended_replicas": 3,
    "applied_replicas": null,
    "reason": "forecast exceeds calibrated capacity for two replicas"
  },
  "experiment": {
    "run_id": "periodic-run-001",
    "scenario": "periodic",
    "dataset_revision": "example-dvc-revision",
    "git_commit": "example-git-sha"
  }
}
```

The final schema should use the real target and model metadata. Preserve `issued_at`, `target_time`, and `observed_at`; without them, the actual-vs-predicted chart can silently compare the wrong timestamps.

### 9.5 Failure and safety states

The UI must not present stale or incomplete data as healthy:

- show `actual = pending` until the forecast horizon has elapsed;
- show the age of the latest prediction and scaler decision;
- mark Prometheus, MLflow, Kubernetes, or inference data as unavailable independently;
- show when fallback/reactive HPA is active;
- distinguish `recommended` from `applied` replicas;
- make shadow/manual/active mode visually explicit;
- keep the dashboard read-only initially;
- never place a public “scale now” button in the first version.

## 10. Domain and Exposure Recommendation

Recommended public/private DNS layout:

| Name | Purpose | Exposure |
|---|---|---|
| `api.titipin.me` | Existing Laravel API | Public HTTPS |
| `grafana.titipin.me` | Infrastructure/application/scaling telemetry | Authenticated |
| `mlops.titipin.me` | Read-only Streamlit ML/scaler dashboard | Authenticated or restricted for the demo |
| MLflow service name inside K3s | Experiment tracking and registry | Cluster-private by default |
| Inference service name inside K3s | `/predict` for scaler/status service | Cluster-private by default |

Use `mlops.titipin.me` rather than `model.titipin.me` as the primary recommendation because the page represents more than a model: it includes drift, experiments, replica decisions, and operational state. `model.titipin.me` remains a reasonable alternative if the page is deliberately limited to prediction/model information.

Avoid adding public subdomains for MLflow and inference unless there is a demonstrated external consumer. If MLflow must be reachable from a laptop, prefer an SSH tunnel, VPN, or authenticated Caddy route. Do not expose the MLflow UI or mutation-capable inference/scaler endpoints anonymously.

## 11. Roadmap After Demo-Ready Infrastructure

The repository already contains workload scenarios and a first merged dataset, so the next work should begin at data validation and EDA rather than rebuilding the infrastructure.

### Phase 1 — Complete the LK reproducibility requirement

Deliver on `feat/initial-eda`:

- `.devcontainer/devcontainer.json`;
- exact, tested dependency pins;
- a clean fresh-Codespace validation;
- `notebooks/01_initial_eda.ipynb`;
- README Codespaces instructions;
- a pull request merged through GitHub Flow.

Exit condition: another person can create a fresh Codespace and run the initial EDA without laptop-specific steps.

### Phase 2 — Validate and version dataset v1

- define schema, units, UTC timestamp policy, sampling interval, missing-value policy, and duplicate policy;
- separate data artifacts from Python source code;
- initialize DVC;
- configure a dedicated object-storage remote;
- record scenario and collection metadata;
- enlarge the dataset beyond the short demo sample before drawing model conclusions.

Exit condition: one Git commit and DVC revision reproduce the same validated dataset.

### Phase 3 — EDA decision gate

- inspect coverage across steady, gradual, spike, periodic, and bursty regimes;
- verify request rate, CPU, latency, and replicas are aligned;
- measure pod startup and scaling delay;
- choose a provisional target, sample interval, feature window, and prediction horizon;
- document leakage prevention and chronological split boundaries.

Exit condition: decisions are supported by plots/statistics and recorded in `DECISIONS.md`.

### Phase 4 — Baseline before complex models

- persistence/last-value baseline;
- moving-average baseline;
- linear regression when useful;
- MAE/RMSE/MAPE plus operational usefulness;
- log run metadata consistently.

Exit condition: there is a minimum score that a nonlinear candidate must beat.

### Phase 5 — MLflow and candidate training

- deploy MLflow with a metadata database and object artifact store;
- log Git commit, DVC revision, features, target, horizon, scenario, parameters, metrics, and plots;
- train the provisional nonlinear candidate only after baselines;
- register candidates without automatic promotion.

Exit condition: a selected model version can be retrieved from MLflow and traced to code/data.

### Phase 6 — Inference and read-only UI

- define `/health`, `/predict`, and `/status` contracts;
- containerize FastAPI;
- load an explicit MLflow model alias/version;
- measure inference latency;
- deploy Streamlit at `mlops.titipin.me`;
- show the required model/scaler fields with freshness states.

Exit condition: the UI and API expose the same prediction/model metadata and survive a pod restart.

### Phase 7 — Predictive scaler safety progression

1. **Shadow:** calculate and log recommendations; never mutate replicas.
2. **Manual:** require explicit operator promotion/application.
3. **Active:** allow the service account to patch only the target deployment's `/scale` subresource.

Add bounds, cooldown, hysteresis if justified, stale-prediction handling, and fallback to the reactive baseline.

Exit condition: scaler failure cannot remove the reactive safety path or exceed configured min/max replicas.

### Phase 8 — Drift, error monitoring, and retraining

- join each prediction with its later actual value;
- calculate rolling error;
- select a drift technique using observed reference/recent windows;
- trigger retraining only with enough new validated data;
- evaluate a candidate against the current selected model;
- promote explicitly; reject without replacing the working model.

Exit condition: a failed candidate leaves the currently served model unchanged.

### Phase 9 — Final comparison experiment

Freeze:

- application image digest;
- Kubernetes requests/limits;
- HPA/scaler bounds and cooldowns;
- workload scripts and random inputs;
- dataset/model versions;
- experiment duration and Prometheus queries.

Run the same workloads for reactive HPA and predictive scaling. Compare p95/p99 latency, error rate, overload/SLO violations, time-to-scale, replica-seconds, CPU/memory, and forecast error. Do not claim predictive scaling is better unless these results support it.

## 12. LK Acceptance Checklist

### Repository initialization

- [ ] Repository is named `predictive-autoscaling-mlops` or follows the required `MLOps-[Topic]` naming accepted by the lecturer.
- [ ] Repository URL is accessible to the lecturer.
- [x] Python-oriented `.gitignore` exists.
- [x] License exists.
- [ ] README status is updated to match the actual demo-ready/data-collection phase.

### Codespaces reproducibility

- [ ] `.devcontainer/devcontainer.json` is committed.
- [ ] A fresh Codespace builds without manual OS setup.
- [ ] `python --version` reports Python 3.12.x.
- [ ] Python, Pylance, Jupyter, Ruff, and YAML extensions are installed automatically.
- [ ] Dependency files contain exact tested versions.
- [ ] `python -m pip check` passes.
- [ ] `pytest -q` passes, or the README explicitly states that no tests exist yet and provides a runnable data validation command.
- [ ] `ruff check .` passes.
- [ ] Initial EDA runs from top to bottom using committed sample data.
- [ ] No secret or production kubeconfig is committed.
- [ ] FastAPI/Streamlit ports, if used, default to private.

### Repository structure

- [ ] Dataset artifacts have a clear `data/` location and are separated from `src/data/` code.
- [ ] Model artifacts have a clear `models/` location and are separated from `src/models/` code.
- [x] `notebooks/`, `src/`, and `configs/` exist.
- [x] Infrastructure, pipelines, tests, and workload responsibilities are separated.
- [ ] Large datasets/models are ignored by Git and versioned through DVC/MLflow as appropriate.

### GitHub Flow

- [ ] `feat/initial-eda` is created from current `main`.
- [ ] Codespaces configuration and initial EDA are committed to that branch.
- [ ] The branch is pushed to GitHub.
- [ ] A pull request to `main` documents validation evidence.
- [ ] The notebook and automated checks pass before merge.
- [ ] The validated change is merged into `main`.

### README documentation

- [x] Project purpose is explained.
- [x] Initial repository structure is documented.
- [ ] Fresh Codespace creation and validation steps are documented.
- [ ] Initial EDA command/notebook is documented.
- [ ] GitHub Flow and `feat/initial-eda` are documented.
- [ ] README states that Codespaces is development-only and VPS/K3s is the production-experiment runtime.
- [ ] README links to this document.

### Evidence to submit or show

- [ ] GitHub repository URL.
- [ ] `.devcontainer/devcontainer.json` in `main` after merge.
- [ ] Screenshot or terminal output from a fresh Codespace showing Python 3.12 and successful validation.
- [ ] Pull request from `feat/initial-eda` to `main`.
- [ ] Initial EDA output.
- [ ] README Codespaces section.

## 13. Definition of Done for This Strategy

This environment strategy is implemented when:

```text
Fresh Codespace
   └── installs deterministic dependencies
       └── validates sample data and runs initial EDA
           └── changes flow through feat/initial-eda and a pull request

VPS/K3s
   └── remains the only long-running production-experiment runtime
       └── serves metrics, model, scaler, drift, and UI components

Laptop/external runner
   └── generates controlled k6 workload outside the cluster
```

## 14. References

- [GitHub Docs: Introduction to dev containers](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/introduction-to-dev-containers)
- [GitHub Docs: Setting up a Python project for GitHub Codespaces](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/setting-up-your-python-project-for-codespaces)
- [GitHub Docs: Configuring dev containers](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/configuring-dev-containers)
- [GitHub Docs: Security in GitHub Codespaces](https://docs.github.com/en/codespaces/reference/security-in-github-codespaces)
- [Development Containers: Features](https://containers.dev/features)
- [Development Containers: Development versus production](https://containers.dev/overview)
