import http from 'k6/http';
import { check } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'https://api.titipin.me';

const endpoints = [
  '/api/v1/categories',
  '/api/v1/jastip/listings',
  '/api/v1/preloved/listings',
  '/api/v1/jastip/requests',
  '/api/v1/preloved/requests',
];

export const options = {
  scenarios: {
    calibration: {
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      preAllocatedVUs: 20,
      maxVUs: 100,
      stages: [
        { target: 1, duration: '1m' },
        { target: 5, duration: '2m' },
        { target: 10, duration: '2m' },
        { target: 15, duration: '2m' },
        { target: 20, duration: '2m' },
        { target: 1, duration: '1m' },
      ],
    },
  },
};

export default function () {
  const endpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
  const res = http.get(`${BASE_URL}${endpoint}`);

  check(res, {
    'HTTP < 500': (r) => r.status < 500,
  });
}
