/**
 * DRIFT: INTENSITY scenario — simulate an increase in overall traffic intensity.
 *
 * Purpose:
 *   - Trigger concept drift by shifting the data distribution from LOW/MEDIUM
 *     to MEDIUM/HIGH compared to the training window.
 *   - Drift must NOT be fabricated by editing CSV values — it must come from
 *     changing the workload so the real system produces a new distribution.
 *
 * Methodology:
 *   Phase 1 (Training period): run `steady.js` or `periodic.js` at LOW/MEDIUM.
 *   Phase 2 (This script):     run at MEDIUM/HIGH for the same duration.
 *   Then compare the two Prometheus windows with a statistical drift test (KS / PSI).
 *
 * Shape:
 *   Training window:   ─────────── 3-8 req/s
 *   Drift window:      ─────────── 10-18 req/s  ← this script
 *
 * Usage:
 *   k6 run workloads/k6/scenarios/drift-intensity.js
 *   BASE_URL=https://api.titipin.me RUN_ID=drift-intensity-001 \
 *     k6 run workloads/k6/scenarios/drift-intensity.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { BASE_URL, RUN_ID } from '../common/config.js';
import { pickEndpoint } from '../common/endpoints.js';

export const options = {
  scenarios: {
    drift_intensity: {
      executor:        'ramping-arrival-rate',
      startRate:       10,
      timeUnit:        '1s',
      preAllocatedVUs: 30,
      maxVUs:          100,
      stages: [
        { target: 10, duration: '2m'  },  // settle at shifted baseline
        { target: 14, duration: '2m'  },  // ramp to shifted MEDIUM-HIGH
        { target: 14, duration: '6m'  },  // hold shifted HIGH — distribution window
        { target: 18, duration: '2m'  },  // occasional near-saturation
        { target: 18, duration: '3m'  },  // hold
        { target: 10, duration: '1m'  },  // settle
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.03'],
  },
  tags: { run_id: RUN_ID, scenario: 'drift-intensity' },
};

const latency = new Trend('custom_latency_ms', true);
const errors  = new Counter('custom_errors');

export default function () {
  const url = `${BASE_URL}${pickEndpoint()}`;
  const res = http.get(url, { tags: { name: url } });

  const ok = check(res, { 'status < 500': (r) => r.status < 500 });
  latency.add(res.timings.duration);
  if (!ok) errors.add(1);
}

export function handleSummary(data) {
  console.log(`[${RUN_ID}] Drift-intensity done.`);
  return {};
}
