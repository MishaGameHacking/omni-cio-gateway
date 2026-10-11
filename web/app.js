/* Public product site, __OMNICIO_BUILD__. No account, market or AI requests. */
"use strict";
(() => {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  function selectTab(tab, focus) {
    for (const item of tabs) {
      const active = item === tab;
      item.setAttribute("aria-selected", String(active));
      item.tabIndex = active ? 0 : -1;
      document.getElementById(item.getAttribute("aria-controls")).hidden = !active;
    }
    if (focus) tab.focus();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectTab(tab, false));
    tab.addEventListener("keydown", event => {
      const actions = {ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1};
      if (!Object.hasOwn(actions, event.key)) return;
      event.preventDefault();
      selectTab(tabs[actions[event.key]], true);
    });
  });
  const link = document.getElementById("apk-download");
  const status = document.getElementById("download-status");
  const details = document.getElementById("release-details");
  const check = document.getElementById("check-release");
  async function checkRelease() {
    check.disabled = true;
    link.hidden = true;
    link.removeAttribute("href");
    details.hidden = true;
    status.textContent = "Проверяем доступность выпуска…";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch("/downloads/android.json", {credentials: "omit", cache: "no-store", redirect: "error", signal: controller.signal});
      if (!response.ok) throw new Error("release_unavailable");
      const release = await response.json();
      if (release.status === "unpublished") {
        status.textContent = "Публичный выпуск готовится. Проверенного APK для установки пока нет.";
        return;
      }
      if (release.status !== "published" || release.package !== "ru.omnicio.app" ||
          !/^[0-9]+\.[0-9]+\.[0-9]+$/.test(release.version) ||
          !Number.isSafeInteger(release.version_code) || release.version_code < 1 ||
          !/^[a-f0-9]{64}$/.test(release.sha256) ||
          !/^[a-f0-9]{64}$/.test(release.certificate_sha256) ||
          !/^[a-f0-9]{40}$/.test(release.commit) ||
          release.url !== `/downloads/omnicio-${release.version}-${release.commit}.apk`) {
        throw new Error("release_invalid");
      }
      link.href = release.url;
      link.hidden = false;
      status.textContent = `OMNICIO ${release.version} · Android`;
      details.textContent = `SHA-256 файла: ${release.sha256}`;
      details.hidden = false;
    } catch {
      status.textContent = "Не удалось проверить выпуск. Повторите запрос позже.";
    } finally {
      clearTimeout(timeout);
      check.disabled = false;
    }
  }
  check.addEventListener("click", checkRelease);
  checkRelease();
  // Retire the old PWA and its cached workspace on existing installations.
  // This worker deletes only OMNICIO-owned caches, then unregisters itself.
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", {updateViaCache: "none"})
      .then(registration => registration.update()).catch(() => {});
  }
})();
