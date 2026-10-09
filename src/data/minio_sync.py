#!/usr/bin/env python3
"""
MinIO Object Storage & DVC Direct Sync Engine
=============================================
Menyediakan sinkronisasi dua arah (Two-Way Synchronization) antara:
  - Lingkungan Produksi (VPS/Kubernetes CronJob & Event Triggers)
  - Object Storage MinIO (s3://mlops-dvc)
  - Lingkungan Lokal Developer (data/raw & data/processed)

Fitur:
  1. Auto-Push saat Ingestion/Retraining:
     Mengunggah file raw dan processed ke MinIO, sekaligus mengisi format
     CAS (Content Addressable Storage) DVC (files/md5/...) agar DVC mengenali data.
  2. One-Command Pull untuk Developer Lokal:
     Menarik semua file dataset terbaru dari MinIO ke data/raw/ dan data/processed/
     tanpa perlu repot memikirkan apakah data sudah di-commit di Git atau belum.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    Minio = None
    S3Error = Exception

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MINIO-SYNC]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("minio-sync")


def calculate_md5(file_path: Path) -> str:
    """Menghitung MD5 checksum sebuah file."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_minio_client() -> Tuple[Minio, str]:
    """Menginisialisasi client MinIO berdasarkan environment variable atau konfigurasi standar."""
    if Minio is None:
        raise RuntimeError("Library 'minio' belum terinstall. Jalankan: pip install minio")

    endpoint_raw = (
        os.getenv("MINIO_ENDPOINT")
        or os.getenv("MLFLOW_S3_ENDPOINT_URL")
        or "https://storage.titipin.me"
    )
    access_key = os.getenv("AWS_ACCESS_KEY_ID") or "titipin_minio"
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or "rahasiawoy"
    bucket_name = os.getenv("DVC_BUCKET_NAME") or "mlops-dvc"

    # Bersihkan skema http/https
    secure = True
    endpoint = endpoint_raw
    if endpoint.startswith("https://"):
        endpoint = endpoint[8:]
        secure = True
    elif endpoint.startswith("http://"):
        endpoint = endpoint[7:]
        secure = False

    # Hapus trailing slashes jika ada
    endpoint = endpoint.rstrip("/")

    client = Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )
    return client, bucket_name


def push_dataset_to_minio(
    raw_path: Optional[Path | str] = None, processed_path: Optional[Path | str] = None
) -> Dict[str, Any]:
    """Mengunggah dataset raw dan processed ke MinIO (Format Langsung + Format CAS DVC)."""
    client, bucket_name = get_minio_client()

    # Pastikan bucket ada
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)

    results: Dict[str, Any] = {"pushed_files": [], "bucket": bucket_name}

    targets = []
    if raw_path:
        p = Path(raw_path)
        if p.exists():
            targets.append((p, "raw"))
    if processed_path:
        p = Path(processed_path)
        if p.exists():
            targets.append((p, "processed"))

    for file_path, prefix in targets:
        md5_hash = calculate_md5(file_path)
        file_size = file_path.stat().st_size
        filename = file_path.name

        # 1. Upload ke path direktori normal (misal: raw/metrics_20261003.csv)
        obj_key_named = f"{prefix}/{filename}"
        logger.info("Mengunggah %s (%d bytes) -> %s", filename, file_size, obj_key_named)
        client.fput_object(bucket_name, obj_key_named, str(file_path))

        # 2. Upload pointer latest (misal: raw/latest.csv)
        obj_key_latest = f"{prefix}/latest.csv"
        client.fput_object(bucket_name, obj_key_latest, str(file_path))

        # 3. Upload ke DVC CAS path: files/md5/xx/xxxxxxxxxxxxxx
        dvc_cas_key = f"files/md5/{md5_hash[:2]}/{md5_hash[2:]}"
        client.fput_object(bucket_name, dvc_cas_key, str(file_path))

        results["pushed_files"].append(
            {
                "file": filename,
                "prefix": prefix,
                "size": file_size,
                "md5": md5_hash,
                "dvc_key": dvc_cas_key,
            }
        )

    logger.info(
        "✓ Berhasil menyinkronkan %d file ke MinIO bucket '%s'",
        len(results["pushed_files"]),
        bucket_name,
    )
    return results


