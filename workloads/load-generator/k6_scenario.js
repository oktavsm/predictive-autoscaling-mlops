import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET_URL = __ENV.TARGET_URL || 'https://api.titipin.me';
const THINK_MIN = parseFloat(__ENV.THINK_MIN || '0.2');
const THINK_MAX = parseFloat(__ENV.THINK_MAX || '0.8');

export const options = {
  discardResponseBodies: true,
  thresholds: {
    http_req_failed: ['rate<0.15'],
  },
};

const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
  'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.6613.88 Mobile Safari/537.36',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
];

export default function () {
  const ua = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
  const res = http.get(TARGET_URL, {
    headers: {
      'User-Agent': ua,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9,id;q=0.8',
      'X-Traffic-Source': 'cp-bcc-continuous-generator',
    },
    timeout: '8s',
  });

  check(res, {
    'status is 2xx': (r) => r.status >= 200 && r.status < 300,
  });

  const thinkTime = Math.random() * (THINK_MAX - THINK_MIN) + THINK_MIN;
  sleep(thinkTime);
}
