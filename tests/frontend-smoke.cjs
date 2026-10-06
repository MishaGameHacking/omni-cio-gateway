/* Observable browser contracts, served by an isolated synthetic API. No production requests. */
"use strict";

const assert = require("node:assert/strict");
const vm = require("node:vm");
const {
  createServer
} = require("node:http");
const {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync
} = require("node:fs");
const {
  join,
  resolve,
  extname
} = require("node:path");
const {
  tmpdir
} = require("node:os");
const {
  spawn,
  spawnSync
} = require("node:child_process");
const root = resolve(__dirname, "..");
const version = /^version = "([^"\r\n]+)"$/m.exec(readFileSync(join(root, "pyproject.toml"), "utf8"))[1];
const build = `smoke-${version}`;
const catalogResult = spawnSync(process.env.OMNICIO_PYTHON || "python", ["-c", "import json,runpy; print(json.dumps(runpy.run_path('src/omnicio/strategy.py')['strategy_catalog']()))"], {
  cwd: root,
  encoding: "utf8",
  maxBuffer: 2 * 1024 * 1024
});
assert.equal(catalogResult.status, 0, "The browser uses the canonical server catalog: " + catalogResult.stderr);
const catalog = JSON.parse(catalogResult.stdout);
const artifacts = join(root, "artifacts", "frontend");
mkdirSync(artifacts, {
  recursive: true
});
const delay = ms => new Promise(resolveDelay => setTimeout(resolveDelay, ms));
const until = async (read, label, attempts = 150) => {
  for (let index = 0; index < attempts; index += 1) {
    if (await read()) return;
    await delay(100);
  }
  throw new Error("Timed out: " + label);
};
const clone = value => structuredClone(value);
// PostgreSQL JSONB need not preserve object-key order; reconciliation must compare meaning.
const reorderJSON = value => Array.isArray(value) ? value.map(reorderJSON) : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).reverse().map(key => [key, reorderJSON(value[key])])) : value;
const stamp = new Date().toISOString();
const day = offset => new Date(Date.now() - offset * 86400000).toISOString();
const fixtures = new Map();
const defaultPreferences = () => ({
  version: 1,
  document: {
    display_name: "Тестовый пользователь",
    locale: "ru",
    theme: "dark",
    mask_balances: false,
    watchlist: [],
    notifications: {
      portfolio: true,
      payments: true,
      goals: true,
      system: true
    },
    quiet_hours: {
      enabled: false,
      start: "22:00",
      end: "08:00",
      timezone: "Europe/Moscow"
    },
    digest_frequency: "off"
  }
});
const makeFixture = mode => {
  const preset = clone(catalog.presets.find(item => item.id === "balanced").document);
  preset.profile.reserve_rub = "123456789.12345678";
  preset.profile.planned_withdrawal_rub = "2500.25";
  preset.policy.securities_tax_rate_percent = "13";
  return {
    mode,
    user: "000000123",
    prefs: defaultPreferences(),
    selection: {
      version: 1,
      document: preset,
      custom_document: null,
      updated_at: stamp
    },
    goals: [],
    events: [{
      id: "synthetic-event-1",
      category: "system",
      kind: "connected",
      severity: "info",
      title: "Тестовое подтверждённое событие",
      detail: "Данные из изолированного API теста",
      occurred_at: stamp,
      read_at: null,
      target: "settings",
      source: "Synthetic API"
    }],
    requests: [],
    mutationDelay: 0,
    failPreferences: false,
    failWorkspace: false,
    failStrategyLoad: false,
    conflict: false,
    lostAck: false,
    activeWrites: 0,
    maxActiveWrites: 0,
    holdWorkspace: false,
    heldWorkspace: [],
    connected: true
  };
};
const overview = () => ({
  status: "observed",
  nav_rub: "150000.25",
  cash_rub: "100000.25",
  blocked_cash_rub: "0",
  free_cash_rub: "100000.25",
  observed_at: stamp,
  history: [{
    captured_at: day(4),
    nav_rub: "148000.25",
    status: "observed"
  }, {
    captured_at: day(2),
    nav_rub: "149000.25",
    status: "observed"
  }, {
    captured_at: stamp,
    nav_rub: "150000.25",
    status: "observed"
  }],
  allocations: [{
    key: "shares",
    label: "Акции",
    value_rub: "50000",
    nav_percent: "33.333"
  }, {
    key: "cash",
    label: "Деньги",
    value_rub: "100000.25",
    nav_percent: "66.667"
  }]
});
const eventDTO = fixture => ({
  items: clone(fixture.events),
  unread_count: fixture.events.filter(item => !item.read_at).length,
  alerts_suppressed: false,
  digest: {
    frequency: fixture.prefs.document.digest_frequency,
    from: day(1),
    count: fixture.events.length,
    by_category: {
      system: fixture.events.length
    }
  }
});
const connection = fixture => ({
  connected: fixture.connected,
  account_id: fixture.connected ? "synthetic-account" : null,
  account_name: fixture.connected ? "Тестовый счёт" : null,
  environment: "prod",
  verified_at: stamp
});
const workspace = fixture => ({
  generated_at: stamp,
  connection: connection(fixture),
  overview: fixture.connected ? overview() : {
    status: "not_connected",
    nav_rub: null,
    history: [],
    allocations: []
  },
  performance: {
    status: "available",
    method: "nav_less_external_flows",
    from: day(4),
    to: stamp,
    start_nav_rub: "148000.25",
    end_nav_rub: "150000.25",
    nav_change_rub: "2000",
    net_contributions_rub: "1000",
    investment_result_rub: "1000",
    return_percent: null,
    income_received_rub: "500",
    fees_rub: "20",
    taxes_rub: "13"
  },
  income: {
    status: "available",
    from: day(4),
    to: stamp,
    coupons_rub: "300",
    dividends_rub: "200",
    other_income_rub: "0",
    total_rub: "500",
    redemptions_rub: "0",
    by_month: []
  },
  preferences: clone(fixture.prefs),
  goals: {
    items: clone(fixture.goals)
  },
  events: eventDTO(fixture)
});
const positions = [{
  instrument_uid: "synthetic-a",
  ticker: "SYNA",
  name: "Тестовая компания A",
  instrument_type: "share",
  current_price_value: "250.25",
  current_price_currency: "rub",
  value_rub: "25000",
  quantity: "100",
  nav_percent: "16.66",
  blocked_lots: "0"
}, {
  instrument_uid: "synthetic-b",
  ticker: "SYNB",
  name: "Тестовая облигация B",
  instrument_type: "bond",
  current_price_value: "1000.55",
  current_price_currency: "rub",
  value_rub: "25000",
  quantity: "25",
  nav_percent: "16.66",
  blocked_lots: "0"
}];
const reference = {
  source: "Bank of Russia",
  status: "available",
  personal_data: false,
  indicators: {
    fetched_at: stamp,
    key_rate: {
      value: "10",
      effective_date: day(1).slice(0, 10)
    },
    usd_rub: {
      value: "80.1234",
      effective_date: day(1).slice(0, 10)
    },
    eur_rub: {
      value: "90.4321",
      effective_date: day(1).slice(0, 10)
    }
  },
  history: {
    fetched_at: stamp,
    points: [{
      effective_date: day(3).slice(0, 10),
      value: "80.12"
    }, {
      effective_date: day(2).slice(0, 10),
      value: "80.17"
    }, {
      effective_date: day(1).slice(0, 10),
      value: "80.1234"
    }]
  }
};
const sendJSON = (response, value, status = 200) => {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json");
  response.end(JSON.stringify(value));
};
const routeAPI = async (request, response, url, fixture, body) => {
  const path = url.pathname;
  const method = request.method;
  fixture.requests.push({
    path,
    method,
    body,
    profile: request.headers["x-omnicio-profile"],
    origin: request.headers.origin
  });
  if (path === "/api/auth/config") return sendJSON(response, {
    login_enabled: true,
    tid_enabled: true,
    tid_configured: true,
    auth_provider: "vkid",
    registration_enabled: false
  });
  if (path === "/api/strategy/catalog") return sendJSON(response, catalog);
  if (path === "/api/public/market-reference") return sendJSON(response, reference);
  if (path === "/api/public/news") return sendJSON(response, {
    items: [{
      id: "news-fixture",
      title: "Тестовая новость официального источника",
      url: "https://www.cbr.ru/press/",
      published_at: stamp,
      source: "Банк России",
      category: "market"
    }],
    fetched_at: stamp,
    freshness: "fresh"
  });
  if (/^\/api\/auth\/(tid|vkid)\/start$/.test(path)) return sendJSON(response, {
    authorize_url: "https://untrusted.invalid/authorize"
  });
  if (fixture.mode === "guest") return sendJSON(response, {
    detail: "authentication required"
  }, 401);
  if (request.headers["x-omnicio-profile"] && request.headers["x-omnicio-profile"] !== fixture.user) return sendJSON(response, {
    detail: "profile_context_changed"
  }, 409);
  if (!["GET", "HEAD"].includes(method) && (request.headers["x-omnicio-profile"] !== fixture.user || request.headers.origin !== `http://${request.headers.host}`)) return sendJSON(response, {
    detail: "profile_context_required"
  }, 409);
  if (path === "/api/me") return sendJSON(response, {
    public_id: fixture.user,
    status: "active",
    role: "user"
  });
  if (path === "/api/auth/identities") return sendJSON(response, {
    providers: ["vkid"],
    available_providers: {
      tid: true,
      vkid: true
    }
  });
  if (path === "/api/workspace") {
    const result = workspace(fixture);
    if (fixture.holdWorkspace) await new Promise(release => fixture.heldWorkspace.push(release));
    return sendJSON(response, fixture.failWorkspace ? {
      detail: "synthetic_failure"
    } : result, fixture.failWorkspace ? 503 : 200);
  }
  if (path === "/api/preferences" || path === "/api/profile/strategy") {
    const strategy = path.endsWith("strategy");
    const current = strategy ? fixture.selection : fixture.prefs;
    if (method === "GET") {
      if (!strategy && fixture.failPreferences || strategy && fixture.failStrategyLoad) return sendJSON(response, {
        detail: "synthetic_load_failure"
      }, 503);
      return sendJSON(response, reorderJSON(strategy ? {
        public_id: fixture.user,
        selection: clone(fixture.selection)
      } : clone(fixture.prefs)));
    }
    fixture.activeWrites += 1;
    fixture.maxActiveWrites = Math.max(fixture.maxActiveWrites, fixture.activeWrites);
    try {
      if (fixture.mutationDelay) await delay(fixture.mutationDelay);
      if (fixture.conflict || body.expected_version !== current.version) return sendJSON(response, {
        detail: "settings_version_conflict"
      }, 409);
      if (strategy) assert.equal(body.expected_public_id, fixture.user);
      const saved = {
        version: current.version + 1,
        document: clone(body.document)
      };
      if (strategy) {
        saved.updated_at = stamp;
        saved.custom_document = body.intent === "edit" ? clone(body.document) : fixture.selection.custom_document;
        fixture.selection = saved;
      } else fixture.prefs = saved;
      if (fixture.lostAck) {
        fixture.lostAck = false;
        return sendJSON(response, {
          detail: "synthetic_lost_ack"
        }, 503);
      }
      return sendJSON(response, strategy ? {
        public_id: fixture.user,
        selection: saved
      } : saved);
    } finally {
      fixture.activeWrites -= 1;
    }
  }
  if (path === "/api/profile/investment") return sendJSON(response, {
    public_id: fixture.user,
    profile: {
      version: 1,
      ...fixture.selection.document.profile
    }
  });
  if (path === "/api/profile/balancing") return sendJSON(response, {
    public_id: fixture.user,
    policy: {
      version: 1,
      ...fixture.selection.document.policy
    }
  });
  if (path === "/api/profile/strategy/account-assessment") return sendJSON(response, {
    public_id: fixture.user,
    strategy_version: fixture.selection.version,
    status: "assessed",
    nav_rub: "150000.25",
    captured_at: stamp,
    checks: [{
      title: "Проверка доли",
      state: "pass",
      detail: "Изолированные данные теста",
      value: "20",
      limit: "30"
    }],
    probability_of_profit: null,
    probability_reason: "Не является прогнозом"
  });
  if (path === "/api/profile/strategy/research") return sendJSON(response, {
    status: "insufficient_data",
    reason: "Нет достаточной истории в изолированном тесте",
    probability_of_profit: null
  });
  if (path === "/api/portfolio/visualization") return sendJSON(response, {
    status: "observed",
    history: overview().history,
    latest: {
      captured_at: stamp,
      ...overview(),
      positions: fixture.connected ? positions : []
    }
  });
  if (path.startsWith("/api/portfolio/instruments/")) return sendJSON(response, {
    status: "observed",
    latest: {
      ...positions[0],
      captured_at: stamp
    },
    sources: [],
    payouts: [],
    history: []
  });
  if (path.startsWith("/api/market/instruments/") && path.endsWith("/facts")) return sendJSON(response, {
    instrument_uid: "synthetic-a",
    currency: "rub",
    name: "Тестовая компания A",
    ticker: "SYNA",
    instrument_type: "share",
    observed_at: stamp,
    status: "partial",
    metrics: [{
      key: "price_earnings_ttm",
      label: "P/E за 12 месяцев",
      value: "11.25",
      unit: "×",
      period: "Последние 12 месяцев",
      source_url: "https://developer.tbank.ru/invest/api/instruments-service"
    }],
    missing_requirements: ["roe_percent"],
    limitations: ["Изолированные данные теста"]
  });
  if (path.startsWith("/api/market/instruments/")) return sendJSON(response, {
    instrument_uid: "synthetic-a",
    period: url.searchParams.get("period"),
    source: "Synthetic exchange",
    observed_at: stamp,
    last_price: "250.25",
    quote_time: stamp,
    quote_status: "fresh",
    trading_status: "SECURITY_TRADING_STATUS_NORMAL_TRADING",
    candles: [{
      time: day(3),
      open: "245",
      high: "249",
      low: "242",
      close: "248",
      volume_lots: 10
    }, {
      time: day(2),
      open: "248",
      high: "251",
      low: "247",
      close: "250.25",
      volume_lots: 15
    }]
  });
  if (path === "/api/broker/tbank/instruments/search") return sendJSON(response, {
    items: [{
      uid: "synthetic-a",
      name: "Тестовая компания A",
      ticker: "SYNA",
      instrument_type: "share"
    }]
  });
  if (path === "/api/broker/tbank/analysis") return sendJSON(response, {
    analysis: {
      security_count: 2,
      valued_security_count: 2,
      sector_coverage_percent: "100",
      observations: []
    },
    refreshed_at: stamp
  });
  if (path === "/api/broker/tbank") {
    if (method === "DELETE") fixture.connected = false;
    if (method === "PUT") fixture.connected = true;
    return sendJSON(response, connection(fixture));
  }
  if (path === "/api/broker/tbank/accounts") return sendJSON(response, {
    accounts: [{
      id: "synthetic-account",
      name: "Тестовый счёт",
      type: "broker",
      status: "open"
    }]
  });
  if (path === "/api/goals" && method === "GET") return sendJSON(response, {
    items: fixture.goals
  });
  if (path === "/api/goals" && method === "POST") {
    const goal = {
      id: `synthetic-goal-${fixture.goals.length + 1}`,
      version: 1,
      ...body.document,
      created_at: stamp,
      progress: {
        status: "available",
        amount_rub: body.document.manual_amount_rub,
        percent: "10",
        remaining_rub: "900",
        source: "manual",
        as_of: stamp
      }
    };
    fixture.goals.push(goal);
    return sendJSON(response, goal);
  }
  if (path.startsWith("/api/goals/")) {
    const id = path.split("/").at(-1);
    const current = fixture.goals.find(goal => goal.id === id);
    if (!current || body.expected_version !== current.version) return sendJSON(response, {
      detail: "settings_version_conflict"
    }, 409);
    if (method === "DELETE") {
      fixture.goals = fixture.goals.filter(goal => goal.id !== id);
      return sendJSON(response, {
        deleted: true
      });
    }
    Object.assign(current, body.document, {
      version: current.version + 1
    });
    return sendJSON(response, current);
  }
  if (path === "/api/events" || path === "/api/events/read") {
    if (method === "POST") fixture.events.filter(item => body.ids.includes(item.id)).forEach(item => {
      item.read_at = stamp;
    });
    return sendJSON(response, eventDTO(fixture));
  }
  if (path === "/api/assistant/status") return sendJSON(response, {
    configured: false,
    provider: "ollama",
    model: null,
    context_supported: true,
    max_message_length: 4000
  });
  if (path === "/api/auth/logout" || path === "/api/account/delete") {
    fixture.mode = "guest";
    response.statusCode = 204;
    return response.end();
  }
  return sendJSON(response, {
    detail: "synthetic_route_missing"
  }, 404);
};
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
    if (url.pathname.startsWith("/api/")) {
      const referrer = new URL(request.headers.referer || "http://127.0.0.1/?case=guest");
      const key = referrer.searchParams.get("case") || "guest";
      if (!fixtures.has(key)) fixtures.set(key, makeFixture(key.startsWith("guest") ? "guest" : "signed"));
      const parts = [];
      for await (const part of request) parts.push(part);
      const body = parts.length ? JSON.parse(Buffer.concat(parts).toString()) : null;
      return await routeAPI(request, response, url, fixtures.get(key), body);
    }
    if (url.pathname === "/version.js") {
      response.setHeader("Content-Type", "text/javascript");
      response.end(`window.OMNICIO_RELEASE=${JSON.stringify({
        version,
        build
      })};`);
      return;
    }
    let path = url.pathname;
    if (path === "/") path = "/index.html";
    let file = join(root, "web", path.replace(/^\/assets\//, "").replace(/^\//, ""));
    if (path.startsWith("/assets/brand/")) file = join(root, "assets", "brand", "web", path.split("/").at(-1));
    if (!file.startsWith(root) || !existsSync(file)) {
      response.statusCode = 404;
      return response.end();
    }
    response.setHeader("Content-Type", {
      ".html": "text/html; charset=utf-8",
      ".js": "text/javascript",
      ".css": "text/css",
      ".png": "image/png",
      ".webmanifest": "application/manifest+json"
    }[extname(file)] || "application/octet-stream");
    const raw = readFileSync(file);
    response.end([".html", ".js", ".css"].includes(extname(file)) ? raw.toString().replaceAll("__OMNICIO_BUILD__", build).replaceAll("__OMNICIO_VERSION__", version) : raw);
  } catch (error) {
    response.statusCode = 500;
    response.end("Synthetic test server failure");
    console.error(error.message);
  }
});
const displayContracts = () => {
  const context = vm.createContext({
    window: {},
    Intl,
    Date,
    URL
  });
  vm.runInContext(readFileSync(join(root, "web", "workspace.js"), "utf8"), context);
  const ui = context.window.OmniUI;
  for (const value of [null, undefined, "", "  ", false, [], {}, "NaN", Infinity]) assert.equal(ui.number(value), null, "Unknown and non-finite values remain unknown");
  assert.equal(ui.money(null), "—");
  assert.equal(ui.percent(null), "—");
  assert.equal(ui.external("javascript:alert(1)"), null);
  assert.equal(ui.external("https://user:password@example.test/"), null);
  assert.equal(ui.external("https://example.test/source"), "https://example.test/source");
  assert.ok(ui.escape('<img src=x onerror="alert(1)">').startsWith("&lt;img"), "Source text is escaped before entering markup");
  assert.ok(!ui.chart([{
    captured_at: stamp,
    nav_rub: "12345"
  }]).includes("chart-path"), "A single observation cannot become a fabricated time series");
  ui.setPrivacy(true);
  assert.ok(!ui.chart([{
    captured_at: day(1),
    nav_rub: "12345"
  }, {
    captured_at: stamp,
    nav_rub: "15000"
  }]).includes("12345"), "Masked balances cannot leak through chart markup");
  ui.setPrivacy(false);
  ui.setLocale("en");
  assert.equal(ui.format("1234.56"), "1,234.56", "Locale setting has a real consumer");
  console.log("PASS display contracts: unknown values, source escaping, privacy, real-series requirements and locale");
};
const workerContract = async () => {
  const handlers = new Map();
  const tasks = [];
  const cached = [];
  let activated = 0;
  const origin = "https://example.test";
  globalThis.self = {
    location: {
      origin
    },
    addEventListener: (name, handler) => handlers.set(name, handler),
    skipWaiting: async () => {
      activated += 1;
    }
  };
  globalThis.caches = {
    open: async () => ({
      addAll: async paths => cached.push(...paths)
    })
  };
  try {
    require("../web/sw.js");
    handlers.get("install")({
      waitUntil: task => tasks.push(task)
    });
    await Promise.all(tasks);
    assert.ok(cached.includes("/offline.html?build=__OMNICIO_BUILD__"));
    assert.ok(cached.every(path => /^\/(offline\.html|assets\/(app\.css|app\.js|workspace\.js))\?build=__OMNICIO_BUILD__$/.test(path)), "Private content never enters the cache allowlist");
    let intercepted = 0;
    for (const path of ["/api/me", "/api/workspace", "/api/preferences", "/api/goals", "/api/assistant/messages", "/api/broker/tbank/portfolio", "/health/ready"]) {
      for (const method of ["GET", "POST"]) handlers.get("fetch")({
        request: {
          url: origin + path,
          method,
          mode: "navigate"
        },
        respondWith: () => {
          intercepted += 1;
        }
      });
    }
    assert.equal(intercepted, 0, "Worker must not intercept private reads, mutations or health checks");
    handlers.get("message")({
      origin: "https://untrusted.invalid",
      data: {
        type: "ACTIVATE_UPDATE"
      },
      waitUntil: task => tasks.push(task)
    });
    assert.equal(activated, 0);
    handlers.get("message")({
      origin,
      data: {
        type: "ACTIVATE_UPDATE"
      },
      waitUntil: task => tasks.push(task)
    });
    await Promise.all(tasks);
    assert.equal(activated, 1);
    console.log("PASS service worker: private-cache isolation and origin checks");
  } finally {
    delete globalThis.self;
    delete globalThis.caches;
  }
};
const protocolClient = async url => {
  const socket = new WebSocket(url);
  const pending = new Map();
  let sequence = 0;
  await new Promise((done, reject) => {
    socket.addEventListener("open", done, {
      once: true
    });
    socket.addEventListener("error", reject, {
      once: true
    });
  });
  socket.addEventListener("message", ({
    data
  }) => {
    const message = JSON.parse(data);
    const waiter = pending.get(message.id);
    if (!waiter) return;
    pending.delete(message.id);
    clearTimeout(waiter.timer);
    if (message.error) waiter.reject(new Error(JSON.stringify(message.error)));else waiter.done(message.result);
  });
  return {
    send(method, params = {}, sessionId) {
      return new Promise((done, reject) => {
        const id = ++sequence;
        const timer = setTimeout(() => {
          pending.delete(id);
          reject(new Error("CDP timeout: " + method));
        }, 15000);
        pending.set(id, {
          done,
          reject,
          timer
        });
        socket.send(JSON.stringify({
          id,
          method,
          params,
          sessionId
        }));
      });
    },
    close: () => socket.close()
  };
};
const runBrowser = async base => {
  const candidates = [process.env.OMNICIO_TEST_BROWSER, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser", "C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe"].filter(Boolean);
  const executable = candidates.find(existsSync);
  assert.ok(executable, "Browser QA requires Chrome/Chromium. Set OMNICIO_TEST_BROWSER; the test cannot silently skip visual or session checks.");
  assert.equal(typeof WebSocket, "function", "Node 22+ is required");
  const profile = mkdtempSync(join(process.env.TMPDIR || tmpdir(), "omnicio-browser-smoke-"));
  const child = spawn(executable, ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-background-networking", "--no-first-run", "--no-default-browser-check", "--password-store=basic", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], {
    stdio: ["ignore", "ignore", "pipe"]
  });
  let websocket = "";
  let exited = false;
  child.stderr.on("data", chunk => {
    const match = /DevTools listening on (ws:\/\/[^\s]+)/.exec(String(chunk));
    if (match) websocket = match[1];
  });
  child.on("exit", () => {
    exited = true;
  });
  child.on("error", error => {
    console.error(error.message);
    exited = true;
  });
  let client;
  try {
    await until(() => websocket || exited, "Chromium start");
    assert.ok(websocket, "Chromium must expose its debugging endpoint");
    client = await protocolClient(websocket);
    const target = await client.send("Target.createTarget", {
      url: "about:blank"
    });
    const {
      sessionId
    } = await client.send("Target.attachToTarget", {
      targetId: target.targetId,
      flatten: true
    });
    const send = (method, params = {}) => client.send(method, params, sessionId);
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Page.addScriptToEvaluateOnNewDocument", {
      source: 'window.__browserErrors=[];window.__cspViolations=[];addEventListener("error",e=>window.__browserErrors.push(e.message));addEventListener("unhandledrejection",e=>window.__browserErrors.push(String(e.reason)));addEventListener("securitypolicyviolation",e=>window.__cspViolations.push(e.effectiveDirective));'
    });
    const evaluate = async expression => {
      const result = await send("Runtime.evaluate", {
        expression,
        returnByValue: true,
        awaitPromise: true
      });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text + ": " + (result.exceptionDetails.exception?.description || ""));
      return result.result.value;
    };
    const click = selector => evaluate(`(() => {
      const element=document.querySelector(${JSON.stringify(selector)});
      if(!element || element.disabled)throw new Error('Control unavailable: '+${JSON.stringify(selector)});
      if(element.closest('#app-sidebar')?.inert)document.querySelector('#app-menu-toggle').click();
      element.click();
    })()`);
    const wait = (expression, label) => until(() => evaluate(expression), label || expression);
    const fieldValue = (form, name, value) => evaluate(`(() => {const input=document.querySelector(${JSON.stringify(form)}).elements[${JSON.stringify(name)}];input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    const checkLayout = async label => {
      const data = await evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,errors:window.__browserErrors,csp:window.__cspViolations})');
      assert.ok(data.scroll <= data.width + 1 && data.body <= data.width + 1, `${label}: horizontal overflow ${JSON.stringify(data)}`);
      assert.deepEqual(data.errors, [], label + ": runtime errors");
      assert.deepEqual(data.csp, [], label + ": production Content Security Policy");
    };
    const screenshot = async name => {
      const result = await send("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false
      });
      writeFileSync(join(artifacts, name), Buffer.from(result.data, "base64"));
    };
    const widths = [1440, 1366, 768, 390, 320];
    for (const round of [1, 2]) {
      for (const width of widths) {
        await send("Emulation.setDeviceMetricsOverride", {
          width,
          height: 900,
          deviceScaleFactor: 1,
          mobile: width < 680
        });
        const guestKey = `guest-${round}-${width}`;
        await send("Page.navigate", {
          url: `${base}?case=${guestKey}`
        });
        await wait('document.querySelectorAll(".public-strategy-card").length===10', "Public canonical catalog");
        await checkLayout(`public ${round}/${width}`);
        await screenshot(`public-${round}-${width}.png`);
        await click('[data-action="tour"]');
        await wait('!document.querySelector("#app-shell").hidden', "Product tour");
        assert.equal(await evaluate('document.querySelectorAll("#sidebar-nav a").length'), 10);
        assert.equal(await evaluate('document.querySelectorAll("#mobile-nav a").length'), 4);
        await checkLayout(`tour ${round}/${width}`);
        assert.equal(fixtures.get(guestKey).requests.filter(item => item.path.startsWith("/api/broker/") || !["GET", "HEAD"].includes(item.method)).length, 0, "Tour cannot read private broker data or mutate anything");
        if (round === 2) {
          await click('#tour-notice [data-action="login"]');
          await checkLayout(`auth ${round}/${width}`);
          await screenshot(`auth-${round}-${width}.png`);
          assert.equal(await evaluate('document.querySelectorAll("#auth-form input[required]").length'), 4, "Both OAuth providers require the four consent choices");
          assert.equal(await evaluate('document.querySelectorAll("#auth-form input[type=password],#auth-form input[type=email]").length'), 0, "Authentication cannot present an unsupported password flow");
          await evaluate('for(const input of document.querySelectorAll("#auth-form input"))input.checked=true');
          await click("#tid-login");
          await wait('document.querySelector("#auth-message").textContent.includes("не прошёл проверку")', "OAuth redirect allowlist");
          assert.ok((await evaluate("location.href")).startsWith(base), "Untrusted provider URL cannot navigate the page");
          await click('#auth-dialog [data-close-dialog]');
        }
        const key = `signed-${round}-${width}`;
        fixtures.set(key, makeFixture("signed"));
        const fixture = fixtures.get(key);
        await send("Page.navigate", {
          url: `${base}?case=${key}`
        });
        await wait('!document.querySelector("#app-shell").hidden && document.querySelector("#profile-name").textContent.includes("Тестовый") && document.querySelector("#view-home .asset-table")', "Authenticated dashboard");
        await checkLayout(`dashboard ${round}/${width}`);
        await screenshot(`dashboard-${round}-${width}.png`);
        assert.equal(await evaluate('document.querySelector("#view-home .metric-card .main-value").textContent'), "—", "Unknown return must not become zero or NAV-growth percentage");
        assert.ok(fixture.requests.filter(item => item.path === "/api/workspace").every(item => item.profile === fixture.user), "Private data requests carry the viewed server profile precondition");
        if (width <= 960) {
          await click("#app-menu-toggle");
          await wait('document.querySelector("#app-sidebar").dataset.open==="true"', "Mobile drawer");
          assert.equal(await evaluate('document.querySelector(".app-main").inert'), true, "Drawer traps interaction outside its surface");
          await send("Input.dispatchKeyEvent", {
            type: "keyDown",
            key: "Escape",
            code: "Escape",
            windowsVirtualKeyCode: 27
          });
          await wait('document.querySelector("#drawer-backdrop").hidden', "Drawer Escape");
          assert.equal(await evaluate('document.activeElement.id'), "app-menu-toggle", "Drawer restores focus");
        }
        for (const view of ["portfolio", "market", "strategies", "goals", "analytics", "events", "profile", "settings", "assistant"]) {
          await click(`#sidebar-nav [data-route="${view}"]`);
          await wait(`!document.querySelector('#view-${view}').hidden && document.querySelector('#view-${view}').textContent.length>20`, view);
          if (view === "strategies") await wait('document.querySelector("#strategy-form") && !document.querySelector("#view-strategies .loading-panel")', "Strategy loaded");
          if (view === "settings") await wait('document.querySelector("#preferences-form")', "Server preferences loaded");
          await delay(80);
          await checkLayout(`${view} ${round}/${width}`);
          if (width <= 390) await screenshot(`${view}-${round}-${width}.png`);
        }
        assert.equal(await evaluate('document.querySelector("#assistant-form textarea").disabled'), true, "Disconnected AI cannot fabricate answers");
        await click('#sidebar-nav [data-route="market"]');
        await fieldValue("#global-search-form", "q", "SYNA");
        await evaluate('document.querySelector("#global-search-form").requestSubmit()');
        await wait('document.querySelector("#view-search .search-result")', "Real search response");
        await click('#view-search [data-asset]');
        await wait('document.querySelector("#view-asset .chart-svg")', "Asset chart");
        await click('#view-asset [data-asset-tab="metrics"]');
        assert.ok(await evaluate('document.querySelector("#view-asset .asset-tab-content").textContent.includes("Максимум периода")'));
        await click('#view-asset [data-asset-tab="chart"]');
        await click('#view-asset [data-period="all"]');
        await wait('document.querySelector("#view-asset .chart-svg") && !document.querySelector("#view-asset .loading-panel")', "All available market history");
        assert.ok(fixture.requests.some(item => item.path.startsWith("/api/market/instruments/")), "Asset tabs consume real API contracts");
        await evaluate('document.querySelector("#view-asset .chart-svg").focus()');
        const before = await evaluate('document.querySelector("#view-asset .chart-readout").textContent');
        await send("Input.dispatchKeyEvent", {
          type: "keyDown",
          key: "Home",
          code: "Home",
          windowsVirtualKeyCode: 36
        });
        assert.notEqual(await evaluate('document.querySelector("#view-asset .chart-readout").textContent'), before, "Keyboard chart inspection changes the selected real observation");
        await checkLayout(`asset ${round}/${width}`);
        await screenshot(`asset-${round}-${width}.png`);
        await click('#view-asset [data-watch]');
        await until(() => fixture.prefs.document.watchlist.length === 1, "Persistent watchlist");
        await wait('document.querySelector("#view-asset [data-watch]").getAttribute("aria-pressed")==="true"', "Saved favorite");
        await click('#sidebar-nav [data-route="strategies"]');
        await wait('document.querySelector("#strategy-form")', "Strategy form");
        fixture.mutationDelay = 150;
        await click('[data-select-strategy="conservative"]');
        await until(() => fixture.selection.document.base_preset_id === "conservative", "Persist strategy selection");
        await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved"', "Strategy saved acknowledgement");
        assert.equal(fixture.selection.document.profile.reserve_rub, "123456789.12345678", "Selecting a preset preserves exact private amounts");
        const reserveControl = '[data-step-field="strategy.profile.reserve_rub"][data-step-direction="1"]';
        await click(reserveControl);
        await until(() => fixture.selection.document.profile.reserve_rub === "123457789.12345678", "Exact decimal step");
        await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved"', "Saved custom parameters");
        assert.equal(fixture.selection.document.customized, true);
        await screenshot(`strategies-${round}-${width}.png`);
        assert.equal(fixture.maxActiveWrites, 1, "Versioned autosave uses a single in-flight mutation");
        await click('#sidebar-nav [data-route="goals"]');
        await click('#view-goals [data-action="goal-create"]');
        await fieldValue("#goal-form", "title", "Тестовая цель");
        await fieldValue("#goal-form", "target_amount_rub", "1000");
        await fieldValue("#goal-form", "progress_source", "manual");
        await fieldValue("#goal-form", "manual_amount_rub", "100");
        await click('#goal-form [type="submit"]');
        await until(() => fixture.goals.length === 1, "Create goal on server");
        await wait('!document.querySelector("#workspace-dialog").open', "Goal saved");
        assert.equal(fixture.goals[0].manual_amount_rub, "100");
        await click('#view-goals [data-goal-edit]');
        await fieldValue("#goal-form", "title", "Изменённая тестовая цель");
        await click('#goal-form [type="submit"]');
        await until(() => fixture.goals[0].version === 2, "Versioned goal update");
        await wait('!document.querySelector("#workspace-dialog").open', "Goal updated");
        await click('#view-goals [data-goal-delete]');
        await click('[data-goal-delete-confirm]');
        await until(() => fixture.goals.length === 0, "Goal deletion");
        await click('#sidebar-nav [data-route="events"]');
        await click('#view-events [data-action="events-read-all"]');
        await until(() => fixture.events.every(item => item.read_at), "Durable read receipts");
        await click('#sidebar-nav [data-route="settings"]');
        await wait('document.querySelector("#preferences-form")', "Preferences form");
        await fieldValue("#preferences-form", "theme", "light");
        await click('#preferences-form [type="submit"]');
        await until(() => fixture.prefs.document.theme === "light", "Server theme setting");
        await wait('document.documentElement.dataset.theme==="light"', "Applied light theme");
        await checkLayout(`settings-light ${round}/${width}`);
        if (round === 2) {
          fixture.lostAck = true;
          await fieldValue("#preferences-form", "theme", "dark");
          await click('#preferences-form [type="submit"]');
          await wait('document.querySelector("[data-save-status=prefs]").dataset.state==="saved" && document.documentElement.dataset.theme==="dark"', "Lost acknowledgement reconciled before Saved");
          assert.equal(fixture.maxActiveWrites, 1);
          fixture.conflict = true;
          await fieldValue("#preferences-form", "locale", "en");
          await click('#preferences-form [type="submit"]');
          await wait('document.querySelector("[data-save-status=prefs]").dataset.state==="conflict"', "Version conflict stays explicit");
          assert.equal(fixture.prefs.document.locale, "ru", "Conflict cannot overwrite the server");
          fixture.conflict = false;
          await click('[data-action="prefs-reload"]');
          await click('[data-action="prefs-discard"]');
          await wait('document.querySelector("[data-save-status=prefs]").dataset.state==="saved"', "Explicit conflict resolution");
          fixture.holdWorkspace = true;
          await click('#view-settings [data-action="refresh"]');
          await until(() => fixture.heldWorkspace.length > 0, "In-flight old-account response");
          fixture.user = "000000999";
          await evaluate('window.dispatchEvent(new Event("focus"))');
          await wait('document.querySelector("#session-dialog").open && document.querySelector("#app-shell").hidden', "Tenant change clears private views");
          fixture.heldWorkspace.splice(0).forEach(release => release());
          fixture.holdWorkspace = false;
          await delay(250);
          assert.equal(await evaluate('document.querySelector("#main-content").textContent.includes("Тестовая компания")'), false, "Late old-profile response cannot restore data");
          assert.equal(await evaluate('document.querySelector("#profile-name").textContent'), "Мой профиль");
        }
        const browserStorage = await evaluate('({local:Object.keys(localStorage),session:Object.keys(sessionStorage)})');
        assert.deepEqual(browserStorage.session, [], "Private session data never enters sessionStorage");
        assert.ok(browserStorage.local.every(key => key === "omnicio-theme"), "Only a display theme may enter localStorage");
        assert.deepEqual(await evaluate("window.__browserErrors"), [], "No browser errors after workflows");
        console.log(`PASS round ${round}, ${width}px: layout, navigation, search, real charts, strategies, goals, events, settings, session isolation`);
      }
    }
    const failureKey = "signed-load-failure";
    const failure = makeFixture("signed");
    failure.failPreferences = true;
    failure.failWorkspace = true;
    failure.failStrategyLoad = true;
    fixtures.set(failureKey, failure);
    await send("Page.navigate", {
      url: `${base}?case=${failureKey}#settings`
    });
    await wait('document.querySelector("#view-settings .notice.error")', "Failed initial settings load");
    assert.equal(await evaluate('Boolean(document.querySelector("#preferences-form"))'), false, "Failed load cannot enable a default settings writer");
    await click('#sidebar-nav [data-route="strategies"]');
    await wait('document.querySelector(".strategy-option")', "Catalog during saved-draft failure");
    await click('[data-select-strategy="balanced"]');
    await delay(750);
    assert.equal(failure.requests.filter(item => !["GET", "HEAD"].includes(item.method)).length, 0, "Unknown saved settings cannot be overwritten by selecting a preset");
    console.log("PASS failure states: no defaults saved over failed loads");
  } finally {
    if (client) {
      try {
        await client.send("Browser.close");
      } catch {/* Process exit also closes the browser. */}
      client.close();
    }
    if (!exited) child.kill();
    for (let attempt = 0; attempt < 30 && !exited; attempt += 1) await delay(100);
    try {
      rmSync(profile, {
        recursive: true,
        force: true,
        maxRetries: 12,
        retryDelay: 250
      });
    } catch (error) {
      console.warn("Temporary Chrome profile cleanup could not finish:", error.code || error.message);
    }
  }
};
(async () => {
  try {
    displayContracts();
    await workerContract();
    await new Promise(done => server.listen(0, "127.0.0.1", done));
    await runBrowser(`http://127.0.0.1:${server.address().port}/`);
  } catch (error) {
    console.error(error.stack || error);
    process.exitCode = 1;
  } finally {
    server.closeAllConnections();
    server.close();
  }
})();
