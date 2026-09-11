# GitHub Codespaces Setup Guide

> **Role:** Reproducible development environment for EDA, notebooks, tests, and local service previews.
> The VPS/K3s cluster remains the only long-running production-experiment runtime.

---

## 1. Prerequisites

You only need a browser and a GitHub account with access to this repository.

For reference, VPS/K3s remains at:

| Node | Role | Public IP |
|---|---|---|
| VM-01 | K3s control plane | `16.79.90.160` |
| VM-02 | Worker 1 | `15.232.116.101` |
| VM-03 | Worker 2 | `15.232.71.54` |

---

## 2. Creating the Codespace

1. Open this repository on GitHub: `https://github.com/oktavsm/predictive-autoscaling-mlops`
2. Click **Code → Codespaces → Create codespace on `feat/initial-eda`**
   - Or use `main` after `feat/initial-eda` is merged.
3. Wait for the container to build (~2–4 minutes on first start).
   - The `postCreateCommand` in `.devcontainer/devcontainer.json` runs automatically:
     ```
     pip install --upgrade pip && pip install -r requirements-dev.txt
     ```
4. VS Code opens in the browser with Python 3.12, Jupyter, Ruff, Pylance, and YAML extensions installed automatically.

> **Note:** Forwarded ports 8000 (FastAPI) and 8501 (Streamlit) default to **private**.
> They are not reachable externally without sharing the forwarded URL manually.

---

## 3. Validate the Environment

Run these in the Codespace terminal immediately after creation to confirm everything is healthy:

```bash
python --version
# Expected: Python 3.12.x

python -m pip check
# Expected: No broken requirements

python -c "import pandas, requests, matplotlib, seaborn, sklearn; print('OK')"
# Expected: OK

pytest -q
# Expected: 8 passed

ruff check .
# Expected: All checks passed!
```

A fresh Codespace must pass all four checks using only committed files, without VPS credentials.

---

## 4. Running the Initial EDA Notebook

```bash
# Open notebooks/01_initial_eda.ipynb in VS Code
# Select kernel: Python 3.12 (base environment)
# Run All Cells — the notebook runs against src/data/demo_metrics.csv (committed sample data)
```

Do **not** run the notebook against live Prometheus in the initial EDA commit.
The committed `demo_metrics.csv` (284 observations) is sufficient for EDA, distributions, and correlations.

---

## 5. Optional: Connecting to the Live Cluster

The Codespace does **not** hold a kubeconfig by default. If you need cluster access from inside the Codespace (e.g., manifest validation), use a Codespace secret:

### 5.1 Export your local kubeconfig as a secret

```bash
# On your laptop:
cat ~/.kube/config | base64 -w 0
# Copy the output
```

1. Go to **GitHub → Settings → Codespaces → New secret**
2. Name: `KUBECONFIG_BASE64`
3. Repository access: `oktavsm/predictive-autoscaling-mlops`
4. Paste the base64 value

### 5.2 Restore inside the Codespace

```bash
mkdir -p ~/.kube
echo "$KUBECONFIG_BASE64" | base64 -d > ~/.kube/config
chmod 600 ~/.kube/config
kubectl get nodes
```

> **Security:** Never commit a kubeconfig to the repository. The `.gitignore` already excludes `*.kubeconfig` and `kubeconfig.yaml`.

---

## 6. Optional: Port-Forward Prometheus for Dataset Export

Prometheus is ClusterIP-only. To export additional data from the Codespace:

> Requires `KUBECONFIG_BASE64` secret (see Section 5).

```bash
# Restore kubeconfig (if not already done)
mkdir -p ~/.kube && echo "$KUBECONFIG_BASE64" | base64 -d > ~/.kube/config && chmod 600 ~/.kube/config

# Port-forward Prometheus
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090 &
PF_PID=$!

# Wait for it to be ready
sleep 3
curl -s http://localhost:9090/-/healthy && echo "Prometheus ready"

# Export dataset (last 60 minutes, 30s step)
export PROM_URL=http://localhost:9090
python scripts/export_dataset.py --minutes 60 --step 30

# Kill port-forward when done
kill $PF_PID
```

> **Note:** k6 load generation should NOT run from Codespace for benchmark evidence.
> Use your laptop (`k6 run workloads/k6/scenarios/steady.js`).
> Codespace may run a quick smoke test only.

