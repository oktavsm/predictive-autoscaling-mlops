/**
 * STEADY workload — constant load for a defined period.
 *
 * Purpose:
 *   - Establish a stable baseline for CPU, memory, latency, and replicas.
 *   - Verify monitoring completeness and data quality.
 *   - Generate the "normal" window used as the ML training reference.
 *
 * Derived from calibration (2026-09-08):
 *   - LOW    = 3  req/s → 1 replica, CPU ~5%
 *   - MEDIUM = 8  req/s → HPA wakes up, 1-2 replicas
 *   - HIGH   = 14 req/s → 3 replicas, CPU ~25% per pod
 *
 * Usage:
 *   k6 run workloads/k6/scenarios/steady.js
 *   BASE_URL=https://api.titipin.me RUN_ID=steady-001 RATE=8 k6 run workloads/k6/scenarios/steady.js
 *
 * ENV:
 *   BASE_URL   (default: https://api.titipin.me)
 *   RATE       target req/s  (default: 8 — MEDIUM)
 *   DURATION   how long to hold load (default: 15m)
 *   RUN_ID     tracing label (default: steady-<timestamp>)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { BASE_URL, RUN_ID } from '../common/config.js';
import { pickEndpoint } from '../common/endpoints.js';

const targetRate = parseInt(__ENV.RATE     || '8');
const duration   = __ENV.DURATION          || '15m';

export const options = {
  scenarios: {
    steady: {
      executor:         'constant-arrival-rate',
      rate:             targetRate,
      timeUnit:         '1s',
      duration:         duration,
      preAllocatedVUs:  20,
      maxVUs:           60,
    },
  },
  thresholds: {
    http_req_failed:   ['rate<0.02'],   // < 2% error rate
    http_req_duration: ['p(95)<1500'],  // p95 < 1500 ms
  },
  tags: { run_id: RUN_ID, scenario: 'steady', rate: String(targetRate) },
};

const latency = new Trend('custom_latency_ms', true);
const errors  = new Counter('custom_errors');

export default function () {
  const url = `${BASE_URL}${pickEndpoint()}`;
  const res = http.get(url, { tags: { name: url } });

  const ok = check(res, {
    'status < 500': (r) => r.status < 500,
    'status != 0':  (r) => r.status !== 0,
  });

  latency.add(res.timings.duration);
  if (!ok) errors.add(1);
}

export function handleSummary(data) {
  console.log(`[${RUN_ID}] Steady done. p95=${data.metrics.http_req_duration?.values?.['p(95)']} ms`);
  return {};
}
