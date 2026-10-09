"use strict";

// Only public, versioned interface assets. Never cache API, HTML sessions or messages.
const build = "__OMNICIO_BUILD__";
// Imports are public, immutable for this build and cached by the browser worker.
importScripts(`/assets/config.js?build=${encodeURIComponent(build)}`, `/assets/i18n.js?build=${encodeURIComponent(build)}`);
const C = globalThis.OMNICIO_CONFIG;
const I = globalThis.OMNICIO_I18N;
if (C?.compiledBuild !== build || I?.compiledBuild !== build) throw new Error("worker_build_mismatch");
const cacheName = `omnicio-public-${build}`;
const publicPaths = ["/assets/config.js", "/assets/tokens.css", "/assets/i18n.js", "/assets/app.css", "/assets/app.js", "/assets/workspace.js", "/assets/brand/omnicio-logo.png"];
const offlineUrl = `/offline.html?build=${encodeURIComponent(build)}`;
const publicUrls = [offlineUrl, ...publicPaths.map(path => `${path}?build=${encodeURIComponent(build)}`)];
let publicCacheWork = null;

const readPublicCache = async () => {
  const cache = await caches.open(cacheName);
  return Promise.all(publicUrls.map(async url => ({url, response: await cache.match(url)})));
};
const validPublicResponse = response => response?.ok && response.headers.get("X-Omnicio-Build") === build;
const completePublicCache = async () => {
  const entries = await readPublicCache();
  return entries.every(({response}) => validPublicResponse(response)) && (await caches.keys()).includes(cacheName);
};
const fillPublicCache = async signal => {
  const entries = await readPublicCache();
  if (signal.aborted) throw new Error("public_cache_timeout");
  const missing = entries.filter(({response}) => !validPublicResponse(response));
  await Promise.all(missing.map(async ({url}) => {
    const response = await fetch(url, {method: "GET", cache: "no-store", credentials: "omit", redirect: "error", signal});
    if (signal.aborted) throw new Error("public_cache_timeout");
    // An older active worker must never cache a later deployment under its key.
    if (!response.ok || response.headers.get("X-Omnicio-Build") !== build || response.url !== new URL(url, self.location.origin).href) throw new Error("public_cache_build_mismatch");
    // Consume each validated response immediately: installing workers may
    // throttle further requests until an earlier response body is consumed.
    // Reopen after fetch so recovery cannot redirect writes to a deleted handle.
    const cache = await caches.open(cacheName);
    if (signal.aborted) throw new Error("public_cache_timeout");
    await cache.put(url, response);
  }));
};
const repairPublicCache = async signal => {
  await fillPublicCache(signal);
  if (await completePublicCache()) return;
  // A deleted partial cache needs its previously present assets too. One retry
  // and a fresh readback share the original deadline; failure stays explicit.
  if (signal.aborted) throw new Error("public_cache_timeout");
  await fillPublicCache(signal);
  if (!await completePublicCache()) throw new Error("public_cache_incomplete");
};
const ensurePublicCache = () => {
  if (publicCacheWork) return publicCacheWork;
  const controller = new AbortController();
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => { controller.abort(); reject(new Error("public_cache_timeout")); }, C.timing.publicCacheRepairMs);
  });
  publicCacheWork = Promise.race([repairPublicCache(controller.signal), deadline]).finally(() => {
    clearTimeout(timer);
    controller.abort();
    publicCacheWork = null;
  });
  return publicCacheWork;
};

self.addEventListener("install", (event) => {
  event.waitUntil(ensurePublicCache());
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
  if (event.data?.type === "REPAIR_PUBLIC_CACHE" && event.data.build === build) {
    event.waitUntil(ensurePublicCache().then(() => {
      event.ports?.[0]?.postMessage({handled: true, ok: true});
    }).catch(() => event.ports?.[0]?.postMessage({handled: true, ok: false})));
  }
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
  const timer = setTimeout(() => fail(), C.timing.workerStorageMs);
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
    }, C.timing.workerStorageMs);
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
const genericNotificationBody = (locale, test = false) => I.t(test ? "push.notification.test" : "push.notification.update", {}, locale);
self.addEventListener("push", event => {
  let payload = {};
  try { payload = event.data?.json() || {}; } catch { /* Payload is never rendered as private text. */ }
  event.waitUntil((async () => {
    const binding = await bindingTransaction().catch(() => null);
    const matches = bindingPattern.test(payload.binding_id || "") && binding?.binding_id === payload.binding_id;
    const tag = typeof payload.tag === "string" && /^[a-f0-9]{64}$/.test(payload.tag) ? payload.tag : "omnicio-event";
    await self.registration.showNotification(I.t("product.name"), {
      body: genericNotificationBody(binding?.locale, matches && payload.kind === "test"),
      icon: "/assets/brand/omnicio-logo.png", badge: "/assets/brand/omnicio-logo.png",
      tag, renotify: false,
      data: {url: matches ? notificationUrl(payload.url) : "/#account/events", binding_id: matches ? binding.binding_id : null}
    });
  })().catch(() => { /* Delivery failure must not cause an unhandled worker rejection. */ }));
});
const notifyAppClient = (client, path, bindingId) => new Promise(resolve => {
  const channel = new MessageChannel();
  const timer = setTimeout(() => { channel.port1.close(); resolve(false); }, C.timing.notificationClientAckMs);
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
