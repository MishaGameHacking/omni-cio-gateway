"use strict";

// Only public, versioned interface assets. Never cache API, HTML sessions or messages.
const build = "__OMNICIO_BUILD__";
const cacheName = `omnicio-public-${build}`;
const publicPaths = ["/assets/i18n.js", "/assets/app.css", "/assets/app.js", "/assets/workspace.js"];
const offlineUrl = `/offline.html?build=${encodeURIComponent(build)}`;

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(cacheName).then((cache) => cache.addAll([
    offlineUrl,
    ...publicPaths.map((path) => `${path}?build=${encodeURIComponent(build)}`),
  ])));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key.startsWith("omnicio-public-") && key !== cacheName)
      .map((key) => caches.delete(key)),
  )).then(() => self.clients.claim()));
});

self.addEventListener("message", (event) => {
  if (event.origin !== self.location.origin) return;
  if (event.data?.type === "ACTIVATE_UPDATE") event.waitUntil(self.skipWaiting());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/health/")) return;
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match(offlineUrl)));
    return;
  }
  if (!publicPaths.includes(url.pathname) || url.searchParams.get("build") !== build) return;
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});

const notificationUrl = value => {
  try {
    const url = new URL(value, self.location.origin);
    if (url.origin !== self.location.origin || url.pathname !== "/" || url.search) return "/#events";
    if (!/^#(?:events(?:\?event=[a-f0-9]{64})?|settings)$/.test(url.hash)) return "/#events";
    return url.pathname + url.hash;
  } catch {
    return "/#events";
  }
};

self.addEventListener("push", event => {
  let payload = {};
  try { payload = event.data?.json() || {}; } catch { /* Generic message contains no private data. */ }
  const tag = typeof payload.tag === "string" && /^[a-f0-9]{64}$/.test(payload.tag) ? payload.tag : "omnicio-event";
  // Server notifications never contain balances or names of personal goals.
  // Opening the destination still requires the current authenticated session.
  event.waitUntil(self.registration.showNotification("OMNICIO", {
    body: "В кабинете появились новые сведения. Откройте приложение, чтобы посмотреть подробности.",
    icon: "/assets/brand/pwa-icon-192.png",
    badge: "/assets/brand/pwa-icon-192.png",
    tag,
    renotify: false,
    data: {url: notificationUrl(payload.url)}
  }));
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const path = notificationUrl(event.notification.data?.url);
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({type: "window", includeUncontrolled: true});
    const existing = windows.find(client => new URL(client.url).origin === self.location.origin);
    if (existing) {
      await existing.navigate(path);
      await existing.focus();
    } else await self.clients.openWindow(path);
  })());
});
