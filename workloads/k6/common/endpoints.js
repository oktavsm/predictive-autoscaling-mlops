/**
 * Endpoint definitions for the Titip-In Laravel backend.
 *
 * ENDPOINT_MIX reflects a realistic read-heavy distribution:
 *   50% jastip listings   (browse, most common action)
 *   20% preloved listings (browse)
 *   15% categories        (lightweight lookup)
 *   10% jastip requests   (detail browse)
 *    5% preloved requests  (detail browse)
 *
 * The mix can be changed per-scenario by overriding the weighted array.
 */

export const ENDPOINTS = {
  categories:        '/api/v1/categories',
  jastipListings:    '/api/v1/jastip/listings',
  prelovedListings:  '/api/v1/preloved/listings',
  jastipRequests:    '/api/v1/jastip/requests',
  prelovedRequests:  '/api/v1/preloved/requests',
};

// Weighted pool — pick randomly to get the desired distribution.
export const WEIGHTED_POOL = [
  ...Array(10).fill(ENDPOINTS.jastipListings),    // 50%
  ...Array(4).fill(ENDPOINTS.prelovedListings),   // 20%
  ...Array(3).fill(ENDPOINTS.categories),         // 15%
  ...Array(2).fill(ENDPOINTS.jastipRequests),     // 10%
  ...Array(1).fill(ENDPOINTS.prelovedRequests),   //  5%
];

/** Pick one endpoint from the weighted pool at random. */
export function pickEndpoint() {
  return WEIGHTED_POOL[Math.floor(Math.random() * WEIGHTED_POOL.length)];
}

/**
 * Write-heavy pool for composition-drift scenarios.
 * More search/write endpoints shift CPU profile.
 */
export const WRITE_HEAVY_POOL = [
  ...Array(5).fill(ENDPOINTS.jastipListings),
  ...Array(5).fill(ENDPOINTS.prelovedListings),
  ...Array(3).fill(ENDPOINTS.jastipRequests),
  ...Array(4).fill(ENDPOINTS.prelovedRequests),
  ...Array(3).fill(ENDPOINTS.categories),
];

export function pickWriteHeavyEndpoint() {
  return WRITE_HEAVY_POOL[Math.floor(Math.random() * WRITE_HEAVY_POOL.length)];
}
