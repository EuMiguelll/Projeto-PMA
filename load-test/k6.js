// Teste de carga com k6 (https://k6.io) — roda em container, sem instalar nada:
//   docker run --rm -i -e BASE_URL=http://<elb-dns> grafana/k6 run - < load-test/k6.js
// Local (compose):  -e BASE_URL=http://host.docker.internal:8080
// Cenários:
//   info      — rampa de usuários no GET /info (alvo do HPA; rota sem rate limit)
//   user_flow — usuários autenticados: login -> /auth/me -> /exchanges/USD/BRL
//               (exercita JWT, cache Redis e o rate limiting: 429 é esperado sob carga)
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8080';
const RAMP = __ENV.RAMP || '1m';   // subida
const HOLD = __ENV.HOLD || '3m';   // platô
const VUS = Number(__ENV.VUS || 100);
const JSON_HEADERS = { headers: { 'Content-Type': 'application/json' } };

export const options = {
  scenarios: {
    info: {
      executor: 'ramping-vus',
      exec: 'info',
      stages: [
        { duration: RAMP, target: VUS },
        { duration: HOLD, target: VUS },
        { duration: '30s', target: 0 },
      ],
    },
    user_flow: {
      executor: 'constant-vus',
      exec: 'userFlow',
      vus: Number(__ENV.USERS || 5),
      duration: HOLD,
      startTime: RAMP,
    },
  },
  thresholds: {
    'http_req_failed{scenario:info}': ['rate<0.01'],
    'http_req_duration{scenario:info}': ['p(95)<800'],
  },
};

export function setup() {
  const email = `k6.${Date.now()}@insper.edu.br`;
  const password = '123@321';
  http.post(`${BASE}/auth/register`, JSON.stringify({ name: 'k6', email, password }), JSON_HEADERS);
  return { email, password };
}

export function info() {
  const r = http.get(`${BASE}/info`);
  check(r, { 'info 200': (res) => res.status === 200 });
}

export function userFlow(user) {
  const login = http.post(`${BASE}/auth/login`, JSON.stringify(user), JSON_HEADERS);
  if (!check(login, { 'login 200': (r) => r.status === 200 })) { sleep(1); return; }
  // o cookie é "Secure": em HTTP o k6 não o reenvia sozinho, então mandamos no header
  const params = { headers: { Cookie: `__store_jwt_token=${login.cookies.__store_jwt_token[0].value}` } };
  for (let i = 0; i < 10; i++) {
    const me = http.get(`${BASE}/auth/me`, params);
    const ex = http.get(`${BASE}/exchanges/USD/BRL`, params);
    check(me, { 'me 200|429': (r) => r.status === 200 || r.status === 429 });
    check(ex, { 'exchange 200|429': (r) => r.status === 200 || r.status === 429 });
    sleep(0.2);
  }
}
