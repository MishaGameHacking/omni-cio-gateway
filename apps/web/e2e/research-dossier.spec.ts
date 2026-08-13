import { expect, test } from "@playwright/test";
import fs from "node:fs";

const fixtures = JSON.parse(
  fs.readFileSync(new URL("../tests/fixtures/wp20_research_dossier.golden.json", import.meta.url), "utf8"),
) as Record<"ready" | "partial", any>;

async function mockShell(page: import("@playwright/test").Page) {
  await page.route("**/api/v10/web/session", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ authenticated: true, user_label: "OWNER", tenant_label: "Personal" }) }));
  await page.route("**/api/v10/web/auth/providers", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route("**/api/v10/web/private-test-login/status", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: '{"enabled":false}' }));
  await page.route("**/api/v10/web/health", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ state: "READY", freshness: "FRESH", checked_at: "2026-08-13T18:00:00Z" }) }));
}

async function mockResearch(page: import("@playwright/test").Page, payload: unknown) {
  await page.route("**/api/v10/web/research-dossiers", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) }));
}

test("WP20 source facts cannot be visually or semantically confused with AI inference", async ({ page }, testInfo) => {
  await mockShell(page);
  await mockResearch(page, fixtures.ready);
  await page.goto("/research");

  await expect(page.getByRole("heading", { name: "Research: provenance before interpretation" })).toBeVisible();
  const fact = page.locator('[data-authority="source-evidence"]');
  const ai = page.locator('[data-authority="ai-non-authoritative"]');
  await expect(fact).toHaveCount(1);
  await expect(ai).toHaveCount(1);
  await expect(fact.getByText("SOURCE FACT", { exact: true })).toBeVisible();
  await expect(ai.getByText("НЕ ИСТОЧНИК ФАКТА", { exact: true })).toBeVisible();
  await expect(ai.getByText(/Non-authoritative interpretation/)).toBeVisible();

  const htmlLike = page.getByText("<strong>External text stays data</strong>", { exact: true });
  await expect(htmlLike).toBeVisible();
  await expect(page.locator(".research-fact__value strong")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "https://issuer.example.test/report/20" })).toHaveAttribute("href", "https://issuer.example.test/report/20");

  const screenshot = await page.screenshot({ fullPage: true, animations: "disabled" });
  const output = testInfo.outputPath("wp20-research-authority-separation.png");
  fs.writeFileSync(output, screenshot);
  await testInfo.attach("wp20-research-authority-separation", { path: output, contentType: "image/png" });
});

test("WP20 stale contradictory evidence and unknowns remain explicit", async ({ page }) => {
  await mockShell(page);
  await mockResearch(page, fixtures.partial);
  await page.goto("/research");

  await expect(page.getByText("Противоречия", { exact: true })).toBeVisible();
  await expect(page.getByText("Неизвестно / coverage gaps", { exact: true })).toBeVisible();
  await expect(page.getByText("STALE", { exact: true })).toHaveCount(2);
  await expect(page.getByText("CONTRADICTED", { exact: true })).toHaveCount(2);
  await expect(page.getByText(/AI summary недоступен/)).toBeVisible();
  await expect(page.getByText("ftp://example.test/document", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "ftp://example.test/document" })).toHaveCount(0);
});

test("WP20 long source lists and long text remain readable on narrow layout", async ({ page }) => {
  await mockShell(page);
  const payload = structuredClone(fixtures.ready);
  const baseFact = payload.dossiers[0].facts[0];
  payload.dossiers[0].ai_summary = { state: "UNAVAILABLE" };
  payload.dossiers[0].facts = Array.from({ length: 48 }, (_, index) => ({
    ...baseFact,
    record_sha256: `record:long-${index}`,
    fact_key: `report.long_fact_${index}`,
    value: { ...baseFact.value, canonical: `Long source text ${index}: ${"x".repeat(1200)}` },
    source: { ...baseFact.source, source_id: `long-source-${index}`, location_text: `https://issuer.example.test/report/${index}`, href: `https://issuer.example.test/report/${index}` },
  }));
  payload.dossiers[0].timeline = payload.dossiers[0].facts.map((fact: any) => ({ event_at: fact.event_at, record_sha256: fact.record_sha256, fact_key: fact.fact_key, value: fact.value, source_class: fact.source.source_class }));
  payload.dossiers[0].counts.facts = 48;

  await mockResearch(page, payload);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/research");
  await expect(page.getByText("report.long_fact_47", { exact: true })).toBeVisible();
  await expect(page.getByText(/^Long source text 47:/)).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflow).toBe(false);
});
