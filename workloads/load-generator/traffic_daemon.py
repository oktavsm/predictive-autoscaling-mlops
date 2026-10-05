#!/usr/bin/env python3
"""
Continuous Synthetic Traffic Generator Daemon (with Remote Dashboard Hook & Heartbeat)
=====================================================================================
Menjalankan simulasi trafik multi-state secara otonom (Markov-chain) 24/7 di VM cp-bcc,
sekaligus menerima perintah override dari Streamlit Web Console via Inference API
(https://model.titipin.me/workload/status) dan melaporkan heartbeat status secara berkala.
"""

from __future__ import annotations

import json
import logging
import os
import random
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [TRAFFIC-DAEMON] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("traffic-daemon")

TARGET_URL = os.getenv("TARGET_URL", "https://api.titipin.me")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCENARIO_PATH = os.path.join(BASE_DIR, "k6_scenario.js")
OVERRIDE_FILE = os.path.join(BASE_DIR, "force_state.txt")
REMOTE_STATUS_URL = os.getenv("REMOTE_STATUS_URL", "https://model.titipin.me/workload/status")
REMOTE_HEARTBEAT_URL = os.getenv("REMOTE_HEARTBEAT_URL", "https://model.titipin.me/workload/heartbeat")

LAST_SEEN_OVERRIDE_ID = 0

# State Definitions: (vus_range, duration_range, think_time, desc)
STATES = {
    "IDLE_SILENT": {
        "vus_range": (0, 1),
        "duration_range": (300, 900),
        "think_time": ("1.0", "3.0"),
        "desc": "Quiet night / No-traffic moment (0-1 RPS, Grafana drops to zero)",
    },
    "STEADY_NORMAL": {
        "vus_range": (4, 8),
        "duration_range": (1200, 2700),
        "think_time": ("0.3", "0.8"),
        "desc": "Steady daytime browsing (5-12 RPS, pod stays at 1 optimal)",
    },
    "BURST_BUSY": {
        "vus_range": (18, 28),
        "duration_range": (600, 1200),
        "think_time": ("0.2", "0.5"),
        "desc": "Busy rush-hour traffic surge (20-40 RPS, scaler anticipates scale-up)",
    },
    "FLASH_ANOMALY": {
        "vus_range": (50, 75),
        "duration_range": (180, 480),
        "think_time": ("0.1", "0.3"),
        "desc": "ANOMALY: Flash-sale massive spike (60-95 RPS, scales to 6 pods)",
    },
    "COOLING_DOWN": {
        "vus_range": (8, 14),
        "duration_range": (300, 600),
        "think_time": ("0.4", "0.9"),
        "desc": "Cooldown period post-surge (smooth descent to baseline)",
    },
}

# Transition Probability Matrix
TRANSITIONS = {
    "IDLE_SILENT": [("STEADY_NORMAL", 0.85), ("FLASH_ANOMALY", 0.15)],
    "STEADY_NORMAL": [
        ("STEADY_NORMAL", 0.55),
        ("BURST_BUSY", 0.25),
        ("IDLE_SILENT", 0.12),
        ("FLASH_ANOMALY", 0.08),
    ],
    "BURST_BUSY": [
        ("COOLING_DOWN", 0.50),
        ("FLASH_ANOMALY", 0.30),
        ("STEADY_NORMAL", 0.20),
    ],
    "FLASH_ANOMALY": [
        ("COOLING_DOWN", 1.00),
    ],
    "COOLING_DOWN": [
        ("STEADY_NORMAL", 0.65),
        ("IDLE_SILENT", 0.35),
    ],
}

running = True
current_proc: Optional[subprocess.Popen] = None


def handle_shutdown(signum, frame):
    global running, current_proc
    logger.info("Shutdown signal received (%s). Gracefully stopping...", signum)
    running = False
    if current_proc and current_proc.poll() is None:
        current_proc.terminate()


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


