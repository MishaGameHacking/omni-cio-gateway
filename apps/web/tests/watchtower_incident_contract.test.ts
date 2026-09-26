import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { appRouteFeatureByPath } from "../src/app-shell/contracts.ts";

const page = readFileSync(new URL("../src/app-shell/watchtower-incidents.tsx", import.meta.url), "utf8");
const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
const backend = readFileSync(new URL("../../../omni_cio/web/watchtower_incidents_v1.py", import.meta.url), "utf8");

test("WP19 replaces Watchtower placeholder inside the accepted application shell", () => {
  assert.equal(appRouteFeatureByPath["/watchtower"], "watchtower-incidents");
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
  assert.match(page, /aria-pressed=/);
});

test("WP19 severity presentation is distinct from freshness state", () => {
  assert.doesNotMatch(page, /StatusBadge/);
  assert.doesNotMatch(page, /"STALE"/);
  assert.match(page, /incident\.severity\.toUpperCase/);
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

test("WP19 attention impact comes from canonical alert without materiality inference", () => {
  assert.match(backend, /requires_owner_attention/);
  assert.match(backend, /OWNER_ATTENTION_REQUIRED/);
  assert.doesNotMatch(backend, /MATERIAL/);
});

test("WP19 does not add incident mutation broker write or browser secret storage", () => {
  const combined = `${page}\n${backend}`;
  assert.doesNotMatch(combined, /@app\.(post|put|patch|delete)\(/i);
  assert.doesNotMatch(combined, /acknowledgeIncident|closeIncident|reopenIncident/);
  assert.doesNotMatch(combined, /TINVEST_TRADING_TOKEN|submit_order|withdraw|transfer/i);
  const forbiddenBrowserStores = [["local", "Storage"].join(""), ["session", "Storage"].join("")];
  for (const identifier of forbiddenBrowserStores) assert.equal(combined.includes(identifier), false);
  assert.doesNotMatch(combined, /secret_ref|account_fingerprint/i);
});
