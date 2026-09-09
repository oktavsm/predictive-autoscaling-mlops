/**
 * DRIFT: COMPOSITION scenario — same total RPS, different endpoint mix.
 *
 * Purpose:
 *   - Test whether the model breaks when CPU/latency behavior changes
 *     even though the raw request rate stays similar.
 *   - Composition drift: heavier endpoints (search, write-heavy) shift
 *     CPU profile at the same RPS.
 *
 * Methodology:
 *   Phase 1 (Training):     run `steady.js` at 8 req/s (read-heavy mix).
 *   Phase 2 (This script):  same 8 req/s but write-heavy endpoint mix.
 *   Expected outcome:       CPU usage and latency increase at the same RPS.
 *
 * Usage:
 *   k6 run workloads/k6/scenarios/drift-composition.js
 *   BASE_URL=https://api.titipin.me RUN_ID=drift-comp-001 \
 *     k6 run workloads/k6/scenarios/drift-composition.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { BASE_URL, RUN_ID } from '../common/config.js';
import { pickWriteHeavyEndpoint } from '../common/endpoints.js';  // ← write-heavy mix

const targetRate = parseInt(__ENV.RATE || '8');  // same rate as training steady
const duration   = __ENV.DURATION      || '15m';

export const options = {
  scenarios: {
    drift_composition: {
      executor:        'constant-arrival-rate',
      rate:            targetRate,
      timeUnit:        '1s',
      duration:        duration,
      preAllocatedVUs: 20,
      maxVUs:          60,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.03'],
  },
  tags: {
    run_id:   RUN_ID,
    scenario: 'drift-composition',
    mix:      'write-heavy',
    rate:     String(targetRate),
  },
};

const latency = new Trend('custom_latency_ms', true);
const errors  = new Counter('custom_errors');

export default function () {
  // Use write-heavy endpoint mix — same rate, different composition
  const url = `${BASE_URL}${pickWriteHeavyEndpoint()}`;
  const res = http.get(url, { tags: { name: url } });

  const ok = check(res, { 'status < 500': (r) => r.status < 500 });
  latency.add(res.timings.duration);
  if (!ok) errors.add(1);
}

export function handleSummary(data) {
  console.log(`[${RUN_ID}] Drift-composition done.`);
  return {};
}