def send_heartbeat(current_state: str, vus: int, remaining_s: int):
    """Sends periodic heartbeat to inference service so dashboard knows daemon is alive."""
    try:
        payload = json.dumps(
            {
                "current_state": current_state,
                "vus": int(vus),
                "remaining_seconds": max(0, int(remaining_s)),
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            REMOTE_HEARTBEAT_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TitipinTrafficDaemon/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5):
            pass
    except Exception:
        pass


def check_override() -> Optional[str]:
    """Checks local file or remote API for state override."""
    global LAST_SEEN_OVERRIDE_ID

    # 1. Local file override
    if os.path.exists(OVERRIDE_FILE):
        try:
            with open(OVERRIDE_FILE, "r") as f:
                val = f.read().strip().upper()
            os.remove(OVERRIDE_FILE)
            if val in STATES:
                return val
            if val in ("SPIKE", "FLASH", "ANOMALY"):
                return "FLASH_ANOMALY"
            if val in ("IDLE", "ZERO"):
                return "IDLE_SILENT"
            if val in ("STEADY", "NORMAL"):
                return "STEADY_NORMAL"
            if val in ("BURST", "BUSY", "PEAK"):
                return "BURST_BUSY"
        except Exception:
            pass

    # 2. Remote API status poll
    try:
        req = urllib.request.Request(
            REMOTE_STATUS_URL,
            headers={"User-Agent": "TitipinTrafficDaemon/1.0"},
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                ov_id = data.get("override_id", 0)
                ov_state = data.get("override_state")
                if ov_id != LAST_SEEN_OVERRIDE_ID and ov_id > 0 and ov_state:
                    LAST_SEEN_OVERRIDE_ID = ov_id
                    logger.info("Remote override triggered from Web Dashboard: ID=%s State=%s", ov_id, ov_state)
                    if ov_state in STATES:
                        return ov_state
                    if ov_state in ("SPIKE", "FLASH", "ANOMALY"):
                        return "FLASH_ANOMALY"
                    if ov_state in ("IDLE", "ZERO"):
                        return "IDLE_SILENT"
                    if ov_state in ("STEADY", "NORMAL"):
                        return "STEADY_NORMAL"
                    if ov_state in ("BURST", "BUSY", "PEAK"):
                        return "BURST_BUSY"
    except Exception:
        pass

    return None


def pick_next_state(current_state: str) -> str:
    ov = check_override()
    if ov:
        logger.info("Using overridden state: %s", ov)
        return ov

    choices = TRANSITIONS.get(current_state, [("STEADY_NORMAL", 1.0)])
    states, probs = zip(*choices)
    return random.choices(states, weights=probs, k=1)[0]


def run_state(state_name: str) -> Optional[str]:
    global current_proc, running
    cfg = STATES[state_name]
    vus = random.randint(*cfg["vus_range"])
    duration = random.randint(*cfg["duration_range"])
    think_min, think_max = cfg["think_time"]

    logger.info("=" * 70)
    logger.info("TRANSITION TO STATE: %s", state_name)
    logger.info("Description        : %s", cfg["desc"])
    logger.info("Virtual Users (VUs): %d", vus)
    logger.info("Duration           : %d seconds (~%.1f mins)", duration, duration / 60.0)
    logger.info("Target URL         : %s", TARGET_URL)
    logger.info("=" * 70)

    if vus == 0:
        start_t = time.time()
        while running and (time.time() - start_t) < duration:
            rem = duration - (time.time() - start_t)
            send_heartbeat(state_name, 0, rem)
            ov = check_override()
            if ov:
                logger.info("Override detected during idle sleep (%s). Breaking early.", ov)
                return ov
            time.sleep(3)
        return None

    env = os.environ.copy()
    env["TARGET_URL"] = TARGET_URL
    env["THINK_MIN"] = think_min
    env["THINK_MAX"] = think_max

    cmd = [
        "k6",
        "run",
        "--vus",
        str(vus),
        "--duration",
        f"{duration}s",
        "--quiet",
        SCENARIO_PATH,
    ]

    next_override = None
    try:
        current_proc = subprocess.Popen(cmd, env=env)
        start_t = time.time()
        while running and current_proc.poll() is None:
            rem = duration - (time.time() - start_t)
            if rem <= 0:
                break
            send_heartbeat(state_name, vus, rem)
            ov = check_override()
            if ov:
                logger.info("Override detected during execution (%s). Terminating current k6 run.", ov)
                next_override = ov
                current_proc.terminate()
                break
            time.sleep(3)

        if current_proc and current_proc.poll() is None:
            current_proc.terminate()
            current_proc.wait(timeout=5)
    except Exception as exc:
        logger.error("Error executing k6 workload: %s", exc)
    finally:
        current_proc = None

    return next_override


def main():
    logger.info("Starting Titipin Continuous Traffic Generator Daemon (with Remote Dashboard Hook & Heartbeat)...")
    logger.info("Scenario Path : %s", SCENARIO_PATH)
    logger.info("Target Host   : %s", TARGET_URL)

    current_state = "STEADY_NORMAL"

    while running:
        try:
            next_ov = run_state(current_state)
            if not running:
                break
            current_state = next_ov if next_ov else pick_next_state(current_state)
        except Exception as exc:
            logger.error("Unexpected error in main loop: %s", exc)
            time.sleep(5)

    logger.info("Traffic Generator Daemon stopped cleanly.")


if __name__ == "__main__":
    main()
