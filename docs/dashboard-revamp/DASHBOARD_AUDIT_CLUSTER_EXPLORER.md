# Audit dashboard dan Cluster Explorer

Update setelah audit ini: [implementasi A–E](OPERATIONS_HARDENING.md) menambahkan actual pod usage, SQLite/PVC, Bearer role tokens, cache delapan detik dan frozen terminal duration. A01 sudah ditangani pada tingkat shared role tokens; A02 untuk decision/action/lifecycle history; A03 untuk terminal state; A10 untuk cache/parallel inventory; A15 untuk pod usage. Per-user auth, pending override durability, workspace-wide deadlines dan role-label discovery tetap belum selesai. Bukti di bawah merupakan snapshot audit awal, bukan klaim bahwa seluruh backlog masih belum dikerjakan.

Tanggal: 13 Oktober 2026. Ruang lingkup: dashboard Streamlit, API inference, hubungan dengan controller/training, dan inventori Kubernetes. Dokumen ini memisahkan kondisi yang terverifikasi, perubahan pada rilis explorer, serta pekerjaan berikutnya. Audit kode dan pembacaan endpoint bukan penetration test, uji beban, atau sertifikasi aksesibilitas.

## Kesimpulan

Dashboard sudah berguna untuk demonstrasi operasi nyata: model yang dimuat, keputusan dan aksi scaling, heartbeat generator, training Job, registry dan artefak memiliki sumber operasional. Titik lemah utama berikutnya adalah kontrol akses operasi, durabilitas riwayat, kesetaraan fitur training/serving, dan kesehatan dependency. Mempercantik dashboard tidak menyelesaikan empat hal tersebut.

Rilis ini memperdalam **Cluster Architecture** menjadi explorer penempatan workload dan alur sistem. Hover memberi ringkasan; klik membuka fungsi, alasan keberadaan, interface, dependency, bukti status dan langkah investigasi. Pengguna dapat memahami arsitektur sekaligus membedakan konfigurasi, inventori yang benar-benar diamati, dan kondisi yang belum diprobe.

## Bukti dan batas pemeriksaan

- Sumber kode: [dashboard](../../src/dashboard/app.py), [adapter](../../src/dashboard/adapter.py), [inference](../../src/inference/service.py), [controller](../../src/scaling/predictive_scaler.py), [training](../../src/pipeline/continuous_training.py), serta [RBAC](../../infrastructure/kubernetes/mlops/01-rbac.yaml).
- Referensi operasi: `docs/internal/AGENT_HANDOFF_OPERATIONS.md` dan [rencana remediasi](REMEDIATION_PLAN_CODEX.md). Handoff internal bukan sumber untuk menyalin IP atau kredensial ke dokumentasi publik.
- Pembacaan awal melalui `https://model.titipin.me` menggunakan tiga GET serial per endpoint, tanpa POST operasional. Snapshot lifecycle bertanggal `2026-10-13T03:25:48Z`, champion yang dilaporkan `v43`, algoritma Ridge, predictive loop aktif.
- [Timing API](validation/cluster-api-timings.json) mencakup jalur publik, DNS/TLS, jaringan, dan reverse proxy. Angka berikut adalah median dari **tiga request**, bukan p95, kapasitas layanan, atau SLO.

| GET | Median ms | Rentang ms | HTTP terakhir | Catatan |
|---|---:|---:|---:|---|
| `/health` | 115.59 | 106.56–248.58 | 200 | Model readiness dan kebijakan runtime |
| `/cluster/status` | 134.63 | 128.29–861.80 | 200 | Sebelum perluasan payload explorer |
| `/scaling/decisions` | 109.76 | 109.56–125.57 | 200 | Buffer keputusan terkini |
| `/scaling/actions` | 97.35 | 92.67–110.94 | 200 | Aksi yang dilaporkan controller |
| `/operations/audit` | 119.22 | 115.45–135.23 | 200 | Metadata ingestion/training/registry |
| `/monitoring/drift` | 104.61 | 100.84–131.26 | 200 | PSI terhadap referensi demo |
| `/workload/status` | 95.31 | 93.53–118.34 | 200 | Heartbeat dan override |
| `/monitoring/autonomous-status` | 92.88 | 92.46–99.77 | 200 | State operasi process-local |