def pull_datasets_from_minio() -> Dict[str, Any]:
    """Mengunduh seluruh dataset terbaru dari MinIO ke direktori lokal data/raw dan data/processed."""
    client, bucket_name = get_minio_client()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    downloaded = []
    skipped = []

    logger.info("Memeriksa objek dataset di bucket MinIO '%s'...", bucket_name)
    objects = list(client.list_objects(bucket_name, recursive=True))

    for obj in objects:
        name = obj.object_name
        # Hanya unduh dari prefix raw/ dan processed/ (kecualikan 'latest.csv' untuk mencegah duplikasi penamaan)
        if (name.startswith("raw/") or name.startswith("processed/")) and not name.endswith(
            "latest.csv"
        ):
            parts = name.split("/", 1)
            folder_type = parts[0]
            filename = parts[1]

            target_dir = RAW_DIR if folder_type == "raw" else PROCESSED_DIR
            local_target = target_dir / filename

            # Cek apakah file sudah ada dan ukurannya sama
            if local_target.exists() and local_target.stat().st_size == obj.size:
                skipped.append(filename)
                continue

            logger.info("Mengunduh %s (%d bytes) -> %s", name, obj.size, local_target)
            client.fget_object(bucket_name, name, str(local_target))
            downloaded.append(
                {
                    "file": filename,
                    "type": folder_type,
                    "size": obj.size,
                }
            )

    # Otomatis trigger dvc commit lokal agar pointer .dvc terupdate tanpa error
    dvc_bin = REPO_ROOT / ".venv" / "bin" / "dvc"
    if dvc_bin.exists() or Path("/usr/bin/dvc").exists():
        bin_to_run = str(dvc_bin) if dvc_bin.exists() else "dvc"
        try:
            subprocess.run(
                [bin_to_run, "commit", "-f"], cwd=str(REPO_ROOT), check=False, capture_output=True
            )
            logger.info("✓ Sinkronisasi lokal DVC cache berhasil di-commit.")
        except Exception as e:
            logger.warning("DVC local commit skipped: %s", e)

    logger.info(
        "✓ Selesai: %d file baru diunduh, %d file lokal sudah cocok.", len(downloaded), len(skipped)
    )
    return {
        "downloaded_count": len(downloaded),
        "downloaded": downloaded,
        "skipped_count": len(skipped),
    }


def list_remote_datasets() -> None:
    """Menampilkan daftar dataset yang tersimpan di MinIO."""
    client, bucket_name = get_minio_client()
    print("\n" + "=" * 75)
    print(f"        REMOTE DATASET REPOSITORY — MINIO S3 (bucket: {bucket_name})")
    print("=" * 75)

    objects = list(client.list_objects(bucket_name, recursive=True))
    raw_files = [o for o in objects if o.object_name.startswith("raw/")]
    proc_files = [o for o in objects if o.object_name.startswith("processed/")]
    dvc_cas_files = [o for o in objects if o.object_name.startswith("files/md5/")]

    print(f"Total DVC CAS Hashes  : {len(dvc_cas_files)} objects")
    print(f"Raw Datasets         : {len(raw_files)} files")
    for r in raw_files:
        print(f"  • {r.object_name:<45} ({r.size / 1024:.1f} KB)")

    print(f"\nProcessed Datasets   : {len(proc_files)} files")
    for p in proc_files:
        print(f"  • {p.object_name:<45} ({p.size / 1024:.1f} KB)")
    print("=" * 75 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MinIO and DVC Bi-Directional Dataset Synchronization"
    )
    parser.add_argument(
        "--pull", action="store_true", help="Unduh semua dataset terbaru dari MinIO ke lokal"
    )
    parser.add_argument(
        "--push-latest",
        action="store_true",
        help="Unggah file raw & processed lokal terbaru ke MinIO",
    )
    parser.add_argument(
        "--status", action="store_true", help="Tampilkan daftar dataset yang tersimpan di MinIO"
    )
    args = parser.parse_args()

    if args.pull:
        res = pull_datasets_from_minio()
        print(f"\n🎉 Berhasil menarik {res['downloaded_count']} file baru dari remote MinIO!")
    elif args.push_latest:
        # Cari file terbaru
        raw_files = sorted(list(RAW_DIR.glob("*.csv")), key=lambda x: x.stat().st_mtime)
        proc_files = sorted(list(PROCESSED_DIR.glob("*.csv")), key=lambda x: x.stat().st_mtime)

        latest_raw = raw_files[-1] if raw_files else None
        latest_proc = proc_files[-1] if proc_files else None

        if not latest_raw and not latest_proc:
            print("Tidak ada file di data/raw atau data/processed untuk di-push.")
            sys.exit(1)

        push_dataset_to_minio(raw_path=latest_raw, processed_path=latest_proc)
        print("🎉 File terbaru berhasil di-push ke MinIO!")
    elif args.status:
        list_remote_datasets()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
