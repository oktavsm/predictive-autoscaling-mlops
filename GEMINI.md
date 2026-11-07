# Local Gemini & Antigravity Rules: predictive-autoscaling-mlops

Target Repository: `oktavsm/predictive-autoscaling-mlops`  
System: Predictive Horizontal Pod Autoscaler for PHP-FPM Microservices (Live K3s Cluster on AWS)

---

## 1. Dual-Documentation Protocol (Wajib)

Setiap kali pengguna meminta laporan tugas, Lembar Kerja (LK), atau dokumentasi penyelesaian milestone praktikum, agen WAJIB menghasilkan **DUA DOKUMEN BERBEDA**:

### Dokumen 1: Laporan Pengumpulan Mahasiswa (Submission Report)
- **Path Berkas:** `docs/coursework/LK-XX_LAPORAN_PRAKTIKUM.md` (di-ignore oleh Git).
- **Tujuan:** Berkas resmi untuk dikumpulkan ke dosen dan asisten praktikum.
- **Gaya Bahasa:** Bahasa Indonesia yang wajar, lugas, mudah dipahami, tidak berbelit-belit, dan tidak over-technical dengan jargon AI yang berlebihan.
- **Sistematika Dokumen:**
  - **Identitas Lengkap:** Mata Kuliah, Nama Mahasiswa, NIM, Dosen Pengampu, Program Studi, Fakultas, Universitas, Tahun, Link Repository, Link Eksekusi Action Run.
  - **Bagian A:** Deskripsi Aktivitas & Konsep Inti (latar belakang, urgensi, relevansi terhadap proyek).
  - **Bagian B:** Metode & Implementasi Alur Kerja (tahapan 1..N dijelaskan runut, cuplikan kode ringkas, dan placeholder screenshot terarah).
  - **Bagian C:** Simulasi Perubahan Kode & Bukti Eksekusi (status run GitHub Actions, ringkasan durasi, log eksekusi).
  - **Bagian D:** Refleksi Singkat (jawaban atas pertanyaan analisis/refleksi praktikum, misal pencegahan silent failure).
- **Batasan Format:**
  - **Utamakan Paragraf:** Fokus pada paragraf penjelasan yang mengalir. Gunakan bullet points atau tabel hanya jika esensial (seperti tabel ambang batas).
  - **Panjang:** Maksimal 3 sampai 4 halaman untuk teks isi (di luar tempat foto screenshot).
  - **Placeholder Screenshot:** Wajib menyertakan placeholder dengan format:
    `> **[TEMPAT SCREENSHOT N: Judul Gambar]**`  
    `> *Deskripsi: Penjelasan apa yang ditampilkan pada gambar.*`

### Dokumen 2: Dokumen Teknis Komprehensif (Internal Engineering Specs)
- **Path Berkas:** `docs/internal/TECHNICAL_SPECS_LK-XX.md` (di-ignore oleh Git).
- **Tujuan:** Catatan teknik mendalam mengenai detail teknis sebenarnya yang dikerjakan oleh AI/developer untuk audit sistem, pemeliharaan jangka panjang, dan kelangsungan proyek.
- **Karakteristik & Isi:**
  - Arsitektur sistem lengkap dan diagram alur DAG (Mermaid / ASCII).
  - Analisis implementasi kode yang granular (fungsi, kelas, decorator, skema signature, algoritma, parameter).
  - Penjelasan matematis atau teknis mendalam (misal analisis perambatan galat autoscaling).
  - Troubleshooting log, edge cases, riwayat bugfix, dan verifikasi eksekusi CLI lengkap.
  - Tanpa batasan panjang halaman (tulis secara detail dan komprehensif).

---

## 2. Infrastructure Truth & Grounding
- Klaster operasional adalah live 3-node K3s cluster di AWS. Jangan membuat mock service jika komponen riil sudah tersedia.
- Prometheus telemetri: `http://127.0.0.1:9090` (tunneled via kubectl port-forward).
- MinIO S3 Object Storage: `https://storage.titipin.me` (bucket `mlops-dvc`).
- Horizon peramalan beban kerja: 60 detik (4 langkah @ 15 detik), didasarkan pada latensi scale-up pod riil (~45 detik).

---

## 3. Privacy, Security & Anti-Slop
- Jangan mencantumkan raw IP publik AWS pada dokumen publik atau commit message. Gunakan placeholder standar `<CONTROL_PLANE_IP>`, `<WORKER_1_IP>`, `<WORKER_2_IP>`.
- Jangan menulis kredensial atau rahasia ke file yang ter-track Git. Seluruh token/password wajib berada di `.env.secrets` atau Kubernetes Secrets.
- Zero emoji di seluruh kode, copy, komentar, dan commit message.
- Selalu jalankan `ruff check .` dan `pytest tests/` sebelum menganggap pekerjaan selesai.
