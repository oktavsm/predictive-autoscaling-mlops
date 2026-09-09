/**
 * SPIKE workload — sudden burst from baseline to high load, then back.
 *
 * Purpose:
 *   - Evaluate reactive scaling delay (the key weakness reactive HPA has).
 *   - Measure latency and error impact during the spike onset.
 *   - KEY COMPARISON SCENARIO: predictive scaling should pre-warm replicas
 *     before the spike arrives, avoiding the initial latency cliff.
 *
 * Shape:
 *   req/s
 *     │           ┌──────────┐
 *     │           │          │
 *     │───────────┘          └──────────
 *     └────────────────────────────────→ time
 *
 * Timeline:
 *   0-5m    →  3 req/s   (LOW baseline — steady before spike)
 *   5-5:30  → 18 req/s   (spike onset — fast ramp in 30s)
 *   5:30-12 → 18 req/s   (hold spike — replicas must have scaled by here)
 *   12-12:30 → 3 req/s   (drop — scale-down observation)
 *   12:30-15 → 3 req/s   (recovery window)
 *
 * The 30-second ramp-up simulates a realistic sudden spike (e.g., flash sale
 * or viral link). For an instantaneous spike, set the ramp duration to '0s'.
 *
 * Usage:
 *   k6 run workloads/k6/scenarios/spike.js
 *   BASE_URL=https://api.titipin.me RUN_ID=spike-001 k6 run workloads/k6/scenarios/spike.js
 *
 *   # Change spike intensity:
 *   SPIKE_RATE=20 k6 run workloads/k6/scenarios/spike.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { BASE_URL, RUN_ID } from '../common/config.js';
import { pickEndpoint } from '../common/endpoints.js';

const spikeRate = parseInt(__ENV.SPIKE_RATE || '18');

export const options = {
  scenarios: {
    spike: {
      executor:        'ramping-arrival-rate',
      startRate:       3,
      timeUnit:        '1s',
      preAllocatedVUs: 40,
      maxVUs:          120,
      stages: [
        { target: 3,         duration: '1m'  },   // baseline (LOW)
        { target: spikeRate, duration: '30s' },   // spike onset (fast ramp)
        { target: spikeRate, duration: '3m'  },   // hold spike (near SATURATION)
        { target: 3,         duration: '30s' },   // drop
        { target: 3,         duration: '1m'  },   // recovery / scale-down window
      ],
    },
  },
  thresholds: {
    // During a spike, some degradation is expected — threshold is lenient.
    http_req_failed:   ['rate<0.05'],
    http_req_duration: ['p(95)<2000'],
  },
  tags: { run_id: RUN_ID, scenario: 'spike', spike_rate: String(spikeRate) },
};

const latency = new Trend('custom_latency_ms', true);
const errors  = new Counter('custom_errors');

export default function () {
  const url = `${BASE_URL}${pickEndpoint()}`;
  const res = http.get(url, { tags: { name: url } });

  const ok = check(res, {
    'status < 500': (r) => r.status < 500,
  });

  latency.add(res.timings.duration);
  if (!ok) errors.add(1);
}

export function handleSummary(data) {
  const p95 = data.metrics.http_req_duration?.values?.['p(95)'];
  const errRate = data.metrics.http_req_failed?.values?.rate;
  console.log(`[${RUN_ID}] Spike done. p95=${p95} ms, error_rate=${errRate}`);
  return {};
}
