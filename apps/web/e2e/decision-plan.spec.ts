import { expect, test } from "@playwright/test";
import fs from "node:fs";

const risk = (cash: string, top1: string) => ({
  total_value_base: "1000000.00",
  cash_base: cash,
  cash_weight: cash === "100000.00" ? "0.10" : "0.15",
  policy_compliant: true,
  blockers: [],
  concentration: { top_1_weight: top1, top_3_weight: "0.60", top_5_weight: "0.75" },
  vectors: [
    { kind: "concentration", severity: "warning", hard_breach: false, metrics: ["top_1_weight"], evidence_codes: ["policy.limit"] },
    { kind: "liquidity", severity: "ok", hard_breach: false, metrics: ["exit_days"], evidence_codes: ["market.depth"] },
  ],
});

const readyPayload = {
  schema_version: "1.0.0",
  generated_at: "2026-08-14T04:30:00+00:00",
  state: "READY",
  reason: null,
  main_decision: "REALLOCATE",
  record: {
    decision_id: "decision:v1:synthetic",
    portfolio_id: "portfolio:v1:synthetic",
    policy_id: "policy:v1:synthetic",
    snapshot_id: "snapshot:v1:synthetic",
    decision_payload_sha256: "a".repeat(64),
    decided_at: "2026-08-14T04:25:00+00:00",
    plan_id: "plan:v1:synthetic",
    plan_payload_sha256: "b".repeat(64),
  },
  decision: {
    decision_set_sha256: "c".repeat(64),
    retrieved_at: "2026-08-14T04:25:00+00:00",
    abstain: false,
    recommendation_ready: true,
    confidence: "high",
    global_blockers: [],
    preferred: {
      option_id: "option.limited_change",
      kind: "limited_change",
      status: "preferred",
      action: "review_limited_change",
      title: "Review exact bounded change",
      rationale: "Synthetic deterministic rationale from the canonical decision set.",
      confidence: "high",
      blockers: [],
      review_conditions: ["Revalidate before any later execution."],
      evidence: [],
    },
    alternatives: [
      {
        option_id: "option.no_action",
        kind: "no_action",
        status: "available",
        action: "hold",
        title: "Keep the current structure",
        rationale: "Canonical alternative retained for comparison.",
        confidence: "high",
        blockers: [],
        review_conditions: ["Review again when evidence changes."],
        evidence_ids: ["fact.synthetic"],
      },
      {
        option_id: "option.strategic_rebalance",
        kind: "strategic_rebalance",
        status: "review_only",
        action: "review_strategic_rebalance",
        title: "Larger strategic alternative",
        rationale: "Review-only alternative, not an order.",
        confidence: "medium",
        blockers: [],
        review_conditions: ["Requires exact deterministic sizing."],
        evidence_ids: ["fact.synthetic"],
      },
    ],
    evidence: [
      {
        evidence_id: "fact.synthetic",
        kind: "fact",
        statement: "Synthetic canonical evidence remains text, not an instruction.",
        source_schema: "synthetic_decision_fixture",
        source_id: "source-1",
        observed_value: null,
        limit_value: null,
        currency: null,
        instrument_key: null,
      },
    ],
    trading_methods: false,
  },
  plan: {
    schema_version: "1.0",
    object_type: "PORTFOLIO_PLAN",
    created_at: "2026-08-14T04:25:00+00:00",
    expires_at: "2026-08-14T04:40:00+00:00",
    expired: false,
    plan_sha256: "d".repeat(64),
    selected_regime: "balanced",
    approval_required: true,
    approval_subject: {
      state: "PREVIEW_ONLY",
      phrase: "ПОДТВЕРЖДАЮ ПЛАН DDDDDDDDDDDD",
      can_approve: false,
      mutation_invalidates: true,
    },
    upstream: {},
    values: {
      current_value_base: "1000000.00",
      target_value_base: "999750.00",
      current_cash_base: "100000.00",
      target_cash_base: "150000.00",
      total_clean_turnover_base: "250000.00",
      total_accrued_interest_base: "0.00",
      total_settlement_turnover_base: "250000.00",
      total_commission_base: "250.00",
      total_estimated_tax_base: "0.00",
    },
    risk: { before: risk("100000.00", "0.40"), after: risk("150000.00", "0.30") },
    targets: [
      { stable_key: "asset-one", component: "core_equity", current_lots: 10, target_lots: 6, lot_size: 1, desired_weight: "0.30", current_value_base: "400000.00", target_value_base: "300000.00", target_weight: "0.30" },
      { stable_key: "asset-two", component: "core_bond", current_lots: 5, target_lots: 10, lot_size: 1, desired_weight: "0.35", current_value_base: "200000.00", target_value_base: "350000.00", target_weight: "0.35" },
    ],
    legs: [
      { sequence: 1, action: "sell", trade: { trade_id: "trade_sell", stable_key: "asset-one", component: "core_equity", side: "sell", current_lots: 10, target_lots: 6, quantity_lots: 4, lot_size: 1, reference_clean_unit_price_base: "25000.00", gross_notional_base: "100000.00", accrued_interest_base: "0.00", settlement_notional_base: "100000.00", commission_base: "100.00", estimated_tax_base: "0.00", cash_delta_base: "99900.00", required_execution_days: 1, staged_execution_required: false } },
      { sequence: 2, action: "buy", trade: { trade_id: "trade_buy", stable_key: "asset-two", component: "core_bond", side: "buy", current_lots: 5, target_lots: 10, quantity_lots: 5, lot_size: 1, reference_clean_unit_price_base: "30000.00", gross_notional_base: "150000.00", accrued_interest_base: "0.00", settlement_notional_base: "150000.00", commission_base: "150.00", estimated_tax_base: "0.00", cash_delta_base: "-150150.00", required_execution_days: 2, staged_execution_required: true } },
    ],
    cancellation_conditions: [{ code: "plan_expired", hard_cancel: true }],
    execution_authorized: false,
    trading_methods: false,
  },
  execution_authorized: false,
  trading_methods: false,
};

