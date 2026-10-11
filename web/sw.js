/* Retire the authenticated web/PWA client. OMNICIO build __OMNICIO_BUILD__. */
"use strict";
const build = "__OMNICIO_BUILD__";
self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil((async () => {
  for (const key of await caches.keys()) {
    if (key.startsWith("omnicio-")) await caches.delete(key);
  }
  await self.clients.claim();
  await self.registration.unregister();
})()));
