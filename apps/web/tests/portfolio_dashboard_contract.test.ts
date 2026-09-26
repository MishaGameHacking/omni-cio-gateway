import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { appRouteFeatureByPath } from "../src/app-shell/contracts.ts";

const dashboard = readFileSync(new URL("../src/app-shell/portfolio-dashboard.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/app-shell/api.ts", import.meta.url), "utf8");
const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
const contracts = readFileSync(new URL("../src/app-shell/contracts.ts", import.meta.url), "utf8");

test("WP18 replaces Portfolio and Assets placeholders inside the accepted shell", () => {
  assert.equal(appRouteFeatureByPath["/portfolio"], "portfolio-dashboard");
  assert.equal(appRouteFeatureByPath["/assets"], "portfolio-assets");
  assert.match(shell, /PortfolioDashboardPage/);
  assert.match(dashboard, /Current-on-demand READ snapshot/);
});

test("WP18 currentness is explicit manual refresh without silent polling", () => {
  assert.match(dashboard, /silent polling отсутствует/);
  assert.match(dashboard, /"Обновить"/);
  assert.match(dashboard, /manual pull-to-refresh; no silent polling/);
  assert.doesNotMatch(dashboard, /setInterval\s*\(/);
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
  assert.match(dashboard, /T-Invest GetPortfolio\/GetPositions/);
  assert.match(dashboard, /T-Invest GetLastPrices/);
});

test("WP18 per-account summary surfaces stale and partial market state", () => {
  assert.match(dashboard, /current_market\.stale_instrument_count > 0/);
  assert.match(dashboard, /current_market\.missing_instrument_count > 0/);
  assert.match(dashboard, /current_market\.state === "PARTIAL"/);
  assert.match(dashboard, /currentMarketDisplayState/);
});

test("WP18 empty broker configuration is stable degraded state, not recovery", () => {
  assert.match(dashboard, /dashboard\.state === "UNAVAILABLE" \|\| dashboard\.state === "EMPTY"/);
  assert.match(dashboard, /return "DEGRADED" as const/);
  assert.match(dashboard, /Broker connection не подключён/);
});

test("WP18 surfaces broker connection state even when account snapshots are unavailable", () => {
  assert.match(dashboard, /dashboard\?\.state === "UNAVAILABLE"/);
  assert.match(dashboard, /Broker snapshot недоступен/);
  assert.match(dashboard, /Broker Connections/);
  assert.match(dashboard, /dashboard\.connections\.map/);
  assert.match(dashboard, /connection\.state/);
  assert.match(dashboard, /connection\.last_verified_at/);
});

test("WP18 multi-account rendering does not assume masked labels are unique", () => {
  assert.match(dashboard, /accounts\.map\(\(account, accountIndex\)/);
  assert.match(dashboard, /key=\{`\$\{account\.masked_account\}-\$\{accountIndex\}`\}/);
});

test("WP18 market quote is not modeled as universal money", () => {
  assert.match(contracts, /interface PortfolioMarketQuoteView/);
  assert.match(contracts, /quotation_unit:\s*string/);
  assert.match(contracts, /quotation_semantics:\s*string/);
  assert.match(contracts, /current_market_last_price:\s*PortfolioMarketQuoteView \| null/);
  assert.match(dashboard, /marketQuote/);
  assert.match(dashboard, /raw quote:/);
  assert.match(dashboard, /quotation_semantics/);
  assert.doesNotMatch(contracts, /current_market_last_price:\s*\(PortfolioMoneyView/);
});

test("WP18 position detail exposes identity and reviewed classification provenance", () => {
  assert.match(dashboard, /Position detail/);
  assert.match(dashboard, /Position UID/);
  assert.match(dashboard, /FIGI/);
  assert.match(dashboard, /ISIN/);
  assert.match(dashboard, /Issuer \/ sector \/ class/);
  assert.match(dashboard, /classification_source/);
  assert.match(dashboard, /classification_as_of/);
  assert.match(contracts, /issuer:\s*string \| null/);
  assert.match(contracts, /sector:\s*string \| null/);
});

test("WP18 does not fabricate research or incident links before their owning indexes", () => {
  assert.match(dashboard, /Research/);
  assert.match(dashboard, /no deterministic current-state WP18 binding/);
  assert.match(dashboard, /Incidents/);
  assert.match(dashboard, /no accepted instrument incident index in WP18/);
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
  assert.match(contracts, /available:\s*string \| null/);
  assert.match(contracts, /blocked:\s*string \| null/);
});

test("WP18 browser source contains no broker token storage surface", () => {
  const combined = `${dashboard}\n${api}\n${contracts}`;
  assert.doesNotMatch(combined, /secret_ref/);
  assert.doesNotMatch(combined, /account_fingerprint/i);
  const forbiddenStorageIdentifiers = [
    ["local", "Storage"].join(""),
    ["session", "Storage"].join(""),
  ];
  for (const identifier of forbiddenStorageIdentifiers) {
    assert.equal(dashboard.includes(identifier), false);
  }
});
