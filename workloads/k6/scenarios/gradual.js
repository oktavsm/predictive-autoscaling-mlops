/**
 * GRADUAL INCREASE workload — traffic rises progressively over time.
 *
 * Purpose:
 *   - Study the relationship between request rate and resource usage.
 *   - Observe exact HPA scaling thresholds in context.
 *   - Primary dataset for the ML model — the model learns how resource
 *     usage changes as a function of load over time.
 *   - Compare reactive vs predictive response to sustained growth.
 *
 * Shape:
 *   req/s
 *     │              ___________
 *     │         ____/
 *     │    ____/
 *     │___/
 *     └──────────────────────────→ time
 *
 * Stages (calibration-derived):
 *   0-3m   →  3  req/s  (LOW: 1 replica baseline)
 *   3-8m   →  8  req/s  (MEDIUM: HPA trigger zone)
 *   8-13m  → 14  req/s  (HIGH: 3 replicas expected)
 *   13-18m → 18  req/s  (near SATURATION)
 *   18-20m →  3  req/s  (cooldown — observe scale-down)
 *
 * Usage:
 *   k6 run workloads/k6/scenarios/gradual.js
 *   BASE_URL=https://api.titipin.me RUN_ID=gradual-001 k6 run workloads/k6/scenarios/gradual.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { BASE_URL, RUN_ID } from '../common/config.js';
import { pickEndpoint } from '../common/endpoints.js';

export const options = {
  scenarios: {
    gradual: {
      executor:        'ramping-arrival-rate',
      startRate:       3,
      timeUnit:        '1s',
      preAllocatedVUs: 30,
      maxVUs:          100,
      stages: [
        { target: 3,  duration: '1m' },   // hold LOW (3 req/s) — baseline
        { target: 8,  duration: '2m' },   // ramp to MEDIUM (8 req/s) — HPA trigger
        { target: 14, duration: '2m' },   // ramp to HIGH (14 req/s) — 3 replicas
        { target: 18, duration: '2m' },   // ramp to SATURATION (18 req/s) — 4 replicas
        { target: 3,  duration: '1m' },   // cooldown (3 req/s) — scale-down
      ],
    },
  },
  thresholds: {
    http_req_failed:   ['rate<0.02'],
    http_req_duration: ['p(95)<1500'],
  },
  tags: { run_id: RUN_ID, scenario: 'gradual' },
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
  console.log(`[${RUN_ID}] Gradual done. p95=${data.metrics.http_req_duration?.values?.['p(95)']} ms`);
  return {};
}
