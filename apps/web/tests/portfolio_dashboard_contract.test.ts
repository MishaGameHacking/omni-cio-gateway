import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const dashboard = readFileSync(new URL("../src/app-shell/portfolio-dashboard.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/app-shell/api.ts", import.meta.url), "utf8");
const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
const contracts = readFileSync(new URL("../src/app-shell/contracts.ts", import.meta.url), "utf8");

test("WP18 replaces Portfolio and Assets placeholders inside the accepted shell", () => {
  assert.match(shell, /path === ["']\/portfolio["']/);
  assert.match(shell, /path === ["']\/assets["']/);
  assert.match(shell, /PortfolioDashboardPage/);
  assert.match(dashboard, /Live READ data/);
});

test("WP18 product API remains same-origin authenticated and no-store", () => {
  assert.match(api, /readPortfolioDashboard/);
  assert.match(api, /\/api\/v10\/web\/portfolio-dashboard/);
  assert.match(api, /credentials:\s*["']same-origin["']/);
  assert.match(api, /cache:\s*["']no-store["']/);
});

test("WP18 UI visibly carries source timestamp freshness and completeness", () => {
  assert.match(contracts, /source:\s*string/);
  assert.match(contracts, /as_of:\s*string/);
  assert.match(contracts, /freshness/);
  assert.match(contracts, /unresolved_position_count/);
  assert.match(dashboard, /As-of \/ источник/);
  assert.match(dashboard, /Completeness/);
  assert.match(dashboard, /Freshness/);
});

test("WP18 never implies unsafe cross-currency or universal market conversion", () => {
  assert.match(dashboard, /Cross-currency aggregation без явного FX conversion запрещён/);
  assert.match(dashboard, /market_conversion_state/);
  assert.match(contracts, /cross_currency_aggregation/);
  assert.match(contracts, /current_market_value/);
});

test("WP18 exposes empty unavailable partial and stale states instead of silent zeroes", () => {
  assert.match(dashboard, /Portfolio API недоступен/);
  assert.match(dashboard, /Нулевые значения не подставлены/);
  assert.match(dashboard, /Broker connection не подключён/);
  assert.match(dashboard, /unresolved/);
  assert.match(dashboard, /STALE/);
});

test("WP18 browser source contains no broker token storage surface", () => {
  const combined = `${dashboard}\n${api}\n${contracts}`;
  assert.doesNotMatch(combined, /secret_ref/);
  assert.doesNotMatch(combined, /account_fingerprint/i);
  assert.doesNotMatch(dashboard, /localStorage|sessionStorage/);
});
