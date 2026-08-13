import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

interface GoldenDashboard {
  state: string;
  generated_at: string;
  accounts: Array<{
    freshness: { state: string; age_seconds: string; evaluated_at: string };
    completeness: string;
    broker_position_count: number;
    normalized_position_count: number;
    unresolved_position_count: number;
    portfolio_total: { amount: string; currency: string; source: string; as_of: string } | null;
    positions: Array<{
      quantity_units: string;
      blocked_units: string;
      broker_value: { amount: string; currency: string; source: string; as_of: string } | null;
      current_market_value: { amount: string; currency: string; source: string; as_of: string } | null;
      market_conversion_state: string;
      weight_within_position_currency_pct: string | null;
    }>;
    warnings: Array<{ code: string }>;
  }>;
}

const fixtures = JSON.parse(
  readFileSync(new URL("./fixtures/wp18_portfolio_dashboard.golden.json", import.meta.url), "utf8"),
) as Record<"normal" | "empty" | "partial" | "stale", GoldenDashboard>;

test("WP18 golden normal fixture preserves Decimal strings and provenance", () => {
  const normal = fixtures.normal;
  assert.equal(normal.state, "READY");
  assert.match(normal.generated_at, /[+]00:00$/);
  const account = normal.accounts[0];
  assert.ok(account);
  assert.equal(account.completeness, "complete");
  assert.equal(account.portfolio_total?.amount, "1000.25");
  assert.equal(account.portfolio_total?.currency, "RUB");
  assert.match(account.portfolio_total?.source ?? "", /T-Invest GetPortfolio/);
  assert.match(account.portfolio_total?.as_of ?? "", /[+]00:00$/);
  const position = account.positions[0];
  assert.ok(position);
  assert.equal(position.quantity_units, "3");
  assert.equal(position.broker_value?.amount, "30.00");
  assert.equal(position.current_market_value?.amount, "31.50");
  assert.equal(position.weight_within_position_currency_pct, "100");
  assert.equal(position.market_conversion_state, "DIRECT_SHARE_OR_ETF");
});

test("WP18 golden empty fixture is distinct from a zero-valued portfolio", () => {
  assert.equal(fixtures.empty.state, "EMPTY");
  assert.deepEqual(fixtures.empty.accounts, []);
});

test("WP18 golden partial fixture keeps unresolved data explicit", () => {
  const account = fixtures.partial.accounts[0];
  assert.ok(account);
  assert.equal(fixtures.partial.state, "PARTIAL");
  assert.equal(account.completeness, "partial");
  assert.equal(account.broker_position_count, 2);
  assert.equal(account.normalized_position_count, 1);
  assert.equal(account.unresolved_position_count, 1);
  assert.equal(account.portfolio_total, null);
  assert.ok(account.warnings.some((warning) => warning.code === "UNRESOLVED_BROKER_POSITIONS"));
});

test("WP18 golden stale fixture retains snapshot timestamp and stale age", () => {
  const account = fixtures.stale.accounts[0];
  assert.ok(account);
  assert.equal(account.freshness.state, "stale");
  assert.equal(account.freshness.age_seconds, "301");
  assert.match(account.freshness.evaluated_at, /[+]00:00$/);
  assert.ok(account.warnings.some((warning) => warning.code === "BROKER_SNAPSHOT_STALE"));
});

test("WP18 golden fixtures contain no credential or raw-account fields", () => {
  const encoded = JSON.stringify(fixtures);
  assert.doesNotMatch(encoded, /secret_ref|account_fingerprint|token|raw_account/i);
});
