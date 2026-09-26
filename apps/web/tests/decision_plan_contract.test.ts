import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { appRouteFeatureByPath } from "../src/app-shell/contracts.ts";

const page = readFileSync(new URL("../src/app-shell/decision-plan.tsx", import.meta.url), "utf8");
const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
const backend = readFileSync(new URL("../../../omni_cio/web/decision_plan_v1.py", import.meta.url), "utf8");

const browserStores = [["local", "Storage"].join(""), ["session", "Storage"].join("")];

test("WP21 replaces Risk Decision Plan placeholders in one accepted shell", () => {
  assert.match(shell, /DecisionPlanPage/);
  assert.equal(appRouteFeatureByPath["/risks"], "decision-risks");
  assert.equal(appRouteFeatureByPath["/decisions"], "decision-decisions");
  assert.equal(appRouteFeatureByPath["/plans"], "decision-plans");
});

test("WP21 exposes deterministic main decision and exact immutable plan math", () => {
  for (const token of [
    "MAIN_DECISION",
    "Risk before / after",
    "Targets, lots, costs, cash",
    "Exact target positions",
    "Exact immutable plan legs",
    "Constraints, blockers, evidence",
    "Cancellation constraints",
    "Version",
    "Alternatives",
  ]) {
    assert.equal(page.includes(token), true, token);
  }
  for (const value of ["NO_ACTION", "HOLD", "REDUCE", "EXIT", "REALLOCATE"]) {
    assert.equal(backend.includes(`\"${value}\"`), true, value);
  }
  assert.equal(page.includes("Number("), false, "WP21 does not convert Decimal strings through binary float");
  assert.equal(page.includes("* 100"), false, "WP21 does not recompute source weights in the browser");
  assert.match(page, /row\.target_weight/);
  assert.match(page, /state\.concentration\.top_1_weight/);
  assert.match(page, /plan\.plan_sha256/);
  assert.match(page, /plan\.schema_version/);
  assert.match(page, /plan\.expires_at/);
  assert.match(page, /plan\.cancellation_conditions/);
});

test("WP21 approval subject is preview-only and has no Web mutation authority", () => {
  assert.match(page, /FUTURE OWNER CONFIRMATION SUBJECT · PREVIEW ONLY/);
  assert.match(page, /Can approve here/);
  assert.match(page, />NO</);
  assert.match(backend, /"can_approve": False/);
  assert.match(backend, /"mutation_invalidates": True/);
  assert.match(backend, /"execution_authorized": False/);
  assert.match(backend, /"trading_methods": False/);
  assert.equal(page.includes("Подтвердить план"), false);
});

test("WP21 read route is session tenant scoped bounded and no-store", () => {
  assert.match(page, /credentials: "same-origin"/);
  assert.match(page, /cache: "no-store"/);
  assert.match(backend, /sessions\.resolve/);
  assert.match(backend, /tenant_id=scope\.tenant_id/);
  assert.match(backend, /_MAX_BLOB_BYTES/);
  assert.match(backend, /Cache-Control/);
  assert.match(backend, /WHERE d\.tenant_id = %s/);
});

test("WP21 validates canonical blobs and exact persisted bindings", () => {
  assert.match(backend, /hashlib\.sha256\(payload\)\.hexdigest\(\) == expected_sha256/);
  assert.match(backend, /DecisionSetV1\.model_validate/);
  assert.match(backend, /PortfolioPlanV1\.model_validate/);
  assert.match(backend, /_DECISION_SCHEMA_REF/);
  assert.match(backend, /_PLAN_SCHEMA_REF/);
  assert.match(backend, /JOIN omni_cio_v10\.portfolio_snapshots s/);
  assert.match(backend, /JOIN omni_cio_v10\.policies pol/);
  assert.match(backend, /s\.source_payload_sha256/);
  assert.match(backend, /pol\.source_policy_id/);
  assert.match(backend, /PLAN_RECORD_BINDING_INVALID/);
  assert.match(backend, /PLAN_PAYLOAD_INVALID/);
  assert.match(backend, /DECISION_ABSTAINS_WAIT_FOR_DATA/);
});

test("WP21 remains read-only and stores no browser credentials", () => {
  const combined = `${page}\n${backend}`;
  for (const forbidden of [
    "@app.post(",
    "@app.put(",
    "@app.patch(",
    "@app.delete(",
    "submit_order",
    "withdraw",
    "TINVEST_TRADING_TOKEN",
    ...browserStores,
  ]) {
    assert.equal(combined.includes(forbidden), false, forbidden);
  }
});
