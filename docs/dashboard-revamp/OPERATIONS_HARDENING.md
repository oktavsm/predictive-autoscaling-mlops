# Implementasi improvement A–E

13 Oktober 2026. Scope mengikuti review pengguna: utilisasi aktual pod (A), persistensi riwayat (B), autentikasi write (C), cache inventory (D), dan waktu lifecycle terminal (E). Tidak menjalankan Docker daemon/build/Compose lokal atau git push. Deployment memakai image yang sudah kompatibel, ConfigMap, Secret dan PVC di K3s.

## Hasil implementasi

| Poin | Perubahan | Bukti penerimaan |
|---|---|---|
| A | CPU rate dua menit dan RAM working set dari Prometheus dipetakan ke namespace/pod/container. Card pod menampilkan nilai aktual dan bar persentase terhadap limit yang lengkap. Pod aktif didahulukan sebelum Job terminal agar metrik live tidak tertutup arsip. | Discovery klaster nyata, API live, browser QA/live, serta tes zero/missing/partial coverage. |
| B | SQLite WAL pada PVC `mlops-operations-state` 1Gi; keputusan, aksi dan lifecycle disimpan lalu dipulihkan saat startup. | Tes proses terpisah dan penggantian pod produksi saat satu owned Job tersuspensi masih tercatat aktif. Operation ID, Job dan keputusan sebelum restart tetap terbaca. |
| C | Dua Bearer token terpisah: operator dan service. Seluruh POST dilindungi; GET tetap publik. Dashboard memerlukan unlock per sesi. | Anonymous/wrong token 401, wrong role 403, missing configuration 503; browser tab kedua tidak mewarisi token; daemon/controller tetap terhubung; service-authenticated model reload berhasil. |
| D | Cache inventory process-local 8 detik dengan single-flight, copy isolation dan metadata umur cache. Tiga Kubernetes reads berjalan paralel. | Tes concurrency/expiry dan pembacaan produksi yang menunjukkan cache hit dengan observation timestamp yang sama. |
| E | `finished_at` disimpan, elapsed terminal tidak bertambah, dan stage ACTIVE ditutup ketika stop/fail/complete. | Tes ketiga terminal state dan uji cancel produksi; elapsed tetap sama setelah menunggu dan tersimpan di SQLite. |

130 tes Python lolos pada suite penuh, termasuk 62 adapter/UI tests. Dua warning dependency tetap ada (Starlette/httpx dan SQLAlchemy/MLflow). Delapan dataset smoke tests lolos dengan `-W error`. Refinement label sumber ketika semua metric hilang diuji lagi dengan 21 hardening tests. Ruff lint/format dan whitespace diff lolos.

## A: utilisasi aktual dengan makna yang jelas

[cluster_metrics.py](../../src/inference/cluster_metrics.py) mengirim dua instant query:

- CPU: `max by(namespace,pod,container)(rate(container_cpu_usage_seconds_total{...}[2m]))` dalam **cores**; UI memformat milli-cores.
- RAM: `max by(namespace,pod,container)(container_memory_working_set_bytes{...})` dalam **bytes**; UI memformat MiB.

