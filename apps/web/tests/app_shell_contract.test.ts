import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { appRouteFeatureByPath, appRoutes, isKnownRoute, isPublicRoute, publicRoutes } from "../src/app-shell/contracts.ts";

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
const expectedPublicRoutes = ["/privacy"];
const forbiddenStorageIdentifiers = [
  ["local", "Storage"].join(""),
  ["session", "Storage"].join(""),
];
const forbiddenHumanSessionBypasses = [
  "/preview-login",
  "/private-test-login",
  "/private-external-login",
];

test("WP17 exposes the exact Master Plan navigation routes", () => {
  assert.deepEqual(appRoutes.map((route) => route.path), expectedRoutes);
  assert.deepEqual(Object.keys(appRouteFeatureByPath), expectedRoutes);
  for (const path of expectedRoutes) assert.equal(isKnownRoute(path), true);
  assert.equal(isKnownRoute("/private-other-tenant"), false);
});

test("privacy policy is a separate public route and not private navigation", () => {
  assert.deepEqual(publicRoutes.map((route) => route.path), expectedPublicRoutes);
  assert.equal(isPublicRoute("/privacy"), true);
  assert.equal(isKnownRoute("/privacy"), false);
});

test("ordinary login surface is exactly Telegram without local password", () => {
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  assert.match(shell, /Продолжить через Telegram/);
  assert.doesNotMatch(shell, /Продолжить через VK ID/);
  assert.doesNotMatch(shell, /vk_id/);
  assert.doesNotMatch(shell, /type=["']password["']/i);
  assert.doesNotMatch(shell, /Google/i);
});

test("login surface links to the fail-closed public privacy surface", () => {
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  assert.match(shell, /href="\/privacy"/);
  assert.match(shell, /Политика обработки персональных данных/);
  assert.match(shell, /Telegram Login запрашивает только scope openid/);
  assert.match(shell, /telegram:bot_access не запрашиваются/);
  assert.match(shell, /канале обращений субъектов персональных данных/);
});

test("provider login starts with POST forms instead of state-changing GET navigation", () => {
  const api = readFileSync(new URL("../src/app-shell/api.ts", import.meta.url), "utf8");
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  assert.match(api, /\/api\/v10\/web\/auth\/telegram\/start/);
  assert.match(shell, /<form method="post" action=\{providerLoginPath\(\)\}>/);
  assert.doesNotMatch(shell, /vk_id/);
  assert.doesNotMatch(shell, /href=\{providerLoginPath/);
});

test("browser product code exposes no preview private or OWNER session-minting bypass", () => {
  const api = readFileSync(new URL("../src/app-shell/api.ts", import.meta.url), "utf8");
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  const combined = `${api}\n${shell}`;
  for (const path of forbiddenHumanSessionBypasses) assert.equal(combined.includes(path), false);
  assert.doesNotMatch(combined, /OWNER acceptance/i);
  assert.doesNotMatch(combined, /previewLogin|privateTestLogin|privateRemoteLogin/);
});

test("synthetic hosted mode remains a non-authority warning only", () => {
  const api = readFileSync(new URL("../src/app-shell/api.ts", import.meta.url), "utf8");
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  assert.match(api, /\/api\/v10\/web\/preview-mode/);
  assert.doesNotMatch(api, /\/api\/v10\/web\/preview-login/);
  assert.match(shell, /real registration, broker credentials and private portfolio data are disabled/);
  assert.match(shell, /Не вводи реальные токены на этом стенде/);
});

test("logout UI never claims revocation when the server request fails", () => {
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(shell, /logoutCurrentSession\(\)\.finally/);
  assert.match(shell, /logoutCurrentSession\(\)[\s\S]*\.then\(authentication\.markSessionClosed\)/);
  assert.match(shell, /\.catch\(authentication\.markSessionUnavailable\)/);
  assert.match(shell, /Выход не подтверждён сервером\. Текущая сессия остаётся активной/);
});

test("status notices use native output semantics without role emulation", () => {
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("../src/app-shell/app-shell.css", import.meta.url), "utf8");
  assert.doesNotMatch(shell, /role="status"/);
  assert.match(shell, /<output className="shell-degraded">[\s\S]*SYNTHETIC PREVIEW/);
  assert.match(shell, /<output className="shell-degraded">[\s\S]*Downstream API недоступен/);
  assert.match(shell, /<output>Проверка server-side session…<\/output>/);
  assert.match(css, /\.shell-degraded,\.login-warning\{display:block;/);
});

test("browser code cannot persist credentials in Web Storage", () => {
  const api = readFileSync(new URL("../src/app-shell/api.ts", import.meta.url), "utf8");
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  const combined = `${api}\n${shell}`;
  for (const identifier of forbiddenStorageIdentifiers) {
    assert.equal(combined.includes(identifier), false);
  }
  assert.match(api, /credentials:\s*["']same-origin["']/);
});

test("hosted browser keeps CSRF bootstrap material transient and never reads cookies", () => {
  const api = readFileSync(new URL("../src/app-shell/api.ts", import.meta.url), "utf8");
  assert.match(api, /let csrfHeaderToken: string \| null = null/);
  assert.match(api, /csrf_token: csrfToken/);
  assert.match(api, /headers\.set\(REMOTE_CSRF_HEADER, csrfHeaderToken\)/);
  assert.doesNotMatch(api, /document\.cookie|readCookie\(/);
  assert.doesNotMatch(api, /response\.headers\.get\(REMOTE_CSRF_HEADER\)/);
  for (const identifier of forbiddenStorageIdentifiers) {
    assert.equal(api.includes(identifier), false);
  }
});

test("WP15 private live values are cleared when the browser challenge expires", () => {
  const pages = readFileSync(new URL("../src/app-shell/pages.tsx", import.meta.url), "utf8");
  assert.match(pages, /Date\.parse\(liveView\.expires_at\)/);
  assert.match(pages, /window\.setTimeout/);
  assert.match(pages, /window\.clearTimeout/);
  assert.match(pages, /Приватные значения удалены из браузера/);
});

test("WP15 live snapshot shows an immediate accessible pending state", () => {
  const pages = readFileSync(new URL("../src/app-shell/pages.tsx", import.meta.url), "utf8");
  assert.match(pages, /Получаем live READ snapshot из T-Invest/);
  assert.match(pages, /Получаем snapshot…/);
  assert.match(pages, /aria-busy=\{liveWorking\}/);
});

test("deployed source identity comes only from server-validated runtime status", () => {
  const pages = readFileSync(new URL("../src/app-shell/pages.tsx", import.meta.url), "utf8");
  const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
  const systemAdmin = readFileSync(new URL("../src/app-shell/system-admin.tsx", import.meta.url), "utf8");
  const vite = readFileSync(new URL("../vite.config.ts", import.meta.url), "utf8");
  assert.match(systemAdmin, /status\?\.release\.git_sha/);
  assert.match(systemAdmin, />Git SHA</);
  for (const source of [pages, shell, systemAdmin, vite]) {
    assert.doesNotMatch(source, /__OMNI_WEB_BUILD_SHA__/);
  }
});
