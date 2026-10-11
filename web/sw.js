/* Retire the authenticated web/PWA client. OMNICIO build __OMNICIO_BUILD__. */
"use strict";
const build = "__OMNICIO_BUILD__";
self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil((async () => {
  const keys = await caches.keys();
  await Promise.all(keys.filter(key => key.startsWith("omnicio-")).map(key => caches.delete(key)));
  await self.clients.claim();
  await self.registration.unregister();
})()));
