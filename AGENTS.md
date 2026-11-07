# Agent Instructions & Operational Rules: predictive-autoscaling-mlops

Target Repository: `oktavsm/predictive-autoscaling-mlops`  
System: Predictive Horizontal Pod Autoscaler for PHP-FPM Microservices (Live K3s Cluster on AWS)

---

## 1. Dual-Documentation Protocol (Mandatory)

Whenever the user requests coursework reports, Lembar Kerja (LK), or milestone documentation, the agent MUST produce **TWO SEPARATE DOCUMENTS**:

### Document 1: Laporan Pengumpulan Mahasiswa (Submission Report)
- **Path:** `docs/coursework/LK-XX_LAPORAN_PRAKTIKUM.md` (gitignored).
- **Purpose:** Official submission report for university course grading (lecturer and teaching assistants).
- **Tone & Language:** Natural, clear, flowing Indonesian. Avoid convoluted or overly technical AI jargon. Explain concepts in a direct, human manner.
- **Document Structure:**
  - **Header:** Course, Student Name, Lecturer, Study Program, University, Year, GitHub Repo Link, Action Run URL.
  - **Bagian A:** Activity Description & Core Concept (background, problem statement, relevance).
  - **Bagian B:** Methodology & Pipeline Implementation (sequential steps 1..N explained in narrative paragraphs, accompanied by concise code snippets and explicit screenshot placeholders).
  - **Bagian C:** Simulation of Changes & Execution Evidence (action logs summary, duration, run status).
  - **Bagian D:** Brief Reflection (answering reflection questions, e.g. silent failure prevention).
- **Format Constraints:**
  - **Paragraph-First:** Focus on explanatory narrative paragraphs. Use bullet points or tables only when strictly necessary (e.g., metric thresholds).
  - **Length:** Maximum 3 to 4 pages of text content (excluding screenshots/images).
  - **Visual Placeholders:** Explicit screenshot guidance formatted as:
    `> **[TEMPAT SCREENSHOT N: Judul Gambar]**`  
    `> *Deskripsi: Penjelasan apa yang ditampilkan pada gambar.*`

### Document 2: Dokumen Teknis Komprehensif (Internal Engineering Specs)
- **Path:** `docs/internal/TECHNICAL_SPECS_LK-XX.md` (gitignored).
- **Purpose:** Full technical record for engineers, system auditors, and long-term project maintenance.
- **Contents:**
  - Complete DAG / system architecture diagrams (Mermaid / ASCII).
  - Granular code implementation analysis (functions, decorators, algorithms, parameters).
  - Mathematical formulas and theoretical justifications (e.g. failure propagation, autoscaling deficit formulas).
  - Edge cases, troubleshooting history, dependency resolution, and runtime logs.
  - No length constraints; cover every detail thoroughly.

---

## 2. Infrastructure Truth & Grounding
- The cluster is a live 3-node K3s cluster on AWS. Do not introduce dummy/mock services when live infrastructure components already exist.
- Prometheus telemetry: `http://127.0.0.1:9090` (tunneled via kubectl port-forward).
- MinIO S3 Object Storage: `https://storage.titipin.me` (bucket `mlops-dvc`).
- Workload prediction horizon: Fixed at 60 seconds (4 steps @ 15 seconds) based on measured pod scale-up latency (~45 seconds).

---

## 3. Privacy, Security & Anti-Slop
- Never expose raw AWS public IPs in public markdown files or commit messages. Use placeholders: `<CONTROL_PLANE_IP>`, `<WORKER_1_IP>`, `<WORKER_2_IP>`.
- Never commit hardcoded secrets. Use `.env.secrets` (gitignored) or Kubernetes Secrets.
- Zero emoji anywhere (code, comments, documentation, commit messages).
- Always verify code with `ruff check .` and `pytest tests/` before marking tasks complete.
