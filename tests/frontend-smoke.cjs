/* Browser contract tests against an isolated synthetic server; no production API. */
const {createServer} = require("node:http");
const {readFileSync, writeFileSync, existsSync, mkdtempSync, mkdirSync, rmSync} = require("node:fs");
const {join, resolve} = require("node:path");
const {tmpdir} = require("node:os");
const {spawn} = require("node:child_process");
const assert = require("node:assert/strict");

const root = resolve(__dirname, "..");
const web = join(root, "web");
const version = /^version = "([^"\r\n]+)"$/m.exec(readFileSync(join(root, "pyproject.toml"), "utf8"))[1];
const build = "smoke-" + version;
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
const initializeWorkspace = window.OmniWorkspace.init;
window.OmniWorkspace.init = (adapter) => {
  const controls = initializeWorkspace(adapter);
  window.__smokeWorkspace = controls;
  return controls;
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
let brokerReads = 0;
const types = {".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".webmanifest": "application/manifest+json", ".png": "image/png"};
const renderPublicBody = (pathname, file) => {
  let body = readFileSync(file);
  if (pathname === "/sw.js") body = body.toString().replaceAll("__OMNICIO_BUILD__", build);
  if (pathname === "/") {
    body = body.toString().replaceAll("__OMNICIO_BUILD__", build).replaceAll("__OMNICIO_VERSION__", version);
    body = body.replace("<head>", '<head><script>window.__smokeErrors=[];addEventListener("error",e=>window.__smokeErrors.push(e.message));addEventListener("unhandledrejection",e=>window.__smokeErrors.push(String(e.reason)));</script>');
    body = body.replace('<script src="/assets/app.js?', '<script src="/smoke.js" defer></script><script src="/assets/app.js?');
  }
  return body;
};
const server = createServer((request, response) => {
  const pathname = new URL(request.url, "http://127.0.0.1").pathname;
  response.setHeader("Cache-Control", "no-store");
  if (pathname.startsWith("/api/")) {
    if (request.method !== "GET") writes += 1;
    if (pathname.startsWith("/api/broker/")) brokerReads += 1;
    response.setHeader("Content-Type", "application/json");
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
  let sequence = 0;
  await new Promise((resolveOpen, reject) => {
    socket.addEventListener("open", resolveOpen, {once: true});
    socket.addEventListener("error", reject, {once: true});
  });
  socket.addEventListener("message", ({data}) => {
    const message = JSON.parse(data);
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
    close: () => socket.close(),
  };
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
    await send("Page.enable");
    await send("Emulation.setDeviceMetricsOverride", {width, height: 1000, deviceScaleFactor: 1, mobile: width < 768});
    await send("Emulation.setEmulatedMedia", {features: [{name: "prefers-color-scheme", value: "light"}, {name: "prefers-reduced-motion", value: "reduce"}]});
    const visit = async (address) => {
      await send("Page.navigate", {url: address});
      const result = await waitUntil(() => evaluate("window.__smokeResult"), 100);
      assert.ok(result, "Browser suite did not finish");
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
    await evaluate("document.querySelector('#smoke-result').remove()");
    await screenshot("home-light");
    await evaluate("document.querySelector('#quick-theme').click()");
    await screenshot("home-dark");
    await evaluate("document.querySelector('#quick-theme').click()");
    await ["strategy", "assets", "payouts", "assistant"].reduce((previous, view) => previous.then(async () => {
      await evaluate(`document.querySelector('[data-view="${view}"]').click()`);
      await screenshot(view);
    }), Promise.resolve());
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
    console.log(`Browser smoke ${width}: ${JSON.stringify(result)}`);
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
    assert.equal(brokerReads, 0, "Demo must never contact broker endpoints");
    console.log("Demo isolation: zero private broker requests and writes");
  } catch (error) { console.error(error.message); process.exitCode = 1; }
  finally { server.close(); }
});
