# ==============================================================================
# Dockerfile — Predictive Horizontal Pod Autoscaler Inference Service
# ==============================================================================
# Produces an optimized, lightweight container running FastAPI + MLflow pyfunc
# for anticipatory pod autoscaling inference on Kubernetes k3s.
# ==============================================================================

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime Stage
FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV MLFLOW_TRACKING_URI=sqlite:////app/mlflow.db
ENV MODEL_NAME=predictive-autoscaler
ENV MODEL_ALIAS=champion

# Copy codebase, models, tracking sqlite, and artifacts
COPY src/ /app/src/
COPY models/ /app/models/
COPY mlflow.db /app/mlflow.db
COPY mlruns/ /app/mlruns/

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "src.inference.service:app", "--host", "0.0.0.0", "--port", "8000"]