## Yang sudah baik

| Area | Kondisi terverifikasi | Nilai praktis / batas |
|---|---|---|
| Pemisahan UI dan model | Streamlit mengonsumsi API; kebijakan replika berasal dari health | Simulator lokal tidak mengganti kebijakan controller |
| Pembacaan data | Adapter memvalidasi angka finite/nonnegatif, timestamp UTC, sorting/dedup dan horizon +60s | Grafik tidak mengisi sumber gagal dengan data demo; validasi adapter tidak menggantikan validasi API |
| Kontrol operasi | Trigger memberi acknowledgement; status lifecycle memisahkan accepted, Job berjalan, hasil gate, promotion dan reload | Tombol diterima tidak otomatis dianggap training selesai |
| Model delivery | Strict reload mempertahankan model sebelumnya bila artefak gagal dimuat; training memeriksa versi registry dan loaded version | Tetap butuh observasi drift dan kualitas online setelah reload |
| Data/artifact lineage | Dataset bernama, content hash, CAS MinIO dan metadata ingestion tersedia | Integritas objek dan retention perlu dipantau berkelanjutan |
| Registry persistence | SQLite MLflow di PVC; artefak baru di MinIO | Pod replacement bukan kehilangan metadata, tetapi local-path PVC bukan HA/backup |
| Workload injection | Heartbeat daemon dipisahkan dari pending override; profil terbatas | Daemon offline tidak diberi status eksekusi palsu |
| Konsistensi visual | Token charcoal/blue/teal, Geist/Geist Mono, kedua tema dan indikator tekstual | Status tidak bergantung pada warna saja |
| Cluster explorer baru | Node/pod/service aktual, detail container, penempatan dan alur dependency yang dapat dipilih | Kapasitas deklaratif, readiness, dependency health dan utilisasi tetap dibedakan |

## Prioritas improvement yang belum selesai

P0 berarti perlu diselesaikan sebelum kontrol write dibuka untuk pengguna yang tidak dipercaya; P1 untuk ketepatan/ketahanan operasi; P2 untuk efisiensi dan kualitas investigasi. Prioritas adalah penilaian engineering, bukan bukti eksploitasi.

