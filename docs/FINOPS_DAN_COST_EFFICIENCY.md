# Analisis FinOps & Green Computing: Efisiensi Biaya & Karbon
## Tata Kelola AI Berkelanjutan (*Sustainable MLOps & Resource Optimization*)

> **Periode Evaluasi:** 1 Bulan Kalender (720 Jam Operasional)  
> **Spesifikasi Pod:** 175m vCPU & 152 MiB RAM per instance PHP-FPM / Laravel  
> **Standar Kurs:** 1 USD = Rp 15,800 IDR  

---

## 📊 1. Matriks Perbandingan Biaya Infrastruktur Bulanan

| Strategi Penskalaan Klaster | Rata-rata Replika | vCPU-Hours | RAM GB-Hours | Biaya Bulanan (USD) | Biaya Bulanan (IDR) | Emisi Karbon (kg CO₂e) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Static Over-Provisioning** *(Always 6 Pods)* | `6.0 Pods` | `756.0` | `656.6` | **$14.67** | **Rp 231,859** | `3.18 kg` |
| **Reactive HPA** *(Bawaan Kubernetes)* | `2.8 Pods` | `352.8` | `306.4` | **$6.85** | **Rp 108,201** | `1.48 kg` |
| **ML Predictive Autoscaler** *(Proaktif)* | `1.6 Pods` | `201.6` | `175.1` | **$3.91** | **Rp 61,829** | **0.85 kg** |

---

## 🏆 2. Kuantifikasi Penghematan FinOps

### A. Dibandingkan Static Over-Provisioning (Alokasi Statis Maksimum):
* 📉 **Penurunan Biaya Komputasi:** **73.3% Lebih Hemat**
* 💵 **Uang yang Dihemat per Bulan:** **$10.76** (atau setara **Rp 170,008**)
* 🌱 **Pengurangan Jejak Karbon:** **2.33 kg CO₂e / bulan**

### B. Dibandingkan Reactive HPA (Penskalaan Reaktif Standar):
* 📉 **Penurunan Biaya Tambahan:** **42.9% Lebih Efisien**
* 💵 **Uang yang Dihemat per Bulan:** **$2.94** (atau setara **Rp 46,452**)
* 🌱 **Pengurangan Jejak Karbon:** **0.63 kg CO₂e / bulan**

---

## 🔍 3. Mengapa Predictive Autoscaling Lebih Hemat daripada Reactive HPA?

1. **Anti-Osilasi Cooldown yang Terukur:**  
   Reactive HPA cenderung lambat melakukan *scale-down* (default K8s stabilisasi 5 menit), sehingga pod berlebih tetap menyala dan membakar biaya komputasi jauh setelah lonjakan trafik mereda.
2. **Right-Sizing Presisi Berbasis Beban Aktual:**  
   Model ML memprediksi kebutuhan kapasitas secara adaptif sesuai *request rate* (RPS), menjaga klaster tetap berada di batas minimum 1 Pod selama periode sepi/malam hari (*idle hours*).
3. **Penyelarasan Prinsip Green Computing & Sustainability:**  
   Pengurangan penggunaan *vCPU-hours* secara langsung berkontribusi pada penurunan konsumsi listrik datacenter AWS dan pemenuhan target *sustainable AI governance*.
