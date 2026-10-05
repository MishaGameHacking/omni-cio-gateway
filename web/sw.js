"use strict";

// Only public, versioned interface assets. Never cache API, HTML sessions or messages.
const build = new URL(self.location.href).searchParams.get("build");
const cacheName = `omnicio-public-${build}`;
const publicPaths = ["/assets/app.css", "/assets/app.js", "/assets/workspace.js"];
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
