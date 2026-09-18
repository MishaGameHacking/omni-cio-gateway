import { expect, test } from "@playwright/test";
import fs from "node:fs";

async function mockAuthenticatedApi(page: import("@playwright/test").Page, options?: { healthOffline?: boolean }) {
  await page.route("**/api/v10/web/session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ authenticated: true, user_label: "USER", tenant_label: "Tenant" }) });
  });
  await page.route("**/api/v10/web/auth/providers", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ provider: "telegram", enabled: false, reason: "NOT_CONFIGURED" }, { provider: "vk_id", enabled: false, reason: "NOT_CONFIGURED" }]) });
  });
  await page.route("**/api/v10/web/preview-mode", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled: true, synthetic: true, broker_credentials_enabled: false, registration_enabled: false, label: "Synthetic technical boundary" }),
    });
  });
  await page.route("**/api/v10/web/health", async (route) => {
    if (options?.healthOffline) {
      await route.abort("connectionrefused");
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ state: "READY", freshness: "FRESH", checked_at: "2026-08-11T07:00:00Z" }) });
  });
  await page.route("**/api/v10/web/broker-connections", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v10/web/session/revoke-all", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' });
  });
}

async function mockUnauthenticatedApi(page: import("@playwright/test").Page, providers: Array<{ provider: "telegram" | "vk_id"; enabled: boolean; reason?: string }>) {
  await page.route("**/api/v10/web/session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: '{"authenticated":false}' });
  });
  await page.route("**/api/v10/web/auth/providers", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(providers) });
  });
  await page.route("**/api/v10/web/preview-mode", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ enabled: true, synthetic: true, broker_credentials_enabled: false, registration_enabled: false, label: "Synthetic technical boundary" }) });
  });
}

test("unauthenticated route is guarded and exposes only Telegram/VK login", async ({ page }) => {
  await mockUnauthenticatedApi(page, [
    { provider: "telegram", enabled: false, reason: "NOT_CONFIGURED" },
    { provider: "vk_id", enabled: false, reason: "NOT_CONFIGURED" },
  ]);
  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "Вход в личный аккаунт" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Продолжить через Telegram" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Продолжить через VK ID" })).toBeDisabled();
  await expect(page.getByRole("heading", { name: "Портфель" })).toHaveCount(0);
  await expect(page.getByText(/OWNER acceptance|публичная демонстрация/i)).toHaveCount(0);
});

test("configured but activation-blocked provider stays disabled truthfully", async ({ page }) => {
  await mockUnauthenticatedApi(page, [
    { provider: "telegram", enabled: false, reason: "PUBLIC_MULTI_USER_DISABLED" },
    { provider: "vk_id", enabled: false, reason: "NOT_CONFIGURED" },
  ]);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Продолжить через Telegram" })).toBeDisabled();
  await expect(page.getByText(/публичная регистрация ещё не активирована/i)).toBeVisible();
});

test("active provider does not inherit a disabled sibling's public-registration warning", async ({ page }) => {
  await mockUnauthenticatedApi(page, [
    { provider: "telegram", enabled: true },
    { provider: "vk_id", enabled: false, reason: "PROVIDER_ACTIVATION_DISABLED" },
  ]);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Продолжить через Telegram" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Продолжить через VK ID" })).toBeDisabled();
  await expect(page.getByText(/публичная регистрация ещё не активирована/i)).toHaveCount(0);
  await expect(page.getByText(/настроенных провайдеров входа ещё не активирована/i)).toBeVisible();
});

