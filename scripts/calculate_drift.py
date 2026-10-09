import csv
import math


def calculate_psi(expected, actual, num_bins=10, epsilon=1e-4):
    if not expected or not actual:
        return 0.0
    sorted_exp = sorted(expected)
    n_exp = len(sorted_exp)

    # Calculate quantile bin edges
    bin_edges = []
    for i in range(num_bins + 1):
        idx = int(round(i * (n_exp - 1) / num_bins))
        bin_edges.append(sorted_exp[idx])

    bin_edges = sorted(list(set(bin_edges)))
    if len(bin_edges) < 2:
        return 0.0

    # Bucket expected and actual
    exp_counts = [0] * (len(bin_edges) - 1)
    act_counts = [0] * (len(bin_edges) - 1)

    for val in expected:
        for b in range(len(bin_edges) - 1):
            if (
                (b == 0 and val <= bin_edges[1])
                or (bin_edges[b] < val <= bin_edges[b + 1])
                or (b == len(bin_edges) - 2 and val >= bin_edges[b])
            ):
                exp_counts[b] += 1
                break

    for val in actual:
        for b in range(len(bin_edges) - 1):
            if (
                (b == 0 and val <= bin_edges[1])
                or (bin_edges[b] < val <= bin_edges[b + 1])
                or (b == len(bin_edges) - 2 and val >= bin_edges[b])
            ):
                act_counts[b] += 1
                break

    psi = 0.0
    n_act = len(actual)
    for b in range(len(bin_edges) - 1):
        e_pct = max(epsilon, exp_counts[b] / max(1, n_exp))
        a_pct = max(epsilon, act_counts[b] / max(1, n_act))
        psi += (a_pct - e_pct) * math.log(a_pct / e_pct)
    return round(psi, 4)


def run_drift_analysis(ref_file, curr_file, threshold=0.20):
    with open(ref_file, "r") as f:
        ref_rows = list(csv.DictReader(f))
    with open(curr_file, "r") as f:
        curr_rows = list(csv.DictReader(f))

    features = [
        "request_rate",
        "php_cpu_cores",
        "p95_latency_seconds",
        "php_memory_mb",
        "rps_roll_mean_60s",
    ]

    print("\n" + "=" * 80)
    print("      MLOps PRODUCTION TELEMETRY DATA DRIFT REPORT (POPULATION STABILITY INDEX)")
    print("=" * 80)
    print(f"Reference Baseline : {ref_file} ({len(ref_rows)} samples)")
    print(f"Current Telemetry  : {curr_file} ({len(curr_rows)} samples)")
    print(f"PSI Threshold      : {threshold}")
    print("-" * 80)
    print(
        f"{'Feature Name':<22} | {'Ref Mean':<10} | {'Curr Mean':<10} | {'PSI Score':<10} | {'Status':<16}"
    )
    print("-" * 80)

    drifted_features = []
    for feat in features:
        ref_vals = [float(r[feat]) for r in ref_rows if r.get(feat)]
        curr_vals = [float(r[feat]) for r in curr_rows if r.get(feat)]
        if not ref_vals or not curr_vals:
            continue
        psi = calculate_psi(ref_vals, curr_vals)
        ref_m = sum(ref_vals) / len(ref_vals)
        curr_m = sum(curr_vals) / len(curr_vals)
        status = (
            "🔴 SIGNIFICANT"
            if psi >= threshold
            else ("🟡 MODERATE" if psi >= 0.10 else "🟢 STABLE")
        )
        if psi >= threshold:
            drifted_features.append(feat)
        print(f"{feat:<22} | {ref_m:<10.2f} | {curr_m:<10.2f} | {psi:<10.4f} | {status}")

    print("=" * 80)
    if drifted_features:
        print(
            f"🚨 STATUS: DRIFT DETECTED IN {len(drifted_features)}/{len(features)} FEATURES: {drifted_features}"
        )
        print("💡 ACTION REQUIRED: Triggering Automated Continuous Retraining (CT) Pipeline...")
    else:
        print("✅ STATUS: Telemetry distributions are stable. No retraining required.")
    print("=" * 80 + "\n")
    return len(drifted_features) > 0


if __name__ == "__main__":
    import sys

    ref = sys.argv[1] if len(sys.argv) > 1 else "data/processed/metrics_demo_processed.csv"
    curr = sys.argv[2] if len(sys.argv) > 2 else "data/processed/metrics_flashsale_drifted.csv"
    drift_detected = run_drift_analysis(ref, curr)