| ID / prioritas | Temuan dan dampak | Perubahan yang disarankan | Bukti penerimaan |
|---|---|---|---|
| A01 / P0 | Route write FastAPI tidak memiliki authentication/authorization dependency pada kode dan OpenAPI. Read audit ini tidak memverifikasi seluruh kebijakan edge. Trigger dapat mengubah workload, training dan model bila endpoint dapat dijangkau tanpa kontrol tambahan. | Autentikasi operator di ingress/API, role reader/operator, service credential controller/daemon, rate limit dan audit actor. Jangan mengandalkan tombol UI sebagai batas keamanan. | Reader mendapat 403 untuk write; anonymous 401; operator hanya aksi yang diizinkan; daemon/controller dibatasi ke route masing-masing; edge policy diuji eksplisit. |
| A02 / P1 | Lifecycle, override dan ring history disimpan pada proses. Restart inference menghapus konteks operasi, keputusan (maks. 60) dan aksi (maks. 40). Beberapa replika API dapat memiliki state berbeda. | Persist operation ID, actor, timestamps, event dan result; rekonsiliasi Job milik operasi saat startup. Buat idempotency key untuk trigger. | Restart di tengah Job tetap bisa melaporkan hasil/cancel; request trigger berulang tidak menciptakan Job ganda; dua replica membaca state sama. |
| A03 / P1 | Terminal `STOPPED` pada snapshot awal masih memiliki item timeline `TRAINING / ACTIVE`; `elapsed_seconds` dihitung dari waktu sekarang meskipun operasi sudah terminal. UI dapat memberi kesan masih berjalan. | Tambahkan `finished_at`, tutup stage aktif dengan cancelled/failed/completed, dan freeze elapsed pada terminal. | Cancel/complete/fail masing-masing menutup stage dan elapsed tidak terus bertambah setelah terminal. |
| A04 / P1 | Lag/rolling/delta tersedia di model input, tetapi serving memakai fallback current-value ketika fitur historis tidak dikirim. Rolling mean pada keputusan menggunakan jumlah sampel terbaru tanpa jaminan grid 15s. | Gunakan feature builder yang sama untuk training dan online; simpan window bertimestamp, resample dengan aturan gap dan freshness yang sama. | Replay window yang sama menghasilkan seluruh fitur sama dalam toleransi; missing/stale window menghasilkan status eksplisit dan fallback aman. |
| A05 / P1 | `TelemetryFeatures` belum memberi batas nonnegatif/finite untuk semua numeric input atau batas hour/minute/current replicas. Adapter UI lebih ketat daripada API. | Validasi finite, domain/range/unit dan policy bounds di API; error 422 yang jelas. Batasi body dan rate untuk public boundary. | Negatif, NaN/Inf, jam di luar 0–23, menit di luar 0–59 dan replica invalid ditolak; controller valid tetap kompatibel. Tidak mengirim payload invalid ke produksi untuk audit ini. |
| A06 / P1 | Health terutama menyatakan artefak sudah di memori. Respons HTTP health tetap 200 ketika `model_ready=false`; readiness HTTP-only dapat meloloskan pod yang belum bisa melayani model. Pod Ready juga tidak membuktikan Prometheus, registry atau bucket sehat. | Pisahkan liveness/readiness dan dependency diagnostics, stale feature/metadata age, timeout serta degradasi. Jangan membuat liveness bergantung pada dependency eksternal. | Readiness 503 sebelum model siap; liveness tetap sehat saat dependency putus; dependency/freshness menjelaskan kegagalan tanpa membocorkan secret. |
| A07 / P1 | PSI memakai `metrics_demo_processed.csv` sebagai baseline. Snapshot menunjukkan PSI sampai 8.7, perbedaan distribusi terhadap demo tidak membuktikan penurunan akurasi champion. | Versikan reference bersama model, gunakan window dan minimum sample terdefinisi, kalibrasi threshold dan konfirmasi dengan delayed online error. | UI menampilkan reference hash/model/window/sample count; replay stabil/drift memberi hasil yang dapat direproduksi; false alarm dievaluasi. |
| A08 / P1 | SQLite registry di local-path PVC tetap bergantung pada satu node; MinIO juga perlu backup dan restore validation. | Backup berkala metadata dan artifact manifest; uji restore, tetapkan RPO/RTO; migrasi backend store jika kebutuhan concurrency/HA meningkat. | Restore ke lingkungan terisolasi bisa memuat versi champion yang sama dan hash artefak cocok. |
| A09 / P1 | ServiceAccount bersama memiliki akses patch/update Deployment dan inventory lintas cluster; operasi Job memakai Role namespace. | Pisahkan service account read inventory, controller scaler dan training; batasi namespace/resource target yang dibutuhkan. | `kubectl auth can-i` membuktikan reader tidak bisa patch, scaler tidak bisa membuat Job, training tidak bisa patch app lintas namespace. |
| A10 / P2 | Dashboard membaca beberapa GET serial dengan timeout 2.5s per sumber. Cluster API melakukan tiga Kubernetes reads serial dengan timeout 5s masing-masing. Worst-case sumber lambat dapat melebihi timeout UI. | Snapshot endpoint per workspace atau reads paralel terbatas; short TTL cache inventory dengan timestamp/age/error; satu deadline dan partial result yang jelas. | Ukur p50/p95 render dan upstream latency di bawah concurrency yang relevan; API tetap di bawah deadline UI saat satu dependency lambat; cache tidak menyamarkan data stale. |
| A11 / P2 | Metadata disinkronisasi background; tidak semua card menjelaskan umur last successful sync. Timestamp respons tidak selalu timestamp observasi dependency. | `observed_at`, `fetched_at`, `last_success_at`, `age_seconds`, source dan error per dependency. | Putuskan satu dependency: card menampilkan last known value bertanggal atau unavailable, bukan healthy baru. |
| A12 / P2 | Riwayat scaling kecil, tanpa jendela Prometheus untuk aligned online error, applied-vs-ready latency atau request success rate pada semua workspace. | Query window terukur dengan downsampling; align actual pada target t+60; pisahkan desired/applied/ready replica; tampilkan data coverage. | SLO/window/error dapat direproduksi dari query + range; tidak menghitung MAE terhadap actual pada timestamp issue. |
| A13 / P2 | FinOps menggunakan rata-rata rekomendasi buffer terbaru dan koefisien estimasi; benchmark adalah referensi sebelumnya, bukan eksperimen baru per refresh. | Integrasi usage aktual per window, harga/region bertanggal dan asumsi carbon; simpan benchmark run manifest, raw k6/Prometheus, config serta confidence/coverage. | Biaya dapat ditelusuri ke penggunaan dan asumsi; benchmark baru hanya diklaim ketika artifact run lengkap. |
| A14 / P2 | Inference/scaler menginstal paket pada startup; hot-code ConfigMap bisa menyimpang dari kode image. Workflow saat ini memvalidasi image inference, bukan image dashboard, dan tidak menjalankan seluruh suite UI. | Build/pin seluruh dependensi di CI cloud; tambah dashboard packaging + UI/API tests di CI, manifest kode/hash rilis, drift detection antara image dan override. | Pod start tanpa akses package index; cloud CI menguji explorer dan seluruh asset; checksum release cocok dengan mount. Tidak membangun Docker lokal. |
| A15 / P2 | Explorer memetakan role berdasarkan prefix pod; service port berdasarkan selector yang cocok dengan subset label. Pod renamed atau selector label di luar allowlist bisa tidak terpetakan. UI tidak membaca PVC state, events, log, actual utilization atau Caddy process health. | Tambahkan role label yang stabil dan query terbatas untuk event/PVC/metrics jika diperlukan; jelaskan sumber, timestamp, permission dan redaction sebelum menambah detail. | Rename pod tidak memutus role mapping; missing label tetap unknown; utilization bersumber metrics, bukan request/limit. |

