import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const matrix = [360, 768, 1440] as const;

function durationToMilliseconds(value: string): number {
  if (value.endsWith("ms")) return Number.parseFloat(value);
  if (value.endsWith("s")) return Number.parseFloat(value) * 1000;
  return Number.NaN;
}

test("design-system gallery is keyboard and label accessible", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Omni-CIO Design System" })).toBeVisible();
  await expect(page.getByLabel("Подпись поля")).toBeVisible();
  await page.keyboard.press("Tab");
  const tag = await page.evaluate(() => document.activeElement?.tagName ?? "");
  expect(["BUTTON", "INPUT"]).toContain(tag);
  await expect(page.locator('[role="alert"]')).toContainText("Действие заблокировано");
});

for (const width of matrix) {
  test(`responsive visual evidence ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    expect(page.viewportSize()?.width).toBe(width);
    const grid = page.locator(".ds-grid");
    await expect(grid).toBeVisible();
    const columns = await grid.evaluate((node) => getComputedStyle(node).gridTemplateColumns.split(" ").filter(Boolean).length);
    expect(columns).toBe(width === 360 ? 1 : width === 768 ? 2 : 3);
    const overflow = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);
    const screenshot = await page.screenshot({ fullPage: true, animations: "disabled" });
    const output = testInfo.outputPath(`design-system-${width}.png`);
    fs.writeFileSync(output, screenshot);
    await testInfo.attach(`design-system-${width}`, { path: output, contentType: "image/png" });
  });
}

test("reduced motion suppresses continuous skeleton animation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const duration = await page.locator(".ds-skeleton span").first().evaluate((node) => getComputedStyle(node).animationDuration);
  const milliseconds = durationToMilliseconds(duration);
  expect(Number.isFinite(milliseconds)).toBe(true);
  expect(milliseconds).toBeLessThanOrEqual(0.01);
});

test("visual evidence output path is isolated from source tree", async ({}, testInfo) => {
  expect(path.normalize(testInfo.outputDir)).toContain(path.normalize("test-results"));
});
