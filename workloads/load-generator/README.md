# 🌐 Continuous Stochastic Workload Generator (cp-bcc VM)

Generator beban sintetis berkelanjutan (24/7) yang berjalan di remote VM `cp-bcc` untuk mensimulasikan trafik realistis ke `https://api.titipin.me`. 

Sistem ini menjamin grafik di Grafana selalu aktif, bergelombang natural, serta sesekali mengalami momen hening (*idle*) dan lonjakan mendadak (*flash-sale spike anomaly*).

---

## 🎲 State Machine & Karakteristik Trafik

| State | Rentang RPS | Rentang Durasi | Perilaku & Dampak pada Klaster |
|---|---|---|---|
| **`IDLE_SILENT`** | 0 – 1 RPS | 5 – 15 menit | Menyimulasikan malam hari / jam sepi. Grafik Grafana turun ke nol, pod Laravel turun ke 1 replika optimal. |
| **`STEADY_NORMAL`** | 4 – 12 RPS | 20 – 45 menit | Menyimulasikan trafik browsing santai pengguna harian. Grafik bergelombang halus, pod tetap 1 replika. |
| **`BURST_BUSY`** | 20 – 40 RPS | 10 – 20 menit | Menyimulasikan jam sibuk (siang / sore). Scaler mendeteksi kenaikan dan mulai mempersiapkan replika tambahan (2-3 pods). |
| **`FLASH_ANOMALY`** | 60 – 95 RPS | 3 – 8 menit | **ANOMALI**: Lonjakan tajam mendadak (flash sale / event viral). Predictive scaler langsung meramal lonjakan dan menaikkan pod ke **4 pods** secara proaktif. |
| **`COOLING_DOWN`** | 10 – 20 $\rightarrow$ 2 RPS | 5 – 10 menit | Periode pendinginan pasca-lonjakan. Grafana memperlihatkan cooldown 60 detik sebelum replika diturunkan bertahap. |

---

## ⚙️ Cara Mengelola Generator di VM `cp-bcc`

Masuk ke VM via SSH:
```bash
ssh cp-bcc
cd ~/titipin-traffic-generator
```

Gunakan skrip kontrol [`manage_generator.sh`](./manage_generator.sh):
```bash
# 1. Cek status service & state yang sedang aktif
./manage_generator.sh status

# 2. Pantau pergerakan trafik real-time
./manage_generator.sh logs

# 3. Paksa transisi ke lonjakan spike flash-sale sekarang juga
./manage_generator.sh trigger spike

# 4. Paksa transisi ke momen hening (0 request)
./manage_generator.sh trigger idle

# 5. Kembalikan ke trafik normal santai
./manage_generator.sh trigger steady

# 6. Menghentikan atau menyalakan service
./manage_generator.sh stop
./manage_generator.sh start
```
