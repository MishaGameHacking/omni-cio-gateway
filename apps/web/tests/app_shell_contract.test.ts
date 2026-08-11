import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { appRoutes, isKnownRoute } from "../src/app-shell/contracts.ts";

const expectedRoutes = [
  "/",
  "/portfolio",
  "/assets",
  "/watchtower",
  "/research",
  "/risks",
  "/decisions",
  "/plans",
  "/execution",
  "/journal",
  "/system",
  "/settings",
];

test("WP17 exposes the exact Master Plan navigation routes", () => {
  assert.deepEqual(appRoutes.map((route) => route.path), expectedRoutes);
  for (const path of expectedRoutes) assert.equal(isKnownRoute(path), true);
  assert.equal(isKnownRoute("/private-other-tenant"), false);
});

test("ordinary login surface is Telegram and VK ID without local password", () => {
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  assert.match(shell, /Продолжить через Telegram/);
  assert.match(shell, /Продолжить через VK ID/);
  assert.doesNotMatch(shell, /type=["']password["']/i);
  assert.doesNotMatch(shell, /Google/i);
});

test("browser code cannot persist credentials in Web Storage", () => {
  const api = readFileSync(new URL("../src/app-shell/api.ts", import.meta.url), "utf8");
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  const combined = `${api}\n${shell}`;
  assert.doesNotMatch(combined, /localStorage/);
  assert.doesNotMatch(combined, /sessionStorage/);
  assert.match(api, /credentials:\s*["']same-origin["']/);
});

test("build identity is rendered only through System route code", () => {
  const pages = readFileSync(new URL("../src/app-shell/pages.tsx", import.meta.url), "utf8");
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  assert.match(pages, /__OMNI_WEB_BUILD_SHA__/);
  assert.match(pages, /path === ["']\/system["']/);
  assert.doesNotMatch(shell, /__OMNI_WEB_BUILD_SHA__/);
});
