/* Browser contract tests against an isolated synthetic server; no production API. */
const {createServer} = require("node:http");
const {readFileSync, writeFileSync, existsSync, mkdtempSync, mkdirSync, rmSync} = require("node:fs");
const {join, resolve} = require("node:path");
const {tmpdir} = require("node:os");
const {spawn} = require("node:child_process");
const assert = require("node:assert/strict");

const root = resolve(__dirname, "..");
const web = join(root, "web");
const candidates = [
  process.env.OMNICIO_TEST_BROWSER,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/usr/bin/chromium", "/usr/bin/google-chrome",
].filter(Boolean);
const executable = candidates.find(existsSync);
assert.ok(executable, "Install Chrome/Edge on the CI runner or set OMNICIO_TEST_BROWSER; browser QA cannot be skipped.");
assert.equal(typeof WebSocket, "function", "Node 22+ is required for the browser protocol client.");
const artifacts = join(root, "artifacts", "frontend");
mkdirSync(artifacts, {recursive: true});

const suite = String.raw`
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
  if (pathname === "/version.js") { response.setHeader("Content-Type", "text/javascript"); response.end('window.OMNICIO_RELEASE={version:"0.19.0",build:"smoke0190"};'); return; }
  if (pathname === "/smoke.js") { response.setHeader("Content-Type", "text/javascript"); response.end(suite); return; }
  let file = join(web, pathname === "/" ? "index.html" : pathname.replace(/^\/assets\//, ""));
  if (pathname.startsWith("/assets/brand/")) file = join(root, "assets/brand/transparent/omni-sentinel-core-color-1024.png");
  if (!file.startsWith(root) || !existsSync(file)) { response.statusCode=404; response.end(); return; }
  const extension = require("node:path").extname(file);
  response.setHeader("Content-Type", types[extension] || "application/octet-stream");
  let body = readFileSync(file);
  if (pathname === "/") {
    body = body.toString().replaceAll("__OMNICIO_BUILD__", "smoke0190").replaceAll("__OMNICIO_VERSION__", "0.19.0");
    body = body.replace("<head>", '<head><script>window.__smokeErrors=[];addEventListener("error",e=>window.__smokeErrors.push(e.message));addEventListener("unhandledrejection",e=>window.__smokeErrors.push(String(e.reason)));</script>');
    body = body.replace("</body>", '<script src="/smoke.js" defer></script></body>');
  }
  response.end(body);
});

const delay = (ms) => new Promise((resolveDelay) => setTimeout(resolveDelay, ms));

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
    send(method, params = {}, sessionId) {
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
    for (let attempt = 0; attempt < 150 && !existsSync(portFile) && !exited; attempt += 1) await delay(100);
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
      let result;
      for (let attempt = 0; attempt < 100 && !result; attempt += 1) {
        await delay(100);
        result = await evaluate("window.__smokeResult");
      }
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
    for (const view of ["strategy", "assets", "payouts", "assistant"]) {
      await evaluate(`document.querySelector('[data-view="${view}"]').click()`);
      await screenshot(view);
    }
    console.log(`Browser smoke ${width}: ${JSON.stringify(result)}`);
  } finally {
    if (client) {
      try { await client.send("Browser.close"); } finally { client.close(); }
    }
    for (let attempt = 0; attempt < 20 && !exited; attempt += 1) await delay(100);
    if (!exited) child.kill();
    rmSync(profile, {recursive: true, force: true, maxRetries: 8, retryDelay: 250});
  }
};

server.listen(0, "127.0.0.1", async () => {
  try {
    const url = `http://127.0.0.1:${server.address().port}/`;
    for (const width of [1440, 768, 390, 320]) await run(url, width);
    assert.equal(writes, 0, "Demo must never call a write endpoint");
    assert.equal(brokerReads, 0, "Demo must never contact broker endpoints");
    console.log("Demo isolation: zero private broker requests and writes");
  } catch (error) { console.error(error.message); process.exitCode = 1; }
  finally { server.close(); }
});
