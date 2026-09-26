import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { appRouteFeatureByPath } from "../src/app-shell/contracts.ts";

const page = readFileSync(new URL("../src/app-shell/research-dossiers.tsx", import.meta.url), "utf8");
const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
const backend = readFileSync(new URL("../../../omni_cio/web/research_dossiers_v1.py", import.meta.url), "utf8");

const rawHtmlEscapeHatch = ["dangerously", "SetInnerHTML"].join("");
const browserStores = [
  ["local", "Storage"].join(""),
  ["session", "Storage"].join(""),
];

test("WP20 replaces Research placeholder inside the accepted shell", () => {
  assert.equal(appRouteFeatureByPath["/research"], "research-dossiers");
  assert.match(shell, /ResearchDossiersPage/);
  assert.match(page, /RESEARCH \/ DOSSIERS/);
});

test("WP20 source facts and AI inference have different origins", () => {
  assert.match(page, /canonical-source-fact/);
  assert.match(page, /canonical-source-facts/);
  assert.match(page, /ai-inference/);
  assert.match(page, /AI \/ INFERENCE · NON-AUTHORITATIVE/);
  assert.match(page, /НЕ ИСТОЧНИК ФАКТОВ/);
  assert.equal(page.includes(rawHtmlEscapeHatch), false);
});

test("WP20 renders provenance freshness contradictions unknowns confidence and links", () => {
  for (const token of [
    "Published",
    "Retrieved",
    "Effective",
    "freshness",
    "Contradictions",
    "Unknowns / coverage gaps",
    "confidence",
    "Credit / Risk",
    "Fund / Assets",
    "Event timeline",
  ]) {
    assert.equal(page.toLowerCase().includes(token.toLowerCase()), true, token);
  }
});

test("WP20 read route is session scoped bounded and no-store", () => {
  assert.match(page, /research-dossiers/);
  assert.match(page, /credentials: "same-origin"/);
  assert.match(page, /cache: "no-store"/);
  assert.match(backend, /sessions\.resolve/);
  assert.match(backend, /tenant_id=scope\.tenant_id/);
  assert.match(backend, /_MAX_DOSSIERS = 100/);
  assert.match(backend, /_MAX_DOSSIER_BLOB_BYTES/);
  assert.match(backend, /Cache-Control/);
});

test("WP20 validates canonical dossier and exact instrument binding", () => {
  assert.match(backend, /ResearchDossierV1\.model_validate/);
  assert.match(backend, /_DOSSIER_SCHEMA_REF/);
  assert.match(backend, /dossier\.target\.instrument_uid != broker_uid/);
  assert.match(backend, /invalid_dossier_count/);
});

test("WP20 source URL allowlist is bounded to browser-safe web locations", () => {
  assert.match(backend, /http/);
  assert.match(backend, /https/);
  assert.match(backend, /parsed\.username/);
  assert.match(page, /noreferrer noopener/);
});

test("WP20 remains read-only and does not introduce browser secret storage", () => {
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
