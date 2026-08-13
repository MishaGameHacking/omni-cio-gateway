import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const page = readFileSync(new URL("../src/app-shell/watchtower-incidents.tsx", import.meta.url), "utf8");
const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
const backend = readFileSync(new URL("../../../omni_cio/web/watchtower_incidents_v1.py", import.meta.url), "utf8");

test("WP19 replaces Watchtower placeholder inside the accepted application shell", () => {
  assert.match(shell, /path === ["']\/watchtower["']/);
  assert.match(shell, /WatchtowerIncidentsPage/);
  assert.match(page, /WATCHTOWER \/ INCIDENTS/);
});

test("WP19 page answers what why when and what happened after detection", () => {
  assert.match(page, /Что произошло/);
  assert.match(page, /Почему важно/);
  assert.match(page, /Когда/);
  assert.match(page, /Что сделала система/);
  assert.match(page, /Lifecycle timeline/);
  assert.match(page, /Decision links/);
  assert.match(page, /Plan links/);
});

test("WP19 exposes active resolved critical filters and reopened semantics", () => {
  assert.match(page, /"active" \| "resolved" \| "critical"/);
  assert.match(page, /REOPENED/);
  assert.match(page, /CLOSED → OPEN/);
});

test("WP19 same-origin API is authenticated by server session and no-store", () => {
  assert.match(page, /\/api\/v10\/web\/watchtower-incidents/);
  assert.match(page, /credentials:\s*["']same-origin["']/);
  assert.match(page, /cache:\s*["']no-store["']/);
  assert.match(backend, /sessions\.resolve/);
  assert.match(backend, /tenant_id=scope\.tenant_id/);
  assert.match(backend, /Cache-Control.*no-store/);
});

test("WP19 missing or conflicting alert evidence is explicit", () => {
  assert.match(page, /Alert evidence:/);
  assert.match(page, /не додумываются/);
  assert.match(backend, /Literal\["VERIFIED", "MISSING", "CONFLICT"\]/);
  assert.match(backend, /watchtower_alert_verified/);
});

test("WP19 does not add incident mutation broker write or browser secret storage", () => {
  const combined = `${page}\n${backend}`;
  assert.doesNotMatch(combined, /@app\.(post|put|patch|delete)\(/i);
  assert.doesNotMatch(combined, /acknowledgeIncident|closeIncident|reopenIncident/);
  assert.doesNotMatch(combined, /TINVEST_TRADING_TOKEN|submit_order|withdraw|transfer/i);
  assert.doesNotMatch(combined, /localStorage|sessionStorage|secret_ref|account_fingerprint/i);
});
