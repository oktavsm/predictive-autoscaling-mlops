#!/usr/bin/env python3
"""
FinOps & Green Computing Resource Efficiency Calculator
======================================================
Evaluates cloud infrastructure cost savings, vCPU/RAM core-hour utilization,
and carbon footprint reduction (kg CO2e) comparing:
1. Static Over-provisioning (Fixed Max Capacity)
2. Kubernetes Reactive HPA Baseline
3. ML-Driven Predictive Autoscaler

Aligned with AI Governance, Resource Optimization & Sustainability standards.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FINOPS]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("finops")

# Hardware & AWS Pricing Reference (AWS EC2 us-east-1 / ap-southeast-3 standard)
CPU_REQUEST_CORES = 0.175  # 175m per pod
RAM_REQUEST_GB = 0.152     # 152 MiB per pod
HOURS_PER_MONTH = 720.0    # 30 days * 24 hours
USD_TO_IDR = 15800.0       # Exchange rate

# AWS Compute Cost Estimation (t3.medium base equivalent ~$0.0416/hr for 2vCPU, 4GB RAM)
COST_PER_VCPU_HOUR_USD = 0.0175
COST_PER_GB_RAM_HOUR_USD = 0.0022

# Carbon Footprint Coefficients (Cloud Carbon Footprint standard for AWS ap-southeast-3)
# ~0.000378 metric tons CO2e per kWh; server power ~3.5W per idle vCPU, 10.5W under load
KG_CO2_PER_VCPU_HOUR = 0.0042


class FinOpsCalculator:
    """Computes infrastructure cost and environmental footprint models."""

    def __init__(
        self,
        hours_analyzed: float = HOURS_PER_MONTH,
        max_pods: int = 6,
        reactive_avg_pods: float = 2.8,
        predictive_avg_pods: float = 1.6,
    ):
        self.hours = hours_analyzed
        self.max_pods = float(max_pods)
        self.reactive_avg = float(reactive_avg_pods)
        self.predictive_avg = float(predictive_avg_pods)

    def _calculate_strategy(self, avg_pods: float, name: str) -> Dict[str, Any]:
        vcpu_hours = avg_pods * CPU_REQUEST_CORES * self.hours
        ram_gb_hours = avg_pods * RAM_REQUEST_GB * self.hours

        cost_vcpu = vcpu_hours * COST_PER_VCPU_HOUR_USD
        cost_ram = ram_gb_hours * COST_PER_GB_RAM_HOUR_USD
        total_usd = cost_vcpu + cost_ram
        total_idr = total_usd * USD_TO_IDR

        carbon_kg = vcpu_hours * KG_CO2_PER_VCPU_HOUR

        return {
            "strategy": name,
            "avg_replicas": round(avg_pods, 2),
            "vcpu_hours": round(vcpu_hours, 2),
            "ram_gb_hours": round(ram_gb_hours, 2),
            "monthly_cost_usd": round(total_usd, 2),
            "monthly_cost_idr": round(total_idr, 0),
            "carbon_kg_co2e": round(carbon_kg, 2),
        }

    def evaluate_all(self) -> Dict[str, Any]:
        static_res = self._calculate_strategy(self.max_pods, "Static Over-Provisioning (Always 6 Pods)")
        reactive_res = self._calculate_strategy(self.reactive_avg, "Reactive HPA Baseline")
        predictive_res = self._calculate_strategy(self.predictive_avg, "ML Predictive Autoscaling")

        # Savings vs Static
        usd_saved_vs_static = static_res["monthly_cost_usd"] - predictive_res["monthly_cost_usd"]
        pct_saved_vs_static = (usd_saved_vs_static / static_res["monthly_cost_usd"]) * 100.0
        carbon_saved_vs_static = static_res["carbon_kg_co2e"] - predictive_res["carbon_kg_co2e"]

        # Savings vs Reactive
        usd_saved_vs_reactive = reactive_res["monthly_cost_usd"] - predictive_res["monthly_cost_usd"]
        pct_saved_vs_reactive = (usd_saved_vs_reactive / reactive_res["monthly_cost_usd"]) * 100.0
        carbon_saved_vs_reactive = reactive_res["carbon_kg_co2e"] - predictive_res["carbon_kg_co2e"]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evaluation_period_hours": self.hours,
            "strategies": {
                "static": static_res,
                "reactive": reactive_res,
                "predictive": predictive_res,
            },
            "comparative_analysis": {
                "vs_static": {
                    "monthly_savings_usd": round(usd_saved_vs_static, 2),
                    "monthly_savings_idr": round(usd_saved_vs_static * USD_TO_IDR, 0),
                    "cost_reduction_pct": round(pct_saved_vs_static, 1),
                    "carbon_avoidance_kg_co2e": round(carbon_saved_vs_static, 2),
                },
                "vs_reactive": {
                    "monthly_savings_usd": round(usd_saved_vs_reactive, 2),
                    "monthly_savings_idr": round(usd_saved_vs_reactive * USD_TO_IDR, 0),
                    "cost_reduction_pct": round(pct_saved_vs_reactive, 1),
                    "carbon_avoidance_kg_co2e": round(carbon_saved_vs_reactive, 2),
                },
            },
        }


def generate_markdown_report(data: Dict[str, Any], output_path: str) -> None:
    st = data["strategies"]
    comp = data["comparative_analysis"]

    md = f"""# Analisis FinOps & Green Computing: Efisiensi Biaya & Karbon
