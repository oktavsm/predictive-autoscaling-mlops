#!/usr/bin/env js
/**
 * k6 Traffic Spike Scenario for Predictive Autoscaler Verification
 * ================================================================
 * Mensimulasikan lonjakan trafik eskalatif ke backend API Laravel
 * untuk membuktikan predictive autoscaler bereaksi SEBELUM puncak trafik.
 *
 * Usage: k6 run workloads/k6/scenarios/spike.js -e TARGET_URL=https://api.titipin.me
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET_URL = __ENV.TARGET_URL || 'https://api.titipin.me';

export const options = {
  stages: [
    { duration: '30s', target: 30 },   // Warm-up baseline
    { duration: '60s', target: 60 },   // Steady state
    { duration: '60s', target: 120 },  // Ramp spike (Phase 1)
    { duration: '60s', target: 200 },  // Peak spike (Phase 2)
    { duration: '30s', target: 200 },  // Hold peak
    { duration: '30s', target: 30 },   // Cool-down
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% requests under 2s
    http_req_failed: ['rate<0.10'],    // Error rate under 10%
  },
};

export default function () {
  // Mix of different API endpoints to simulate realistic traffic
  const endpoints = [
    `${TARGET_URL}/`,
    `${TARGET_URL}/`,
    `${TARGET_URL}/`,
  ];

  const url = endpoints[Math.floor(Math.random() * endpoints.length)];
  const res = http.get(url, {
    headers: {
      'Accept': 'application/json',
      'X-Traffic-Source': 'predictive-autoscaler-spike',
    },
    timeout: '10s',
  });

  check(res, {
    'status 2xx or 3xx': (r) => r.status >= 200 && r.status < 400,
    'response time < 2s': (r) => r.timings.duration < 2000,
  });

  sleep(Math.random() * 0.5 + 0.1); // 0.1–0.6s think time
}