Container kosong, infra `POD` dan image kosong dikecualikan. `max` pada label identitas mencegah penjumlahan scrape duplikat. Query menyaring series dengan timestamp raw sample lebih lama dari 45 detik; parser menolak nonfinite, negatif, timestamp invalid dan hasil vector yang tidak sesuai. CPU merupakan rata-rata window, bukan snapshot instantaneous. Referensi: [Prometheus rate dan timestamp functions](https://prometheus.io/docs/prometheus/latest/querying/functions/).

Total pod hanya tersedia jika seluruh container deklaratif punya metrik yang valid untuk resource tersebut. Coverage seperti `1/2` tetap tersedia di inspector. Nol yang benar-benar diamati tampil sebagai nol; missing tidak menjadi nol. Limit agregat hanya dipakai jika seluruh container punya limit positif yang dapat diparse. Bar memakai `usage / limit × 100`; fill visual dibatasi 100%, sementara label tetap menampilkan nilai persentase aktual. Request/limit dan allocatable node tetap deklaratif, terpisah dari metrik penggunaan.

API menambah `container_details[].usage`, `pods[].usage`, serta `usage_source`. Sumber berstatus UNAVAILABLE ketika tidak ada data valid, PARTIAL ketika hanya sebagian query tersedia, atau AVAILABLE untuk query yang tersedia. Coverage tiap pod tetap harus diperiksa. Cache dapat menambah umur hingga delapan detik setelah waktu query; timestamp query dan umur cache ditampilkan. Pause auto-refresh berarti UI mempertahankan snapshot terakhir, bukan mengklaim pengukuran baru.

## B: persistensi dan pemulihan

[operational_store.py](../../src/inference/operational_store.py) memakai SQLite stdlib, WAL, transaction, busy timeout dan koneksi yang ditutup setelah operasi. Batas penyimpanan:

| Data | SQLite | Recent API / UI |
|---|---:|---:|
| Keputusan scaling | 10.000 record | Ring 60 record, dihydrate saat startup |
| Aksi scaling | 1.000 record | Ring 40 record, dihydrate saat startup |
| Operasi lifecycle | 100 operasi, snapshot terkini per operation ID | GET `/operations/history` dan expander Persisted lifecycle history |

Record ditulis sebelum acknowledgement keputusan/aksi. Lifecycle disimpan saat accepted, perubahan stage, stop request dan terminal. Startup memulihkan state. Bila active operation punya Job yang sudah tercatat, worker memantau **Job yang sama**. Shutdown layanan menghentikan pemantauan tanpa otomatis menghapus Job; Stop eksplisit tetap membatalkan owned Job dan menunggu konfirmasi penghapusan. Stop yang masih tertunda dipulihkan sebagai permintaan cancel, bukan diubah menjadi training baru.

Jika restart terjadi sebelum `job_name` tersimpan, state menjadi INTERRUPTED dan meminta pemeriksaan owned Jobs sebelum retry. Nama Job berasal dari operation ID dan label menyimpan ID tersebut. SQLite dan Kubernetes tidak merupakan satu transaksi terdistribusi; exactly-once dispatch/idempotency lintas batas ini belum diklaim.

PVC memakai local-path dan ReadWriteOnce. Deployment inference dijaga **satu replika / satu Uvicorn process**, strategi **Recreate**, agar tidak ada dua coordinator/writer saat pergantian pod. Ini menyebabkan jeda API ketika update/restart. ReadWriteOnce sendiri tidak menjamin satu pod writer pada satu node; batas writer di sini datang dari konfigurasi deployment. [Kubernetes PV access modes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#access-modes).

Import awal mengambil 60 keputusan dan 19 aksi dari API lama sebelum cutover. State lifecycle saat snapshot sudah IDLE; data yang sebelumnya hilang dari RAM tidak direkonstruksi. Import ini best-effort, bukan jaminan atomic capture seluruh request di sekitar cutover. Sesudah fitur aktif, acknowledgement bergantung pada penulisan SQLite. PVC bertahan terhadap penggantian pod, tetapi bukan backup untuk kehilangan node/volume. Backup off-node dan restore drill tetap backlog.

## C: kontrak akses write

| Pemanggil | POST yang diizinkan |
|---|---|
| Operator | `/auth/operator`, `/predict`, `/model/reload`, `/workload/trigger`, `/monitoring/retrain/trigger`, `/monitoring/autonomous-scenario/start`, `/monitoring/autonomous-scenario/stop` |
| Service | `/predict`, `/model/reload`, `/scale-decision`, `/scaling/action-record`, `/workload/heartbeat`, `/operations/record-ingestion` |
| Anonymous / token salah | Tidak ada POST |
| Reader | Seluruh GET tetap tanpa token, termasuk health, inventory dan history |

Kedua secret harus dikonfigurasi; write fail closed bila konfigurasi belum lengkap. Perbandingan token memakai constant-time comparison. Token tidak diterima dari URL/query dan tidak dicetak pada response/log yang ditambahkan rilis ini. OpenAPI mendeklarasikan Bearer pada seluruh POST tanpa memberi syarat tersebut pada GET.

Server memakai `OPERATOR_API_TOKEN` dan `SERVICE_API_TOKEN`, dari Secret **`mlops-api-auth`**. Controller, CT Job dan daemon mengirim `Authorization: Bearer ...` memakai **`INFERENCE_API_TOKEN`**, berisi service token. CronJob template, code map training, sidecar scaler, daemon systemd dan dua script/client reload ikut disesuaikan. CLI automated pipeline berhenti sebelum mulai workload bila token belum disediakan.

Dashboard tidak menyimpan operator credential sebagai environment token yang bisa dipakai semua pengunjung. Pada workspace yang memiliki write control, buka **Operator access** di sidebar, masukkan token pada password field, lalu **Unlock operator access**. Server memverifikasi role melalui `/auth/operator`; token disimpan pada sesi Streamlit tersebut. **Lock operator access** menghapus token sesi dan input. HTTP 401/403 pada action mengunci sesi lagi. Kontrol lokal/GET tetap tersedia, sedangkan tombol write dikunci sebelum unlock.

Browser memverifikasi bahwa tab lain tidak mewarisi credential, cluster component tidak mendapat token, dan localStorage/sessionStorage tidak memuat token. Verifikasi browser login/logout hanya mengubah sesi dan memanggil auth verification; tidak melakukan forecast, traffic injection atau retraining.

### Credential handoff

Nilai dibuat secara acak dengan 32 byte entropy, disimpan lokal di directory mode 0700 dan file mode 0600:

- `~/.config/titipin-mlops/operator-token`: token untuk unlock dashboard.
- `~/.config/titipin-mlops/service-token`: credential layanan.
- `~/.config/titipin-mlops/credentials.env`: export untuk penggunaan CLI yang diotorisasi.

Tidak ada nilai secret di Git, artefak validation atau chat. Daemon membaca `/home/dev/.config/titipin-traffic-generator/api.env` melalui systemd drop-in. File tersebut mode 0600; daemon direstart sekali untuk membaca environment baru. Rotasi token harus disinkronkan ke Secret/client dan diikuti restart consumer karena environment tidak memperbarui dirinya ketika Secret berubah. Shared role tokens ini belum merupakan account-based SSO, revocation per user, rate limiting atau audit identity individual.

## D: cache dan keterbatasan latency

`/cluster/status` membungkus snapshot lengkap dalam TTL delapan detik. Satu thread melakukan refresh; pembaca lain memakai snapshot yang sama. Response menambahkan `cached`, `cache_age_seconds`, dan `cache_ttl_seconds`. Timestamp Kubernetes/Prometheus tidak diganti dengan waktu cache hit. Copy per response mencegah mutasi satu caller merusak cache.

Inventory nodes/pods/services dibaca paralel, kemudian dua query usage berjalan paralel. Kegagalan metrics tidak meniadakan inventori yang valid; nilai metrik tetap unavailable. Kegagalan inventori mengembalikan sanitized 503, bukan stale data yang diberi cap healthy baru. Ini bukan cache lintas replika atau jaminan SLA. Cold miss saat Kubernetes lambat tetap bisa melewati timeout UI; aggregate workspace snapshot/deadline/negative cache masih improvement berikutnya.

## E: waktu terminal dan status timeline

`started_at` dan `finished_at` memakai epoch UTC. Elapsed dihitung dari now hanya saat active. Ketika COMPLETED, FAILED atau STOPPED, waktu akhir disimpan dan elapsed menggunakan waktu itu. Cancel menutup ACTIVE sebagai CANCELLED; fail/complete menutup stage sesuai hasil. STOPPING/STOP_FAILED yang masih active belum dianggap terminal.

Operasi legacy yang tidak memiliki waktu akhir tidak diberi duration palsu; UI menampilkan **End time not recorded**. Riwayat registry/training dan state lifecycle tidak disamakan dengan accepted trigger atau Job terminal outcome.

## Validasi produksi dan batas klaim

- [API live](validation/hardening/api-live.json): 15 checks, termasuk auth/role, cache hit/timestamp, real usage, persistence, daemon dan service-token model reload.
- [Restart/cancel live](validation/hardening/restart-live.json): 16 checks. Satu owned Job dibuat melalui authenticated trigger dengan template sementara `spec.suspend=true`, lalu template dikembalikan sebelum restart. Tidak ada training pod. Inference pod benar-benar diganti, operation/Job yang sama terhubung kembali, keputusan sebelum restart tetap terbaca, lalu Job dibatalkan dan hilang dari Kubernetes. Durasi terminal tidak terus berjalan dan champion tetap v43. Ini membuktikan recovery/cancel, bukan eksperimen training/model-quality baru. [Kubernetes suspended Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/#suspending-a-job).
- [Explorer QA](validation/hardening/cluster-qa.json): 112 checks. [Kontrol QA](validation/hardening/controls.json): 196 checks. Fixture tetap khusus QA, bukan data produksi.
- [Explorer live](validation/hardening/cluster-live.json): 100 checks, tanpa operational browser writes. [Operator QA](validation/hardening/operator-qa.json): 12 checks termasuk immediate relock setelah 401; unit tests mencakup 401/403; [operator live](validation/hardening/operator-live.json): 9 checks.
- [Checksum consuming runtime](validation/hardening/mounted-sha256.json): source dipastikan pada container yang benar; scaler diverifikasi di sidecar, bukan file bawaan image container API. [Rollout reads](validation/hardening/rollout-reads.json) hanya sampel kecil, bukan no-downtime guarantee. Strategi Recreate memang memiliki jeda yang perlu dijadwalkan.
- Bukti final PVC, ConfigMap, Secret **references**, frozen state setelah update terakhir dan code digest dicatat pada [release manifest](validation/hardening/release.json). [Audit visual setelah implementasi](anti-slop/audit-005-2026-10-13.md) mencatat gate desain dan batas pemeriksaannya. Nilai Secret tidak disimpan pada artefak.

## Yang tetap belum diselesaikan

Review menyebut banyak metrik “100% real-time”; istilah yang tepat adalah snapshot/polling dengan window, cache dan freshness. FinOps tetap estimasi berdasarkan rekomendasi replika, bukan billing atau utilisation aktual. Benchmark masih artifact referensi, dan PSI masih terhadap reference demo. Role/relasi arsitektur masih dikonfigurasi statis dan prefix pod masih dipakai untuk mapping.

Controller lama juga mempunyai fallback RPS/CPU/latency/memory dan heuristic prediction ketika upstream gagal. Karena itu, seluruh buffer scaling tidak boleh diasumsikan selalu pengukuran mentah yang valid hanya dari `provenance=live-services`. Rilis ini membuat metrik penggunaan explorer strict/unavailable, tetapi tidak mengganti feature builder dan fallback controller. Feature parity, provenance fallback, reference drift per model, backup off-node, per-user auth/rate limiting, pending workload override persistence dan input bounds masih backlog.

## Operasi berikutnya

Validasi tetap melalui `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, dan pytest. Docker lokal dilarang; packaging image tetap di cloud CI ketika push diotorisasi. Tidak ada push/merge otomatis dalam rilis ini.

Hot-deploy dashboard tetap memakai kelima key ConfigMap `mlops-dashboard-code`. Backend code map immutable harus memuat `service.py`, `operational_store.py`, `cluster_metrics.py`, `predictive_scaler.py`, `minio_sync.py`; command API menyalin kedua helper sebelum Uvicorn. Jangan mengganti app/service tunggal jika helper berubah. CronJob harus merujuk CT code map yang sudah mendukung service token. Pertahankan Secret refs, PVC, satu replika dan strategi Recreate.

Simpan backup SQLite dengan SQLite backup API saat aktif, serta snapshot template dan code-map references sebelum rilis berikutnya. Jangan menyalin hanya file database ketika WAL masih aktif. Jangan menghapus PVC saat rollback. Rollback ke versi **sebelum autentikasi** dapat membuka public POST lagi: tutup public writes di ingress terlebih dahulu jika emergency rollback semacam itu diperlukan. Utamakan rollback ke rilis secure yang kompatibel atau roll-forward perbaikannya. Rollback runtime tidak dieksekusi pada validasi ini.