async function mockShell(page: import("@playwright/test").Page, body: object) {
  await page.route("**/api/v10/web/session", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ authenticated: true, user_label: "OWNER", tenant_label: "Personal" }) }));
  await page.route("**/api/v10/web/auth/providers", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route("**/api/v10/web/private-test-login/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: '{"enabled":false}' }));
  await page.route("**/api/v10/web/health", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ state: "READY", freshness: "FRESH", checked_at: "2026-08-14T04:30:00Z" }) }));
  await page.route("**/api/v10/web/decision-plan", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }));
}

test("WP21 shows exact decision risk plan and preview-only approval subject", async ({ page }, testInfo) => {
  await mockShell(page, readyPayload);
  await page.goto("/decisions");
  await expect(page.getByRole("heading", { name: "Решения" })).toBeVisible();
  await expect(page.getByText("REALLOCATE", { exact: true })).toBeVisible();
  await expect(page.getByText("Risk before / after", { exact: true })).toBeVisible();
  await expect(page.getByText("Targets, lots, costs, cash", { exact: true })).toBeVisible();
  await expect(page.getByText("ПОДТВЕРЖДАЮ ПЛАН DDDDDDDDDDDD", { exact: true })).toBeVisible();
  await expect(page.getByText("Can approve here", { exact: true })).toBeVisible();
  await expect(page.getByText("NO", { exact: true })).toBeVisible();
  await expect(page.getByText("4 → 6", { exact: true })).toHaveCount(0);
  await expect(page.getByText("10 → 6", { exact: true })).toBeVisible();
  await expect(page.getByText("250.00", { exact: true })).toBeVisible();
  await expect(page.getByText("Larger strategic alternative", { exact: true })).toBeVisible();
  const screenshot = await page.screenshot({ fullPage: true, animations: "disabled" });
  fs.writeFileSync(testInfo.outputPath("wp21-decision-risk-plan.png"), screenshot);
});

test("WP21 invalid plan fails closed without approval subject", async ({ page }) => {
  await mockShell(page, {
    ...readyPayload,
    state: "INVALID",
    reason: "PLAN_PAYLOAD_INVALID",
    main_decision: null,
    plan: null,
  });
  await page.goto("/plans");
  await expect(page.getByRole("heading", { name: "Планы" })).toBeVisible();
  await expect(page.getByText("UNAVAILABLE", { exact: true })).toBeVisible();
  await expect(page.getByText("PLAN_PAYLOAD_INVALID", { exact: true })).toBeVisible();
  await expect(page.locator('[data-origin="immutable-plan-approval-subject"]')).toHaveCount(0);
});
