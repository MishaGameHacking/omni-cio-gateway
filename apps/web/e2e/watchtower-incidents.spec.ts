import { expect, test } from "@playwright/test";
import fs from "node:fs";

const fixtures = JSON.parse(fs.readFileSync(new URL("../tests/fixtures/wp19_watchtower_incidents.golden.json", import.meta.url), "utf8")) as Record<string, unknown>;

async function mockShell(page: import("@playwright/test").Page) {
  await page.route("**/api/v10/web/session", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ authenticated: true, user_label: "OWNER", tenant_label: "Personal" }) }));
  await page.route("**/api/v10/web/auth/providers", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route("**/api/v10/web/private-test-login/status", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: '{"enabled":false}' }));
  await page.route("**/api/v10/web/health", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ state: "READY", freshness: "FRESH", checked_at: "2026-08-13T14:00:00Z" }) }));
}

test("WP19 incident lifecycle is understandable and filters do not mutate state", async ({ page }, testInfo) => {
  await mockShell(page);
  await page.route("**/api/v10/web/watchtower-incidents", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fixtures.normal) }));
  await page.goto("/watchtower");
  await expect(page.getByRole("heading", { name: "Инциденты" })).toBeVisible();
  await expect(page.getByText("portfolio:owner", { exact: true })).toBeVisible();
  await expect(page.getByText("WATCHTOWER_CONCENTRATION_BREACH", { exact: true })).toBeVisible();
  await expect(page.getByText("YES — CLOSED → OPEN обнаружен", { exact: true })).toBeVisible();
  await expect(page.getByText("instrument:SYNTH", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Все" }).click();
  await expect(page.getByText("instrument:SYNTH", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Критические" }).click();
  await expect(page.getByText("portfolio:owner", { exact: true })).toBeVisible();
  await expect(page.getByText("instrument:SYNTH", { exact: true })).toHaveCount(0);
  const screenshot = await page.screenshot({ fullPage: true, animations: "disabled" });
  const output = testInfo.outputPath("wp19-watchtower-lifecycle.png");
  fs.writeFileSync(output, screenshot);
  await testInfo.attach("wp19-watchtower-lifecycle", { path: output, contentType: "image/png" });
});

test("WP19 missing evidence is visibly partial and never replaced with a clean state", async ({ page }) => {
  await mockShell(page);
  await page.route("**/api/v10/web/watchtower-incidents", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fixtures.missingEvidence) }));
  await page.goto("/watchtower");
  await expect(page.getByText("Incident view PARTIAL", { exact: true })).toBeVisible();
  await expect(page.getByText("Alert evidence: MISSING", { exact: true })).toBeVisible();
  await expect(page.getByText(/Severity\/subject\/action не додумываются/)).toBeVisible();
  await expect(page.getByText("Субъект не верифицирован", { exact: true })).toBeVisible();
});
