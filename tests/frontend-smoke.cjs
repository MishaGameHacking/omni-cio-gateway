/* Observable browser contracts, served by an isolated synthetic API. No production requests. */
"use strict";

const assert = require("node:assert/strict");
const vm = require("node:vm");
const {
  createHash
} = require("node:crypto");
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
    tidEnabled: true,
    vkidEnabled: true,
    user: "000000123",
    prefs: defaultPreferences(),
    selection: {
      version: 1,
      document: preset,
      custom_document: null,
      updated_at: stamp
    },
    goals: [],
    goalSequence: 0,
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
    holdPreferences: false,
    heldPreferences: [],
    holdWorkspace: false,
    heldWorkspace: [],
    holdGoals: false,
    heldGoals: [],
    failGoals: false,
    goalDeleteNoContent: false,
    goalWriteConsentAfterCommit: false,
    goalPutConsentAfterCommit: false,
    holdGoalWriteAck: false,
    heldGoalWrites: [],
    lateGoalAck: null,
    refreshQueued: false,
    refreshPollsRemaining: 0,
    refreshStatus: {
      status: "idle",
      job_id: null,
      requested_at: null,
      started_at: null,
      finished_at: null,
      observed_at: stamp,
      snapshot_saved: false,
      history_status: null,
      history_pages: 0,
      can_refresh: true,
      retry_after_seconds: 0,
      cooldown_until: null,
      reason: null
    },
    executions: [],
    mandate: null,
    recoveryLostAck: false,
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
const testApiHandlers = [{
  matches: ({
    path
  }) => path === "/api/auth/config",
  run: serveTestAuthConfig
}, {
  matches: ({
    path
  }) => path === "/api/strategy/catalog",
  run: serveTestStrategyCatalog
}, {
  matches: ({
    path
  }) => path === "/api/public/market-reference",
  run: serveTestPublicMarketReference
}, {
  matches: ({
    path
  }) => path === "/api/public/news",
  run: serveTestPublicNews
}, {
  matches: ({
    path
  }) => /^\/api\/auth\/(tid|vkid)\/start$/.test(path),
  run: serveTestGuard5
}, {
  matches: ({
    fixture
  }) => fixture.mode === "guest",
  run: serveTestGuard6
}, {
  matches: ({
    request,
    fixture
  }) => request.headers["x-omnicio-profile"] && request.headers["x-omnicio-profile"] !== fixture.user,
  run: serveTestGuard7
}, {
  matches: ({
    method,
    request,
    fixture
  }) => !["GET", "HEAD"].includes(method) && (request.headers["x-omnicio-profile"] !== fixture.user || request.headers.origin !== `http://${request.headers.host}`),
  run: serveTestGuard8
}, {
  matches: ({
    path
  }) => path === "/api/me",
  run: serveTestMe
}, {
  matches: ({
    path
  }) => path === "/api/auth/identities",
  run: serveTestAuthIdentities
}, {
  matches: ({
    path
  }) => path === "/api/workspace",
  run: serveTestWorkspace
}, {
  matches: ({
    path
  }) => path === "/api/workspace/refresh",
  run: serveTestRefresh
}, {
  matches: ({
    path
  }) => path.startsWith("/api/portfolio/executions"),
  run: serveTestExecutions
}, {
  matches: ({
    path
  }) => path === "/api/portfolio/live-execution/mandate",
  run: serveTestMandate
}, {
  matches: ({
    path
  }) => path === "/api/preferences" || path === "/api/profile/strategy",
  run: serveTestPreferences
}, {
  matches: ({
    path
  }) => path === "/api/profile/investment",
  run: serveTestProfileInvestment
}, {
  matches: ({
    path
  }) => path === "/api/profile/balancing",
  run: serveTestProfileBalancing
}, {
  matches: ({
    path
  }) => path === "/api/profile/strategy/account-assessment",
  run: serveTestProfileStrategyAccountAssessment
}, {
  matches: ({
    path
  }) => path === "/api/profile/strategy/research",
  run: serveTestProfileStrategyResearch
}, {
  matches: ({
    path
  }) => path === "/api/portfolio/visualization",
  run: serveTestPortfolioVisualization
}, {
  matches: ({
    path
  }) => path.startsWith("/api/portfolio/instruments/"),
  run: serveTestPortfolioInstruments
}, {
  matches: ({
    path
  }) => path.startsWith("/api/market/instruments/") && path.endsWith("/facts"),
  run: serveTestMarketInstruments
}, {
  matches: ({
    path
  }) => path.startsWith("/api/market/instruments/"),
  run: serveTestMarketInstruments2
}, {
  matches: ({
    path
  }) => path === "/api/broker/tbank/instruments/search",
  run: serveTestBrokerTbankInstrumentsSearch
}, {
  matches: ({
    path
  }) => path === "/api/broker/tbank/analysis",
  run: serveTestBrokerTbankAnalysis
}, {
  matches: ({
    path
  }) => path === "/api/broker/tbank",
  run: serveTestBrokerTbank
}, {
  matches: ({
    path
  }) => path === "/api/broker/tbank/accounts",
  run: serveTestBrokerTbankAccounts
}, {
  matches: ({
    path,
    method
  }) => path === "/api/goals" && method === "GET",
  run: serveTestGoals
}, {
  matches: ({
    path,
    method
  }) => path === "/api/goals" && method === "POST",
  run: serveTestGoals2
}, {
  matches: ({
    path
  }) => path.startsWith("/api/goals/"),
  run: serveTestGoals3
}, {
  matches: ({
    path
  }) => path === "/api/events" || path === "/api/events/read",
  run: serveTestEvents
}, {
  matches: ({
    path
  }) => path === "/api/assistant/status",
  run: serveTestAssistantStatus
}, {
  matches: ({
    path
  }) => path === "/api/auth/logout" || path === "/api/account/delete",
  run: serveTestAuthLogout
}];
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
  const context = {
    request,
    response,
    url,
    fixture,
    body,
    path,
    method
  };
  const handler = testApiHandlers.find(candidate => candidate.matches(context));
  if (handler) {
    return handler.run(context);
  }
  return sendJSON(response, {
    detail: "synthetic_route_missing"
  }, 404);
};
const serveTestApiRequest = async (request, response, url) => {
  const referrer = new URL(request.headers.referer || "http://127.0.0.1/?case=guest");
  const key = referrer.searchParams.get("case") || "guest";
  if (!fixtures.has(key)) fixtures.set(key, makeFixture(key.startsWith("guest") ? "guest" : "signed"));
  const parts = [];
  for await (const part of request) parts.push(part);
  const body = parts.length ? JSON.parse(Buffer.concat(parts).toString()) : null;
  return await routeAPI(request, response, url, fixtures.get(key), body);
};
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
    if (url.pathname.startsWith("/api/")) return await serveTestApiRequest(request, response, url);
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
  goalVersionContracts(ui);
  chartAxisContracts(ui);
  viewportSizeContracts();
  console.log("PASS display contracts: unknown values, source escaping, privacy, real-series requirements and locale");
};
function goalVersionContracts(ui) {
  const known = [{
    id: "goal-a",
    version: 3,
    title: "Актуальная версия"
  }];
  const stale = [{
    id: "goal-a",
    version: 2,
    title: "Старый снимок"
  }];
  const deleted = new Set();
  const merged = ui.mergeGoals(stale, known, deleted);
  assert.equal(merged[0].version, 3, "Concurrent workspace and goal reads cannot lower a known record version");
  assert.equal(merged[0].title, "Актуальная версия", "The newer server document remains authoritative");
  assert.equal(stale[0].version, 2, "Reconciliation does not mutate an earlier server response");
  assert.equal(ui.mergeGoals([{
    id: "goal-a",
    version: 4
  }], known, deleted)[0].version, 4, "A higher server version replaces the previous document");
  assert.equal(ui.mergeGoals([], known, deleted).length, 0, "An empty server list is an authoritative empty list");
  deleted.add("goal-a");
  assert.equal(ui.mergeGoals(stale, known, deleted).length, 0, "An acknowledged deletion cannot be restored by a delayed list");
  assert.equal(ui.mergeGoals([{
    id: "goal-b",
    version: 1
  }], known, deleted)[0].id, "goal-b", "A tombstone cannot hide another goal");
  deleted.clear();
  assert.equal(ui.mergeGoals(stale, [], deleted)[0].version, 2, "A new session has no version or deletion authority from the previous session");
  console.log("PASS goal version contracts: monotonic records, immutable reads, empty lists and session tombstones");
}
function chartAxisContracts(ui) {
  const rows = [{
    captured_at: day(2),
    nav_rub: "80.12"
  }, {
    captured_at: stamp,
    nav_rub: "80.16"
  }];
  const markup = ui.chart(rows);
  const labels = [...markup.matchAll(/<span class="chart-axis"[^>]*>([^<]+)<\/span>/g)].map(match => match[1]);
  assert.equal(labels.length, 5, "Full charts have three value labels and two date labels");
  assert.equal(new Set(labels.slice(0, 3)).size, 3, "A narrow nonzero range retains three distinguishable value ticks");
  assert.equal(/<text\b/.test(markup), false, "Axis text cannot be stretched by the SVG viewBox");
  assert.equal(ui.chart(rows, {
    compact: true
  }).includes('class="chart-axis"'), false, "Compact charts retain their unlabelled layout");
  console.log("PASS chart axes: native labels, narrow-range precision and compact layout");
}
const cssRule = (css, selector) => {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = new RegExp(escaped + "\\s*\\{([^{}]*)\\}").exec(css);
  assert.ok(match, "Style rule exists: " + selector);
  return Object.fromEntries([...match[1].matchAll(/([a-z-]+)\s*:\s*([^;\n}]+)/g)].map(item => [item[1], item[2].trim()]));
};
const relativeLuminance = color => {
  let hex = color.replace("#", "");
  if (hex.length === 3) hex = [...hex].map(digit => digit + digit).join("");
  const linear = [0, 2, 4].map(index => {
    const channel = Number.parseInt(hex.slice(index, index + 2), 16) / 255;
    return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
  });
  return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2];
};
const assertTextContrast = (foreground, background, label) => {
  const values = [relativeLuminance(foreground), relativeLuminance(background)];
  const ratio = (Math.max(...values) + .05) / (Math.min(...values) + .05);
  assert.ok(ratio >= 4.5, label + ": normal text contrast " + ratio.toFixed(2) + ":1 must reach 4.5:1");
};
const styleContracts = () => {
  const css = readFileSync(join(root, "web", "app.css"), "utf8");
  const declared = new Set([...css.matchAll(/(--[\w-]+)\s*:/g)].map(item => item[1]));
  for (const reference of css.matchAll(/var\((--[\w-]+)(,)?/g)) assert.ok(declared.has(reference[1]) || reference[2], "CSS custom property must exist or have a fallback: " + reference[1]);
  for (const selector of [":root", ":root[data-theme=light]"]) {
    const palette = cssRule(css, selector);
    for (const text of ["--text", "--muted", "--subtle", "--blue-light", "--green", "--red", "--purple", "--gold"]) {
      for (const surface of ["--bg", "--panel", "--panel-deep", "--panel-hover"]) assertTextContrast(palette[text], palette[surface], selector + " " + text + " on " + surface);
    }
    assertTextContrast("#ffffff", palette["--blue"], selector + " selected controls");
  }
  for (const selector of [".button.primary", ".button.primary:hover", ".vk-provider", ".vk-provider:hover", ".strategy-option .strategy-icon"]) {
    const rule = cssRule(css, selector);
    for (const background of rule.background.match(/#[a-f0-9]{6}\b/gi) || []) assertTextContrast("#ffffff", background, selector);
  }
  const avatar = cssRule(css, ".avatar");
  for (const background of avatar.background.match(/#[a-f0-9]{6}\b/gi)) assertTextContrast(avatar.color, background, "Profile avatar text");
  console.log("PASS style contracts: declared tokens and normal-text contrast in both themes");
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
function captureBrowserLayout() {
  const readableElements = selector => [...document.querySelectorAll(selector)].filter(element => element.getClientRects().length && getComputedStyle(element).visibility !== "hidden").map(element => ({
    label: element.getAttribute("aria-label") || element.name || element.textContent.trim().slice(0, 70),
    fontSize: Number.parseFloat(getComputedStyle(element).fontSize),
    compactAction: element.classList.contains("small-button"),
    rect: element.getBoundingClientRect().toJSON()
  }));
  const elementGeometry = element => {
    const parent = element.offsetParent;
    return {
      rect: element.getBoundingClientRect().toJSON(),
      offsetParent: parent ? {
        tag: parent.tagName,
        id: parent.id,
        className: parent.className,
        rect: parent.getBoundingClientRect().toJSON()
      } : null
    };
  };
  const visibleApp = !document.querySelector("#app-shell").hidden;
  const modal = Boolean(document.querySelector("dialog[open]"));
  const hero = !visibleApp && !modal && innerWidth <= 680 ? {
    required: true,
    rect: document.querySelector(".hero").getBoundingClientRect().toJSON(),
    regions: [
      ["eyebrow", ".hero-copy>.eyebrow"],
      ["heading", "#hero-title"],
      ["lead", ".hero-lead"],
      ["data", ".hero-data"],
      ["actions", ".hero-buttons"],
      ["facts", ".hero-facts"]
    ].map(([name, selector]) => {
      const element = document.querySelector(selector);
      if (!element) return {name, visible: false};
      const style = getComputedStyle(element);
      return {
        name,
        visible: Boolean(element.getClientRects().length) && style.visibility === "visible" && Number(style.opacity) > 0,
        text: element.innerText.trim(),
        fontSize: Number.parseFloat(style.fontSize),
        rect: element.getBoundingClientRect().toJSON()
      };
    })
  } : {required: false};
  const drawer = document.querySelector("#app-sidebar").dataset.open === "true";
  const nav = document.querySelector(visibleApp ? "#mobile-nav" : ".public-mobile-nav");
  const viewport = {
    width: innerWidth,
    height: innerHeight,
    clientWidth: document.documentElement.clientWidth,
    clientHeight: document.documentElement.clientHeight,
    devicePixelRatio,
    visualWidth: visualViewport.width,
    visualHeight: visualViewport.height,
    offsetLeft: visualViewport.offsetLeft,
    offsetTop: visualViewport.offsetTop,
    scale: visualViewport.scale,
    scrollX,
    scrollY
  };
  const links = [...nav.querySelectorAll("a")].map(link => {
    const rect = link.getBoundingClientRect().toJSON();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const hit = document.elementFromPoint(x, y);
    return {
      route: link.getAttribute("href"),
      rect,
      x,
      y,
      hit: link.contains(hit),
      topElement: hit?.id || hit?.className?.baseVal || hit?.className || hit?.tagName || null
    };
  });
  const navStyle = getComputedStyle(nav);
  const navigation = {
    required: innerWidth <= 960 && !modal && !drawer,
    modal,
    drawer,
    rect: nav.getBoundingClientRect().toJSON(),
    style: {
      display: navStyle.display,
      position: navStyle.position,
      visibility: navStyle.visibility,
      opacity: navStyle.opacity,
      zIndex: navStyle.zIndex
    },
    inert: nav.inert,
    links
  };
  const charts = [...document.querySelectorAll('.view:not([hidden]) .chart-plot')].map(plot => {
    const svg = plot.querySelector("svg");
    const axes = [...plot.querySelectorAll(".chart-axis")].map(axis => {
      const style = getComputedStyle(axis);
      return {
        text: axis.textContent,
        html: axis.namespaceURI === "http://www.w3.org/1999/xhtml",
        rect: axis.getBoundingClientRect().toJSON(),
        fontSize: Number.parseFloat(style.fontSize),
        transform: style.transform
      };
    });
    return {
      compact: plot.classList.contains("chart-compact"),
      rect: plot.getBoundingClientRect().toJSON(),
      svg: svg.getBoundingClientRect().toJSON(),
      svgText: svg.querySelectorAll("text").length,
      axes
    };
  });
  const tables = [...document.querySelectorAll('.view:not([hidden]) .table-scroll')].map(container => {
    const style = getComputedStyle(container);
    const table = container.querySelector("table");
    const hiddenHeaders = [...container.querySelectorAll("th .sr-only")].map(header => {
      return {
        text: header.textContent,
        ...elementGeometry(header),
        position: getComputedStyle(header).position,
        contained: container.contains(header.offsetParent)
      };
    });
    return {
      ...elementGeometry(container),
      clientWidth: container.clientWidth,
      scrollWidth: container.scrollWidth,
      scrollLeft: container.scrollLeft,
      position: style.position,
      overflowX: style.overflowX,
      table: elementGeometry(table),
      hiddenHeaders
    };
  });
  return {
    width: innerWidth,
    scroll: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    errors: window.__browserErrors,
    csp: window.__cspViolations,
    viewport,
    readability: {
      menu: readableElements("#sidebar-nav .nav-link"),
      fields: readableElements('.field input:not([type=checkbox]):not([type=range]), .field select, .field textarea, .global-search input, .chat-compose textarea'),
      captions: readableElements(".card-label, .data-footnote, .source-line, .event-meta"),
      actions: readableElements(".button, .icon-button")
    },
    hero,
    navigation,
    charts,
    tables
  };
}
function assertViewportSize(data, label) {
  const expected = data.expectedViewport;
  const viewport = data.viewport;
  assert.ok(Math.abs(viewport.width - expected.width) <= 1, label + ": layout width matches the requested CSS viewport " + JSON.stringify({
    expected,
    viewport
  }));
  assert.ok(Math.abs(viewport.height - expected.height) <= 1, label + ": layout height matches the requested CSS viewport " + JSON.stringify({
    expected,
    viewport
  }));
  const scrollbarWidth = viewport.width - viewport.clientWidth;
  const scrollbarHeight = viewport.height - viewport.clientHeight;
  const effectiveWidth = viewport.visualWidth * viewport.scale;
  const effectiveHeight = viewport.visualHeight * viewport.scale;
  assert.ok(Math.abs(effectiveWidth - (expected.width - scrollbarWidth)) <= 1, label + ": visual and layout widths agree after the native scrollbar");
  assert.ok(Math.abs(effectiveHeight - (expected.height - scrollbarHeight)) <= 1, label + ": visual and layout heights agree after the native scrollbar");
  assert.ok(data.scroll <= viewport.clientWidth + 1 && data.body <= viewport.clientWidth + 1, label + ": document content cannot expand the viewport " + JSON.stringify({
    scroll: data.scroll,
    body: data.body,
    viewport
  }));
}
function viewportSizeContracts() {
  const desktop = {
    expectedViewport: {
      width: 1440,
      height: 900
    },
    viewport: {
      width: 1440,
      height: 900,
      clientWidth: 1425,
      clientHeight: 900,
      visualWidth: 1425,
      visualHeight: 900,
      scale: 1,
      devicePixelRatio: 1
    },
    scroll: 1425,
    body: 1425
  };
  assertViewportSize(desktop, "Native desktop scrollbar");
  assertViewportSize({
    ...desktop,
    viewport: {
      ...desktop.viewport,
      devicePixelRatio: 2
    }
  }, "Device pixels do not change CSS viewport dimensions");
  assertViewportSize({
    ...desktop,
    viewport: {
      ...desktop.viewport,
      visualWidth: 712.5,
      visualHeight: 450,
      scale: 2
    }
  }, "Visual viewport scale remains explicit");
  const expanded = {
    expectedViewport: {
      width: 320,
      height: 900
    },
    viewport: {
      width: 341,
      height: 960,
      clientWidth: 341,
      clientHeight: 960,
      visualWidth: 320,
      visualHeight: 900,
      scale: 1,
      devicePixelRatio: 1
    },
    scroll: 341,
    body: 320
  };
  assert.throws(() => assertViewportSize(expanded, "Observed mobile expansion"), /layout width matches the requested CSS viewport/, "A self-consistent expanded layout cannot pass a requested-width check");
  assert.throws(() => assertViewportSize({
    ...desktop,
    scroll: 1440
  }, "Content overflow behind a native scrollbar"), /document content cannot expand the viewport/);
  console.log("PASS viewport contracts: requested CSS dimensions, native scrollbars, DPR and mobile expansion detection");
}
function assertTableClipping(tables, label) {
  for (const table of tables) {
    for (const header of table.hiddenHeaders) assert.equal(header.contained, true, label + ": hidden table headers belong to their scrolling container " + JSON.stringify(header));
    if (table.scrollWidth > table.clientWidth + 1) assert.ok(["auto", "scroll"].includes(table.overflowX), label + ": wide table content remains locally scrollable");
  }
}
function assertMobileNavigation(data, label) {
  const nav = data.navigation;
  if (!nav.required) return;
  const viewport = data.viewport;
  const bottom = viewport.offsetTop + viewport.visualHeight;
  const right = viewport.offsetLeft + viewport.visualWidth;
  assert.equal(nav.links.length, 4, label + ": four navigation links remain available");
  assert.equal(nav.inert, false, label + ": closed drawer cannot leave the navigation inert");
  assert.ok(Math.abs(nav.rect.bottom - bottom) <= 2, label + ": navigation follows the visible viewport bottom " + JSON.stringify({
    rect: nav.rect,
    viewport
  }));
  for (const link of nav.links) {
    assert.ok(link.rect.width >= 44 && link.rect.height >= 44, label + ": navigation link has a comfortable touch target " + link.route);
    assert.ok(link.x >= viewport.offsetLeft && link.x <= right && link.y >= viewport.offsetTop && link.y <= bottom, label + ": navigation center is visible " + link.route);
    assert.equal(link.hit, true, label + ": navigation center receives interaction " + JSON.stringify(link));
  }
}
function assertReadability(data, label) {
  const minimumMenuSize = data.width <= 960 ? 16 : 15;
  for (const item of data.readability.menu) assert.ok(item.fontSize >= minimumMenuSize, label + ": readable menu " + JSON.stringify(item));
  for (const item of data.readability.fields) assert.ok(item.fontSize >= 16, label + ": readable input without mobile focus zoom " + JSON.stringify(item));
  for (const item of data.readability.captions) assert.ok(item.fontSize >= 12, label + ": readable supporting information " + JSON.stringify(item));
  for (const item of data.readability.actions) {
    const minimumHeight = item.compactAction && data.width > 960 ? 40 : 44;
    assert.ok(item.rect.height >= minimumHeight, label + ": comfortable action height " + JSON.stringify(item));
  }
}
function assertMobileHero(data, label) {
  const hero = data.hero;
  if (!hero.required) return;
  let previous = null;
  for (const region of hero.regions) {
    assert.equal(region.visible, true, label + ": hero content remains visible " + region.name);
    assert.ok(region.text.length > 0 && region.rect.width > 0 && region.rect.height > 0, label + ": hero content has a rendered text region " + JSON.stringify(region));
    assert.ok(region.rect.left >= hero.rect.left - 1 && region.rect.right <= hero.rect.right + 1 && region.rect.top >= hero.rect.top - 1 && region.rect.bottom <= hero.rect.bottom + 1, label + ": hero content stays inside its unclipped section " + JSON.stringify(region));
    if (previous) assert.ok(region.rect.top >= previous.rect.bottom - 1, label + ": mobile hero content follows the preceding region without overlap " + JSON.stringify({previous, region}));
    if (region.name === "lead") assert.ok(region.fontSize >= 16, label + ": the complete hero description remains readable " + JSON.stringify(region));
    previous = region;
  }
}
function assertChartLayout(charts, label) {
  for (const chart of charts) {
    assert.equal(chart.svgText, 0, label + ": SVG geometry cannot scale axis text");
    assert.equal(chart.axes.length, chart.compact ? 0 : 5, label + ": chart axis count");
    if (chart.compact) continue;
    for (const axis of chart.axes) {
      assert.equal(axis.html, true, label + ": native HTML axis");
      assert.ok(axis.fontSize >= 11 && axis.rect.height >= 11, label + ": readable axis type size");
      assert.equal(axis.transform, "none", label + ": axes cannot scale their glyphs");
    }
    const ticks = chart.axes.slice(0, 3);
    assert.equal(new Set(ticks.map(axis => axis.text)).size, 3, label + ": value ticks remain distinguishable");
    for (const [index, axis] of ticks.entries()) {
      const center = axis.rect.top + axis.rect.height / 2;
      const expected = chart.svg.top + chart.svg.height * index / 2;
      assert.ok(Math.abs(center - expected) <= 1.5, label + ": value tick aligns with its grid line");
      assert.ok(axis.rect.left >= chart.svg.right && axis.rect.right <= chart.rect.right + 1, label + ": value axis stays outside the plot and inside its card");
    }
    for (const axis of chart.axes.slice(3)) assert.ok(axis.rect.top >= chart.svg.bottom && axis.rect.left >= chart.svg.left - 1 && axis.rect.right <= chart.svg.right + 1, label + ": date axis stays below its own plot");
  }
}
const screenshotEvidenceNames = new Set(["portfolio-2-320.png", "market-2-320.png", "strategies-2-390.png", "strategies-custom-2-390.png", "auth-2-390.png", "auth-2-320.png", "failure-state.png"]);
let screenshotEvidenceCharacters = 0;
let screenshotEvidenceSequence = 0;
function logScreenshotEvidence(name, png) {
  if (!screenshotEvidenceNames.has(name)) return;
  const encoded = png.toString("base64");
  screenshotEvidenceSequence += 1;
  const metadata = {
    capture: screenshotEvidenceSequence,
    file: name,
    sha256: createHash("sha256").update(png).digest("hex"),
    bytes: png.length,
    encoding: "base64",
    encoded_characters: encoded.length,
    chunks: Math.ceil(encoded.length / 4096),
    chunk_size: 4096
  };
  if (encoded.length > 1024 * 1024 || screenshotEvidenceCharacters + encoded.length > 3 * 1024 * 1024) {
    console.log(JSON.stringify({
      event: "OMNICIO_PNG_SKIPPED",
      ...metadata,
      reason: "encoded_size_limit"
    }));
    return;
  }
  screenshotEvidenceCharacters += encoded.length;
  console.log(JSON.stringify({
    event: "OMNICIO_PNG_BEGIN",
    ...metadata
  }));
  for (let offset = 0; offset < encoded.length; offset += 4096) {
    console.log(JSON.stringify({
      event: "OMNICIO_PNG_CHUNK",
      capture: metadata.capture,
      file: name,
      index: offset / 4096,
      data: encoded.slice(offset, offset + 4096)
    }));
  }
  console.log(JSON.stringify({
    event: "OMNICIO_PNG_END",
    ...metadata
  }));
}
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
  let captureFailure;
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
    let requestedViewport = null;
    const configureViewport = async (width, height = 900) => {
      const params = {
        width,
        height,
        deviceScaleFactor: 1,
        mobile: width < 680
      };
      await send("Emulation.setDeviceMetricsOverride", params);
      requestedViewport = params;
    };
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Page.addScriptToEvaluateOnNewDocument", {
      source: 'window.__browserErrors=[];window.__cspViolations=[];addEventListener("error",e=>window.__browserErrors.push(e.error?.stack||e.message));addEventListener("unhandledrejection",e=>window.__browserErrors.push(e.reason?.stack||String(e.reason)));addEventListener("securitypolicyviolation",e=>window.__cspViolations.push(e.effectiveDirective));'
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
    const wait = (expression, label) => until(async () => {
      const result = await evaluate(`({ready:Boolean(${expression}),errors:window.__browserErrors||[],csp:window.__cspViolations||[]})`);
      assert.deepEqual(result.errors, [], `${label}: runtime errors before state acknowledgement`);
      assert.deepEqual(result.csp, [], `${label}: CSP violations before state acknowledgement`);
      return result.ready;
    }, label || expression);
    const fieldValue = (form, name, value) => evaluate(`(() => {const input=document.querySelector(${JSON.stringify(form)}).elements[${JSON.stringify(name)}];input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));})()`);
    const layoutMetrics = [];
    const recordLayout = async label => {
      const data = await evaluate(`(${captureBrowserLayout.toString()})()`);
      data.expectedViewport = {
        ...requestedViewport
      };
      layoutMetrics.push({
        label,
        ...data
      });
      writeFileSync(join(artifacts, "layout-metrics.json"), JSON.stringify(layoutMetrics, null, 2));
      return data;
    };
    const settleLayout = () => evaluate(`(async () => {
      const finite = document.getAnimations().filter(animation => animation.playState === 'running' && Number.isFinite(animation.effect?.getComputedTiming().iterations));
      await Promise.allSettled(finite.map(animation => animation.finished));
      await new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)));
    })()`);
    const checkLayout = async label => {
      await settleLayout();
      const data = await recordLayout(label);
      assertViewportSize(data, label);
      assert.deepEqual(data.errors, [], label + ": runtime errors");
      assert.deepEqual(data.csp, [], label + ": production Content Security Policy");
      assertMobileNavigation(data, label);
      assertReadability(data, label);
      assertMobileHero(data, label);
      assertChartLayout(data.charts, label);
      assertTableClipping(data.tables, label);
    };
    const screenshot = async (name, {
      validate = true
    } = {}) => {
      if (validate) {
        await checkLayout(name);
      } else {
        await settleLayout();
        await recordLayout(name);
      }
      const opacity = await evaluate(`(() => {
        const view = document.querySelector('.view:not([hidden])');
        return view?.getClientRects().length ? Number(getComputedStyle(view).opacity) : 1;
      })()`);
      if (validate) assert.equal(opacity, 1, "A settled page must retain full opacity: " + name);
      const result = await send("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false
      });
      const png = Buffer.from(result.data, "base64");
      writeFileSync(join(artifacts, name), png);
      logScreenshotEvidence(name, png);
    };
    captureFailure = async error => {
      const documentState = await evaluate('({url:location.href,ready:document.readyState,errors:window.__browserErrors,csp:window.__cspViolations,bodyText:document.body?.innerText,bodyHTML:document.body?.innerHTML})');
      const requests = Object.fromEntries([...fixtures].map(([key, fixture]) => [key, fixture.requests.slice(-30)]));
      const debug = {
        failure: error.stack || String(error),
        document: documentState,
        requests
      };
      writeFileSync(join(artifacts, "failure-state.json"), JSON.stringify(debug, null, 2));
      await screenshot("failure-state.png", {
        validate: false
      });
      console.error(JSON.stringify({
        failure: error.message,
        url: documentState.url,
        errors: documentState.errors,
        csp: documentState.csp,
        bodyText: documentState.bodyText?.slice(0, 3500),
        requests
      }, null, 2));
    };
    const widths = [1440, 1366, 768, 390, 320];
    for (const round of [1, 2]) {
      for (const width of widths) {
        await exerciseViewport({
          send,
          configureViewport,
          width,
          round,
          base,
          wait,
          checkLayout,
          screenshot,
          click,
          evaluate,
          fieldValue
        });
      }
      await exerciseThemePersistence({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout, screenshot});
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
    await click('#strategy-tab-custom');
    assert.equal(await evaluate('document.querySelector("[data-action=strategy-apply-custom]").disabled'), true, "A failed saved-draft load cannot enable custom strategy application");
    await delay(750);
    assert.equal(failure.requests.filter(item => !["GET", "HEAD"].includes(item.method)).length, 0, "Unknown saved settings cannot be overwritten by selecting a preset");
    console.log("PASS failure states: no defaults saved over failed loads");
  } catch (error) {
    if (captureFailure) await captureFailure(error).catch(diagnosticError => console.error("Could not capture browser failure:", diagnosticError.message));
    throw error;
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
    styleContracts();
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
async function serveTestAuthConfig({
  response,
  fixture
}) {
  return sendJSON(response, {
    login_enabled: fixture.tidEnabled || fixture.vkidEnabled,
    vkid_enabled: fixture.vkidEnabled,
    tid_enabled: fixture.tidEnabled,
    tid_configured: fixture.tidEnabled,
    auth_provider: "vkid",
    registration_enabled: false
  });
}
async function serveTestStrategyCatalog({
  response
}) {
  return sendJSON(response, catalog);
}
async function serveTestPublicMarketReference({
  response
}) {
  return sendJSON(response, reference);
}
async function serveTestPublicNews({
  response
}) {
  return sendJSON(response, {
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
}
async function serveTestGuard5({
  response
}) {
  return sendJSON(response, {
    authorize_url: "https://untrusted.invalid/authorize"
  });
}
async function serveTestGuard6({
  response
}) {
  return sendJSON(response, {
    detail: "authentication required"
  }, 401);
}
async function serveTestGuard7({
  response
}) {
  return sendJSON(response, {
    detail: "profile_context_changed"
  }, 409);
}
async function serveTestGuard8({
  response
}) {
  return sendJSON(response, {
    detail: "profile_context_required"
  }, 409);
}
async function serveTestMe({
  response,
  fixture
}) {
  return sendJSON(response, {
    public_id: fixture.user,
    status: "active",
    role: "user"
  });
}
async function serveTestAuthIdentities({
  response
}) {
  return sendJSON(response, {
    providers: ["vkid"],
    available_providers: {
      tid: true,
      vkid: true
    }
  });
}
async function serveTestWorkspace({
  fixture,
  response,
  url
}) {
  const result = workspace(fixture);
  const period = url.searchParams.get("history_period") || "all";
  const stored = result.overview.history;
  const days = {
    "1d": 1,
    "1w": 7,
    "1m": 31,
    "3m": 93,
    "1y": 365
  }[period];
  const requestedFrom = days ? day(days) : null;
  const points = stored.filter(item => !requestedFrom || item.captured_at >= requestedFrom);
  result.overview.history = points;
  result.overview.history_coverage = {
    status: points.length ? "complete" : "empty",
    period,
    requested_from: requestedFrom,
    requested_to: stamp,
    available_from: stored[0]?.captured_at || null,
    available_to: stored.at(-1)?.captured_at || null,
    total_stored_observations: stored.length,
    total_observations: points.length,
    returned_observations: points.length,
    returned_from: points[0]?.captured_at || null,
    returned_to: points.at(-1)?.captured_at || null,
    sampling: "all_observations",
    max_points: 366
  };
  if (fixture.holdWorkspace) await new Promise(release => fixture.heldWorkspace.push(release));
  return sendJSON(response, fixture.failWorkspace ? {
    detail: "synthetic_failure"
  } : result, fixture.failWorkspace ? 503 : 200);
}
function serveTestRefresh({
  fixture,
  response,
  method,
  body
}) {
  if (method === "POST") {
    assert.equal(body.expected_public_id, fixture.user, "Refresh body confirms current public profile");
    fixture.refreshPollsRemaining = fixture.refreshQueued ? 2 : 0;
    fixture.refreshStatus = {
      ...fixture.refreshStatus,
      status: fixture.refreshQueued ? "queued" : "succeeded",
      job_id: "synthetic-refresh",
      requested_at: stamp,
      started_at: stamp,
      can_refresh: !fixture.refreshQueued,
      snapshot_saved: !fixture.refreshQueued
    };
  } else if (fixture.refreshPollsRemaining > 0) {
    fixture.refreshPollsRemaining -= 1;
    const finished = fixture.refreshPollsRemaining === 0;
    fixture.refreshStatus = {
      ...fixture.refreshStatus,
      status: finished ? "succeeded" : "running",
      finished_at: finished ? stamp : null,
      can_refresh: finished,
      snapshot_saved: finished,
      history_status: finished ? "complete" : null
    };
  }
  return sendJSON(response, fixture.refreshStatus);
}
const executionListDTO = fixture => ({
  executions: fixture.executions.map(execution => ({
    ...execution,
    legs: []
  })),
  has_active_live_execution: fixture.executions.some(execution => execution.mode === "live" && ["created", "running", "reconciling"].includes(execution.status)),
  live_mandate: fixture.mandate,
  recovery_only: true,
  new_orders_enabled: false
});
const executionDetailDTO = execution => ({
  execution: clone(execution),
  events: [],
  recovery_only: true,
  new_orders_enabled: false
});
function serveTestExecutions({
  path,
  fixture,
  response,
  method
}) {
  if (path === "/api/portfolio/executions") return sendJSON(response, executionListDTO(fixture));
  const [,,,, id, action] = path.split("/");
  const execution = fixture.executions.find(item => item.id === id);
  if (!execution) return sendJSON(response, {
    detail: "execution_not_found"
  }, 404);
  if (method === "POST") {
    assert.ok(["reconcile", "cancel"].includes(action), "Recovery can only reconcile or cancel existing requests");
    if (action === "cancel") {
      execution.status = "cancelled";
      execution.legs[0].status = "cancelled";
    } else execution.legs[0].last_checked_at = stamp;
    if (fixture.recoveryLostAck) {
      fixture.recoveryLostAck = false;
      return sendJSON(response, {
        detail: "synthetic_lost_ack"
      }, 503);
    }
  }
  return sendJSON(response, executionDetailDTO(execution));
}
function serveTestMandate({
  fixture,
  response,
  method
}) {
  if (method === "DELETE") fixture.mandate = null;
  return sendJSON(response, {
    live_mandate: fixture.mandate
  });
}
async function serveTestPreferences({
  path,
  fixture,
  method,
  response,
  body
}) {
  const strategy = path.endsWith("strategy");
  const current = strategy ? fixture.selection : fixture.prefs;
  if (method === "GET") return serveTestSavedSettings({
    strategy,
    fixture,
    response
  });
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
async function serveTestProfileInvestment({
  response,
  fixture
}) {
  return sendJSON(response, {
    public_id: fixture.user,
    profile: {
      version: 1,
      ...fixture.selection.document.profile
    }
  });
}
async function serveTestProfileBalancing({
  response,
  fixture
}) {
  return sendJSON(response, {
    public_id: fixture.user,
    policy: {
      version: 1,
      ...fixture.selection.document.policy
    }
  });
}
async function serveTestProfileStrategyAccountAssessment({
  response,
  fixture
}) {
  return sendJSON(response, {
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
}
async function serveTestProfileStrategyResearch({
  response
}) {
  return sendJSON(response, {
    status: "insufficient_data",
    reason: "Нет достаточной истории в изолированном тесте",
    probability_of_profit: null
  });
}
async function serveTestPortfolioVisualization({
  response,
  fixture
}) {
  return sendJSON(response, {
    status: "observed",
    history: overview().history,
    latest: {
      captured_at: stamp,
      ...overview(),
      positions: fixture.connected ? positions : []
    }
  });
}
async function serveTestPortfolioInstruments({
  response
}) {
  return sendJSON(response, {
    status: "observed",
    latest: {
      ...positions[0],
      captured_at: stamp
    },
    sources: [],
    payouts: [],
    history: []
  });
}
async function serveTestMarketInstruments({
  response
}) {
  return sendJSON(response, {
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
}
async function serveTestMarketInstruments2({
  response,
  url
}) {
  return sendJSON(response, {
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
}
async function serveTestBrokerTbankInstrumentsSearch({
  response
}) {
  return sendJSON(response, {
    items: [{
      uid: "synthetic-a",
      name: "Тестовая компания A",
      ticker: "SYNA",
      instrument_type: "share"
    }]
  });
}
async function serveTestBrokerTbankAnalysis({
  response
}) {
  return sendJSON(response, {
    analysis: {
      security_count: 2,
      valued_security_count: 2,
      sector_coverage_percent: "100",
      observations: []
    },
    refreshed_at: stamp
  });
}
async function serveTestBrokerTbank({
  method,
  fixture,
  response
}) {
  if (method === "DELETE") fixture.connected = false;
  if (method === "PUT") fixture.connected = true;
  return sendJSON(response, connection(fixture));
}
async function serveTestBrokerTbankAccounts({
  response
}) {
  return sendJSON(response, {
    accounts: [{
      id: "synthetic-account",
      name: "Тестовый счёт",
      type: "broker",
      status: "open"
    }]
  });
}
async function serveTestGoals({
  response,
  fixture
}) {
  if (fixture.failGoals) return sendJSON(response, {
    detail: "read_source_unavailable"
  }, 503);
  const result = {
    items: clone(fixture.goals)
  };
  if (fixture.holdGoals) await new Promise(release => fixture.heldGoals.push({
    release,
    items: result.items
  }));
  return sendJSON(response, result);
}
async function serveTestGoals2({
  fixture,
  body,
  response
}) {
  fixture.goalSequence += 1;
  const goal = {
    id: `synthetic-goal-${fixture.goalSequence}`,
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
  if (fixture.goalWriteConsentAfterCommit) return sendJSON(response, {
    detail: "updated_legal_consent_required"
  }, 409);
  return sendJSON(response, goal, 201);
}
async function serveTestGoals3({
  path,
  fixture,
  body,
  response,
  method
}) {
  const id = path.split("/").at(-1);
  const current = fixture.goals.find(goal => goal.id === id);
  if (!current || body.expected_version !== current.version) return sendJSON(response, {
    detail: "settings_version_conflict"
  }, 409);
  if (method === "DELETE") {
    fixture.goals = fixture.goals.filter(goal => goal.id !== id);
    if (fixture.goalDeleteNoContent) {
      response.statusCode = 204;
      return response.end();
    }
    return sendJSON(response, {
      deleted: true
    });
  }
  Object.assign(current, body.document, {
    version: current.version + 1
  });
  const saved = clone(current);
  if (fixture.holdGoalWriteAck) await new Promise(release => fixture.heldGoalWrites.push({
    release,
    goal: saved
  }));
  if (fixture.goalWriteConsentAfterCommit) return sendJSON(response, {
    detail: "updated_legal_consent_required"
  }, 409);
  return sendJSON(response, saved);
}
async function serveTestEvents({
  method,
  fixture,
  body,
  response
}) {
  if (method === "POST") fixture.events.filter(item => body.ids.includes(item.id)).forEach(item => {
    item.read_at = stamp;
  });
  return sendJSON(response, eventDTO(fixture));
}
async function serveTestAssistantStatus({
  response
}) {
  return sendJSON(response, {
    configured: false,
    provider: "ollama",
    model: null,
    context_supported: true,
    max_message_length: 4000
  });
}
async function serveTestAuthLogout({
  fixture,
  response
}) {
  fixture.mode = "guest";
  response.statusCode = 204;
  return response.end();
}
async function exerciseGuestViewport({
  send,
  width,
  round,
  base,
  wait,
  checkLayout,
  screenshot,
  click,
  evaluate
}) {
  const guestKey = `guest-${round}-${width}`;
  fixtures.set(guestKey, makeFixture("guest"));
  if (width === 320) fixtures.get(guestKey).vkidEnabled = false;
  await send("Page.navigate", {
    url: `${base}?case=${guestKey}`
  });
  await wait('document.querySelectorAll(".public-strategy-card").length===10', "Public canonical catalog");
  const publicVersions = await evaluate('({hero:document.querySelector(".hero-facts>div:last-child strong").textContent,footer:document.querySelector(".public-footer [data-release-version]").textContent})');
  assert.deepEqual(publicVersions, {hero: version, footer: version}, "The public release badge and footer show the current build version");
  await checkLayout(`public ${round}/${width}`);
  await screenshot(`public-${round}-${width}.png`);
  await click('[data-action="tour"]');
  await wait('!document.querySelector("#app-shell").hidden', "Product tour");
  assert.equal(await evaluate('document.querySelectorAll("#sidebar-nav a").length'), 10);
  assert.equal(await evaluate('document.querySelectorAll("#mobile-nav a").length'), 4);
  await checkLayout(`tour ${round}/${width}`);
  if (width === 390) {
    await click('#sidebar-nav [data-route="strategies"]');
    await wait('document.querySelector("#strategy-tab-custom")', "Tour strategy catalog");
    await click('#strategy-tab-custom');
    assert.equal(await evaluate('document.querySelector("[data-action=strategy-apply-custom]").disabled'), true, "Tour can browse custom strategy information without enabling a writer");
    await click('#sidebar-nav [data-route="home"]');
  }
  assert.equal(fixtures.get(guestKey).requests.filter(item => item.path.startsWith("/api/broker/") || !["GET", "HEAD"].includes(item.method)).length, 0, "Tour cannot read private broker data or mutate anything");
  if (round === 2) {
    await click('#tour-notice [data-action="login"]');
    await checkLayout(`auth ${round}/${width}`);
    await screenshot(`auth-${round}-${width}.png`);
    assert.equal(await evaluate('document.querySelectorAll("#auth-form input[required]").length'), 4, "Both OAuth providers require the four consent choices");
    assert.equal(await evaluate('document.querySelectorAll("#auth-form input[type=password],#auth-form input[type=email]").length'), 0, "Authentication cannot present an unsupported password flow");
    assert.equal(await evaluate('document.querySelector("#vkid-login").disabled'), !fixtures.get(guestKey).vkidEnabled, "VK ID uses its own server availability, independently of T-ID");
    assert.equal(await evaluate('document.querySelector("#tid-login").disabled'), !fixtures.get(guestKey).tidEnabled, "T-ID uses its own server availability");
    await evaluate('for(const input of document.querySelectorAll("#auth-form input"))input.checked=true');
    await click("#tid-login");
    await wait('document.querySelector("#auth-message").textContent.includes("не прошёл проверку")', "OAuth redirect allowlist");
    assert.ok((await evaluate("location.href")).startsWith(base), "Untrusted provider URL cannot navigate the page");
    await click('#auth-dialog [data-close-dialog]');
  }
}
async function exerciseThemePersistence({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout, screenshot}) {
  await configureViewport(1440);
  const key = `signed-theme-${round}`;
  const fixture = makeFixture("signed");
  fixture.prefs.document.theme = "light";
  fixture.prefs.document.notifications.payments = false;
  fixture.prefs.document.quiet_hours.enabled = true;
  fixture.holdPreferences = true;
  fixture.holdWorkspace = true;
  const original = clone(fixture.prefs);
  fixtures.set(key, fixture);
  await send("Page.navigate", {url: `${base}?case=${key}#assistant`});
  await wait('!document.querySelector("#app-shell").hidden', "Direct assistant route has a theme control");
  await until(() => fixture.heldPreferences.length === 1, "Preferences load on the direct assistant route");
  await click('.app-topbar [data-theme-choice="dark"]');
  await wait('document.documentElement.dataset.theme==="dark"', "Theme responds before slow preferences arrive");
  await delay(750);
  assert.equal(fixture.requests.filter(item => item.path === "/api/preferences" && item.method === "PUT").length, 0, "An early theme choice cannot write before either preferences source is known");
  fixture.holdPreferences = false;
  fixture.holdWorkspace = false;
  fixture.heldPreferences.splice(0).forEach(release => release());
  fixture.heldWorkspace.splice(0).forEach(release => release());
  await until(() => fixture.prefs.version === original.version + 1, "Early explicit theme is saved against the loaded version");
  await wait('document.querySelector(".app-topbar [data-theme-choice=dark]").getAttribute("aria-pressed")==="true"', "Late server response cannot replace the chosen theme");
  assert.deepEqual(fixture.prefs.document, {...original.document, theme: "dark"}, "Bootstrap theme must preserve every unrelated server preference");
  const firstWrite = fixture.requests.find(item => item.path === "/api/preferences" && item.method === "PUT");
  assert.equal(firstWrite.body.expected_version, original.version, "Theme uses the actual server revision");
  assert.equal(firstWrite.profile, fixture.user, "Theme writes retain the profile precondition");
  await click('#sidebar-nav [data-route="settings"]');
  await wait('document.querySelector("#preferences-form")', "Settings after an early theme choice");
  await fieldValue("#preferences-form", "locale", "en");
  await fieldValue("#preferences-form", "quiet_start", "");
  const beforeHeader = clone(fixture.prefs);
  await click('.app-topbar [data-theme-choice="light"]');
  await until(() => fixture.prefs.version === beforeHeader.version + 1, "Header theme saves despite an unrelated invalid form draft");
  assert.deepEqual(fixture.prefs.document, {...beforeHeader.document, theme: "light"}, "Unsubmitted form fields cannot accompany a header theme write");
  assert.deepEqual(await evaluate('(() => {const form=document.querySelector("#preferences-form");return {theme:form.elements.theme.value,locale:form.elements.locale.value,quiet:form.elements.quiet_start.value,valid:form.checkValidity()};})()'), {theme: "light", locale: "en", quiet: "", valid: false}, "Theme field synchronizes while unrelated form edits remain unsubmitted");
  await click('#preferences-form [type="submit"]');
  await delay(750);
  assert.equal(fixture.prefs.version, beforeHeader.version + 1, "Invalid explicit form submit remains blocked");
  await fieldValue("#preferences-form", "quiet_start", original.document.quiet_hours.start);
  await click('#preferences-form [type="submit"]');
  await until(() => fixture.prefs.document.locale === "en", "Other settings save after validation");
  assert.equal(fixture.prefs.document.theme, "light", "Saving another setting cannot restore the stale form theme");
  fixture.lostAck = true;
  await click('.app-topbar [data-theme-choice="system"]');
  await wait('document.querySelector("[data-save-status=prefs]").dataset.state==="saved" && document.querySelector(".app-topbar [data-theme-choice=system]").getAttribute("aria-pressed")==="true"', "Auto theme reconciles a lost save acknowledgement");
  assert.equal(fixture.prefs.document.theme, "system", "Auto is stored as a mode");
  for (const color of ["dark", "light"]) {
    await send("Emulation.setEmulatedMedia", {features: [{name: "prefers-color-scheme", value: color}]});
    await wait(`document.documentElement.dataset.theme===${JSON.stringify(color)}`, "Auto follows the operating system: " + color);
    assert.equal(await evaluate('localStorage.getItem("omnicio-theme")'), "system", "Resolved color cannot replace the stored auto choice");
    assert.equal(await evaluate('document.querySelector(".app-topbar [data-theme-choice=system]").getAttribute("aria-pressed")'), "true");
  }
  const savedVersion = fixture.prefs.version;
  await click('#sidebar-nav [data-route="assistant"]');
  const previousDocumentTimeOrigin = await evaluate("performance.timeOrigin");
  await send("Page.reload");
  await wait(`performance.timeOrigin!==${previousDocumentTimeOrigin} && document.querySelector("#app-shell")?.hidden===false && document.querySelector("#profile-name")?.textContent.includes("Тестовый") && document.documentElement.dataset.theme==="light"`, "Auto theme survives a new direct-route document with loaded preferences");
  assert.equal(await evaluate('document.querySelector(".app-topbar [data-theme-choice=system]").getAttribute("aria-pressed")'), "true");
  assert.equal(fixture.prefs.version, savedVersion, "Reload does not rewrite unchanged preferences");
  await checkLayout(`theme-auto ${round}/1440`);
  await exerciseShortDrawer({configureViewport, round, click, wait, evaluate, checkLayout, screenshot});
  await send("Emulation.setEmulatedMedia", {features: []});
  console.log(`PASS theme round ${round}: direct route, slow load, CAS, unrelated drafts, validation, lost acknowledgement, system changes and reload`);
}
async function exerciseShortDrawer({configureViewport, round, click, wait, evaluate, checkLayout, screenshot}) {
  await configureViewport(390, 568);
  await click("#app-menu-toggle");
  await wait('document.querySelector("#app-sidebar").dataset.open==="true"', "Short-screen drawer");
  await checkLayout(`short-drawer ${round}/390`);
  const reachability = await evaluate('(() => {const last=document.querySelector("#sidebar-nav [data-route=settings]");last.scrollIntoView({block:"nearest",behavior:"instant"});const rect=last.getBoundingClientRect();const close=document.querySelector("#drawer-close");const box=close.getBoundingClientRect();return {hit:last.contains(document.elementFromPoint(rect.left+rect.width/2,rect.top+rect.height/2)),height:rect.height,closeVisible:box.top>=0&&box.bottom<=innerHeight,closeHit:close.contains(document.elementFromPoint(box.left+box.width/2,box.top+box.height/2)),closeWidth:box.width,closeHeight:box.height};})()');
  assert.equal(reachability.hit, true, "The final settings item remains reachable");
  assert.ok(reachability.height >= 44, "Drawer items retain comfortable touch targets");
  assert.equal(reachability.closeVisible, true, "The close control remains entirely visible after scrolling to the last menu item");
  assert.equal(reachability.closeHit, true, "The close control remains reachable on a short touch screen");
  assert.ok(reachability.closeWidth >= 44 && reachability.closeHeight >= 44, "The visible close target cannot be reduced to fit the short drawer");
  await screenshot(`drawer-short-${round}-390.png`);
  await click("#drawer-close");
  await wait('document.querySelector("#drawer-backdrop").hidden && !document.querySelector(".app-main").inert', "Close control releases the page after scrolling");
  await click('#sidebar-nav [data-route="settings"]');
  await wait('document.querySelector("#app-sidebar").dataset.open!=="true" && document.querySelector("#preferences-form")', "Final drawer item opens its page");
}
async function exerciseViewport({
  send,
  configureViewport,
  width,
  round,
  base,
  wait,
  checkLayout,
  screenshot,
  click,
  evaluate,
  fieldValue
}) {
  await configureViewport(width);
  await exerciseGuestViewport({
    send,
    width,
    round,
    base,
    wait,
    checkLayout,
    screenshot,
    click,
    evaluate
  });
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
    await checkLayout(`drawer ${round}/${width}`);
    if (round === 2 && width <= 390) await screenshot(`drawer-${round}-${width}.png`);
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
  await exerciseChartPointer({
    send,
    evaluate,
    expectedEnd: before
  });
  await checkLayout(`asset ${round}/${width}`);
  await screenshot(`asset-${round}-${width}.png`);
  await click('#view-asset [data-watch]');
  await until(() => fixture.prefs.document.watchlist.length === 1, "Persistent watchlist");
  await wait('document.querySelector("#view-asset [data-watch]").getAttribute("aria-pressed")==="true"', "Saved favorite");
  await click('#sidebar-nav [data-route="strategies"]');
  await wait('document.querySelector("#strategy-form")', "Strategy form");
  await exerciseStrategyTabs({
    fixture,
    click,
    evaluate,
    send,
    wait
  });
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
  await exerciseCustomStrategyRestore({
    fixture,
    click,
    fieldValue,
    evaluate,
    wait
  });
  if (width === 390) await screenshot(`strategies-custom-${round}-${width}.png`);
  await click('#strategy-tab-catalog');
  assert.equal(fixture.maxActiveWrites, 1, "Versioned autosave uses a single in-flight mutation");
  configureGoalCases(fixture, round, width);
  await exerciseGoalCRUD({
    fixture,
    click,
    fieldValue,
    wait,
    evaluate
  });
  await click('#sidebar-nav [data-route="events"]');
  await click('#view-events [data-action="events-read-all"]');
  await until(() => fixture.events.every(item => item.read_at), "Durable read receipts");
  await click('#sidebar-nav [data-route="settings"]');
  await wait('document.querySelector("#preferences-form")', "Preferences form");
  if (width === 390) await exerciseProfileDraft({
    fixture,
    click,
    fieldValue,
    wait,
    evaluate
  });
  const preferencesVersionBeforeInput = fixture.prefs.version;
  await fieldValue("#preferences-form", "theme", "light");
  await wait('document.querySelector("#preferences-form [data-save-status=prefs]").dataset.state==="pending"', "Unsubmitted preference draft is visible");
  if (width === 390) await delay(700);
  assert.equal(fixture.prefs.version, preferencesVersionBeforeInput, "Editing a form cannot submit settings before the explicit save action");
  await click('#preferences-form [type="submit"]');
  await until(() => fixture.prefs.document.theme === "light", "Server theme setting");
  await wait('document.documentElement.dataset.theme==="light"', "Applied light theme");
  await checkLayout(`settings-light ${round}/${width}`);
  if (width === 390) await exerciseInterruptedSave({
    fixture,
    click,
    fieldValue,
    wait,
    evaluate
  });
  if (width === 390) await exerciseRefreshRecovery({
    fixture,
    click,
    wait,
    evaluate,
    checkLayout
  });
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
const completedResourceCount = path => `performance.getEntriesByType("resource").filter(entry=>new URL(entry.name).pathname===${JSON.stringify(path)}).length`;
const strategyWrites = fixture => fixture.requests.filter(item => item.path === "/api/profile/strategy" && !["GET", "HEAD"].includes(item.method)).length;
async function assertStrategyPane(evaluate, pane, focused = false) {
  const state = await evaluate(`(() => ({
    focused:document.activeElement.id,
    tabs:[...document.querySelectorAll('.strategy-catalog [role="tab"]')].map(tab => {
      const panel=document.getElementById(tab.getAttribute('aria-controls'));
      return {id:tab.id,selected:tab.getAttribute('aria-selected')==='true',tabIndex:tab.tabIndex,panel:panel?.id,role:panel?.getAttribute('role'),labelledBy:panel?.getAttribute('aria-labelledby'),hidden:panel?.hidden};
    }),
    visibleOptions:[...document.querySelectorAll('.strategy-option')].filter(option=>option.getClientRects().length).length,
    editor:Boolean(document.querySelector('#strategy-form')?.getClientRects().length)
  }))()`);
  assert.equal(state.tabs.length, 2, "The strategy source control exposes two tabs");
  for (const tab of state.tabs) {
    const selected = tab.id === "strategy-tab-" + pane;
    assert.equal(tab.selected, selected, "The selected tab follows the viewed panel");
    assert.equal(tab.tabIndex, selected ? 0 : -1, "Only the selected source tab belongs to the Tab sequence");
    assert.equal(tab.role, "tabpanel", "Each source tab controls a real panel");
    assert.equal(tab.labelledBy, tab.id, "Each panel is named by its controlling tab");
    assert.equal(tab.hidden, !selected, "Inactive source panels are hidden");
  }
  assert.equal(state.visibleOptions, pane === "catalog" ? 10 : 0, "The ten preset choices belong only to the catalog panel");
  assert.equal(state.editor, true, "Browsing sources preserves the current strategy editor");
  if (focused) assert.equal(state.focused, "strategy-tab-" + pane, "Keyboard tab selection preserves focus on the selected tab");
}
async function exerciseStrategyTabs({
  fixture,
  click,
  evaluate,
  send,
  wait
}) {
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved" && !document.querySelector("[data-action=strategy-apply-custom]").disabled', "Saved strategy and personal conditions before tab navigation");
  const version = fixture.selection.version;
  const document = clone(fixture.selection.document);
  const writes = strategyWrites(fixture);
  await assertStrategyPane(evaluate, "catalog");
  const point = await evaluate(`(() => {
    const tab=document.querySelector('#strategy-tab-custom');
    tab.scrollIntoView({block:'center',behavior:'instant'});
    const rect=tab.getBoundingClientRect();
    return {x:rect.left+rect.width/2,y:rect.top+rect.height/2};
  })()`);
  await send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    button: "left",
    clickCount: 1,
    ...point
  });
  await send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    button: "left",
    clickCount: 1,
    ...point
  });
  await assertStrategyPane(evaluate, "custom", true);
  for (const [key, code, expected] of [["Home", 36, "catalog"], ["End", 35, "custom"], ["ArrowLeft", 37, "catalog"], ["ArrowRight", 39, "custom"]]) {
    await send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key,
      code: key,
      windowsVirtualKeyCode: code
    });
    await assertStrategyPane(evaluate, expected, true);
  }
  await click('#strategy-tab-catalog');
  await click('#strategy-tab-catalog');
  await delay(700);
  assert.equal(fixture.selection.version, version, "Mouse, keyboard and repeated tab activation cannot change the saved strategy version");
  assert.deepEqual(fixture.selection.document, document, "Source navigation preserves all strategy parameters");
  assert.equal(strategyWrites(fixture), writes, "Tab navigation cannot issue strategy POST/PUT requests");
  await click('#strategy-tab-custom');
  assert.equal(await evaluate('document.querySelector("[data-action=strategy-apply-custom]").textContent'), "Создать из текущей");
  await click('[data-action="strategy-apply-custom"]');
  assert.equal(await evaluate('document.querySelector("[data-action=strategy-apply-custom]").disabled'), true, "Explicit creation disables another application while its write is pending");
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved"', "Explicit custom creation acknowledged");
  assert.deepEqual(fixture.selection.document, {
    ...document,
    customized: true
  }, "Creating a custom strategy preserves the current exact parameters");
  assert.deepEqual(fixture.selection.custom_document, fixture.selection.document, "Creation persists the personal copy through the existing API");
  assert.equal(strategyWrites(fixture), writes + 1, "Only the explicit Create action writes");
  await assertStrategyPane(evaluate, "custom");
  await click('#strategy-tab-catalog');
}
async function exerciseCustomStrategyRestore({
  fixture,
  click,
  fieldValue,
  evaluate,
  wait
}) {
  await fieldValue('#strategy-form', 'strategy.profile.reserve_rub', '');
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved"', "Explicit unknown personal amount acknowledged");
  assert.equal(fixture.selection.document.profile.reserve_rub, null, "Clearing a personal amount is an explicit unknown value");
  const saved = clone(fixture.selection.custom_document);
  await click('[data-select-strategy="aggressive"]');
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved"', "Alternate preset acknowledged");
  assert.equal(fixture.selection.document.base_preset_id, "aggressive");
  assert.equal(fixture.selection.document.profile.reserve_rub, null, "Preset selection cannot restore a stale legacy amount over explicit null");
  assert.deepEqual(fixture.selection.custom_document, saved, "Selecting a preset preserves the last saved personal copy");
  const version = fixture.selection.version;
  const writes = strategyWrites(fixture);
  await click('#strategy-tab-custom');
  assert.equal(await evaluate('document.querySelector("[data-action=strategy-apply-custom]").textContent'), "Применить мою настройку");
  await click('[data-action="strategy-apply-custom"]');
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved"', "Restored personal strategy acknowledged");
  assert.deepEqual(fixture.selection.document, saved, "Apply restores the saved custom parameters while preserving current explicit personal values");
  assert.equal(fixture.selection.version, version + 1);
  assert.equal(strategyWrites(fixture), writes + 1, "Restoration issues one explicit versioned mutation");
  await assertStrategyPane(evaluate, "custom");
  assert.equal(await evaluate('document.querySelector("[data-action=strategy-apply-custom]").disabled'), true, "An identical active custom strategy is a no-op");
  assert.equal(await evaluate('document.querySelector("[data-action=strategy-apply-custom]").textContent'), "Уже применяется");
  await evaluate('document.querySelector("[data-action=strategy-apply-custom]").click()');
  await delay(700);
  assert.equal(strategyWrites(fixture), writes + 1, "An already applied custom strategy cannot create an unchanged-version write");
}
async function exerciseChartPointer({
  send,
  evaluate,
  expectedEnd
}) {
  const point = await evaluate('(() => {const rect=document.querySelector("#view-asset .chart-svg").getBoundingClientRect();return {x:rect.right-1,y:rect.top+rect.height/2};})()');
  await send("Input.dispatchMouseEvent", {
    type: "mouseMoved",
    ...point
  });
  assert.equal(await evaluate('document.querySelector("#view-asset .chart-readout").textContent'), expectedEnd, "Pointer coordinates use the real SVG plot after axes move outside it");
  await send("Input.dispatchKeyEvent", {
    type: "keyDown",
    key: "Home",
    code: "Home",
    windowsVirtualKeyCode: 36
  });
}
function configureGoalCases(fixture, round, width) {
  fixture.goalDeleteNoContent = round === 2;
  fixture.goalWriteConsentAfterCommit = round === 2 && width === 390;
  fixture.goalPutConsentAfterCommit = round === 2 && width === 320;
  if (round !== 1) return;
  if (width === 390) fixture.lateGoalAck = "newer_version";
  if (width === 320) fixture.lateGoalAck = "deleted";
}
async function assertDeletedGoalAfterRead({
  release,
  path,
  wait,
  evaluate
}) {
  const before = await evaluate(completedResourceCount(path));
  release();
  await wait(`${completedResourceCount(path)}>${before}`, "Delayed goal read completed in the browser");
  assert.equal(await evaluate('document.querySelectorAll("#view-goals .goal-card").length'), 0, "A read started before the confirmed deletion cannot resurrect a goal");
}
async function reconcileGoalConsentError({
  fixture,
  click,
  wait,
  evaluate,
  method = "POST"
}) {
  await wait('document.querySelector("#goal-form").dataset.uncertain==="true"', "Post-commit legal change requires goal read-back");
  assert.equal(await evaluate('document.querySelector("#goal-form [type=submit]").disabled'), true, "A 409 legal update after commit cannot enable a duplicate " + method);
  const writes = fixture.requests.filter(item => item.path.startsWith("/api/goals") && item.method === method).length;
  if (method === "PUT") await assertGoalReadbackFailure({
    fixture,
    click,
    wait,
    evaluate
  });
  fixture.holdGoals = true;
  await click('#goal-form [data-action="goal-reconcile"]');
  await until(() => fixture.heldGoals.length > 0, "Server goal read remains withheld during reconciliation");
  assert.equal(await evaluate('document.querySelector("#workspace-dialog").open'), true, "The dialog cannot close before its server read completes");
  assert.equal(await evaluate('document.querySelector("#goal-form [type=submit]").disabled'), true, "A pending read-back cannot enable another write");
  fixture.holdGoals = false;
  fixture.heldGoals.splice(0).forEach(read => read.release());
  await wait('!document.querySelector("#workspace-dialog").open && document.querySelector("#view-goals .goal-card")', "Saved goal recovered only through the server list");
  assert.equal(fixture.requests.filter(item => item.path.startsWith("/api/goals") && item.method === method).length, writes, "Goal reconciliation cannot repeat the unacknowledged " + method);
  fixture.goalWriteConsentAfterCommit = false;
}
async function assertGoalReadbackFailure({
  fixture,
  click,
  wait,
  evaluate
}) {
  fixture.failGoals = true;
  await click('#goal-form [data-action="goal-reconcile"]');
  await wait('document.querySelector("#goal-form [data-goal-readback-status]").textContent.length>0 && !document.querySelector("#goal-form [data-action=goal-reconcile]").disabled', "A failed server read exposes its error and a read-only retry");
  assert.equal(await evaluate('document.querySelector("#workspace-dialog").open'), true, "A failed read-back keeps the unresolved dialog open");
  assert.equal(await evaluate('document.querySelector("#goal-form [type=submit]").disabled'), true, "A failed read-back cannot enable a duplicate write");
  fixture.failGoals = false;
}
async function exerciseGoalCRUD(options) {
  const {
    fixture,
    click,
    fieldValue,
    wait
  } = options;
  await click('#sidebar-nav [data-route="goals"]');
  await click('#view-goals [data-action="goal-create"]');
  await fieldValue("#goal-form", "title", "Тестовая цель");
  await fieldValue("#goal-form", "target_amount_rub", "1000");
  await fieldValue("#goal-form", "progress_source", "manual");
  await fieldValue("#goal-form", "manual_amount_rub", "100");
  await click('#goal-form [type="submit"]');
  await until(() => fixture.goals.length === 1, "Create goal on server");
  if (fixture.goalWriteConsentAfterCommit) await reconcileGoalConsentError(options);
  await wait('!document.querySelector("#workspace-dialog").open', "Goal saved");
  assert.equal(fixture.goals[0].manual_amount_rub, "100");
  if (fixture.lateGoalAck) {
    await exerciseLateGoalAcknowledgement(options);
  } else if (fixture.goalPutConsentAfterCommit) {
    await exerciseGoalPutConsent(options);
  } else {
    await exerciseGoalReadRace(options);
  }
}
async function exerciseGoalReadRace({
  fixture,
  click,
  fieldValue,
  wait,
  evaluate
}) {
  fixture.holdGoals = true;
  fixture.holdWorkspace = true;
  await click('#view-goals [data-action="refresh"]');
  await until(() => fixture.heldGoals.length > 0 && fixture.heldWorkspace.length > 0, "Older goal and workspace reads remain in flight");
  await click('#view-goals [data-goal-edit]');
  assert.equal(await evaluate('document.querySelector("#goal-form").dataset.goalVersion'), "1", "Only the server-confirmed goal supplies the next edit version");
  await fieldValue("#goal-form", "title", "Изменённая тестовая цель");
  await click('#goal-form [type="submit"]');
  await until(() => fixture.goals[0].version === 2, "Versioned goal update");
  await wait('!document.querySelector("#workspace-dialog").open', "Goal updated");
  await until(() => fixture.heldGoals.some(read => read.items[0]?.version === 2), "Post-update list remains delayed");
  assert.equal(await evaluate('document.querySelector("#view-goals .goal-card h2").textContent'), "Изменённая тестовая цель", "The UI accepts the acknowledged goal before its dialog closes");
  await click('#view-goals [data-goal-delete]');
  assert.equal(await evaluate('document.querySelector("[data-goal-delete-confirm]").dataset.version'), "2", "Deletion uses the newly acknowledged version without waiting for a GET");
  await click('[data-goal-delete-confirm]');
  await until(() => fixture.goals.length === 0, "Goal deletion");
  await wait('!document.querySelector("#workspace-dialog").open', "Goal deletion acknowledged");
  await until(() => fixture.heldGoals.some(read => read.items.length === 0), "Post-deletion list remains delayed");
  assert.equal(await evaluate('document.querySelectorAll("#view-goals .goal-card").length'), 0, "The confirmed deletion removes the card before its list reload");
  fixture.holdGoals = false;
  fixture.holdWorkspace = false;
  for (const read of fixture.heldGoals.splice(0).reverse()) await assertDeletedGoalAfterRead({
    release: read.release,
    path: "/api/goals",
    wait,
    evaluate
  });
  for (const release of fixture.heldWorkspace.splice(0)) await assertDeletedGoalAfterRead({
    release,
    path: "/api/workspace",
    wait,
    evaluate
  });
}
async function confirmTestGoalDeletion({
  fixture,
  click,
  wait,
  evaluate
}, version) {
  await click('#view-goals [data-goal-delete]');
  assert.equal(await evaluate('document.querySelector("[data-goal-delete-confirm]").dataset.version'), String(version), "Deletion uses the latest acknowledged goal version");
  await click('[data-goal-delete-confirm]');
  await until(() => fixture.goals.length === 0, "Goal deletion");
  await wait('!document.querySelector("#workspace-dialog").open', "Goal deletion acknowledged");
  assert.equal(await evaluate('document.querySelectorAll("#view-goals .goal-card").length'), 0, "Confirmed deletion removes the visible goal");
}
async function exerciseGoalPutConsent(options) {
  const {
    fixture,
    click,
    fieldValue,
    wait,
    evaluate
  } = options;
  fixture.goalWriteConsentAfterCommit = true;
  await click('#view-goals [data-goal-edit]');
  await fieldValue("#goal-form", "title", "Цель после обновления согласия");
  await click('#goal-form [type="submit"]');
  await until(() => fixture.goals[0].version === 2, "PUT committed before the legal recheck");
  await reconcileGoalConsentError({
    ...options,
    method: "PUT"
  });
  assert.equal(await evaluate('document.querySelector("#view-goals .goal-card h2").textContent'), "Цель после обновления согласия", "Read-back supplies the committed document after a legal 409");
  await wait('!document.querySelector("#workspace-dialog").open', "Read-back completed");
  await confirmTestGoalDeletion(options, 2);
}
async function exerciseLateGoalAcknowledgement(options) {
  const {
    fixture,
    click,
    fieldValue,
    wait,
    evaluate
  } = options;
  fixture.holdGoalWriteAck = true;
  await click('#view-goals [data-goal-edit]');
  await fieldValue("#goal-form", "title", "Задержанное подтверждение");
  await click('#goal-form [type="submit"]');
  await until(() => fixture.heldGoalWrites.length === 1, "The server committed version 2 but its ACK is withheld");
  const acknowledgement = fixture.heldGoalWrites.shift();
  assert.equal(acknowledgement.goal.version, 2);
  await click('#goal-form [data-close-dialog]');
  fixture.goals[0].version = 3;
  fixture.goals[0].title = "Более новая версия цели";
  await click('#view-goals [data-action="refresh"]');
  await wait('document.querySelector("#view-goals .goal-card h2").textContent==="Более новая версия цели"', "A newer server version is known before the delayed ACK");
  if (fixture.lateGoalAck === "deleted") await confirmTestGoalDeletion(options, 3);
  fixture.holdGoals = true;
  fixture.holdGoalWriteAck = false;
  const path = "/api/goals/" + acknowledgement.goal.id;
  const before = await evaluate(completedResourceCount(path));
  acknowledgement.release();
  await wait(`${completedResourceCount(path)}>${before}`, "The older write ACK arrived in the browser");
  await until(() => fixture.heldGoals.length > 0, "The ACK read-back cannot repair the tested UI state yet");
  if (fixture.lateGoalAck === "newer_version") {
    assert.equal(await evaluate('document.querySelector("#view-goals .goal-card h2").textContent'), "Более новая версия цели", "A delayed version-2 ACK cannot replace known version 3 before read-back");
    await confirmTestGoalDeletion(options, 3);
    await until(() => fixture.heldGoals.some(read => read.items.length === 0), "Deletion read-back remains withheld");
  }
  assert.equal(await evaluate('document.querySelectorAll("#view-goals .goal-card").length'), 0, "An older write ACK cannot restore a confirmed deletion");
  fixture.holdGoals = false;
  for (const read of fixture.heldGoals.splice(0).reverse()) await assertDeletedGoalAfterRead({
    release: read.release,
    path: "/api/goals",
    wait,
    evaluate
  });
}
async function exerciseInterruptedSave({
  fixture,
  click,
  fieldValue,
  wait,
  evaluate
}) {
  await wait('document.querySelector("#preferences-form [data-save-status=prefs]").dataset.state==="saved"', "Initial settings acknowledged");
  fixture.mutationDelay = 800;
  await fieldValue("#preferences-form", "locale", "en");
  await click('#preferences-form [type="submit"]');
  await until(() => fixture.activeWrites === 1, "Preference write in flight before pagehide");
  await evaluate('window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true}))');
  await wait('document.querySelector("#preferences-form [data-save-status=prefs]").dataset.state==="error"', "Interrupted write remains explicitly unconfirmed");
  await until(() => fixture.activeWrites === 0 && fixture.prefs.document.locale === "en", "Server completed the interrupted write");
  const persistedVersion = fixture.prefs.version;
  await evaluate('window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true}))');
  await click('#preferences-form [data-action="prefs-retry"]');
  await wait('document.querySelector("#preferences-form [data-save-status=prefs]").dataset.state==="saved"', "Interrupted write reconciled from the server");
  assert.equal(fixture.prefs.version, persistedVersion, "Read-back cannot repeat a mutation whose response was interrupted");
  fixture.mutationDelay = 150;
  await fieldValue("#preferences-form", "locale", "ru");
  await click('#preferences-form [type="submit"]');
  await wait('document.querySelector("#preferences-form [data-save-status=prefs]").dataset.state==="saved"', "Restore the selected number format");
}
async function exerciseProfileDraft({
  fixture,
  click,
  fieldValue,
  wait,
  evaluate
}) {
  const name = fixture.prefs.document.display_name;
  const version = fixture.prefs.version;
  await click('#sidebar-nav [data-route="profile"]');
  await wait('document.querySelector("#profile-form")', "Editable profile loaded");
  await fieldValue("#profile-form", "display_name", "Несохранённый черновик");
  await wait('document.querySelector("#profile-form [data-save-status=prefs]").dataset.state==="pending"', "Profile draft status");
  await delay(700);
  assert.equal(fixture.prefs.document.display_name, name, "Typing a profile name does not mutate the server");
  assert.equal(fixture.prefs.version, version);
  await click('#sidebar-nav [data-route="home"]');
  await wait('document.querySelector("#view-home .asset-table")', "Home remains available with a local form draft");
  await click('#sidebar-nav [data-route="profile"]');
  await wait('document.querySelector("#profile-form").elements.display_name.value==="Несохранённый черновик"', "A server reload cannot erase an unsubmitted form draft");
  assert.equal(await evaluate('document.querySelector("#profile-name").textContent'), name, "The identity header still displays confirmed preferences");
  await fieldValue("#profile-form", "display_name", name);
  await wait('document.querySelector("#profile-form [data-save-status=prefs]").dataset.state==="saved"', "Reverting a draft restores the accurate saved status");
  await click('#sidebar-nav [data-route="settings"]');
  await wait('document.querySelector("#preferences-form")', "Return to settings");
}
async function exerciseRefreshRecovery({
  fixture,
  click,
  wait,
  evaluate,
  checkLayout
}) {
  await wait('document.querySelector("#view-settings [data-action=refresh]").disabled===false', "Refresh available");
  fixture.refreshQueued = true;
  const initialObservations = fixture.requests.filter(item => item.path === "/api/workspace").length;
  await click('#view-settings [data-action="refresh"]');
  await wait('document.querySelector("#connection-banner").textContent.includes("поставлено в очередь")', "Durable refresh queue");
  assert.equal(await evaluate('document.querySelector("#view-settings [data-action=refresh]").disabled'), true, "Repeated refresh stays disabled while the server job runs");
  await wait('document.querySelector("#view-settings [data-action=refresh]").disabled===false', "Completed refresh job");
  assert.ok(fixture.requests.filter(item => item.path === "/api/workspace").length > initialObservations, "A completed job reloads saved observations");
  assert.ok(fixture.requests.filter(item => item.path === "/api/workspace/refresh" && item.method === "GET").length >= 2, "Running refresh is polled from the server");
  fixture.refreshQueued = false;
  fixture.executions = [{
    id: "synthetic-run",
    proposal_id: "synthetic-proposal",
    account_id: "synthetic-account",
    mode: "live",
    provider_environment: "prod",
    status: "running",
    error_code: null,
    created_at: stamp,
    updated_at: stamp,
    finished_at: null,
    legs: [{
      id: "synthetic-leg",
      leg_index: 0,
      action: "buy",
      instrument_uid: "synthetic-uid",
      lots_requested: 2,
      lots_executed: 1,
      request_id: "synthetic-request",
      provider_order_id: "synthetic-order",
      provider_status: "EXECUTION_REPORT_STATUS_PARTIALLYFILL",
      status: "partially_filled",
      submitted_at: stamp,
      last_checked_at: null,
      terminal_at: null
    }]
  }];
  fixture.mandate = {
    id: "synthetic-mandate",
    account_id: "synthetic-account",
    max_order_notional_rub: "1000",
    max_daily_notional_rub: "2000",
    created_at: stamp,
    expires_at: day(-1),
    revoked_at: null
  };
  await click('[data-action="recovery-reload"]');
  await wait('document.querySelector(".recovery-row")', "Existing execution history");
  assert.equal(await evaluate('document.querySelector("[data-action=disconnect-start]").disabled'), true, "Active order blocks a simple broker disconnect");
  await click('[data-action="recovery-open"]');
  await wait('document.querySelector(".recovery-leg")', "Persisted execution details");
  await checkLayout("Recovery details at 390px");
  await click('[data-action="recovery-reconcile"]');
  await wait('document.querySelector("#recovery-message").textContent.includes("Состояние получено")', "Read-only reconciliation");
  assert.equal(fixture.executions[0].legs[0].lots_executed, 1, "Reconciliation does not fabricate an execution");
  fixture.recoveryLostAck = true;
  await click('[data-action="recovery-cancel"]');
  await click('[data-action="recovery-cancel-confirm"]');
  await wait('document.querySelector("#recovery-message").classList.contains("error")', "Ambiguous cancellation is explicit");
  assert.equal(await evaluate('document.querySelector("[data-action=recovery-cancel]").disabled'), true, "Unconfirmed cancellation cannot be repeated against the next leg");
  await click('[data-action="recovery-detail-reload"]');
  await wait('document.querySelector("#dialog-content").textContent.includes("Отменено") && !document.querySelector("[data-action=recovery-cancel]")', "Cancellation read back from ledger");
  await click('#workspace-dialog [data-close-dialog]');
  await click('[data-action="recovery-reload"]');
  await wait('document.querySelector("[data-action=disconnect-start]").disabled===false', "Terminal order allows disconnect");
  await click('[data-action="mandate-revoke"]');
  await click('[data-action="mandate-revoke-confirm"]');
  await wait('!document.querySelector("#workspace-dialog").open && !document.querySelector("[data-action=mandate-revoke]")', "Server-side mandate revoked");
  assert.equal(fixture.mandate, null);
  assert.equal(fixture.requests.filter(item => item.method === "POST" && /proposals|advance|executions$/.test(item.path)).length, 0, "Recovery must never create or advance a plan");
}
async function serveTestSavedSettings({
  strategy,
  fixture,
  response
}) {
  if (!strategy && fixture.failPreferences || strategy && fixture.failStrategyLoad) return sendJSON(response, {
    detail: "synthetic_load_failure"
  }, 503);
  const saved = reorderJSON(strategy ? {
    public_id: fixture.user,
    selection: clone(fixture.selection)
  } : clone(fixture.prefs));
  if (!strategy && fixture.holdPreferences) await new Promise(release => fixture.heldPreferences.push(release));
  return sendJSON(response, saved);
}
