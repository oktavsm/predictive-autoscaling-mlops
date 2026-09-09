/**
 * PERIODIC workload — traffic repeatedly rises and falls in a wave pattern.
 *
 * Purpose:
 *   - Create learnable temporal structure in the dataset.
 *   - Most important scenario for the ML model: a good time-series model
 *     should "see" the pattern and pre-scale before each peak.
 *   - Compare reactive (always reacting after the fact) vs predictive
 *     (anticipating the next wave).
 *
 * Shape:
 *   req/s
 *     │    /\      /\      /\
 *     │___/  \____/  \____/  \___
 *     └────────────────────────────→ time
 *
 * Cycle (3 full waves, ~30 min total):
 *   Each wave:
 *     LOW  (3  req/s) hold 2m  — trough
 *     ramp to HIGH (14 req/s) over 2m
 *     HIGH hold 3m             — peak
 *     drop back to LOW over 1m
 *
 * Usage:
 *   k6 run workloads/k6/scenarios/periodic.js
 *   BASE_URL=https://api.titipin.me RUN_ID=periodic-001 k6 run workloads/k6/scenarios/periodic.js
 *
 *   # Adjust peak load:
 *   PEAK_RATE=18 k6 run workloads/k6/scenarios/periodic.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { BASE_URL, RUN_ID } from '../common/config.js';
import { pickEndpoint } from '../common/endpoints.js';

const peakRate  = parseInt(__ENV.PEAK_RATE  || '14');
const troughRate = parseInt(__ENV.TROUGH_RATE || '3');

// One wave: trough → ramp → peak → drop
const oneWave = [
  { target: troughRate, duration: '1m' },   // trough (LOW)
  { target: peakRate,   duration: '1m30s' }, // ramp up
  { target: peakRate,   duration: '2m' },   // peak hold (HIGH)
  { target: troughRate, duration: '30s' },  // drop
];

export const options = {
  scenarios: {
    periodic: {
      executor:        'ramping-arrival-rate',
      startRate:       troughRate,
      timeUnit:        '1s',
      preAllocatedVUs: 30,
      maxVUs:          100,
      stages: [
        { target: troughRate, duration: '1m' }, // warm-up
        ...oneWave,
        ...oneWave,
        { target: troughRate, duration: '1m' }, // cooldown
      ],
    },
  },
  thresholds: {
    http_req_failed:   ['rate<0.02'],
    http_req_duration: ['p(95)<1500'],
  },
  tags: {
    run_id:     RUN_ID,
    scenario:   'periodic',
    peak_rate:  String(peakRate),
    trough_rate: String(troughRate),
  },
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
  console.log(`[${RUN_ID}] Periodic done. p95=${data.metrics.http_req_duration?.values?.['p(95)']} ms`);
  return {};
}
