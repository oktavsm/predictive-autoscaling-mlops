# Panduan Lengkap Silsilah Data DVC & MinIO S3 Storage
## Arsitektur Content-Addressable Storage (CAS), Hash MD5, & Alur Versioning

Dokumen ini menjelaskan arsitektur penyimpanan dataset **Predictive Autoscaling MLOps**, mekanisme Content-Addressable Storage (CAS) pada MinIO S3, integritas hash MD5, serta cara kerja pelacakan silsilah (*data lineage*) dan *time-travel versioning*.

---

## 🔍 1. Prinsip Content-Addressable Storage (CAS) di MinIO S3

> **Pertanyaan Umum / FAQ:**  
> *"Mengapa di dalam bucket `mlops-dvc` pada MinIO S3 tidak ditemukan struktur folder konvensional berisi file `.csv`, melainkan direktori seperti `6b/`, `b7/`, `70/` dengan nama file berupa hash panjang? Di mana data aslinya dan bagaimana versioning-nya bekerja?"*

### 💡 Penjelasan Arsitektur Sistem:
MinIO dalam arsitektur MLOps ini berfungsi sebagai **Remote Cache DVC (Data Version Control)** yang mengadopsi mekanisme **Content-Addressable Storage (CAS)**. Ini adalah **standar industri yang sama persis dengan cara kerja Git**:

1. **Analogi dengan Git:**  
   Ketika Anda melakukan `git commit` pada file `app.py`, Git **tidak** menyimpan file bernama `app.py` di dalam `.git/objects/`. Sebaliknya, Git menghitung hash SHA-1 dari isinya dan menyimpannya sebagai objek blob seperti `.git/objects/1a/6f958...`.  
2. **Penerapan pada DVC & MinIO S3:**  
   DVC memperlakukan MinIO S3 persis seperti Git memperlakukan `.git/objects/`:
   * Setiap file CSV dihitung nilai *fingerprint* uniknya menggunakan **MD5 Checksum** 32-karakter heksadesimal.
   * File data biner di-upload ke MinIO dengan nama hash MD5 tersebut di path `s3://mlops-dvc/files/md5/{2-karakter-pertama}/{sisa-hash}`.
3. **Mengapa Harus Berupa Hash MD5?**
   * **Integritas Data Mutlak (*Data Integrity & Immutability*):** Jika ada seseorang atau virus yang mengubah 1 baris angka di dalam file CSV, nilai MD5-nya akan langsung berubah. DVC akan menolak data tersebut karena tidak cocok dengan hash yang tercatat di Git.
   * **Deduplikasi Cerdas (*Deduplication*):** Jika ada 5 model berbeda menggunakan dataset 500 MB yang sama, DVC hanya mengunggah file tersebut 1 kali ke MinIO, menghemat kapasitas penyimpanan S3 secara drastis.
   * **Mencegah Repositori Membengkak (*Zero Git Bloat*):** File CSV berukuran ratusan Megabyte tidak disimpan di GitHub, melainkan di MinIO. GitHub hanya menyimpan file pointer teks berukuran beberapa Byte (`data/processed.dvc`).

---

## 🗺️ 2. Hubungan Segitiga: Git ↔ DVC Pointer ↔ MinIO S3 ↔ Workspace Lokal

```
    [ GitHub Repository ]
      ├─ Tag: v1.0-data
      ├─ Tag: v2.0-data
      └─ File Pointer Teks:
         ├─ data/raw.dvc       (Berisi hash: b72a5376a58b361528b426d5270e6b57.dir)
         └─ data/processed.dvc (Berisi hash: 6bb279246f63ba1bc8dc0356c8ec417b.dir)
                │
                ▼ (Mencocokkan Hash MD5)
    [ MinIO Object Storage S3 ] (https://minio.titipin.me / bucket: mlops-dvc)
      └─ files/md5/
         ├─ 6b/b279246f63ba1bc8dc0356c8ec417b.dir  <-- Kamus Mapping File CSV
         ├─ 4a/ec50d2130dd676189c7192eb66a078      <-- Objek Data Biner CSV
         ├─ eb/fb3759b7a425af052f5e73e2e4a072      <-- Objek Data Biner CSV
         └─ 70/caf5ea7e6f4e72243ecd8a15e8f4e5      <-- Objek Data Biner CSV
                │
                ▼ (Diekstrak oleh perintah: dvc pull / dvc checkout)
    [ Workspace Lokal Mahasiswa ]
      ├─ data/raw/
      │   ├─ metrics_20260928_102236.csv
      │   ├─ metrics_gradual_20260924_001.csv
      │   └─ metrics_periodic_20260924_001.csv
      └─ data/processed/
          ├─ metrics_demo_processed.csv       (51 KB, 250 baris data latih)
          ├─ metrics_flashsale_drifted.csv    (35 KB, data simulasi lonjakan beban)
          └─ metrics_processed_20260928.csv   (34 KB, data telemetri bersih)
```

