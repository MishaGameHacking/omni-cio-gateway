/* Browser contract tests against an isolated synthetic server; no production API. */
const {createServer} = require("node:http");
const {readFileSync, writeFileSync, existsSync, mkdtempSync, mkdirSync, rmSync} = require("node:fs");
const {join, resolve} = require("node:path");
const {tmpdir} = require("node:os");
const {spawn, spawnSync} = require("node:child_process");
const assert = require("node:assert/strict");

const root = resolve(__dirname, "..");
const web = join(root, "web");
const version = /^version = "([^"\r\n]+)"$/m.exec(readFileSync(join(root, "pyproject.toml"), "utf8"))[1];
const build = "smoke-" + version;
const catalogProcess = spawnSync(process.env.OMNICIO_PYTHON || "python", ["-c",
  "import json,runpy; print(json.dumps(runpy.run_path('src/omnicio/strategy.py')['strategy_catalog']()))"],
  {cwd: root, encoding: "utf8", maxBuffer: 2 * 1024 * 1024});
assert.equal(catalogProcess.status, 0, "The browser fixture must use the canonical Python catalog: " + catalogProcess.stderr);
const strategyCatalog = JSON.parse(catalogProcess.stdout);
const candidates = [
  process.env.OMNICIO_TEST_BROWSER,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/chromium", "/usr/bin/google-chrome",
].filter(Boolean);
const executable = candidates.find((candidate) => existsSync(candidate));
assert.ok(executable, "Install Chrome/Edge on the CI runner or set OMNICIO_TEST_BROWSER; browser QA cannot be skipped.");
assert.equal(typeof WebSocket, "function", "Node 22+ is required for the browser protocol client.");
const artifacts = join(root, "artifacts", "frontend");
mkdirSync(artifacts, {recursive: true});

const verifyPublicWorker = async () => {
  const handlers = new Map();
  const cached = [];
  const tasks = [];
  let activations = 0;
  const origin = "https://example.test";
  const worker = {
    location: {origin, href: origin + "/sw.js?build=contract"},
    addEventListener: (name, action) => handlers.set(name, action),
    skipWaiting: async () => { activations += 1; },
  };
  const previousSelf = globalThis.self;
  const previousCaches = globalThis.caches;
  try {
    globalThis.self = worker;
    globalThis.caches = {open: async () => ({addAll: async (urls) => cached.push(...urls)})};
    require("../web/sw.js");
    handlers.get("install")({waitUntil: (task) => tasks.push(task)});
    await Promise.all(tasks);
    assert.ok(cached.includes("/offline.html?build=__OMNICIO_BUILD__"), "The offline fallback must be public");
    assert.ok(cached.every((path) => /^\/(offline\.html|assets\/(app\.css|app\.js|workspace\.js))\?build=__OMNICIO_BUILD__$/.test(path)), "Only the public interface allowlist may be cached");
    let intercepted = 0;
    for (const [path, method] of [["/api/auth/me", "GET"], ["/api/broker/tbank/portfolio", "GET"], ["/api/auth/logout", "POST"], ["/health/ready", "GET"]]) {
      handlers.get("fetch")({request: {url: origin + path, method, mode: "navigate"}, respondWith: () => { intercepted += 1; }});
    }
    assert.equal(intercepted, 0, "The worker must not intercept private requests, writes or health checks");
    const message = {data: {type: "ACTIVATE_UPDATE"}, waitUntil: (task) => tasks.push(task)};
    handlers.get("message")({...message, origin: "https://untrusted.example"});
    assert.equal(activations, 0, "A foreign message cannot activate a worker");
    handlers.get("message")({...message, origin});
    await Promise.all(tasks);
    assert.equal(activations, 1, "Same-origin explicit update is supported");
    console.log("PWA contract: public cache only, private requests untouched, update origin verified");
  } finally {
    if (previousSelf === undefined) delete globalThis.self;
    else globalThis.self = previousSelf;
    if (previousCaches === undefined) delete globalThis.caches;
    else globalThis.caches = previousCaches;
  }
};