test("configured provider login uses a top-level POST instead of state-changing GET", async ({ page }) => {
  await mockUnauthenticatedApi(page, [
    { provider: "telegram", enabled: true },
    { provider: "vk_id", enabled: false, reason: "NOT_CONFIGURED" },
  ]);
  let observedMethod = "";
  await page.route("**/api/v10/web/auth/telegram/start", async (route) => {
    observedMethod = route.request().method();
    await route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"IDENTITY_PROVIDER_UNAVAILABLE"}' });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Продолжить через Telegram" }).click();
  await expect.poll(() => observedMethod).toBe("POST");
});

test("authenticated shell navigates without exposing build identity globally", async ({ page }) => {
  await mockAuthenticatedApi(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.getByText("OMNI-CIO", { exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Основная навигация" })).toBeVisible();
  await expect(page.getByText("READY", { exact: true })).toBeVisible();
  await expect(page.getByText("Git SHA", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Система" }).click();
  await expect(page).toHaveURL(/\/system$/);
  await expect(page.getByRole("heading", { name: "Система" })).toBeVisible();
  await expect(page.getByText("Git SHA", { exact: true })).toBeVisible();
});

test("revoke-all immediately closes the current authenticated shell", async ({ page }) => {
  await mockAuthenticatedApi(page);
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Настройки" })).toBeVisible();
  await page.getByRole("button", { name: "Выйти на всех устройствах" }).click();
  await expect(page.getByRole("heading", { name: "Вход в личный аккаунт" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Настройки" })).toHaveCount(0);
});

test("degraded downstream API leaves authenticated shell available", async ({ page }) => {
  await mockAuthenticatedApi(page, { healthOffline: true });
  await page.goto("/system");
  await expect(page.getByText("OMNI-CIO", { exact: true })).toBeVisible();
  await expect(page.getByText(/shell работает в DEGRADED режиме/)).toBeVisible();
  await expect(page.getByLabel("Глобальное состояние").getByText("DEGRADED", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Система" })).toBeVisible();
});

for (const width of [360, 768, 1440] as const) {
  test(`application shell responsive evidence ${width}px`, async ({ page }, testInfo) => {
    await mockAuthenticatedApi(page);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await expect(page.getByText("OMNI-CIO", { exact: true })).toBeVisible();
    const previewBanner = page.locator(".shell-degraded").filter({ hasText: "SYNTHETIC PREVIEW" });
    await expect(previewBanner).toBeVisible();
    const previewBackground = await previewBanner.evaluate((element) => getComputedStyle(element).backgroundColor);
    expect(previewBackground).not.toBe("rgba(0, 0, 0, 0)");
    if (width === 360) {
      const navigation = page.getByRole("navigation", { name: "Основная навигация" });
      await expect(navigation).not.toBeVisible();
      await expect(page.getByRole("button", { name: "Меню" })).toBeVisible();
      await page.getByRole("button", { name: "Меню" }).click();
      await expect(navigation).toBeVisible();
      const sidebar = page.locator(".shell-sidebar");
      const sidebarStyle = await sidebar.evaluate((element) => {
        const style = getComputedStyle(element);
        return { backgroundColor: style.backgroundColor, position: style.position };
      });
      expect(sidebarStyle.backgroundColor).not.toBe("rgba(0, 0, 0, 0)");
      expect(sidebarStyle.position).toBe("fixed");
      const sidebarBox = await sidebar.boundingBox();
      expect(sidebarBox).not.toBeNull();
      expect(sidebarBox!.x).toBeLessThanOrEqual(0.5);
      expect(sidebarBox!.width).toBeGreaterThanOrEqual(width - 1);
      const drawerOwnsViewportPoint = await page.evaluate(() => {
        const topmost = document.elementFromPoint(window.innerWidth / 2, Math.min(window.innerHeight - 1, 200));
        return Boolean(topmost?.closest(".shell-sidebar"));
      });
      expect(drawerOwnsViewportPoint).toBe(true);
    }
    const overflow = await page.evaluate(() => ({ clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);
    const screenshot = await page.screenshot({ fullPage: true, animations: "disabled" });
    const output = testInfo.outputPath(`app-shell-${width}.png`);
    fs.writeFileSync(output, screenshot);
    await testInfo.attach(`app-shell-${width}`, { path: output, contentType: "image/png" });
  });
}