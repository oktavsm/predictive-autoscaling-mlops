#!/usr/bin/env python3
"""
Streamlit Control Dashboard — Predictive Autoscaling MLOps
==========================================================
Antarmuka visual interaktif untuk demonstrasi inferensi model prediktif,
simulasi penskalaan pod Kubernetes (HPA), inspeksi silsilah data DVC,
dan pemantauan status microservices.
"""

import os
import time

import requests
import streamlit as st

# Configuration
INFERENCE_API_URL = os.getenv("INFERENCE_API_URL", "http://localhost:8000")
MLFLOW_URL = os.getenv("MLFLOW_URL", "http://localhost:5000")
MINIO_URL = os.getenv("MINIO_URL", "http://localhost:9001")

st.set_page_config(
    page_title="Predictive Autoscaler MLOps Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚡ Predictive Horizontal Pod Autoscaler — Control Center")
st.markdown(
    """
    Sistem manajemen beban kerja cerdas berbasis pembelajaran mesin untuk mengantisipasi
    lonjakan trafik (*traffic spikes*) pada klaster Kubernetes k3s sebelum latensi terdegradasi.
    """
)

# Sidebar: System Links & Navigation
with st.sidebar:
    st.header("🌐 Quick Navigation")
    st.markdown(f"**Inference API:** [`:8000/docs`]({INFERENCE_API_URL}/docs)")
    st.markdown(f"**MLflow Tracking:** [`:5000`]({MLFLOW_URL})")
    st.markdown(f"**MinIO Console:** [`:9001`]({MINIO_URL})")
    st.markdown("**Public Domain:** [mlops.titipin.me](https://mlops.titipin.me)")
    st.divider()

    st.subheader("⚙️ Scaling Target Policy")
    target_capacity = st.number_input("Target RPS per Pod", value=10.0, step=1.0)
    min_pods = st.number_input("Min Replicas", value=1, step=1)
    max_pods = st.number_input("Max Replicas", value=4, step=1)
    st.caption("Konfigurasi kapasitas pod PHP-FPM WordPress.")

# Service Health Check
health_data = {}
try:
    resp = requests.get(f"{INFERENCE_API_URL}/health", timeout=2)
    if resp.status_code == 200:
        health_data = resp.json()
except Exception:
    pass

col_h1, col_h2, col_h3, col_h4 = st.columns(4)
with col_h1:
    is_up = health_data.get("status") == "healthy"
    st.metric(
        "Inference Service",
        "ONLINE" if is_up else "DEGRADED",
        delta="Normal" if is_up else "Check API",
    )
with col_h2:
    st.metric(
        "Active Model",
        health_data.get("model_name", "predictive-autoscaler"),
        f"@{health_data.get('model_alias', 'champion')}",
    )
with col_h3:
    st.metric(
        "Model Load Time", f"{health_data.get('load_time_ms', 0):.1f} ms", delta="Memory Cached"
    )
with col_h4:
    st.metric("Replica Bounds", f"{min_pods} - {max_pods} Pods", f"{target_capacity} RPS/Pod")

st.divider()

# Tabs
tab_sim, tab_model, tab_k8s = st.tabs(
    ["🎮 Traffic & Scaling Simulator", "📦 Model Registry & Lineage", "☸️ Kubernetes Architecture"]
)