const suite = String.raw`
window.__smokeRequests = [];
const observedFetch = window.fetch;
window.fetch = (path, options = {}) => {
  window.__smokeRequests.push({path, method: options.method || "GET", body: options.body ? JSON.parse(options.body) : null});
  return observedFetch(path, options);
};
window.__confirmAnswers = [];
window.confirm = () => window.__confirmAnswers.length ? window.__confirmAnswers.shift() : true;
const initializeWorkspace = window.OmniWorkspace.init;
window.OmniWorkspace.init = (adapter) => {
  const controls = initializeWorkspace(adapter);
  window.__smokeWorkspace = controls;
  return controls;
};
const verifyHelp = async (check) => {
  const trigger = document.querySelector(".help-trigger");
  const popup = document.querySelector("#workspace-help");
  const pause = (ms) => new Promise((resolvePause) => setTimeout(resolvePause, ms));
  const escape = () => document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
  const pointer = (type, target = trigger, options = {}) => {
    const event = new PointerEvent(type, {bubbles: true, cancelable: true, isPrimary: true, button: 0, pointerType: "touch", pointerId: 17, clientX: 30, clientY: 30, ...options});
    target.dispatchEvent(event);
    return event;
  };
  const tap = () => { pointer("pointerdown"); pointer("pointerup"); pointer("click", trigger, {detail: 1}); };
  const reset = () => { trigger.blur(); escape(); };
  check(Boolean(trigger && popup), "Help reuses the workspace component");
  // Complete the viewport change before starting a timed hover gesture.
  trigger.scrollIntoView({block: "center", behavior: "instant"});
  await pause(100);
  trigger.focus({preventScroll: true});
  check(!popup.hidden && popup.getAttribute("role") === "tooltip", "Keyboard focus opens noninteractive help");
  document.dispatchEvent(new Event("scroll"));
  check(!popup.hidden && document.activeElement === trigger, "Focus scrolling preserves the keyboard explanation");
  check(Boolean(document.getElementById(trigger.getAttribute("aria-describedby"))?.textContent), "Help has a valid accessible description");
  check([...popup.querySelectorAll("button")].every((item) => getComputedStyle(item).display === "none"), "Transient tooltip contains no visible interactive control");
  trigger.click();
  check(popup.getAttribute("role") === "dialog" && popup.contains(document.activeElement), "Keyboard activation pins help and moves focus to its close control");
  trigger.focus({preventScroll: true});
  check(popup.getAttribute("role") === "dialog", "Returning focus does not unpin help");
  popup.querySelector("button").click();
  check(popup.hidden && document.activeElement === trigger, "Close restores focus without reopening help");
  check(!trigger.hasAttribute("aria-describedby"), "Closing removes the stale description binding");
  await ["scroll", "resize"].reduce((previous, eventName) => previous.then(async () => {
    trigger.click();
    check(popup.contains(document.activeElement) && !popup.hidden, "Pinned lifecycle starts with dialog focus: " + eventName);
    (eventName === "scroll" ? document : window).dispatchEvent(new Event(eventName));
    check(popup.hidden && document.activeElement === trigger, "Lifecycle dismissal restores trigger focus: " + eventName);
    await pause(390);
    check(popup.hidden && document.activeElement === trigger, "Restored lifecycle focus does not reopen help: " + eventName);
  }), Promise.resolve());
  trigger.click();
  check(popup.contains(document.activeElement), "View-change regression starts with dialog focus");
  window.__smokeWorkspace.onView("assets");
  check(popup.hidden && !popup.contains(document.activeElement) && document.activeElement !== trigger, "A destination view never restores focus to the old-screen trigger");
  await pause(390);
  check(popup.hidden, "View-change dismissal leaves no delayed reopen");
  window.__smokeWorkspace.onView("home");
  trigger.focus({preventScroll: true});
  trigger.click();
  const outside = document.querySelector("#privacy-toggle");
  outside.focus({preventScroll: true});
  check(document.activeElement === outside, "Outside-focus precondition uses a visible control at this viewport");
  window.__smokeWorkspace.onView("assets");
  check(popup.hidden && document.activeElement === outside, "View-change cleanup preserves focus already moved to another control");
  window.__smokeWorkspace.onView("home");
  trigger.focus({preventScroll: true});
  trigger.click();
  outside.focus({preventScroll: true});
  check(document.activeElement === outside, "Resize starts with focus outside the popover");
  window.dispatchEvent(new Event("resize"));
  check(popup.hidden && document.activeElement === outside, "Lifecycle cleanup does not steal focus outside the popover");
  outside.blur();
  reset();
  pointer("pointerenter", trigger, {pointerType: "mouse"});
  await pause(180);
  check(popup.hidden, "Mouse hover does not open before the delay");
  await pause(220);
  check(!popup.hidden, "Mouse hover opens after 350 ms");
  pointer("pointerleave", trigger, {pointerType: "mouse"});
  pointer("pointerenter", popup, {pointerType: "mouse"});
  await pause(180);
  check(!popup.hidden, "Pointer can move onto help without losing its text");
  pointer("pointerleave", popup, {pointerType: "mouse"});
  await pause(180);
  check(popup.hidden, "Leaving both hover surfaces closes help after the grace period");
  const start = pointer("pointerdown");
  trigger.focus({preventScroll: true});
  check(!start.defaultPrevented && popup.hidden, "Touch keeps native scrolling and does not open on pointer-induced focus");
  pointer("pointerup");
  pointer("click", trigger, {detail: 1});
  check(!popup.hidden && popup.getAttribute("role") === "dialog", "Short tap pins help");
  tap();
  check(popup.hidden, "A second tap closes pinned help");
  pointer("pointerdown");
  await pause(330);
  check(!popup.hidden && popup.getAttribute("role") === "tooltip", "Long press opens temporary help");
  pointer("pointerup", document.body);
  check(popup.hidden, "Releasing outside the trigger closes temporary help");
  pointer("click", trigger, {detail: 1});
  check(popup.hidden, "Synthetic click from the long press is suppressed");
  tap();
  check(!popup.hidden && popup.getAttribute("role") === "dialog", "The next tap is not suppressed by the previous gesture");
  pointer("pointerdown", document.body);
  check(popup.hidden, "Outside pointer action dismisses pinned help");
  for (const afterHold of [false, true]) {
    pointer("pointerdown");
    if (afterHold) await pause(330);
    pointer("pointermove", document.body, {clientX: 41});
    pointer("pointerup", document.body);
    pointer("click", trigger, {detail: 1});
    await pause(330);
    check(popup.hidden, "Movement over 10 px cancels help and click, held=" + afterHold);
  }
  pointer("pointerdown");
  await pause(330);
  pointer("pointercancel", document.body);
  check(popup.hidden, "Pointer cancellation closes an active long press");
  reset();
  for (const eventName of ["scroll", "resize", "pagehide"]) {
    pointer("pointerenter", trigger, {pointerType: "mouse"});
    (eventName === "scroll" ? document : window).dispatchEvent(new Event(eventName));
    await pause(390);
    check(popup.hidden, "Lifecycle cancels delayed hover: " + eventName);
  }
  pointer("pointerdown");
  const previousHidden = Object.getOwnPropertyDescriptor(document, "hidden");
  try {
    Object.defineProperty(document, "hidden", {configurable: true, value: true});
    document.dispatchEvent(new Event("visibilitychange"));
  } finally {
    if (previousHidden) Object.defineProperty(document, "hidden", previousHidden);
    else delete document.hidden;
  }
  await pause(330);
  check(popup.hidden, "Hiding the document cancels a pending long press");
  reset();
  pointer("pointerenter", trigger, {pointerType: "mouse"});
  window.__smokeWorkspace.onView("home");
  await pause(390);
  check(popup.hidden, "View changes cancel delayed help instead of resurrecting it");
  trigger.focus({preventScroll: true});
  const rect = popup.getBoundingClientRect();
  check(rect.left >= 15 && rect.right <= innerWidth - 15 && rect.top >= 15 && rect.bottom <= innerHeight - 15, "Help stays inside the viewport");
  reset();
};
window.addEventListener("load", () => setTimeout(async () => {
  const results = [];
  const check = (value, label) => { if (!value) throw new Error(label); results.push(label); };
  const one = (s) => document.querySelector(s);
  const click = (s) => { const element=one(s); check(Boolean(element), "Control exists: " + s); element.click(); };
  const navigate = (view) => {
    if (innerWidth < 1200) click("#app-menu-toggle");
    click('[data-view="' + view + '"]');
    check(!one('[data-view-panel="' + view + '"]').classList.contains("hidden"), "View opened: " + view);
    check(document.documentElement.scrollWidth <= innerWidth + 1, "No page overflow: " + view);
  };
  const set = (element, value) => { element.value=value; element.dispatchEvent(new Event("input", {bubbles:true})); };
  try {
    check(window.__smokeErrors.length === 0, "No boot errors: " + window.__smokeErrors.join(", "));
    if (new URLSearchParams(location.search).get("fixture") === "strategy-load-error") {
      for (let attempt = 0; attempt < 100; attempt += 1) {
        const retry = document.querySelector(".strategy-load-status button");
        if (retry && !retry.hidden && !retry.disabled) break;
        await new Promise((resolveWait) => setTimeout(resolveWait, 30));
      }
      navigate("strategy");
      check(one(".strategy-load-status")?.textContent.includes("Не удалось загрузить"), "Initial library failure is visible");
      check(one(".strategy-layout").inert && one(".strategy-live-settings").inert, "Controls cannot accept unsavable edits before initial library verification");
      check(!one(".strategy-catalog"), "Failure does not pretend the default template loaded");
      check(window.__smokeRequests.every((item) => item.method !== "PUT"), "Failed initial load never writes");
      window.__smokeResult = {passed: true, checks: results.length, viewport: innerWidth};
      return;
    }
    if (new URLSearchParams(location.search).has("catalog")) {
      for (let attempt = 0; attempt < 100 && !document.querySelector(".strategy-catalog"); attempt += 1) await new Promise(resolve => setTimeout(resolve, 50));
      navigate("strategy");
      check(document.querySelectorAll("[data-choose-strategy]").length === 10, "Ten canonical presets rendered");
      window.__smokeResult = {passed: true, viewport: innerWidth};
      return;
    }
    if (new URLSearchParams(location.search).has("synthetic")) {
      const mode = new URLSearchParams(location.search).get("fixture") || "saved";
      const waitFor = async (condition) => {
        for (let attempt = 0; attempt < 100; attempt += 1) {
          if (condition()) return;
          await new Promise((resolveWait) => setTimeout(resolveWait, 30));
        }
        throw new Error("Synthetic authenticated settings timed out: " + mode);
      };
      await waitFor(() => !one("#profile-panel").classList.contains("hidden"));
      navigate("strategy");
      const form = one("#investment-profile-form");
      const input = one("#profile-reserve-rub");
      const field = input.closest(".touch-setting");
      const writes = () => window.__smokeRequests.filter((request) => request.method === "PUT" && request.path !== "/api/profile/strategy");
      const help = one("#workspace-help");
      if (["load-error", "wrong-owner"].includes(mode)) {
        await waitFor(() => one("#investment-profile-message").classList.contains("error"));
        check(input.disabled && input.value === "", "Failed/foreign load cannot initialize editable defaults: " + mode);
        check(one("#investment-profile-save").disabled, "Unverified owner/version cannot save");
      } else {
        await waitFor(() => !input.disabled && document.querySelectorAll("[data-choose-strategy]").length === 10);
        click('[data-strategy-tab="2"]');
        check(one("#settings-profile-id").textContent === "000000123", "Synthetic authenticated tenant loaded");
        check(document.querySelectorAll("#investment-profile-form .step-button").length === 10, "Every profile number has step controls");
        check(document.querySelectorAll("#balancing-policy-form .step-button").length === 34, "Every policy number has step controls");
        check([...form.querySelectorAll('input[type="number"]')].every((item) => item.hidden), "No keyboard is required for the initial form");
        check(writes().length === 0, "Loading, defaults and grouping never save automatically");
        if (mode === "empty") {
          check(input.value === "", "Unknown personal reserve is never invented by a template");
          check(one(".strategy-savebar [role=status]").textContent.includes("не сохранён"), "Starter status is not saved-success");
          check(!one("#profile-allow-below-grade").checked, "High-risk permission remains opt-in");
          field.querySelector('[aria-label^="Не знаю:"]').click();
          check(input.value === "", "Unknown is not zero");
          form.requestSubmit();
          check(!one("#workspace-dialog").open && one("#investment-profile-message").classList.contains("error"), "Unknown blocks confirmation and stays visible");
          field.querySelector('[data-quick-value="100000"]').click();
          one("#profile-withdrawal-rub").closest(".touch-setting").querySelector('[data-quick-value="0"]').click();
        } else {
          check(input.value === "123456789.12345678", "Saved eight-place amount wins over defaults without rounding");
          check(one("#balance-max-instrument").value === "12.3456", "Saved four-place policy percentage stays exact");
          const drawdown = one("#profile-max-drawdown");
          const range = drawdown.closest(".touch-setting").querySelector('input[type="range"]');
          check(range.value === "18.5123", "Loaded slider and source value are synchronized");
          const step = field.querySelector("select");
          step.value = "0.01";
          step.dispatchEvent(new Event("change", {bubbles: true}));
          field.querySelector('[data-step-direction="1"]').click();
          check(input.value === "123456789.13345678", "Cent step preserves all existing decimal places");
          check(input.hidden, "Stepper does not open the software keyboard");
        }
        const settingsInputs = [...document.querySelectorAll('.touch-setting input[type="number"]')];
        const valuesBeforeHelp = settingsInputs.map((item) => item.value);
        for (const setting of settingsInputs) {
          const tabPanel = setting.closest('[role="tabpanel"]');
          if (tabPanel) click('[aria-controls="' + tabPanel.id + '"]');
          const panel = setting.closest("details");
          const wasOpen = panel?.open;
          if (panel) panel.open = true;
          const settingHelp = setting.closest(".touch-setting").querySelector(".setting-label .help-trigger");
          settingHelp.click();
          check(help.classList.contains("help-expanded") && help.getAttribute("role") === "dialog", "Tap opens detailed help: " + setting.id);
          check(help.querySelectorAll(".help-section").length >= 5, "Meaning, change, example and limits are present: " + setting.id);
          check(help.textContent.includes("Выбрано сейчас") && help.textContent.includes("Пример"), "Help separates current value from example: " + setting.id);
          const box = help.getBoundingClientRect();
          check(box.left >= 0 && box.right <= innerWidth + 1 && box.top >= 0 && box.bottom <= innerHeight + 1, "Long help stays within viewport: " + setting.id);
          help.scrollTop = help.scrollHeight;
          help.dispatchEvent(new Event("scroll", {bubbles: true}));
          check(!help.hidden, "Reading long help does not dismiss it: " + setting.id);
          help.querySelector("button").click();
          if (panel) panel.open = wasOpen;
        }
        check(JSON.stringify(settingsInputs.map((item) => item.value)) === JSON.stringify(valuesBeforeHelp), "Reading all explanations changes no settings");
        click('[data-strategy-tab="3"]');
        const bandHelp = one("#balance-no-trade-band").closest(".touch-setting").querySelector(".setting-label .help-trigger");
        bandHelp.closest("details").open = true;
        bandHelp.click();
        check(help.textContent.includes("не отклонение") && help.textContent.includes("строго"), "Replacement threshold is not mislabelled as allocation drift");
        help.querySelector("button").click();
        check(writes().length === 0, "Draft edits and help never apply confirmed profile/policy");
        click('[data-strategy-tab="2"]');
        one("#investment-profile-save").click();
        check(one("#workspace-dialog").open && one(".settings-review"), "Readable review opens before saving");
        check(!one("#dialog-content").textContent.includes("expected_public_id"), "Internal API keys are not exposed as review labels");
        check(one("#settings-review-save").disabled && !one("#settings-review-confirmation").checked, "Confirmation is never prechecked");
        const trigger = one("#dialog-content .help-trigger");
        trigger.click();
        check(!help.hidden && help.parentElement === one("#workspace-dialog"), "Shared help uses native modal top layer");
        check(document.querySelectorAll("#workspace-help").length === 1, "There is only one help engine");
        document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
        check(help.hidden && one("#workspace-dialog").open, "Escape dismisses help before the parent review");
        one(".settings-review-actions .button-secondary").click();
        await new Promise((resolveWait) => setTimeout(resolveWait, 20));
        check(!one("#workspace-dialog").open && writes().length === 0, "Review cancellation writes nothing");
        const sentAmount = input.value;
        one("#investment-profile-save").click();
        one("#settings-review-confirmation").click();
        one("#settings-review-save").click();
        await waitFor(() => form.getAttribute("aria-busy") === "false");
        check(writes().length === 1, "Explicit review causes exactly one PUT");
        const sent = writes()[0].body;
        check(sent.reserve_rub === sentAmount && sent.expected_public_id === "000000123", "The exact reviewed amount and owner are transmitted");
        check(sent.expected_version === (mode === "empty" ? 0 : 3), "Expected version is retained in the existing contract");
        if (["conflict", "save-error"].includes(mode)) {
          check(one("#investment-profile-message").classList.contains("error"), "Failed save is not shown as success");
          check(input.value === sentAmount, "Failed save preserves the draft");
          if (mode === "conflict") check(one("#investment-profile-save").disabled, "Version conflict requires an explicit reload");
        } else {
          check(one("#investment-profile-version").textContent === (mode === "empty" ? "v1" : "v4"), "Server-confirmed version is displayed");
          check(input.value === sentAmount, "Exact amount survives save and render");
          // Opening a new review and then editing the actual input invalidates that snapshot.
          one("#investment-profile-save").click();
          input.value = "50000";
          input.dispatchEvent(new Event("input", {bubbles: true}));
          check(!one("#workspace-dialog").open && writes().length === 1, "Later input invalidates the old review without writing");
          // Restoring confirmed data must also refresh every generated control, not only hidden inputs.
          one("#investment-profile-reload").click();
          await waitFor(() => form.getAttribute("aria-busy") === "false");
          check(input.value === sentAmount && field.querySelector(".setting-value").textContent.replace(/\s/g, "").includes(sentAmount.replace(".", ",")), "Reload refreshes the visible value from the saved record");
        }
        check(document.querySelectorAll("[data-view-panel='strategy'] .help-trigger").length >= 36, "Profile, policy, allocation and permission controls have shared help");
      }
      check(matchMedia("(prefers-reduced-motion: reduce)").matches, "Reduced-motion environment is active");
      check(document.documentElement.scrollWidth <= innerWidth + 1, "Authenticated Strategy has no page overflow");
      check(window.__smokeErrors.length === 0, "No runtime errors: " + window.__smokeErrors.join(", "));
      window.__smokeResult = {passed: true, checks: results.length, viewport: innerWidth, mode};
      return;
    }
    check(!one("#auth-card").classList.contains("hidden"), "Anonymous login page visible");
    click('[data-auth-mode="register"]');
    check(one("#login-title").textContent.includes("Создать"), "Registration view");
    if (new URLSearchParams(location.search).has("login")) {
      window.__smokeResult = {passed: true, checks: results.length, viewport: innerWidth};
      return;
    }
    click("#start-demo");
    check(!one("#profile-panel").classList.contains("hidden"), "Demo workspace opened");
    check(one("#home-portfolio-total").textContent.replace(/\s/g, "").includes("1250000"), "Demo capital rendered");
    check(!one("#demo-banner").classList.contains("hidden"), "Permanent demo label");
    if (innerWidth < 1200) {
      check(one("#app-drawer").inert, "Closed drawer is not keyboard reachable");
      click("#app-menu-toggle");
      check(document.activeElement.id === "drawer-close", "Drawer receives focus");
      document.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
      check(one("#app-drawer").inert && document.activeElement.id === "app-menu-toggle", "Escape closes drawer and restores focus");
    }
    for (const view of ["home", "portfolio", "events", "assets", "strategy", "decisions", "orders", "payouts", "goals", "assistant", "settings"]) navigate(view);
    navigate("strategy");
    click('[data-lock="bonds"]');
    set(one('[data-target-number="shares"]'), "90");
    let values=[...document.querySelectorAll("[data-target-number]")].map(e=>Number(e.value));
    check(values.reduce((a,b)=>a+b,0)===100 && values[1]===60, "Locked allocation and exact total");
    check(values[0]===40, "Allocation clamps to unreserved remainder");
    click("#review-allocation");
    check(one("#workspace-dialog").open, "Draft diff dialog");
    click("#dialog-close");
    click("#reset-allocation");
    click('[data-allow="shares"]');
    check(one('[data-target-number="shares"]').disabled && one('[data-target-number="shares"]').value === "0", "Excluded class has zero allocation");
    check([...document.querySelectorAll("[data-target-number]")].reduce((sum, item) => sum + Number(item.value), 0) === 100, "Allowed classes still total 100%");
    click("#reset-allocation");
    navigate("assets");
    check(document.querySelectorAll(".hunter-result").length===4, "Synthetic catalog");
    click('[data-asset-filter="bond"]');
    check(document.querySelectorAll(".hunter-result").length===2, "Bond filter");
    const assetActions=[...document.querySelectorAll(".asset-actions")];
    assetActions[0].querySelectorAll("button")[1].click();
    click('[data-asset-filter="favorites"]');
    check(document.querySelectorAll(".hunter-result").length===1, "Favorite filter");
    click('[data-asset-filter="all"]');
    [...document.querySelectorAll(".asset-actions")].slice(0,2).forEach(row=>row.querySelectorAll("button")[2].click());
    click("#compare-assets");
    check(one("#workspace-dialog").open && document.querySelectorAll("#dialog-content td").length===8, "Two-instrument comparison");
    click("#dialog-close");
    navigate("goals");
    click("#create-goal");
    const form=one("#dialog-content form");
    for(const [name,value] of Object.entries({name:"Тестовая цель",target:"1000000",initial:"100000",monthly:"10000",date:"2030-12-01"})) set(form.elements[name],value);
    form.requestSubmit();
    check(!one("#workspace-dialog").open && one(".goal-card"), "Goal scenario created");
    check(one(".goal-card").textContent.includes("Тестовая цель"), "Goal title preserved");
    navigate("payouts");
    check(document.querySelectorAll(".calendar-day.has-payout").length===2, "Payout calendar renders dates");
    click(".calendar-day.has-payout");
    check(one("#workspace-dialog").open, "Payout details");
    click("#dialog-close");
    navigate("assistant");
    click("[data-prompt]");
    one("#assistant-form").requestSubmit();
    check(one("#assistant-message").textContent.includes("не отправлено"), "Unconfigured AI is honestly marked");
    navigate("home");
    await verifyHelp(check);
    click("#privacy-toggle");
    check(document.body.classList.contains("privacy-mode"), "Hide amounts");
    click("#privacy-toggle");
    click("#quick-theme");
    check(document.body.dataset.theme === "dark", "Dark theme");
    click("#quick-theme");
    click("#open-onboarding");
    check(one("#workspace-dialog").open, "Onboarding dialog");
    click("#dialog-close");
    check(window.__smokeErrors.length===0, "No runtime errors: " + window.__smokeErrors.join(", "));
    window.__smokeResult = {passed: true, checks: results.length, viewport: innerWidth};
    const output=document.createElement("pre");output.id="smoke-result";output.dataset.result="passed";output.textContent=JSON.stringify({viewport:innerWidth,checks:results.length});document.body.append(output);
  } catch(error) {
    window.__smokeResult = {passed: false, error: error.stack + "\n" + window.__smokeErrors.join("\n")};
    const output=document.createElement("pre");output.id="smoke-result";output.dataset.result="failed";output.textContent=error.stack + "\n"+window.__smokeErrors.join("\n");document.body.append(output);
  }
}, 300));
`;

