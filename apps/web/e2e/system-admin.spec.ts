import { expect, test } from "@playwright/test";

async function mockShell(page: import("@playwright/test").Page, systemStatus?: object) {
  await page.route("**/api/v10/web/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ authenticated: true, user_label: "OWNER", tenant_label: "Personal" }),
    });
  });
  await page.route("**/api/v10/web/auth/providers", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { provider: "telegram", enabled: false, reason: "NOT_CONFIGURED" },
      ]),
    });
  });
  await page.route("**/api/v10/web/health", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ state: "READY", freshness: "FRESH", checked_at: "2026-08-14T09:30:00Z" }),
    });
  });
  await page.route("**/api/v10/web/system-status", async (route) => {
    if (!systemStatus) {
      await route.abort("connectionrefused");
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(systemStatus),
    });
  });
}

function statusPayload() {
  return {
    schema_version: "1.0.0",
    generated_at: "2026-08-14T09:30:00+00:00",
    state: "READY",
    release: {
      release: "V10_UNRELEASED",
      git_sha: "a".repeat(40),
      git_sha_source: "git",
      last_deploy_at: "2026-08-14T09:20:00+00:00",
      last_deploy_source: "omni_v10_last_deploy_at",
      web_artifact_at: "2026-08-14T09:18:00+00:00",
      web_artifact_source: "web_dist_mtime",
    },
    database: {
      state: "READY",
      availability: "AVAILABLE",
      current_migration: "0003",
      expected_migration: "0003",
      migration_count: 3,
      exact_migration_state: true,
    },
    backup: {
      state: "READY",
      availability: "AVAILABLE",
      last_success_at: "2026-08-14T09:00:00+00:00",
      rpo_minutes: 60,
      rto_minutes: 240,
    },
    resources: {
      disk: {
        state: "READY",
        availability: "AVAILABLE",
        free_gib: 510.5,
        free_percent: 61.2,
        warning_threshold_gib: 50,
        block_threshold_gib: 20,
      },
      temperature: {
        state: "READY",
        availability: "AVAILABLE",
        gpu_c: 53,
        limit_c: 87,
      },
    },
    safety: {
      mode: "READ_ONLY_DIAGNOSTIC",
      real_execution_enabled: false,
      trading_methods: false,
      broker_write_authority: false,
      public_ingress: false,
      watchtower_enabled: false,
    },
    services: [
      { id: "web", label: "Local Web", state: "READY", availability: "AVAILABLE", detail: "Authenticated local/private Web API is responding.", observed_at: "2026-08-14T09:30:00+00:00" },
      { id: "database", label: "PostgreSQL", state: "READY", availability: "AVAILABLE", detail: "Migration state matches source-controlled series.", observed_at: null },
      { id: "t_invest", label: "T-Invest READ", state: "READY", availability: "AVAILABLE", detail: "1 verified READ connection(s).", observed_at: null },
      { id: "watchtower", label: "Watchtower", state: "READY", availability: "AVAILABLE", detail: "Last durable job: SUCCEEDED.", observed_at: "2026-08-14T09:25:00+00:00" },
      { id: "telegram", label: "Telegram", state: "OFFLINE", availability: "LOCKED_FUTURE_WP", detail: "Runtime activation is owned by WP23+ and remains locked.", observed_at: null },
      { id: "ai", label: "AI / Cortex", state: "OFFLINE", availability: "LOCKED_FUTURE_WP", detail: "Runtime activation is owned by WP27+ and remains locked.", observed_at: null },
    ],
    recent_jobs: [
      { job_type: "WATCHTOWER", state: "SUCCEEDED", attempts: 1, max_attempts: 3, error_class: null, observed_at: "2026-08-14T09:25:00+00:00" },
    ],
    recent_errors: [
      { job_type: "HEALTH", state: "FAILED_PERMANENT", error_class: "PERMANENT", observed_at: "2026-08-14T08:00:00+00:00" },
    ],
    limits: { recent_jobs: 12, recent_errors: 8 },
  };
}

test("WP22 system view explains ordinary operational state without mutation controls", async ({ page }) => {
  await mockShell(page, statusPayload());
  await page.goto("/system");

  await expect(page.getByRole("heading", { name: "Система" })).toBeVisible();
  await expect(page.getByText("Service health")).toBeVisible();
  await expect(page.getByText("Database / migrations")).toBeVisible();
  await expect(page.getByText("Backup / recovery")).toBeVisible();
  await expect(page.getByText("Resources")).toBeVisible();
  await expect(page.getByText("Safety / kill switches")).toBeVisible();
  await expect(page.getByText("Recent jobs")).toBeVisible();
  await expect(page.getByText("Recent sanitized errors")).toBeVisible();
  await expect(page.getByText("T-Invest READ")).toBeVisible();
  await expect(page.getByText("Telegram")).toBeVisible();
  await expect(page.getByText("AI / Cortex")).toBeVisible();
  await expect(page.getByText("LOCKED_FUTURE_WP").first()).toBeVisible();
  await expect(page.getByText("510.5 GiB")).toBeVisible();
  await expect(page.getByText("53 °C")).toBeVisible();
  await expect(page.getByText("60 min")).toBeVisible();
  await expect(page.getByText("240 min")).toBeVisible();
  await expect(page.getByText("2026-08-14T09:20:00+00:00")).toBeVisible();
  await expect(page.getByText("2026-08-14T09:18:00+00:00")).toBeVisible();
  await expect(page.getByText("a".repeat(40))).toBeVisible();
  await expect(page.getByText("Exact source Git SHA")).toBeVisible();

  await expect(page.getByRole("button", { name: /enable|disable|kill|trading/i })).toHaveCount(0);
  await expect(page.getByText(/broker-account|authorization bearer|secret-token/i)).toHaveCount(0);
});

test("WP22 diagnostics failure is explicit and never rendered as READY system snapshot", async ({ page }) => {
  await mockShell(page);
  await page.goto("/system");

  await expect(page.getByText("System diagnostics API недоступен")).toBeVisible();
  await expect(page.getByText(/Неизвестное состояние не преобразуется в READY/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Система" })).toBeVisible();
});