---

## 📑 3. Tabel Pemetaan Resmi File CSV Asli vs Hash MD5 di MinIO

Di dalam file pointer DVC directory (`.dir`), DVC menyimpan kamus mapping JSON yang menghubungkan nama file yang dapat dibaca manusia dengan hash MD5 di MinIO:

| Nama File CSV di Workspace Lokal | Letak Folder | Hash MD5 di MinIO S3 | Ukuran | Deskripsi & Versi |
|:---|:---:|:---:|:---:|:---|
| **`metrics_gradual_20260924_001.csv`** | `data/raw/` | `b4d0a70e7115a4e4c370909ba364518b` | 4.8 KB | Telemetri mentah uji sequence awal (`v1.0-data`) |
| **`metrics_processed_20260927_132354.csv`** | `data/processed/` | `4aec50d2130dd676189c7192eb66a078` | 12.8 KB | Data latih model generasi awal (`v1.0-data`) |
| **`metrics_20260928_102236.csv`** | `data/raw/` | `b7dccb5bfc334d2647218067177aeb4e` | 21.6 KB | Batch data baru continual learning (`v2.0-data`) |
| **`metrics_demo_processed.csv`** | `data/processed/` | `5a8e0291dfbb38ac471029cba8d19321` | 51.5 KB | Dataset latih baseline model Champion (`v2.0-data`) |
| **`metrics_flashsale_drifted.csv`** | `data/processed/` | `70caf5ea7e6f4e72243ecd8a15e8f4e5` | 35.9 KB | Dataset lonjakan flash-sale (Champion v8) |

> 📌 **Bukti File Kamus Mapping di Repositori:**  
> Buka berkas cache: `.dvc/cache/files/md5/6b/b279246f63ba1bc8dc0356c8ec417b.dir`.  
> Isinya adalah array JSON:  
> `[{"md5": "4aec50d2130dd...", "relpath": "metrics_processed_20260927_132354.csv"}, ...]`

---

## ⚡ 4. Verifikasi Time-Travel Versioning Data

DVC dan Git memungkinkan reproduktibilitas dataset dua arah (*Time Travel Data Versioning*):

### A. Memeriksa Versi 1.0 (Baseline Awal):
```bash
# Pindah ke versi data 1.0 di Git
git checkout v1.0-data

# Periksa hash DVC yang aktif
cat data/processed.dvc
# Hasil: outs md5 = 81228fb7720d0e37aa589d98fe4356e5.dir

# Pulihkan kondisi file data versi 1.0 secara instan
dvc checkout
```
*Folder `data/` akan kembali persis ke kondisi awal proyek (3 file processed).*

---

### B. Beralih ke Versi 2.0 (Continual Learning dengan Batch Baru):
```bash
# Pindah ke versi data 2.0 di Git
git checkout v2.0-data

# Periksa hash DVC yang aktif
cat data/processed.dvc
# Hasil: outs md5 = 6bb279246f63ba1bc8dc0356c8ec417b.dir

# Pulihkan kondisi file data versi 2.0
dvc checkout
```
*Folder `data/` secara otomatis bertambah file baru hasil retraining dan simulasi drift.*

---

## 🌐 5. Visualisasi Silsilah Data di Web UI

Untuk melihat pemetaan silsilah dataset tanpa CLI terminal, akses **Streamlit Control Center**:
1. Buka: 👉 **https://mlops.titipin.me**
2. Klik tab: **`Model Registry`**
3. Gulir ke bagian bawah:
   * **Tabel Pemetaan Silsilah Data DVC:** Memperlihatkan hubungan langsung antara nama file CSV, Git Tag, dan hash MD5 MinIO.
   * **Pratinjau Baris Data CSV Asli:** Menampilkan tabel interaktif berisi 5 baris pertama data telemetri aktual (`timestamp`, `request_rate`, `php_cpu_cores`, `p95_latency`, `target_rps_60s`).
4. Buka tab baru ke MinIO: 👉 **https://minio.titipin.me**  
   Bucket `mlops-dvc` membuktikan penyimpanan fisik Content-Addressable Storage (CAS) di MinIO S3 yang menyimpan blok biner terenkripsi hash MD5 sesuai tabel pemetaan silsilah di atas.