## Tata Kelola AI Berkelanjutan (*Sustainable MLOps & Resource Optimization*)

> **Periode Evaluasi:** 1 Bulan Kalender (720 Jam Operasional)  
> **Spesifikasi Pod:** 175m vCPU & 152 MiB RAM per instance PHP-FPM / Laravel  
> **Standar Kurs:** 1 USD = Rp {USD_TO_IDR:,.0f} IDR  

---

## 📊 1. Matriks Perbandingan Biaya Infrastruktur Bulanan

| Strategi Penskalaan Klaster | Rata-rata Replika | vCPU-Hours | RAM GB-Hours | Biaya Bulanan (USD) | Biaya Bulanan (IDR) | Emisi Karbon (kg CO₂e) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Static Over-Provisioning** *(Always 6 Pods)* | `6.0 Pods` | `{st['static']['vcpu_hours']:,.1f}` | `{st['static']['ram_gb_hours']:,.1f}` | **${st['static']['monthly_cost_usd']:,.2f}** | **Rp {st['static']['monthly_cost_idr']:,.0f}** | `{st['static']['carbon_kg_co2e']:.2f} kg` |
| **Reactive HPA** *(Bawaan Kubernetes)* | `2.8 Pods` | `{st['reactive']['vcpu_hours']:,.1f}` | `{st['reactive']['ram_gb_hours']:,.1f}` | **${st['reactive']['monthly_cost_usd']:,.2f}** | **Rp {st['reactive']['monthly_cost_idr']:,.0f}** | `{st['reactive']['carbon_kg_co2e']:.2f} kg` |
| **ML Predictive Autoscaler** *(Proaktif)* | `1.6 Pods` | `{st['predictive']['vcpu_hours']:,.1f}` | `{st['predictive']['ram_gb_hours']:,.1f}` | **${st['predictive']['monthly_cost_usd']:,.2f}** | **Rp {st['predictive']['monthly_cost_idr']:,.0f}** | **{st['predictive']['carbon_kg_co2e']:.2f} kg** |

---

## 🏆 2. Kuantifikasi Penghematan FinOps

### A. Dibandingkan Static Over-Provisioning (Alokasi Statis Maksimum):
* 📉 **Penurunan Biaya Komputasi:** **{comp['vs_static']['cost_reduction_pct']}% Lebih Hemat**
* 💵 **Uang yang Dihemat per Bulan:** **${comp['vs_static']['monthly_savings_usd']:.2f}** (atau setara **Rp {comp['vs_static']['monthly_savings_idr']:,.0f}**)
* 🌱 **Pengurangan Jejak Karbon:** **{comp['vs_static']['carbon_avoidance_kg_co2e']:.2f} kg CO₂e / bulan**

### B. Dibandingkan Reactive HPA (Penskalaan Reaktif Standar):
* 📉 **Penurunan Biaya Tambahan:** **{comp['vs_reactive']['cost_reduction_pct']}% Lebih Efisien**
* 💵 **Uang yang Dihemat per Bulan:** **${comp['vs_reactive']['monthly_savings_usd']:.2f}** (atau setara **Rp {comp['vs_reactive']['monthly_savings_idr']:,.0f}**)
* 🌱 **Pengurangan Jejak Karbon:** **{comp['vs_reactive']['carbon_avoidance_kg_co2e']:.2f} kg CO₂e / bulan**

---

## 🔍 3. Mengapa Predictive Autoscaling Lebih Hemat daripada Reactive HPA?

1. **Anti-Osilasi Cooldown yang Terukur:**  
   Reactive HPA cenderung lambat melakukan *scale-down* (default K8s stabilisasi 5 menit), sehingga pod berlebih tetap menyala dan membakar biaya komputasi jauh setelah lonjakan trafik mereda.
2. **Right-Sizing Presisi Berbasis Beban Aktual:**  
   Model ML memprediksi kebutuhan kapasitas secara adaptif sesuai *request rate* (RPS), menjaga klaster tetap berada di batas minimum 1 Pod selama periode sepi/malam hari (*idle hours*).
3. **Penyelarasan Prinsip Green Computing & Sustainability:**  
   Pengurangan penggunaan *vCPU-hours* secara langsung berkontribusi pada penurunan konsumsi listrik datacenter AWS dan pemenuhan target *sustainable AI governance*.
"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
    logger.info("FinOps markdown report saved to %s", output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="FinOps & Cost Efficiency Calculator")
    parser.add_argument("--max-pods", type=int, default=6)
    parser.add_argument("--reactive-avg", type=float, default=2.8)
    parser.add_argument("--predictive-avg", type=float, default=1.6)
    parser.add_argument("--output-json", default="docs/coursework/FINOPS_COST_ANALYSIS.json")
    parser.add_argument("--output-md", default="docs/FINOPS_DAN_COST_EFFICIENCY.md")
    args = parser.parse_args()

    calc = FinOpsCalculator(
        max_pods=args.max_pods,
        reactive_avg_pods=args.reactive_avg,
        predictive_avg_pods=args.predictive_avg,
    )
    res = calc.evaluate_all()

    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    logger.info("FinOps JSON output written to %s", args.output_json)

    generate_markdown_report(res, args.output_md)


if __name__ == "__main__":
    main()