---

## 7. Setting Up Secrets / Environment Variables

### Required for export scripts

```bash
# Inside Codespace terminal:
export PROM_URL=http://localhost:9090  # after port-forward is up
```

### For future MLOps phases

These variable names will be configured as Codespace secrets when the corresponding service is deployed:

| Variable | Phase | Where it points |
|---|---|---|
| `PROM_URL` | Now (via port-forward) | `http://localhost:9090` |
| `MLFLOW_TRACKING_URI` | Phase 5 | `http://<K3s-internal>:5000` (via tunnel) |
| `MODEL_STATUS_URL` | Phase 6 | `http://<K3s-internal>:8000/status` |
| `DVC_REMOTE_NAME` | Phase 2 | `mlops-dvc` (MinIO bucket) |
| `INFERENCE_API_URL` | Phase 6 | FastAPI cluster-internal URL |
| `SCALER_MODE` | Phase 7 | `shadow` / `manual` / `active` |

**Reminder:** Store real values in Codespace secrets or local `.env.*` files.
Never commit them. The `.gitignore` pattern `.env.*` (with `!.env.*.example` whitelist) is already in place.

---

## 8. What Codespace CAN and CANNOT Do

| Task | Codespace | Reason |
|---|---|---|
| EDA on committed dataset | ✅ | No credentials needed |
| Run pytest and ruff | ✅ | Pure Python, committed files |
| Preview FastAPI / Streamlit | ✅ | Private forwarded ports |
| Validate K8s manifests (`kubectl --dry-run`) | ✅ (with secret) | kubectl installed via Feature |
| Port-forward Prometheus for export | ✅ (with kubeconfig secret) | Only kubectl needed |
| Generate benchmark k6 load | ❌ | Must originate outside cluster (laptop) |
| Own production Prometheus data | ❌ | Authoritative data stays on VPS |
| Hold the production MLflow database | ❌ | VPS/K3s only |
| Run the predictive scaler | ❌ | VPS/K3s only |
| Stay online persistently | ❌ | Codespaces stop after inactivity |

---

## 9. GitHub Flow for `feat/initial-eda`

```bash
# Already on feat/initial-eda? Skip the first two lines.
git switch main
git switch -c feat/initial-eda

# Add Codespaces config, requirements, EDA notebook, and tests
git add .devcontainer requirements.txt requirements-dev.txt pyproject.toml \
        notebooks/01_initial_eda.ipynb tests/ docs/CODESPACE_SETUP.md
git commit -m "feat: add reproducible Codespaces EDA environment"
git push -u origin feat/initial-eda
```

Then open a Pull Request to `main` and document:

- Python version (`python --version` output)
- `pytest -q` output (all 8 tests passing)
- `ruff check .` output (all checks passed)
- Notebook ran top-to-bottom on committed dataset
- Key EDA observations (distributions, correlations, scaling delays)

Merge with **Squash and merge**, then delete the branch.

---

## 10. LK Checklist Covered by This Setup

| Item | Status |
|---|---|
| `.devcontainer/devcontainer.json` committed | ✅ |
| Fresh Codespace builds without manual OS setup | ✅ |
| `python --version` reports Python 3.12.x | ✅ |
| Jupyter, Pylance, Ruff, YAML extensions auto-installed | ✅ |
| Exact tested versions in `requirements*.txt` | ✅ |
| `python -m pip check` passes | ✅ |
| `pytest -q` passes on committed dataset | ✅ |
| `ruff check .` passes | ✅ |
| No secret or kubeconfig committed | ✅ |
| FastAPI/Streamlit ports default to private | ✅ |

---

## 11. References

- [GitHub Docs: Introduction to dev containers](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/introduction-to-dev-containers)
- [GitHub Docs: Setting up a Python project for Codespaces](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/adding-a-dev-container-configuration/setting-up-your-python-project-for-codespaces)
- [GitHub Docs: Codespaces secrets](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-encrypted-secrets-for-your-codespaces)
- See also: [`ENVIRONMENT_AND_DEPLOYMENT_STRATEGY.md`](ENVIRONMENT_AND_DEPLOYMENT_STRATEGY.md) — full strategy and component responsibilities