Urutan yang disarankan: A01 → A02/A03 → A04/A05/A06 → A07/A08/A09 → A10–A15. Sebagian pekerjaan dapat berjalan bersamaan setelah kontrak API ditetapkan. Tidak ada klaim bahwa seluruh backlog tersebut sudah diperbaiki pada rilis explorer.

## Kontrak API yang dipakai dashboard

| Kelompok | Endpoint | Makna dan batas |
|---|---|---|
| Serving/policy | GET `/health` | Loaded model, replica bounds, recent loop activity; bukan health menyeluruh |
| Evidence | GET `/scaling/decisions`, `/scaling/actions`, `/telemetry/live-sample` | Recent observation/recommendation/action, dibedakan satu sama lain |
| Data/registry | GET `/operations/audit` | Metadata registry, ingestion dan lineage; sebagian background-sync |
| Drift | GET `/monitoring/drift` | Distribusi fitur terhadap reference; bukan akurasi online |
| Generator | GET `/workload/status` | Execution heartbeat versus pending override |
| Lifecycle | GET `/monitoring/autonomous-status` | Operasi aktif/terminal, Job/result/timeline; process-local |
| Cluster | GET `/cluster/status` | Read-only snapshot node dan pod/service pada tiga namespace |
| Local simulation | POST `/predict` | Memanggil model; bukan patch Kubernetes |
| Operational writes | POST `/workload/trigger`, `/monitoring/retrain/trigger`, `/monitoring/autonomous-scenario/start`, `/monitoring/autonomous-scenario/stop` | Explicit operator action, acknowledgement harus diikuti polling hasil |
| Delivery/control | POST `/model/reload`, `/scale-decision`, `/scaling/action-record`, `/workload/heartbeat` | Dipakai layanan/controller/daemon; perlu identitas terpisah dari reader |

Explorer hanya menambahkan pembacaan inventory yang diperluas. Hover, klik, pencarian, namespace filter, flow tabs, dan ekspansi pod berjalan lokal di browser, tidak mengirim action operasional.

## Implementasi Cluster Explorer

### Dua cara membaca cluster

