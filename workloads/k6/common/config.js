/**
 * Shared runtime configuration.
 * Override via environment variables when running k6.
 *
 * Example:
 *   BASE_URL=https://api.titipin.me RUN_ID=steady-001 k6 run workloads/k6/scenarios/steady.js
 */

export const BASE_URL = __ENV.BASE_URL || 'https://api.titipin.me';
export const RUN_ID   = __ENV.RUN_ID   || 'run-' + Date.now();

// Workload range derived from calibration (2026-09-08):
//   ~3  req/s → 1 replica  (LOW)
//   ~8  req/s → HPA triggers, moves to 2 replicas  (MEDIUM)
//   ~14 req/s → 3 replicas  (HIGH)
//   ~15 req/s → 4 replicas (max)  (SATURATION edge)
//   ~20 req/s → all 4 replicas saturated, p95 latency begins climbing
export const LOAD = {
  LOW:        3,
  MEDIUM:     8,
  HIGH:      14,
  SATURATION: 20,
};
