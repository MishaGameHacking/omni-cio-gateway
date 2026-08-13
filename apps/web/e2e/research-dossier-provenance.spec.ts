import { expect, test } from "@playwright/test";
import fs from "node:fs";

const markupProvider = ["<", "em", ">Untrusted provider label</", "em", ">"].join("");
const markupFact = ["<", "svg>", "LONG SOURCE TEXT ".repeat(80), "</", "svg", ">"].join("");
const aiText = ["<", "strong", ">MODEL INTERPRETATION</", "strong", "> ", "synthetic summary ".repeat(30)].join("");

function fact(index: number) {
  return {
    record_sha256: `${String(index).padStart(64, "a")}`.slice(-64),
    fact_type: index === 0 ? "material_event" : "fundamental",
    fact_key: index === 0 ? "material_event.board_update" : `fundamental.metric_${index}`,
    value: { type: "text", canonical: index === 2 ? markupFact : `Synthetic value ${index}`, currency: null },
    use: "decision_grade",
    confidence: index === 3 ? "LIMITED" : "DECISION_GRADE",
    freshness: "FRESH",
    source: {
      provider: index === 2 ? markupProvider : `Synthetic source ${index}`,
      class: "issuer",
      authority: "official",
      source_id: `source-${index}`,
      location: index === 2 ? null : `https://example.test/source/${index}`,
      location_rejected: index === 2,
      retrieved_at: "2026-08-13T18:00:00+00:00",
      published_at: "2026-08-13T17:00:00+00:00",
      effective_at: "2026-08-13T17:00:00+00:00",
    },
    contradiction: index === 3 ? { severity: "critical", comparison_period: "2026-Q2", distinct_values: ["100", "120"] } : null,
  };
}

function payload(stale = false) {
  const facts = Array.from({ length: 28 }, (_, index) => fact(index));
  if (stale) facts[0].freshness = "STALE";
  return {
    schema_version: "1.0.0",
    generated_at: "2026-08-13T18:00:00+00:00",
    state: stale ? "STALE" : "PARTIAL",
    truncated: false,
    invalid_dossier_count: 0,
    duplicate_dossier_count: 0,
    dossiers: [{
      cache_key: "research:instrument-1",
      source_identity: "research-evidence-v1",
      content_sha256: "b".repeat(64),
      cache_retrieved_at: "2026-08-13T18:00:00+00:00",
      cache_expires_at: stale ? "2026-08-13T17:00:00+00:00" : "2026-08-13T20:00:00+00:00",
      cache_freshness: stale ? "STALE" : "FRESH",
      dossier_sha256: "c".repeat(64),
      assessed_at: "2026-08-13T18:00:00+00:00",
      state: stale ? "STALE" : "PARTIAL",
      decision_ready: true,
      strong_recommendation_allowed: false,
      security: { instrument_id: "instrument:v1:one", instrument_uid: "instrument-1", instrument_type: "share", ticker: "SYNTH", name: "Synthetic Issuer", figi: "BBG000000001", isin: "RU000A000001" },
      facts,
      contradictions: [{ fact_key: "fundamental.metric_3", comparison_period: "2026-Q2", severity: "critical", record_sha256s: [facts[3].record_sha256, "d".repeat(64)], distinct_values: ["100", "120"], unresolved: true }],
      unknowns: [{ requirement_id: "req-material", fact_type: "fundamental", importance: "material", reason: "stale_record" }],
      timeline: [{ record_sha256: facts[0].record_sha256, fact_type: "material_event", fact_key: "material_event.board_update", value: "Board approved synthetic policy update", currency: null, at: "2026-08-13T17:00:00+00:00", source_label: "Synthetic source 0 · issuer", confidence: "DECISION_GRADE" }],
      links: { credit: "/risks?instrument_uid=instrument-1", fund: null },
      ai_summary: { state: "AVAILABLE", non_authoritative: true, text: aiText, generated_at: "2026-08-13T18:01:00+00:00", model_label: "synthetic-test-model", confidence: "LOW" },
    }],
  };
}

async function mockShell(page: import("@playwright/test").Page, body: object) {
  await page.route("**/api/v10/web/session", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ authenticated: true, user_label: "OWNER", tenant_label: "Personal" }) }));
  await page.route("**/api/v10/web/auth/providers", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route("**/api/v10/web/private-test-login/status", (route) => route.fulfill({ status: 200, contentType: "application/json", body: '{"enabled":false}' }));
  await page.route("**/api/v10/web/health", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ state: "READY", freshness: "FRESH", checked_at: "2026-08-13T18:00:00Z" }) }));
  await page.route("**/api/v10/web/research-dossiers", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }));
}

test("WP20 keeps canonical facts distinct from inference with long evidence", async ({ page }, testInfo) => {
  await mockShell(page, payload());
  await page.goto("/research");
  await expect(page.getByRole("heading", { name: "Research Dossier" })).toBeVisible();
  await expect(page.locator('[data-origin="canonical-source-fact"]')).toHaveCount(28);
  await expect(page.locator('[data-origin="canonical-source-facts"]')).toBeVisible();
  await expect(page.locator('[data-origin="ai-inference"]')).toBeVisible();
  await expect(page.getByText("AI / INFERENCE · NON-AUTHORITATIVE", { exact: true })).toBeVisible();
  await expect(page.getByText("НЕ ИСТОЧНИК ФАКТОВ", { exact: true })).toBeVisible();
  await expect(page.getByText(/LONG SOURCE TEXT LONG SOURCE TEXT/)).toBeVisible();
  await expect(page.getByText(markupProvider, { exact: false })).toBeVisible();
  await expect(page.locator('[data-origin="canonical-source-facts"] em')).toHaveCount(0);
  await expect(page.locator('[data-origin="canonical-source-facts"] svg')).toHaveCount(0);
  await expect(page.getByText(aiText, { exact: false })).toBeVisible();
  await expect(page.locator('[data-origin="ai-inference"] strong')).toHaveCount(0);
  const screenshot = await page.screenshot({ fullPage: true, animations: "disabled" });
  const output = testInfo.outputPath("wp20-research-provenance.png");
  fs.writeFileSync(output, screenshot);
  await testInfo.attach("wp20-research-provenance", { path: output, contentType: "image/png" });
});

test("WP20 keeps stale contradictions and unknowns explicit", async ({ page }) => {
  await mockShell(page, payload(true));
  await page.goto("/research");
  await expect(page.getByText("Research view STALE", { exact: true })).toBeVisible();
  await expect(page.getByText("Research dossier STALE", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Contradictions" })).toBeVisible();
  await expect(page.getByText("CRITICAL · fundamental.metric_3", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Unknowns / coverage gaps" })).toBeVisible();
  await expect(page.getByText("fundamental · stale_record", { exact: true })).toBeVisible();
});