1. **Workload placement** menampilkan node aktual, Ready, role, allocatable CPU/RAM dan pod yang ditempatkan. Klik node membuka condition, OS/runtime, kubelet, capacity dan allocatable. Klik pod membuka namespace, owner, phase, ready containers, restart, created-at, state per container, requests dan limits. Job Completed tidak diberi label Ready. Pod unscheduled atau node di luar snapshot tampil terpisah. Filter namespace, search dan expand/collapse bekerja pada inventori yang sama.
2. **System flow** menyediakan Serving & scaling, Training & registry, serta Observability. Memilih komponen menyorot koneksi terkait dan membuka penjelasan peran, alasan, interface, workload yang cocok, port service aktual, dependency serta investigasi kegagalan. Panah menunjukkan hubungan arsitektur yang dikonfigurasi, bukan network tracing.

Dua belas role: k6 remote VM, Caddy, Laravel, Prometheus, predictive scaler, inference, Kubernetes API, dashboard, continuous training, MLflow, MinIO, Grafana. VM `cp-bcc` terpisah dari node K3s. Caddy diberi label **Configured · not probed**. Heartbeat generator dan Kubernetes pod readiness adalah sinyal berbeda. Scaler dan inference berbagi pod, tetapi memiliki tanggung jawab berbeda.

### Visual dan interaksi

Arah: console operasi teknis, charcoal/blue/teal sesuai design kit; ENERGY 1 / RHYTHM 2 / MOTION 1. Node/pod placement menjadi fokus tampilan pertama, selected dependency menjadi fokus flow. SVG lokal menggambarkan fungsi tiap role dengan stroke yang sama; tidak perlu gambar raster atau dependency frontend baru. Blue menandai selection/relasi; warna semantik disertai teks status. Panel 10px, jarak 18px, Geist untuk prose dan Geist Mono untuk resource/name mengikuti kit.

Hover/focus memberi ringkasan yang dapat ditutup Escape. Native buttons mendukung Tab/Enter/Space dan focus-visible; inspector menerima fokus setelah selection. View, filter, search dan selection bertahan pada refresh melalui sessionStorage per tab. Tidak ada polling jaringan tambahan dari komponen. ResizeObserver menggambar ulang koneksi sesuai lebar, lalu dibersihkan saat unmount. Pada mobile layout bertumpuk, graph menjadi dua kolom, dan daftar koneksi tetap tersedia saat garis SVG disembunyikan. Reduced-motion mematikan transisi dan scroll halus.

