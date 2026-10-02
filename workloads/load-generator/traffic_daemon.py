#!/usr/bin/env python3
"""
Continuous Stochastic Workload Generator Daemon for MLOps Observability
=======================================================================
Simulates realistic 24/7 web application traffic to https://api.titipin.me.
Runs as a systemd service on remote VM (cp-bcc), generating stochastic load patterns:
  1. IDLE_SILENT    : 0 - 1 RPS (Quiet nights / Zero traffic moments, 5-15 mins)
  2. STEADY_NORMAL  : 4 - 12 RPS (Casual daytime traffic, 20-45 mins)
  3. BURST_BUSY     : 20 - 40 RPS (Peak shopping / lunch hours, 10-20 mins)
  4. FLASH_ANOMALY  : 60 - 95 RPS (Sudden unexpected flash sale spike anomaly, 3-8 mins)
  5. COOLING_DOWN   : 10 - 20 -> 2 RPS (Post-spike stabilization, 5-10 mins)

Also supports manual override triggers via force_state.txt.
"""

import os
import sys
import time
import random
import signal
import logging
import subprocess
from datetime import datetime, timezone

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

# State Definitions: (min_vus, max_vus, min_duration_sec, max_duration_sec, description)
STATES = {
    "IDLE_SILENT": {
        "vus_range": (0, 1),
        "duration_range": (300, 900),  # 5 - 15 minutes
        "think_time": ("1.0", "3.0"),
        "desc": "Quiet night / No-traffic moment (0-1 RPS, Grafana drops to zero)",
    },
    "STEADY_NORMAL": {
        "vus_range": (4, 8),
        "duration_range": (1200, 2700),  # 20 - 45 minutes
        "think_time": ("0.3", "0.8"),
        "desc": "Steady daytime browsing (5-12 RPS, pod stays at 1 optimal)",
    },
    "BURST_BUSY": {
        "vus_range": (18, 28),
        "duration_range": (600, 1200),  # 10 - 20 minutes
        "think_time": ("0.2", "0.5"),
        "desc": "Busy rush-hour traffic surge (20-40 RPS, scaler anticipates scale-up)",
    },
    "FLASH_ANOMALY": {
        "vus_range": (50, 75),
        "duration_range": (180, 480),  # 3 - 8 minutes
        "think_time": ("0.1", "0.3"),
        "desc": "ANOMALY: Flash-sale massive spike (60-95 RPS, scales to 4 pods)",
    },
    "COOLING_DOWN": {
        "vus_range": (8, 14),
        "duration_range": (300, 600),  # 5 - 10 minutes
        "think_time": ("0.4", "0.9"),
        "desc": "Cooldown period post-surge (smooth descent to baseline)",
    },
}

# Transition Probability Matrix
TRANSITIONS = {
    "IDLE_SILENT": [
        ("STEADY_NORMAL", 0.85),
        ("FLASH_ANOMALY", 0.15),  # Surprise sudden spike from dead silence!
    ],
    "STEADY_NORMAL": [
        ("STEADY_NORMAL", 0.55),
        ("BURST_BUSY", 0.25),
        ("IDLE_SILENT", 0.12),
        ("FLASH_ANOMALY", 0.08),  # Random sudden flash-sale anomaly
    ],
    "BURST_BUSY": [
        ("COOLING_DOWN", 0.50),
        ("FLASH_ANOMALY", 0.30),  # Escalates to flash anomaly
        ("STEADY_NORMAL", 0.20),
    ],
    "FLASH_ANOMALY": [
        ("COOLING_DOWN", 1.00),  # Must cool down after peak anomaly
    ],
    "COOLING_DOWN": [
        ("STEADY_NORMAL", 0.65),
        ("IDLE_SILENT", 0.35),
    ],
}

running = True
current_proc = None


def handle_shutdown(signum, frame):
    global running, current_proc
    logger.info("Shutdown signal received (%s). Gracefully stopping...", signum)
    running = False
    if current_proc and current_proc.poll() is None:
        current_proc.terminate()


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


def pick_next_state(current_state: str) -> str:
    # Check for manual override file
    if os.path.exists(OVERRIDE_FILE):
        try:
            with open(OVERRIDE_FILE, "r") as f:
                override = f.read().strip().upper()
            os.remove(OVERRIDE_FILE)
            if override in STATES:
                logger.info("Manual override triggered: %s", override)
                return override
            elif override == "SPIKE":
                return "FLASH_ANOMALY"
            elif override == "IDLE":
                return "IDLE_SILENT"
            elif override == "STEADY":
                return "STEADY_NORMAL"
        except Exception as e:
            logger.warning("Failed to read override file: %s", e)

    choices = TRANSITIONS.get(current_state, [("STEADY_NORMAL", 1.0)])
    states, probs = zip(*choices)
    return random.choices(states, weights=probs, k=1)[0]


def run_state(state_name: str):
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
        # Zero-traffic sleep
        start_t = time.time()
        while running and (time.time() - start_t) < duration:
            # Check override during sleep
            if os.path.exists(OVERRIDE_FILE):
                logger.info("Override detected during idle sleep. Breaking early.")
                break
            time.sleep(2)
        return

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

    try:
        current_proc = subprocess.Popen(cmd, env=env)
        start_t = time.time()
        while running and current_proc.poll() is None:
            if (time.time() - start_t) >= duration:
                break
            # Check for override trigger
            if os.path.exists(OVERRIDE_FILE):
                logger.info("Override detected during execution. Terminating current run early.")
                current_proc.terminate()
                break
            time.sleep(2)

        if current_proc and current_proc.poll() is None:
            current_proc.terminate()
            current_proc.wait(timeout=5)
    except Exception as exc:
        logger.error("Error executing k6 workload: %s", exc)
    finally:
        current_proc = None


def main():
    logger.info("Starting Titipin Continuous Traffic Generator Daemon...")
    logger.info("Scenario Path : %s", SCENARIO_PATH)
    logger.info("Target Host   : %s", TARGET_URL)

    # Start with a comfortable steady state
    current_state = "STEADY_NORMAL"

    while running:
        try:
            run_state(current_state)
            if not running:
                break
            current_state = pick_next_state(current_state)
        except Exception as exc:
            logger.error("Unexpected error in main loop: %s", exc)
            time.sleep(5)

    logger.info("Traffic Generator Daemon stopped cleanly.")


if __name__ == "__main__":
    main()