let writes = 0;
let syntheticWrites = 0;
let strategyWrites = 0;
let brokerReads = 0;
const types = {".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".webmanifest": "application/manifest+json", ".png": "image/png"};
const renderPublicBody = (pathname, file) => {
  let body = readFileSync(file);
  if (pathname === "/sw.js") body = body.toString().replaceAll("__OMNICIO_BUILD__", build);
  if (pathname === "/") {
    body = body.toString().replaceAll("__OMNICIO_BUILD__", build).replaceAll("__OMNICIO_VERSION__", version);
    body = body.replace("<head>", '<head><script>window.__smokeDocumentUrl=location.href;window.__smokeErrors=[];addEventListener("error",e=>window.__smokeErrors.push(e.message));addEventListener("unhandledrejection",e=>window.__smokeErrors.push(String(e.reason)));</script>');
    body = body.replace('<script src="/assets/app.js?', '<script src="/smoke.js" defer></script><script src="/assets/app.js?');
  }
  return body;
};
// Synthetic-only contract. No credential, real account or provider request is used.
const createSettingsFixture = (mode = "saved") => {
  const owner = "000000123";
  const state = {
    requests: [],
    profile: mode === "empty" ? null : {
      version: 3, created_at: "2026-10-05T10:00:00Z", reserve_rub: "123456789.12345678",
      planned_withdrawal_rub: "2500.25", horizon_months: 84, max_drawdown_percent: "18.5123",
      liquidity_horizon_days: 14, allow_below_investment_grade: false,
    },
    policy: mode === "empty" ? null : {
      version: 3, created_at: "2026-10-05T10:00:00Z", max_instrument_percent: "12.3456",
      max_sector_percent: "25.5", max_issuer_percent: "15.1", max_group_percent: "22.2",
      max_share_percent: "55.5", max_bond_percent: "80", max_etf_percent: "30",
      max_below_grade_percent: "0", max_unknown_percent: "0", max_term_months: 180,
      turnover_budget_percent: "9.5", max_daily_turnover_participation_percent: "4.5",
      securities_tax_rate_percent: "13", uncertainty_haircut_percent: "8.5",
      credit_loss_haircut_percent: "17.5", no_trade_band_percent: "1.5", min_replace_benefit_rub: "9999.99",
    },
  };
  const json = (value, status = 200) => new Response(JSON.stringify(value), {
    status, headers: {"Content-Type": "application/json"},
  });
  const request = async (path, options = {}) => {
    const method = options.method || "GET";
    const payload = options.body ? JSON.parse(options.body) : null;
    state.requests.push({path, method, payload});
    if (path === "/api/auth/config") return json({auth_provider: "vkid", login_enabled: true, registration_enabled: false, registration_max_users: 2});
    if (path === "/api/me") return json({public_id: owner, role: "user"});
    if (path === "/api/broker/tbank") return json({connected: false});
    const key = {"/api/profile/investment": "profile", "/api/profile/balancing": "policy"}[path];
    if (!key) return json({detail: "synthetic_unavailable"}, 404);
    if (mode === "load-error" && method === "GET") return json({detail: "synthetic_failure"}, 503);
    if (method === "PUT") {
      if (new Headers(options.headers).get("X-Omnicio-Profile") !== owner || payload.expected_public_id !== owner) {
        return json({detail: "settings_owner_conflict"}, 409);
      }
      if (mode === "conflict" || payload.expected_version !== (state[key]?.version || 0)) {
        return json({detail: "settings_version_conflict"}, 409);
      }
      if (mode === "save-error") return json({detail: "synthetic_save_failure"}, 500);
      const keys = Object.keys(payload).filter((name) => !name.startsWith("expected_"));
      if (keys.length !== (key === "profile" ? 6 : 17)) return json({detail: "invalid_contract"}, 422);
      state[key] = Object.fromEntries(keys.map((name) => [name, payload[name]]));
      state[key].version = payload.expected_version + 1;
      state[key].created_at = "2026-10-05T10:01:00Z";
    }
    return json({public_id: mode === "wrong-owner" ? "000000999" : owner, [key]: state[key]});
  };
  return {state, request};
};

const createStrategyFixture = (mode = "saved") => {
  const original = createSettingsFixture(mode);
  const state = {...original.state, selection: null, delay: 0, failure: null, loadFailure: mode === "strategy-load-error",
    holdPrerequisites: mode === "strategy-prerequisite-delay", waitingPrerequisites: []};
  state.releasePrerequisites = () => {
    state.holdPrerequisites = false;
    state.waitingPrerequisites.splice(0).forEach((release) => release());
  };
  const json = (value, status = 200) => new Response(JSON.stringify(value), {status, headers: {"Content-Type": "application/json"}});
  return {state, request: async (path, options) => {
    if (state.holdPrerequisites && options.method === "GET"
      && ["/api/profile/investment", "/api/profile/balancing"].includes(path)) {
      await new Promise((release) => state.waitingPrerequisites.push(release));
    }
    if (path === "/api/strategy/catalog") return state.loadFailure ? json({detail: "synthetic_initial_failure"}, 503) : json(strategyCatalog);
    if (path !== "/api/profile/strategy") return original.request(path, options);
    if (options.method === "GET") return json({public_id: "000000123", selection: state.selection});
    const payload = JSON.parse(options.body);
    state.requests.push({path, method: options.method, payload});
    if (state.delay) await new Promise((resolve) => setTimeout(resolve, state.delay));
    if (state.failure === "unavailable") { state.failure = null; return json({detail: "synthetic_save_failure"}, 503); }
    if (payload.expected_public_id !== "000000123" || payload.expected_version !== (state.selection?.version ?? 0)) return json({detail: "settings_version_conflict"}, 409);
    const document = structuredClone(payload.document);
    if (payload.intent === "edit") document.customized = true;
    state.selection = {document, custom_document: document.customized ? document : state.selection?.custom_document ?? null,
      version: (state.selection?.version ?? 0) + 1, updated_at: new Date().toISOString()};
    if (state.failure === "lost_ack") { state.failure = null; return json({detail: "synthetic_response_lost"}, 503); }
    return json({public_id: "000000123", selection: state.selection});
  }};
};

const syntheticSessions = new Map();
const server = createServer(async (request, response) => {
  const pathname = new URL(request.url, "http://127.0.0.1").pathname;
  response.setHeader("Cache-Control", "no-store");
  if (pathname.startsWith("/api/")) {
    const referrer = new URL(request.headers.referer || "http://127.0.0.1");
    const synthetic = referrer.searchParams.has("synthetic");
    if (request.method !== "GET") {
      if (synthetic && pathname.startsWith("/api/profile/strategy")) strategyWrites += 1;
      else if (synthetic) syntheticWrites += 1;
      else writes += 1;
    }
    if (!synthetic && pathname.startsWith("/api/broker/")) brokerReads += 1;
    response.setHeader("Content-Type", "application/json");
    if (synthetic) {
      const identity = referrer.searchParams.get("session") || "default";
      if (!syntheticSessions.has(identity)) syntheticSessions.set(identity, createStrategyFixture(referrer.searchParams.get("fixture") || "saved"));
      const fixture = syntheticSessions.get(identity);
      const chunks = []; for await (const chunk of request) chunks.push(chunk);
      const result = await fixture.request(pathname, {method: request.method, headers: request.headers, body: chunks.length ? Buffer.concat(chunks).toString() : null});
      response.statusCode = result.status;
      response.end(await result.text());
      return;
    }
    response.statusCode = pathname === "/api/auth/config" ? 200 : 401;
    response.end(JSON.stringify(pathname === "/api/auth/config" ? {auth_provider: "vkid", login_enabled: true, registration_enabled: true, registration_max_users: 2} : {detail: "unauthenticated"}));
    return;
  }
  if (pathname === "/version.js") { response.setHeader("Content-Type", "text/javascript"); response.end('window.OMNICIO_RELEASE=' + JSON.stringify({version, build}) + ';'); return; }
  if (pathname === "/smoke.js") { response.setHeader("Content-Type", "text/javascript"); response.end(suite); return; }
  let file = join(web, pathname === "/" ? "index.html" : pathname.replace(/^\/assets\//, ""));
  if (pathname.startsWith("/assets/brand/")) file = join(root, "assets/brand/transparent/omni-sentinel-core-color-1024.png");
  if (!file.startsWith(root) || !existsSync(file)) { response.statusCode=404; response.end(); return; }
  const extension = require("node:path").extname(file);
  response.setHeader("Content-Type", types[extension] || "application/octet-stream");
  response.end(renderPublicBody(pathname, file));
});

const delay = (ms) => new Promise((resolveDelay) => setTimeout(resolveDelay, ms));
const waitUntil = async (condition, attempts = 150) => {
  const result = await condition();
  if (result || attempts === 0) return result;
  await delay(100);
  return waitUntil(condition, attempts - 1);
};

const protocolClient = async (url) => {
  const socket = new WebSocket(url);
  const pending = new Map();
  const listeners = new Set();
  let sequence = 0;
  await new Promise((resolveOpen, reject) => {
    socket.addEventListener("open", resolveOpen, {once: true});
    socket.addEventListener("error", reject, {once: true});
  });
  socket.addEventListener("message", ({data}) => {
    const message = JSON.parse(data);
    if (message.method) listeners.forEach((listener) => listener(message));
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    clearTimeout(request.timer);
    if (message.error) request.reject(new Error(JSON.stringify(message.error)));
    else request.resolveRequest(message.result);
  });
  return {
    send(method, params, sessionId) {
      return new Promise((resolveRequest, reject) => {
        const id = ++sequence;
        const timer = setTimeout(() => { pending.delete(id); reject(new Error("Protocol timed out: " + method)); }, 10000);
        pending.set(id, {resolveRequest, reject, timer});
        socket.send(JSON.stringify({id, method, params, sessionId}));
      });
    },
    onEvent: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    close: () => socket.close(),
  };
};

const verifyHelpInput = async (send, evaluate) => {
  const hidden = () => evaluate('document.querySelector("#workspace-help").hidden');
  const pinned = () => evaluate('!document.querySelector("#workspace-help").hidden && document.querySelector("#workspace-help").getAttribute("role") === "dialog"');
  const key = async (name, code, value) => {
    const text = {Enter: "\r", Space: " "}[code] || "";
    await send("Input.dispatchKeyEvent", {type: "keyDown", key: name, code, windowsVirtualKeyCode: value, text});
    await send("Input.dispatchKeyEvent", {type: "keyUp", key: name, code, windowsVirtualKeyCode: value, text: ""});
  };
  await evaluate('document.querySelector(".help-trigger").scrollIntoView({block:"center",behavior:"instant"})');
  await delay(100);
  await evaluate('document.querySelector(".help-trigger").focus()');
  await key("Enter", "Enter", 13);
  assert.equal(await pinned(), true, "Native Enter pins help");
  await key("Escape", "Escape", 27);
  assert.equal(await hidden(), true, "Native Escape closes pinned help");
  assert.equal(await evaluate('document.activeElement === document.querySelector(".help-trigger")'), true, "Native Escape restores the trigger focus");
  await key(" ", "Space", 32);
  assert.equal(await pinned(), true, "Native Space pins help without an extra activation");
  await key("Escape", "Escape", 27);
  await evaluate('document.activeElement.blur()');
  const center = await evaluate('(() => { const r=document.querySelector(".help-trigger").getBoundingClientRect(); return {x:r.left+r.width/2,y:r.top+r.height/2}; })()');
  await send("Input.dispatchMouseEvent", {type: "mouseMoved", ...center});
  assert.equal(await waitUntil(async () => !await hidden()), true, "Native mouse hover opens help");
  const popupPoint = await evaluate('(() => { const r=document.querySelector("#workspace-help").getBoundingClientRect(); return {x:r.left+r.width/2,y:r.top+r.height/2}; })()');
  await send("Input.dispatchMouseEvent", {type: "mouseMoved", ...popupPoint});
  await delay(220);
  assert.equal(await hidden(), false, "Native pointer can hover over the help text");
  await send("Input.dispatchMouseEvent", {type: "mouseMoved", x: 1, y: 1});
  assert.equal(await waitUntil(hidden), true, "Native pointer departure closes unpinned help");
  await send("Emulation.setTouchEmulationEnabled", {enabled: true});
  try {
    await send("Input.dispatchTouchEvent", {type: "touchStart", touchPoints: [{...center, id: 1}]});
    assert.equal(await waitUntil(async () => !await hidden()), true, "Native long press opens temporary help");
    await send("Input.dispatchTouchEvent", {type: "touchEnd", touchPoints: []});
    await delay(220);
    assert.equal(await hidden(), true, "Native touch release and compatibility click do not reopen help");
    await send("Input.dispatchTouchEvent", {type: "touchStart", touchPoints: [{...center, id: 2}]});
    await send("Input.dispatchTouchEvent", {type: "touchEnd", touchPoints: []});
    assert.equal(await pinned(), true, "The next native short tap remains available");
    assert.equal(await hidden(), false, "The next native tap pins visible help");
    await key("Escape", "Escape", 27);
  } finally {
    await send("Emulation.setTouchEmulationEnabled", {enabled: false});
  }
  await evaluate('document.activeElement.blur()');
};

// Uses browser input events on the real controls, never force-enables a field.
const verifyStrategyInput = async (send, evaluate) => {
  const key = async (name, code, value) => {
    await send("Input.dispatchKeyEvent", {type: "keyDown", key: name, code, windowsVirtualKeyCode: value});
    await send("Input.dispatchKeyEvent", {type: "keyUp", key: name, code, windowsVirtualKeyCode: value});
  };
  const locate = async (selector) => {
    await evaluate(`(() => { const e=document.querySelector(${JSON.stringify(selector)}); const panel=e.closest('[role="tabpanel"]'); if(panel)document.querySelector('[aria-controls="'+panel.id+'"]').click(); const d=e.closest("details"); if(d) d.open=true; e.scrollIntoView({block:"center",behavior:"instant"}); })()`);
    await delay(80);
    return evaluate(`(() => { const e=document.querySelector(${JSON.stringify(selector)}); const r=e.getBoundingClientRect(); return {x:r.left+r.width/2,y:r.top+r.height/2}; })()`);
  };
  const mouse = async (selector) => {
    const point = await locate(selector);
    await send("Input.dispatchMouseEvent", {type: "mouseMoved", ...point});
    await send("Input.dispatchMouseEvent", {type: "mousePressed", button: "left", clickCount: 1, ...point});
    await send("Input.dispatchMouseEvent", {type: "mouseReleased", button: "left", clickCount: 1, ...point});
  };
  const count = await evaluate('window.__smokeRequests.filter(r=>r.method==="PUT" && r.path!=="/api/profile/strategy").length');
  const stepSelector = '.touch-setting:has(#profile-reserve-rub) select';
  await locate(stepSelector);
  await evaluate(`document.querySelector(${JSON.stringify(stepSelector)}).focus({preventScroll:true})`);
  await key("Home", "Home", 36);
  await key("ArrowDown", "ArrowDown", 40);
  await key("ArrowDown", "ArrowDown", 40); // Explicitly select the one-cent step.
  const plus = '#profile-reserve-rub';
  const button = '.touch-setting:has(' + plus + ') [data-step-direction="1"]';
  await mouse(button);
  assert.equal(await evaluate('document.querySelector("#profile-reserve-rub").value'), "123456789.14345678", "Native click adds one cent without rounding the saved eight-place amount");
  const point = await locate(button);
  await send("Emulation.setTouchEmulationEnabled", {enabled: true});
  try {
    await send("Input.dispatchTouchEvent", {type: "touchStart", touchPoints: [{...point, id: 1}]});
    await send("Input.dispatchTouchEvent", {type: "touchEnd", touchPoints: []});
    await delay(80);
    assert.equal(await evaluate('document.querySelector("#profile-reserve-rub").value'), "123456789.15345678", "Native tap changes the value exactly once");
  } finally { await send("Emulation.setTouchEmulationEnabled", {enabled: false}); }
  assert.equal(await evaluate('document.querySelector("#profile-reserve-rub").hidden'), true, "Touch adjustment never opens mandatory typing");
  const ids = await evaluate('[...document.querySelectorAll(".touch-setting input[type=number]")].map(e=>e.id)');
  assert.equal(ids.length, 22);
  for (const id of ids) {
    const selector = '.touch-setting:has(#' + id + ')';
    const range = selector + ' .setting-range';
    if (await evaluate(`Boolean(document.querySelector(${JSON.stringify(range)}))`)) {
      await locate(range);
      await evaluate(`document.querySelector(${JSON.stringify(range)}).focus({preventScroll:true})`);
      await key("End", "End", 35);
      await key("ArrowRight", "ArrowRight", 39);
      assert.equal(await evaluate(`document.getElementById(${JSON.stringify(id)}).value`), await evaluate(`document.getElementById(${JSON.stringify(id)}).max`), id + " native maximum bound");
      await key("Home", "Home", 36);
      await key("ArrowLeft", "ArrowLeft", 37);
      assert.equal(await evaluate(`document.getElementById(${JSON.stringify(id)}).value`), await evaluate(`document.getElementById(${JSON.stringify(id)}).min`), id + " native minimum bound");
    } else {
      const step = selector + ' select';
      await locate(step);
      await evaluate(`document.querySelector(${JSON.stringify(step)}).focus({preventScroll:true})`);
      await key("End", "End", 35);
      await mouse(selector + ' [data-step-direction="1"]');
      const maximum = await evaluate(`document.getElementById(${JSON.stringify(id)}).max`);
      const value = await evaluate(`document.getElementById(${JSON.stringify(id)}).value`);
      assert.equal(value, id === "profile-liquidity-days" ? "114" : maximum, id + " native coarse step");
    }
    const geometry = await evaluate(`(() => { const e=document.querySelector(${JSON.stringify(selector)}); const b=e.querySelector('.step-button').getBoundingClientRect(); return {width:b.width,height:b.height,overflow:document.documentElement.scrollWidth>innerWidth+1}; })()`);
    assert.ok(geometry.width >= 44 && geometry.height >= 44 && !geometry.overflow, id + " usable touch targets and no overflow");
  }
  assert.equal(await evaluate('window.__smokeRequests.filter(r=>r.method==="PUT" && r.path!=="/api/profile/strategy").length'), count, "Native changes never apply confirmed profile/policy without review");
};


const verifyStrategyLibrary = async (send, evaluate, fixture) => {
  const click = async (selector) => {
    const point = await evaluate(`(() => { const e=document.querySelector(${JSON.stringify(selector)}); if(!e||e.disabled)throw Error('Missing/disabled '+${JSON.stringify(selector)}); e.scrollIntoView({block:'center',behavior:'instant'}); const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    await send("Input.dispatchMouseEvent", {type: "mousePressed", button: "left", clickCount: 1, ...point});
    await send("Input.dispatchMouseEvent", {type: "mouseReleased", button: "left", clickCount: 1, ...point});
  };
  const saved = async () => assert.equal(await waitUntil(() => evaluate('document.querySelector(".strategy-savebar [role=status]").textContent.includes("сохранён в аккаунте")')), true, "Autosave acknowledged, not optimistic success");
  assert.equal(fixture.state.selection, null, "Loading a default sends no write");
  assert.equal(await evaluate('document.querySelectorAll("[data-strategy-tab]").length'), 5);
  const originalMoney = await evaluate('document.querySelector("#profile-reserve-rub").value');
  for (const preset of strategyCatalog.presets) {
    await click(`[data-choose-strategy="${preset.id}"]`); await saved();
    assert.equal(fixture.state.selection.document.base_preset_id, preset.id);
    assert.equal(fixture.state.selection.document.customized, false);
    assert.deepEqual(fixture.state.selection.document.allocation, preset.document.allocation);
    assert.equal(fixture.state.selection.document.profile.reserve_rub, originalMoney, "Personal money is preserved across templates");
  }
  await click('[data-strategy-tab="2"]');
  const plus = '.touch-setting:has(#profile-reserve-rub) [data-step-direction="1"]';
  await click(plus);
  assert.equal(await evaluate('document.querySelector(".strategy-savebar strong").textContent.startsWith("Пользовательская")'), true, "The label changes immediately after a real edit");
  await saved();
  const custom = structuredClone(fixture.state.selection.document);
  assert.equal(custom.customized, true);
  assert.notEqual(custom.profile.reserve_rub, originalMoney);
  await click('[data-strategy-tab="0"]'); await click('[data-choose-strategy="income"]'); await saved();
  assert.deepEqual(fixture.state.selection.custom_document, custom, "Selecting a template preserves the custom copy");
  await click('#strategy-restore-custom'); await saved();
  assert.deepEqual(fixture.state.selection.document, custom, "Personal configuration can be restored exactly");
  await click('[data-strategy-tab="2"]');
  fixture.state.delay = 600;
  await click(plus); await delay(180); await click(plus); await delay(180); await click(plus);
  await saved(); fixture.state.delay = 0;
  assert.equal(fixture.state.selection.document.profile.reserve_rub, await evaluate('document.querySelector("#profile-reserve-rub").value'), "Late save responses do not erase newer edits");
  fixture.state.failure = "lost_ack"; await click(plus);
  assert.equal(await waitUntil(() => evaluate('!document.querySelector(".strategy-savebar button:nth-last-child(2)").hidden')), true);
  const lostVersion = fixture.state.selection.version;
  await click('.strategy-savebar button:nth-last-child(2)');
  assert.equal(await waitUntil(() => evaluate('document.querySelector(".strategy-savebar [role=status]").textContent.includes("подтверждено сервером")')), true);
  assert.equal(fixture.state.selection.version, lostVersion, "Lost acknowledgement reconciliation does not duplicate the write");
  fixture.state.delay = 600; fixture.state.failure = "lost_ack";
  await click(plus); await delay(650); await click(plus);
  assert.equal(await waitUntil(() => evaluate('!document.querySelector(".strategy-savebar button:nth-last-child(2)").hidden')), true);
  fixture.state.delay = 0;
  const acknowledgedVersion = fixture.state.selection.version;
  const newestAmount = await evaluate('document.querySelector("#profile-reserve-rub").value');
  assert.notEqual(fixture.state.selection.document.profile.reserve_rub, newestAmount, "The newer local edit is not the lost-ACK snapshot");
  await click('.strategy-savebar button:nth-last-child(2)'); await saved();
  assert.equal(fixture.state.selection.version, acknowledgedVersion + 1, "Newer edit is saved only after the earlier exact snapshot is reconciled");
  assert.equal(fixture.state.selection.document.profile.reserve_rub, newestAmount, "Lost acknowledgement cannot strand newer edits");
  fixture.state.selection.version += 1; // Another device, not a client overwrite.
  const foreign = structuredClone(fixture.state.selection.document);
  await click(plus);
  assert.equal(await waitUntil(() => evaluate('document.querySelector(".strategy-savebar [role=status]").textContent.includes("Конфликт версий")')), true);
  assert.deepEqual(fixture.state.selection.document, foreign, "Conflict cannot overwrite another device's document");
  assert.notEqual(await evaluate('document.querySelector("#profile-reserve-rub").value'), foreign.profile.reserve_rub, "Conflict retains local edits");
  await click('[data-strategy-tab="3"]');
  assert.equal(await evaluate('document.querySelectorAll(".strategy-rating-grid select").length'), strategyCatalog.rating_levels.length);
  assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'), true, "Compact layout has no horizontal overflow");
  assert.equal(fixture.state.requests.some((item) => item.method === "PUT" && item.path !== "/api/profile/strategy"), false, "Autosave never applies profile/policy or broker permissions");
  console.log("Strategy catalog/autosave: template selection, custom restore, exact money, slow save, lost acknowledgement and conflict verified");
};

const run = async (url, width) => {
  const profile = mkdtempSync(join(tmpdir(), "omnicio-browser-test-"));
  const child = spawn(executable, ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], {stdio: ["ignore", "ignore", "pipe"]});
  let errors = "";
  let exited = false;
  child.stderr.on("data", (chunk) => { errors = (errors + chunk).slice(-5000); });
  child.on("error", (error) => { errors += error.message; exited = true; });
  child.on("close", () => { exited = true; });
  let client;
  try {
    const portFile = join(profile, "DevToolsActivePort");
    await waitUntil(() => existsSync(portFile) || exited);
    assert.ok(existsSync(portFile), "Browser did not start: " + errors);
    const [port, endpoint] = readFileSync(portFile, "utf8").trim().split(/\r?\n/);
    client = await protocolClient(`ws://127.0.0.1:${port}${endpoint}`);
    const {targetId} = await client.send("Target.createTarget", {url: "about:blank"});
    const {sessionId} = await client.send("Target.attachToTarget", {targetId, flatten: true});
    const send = (method, params) => client.send(method, params, sessionId);
    const evaluate = async (expression) => {
      const result = await send("Runtime.evaluate", {expression, returnByValue: true, awaitPromise: true});
      assert.ok(!result.exceptionDetails, JSON.stringify(result.exceptionDetails));
      return result.result.value;
    };
    let navigationRequested = false;
    let dialogError = null;
    let unloadWarnings = 0;
    client.onEvent((message) => {
      if (message.method !== "Page.javascriptDialogOpening" || message.sessionId !== sessionId) return;
      const expected = navigationRequested && message.params.type === "beforeunload";
      if (!expected) dialogError = new Error("Unexpected native dialog: " + message.params.type);
      else unloadWarnings += 1;
      void send("Page.handleJavaScriptDialog", {accept: expected}).catch((error) => { dialogError = error; });
    });
    await send("Page.enable");
    await send("Emulation.setDeviceMetricsOverride", {width, height: 1000, deviceScaleFactor: 1, mobile: width < 768});
    await send("Emulation.setEmulatedMedia", {features: [{name: "prefers-color-scheme", value: "light"}, {name: "prefers-reduced-motion", value: "reduce"}]});
    const navigatePage = async (address) => {
      navigationRequested = true;
      console.log("Browser fixture " + width + ": " + address);
      try { await send("Page.navigate", {url: address}); }
      finally { navigationRequested = false; }
      assert.equal(dialogError, null);
    };
    const visit = async (address) => {
      await navigatePage(address);
      const result = await waitUntil(() => evaluate(`window.__smokeDocumentUrl === ${JSON.stringify(address)} && document.readyState === "complete" && window.__smokeResult`), 100);
      assert.ok(result, "Browser suite did not finish: " + JSON.stringify(await evaluate("({errors:window.__smokeErrors,url:location.href,text:document.body?.textContent.slice(0,600)})")));
      assert.equal(result.passed, true, result.error);
      assert.equal(result.viewport, width, "The actual viewport must match the requested size");
      return result;
    };
    const screenshot = async (name) => {
      const {data} = await send("Page.captureScreenshot", {format: "png"});
      writeFileSync(join(artifacts, `${name}-${width}.png`), Buffer.from(data, "base64"));
    };
    await visit(url + "?login");
    await screenshot("registration");
    const result = await visit(url);
    await verifyHelpInput(send, evaluate);
    await evaluate("document.querySelector('#smoke-result').remove()");
    await screenshot("home-light");
    await evaluate("document.querySelector('#quick-theme').click()");
    await screenshot("home-dark");
    await evaluate("document.querySelector('#quick-theme').click()");
    await ["strategy", "assets", "payouts", "assistant"].reduce((previous, view) => previous.then(async () => {
      await evaluate(`document.querySelector('[data-view="${view}"]').click()`);
      await screenshot(view);
    }), Promise.resolve());
    // Hold both prerequisite responses: no race can turn an early starter edit
    // into a baseline and then erase it with the subsequently loaded strategy.
    const prerequisiteId = "prerequisites-" + width;
    const prerequisite = createStrategyFixture("strategy-prerequisite-delay");
    syntheticSessions.set(prerequisiteId, prerequisite);
    const prerequisiteUrl = url + "?synthetic=1&catalog=1&session=" + prerequisiteId;
    await navigatePage(prerequisiteUrl);
    assert.equal(await waitUntil(() => prerequisite.state.waitingPrerequisites.length === 2), true);
    await evaluate(`document.querySelector('[data-view="strategy"]').click()`);
    assert.equal(await evaluate('document.querySelector(".strategy-layout").inert && document.querySelector(".strategy-live-settings").inert'), true, "Starter controls are blocked while prerequisite profile requests are pending");
    const allocationBefore = await evaluate('window.__smokeWorkspace.readAllocation()');
    const earlyPoint = await evaluate(`(() => { const e=document.querySelector('#target-shares'); e.scrollIntoView({block:'center',behavior:'instant'}); const r=e.getBoundingClientRect(); return {x:r.x+r.width*0.8,y:r.y+r.height/2}; })()`);
    await send("Input.dispatchMouseEvent", {type: "mousePressed", button: "left", clickCount: 1, ...earlyPoint});
    await send("Input.dispatchMouseEvent", {type: "mouseReleased", button: "left", clickCount: 1, ...earlyPoint});
    assert.deepEqual(await evaluate('window.__smokeWorkspace.readAllocation()'), allocationBefore, "Native input cannot change a not-yet-loaded strategy");
    assert.equal(prerequisite.state.requests.some((item) => item.method === "PUT"), false);
    prerequisite.state.releasePrerequisites();
    const initialized = await waitUntil(() => evaluate(`window.__smokeDocumentUrl === ${JSON.stringify(prerequisiteUrl)} && window.__smokeResult`));
    assert.equal(initialized?.passed, true, initialized?.error);
    assert.equal(await evaluate('document.querySelector("#profile-reserve-rub").value'), "123456789.12345678", "Fetched owner values survive initialization");
    const authenticated = await visit(url + "?synthetic=1&session=saved-" + width);
    await screenshot("strategy-authenticated");
    await verifyStrategyInput(send, evaluate);
    console.log(`Authenticated settings ${width}: ${JSON.stringify(authenticated)}`);
    for (const fixture of ["empty", "load-error", "conflict", "save-error", "wrong-owner"]) {
      const outcome = await visit(url + `?synthetic=1&fixture=${fixture}&session=${fixture}-${width}`);
      console.log(`Settings ${fixture} ${width}: ${JSON.stringify(outcome)}`);
    }
    const failedIdentity = "strategy-load-error-" + width;
    await visit(url + "?synthetic=1&fixture=strategy-load-error&session=" + failedIdentity);
    syntheticSessions.get(failedIdentity).state.loadFailure = false;
    const retryPoint = await evaluate(`(() => { const e=document.querySelector('.strategy-load-status button'); e.scrollIntoView({block:'center',behavior:'instant'}); const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};})()`);
    await send("Input.dispatchMouseEvent", {type: "mousePressed", button: "left", clickCount: 1, ...retryPoint});
    await send("Input.dispatchMouseEvent", {type: "mouseReleased", button: "left", clickCount: 1, ...retryPoint});
    assert.equal(await waitUntil(() => evaluate('document.querySelectorAll("[data-choose-strategy]").length === 10')), true, "Initial failed load can be retried inside Strategy");
    assert.equal(await evaluate('document.querySelector(".strategy-load-status").hidden'), true);
    assert.equal(syntheticSessions.get(failedIdentity).state.requests.some((item) => item.method === "PUT"), false, "Retry does not save defaults");
    const catalogIdentity = "catalog-" + width;
    await visit(url + "?synthetic=1&catalog=1&session=" + catalogIdentity);
    await verifyStrategyLibrary(send, evaluate, syntheticSessions.get(catalogIdentity));
    await evaluate(`document.querySelector('[data-strategy-tab="0"]').click()`);
    await screenshot("strategy-catalog");
    const calendarDays = await evaluate(`(() => {
      const now = new Date();
      const stamp = (day) => new Date(now.getFullYear(), now.getMonth(), day, 12).toISOString();
      window.__smokeWorkspace.setPayouts([
        {instrument_uid: "record-only", event_type: "dividend", record_at: stamp(15), status: "announced"},
        {instrument_uid: "paid", event_type: "coupon", actual_at: stamp(10), expected_at: stamp(20), amount: "10", currency: "RUB", status: "paid"},
      ]);
      return [...document.querySelectorAll(".calendar-day.has-payout")].map(element => element.firstChild.textContent);
    })()`);
    assert.deepEqual(calendarDays, ["10"], "Record dates are not payment dates, and actual payment dates supersede estimates");
    const cacheNames = await evaluate("navigator.serviceWorker.ready.then(() => caches.keys())");
    assert.ok(cacheNames.includes("omnicio-public-" + build), "The installed worker cache must use the rendered release build");
    assert.equal(dialogError, null);
    assert.ok(unloadWarnings > 0, "Native unsaved-draft exit protection remains active");
    console.log(`Browser smoke ${width}: ${JSON.stringify(result)}; native exit warnings: ${unloadWarnings}`);
  } finally {
    if (client) {
      try { await client.send("Browser.close"); } finally { client.close(); }
    }
    if (!await waitUntil(() => exited, 20)) child.kill();
    rmSync(profile, {recursive: true, force: true, maxRetries: 8, retryDelay: 250});
  }
};

server.listen(0, "127.0.0.1", async () => {
  try {
    await verifyPublicWorker();
    const url = `http://127.0.0.1:${server.address().port}/`;
    await [1440, 768, 390, 320].reduce((previous, width) => previous.then(() => run(url, width)), Promise.resolve());
    assert.equal(writes, 0, "Demo must never call a write endpoint");
    assert.equal(syntheticWrites, 16, "Each successful-load scenario sends one reviewed write; failed loads send none");
    assert.equal(brokerReads, 0, "Demo must never contact broker endpoints");
    assert.ok(strategyWrites >= 4 * 16, "All viewports exercise actual synthetic-server autosaves");
    console.log("Demo isolation: zero private broker requests and writes");
  } catch (error) { console.error(error.message); process.exitCode = 1; }
  finally { server.close(); }
});
