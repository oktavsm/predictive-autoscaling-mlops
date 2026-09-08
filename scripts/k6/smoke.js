import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 2,
  duration: '30s',
};

const BASE_URL = __ENV.BASE_URL || 'https://api.titipin.me';

const endpoints = [
  '/api/v1/categories',
  '/api/v1/jastip/listings',
  '/api/v1/preloved/listings',
  '/api/v1/jastip/requests',
  '/api/v1/preloved/requests',
];

export default function () {
  const endpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
  const res = http.get(`${BASE_URL}${endpoint}`);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'HTTP < 500': (r) => r.status < 500,
  });

  sleep(0.5);
}