Implementasi memakai [Streamlit components v2](https://docs.streamlit.io/develop/concepts/custom-components/components-v2/register) yang tersedia pada runtime 1.65.0. Python mengirim data terstruktur; teks API di-escape sebelum masuk DOM. Asset JS/CSS adalah kode lokal terpercaya, bukan kode yang berasal dari Kubernetes. Nama pod berisi markup diuji sebagai teks literal. Ini tidak menggantikan autentikasi API.

### Payload cluster yang diperluas

`/cluster/status` mengembalikan `timestamp`, `scope`, `source`, `nodes`, `pods`, `services`. Query memakai izin inventory yang sudah ada; tidak menambah verb RBAC.

| Entitas | Detail yang diekspos | Sengaja tidak dikirim |
|---|---|---|
| Node | name, role, Ready, unschedulable, capacity/allocatable CPU-memory-pods, runtime/version, categorical conditions | Addresses, provider ID, arbitrary labels/annotations, raw condition messages |
| Pod | name, namespace, node, phase, owner, created-at, allowlisted labels, ready count, restart count, container resource declarations dan sanitized state | IP, environment, secrets, image credential, logs, container ID, raw termination messages |
| Service | name, namespace, type, selector dan port/targetPort/nodePort/protocol | Cluster/external IP dan load-balancer address |

CPU/memory pada node dan container bukan utilisasi saat ini. Kubernetes inventory tidak membuktikan query Prometheus, bucket permission, TLS atau artifact integrity. Bila inventory gagal, API merespons sanitized 503 dan UI tidak mengarang node/pod pengganti. Snapshot berasal dari tiga reads, sehingga bukan transaksi Kubernetes atomik.

### File dan validasi

- [cluster.py](../../src/dashboard/cluster.py): registration/mount komponen; [cluster.js](../../src/dashboard/assets/cluster.js): interaksi read-only; [cluster.css](../../src/dashboard/assets/cluster.css): responsive/theme; [catalog](../../src/dashboard/assets/cluster-catalog.json): role dan koneksi yang dijelaskan.
- [API tests](../../tests/test_dashboard_remediation.py): detail inventory, readiness, sanitized payload, error 503. [UI tests](../../tests/test_dashboard_ui.py): seluruh workspace tetap bisa dirender dan tidak melakukan write otomatis.
- [Browser script](validation/cluster.cjs): hover, keyboard, Escape, node/pod/component inspector, namespace/search/expand, tiga flow, selected edges, refresh state, kedua tema, responsive, XSS fixture dan empty/error sources. Mode fixture menggunakan data QA yang sengaja dilabeli synthetic; mode `--live` tidak mengubah keadaan operasional.
- Hasil command, browser JSON, screenshot dan detail hot-deploy tercatat pada bagian rilis di bawah.

## Operasional rilis

Tidak menjalankan Docker daemon/build/Compose lokal. Pemeriksaan packaging diserahkan ke GitHub Actions ketika ada push yang diotorisasi; perubahan ini tidak otomatis di-push. Dashboard live memakai image yang sudah mendukung components v2. Karena rilis menambah modul dan asset, hot-deploy harus memasang **semua** file explorer melalui ConfigMap, bukan hanya app.py. Pertahankan isi image lain, environment, secret refs dan resource limit yang sudah aktif. Simpan snapshot pod template sebelumnya untuk rollback.

App-only hot reload ke image lama tidak memadai untuk rilis ini. Runbook hot-deploy multi-file dan bukti rollout tercatat di bawah.

### Hasil rilis yang diverifikasi

Rilis `cluster-20261013-0404` sudah live di [dashboard](https://mlops.titipin.me), workspace **Cluster Architecture**. [Release manifest](validation/cluster-release.json) mencatat digest image yang tetap, ConfigMap aktif, hash keenam file yang cocok dengan mount pod, status serving dan jumlah inventori. Backend memakai `mlops-inference-code-cluster-20261013-0404`; dashboard memakai `mlops-dashboard-code` dengan lima key/mount. Model tetap `v43` / Ridge. Snapshot verifikasi rilis: 3/3 node Ready, 22 pod, 15 service; jumlah workload dapat berubah setelah snapshot.

- **106 tes Python lolos**, termasuk 59 adapter/UI. Dua warning dependency: Starlette/httpx deprecation dan SQLAlchemy loader MLflow deprecation. Delapan dataset smoke tests juga lolos terpisah dengan `-W error`.
- Ruff lint, format check dan `git diff --check` lolos. Formatting code fence pada rencana remediasi ikut diselaraskan agar gate repository lolos; isi rencana tidak diubah.
- **108 pemeriksaan browser fixture**: [hasil QA](validation/cluster-qa.json). **98 pemeriksaan browser produksi**: [hasil live](validation/cluster-live.json). Keduanya mencatat nol page errors dan nol browser operational writes. Fixture tambahan memeriksa XSS literal, unscheduled/completed workload serta inventory kosong/gagal.
- Kedua tema dan lebar 1600/1024/390/320 px diperiksa; teks root komponen diperbesar di 320 px tanpa overflow. [70 pasangan warna normal-text](validation/cluster-contrast.json) lolos rasio 4.5:1. Pemeriksaan tersebut bukan sertifikasi WCAG menyeluruh.
- [72 GET selama rollout](validation/cluster-rollout-reads.json) semuanya 200. Satu **HEAD tambahan** tepat sesudah rollout dashboard menghasilkan 502; empat pemeriksaan GET dashboard berikutnya kembali 200. Sampel GET itu tidak membuktikan zero downtime. Tidak menutupi kegagalan transisi dengan status rollout Kubernetes.
- [Timing payload cluster baru](validation/cluster-api-after.json) menyimpan tiga GET setelah deploy, ukuran response dan latency; tetap diagnostic kecil, bukan uji beban.
- [Desktop live gelap](validation/cluster-live-dark-flow-1600.png), [desktop live terang](validation/cluster-live-light-placement-1600.png), [mobile live gelap](validation/cluster-live-dark-placement-390.png), [mobile live terang](validation/cluster-live-light-flow-390.png). Streamlit memiliki area main yang scroll internal; PNG merekam viewport, bukan seluruh inspector panjang dalam satu gambar. PNG `cluster-qa-*` memakai fixture, sedangkan `cluster-live-*` memakai inventory produksi.
- [Audit visual sesudah implementasi](anti-slop/audit-004-2026-10-13.md) membatasi hasil pada explorer dan perubahan rilis ini. Backlog A01–A15 tetap tercatat, tidak dianggap selesai oleh lolosnya tes UI.

### Hot-deploy berikutnya tanpa Docker lokal

Lima mount sudah terpasang pada deployment. Untuk update kode explorer yang tidak mengubah dependency runtime, salin seluruh file, simpan backup template/ConfigMap, update map dan restart. Jangan menghapus module/asset key ketika hanya app.py berubah.

```sh
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest tests/test_dashboard_adapter.py tests/test_dashboard_ui.py -v

ssh cp 'mkdir -p /tmp/cluster-explorer-next'
ssh cp 'kubectl -n mlops get deployment mlops-dashboard -o json > /tmp/cluster-explorer-next/dashboard-before.json'
ssh cp 'kubectl -n mlops get configmap mlops-dashboard-code -o yaml > /tmp/cluster-explorer-next/dashboard-code-before.yaml'
scp src/dashboard/app.py src/dashboard/cluster.py \
  src/dashboard/assets/cluster.js src/dashboard/assets/cluster.css \
  src/dashboard/assets/cluster-catalog.json cp:/tmp/cluster-explorer-next/
ssh cp 'set -eu
cd /tmp/cluster-explorer-next
kubectl -n mlops create configmap mlops-dashboard-code \
  --from-file=app.py --from-file=cluster.py --from-file=cluster.js \
  --from-file=cluster.css --from-file=cluster-catalog.json \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n mlops rollout restart deployment/mlops-dashboard
kubectl -n mlops rollout status deployment/mlops-dashboard --timeout=180s'
curl --fail --silent --head https://mlops.titipin.me
```

Jika HEAD gagal, periksa GET root dan `/_stcore/health`, readiness pod, endpoints service dan log aplikasi sebelum menyatakan berhasil. Buka browser untuk memeriksa module/asset dan interaksi; HTTP 200 saja tidak membuktikan explorer berhasil dirender. Jangan menganggap `kubectl rollout undo` akan mengembalikan isi ConfigMap mutable yang sudah ditimpa: untuk update berikutnya restore backup kode juga, kemudian restart.

Pada rilis ini, mount tambahan dipasang melalui strategic patch volume/volumeMounts dan annotation hash, tanpa mengubah image/env/resource/probe. Perluasan backend memakai ConfigMap baru yang immutable dengan `service.py`, `predictive_scaler.py` dan `minio_sync.py`; dua file terakhir dibandingkan dengan map sebelumnya dan tetap identik. Rollout backend mengosongkan buffer process-local (A02); tidak menjalankan retraining atau mengganti champion.

### Rollback rilis ini

Snapshot template sebelum perubahan tersedia pada control plane di `/tmp/cluster-explorer-20261013-0404/cluster-explorer-mlops-dashboard-rollback.json` dan pasangannya untuk inference. File berisi JSON Patch `replace /spec/template`; template lama merujuk ConfigMap lama yang masih dipertahankan. Jangan menyalin full deployment dengan metadata server-generated untuk rollback.

```sh
ssh cp 'set -eu
cd /tmp/cluster-explorer-20261013-0404
kubectl -n mlops patch deployment mlops-dashboard --type=json \
  --patch-file=cluster-explorer-mlops-dashboard-rollback.json
kubectl -n mlops rollout status deployment/mlops-dashboard --timeout=180s
kubectl -n mlops patch deployment mlops-inference --type=json \
  --patch-file=cluster-explorer-mlops-inference-rollback.json
kubectl -n mlops rollout status deployment/mlops-inference --timeout=300s'
```

Rollback template/hashes diperiksa sebagai artefak; rollback tidak dieksekusi karena rilis berhasil. `/tmp` bukan arsip permanen: simpan backup rilis ke lokasi operasi yang terkelola sebelum cleanup VM. Perubahan dependency/image berikutnya tetap melalui cloud CI; CI/build/push tidak dijalankan sebagai bagian hot-deploy ini.