with tab_sim:
    st.subheader("Simulasi Beban Kerja & Rekomendasi Penskalaan Pod")

    # Quick scenario buttons
    col_b1, col_b2, col_b3 = st.columns(3)
    if col_b1.button("🟢 Skenario Normal (15 RPS)"):
        st.session_state["cur_rps"] = 15.2
        st.session_state["cur_cpu"] = 0.35
        st.session_state["cur_p95"] = 0.045
        st.session_state["cur_mem"] = 120.0
    if col_b2.button("🔴 Skenario Lonjakan Mendadak (35 RPS)"):
        st.session_state["cur_rps"] = 35.8
        st.session_state["cur_cpu"] = 0.85
        st.session_state["cur_p95"] = 0.120
        st.session_state["cur_mem"] = 165.0
    if col_b3.button("🌙 Skenario Jam Tenang (2 RPS)"):
        st.session_state["cur_rps"] = 2.1
        st.session_state["cur_cpu"] = 0.05
        st.session_state["cur_p95"] = 0.020
        st.session_state["cur_mem"] = 95.0

    col_inp1, col_inp2 = st.columns(2)
    with col_inp1:
        req_rate = st.slider(
            "Current Request Rate (RPS)", 0.0, 50.0, st.session_state.get("cur_rps", 15.0), step=0.5
        )
        cpu_cores = st.slider(
            "PHP-FPM CPU Usage (Cores)", 0.0, 2.0, st.session_state.get("cur_cpu", 0.35), step=0.05
        )
    with col_inp2:
        p95_lat = st.slider(
            "P95 Latency (Seconds)",
            0.005,
            0.500,
            st.session_state.get("cur_p95", 0.045),
            step=0.005,
        )
        mem_mb = st.slider(
            "Memory Footprint (MB)", 50.0, 400.0, st.session_state.get("cur_mem", 120.0), step=5.0
        )

    # Trigger Inference
    if st.button("🚀 Prediksi Beban t+60s & Hitung Rekomendasi Pod", type="primary"):
        payload = {
            "request_rate": req_rate,
            "php_cpu_cores": cpu_cores,
            "p95_latency_seconds": p95_lat,
            "php_memory_mb": mem_mb,
            "rps_lag1": req_rate * 0.95,
            "rps_lag2": req_rate * 0.90,
            "cpu_lag1": cpu_cores * 0.95,
            "cpu_lag2": cpu_cores * 0.90,
            "rps_roll_mean_60s": req_rate,
            "rps_roll_std_60s": 0.5,
            "rps_delta": 0.2,
            "cpu_delta": 0.01,
        }

        try:
            t0 = time.perf_counter()
            pred_resp = requests.post(f"{INFERENCE_API_URL}/predict", json=payload, timeout=3)
            client_lat_ms = (time.perf_counter() - t0) * 1000.0

            if pred_resp.status_code == 200:
                result = pred_resp.json()
                pred_rps = result["predicted_workload_rps_60s"]
                rec_pods = result["recommended_replicas"]
                action = result["scaling_action"]
                server_lat_ms = result["inference_latency_ms"]

                st.success("Inferensi Model Berhasil!")

                col_res1, col_res2, col_res3, col_res4 = st.columns(4)
                with col_res1:
                    st.metric(
                        "Predicted Workload (t+60s)",
                        f"{pred_rps:.2f} RPS",
                        delta=f"{pred_rps - req_rate:+.2f} RPS",
                    )
                with col_res2:
                    st.metric("Recommended Pods", f"{rec_pods} Pods", delta=f"{action}")
                with col_res3:
                    st.metric(
                        "Target Total Capacity",
                        f"{rec_pods * target_capacity:.0f} RPS",
                        "Safe Headroom",
                    )
                with col_res4:
                    st.metric(
                        "Inference Latency",
                        f"{server_lat_ms:.1f} ms",
                        f"Client: {client_lat_ms:.1f} ms",
                    )

                st.subheader("Status Visual Alokasi Pod Kubernetes")
                cols_pods = st.columns(4)
                for i in range(4):
                    with cols_pods[i]:
                        if i < rec_pods:
                            st.info(
                                f"🟢 **Pod {i + 1}**: RUNNING\n\nKapasitas: {target_capacity} RPS"
                            )
                        else:
                            st.write(f"⚪ *Pod {i + 1}*: IDLE / SCALED DOWN")

                with st.expander("Lihat Respons JSON Lengkap"):
                    st.json(result)
            else:
                st.error(f"Inference error ({pred_resp.status_code}): {pred_resp.text}")
        except Exception as e:
            st.error(f"Gagal menghubungi inference API di {INFERENCE_API_URL}: {e}")

with tab_model:
    st.subheader("Model Registry & Silsilah Data (Data Lineage)")
    st.markdown(
        """
        Model prediktif dikelola secara terpusat melalui **MLflow Model Registry** dengan transisi
        siklus hidup otomatis (*lifecycle stages*) dan pelacakan silsilah dataset berbasis **DVC**.
        """
    )

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("### 🏆 Champion Model (Version 2)")
        st.markdown("- **Arsitektur:** Random Forest Regressor (`n_estimators=100`, `max_depth=6`)")
        st.markdown("- **Validation MAE:** **`0.0295 RPS`** (Galat terendah)")
        st.markdown("- **Validation RMSE:** `0.1523`")
        st.markdown("- **Status:** `Production` / `@champion` (Melayani inferensi langsung)")
        st.markdown("- **Silsilah DVC:** Dataset Tag `v2.0-data`")

    with col_m2:
        st.markdown("### 🥈 Challenger Model (Version 1)")
        st.markdown("- **Arsitektur:** LightGBM Regressor (`learning_rate=0.05`)")
        st.markdown("- **Validation MAE:** `0.1246 RPS`")
        st.markdown("- **Validation RMSE:** `0.2745`")
        st.markdown("- **Latensi Inferensi:** `3.06 ms` (Ultra-low latency)")
        st.markdown("- **Status:** `Staging` / `@challenger`")
        st.markdown("- **Silsilah DVC:** Dataset Tag `v1.0-data`")

    st.info(
        "Penyimpanan artefak model dan silsilah dataset terhubung ke MinIO S3 (`storage.titipin.me/mlops-dvc`)."
    )

with tab_k8s:
    st.subheader("Arsitektur Deployment Kubernetes k3s")
    st.markdown(
        """
        Integrasi autoscaling beroperasi pada klaster **Kubernetes k3s** lingkungan live AWS:
        - **Workload Target:** `wordpress-fpm` (PHP-FPM container)
        - **Metrik Telemetri:** Diekstrak dari Prometheus Operator setiap 15 detik
        - **Anticipatory Horizon:** Model memprediksi beban 60 detik sebelum puncak trafik tiba
        - **Aksi Kontroler:** Mengatur skala replika pod antara 1 hingga 4 pods melalui endpoint `/scale-decision`
        """
    )
    st.code(
        """
+-----------------------+      +---------------------------+      +---------------------------+
| Prometheus Telemetry  | ---> | Predictive Inference API  | ---> | Kubernetes Custom HPA     |
| (RPS, CPU, Latency)   |      | (mlops-inference-api:8000)|      | (wordpress-fpm Deployment)|
+-----------------------+      +---------------------------+      +---------------------------+
        """,
        language="text",
    )
