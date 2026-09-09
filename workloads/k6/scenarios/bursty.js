/**
 * BURSTY workload — irregular short bursts with different magnitudes.
 *
 * Purpose:
 *   - Add high-variance, unpredictable observations to the dataset.
 *   - Test forecasting robustness against noise.
 *   - Measure scaling behavior under less predictable, real-world-like traffic.
 *
 * Shape:
 *   req/s
 *     │       /\       /\
 *     │  /\  /  \  /\ /  \
 *     │_/  \/    \/  V    \____
 *     └──────────────────────────→ time
 *
 * Pattern:
 *   Intentionally varied — different heights (LOW/MEDIUM/HIGH) and
 *   different durations (30s to 3m). This mimics unpredictable real traffic
 *   and prevents the model from over-fitting to a single periodic shape.
 *
 * Usage:
 *   k6 run workloads/k6/scenarios/bursty.js
 *   BASE_URL=https://api.titipin.me RUN_ID=bursty-001 k6 run workloads/k6/scenarios/bursty.js
 */

import http from 'k6/http';
import { check } from 'k6';
import { Trend, Counter } from 'k6/metrics';
import { BASE_URL, RUN_ID } from '../common/config.js';
import { pickEndpoint } from '../common/endpoints.js';

export const options = {
  scenarios: {
    bursty: {
      executor:        'ramping-arrival-rate',
      startRate:       3,
      timeUnit:        '1s',
      preAllocatedVUs: 40,
      maxVUs:          120,
      stages: [
        // Start quiet
        { target: 3,  duration: '1m30s' },  // baseline trough
        // Burst 1: small-medium (MEDIUM)
        { target: 8,  duration: '30s'   },  // quick ramp
        { target: 8,  duration: '1m30s' },  // hold medium
        { target: 3,  duration: '30s'   },  // drop
        // Quiet interlude
        { target: 3,  duration: '1m'    },
        // Burst 2: large (HIGH)
        { target: 14, duration: '45s'   },  // ramp to high
        { target: 14, duration: '2m'    },  // hold high
        { target: 3,  duration: '30s'   },  // drop
        // Brief recovery
        { target: 3,  duration: '45s'   },
        // Burst 3: very large and fast (near SATURATION)
        { target: 18, duration: '30s'   },  // sharp ramp
        { target: 18, duration: '1m'    },  // short hold — stressful
        { target: 5,  duration: '30s'   },  // partial drop
        // Burst 4: small, overlapping the previous cooldown
        { target: 10, duration: '45s'   },
        { target: 10, duration: '1m30s' },
        { target: 3,  duration: '45s'   },
        // Final cooldown
        { target: 3,  duration: '2m'    },
      ],
    },
  },
  thresholds: {
    http_req_failed:   ['rate<0.05'],
    http_req_duration: ['p(95)<1500'],
  },
  tags: { run_id: RUN_ID, scenario: 'bursty' },
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
  console.log(`[${RUN_ID}] Bursty done. p95=${data.metrics.http_req_duration?.values?.['p(95)']} ms`);
  return {};
}
