"use strict";

// Only public, versioned interface assets. Never cache API, HTML sessions or messages.
const build = "__OMNICIO_BUILD__";
const cacheName = `omnicio-public-${build}`;
const publicPaths = ["/assets/i18n.js", "/assets/app.css", "/assets/app.js", "/assets/workspace.js", "/assets/brand/omnicio-logo.png"];
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
  if (["PUSH_BINDING", "CLEAR_PUSH_BINDING"].includes(event.data?.type)) {
    event.waitUntil(updatePushBinding(event.data).then(result => {
      event.ports?.[0]?.postMessage({handled: true, ok: true, ...result});
    }).catch(() => event.ports?.[0]?.postMessage({handled: true, ok: false})));
  }
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
    if (url.origin !== self.location.origin || url.pathname !== "/" || url.search) return "/#account/events";
    if (/^#events(?:\?event=[a-f0-9]{64})?$/.test(url.hash)) return url.hash.includes("?event=") ? "/#account/events/detail?event=" + url.hash.split("?event=")[1] : "/#account/events";
    if (url.hash === "#settings") return "/#account/settings/notifications";
    if (!/^#account\/(?:events(?:\/detail\?event=[a-f0-9]{64})?|settings\/notifications)$/.test(url.hash)) return "/#account/events";
    return url.pathname + url.hash;
  } catch {
    return "/#account/events";
  }
};

const bindingPattern = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const bindingDatabase = () => new Promise((resolve, reject) => {
  const request = indexedDB.open("omnicio-device", 1);
  let settled = false;
  const fail = error => {
    settled = true;
    clearTimeout(timer);
    reject(error || new Error("binding_storage_failed"));
  };
  const timer = setTimeout(() => fail(), 1000);
  request.onupgradeneeded = () => {
    if (settled) { request.transaction.abort(); return; }
    request.result.createObjectStore("binding");
  };
  request.onsuccess = () => {
    if (settled) { request.result.close(); return; }
    settled = true;
    clearTimeout(timer);
    resolve(request.result);
  };
  request.onerror = () => fail(request.error);
  request.onblocked = () => fail();
});
const bindingTransaction = async (change = null) => {
  const db = await bindingDatabase();
  return new Promise((resolve, reject) => {
    let transaction;
    let finished = false;
    const finish = (error, result) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      db.close();
      if (error) reject(error); else resolve(result);
    };
    const timer = setTimeout(() => {
      finish(new Error("binding_storage_failed"));
      try { transaction?.abort(); } catch { /* The transaction may have completed at the deadline. */ }
    }, 1000);
    try {
      transaction = db.transaction("binding", change ? "readwrite" : "readonly");
      const store = transaction.objectStore("binding");
      const request = store.get("current");
      let result;
      request.onsuccess = () => {
        if (finished) return;
        try { result = change ? change(request.result || null, store) : request.result || null; }
        catch { transaction.abort(); }
      };
      transaction.oncomplete = () => finish(null, result);
      transaction.onerror = transaction.onabort = () => finish(transaction.error || new Error("binding_storage_failed"));
    } catch (error) { finish(error); }
  });
};
const updatePushBinding = message => {
  const bindingId = message.binding_id;
  if (!bindingPattern.test(bindingId || "")) return Promise.reject(new Error("invalid_binding"));
  return bindingTransaction((current, store) => {
    if (message.type === "CLEAR_PUSH_BINDING") {
      const cleared = current?.binding_id === bindingId;
      if (cleared) store.delete("current");
      return {cleared};
    }
    store.put({binding_id: bindingId, locale: message.locale === "en" ? "en" : "ru"}, "current");
    return {binding_id: bindingId};
  });
};
const genericNotificationBody = (locale, test = false) => {
  if (test) return locale === "en" ? "This is an OMNICIO test notification." : "Это проверочное уведомление OMNICIO.";
  return locale === "en"
    ? "New information is available in your account. Open the app to view it."
    : "В кабинете появились новые сведения. Откройте приложение, чтобы посмотреть подробности.";
};
self.addEventListener("push", event => {
  let payload = {};
  try { payload = event.data?.json() || {}; } catch { /* Payload is never rendered as private text. */ }
  event.waitUntil((async () => {
    const binding = await bindingTransaction().catch(() => null);
    const matches = bindingPattern.test(payload.binding_id || "") && binding?.binding_id === payload.binding_id;
    const tag = typeof payload.tag === "string" && /^[a-f0-9]{64}$/.test(payload.tag) ? payload.tag : "omnicio-event";
    await self.registration.showNotification("OMNICIO", {
      body: genericNotificationBody(binding?.locale, matches && payload.kind === "test"),
      icon: "/assets/brand/omnicio-logo.png", badge: "/assets/brand/omnicio-logo.png",
      tag, renotify: false,
      data: {url: matches ? notificationUrl(payload.url) : "/#account/events", binding_id: matches ? binding.binding_id : null}
    });
  })().catch(() => { /* Delivery failure must not cause an unhandled worker rejection. */ }));
});
const notifyAppClient = (client, path, bindingId) => new Promise(resolve => {
  const channel = new MessageChannel();
  const timer = setTimeout(() => { channel.port1.close(); resolve(false); }, 1500);
  channel.port1.onmessage = event => {
    clearTimeout(timer);
    channel.port1.close();
    resolve(event.data?.handled === true);
  };
  try { client.postMessage({type: "OPEN_NOTIFICATION", url: path, binding_id: bindingId}, [channel.port2]); }
  catch { clearTimeout(timer); channel.port1.close(); resolve(false); }
});
const appClient = client => {
  try { const url = new URL(client.url); return url.origin === self.location.origin && url.pathname === "/"; }
  catch { return false; }
};
const openNotification = async data => {
  const binding = await bindingTransaction().catch(() => null);
  const matches = bindingPattern.test(data?.binding_id || "") && binding?.binding_id === data.binding_id;
  const path = matches ? notificationUrl(data?.url) : "/#account/events";
  const windows = (await self.clients.matchAll({type: "window", includeUncontrolled: true})).filter(appClient);
  const existing = windows.find(client => client.focused) || windows.find(client => client.visibilityState === "visible") || windows[0];
  if (!existing) { await self.clients.openWindow(path); return; }
  await existing.focus();
  // A busy or older app may not acknowledge. Keeping its document protects unsaved input.
  await notifyAppClient(existing, path, matches ? binding.binding_id : null);
};
self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(openNotification(event.notification.data).catch(() => { /* No duplicate window after a failed navigation. */ }));
});
