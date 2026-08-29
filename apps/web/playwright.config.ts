import { defineConfig } from "@playwright/test";

const channel = process.env.OMNI_WEB_BROWSER_CHANNEL;
const baseURL = process.env.OMNI_WEB_PREVIEW_URL?.trim() || "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 1,
  reporter: "line",
  globalTimeout: 90_000,
  timeout: 15_000,
  captureGitInfo: {
    commit: false,
    diff: false,
  },
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL,
    browserName: "chromium",
    channel: channel || undefined,
    headless: true,
    actionTimeout: 5_000,
    navigationTimeout: 10_000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
