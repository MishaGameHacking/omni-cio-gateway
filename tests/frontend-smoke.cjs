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
const serverContractResult = spawnSync(process.env.OMNICIO_PYTHON || "python", ["tests/frontend_server_contract.py"], {
  cwd: root,
  env: {...process.env, PYTHONPATH: join(root, "src")},
  encoding: "utf8",
  maxBuffer: 2 * 1024 * 1024
});
assert.equal(serverContractResult.status, 0, "Browser API contracts come from the actual server: " + serverContractResult.stderr);
const serverContracts = JSON.parse(serverContractResult.stdout);
assert.equal(serverContracts.goal_available.title, "Тестовая цель источника", "The Python JSON contract preserves Unicode across Windows stdout");
const marketEvent = JSON.parse(serverContracts.instrument_market_event.split("\ndata: ")[1].trim());
assert.equal(marketEvent.instrument_uid, "synthetic-a");
assert.equal(marketEvent.quote_status, "live");
const restMarketObservedAt = new Date(Date.parse(marketEvent.observed_at) - 1000).toISOString();
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
    digest_frequency: "off",
    digest_time: "09:00",
    digest_timezone: "Europe/Moscow"
  }
});
const makeFixture = mode => {
  const preset = clone(catalog.presets.find(item => item.id === "balanced").document);
  preset.profile.reserve_rub = "123456789.12345678";
  preset.profile.planned_withdrawal_rub = "2500.25";
  preset.policy.securities_tax_rate_percent = "13";
  return {
    mode,
    missingBundle: "",
    legacyHtml: false,
    tidEnabled: true,
    vkidEnabled: true,
    user: "000000123",
    canViewOperationalMetrics: false,
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
      id: createHash("sha256").update("synthetic-event-1").digest("hex"),
      revision: 1,
      category: "system",
      kind: "connected",
      severity: "info",
      title: "Тестовое подтверждённое событие",
      detail: "Данные из изолированного API теста",
      occurred_at: stamp,
      read_at: null,
      target: "settings",
      source: {type: "operation", amount: "125.50", currency: "RUB", expected_at: stamp, instrument_uid: "synthetic-a", state: "executed"},
      destination: {view: "asset", uid: "synthetic-a"}
    }],
    holdEventSummary: false,
    heldEventSummaries: [],
    holdEventReads: false,
    heldEventReads: [],
    ledgerItems: [{id: "fixture-ledger-1", operation_date: stamp, name: "Контрольная выплата", category: "income", instrument_uid: "synthetic-a", ticker: "SYNA", payment: {value: "12.34", currency: "eur"}}],
    notificationChannels: [],
    news: [{id: "synthetic-news-1", title: "Изолированная публикация инструмента", summary: "Краткое содержание теста", content: "Полный текст публикации из изолированного API", source: "Изолированный источник", source_url: "https://example.test/news/1", occurred_at: stamp, instrument_uids: ["synthetic-a"], priority: 1}],
    requests: [],
    mutationDelay: 0,
    failPreferences: false,
    failWorkspace: false,
    failStrategyLoad: false,
    failNotifications: false,
    holdNotifications: false,
    heldNotifications: [],
    conflict: false,
    lostAck: false,
    activeWrites: 0,
    maxActiveWrites: 0,
    holdPreferences: false,
    heldPreferences: [],
    holdPublicNews: false,
    heldPublicNews: [],
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
    executionProposals: [],
    researchRuns: [],
    researchRequests: new Map(),
    researchPrerequisite: null,
    researchDropBeforeAccept: false,
    researchLoseAcknowledgment: false,
    researchHoldAcknowledgment: false,
    researchHeldAcknowledgments: [],
    failResearchPage: false,
    heldResearchReads: [],
    holdResearchReads: false,
    heldExecutionReads: [],
    holdExecutionReads: false,
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
const eventDTO = (fixture, url = new URL("https://example.test/api/events")) => {
  const [offset, ceiling] = url.searchParams.has("cursor") ? url.searchParams.get("cursor").split(":").map(Number) : [0, Math.max(0, ...fixture.events.map(item => item.revision))];
  const query = (url.searchParams.get("query") || "").toLowerCase();
  const category = url.searchParams.get("category") || "all";
  const includesCategory = item => category === "all" || (category === "assets" ? ["portfolio", "payments"].includes(item.category) : item.category === category);
  const important = url.searchParams.get("important_only") === "true";
  const items = fixture.events.filter(item => item.revision <= ceiling && JSON.stringify(item).toLowerCase().includes(query) && includesCategory(item) && (!important || ["warning", "critical", "high"].includes(item.severity))).sort((a, b) => b.occurred_at.localeCompare(a.occurred_at) || b.id.localeCompare(a.id));
  const limit = Number(url.searchParams.get("limit") || 50);
  return {
  items: clone(items.slice(offset, offset + limit)),
  next_cursor: offset + limit < items.length ? `${offset + limit}:${ceiling}` : null,
  read_all_before: ceiling,
  unread_count: fixture.events.filter(item => !item.read_at && includesCategory(item)).length,
  alerts_suppressed: false,
  digest: {
    frequency: fixture.prefs.document.digest_frequency,
    from: day(1),
    count: fixture.events.length,
    by_category: {
      system: fixture.events.length
    }
  }
};
};
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
  matches: ({path}) => path === "/api/public/support",
  run: ({response}) => sendJSON(response, {configured: true, name: "Fixture operator", email: "support@example.test", mailto: "mailto:support@example.test", scope: "user_initiated_email"})
}, {
  matches: ({
    path
  }) => path === "/api/public/news",
  run: serveTestPublicNews
}, {
  matches: ({path}) => path.startsWith("/api/public/news/"),
  run: ({path,response}) => sendJSON(response,{id:path.split("/").at(-1),title:"Тестовая новость официального источника",content:"Подтверждённый текст изолированного официального источника.",url:"https://www.cbr.ru/press/",published_at:stamp,source:"Банк России",scope:"official_page_text",truncated:false})
}, {
  matches: ({
    path
  }) => /^\/api\/auth\/(tid|vkid)\/start$/.test(path),
  run: serveTestGuard5
}, {
  matches: ({path}) => path === "/api/me",
  run: serveTestMe
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
  matches: ({path}) => path === "/api/system/metrics",
  run: serveTestOperationalMetrics
}, {
  matches: ({
    path
  }) => path.startsWith("/api/me/sessions"),
  run: serveTestSessions
}, {
  matches: ({path}) => path === "/api/billing" || path.startsWith("/api/billing/"),
  run: serveTestBilling
}, {
  matches: ({path}) => path.startsWith("/api/research/"),
  run: serveTestResearchArchive
}, {
  matches: ({path}) => path === "/api/auth/identities",
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
  matches: ({path}) => path === "/api/portfolio/execution-capabilities" || path.startsWith("/api/portfolio/proposals/"),
  run: serveTestExecutionPlans
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
  matches: ({path}) => path === "/api/market/quotes",
  run: ({url,response}) => sendJSON(response,{items:(url.searchParams.get("instrument_uids") || "").split(",").filter(Boolean).map(uid=>({...marketEvent,instrument_uid:uid,metadata_status:"available"})),source:"T-Invest",observed_at:stamp,refresh_after_seconds:10})
}, {
  matches: ({path}) => path === "/api/workspace/operations",
  run: ({fixture,response}) => sendJSON(response,{items:clone(fixture.ledgerItems),next_cursor:null,status:"available",source:"T-Invest",observed_at:stamp})
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
  }) => path.startsWith("/api/goals/") && path.endsWith("/plan"),
  run: serveTestGoalPlan
}, {
  matches: ({path}) => path.startsWith("/api/goals/"),
  run: serveTestGoals3
}, {
  matches: ({
    path
  }) => path === "/api/events" || path.startsWith("/api/events/"),
  run: serveTestEvents
}, {
  matches: ({path}) => path === "/api/news" || path.startsWith("/api/news/"),
  run: serveTestNews
}, {
  matches: ({path}) => path === "/api/notifications" || path.startsWith("/api/notifications/"),
  run: serveTestNotifications
}, {
  matches: ({
    path
  }) => path.startsWith("/api/assistant/"),
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
  response.setHeader("X-Omnicio-Build", fixture.serverBuild || build);
  fixture.requests.push({
    path,
    query: url.searchParams.toString(),
    method,
    body,
    profile: request.headers["x-omnicio-profile"],
    clientBuild: request.headers["x-omnicio-client-build"],
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
    const page = new URL(request.headers.referer || url.href);
    const fixture = fixtures.get((url.pathname === "/" ? url : page).searchParams.get("case"));
    if (fixture?.missingBundle === url.pathname) {
      response.statusCode = 404;
      return response.end();
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
    if (path.startsWith("/assets/brand/")) file = path === "/assets/brand/omnicio-logo.png" ? join(root,"assets","brand","omnicio-logo.png") : join(root, "assets", "brand", "web", path.split("/").at(-1));
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
    let content = [".html", ".js", ".css"].includes(extname(file)) ? raw.toString().replaceAll("__OMNICIO_BUILD__", build).replaceAll("__OMNICIO_VERSION__", version) : raw;
    if (fixture?.legacyHtml && path === "/index.html") content = content.replace(/<main id="startup-state"[\s\S]*?<\/main>/, "").replace('<div id="public-site" hidden>', '<div id="public-site">');
    response.end(content);
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
    URL,
    URLSearchParams
  });
  vm.runInContext(readFileSync(join(root, "web", "i18n.js"), "utf8"), context);
  vm.runInContext(readFileSync(join(root, "web", "workspace.js"), "utf8"), context);
  const ui = context.window.OmniUI;
  for (const value of [null, undefined, "", "  ", false, [], {}, "NaN", Infinity]) assert.equal(ui.number(value), null, "Unknown and non-finite values remain unknown");
  assert.equal(ui.money(null), "—");
  assert.equal(ui.percent(null), "—");
  assert.ok(ui.freshness("T-Invest", stamp, "live").includes("Текущая котировка"), "The actual server live status has an authored user-facing label");
  assert.ok(!ui.freshness("T-Invest", stamp, "live").includes("Статус требует проверки"));
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
  startupBuildContracts();
  eventReadReceiptContracts();
  goalRouteContracts(ui);
  goalVersionContracts(ui);
  chartAxisContracts(ui);
  viewportSizeContracts();
  console.log("PASS display contracts: unknown values, source escaping, privacy, real-series requirements and locale");
};
function startupBuildContracts() {
  for (const [bundleBuild, releaseBuild] of [["__OMNICIO_BUILD__", undefined], [build, undefined], [build, build]]) {
    const reachedApplication = new Error("compatible modules reached document initialization");
    const document = {currentScript: {src: `http://127.0.0.1/assets/app.js?build=${bundleBuild}`}, documentElement: {dataset: {}}, querySelector: selector => selector === "#startup-state" ? {} : null};
    const context = vm.createContext({window: {}, document, URL});
    if (releaseBuild) context.window.OMNICIO_RELEASE = {build: releaseBuild};
    for (const name of ["i18n", "workspace"]) vm.runInContext(readFileSync(join(root, "web", `${name}.js`), "utf8").replaceAll("__OMNICIO_BUILD__", bundleBuild), context);
    context.window.OMNICIO_I18N = {...context.window.OMNICIO_I18N, apply() { throw reachedApplication; }};
    const app = readFileSync(join(root, "web", "app.js"), "utf8").replaceAll("__OMNICIO_BUILD__", bundleBuild);
    assert.throws(() => vm.runInContext(app, context), error => error === reachedApplication, "A coherent raw/dev or stamped bundle starts without relying on optional version.js metadata");
  }
  console.log("PASS startup build contracts: coherent dev and stamped bundles reach initialization even without release metadata");
}
function goalRouteContracts(ui) {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const opener = app.slice(app.indexOf("  const openGoal ="), app.indexOf("  const updateGoalFields ="));
  const entry = app.slice(app.indexOf("  function enterRouteScreen("), app.indexOf("  async function restoreRouteOverlay("));
  const state = {view: "goals", route: ui.parseRoute("#account/goals/create"), data: {goals: {items: [{id: "goal-a", title: "A"}, {id: "goal-b", title: "B"}]}}};
  const navigations = [], opened = [];
  const context = vm.createContext({state, navigate: (...args) => navigations.push(args), requireUser: () => true, goalDocument: goal => goal || {}, T: value => value, H: value => value, esc: String, field: () => "", select: () => "", openDialog: (...args) => opened.push(args), updateGoalFields() {}});
  vm.runInContext(entry + opener + "\nglobalThis.open=openGoal;", context);
  context.open();
  assert.equal(opened.length, 1, "A parsed create route opens its form without a second navigation that would reset restored scroll");
  assert.equal(navigations.length, 0, "An absent goal ID remains absent for the addressable creation screen");
  state.route = ui.parseRoute("#account/goals/edit?goal=goal-a");
  context.open("goal-a");
  assert.equal(opened.length, 2, "An addressed edit route opens the selected goal directly");
  context.open("goal-b");
  assert.equal(navigations.length, 1, "Selecting a different goal still changes the route");
  assert.equal(navigations[0][1].goal_id, "goal-b");
  assert.equal(opened.length, 2, "The different goal is not rendered before its navigation");
  state.route = ui.parseRoute("#account/goals");
  context.open();
  assert.equal(navigations.length, 2, "Opening a new goal from the list still enters its own screen");
  assert.equal(navigations[1][1].screen, "create");
  console.log("PASS goal route entry: parsed creation and edit screens preserve history restoration; another goal or screen still navigates");
}
function eventReadReceiptContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const start = app.indexOf("  const eventIsRead =");
  const end = app.indexOf("  const paintEventRow =", start);
  assert.ok(start >= 0 && end > start, "Read receipt contracts exercise the actual application reconciliation");
  const context = vm.createContext({});
  vm.runInContext(app.slice(start, end) + "\nglobalThis.reconcile = confirmEventItems;", context);
  const row = {id: "source-event", revision: 10, read_at: null, title: "Earlier fact"};
  const [changed] = context.reconcile([row], item => item.revision <= 10, new Map([[row.id, {...row, revision: 11, title: "New source fact"}]]));
  assert.equal(changed.revision, 11);
  assert.equal(changed.read_at, null);
  assert.equal(changed.read_confirmed, undefined, "A source revision newer than the read-all boundary stays unread");
  const [omitted] = context.reconcile([row], () => true, new Map());
  assert.equal(omitted.read_confirmed, true, "A successful receipt confirms an affected archived row beyond its bounded response");
  assert.equal(omitted.read_at, null, "Confirmation cannot fabricate a server timestamp");
  const [delayed] = context.reconcile([omitted], () => true, new Map([[row.id, row]]));
  assert.equal(delayed.read_confirmed, true, "A delayed overlapping receipt cannot undo a confirmed read of the same source revision");
  const [observed] = context.reconcile([omitted], () => true, new Map([[row.id, {...row, read_at: "2026-10-07T12:00:00Z"}]]));
  assert.equal(observed.read_at, "2026-10-07T12:00:00Z", "A real returned read timestamp replaces the local confirmation");
  const [newer] = context.reconcile([changed], () => true, new Map([[row.id, {...row, read_at: "2026-10-07T12:00:00Z"}]]));
  assert.equal(newer.revision, 11);
  assert.equal(newer.read_at, null, "An older acknowledged source cannot replace the displayed newer unread fact");
  const counters = app.slice(app.indexOf("  const eventUnreadCount ="), app.indexOf("  const eventUnreadLabel ="));
  const state = {tour: false, data: {events: {unread_count: 2, read_all_before: 10}}};
  const counts = vm.createContext({state, number: value => value == null ? null : Number(value)});
  vm.runInContext(counters + "\nglobalThis.count = eventUnreadCount;globalThis.boundary = eventReadBoundary;", counts);
  assert.equal(counts.count(), null, "A category-filtered page cannot establish the global unread count");
  state.data.eventSummary = {unread_total: 8, max_revision: 11};
  assert.equal(counts.count(), 8);
  assert.equal(counts.boundary(), 11, "The next explicit read-all uses the last trusted global observation without altering pagination");
  assert.equal(state.data.events.read_all_before, 10);
  console.log("PASS event receipts: source revisions, archived confirmations, global counters and independent pagination");
}
function deletionDraftFixture(app, kind, outcome) {
  const id = "deleted-record";
  const owned = kind === "goal" ? [`goal-form:${id}`, `goal-plan-form:${id}`] : [`assistant-memory-form:${id}`];
  const formId = kind === "goal" ? "goal-form" : "assistant-memory-form";
  const newId = kind === "goal" ? "" : "new-note";
  const unrelated = [`${formId}:another-record`, `${formId}:${newId}`];
  const state = {generation: 1, eventRequest: 1, view: kind === "goal" ? "goals" : "assistant", deletedGoalIds: new Set(), data: {goals: {items: [{id, version: 3}]}, assistantMemory: {items: [{id, version: 2}]}}, screenDrafts: {}, screenBaselines: {}, assistantDraft: {message: ""}, assistantMemorySelected: new Set([id])};
  for (const key of [...owned, ...unrelated]) { state.screenDrafts[key] = {title: "Unsubmitted " + key}; state.screenBaselines[key] = "{}"; }
  const editorId = outcome === "other-editor" ? "another-record" : outcome === "new-editor" ? newId : id;
  const dialog = {open: true, close() { this.open = false; }};
  let editor = {id: kind === "goal" && outcome === "plan-editor" ? "goal-plan-form" : formId, dataset: kind === "goal" ? {goalId: editorId} : {id: editorId}, closest: () => kind === "goal" ? dialog : null, remove() { editor = null; }};
  const hooks = new Map();
  const capture = () => {
    if (!editor) return;
    const key = `${editor.id}:${editor.dataset.goalId || editor.dataset.id || ""}`;
    state.screenBaselines[key] ||= "{}";
    state.screenDrafts[key] = {content: "Editing this note"};
  };
  const context = vm.createContext({
    state, acceptingUpdate: false, requireUser: () => true, safeSegment: value => value, T: value => value,
    api: async () => {
      if (outcome === "unknown") throw Object.assign(new Error("lost_ack"), {status: 503});
      if (outcome === "changed-profile") state.generation += 1;
      if (["other-editor", "new-editor"].includes(outcome)) state.eventRequest += 1;
      if (outcome === "invalid") return {deleted: false};
      return outcome === "no-content" ? null : {deleted: true};
    },
    $: selector => selector === "#workspace-dialog" ? dialog : selector === "#" + editor?.id ? editor : null,
    window: {addEventListener: (type, handler) => hooks.set(type, handler)},
    captureScreenDrafts: capture, saveNavigationPosition() {}, hasPending: () => false,
    clearScreenDraft() { throw new Error("An older goal acknowledgment cannot accept its form as the current saved version"); },
    replaceGoalList: items => { state.data.goals = {items}; },
    renderGoalConsumers: capture, refreshGoalList: async () => {}, toast() {}, reportGoalDeleteError() {},
    loadResource: async () => { capture(); state.data.assistantMemory.items = []; }, renderAssistant: capture
  });
  const parts = [
    ["  function draftKey(", "  function draftForms("],
    ["  function discardScreenDraft(", "  function screenLink("],
    ["  const acceptSavedGoal =", "  const renderGoalConsumers ="],
    ["  async function handleClickGoalDeleteConfirm(", "  async function handleClickStrategy("],
    ["  async function deleteAssistantMemory(", "  function assistantSourcesHTML("],
    ['  window.addEventListener("beforeunload",', '  window.addEventListener("pagehide",']
  ].map(([start, end]) => {
    const from = app.indexOf(start), to = app.indexOf(end, from);
    assert.ok(from >= 0 && to > from, "Deletion contracts use the current application lifecycle: " + start);
    return app.slice(from, to);
  });
  vm.runInContext(parts.join("\n") + "\nglobalThis.acceptGoal=acceptSavedGoal;globalThis.deleteGoal=handleClickGoalDeleteConfirm;globalThis.deleteMemory=deleteAssistantMemory;", context);
  return {id, owned, unrelated, state, hooks, context, dialog, editorPresent: () => Boolean(editor), resolveUnrelatedInput: () => { if (editorId !== id) editor = null; }};
}
async function deletedDraftContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  for (const kind of ["goal", "memory"]) for (const outcome of ["success", "no-content", "unknown", "invalid", "changed-profile", "other-editor", "new-editor", "plan-editor"]) {
    const fixture = deletionDraftFixture(app, kind, outcome);
    const {id, owned, unrelated, state, hooks, context} = fixture;
    if (kind === "goal") assert.equal(context.acceptGoal({id, version: 2}, {dataset: {goalId: id, goalVersion: "1"}}), false);
    const confirmed = ["success", "other-editor", "new-editor", "plan-editor"].includes(outcome) || kind === "goal" && outcome === "no-content";
    const remove = kind === "goal" ? () => context.deleteGoal({event: {preventDefault() {}}, control: {dataset: {goalDeleteConfirm: id, version: "3"}, isConnected: false}}) : () => context.deleteMemory(id);
    if (kind === "memory" && !confirmed && outcome !== "changed-profile") await assert.rejects(remove());
    else await remove();
    for (const key of owned) {
      assert.equal(Object.hasOwn(state.screenDrafts, key), !confirmed, `${kind}/${outcome}: only confirmed deletion discards that record's draft`);
      assert.equal(Object.hasOwn(state.screenBaselines, key), !confirmed, `${kind}/${outcome}: a deleted editor cannot recapture its baseline`);
    }
    for (const key of unrelated) assert.ok(state.screenDrafts[key] && state.screenBaselines[key], "Unrelated and new-record drafts remain protected");
    if (["other-editor", "new-editor"].includes(outcome)) {
      assert.equal(fixture.editorPresent(), true, "A different or new editor opened during deletion stays present");
      assert.equal(fixture.dialog.open, true, "A late deletion cannot close the newer dialog");
    } else if (confirmed) assert.equal(fixture.editorPresent(), false, "A reopened editor for the deleted record cannot recreate its draft");
    let prevented = false;
    hooks.get("beforeunload")({preventDefault() { prevented = true; }});
    assert.equal(prevented, true, "Leaving still protects unrelated unsaved input");
    for (const key of unrelated) { delete state.screenDrafts[key]; delete state.screenBaselines[key]; }
    fixture.resolveUnrelatedInput();
    prevented = false;
    hooks.get("beforeunload")({preventDefault() { prevented = true; }});
    assert.equal(prevented, !confirmed, "A confirmed deletion leaves no orphan warning; an unconfirmed outcome remains protected");
  }
  console.log("PASS deleted drafts: delayed goal ACK, goal/plan and memory ownership, confirmed responses, generation changes and preserved unrelated input");
}
async function nativeDialogProtocolContracts() {
  const source = readFileSync(join(root, "tests", "frontend-smoke.cjs"), "utf8");
  const from = source.indexOf("\nconst protocolClient = async url => {") + 1;
  const to = source.indexOf("\nconst runBrowser =", from);
  let socket;
  class SyntheticSocket {
    constructor() { socket = this; this.listeners = new Map(); this.sent = []; queueMicrotask(() => this.emit("open", {})); }
    addEventListener(type, handler) { if (!this.listeners.has(type)) this.listeners.set(type, []); this.listeners.get(type).push(handler); }
    emit(type, value) { for (const handler of this.listeners.get(type) || []) handler(value); }
    send(value) { this.sent.push(JSON.parse(value)); }
    close() {}
  }
  const context = vm.createContext({WebSocket: SyntheticSocket, setTimeout, clearTimeout});
  vm.runInContext(source.slice(from, to) + "\nglobalThis.connect=protocolClient;", context);
  const client = await context.connect("ws://synthetic.invalid");
  const navigate = client.send("Page.navigate", {url: "http://127.0.0.1/?case=next"}, "target");
  const stopped = assert.rejects(navigate, error => error.code === "unexpected_native_dialog" && error.dialog.type === "beforeunload" && error.message.includes("Page.navigate"));
  socket.emit("message", {data: JSON.stringify({method: "Page.javascriptDialogOpening", sessionId: "target", params: {type: "beforeunload", url: "http://127.0.0.1/?case=current", message: "Unsaved input", hasBrowserHandler: true}})});
  await stopped;
  await assert.rejects(client.send("Runtime.evaluate", {expression: "document.body.innerText"}, "target"), error => error.code === "unexpected_native_dialog");
  assert.equal(client.nativeDialog.type, "beforeunload", "Failure evidence retains the blocking browser event");
  const close = client.send("Browser.close");
  socket.emit("message", {data: JSON.stringify({id: socket.sent.at(-1).id, result: {}})});
  await close;
  assert.deepEqual(socket.sent.map(item => item.method), ["Page.navigate", "Browser.close"], "Diagnostics neither evaluate a blocked renderer nor accept or dismiss native dialogs");
  client.close();
  console.log("PASS native dialog diagnostics: exact event metadata, immediate target failure and safe browser cleanup without acceptance");
}
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
  const notifications = [];
  const opened = [];
  let activated = 0;
  const origin = "https://example.test";
  globalThis.self = {
    location: {
      origin
    },
    addEventListener: (name, handler) => handlers.set(name, handler),
    registration: {showNotification: async (title, options) => notifications.push({title, options})},
    clients: {matchAll: async () => [], openWindow: async path => opened.push(path)},
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
    assert.ok(cached.every(path => /^\/(offline\.html|assets\/(app\.css|app\.js|workspace\.js|i18n\.js|brand\/omnicio-logo\.png))\?build=__OMNICIO_BUILD__$/.test(path)), "Private content never enters the cache allowlist");
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
    for (const url of ["https://untrusted.invalid/#events", "/#events?event=" + "a".repeat(64), "/?credential=secret#events", "/#settings"]) {
      handlers.get("push")({data: {json: () => ({title: "PRIVATE GOAL", body: "PRIVATE AMOUNT", url, tag: "a".repeat(64)})}, waitUntil: task => tasks.push(task)});
    }
    await Promise.all(tasks);
    assert.deepEqual(notifications.map(item => item.options.data.url), ["/#account/events", "/#account/events/detail?event=" + "a".repeat(64), "/#account/events", "/#account/settings/notifications"]);
    assert.ok(notifications.every(item => item.title === "OMNICIO" && !item.options.body.includes("PRIVATE")), "Lock-screen push never shows private source content");
    let closed = false;
    handlers.get("notificationclick")({notification: {data: {url: "https://untrusted.invalid/"}, close: () => {closed = true;}}, waitUntil: task => tasks.push(task)});
    await Promise.all(tasks);
    assert.equal(closed, true);
    assert.deepEqual(opened, ["/#account/events"]);
    console.log("PASS service worker: private-cache isolation, origin checks, private push redaction and safe notification navigation");
  } finally {
    delete globalThis.self;
    delete globalThis.caches;
  }
};
function captureBrowserLayout() {
  const visible = element => element.getClientRects().length && getComputedStyle(element).visibility !== "hidden";
  const readableElements = selector => [...document.querySelectorAll(selector)].filter(visible).map(element => ({
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
  const visiblePublic = !document.querySelector("#public-site").hidden;
  const modal = Boolean(document.querySelector("dialog[open]"));
  const heroVisible = visible(document.querySelector(".hero"));
  const hero = !visibleApp && !modal && heroVisible && innerWidth <= 680 ? {
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
  const heroDecorations = !visibleApp && !modal && heroVisible && innerWidth > 680 && innerWidth <= 960 ? {
    required: true,
    rect: document.querySelector(".hero").getBoundingClientRect().toJSON(),
    labels: [...document.querySelectorAll(".hero .orbit-node")].map(element => ({text:element.textContent.trim(),rect:element.getBoundingClientRect().toJSON(),visible:Boolean(element.getClientRects().length)})),
    protected: [...document.querySelectorAll(".hero-copy,.hero-insight,.hero-data,.hero-signature")].map(element => ({name:element.className,rect:element.getBoundingClientRect().toJSON()}))
  } : {required:false};
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
    required: (visibleApp || visiblePublic) && innerWidth <= 960 && !modal && !drawer,
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
  const surface = document.querySelector("dialog[open]") || document;
  const charts = [...surface.querySelectorAll('.chart-plot')].filter(visible).map(plot => {
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
  const tables = [...surface.querySelectorAll('.table-scroll')].filter(visible).map(container => {
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
      actions: readableElements(".button, .icon-button, .screen-menu-item")
    },
    hero,
    heroDecorations,
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
function assertHeroDecorations(data, label) {
  const decorations = data.heroDecorations;
  if (!decorations.required) return;
  assert.equal(decorations.labels.length,7,label+": all reference asset labels remain present on tablets");
  const intersects = (a,b) => a.left-4 < b.right && a.right+4 > b.left && a.top-4 < b.bottom && a.bottom+4 > b.top;
  for (const [index,item] of decorations.labels.entries()) {
    assert.ok(item.visible && item.rect.width > 0 && item.rect.height > 0,label+": decorative label stays visible "+item.text);
    assert.ok(item.rect.left >= decorations.rect.left+4 && item.rect.right <= decorations.rect.right-4 && item.rect.top >= decorations.rect.top+4 && item.rect.bottom <= decorations.rect.bottom-4,label+": decorative label fits the planet area "+item.text);
    for (const region of decorations.protected) assert.equal(intersects(item.rect,region.rect),false,label+": decorative marker cannot cross text, controls or information cards "+JSON.stringify({item,region}));
    for (const previous of decorations.labels.slice(0,index)) assert.equal(intersects(item.rect,previous.rect),false,label+": decorative labels do not overlap each other "+JSON.stringify({item,previous}));
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
  let nativeDialog = null;
  const dialogError = method => Object.assign(new Error(`Unexpected native ${nativeDialog.type} dialog during ${method} at ${nativeDialog.url}`), {code: "unexpected_native_dialog", dialog: {...nativeDialog}});
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
    if (message.method === "Page.javascriptDialogOpening") {
      nativeDialog = {...message.params, sessionId: message.sessionId};
      for (const [id, waiter] of pending) {
        if (waiter.sessionId !== message.sessionId) continue;
        clearTimeout(waiter.timer);
        pending.delete(id);
        waiter.reject(dialogError(waiter.method));
      }
      return;
    }
    if (message.method === "Page.javascriptDialogClosed" && nativeDialog?.sessionId === message.sessionId) nativeDialog = null;
    const waiter = pending.get(message.id);
    if (!waiter) return;
    pending.delete(message.id);
    clearTimeout(waiter.timer);
    if (message.error) waiter.reject(new Error(JSON.stringify(message.error)));else waiter.done(message.result);
  });
  return {
    get nativeDialog() { return nativeDialog; },
    send(method, params = {}, sessionId) {
      if (nativeDialog && nativeDialog.sessionId === sessionId && method !== "Browser.close") return Promise.reject(dialogError(method));
      return new Promise((done, reject) => {
        const id = ++sequence;
        const timer = setTimeout(() => {
          pending.delete(id);
          reject(new Error("CDP timeout: " + method));
        }, 15000);
        pending.set(id, {
          method,
          sessionId,
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
    const revealControl = async selector => {
      const section = await evaluate(`(() => { const matches=[...document.querySelectorAll(${JSON.stringify(selector)})]; const element=matches.find(item=>item.getClientRects().length) || matches[0]; if (!element || element.getClientRects().length) return null; return element.closest("[data-screen-content]")?.dataset.screenContent || null; })()`);
      if (!section) return;
      await evaluate(`(() => { const view=document.querySelector(".view:not([hidden])"); const menu=view?.querySelector('[data-route][data-screen="'+${JSON.stringify(section)}+'"]'); if(!menu) throw new Error("No visible section menu for requested control"); menu.click(); })()`);
      await wait(`document.querySelector(${JSON.stringify(selector)})?.getClientRects().length > 0`, "Control is visible in its own section: " + selector);
    };
    const click = async selector => { await revealControl(selector); return evaluate(`(() => {
      const matches=[...document.querySelectorAll(${JSON.stringify(selector)})];
      const element=matches.find(item=>item.getClientRects().length) || matches[0];
      if(!element || element.disabled)throw new Error('Control unavailable: '+${JSON.stringify(selector)});
      if(element.closest('#app-sidebar')?.inert)document.querySelector('#app-menu-toggle').click();
      if(element.closest('.public-nav') && !element.getClientRects().length)document.querySelector('#public-menu-toggle').click();
      if(!element.getClientRects().length)throw new Error("Control has no visible user path: "+${JSON.stringify(selector)});
      element.click();
    })()`); };
    const wait = (expression, label) => until(async () => {
      const result = await evaluate(`({ready:Boolean(${expression}),errors:window.__browserErrors||[],csp:window.__cspViolations||[]})`);
      assert.deepEqual(result.errors, [], `${label}: runtime errors before state acknowledgement`);
      assert.deepEqual(result.csp, [], `${label}: CSP violations before state acknowledgement`);
      return result.ready;
    }, label || expression);
    const fieldValue = async (form, name, value) => { await revealControl(`${form} [name="${name}"]`); return evaluate(`(() => {const input=document.querySelector(${JSON.stringify(form)}).elements[${JSON.stringify(name)}];input.value=${JSON.stringify(value)};input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));})()`); };
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
    const checkLayout = async (label, {minCharts = 0, minTables = 0} = {}) => {
      await settleLayout();
      const data = await recordLayout(label);
      assertViewportSize(data, label);
      assert.deepEqual(data.errors, [], label + ": runtime errors");
      assert.deepEqual(data.csp, [], label + ": production Content Security Policy");
      assertMobileNavigation(data, label);
      assertReadability(data, label);
      assertMobileHero(data, label);
      assertHeroDecorations(data, label);
      assert.ok(data.charts.length >= minCharts, label + ": the requested chart is visible on its page");
      assert.ok(data.tables.length >= minTables, label + ": the requested table is visible on its page");
      assertChartLayout(data.charts, label);
      assertTableClipping(data.tables, label);
      return data;
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
      const requests = Object.fromEntries([...fixtures].map(([key, fixture]) => [key, fixture.requests.slice(-30)]));
      const debug = {
        failure: error.stack || String(error),
        nativeDialog: client.nativeDialog || error.dialog || null,
        requests
      };
      writeFileSync(join(artifacts, "failure-state.json"), JSON.stringify(debug, null, 2));
      if (client.nativeDialog) { console.error(JSON.stringify(debug, null, 2)); return; }
      const documentState = await evaluate('({url:location.href,ready:document.readyState,errors:window.__browserErrors,csp:window.__cspViolations,bodyText:document.body?.innerText,bodyHTML:document.body?.innerHTML})');
      debug.document = documentState;
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
    await exerciseStartupRecovery({send, configureViewport, base, wait, click, evaluate, checkLayout, screenshot});
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
      await exerciseCanonicalNavigation({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout});
      await exerciseIndependentPageLoads({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout});
      await exerciseSafeUpdate({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout});
      await exerciseThemePersistence({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout, screenshot});
      await exerciseEnglishLocale({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout, screenshot});
      await exerciseReadConsistency({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout, screenshot});
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
    await deletedDraftContracts();
    await nativeDialogProtocolContracts();
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
  fixture,
  response
}) {
  if (fixture.holdPublicNews) await new Promise(release => fixture.heldPublicNews.push(release));
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
  if (fixture.holdMe) await new Promise(resolve => { fixture.releaseMe = resolve; });
  if (fixture.failMe) return sendJSON(response, {detail: "synthetic_session_unavailable"}, 503);
  if (fixture.mode === "guest") return sendJSON(response, {detail: "authentication required"}, 401);
  return sendJSON(response, {
    public_id: fixture.user,
    status: "active",
    role: "user",
    can_view_operational_metrics: fixture.canViewOperationalMetrics
  });
}
function serveTestOperationalMetrics({fixture,response}) {
  if (!fixture.canViewOperationalMetrics) return sendJSON(response,{detail:"operator_required"},403);
  const worker = (status, age) => ({status,checked_at:day(age),completed_at:day(age),stale_after_seconds:300});
  return sendJSON(response, {
    status:"attention",checked_at:stamp,active_users:2,
    observer:{connected_accounts:2,queued:1,running:1,stale:1,failed_24h:2,degraded_24h:3,stale_success_accounts:1},
    oldest_pending_at:day(1),latest_success_at:stamp,stale_after_seconds:1800,observation_stale_after_seconds:129600,
    notifications:{queued:2,sending:1,stale:1,failed_24h:1,uncertain:2,oldest_due_at:day(1),last_accepted_at:stamp,stale_after_seconds:900},
    workers:{notifications:worker("attention",0),portfolio_refresh:worker("stale",1),portfolio_daily:worker("not_reported",2)},
    issues:["observer_stale","notifications_uncertain","portfolio_daily_worker_not_reported"]
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
  if (fixture.periodResults?.[period]) result.performance.investment_result_rub = fixture.periodResults[period];
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
async function serveTestExecutions({
  path,
  fixture,
  response,
  method,
  body
}) {
  if (path === "/api/portfolio/executions") {
    const saved = clone(executionListDTO(fixture));
    if (fixture.holdExecutionReads) await new Promise(release => fixture.heldExecutionReads.push(release));
    return sendJSON(response, saved);
  }
  const [,,,, id, action] = path.split("/");
  const execution = fixture.executions.find(item => item.id === id);
  if (!execution) return sendJSON(response, {
    detail: "execution_not_found"
  }, 404);
  if (method === "POST") {
    assert.ok(["reconcile", "cancel", "dispatch"].includes(action), "Only explicit execution actions are accepted");
    if (action === "dispatch") {
      assert.equal(execution.mode, "shadow", "The test UI must never submit a live broker order");
      const leg = execution.legs.find(item => item.status === "pending");
      if (!leg || leg.id !== body.expected_leg_id) return sendJSON(response, {detail: "execution_leg_changed"}, 409);
      assert.match(body.expected_leg_id, /^[a-f0-9-]{36}$/);
      leg.status = "shadow_filled";
      leg.lots_executed = leg.lots_requested;
      leg.last_checked_at = stamp;
      leg.terminal_at = stamp;
      execution.status = execution.legs.every(item => item.status === "shadow_filled") ? "succeeded" : "running";
      return sendJSON(response, executionDetailDTO(execution));
    }
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
function researchRequestDTO(request) {
  const {id,status,run_id,error_code,created_at,updated_at,expires_at} = request;
  return {id,status,run_id,error_code,created_at,updated_at,expires_at};
}
function completeTestResearch(fixture, request) {
  const result = {
    status: "insufficient_data", reason: "Нет достаточной истории в изолированном тесте",
    probability_of_profit: null, request_id: request.id, strategy_version: request.body.expected_version,
    data_coverage: [{instrument_uid: "synthetic-a", automatic_cashflow_events: 2,
      daily_accrual_observations: 20, historical_fact_observations: 3,
      missing: ["historical_lot_sizes", "bond_nkd_open_close_timing"], total_return_verified: false}]
  };
  const run = {id: require("node:crypto").randomUUID(), strategy_version: result.strategy_version,
    created_at: new Date().toISOString(), status: result.status, result, inputs: clone(request.body), metrics: {}};
  fixture.researchRuns.unshift(run);
  Object.assign(request, {status: "completed", run_id: run.id, updated_at: run.created_at});
  return {...clone(result), archive: {id: run.id, created_at: run.created_at}};
}
async function serveTestProfileStrategyResearch({response, fixture, body}) {
  assert.match(body.request_id, /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/);
  if (body.expected_version !== fixture.selection.version) return sendJSON(response, {detail: "settings_version_conflict"}, 409);
  if (fixture.researchPrerequisite) return sendJSON(response, {status: fixture.researchPrerequisite, execution_enabled: false});
  if (fixture.researchDropBeforeAccept) {
    fixture.researchDropBeforeAccept = false;
    return sendJSON(response, {detail: "synthetic_lost_ack"}, 503);
  }
  const existing = fixture.researchRequests.get(body.request_id);
  if (existing) {
    if (JSON.stringify(existing.body) !== JSON.stringify(body)) return sendJSON(response, {detail: "settings_version_conflict"}, 409);
    if (existing.status === "completed") {
      const run = fixture.researchRuns.find(item => item.id === existing.run_id);
      return sendJSON(response, {...run.result, archive: {id: run.id, created_at: run.created_at}});
    }
    return sendJSON(response, {...researchRequestDTO(existing), request_id: existing.id});
  }
  const request = {id: body.request_id, body: clone(body), status: "running", run_id: null, error_code: null,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(), expires_at: new Date(Date.now() + 600000).toISOString()};
  fixture.researchRequests.set(request.id, request);
  if (fixture.researchLoseAcknowledgment) {
    fixture.researchLoseAcknowledgment = false;
    return sendJSON(response, {detail: "synthetic_lost_ack"}, 503);
  }
  const result = completeTestResearch(fixture, request);
  if (fixture.researchHoldAcknowledgment) await new Promise(release => fixture.researchHeldAcknowledgments.push(release));
  return sendJSON(response, result);
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
  response,
  fixture
}) {
  return sendJSON(response, {
    status: "observed",
    current_holding: {status: fixture.closedPosition ? "not_held" : "held", quantity: fixture.closedPosition ? "0" : positions[0].quantity, observed_at: stamp},
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
  fixture,
  response,
  url
}) {
  if (url.pathname.endsWith("/stream")) {
    response.setHeader("Content-Type", "text/event-stream");
    response.flushHeaders();
    fixture.marketStreams ||= new Set();
    fixture.marketStreams.add(response);
    response.once("close", () => fixture.marketStreams.delete(response));
    if (!fixture.holdMarketStream) response.write(serverContracts.instrument_market_event);
    return;
  }
  return sendJSON(response, {
    instrument_uid: "synthetic-a",
    period: url.searchParams.get("period"),
    source: "Synthetic exchange",
    observed_at: restMarketObservedAt,
    last_price: "250.25",
    quote_time: restMarketObservedAt,
    quote_status: "live",
    price_unit: "currency",
    price_currency: "RUB",
    cash_price: "250.25",
    cash_price_currency: "RUB",
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
  response,
  path,
  url
}) {
  if (path === "/api/events/summary") {
    const summary = {unread_total: fixture.events.filter(item => !item.read_at).length, max_revision: Math.max(0, ...fixture.events.map(item => item.revision)), categories: {}, observed_at: stamp, alerts_suppressed: false};
    if (fixture.holdEventSummary) await new Promise(release => fixture.heldEventSummaries.push({release, summary}));
    return sendJSON(response, summary);
  }
  if (method === "GET" && path.startsWith("/api/events/")) {
    const item = fixture.events.find(event => event.id === path.split("/").at(-1));
    return sendJSON(response, item || {detail: "event_not_found"}, item ? 200 : 404);
  }
  if (method === "POST") {
    if (path === "/api/events/read-all" && fixture.arrivingEvent) {
      fixture.events.push(fixture.arrivingEvent);
      fixture.arrivingEvent = null;
    }
    fixture.events.filter(item => path === "/api/events/read-all" ? item.revision <= body.through_revision : body.ids.includes(item.id)).forEach(item => { item.read_at = body.read === false ? null : stamp; });
  }
  const result = eventDTO(fixture, url);
  if (method === "GET" && fixture.holdEventReads) await new Promise(release => fixture.heldEventReads.push({release, result}));
  return sendJSON(response, result);
}
async function serveTestNews({fixture, url, response}) {
  if (url.pathname !== "/api/news") { const item=fixture.news.find(row=>row.id===url.pathname.split("/").at(-1)); return sendJSON(response,item || {detail:"news_not_found"},item?200:404); }
  const query = (url.searchParams.get("query") || "").toLowerCase();
  const uid = url.searchParams.get("instrument_uid");
  const items = fixture.news.filter(item => (!uid || item.instrument_uids.includes(uid)) && JSON.stringify(item).toLowerCase().includes(query));
  const offset = Number(url.searchParams.get("cursor") || 0);
  const limit = Number(url.searchParams.get("limit") || 50);
  return sendJSON(response, {items: clone(items.slice(offset, offset + limit)), next_cursor: offset + limit < items.length ? String(offset + limit) : null, scanned_items: Math.min(limit, items.length - offset), instrument_uid: uid, source: "Изолированный источник", observed_at: stamp, status: items.length ? "received" : "empty"});
}
async function serveTestNotifications({fixture, path, body, method, response}) {
  if (path === "/api/notifications" && fixture.holdNotifications) await new Promise(release => fixture.heldNotifications.push(release));
  if (path === "/api/notifications" && fixture.failNotifications) return sendJSON(response, {detail: "synthetic_notification_read_failure"}, 503);
  if (path === "/api/notifications/email/request") {
    const channel = {id: "00000000-0000-4000-8000-000000000801", kind: "email", label: "t***@example.test", status: "pending", verification_expires_at: new Date(Date.now() + 900000).toISOString(), verification_attempts_remaining: 5};
    fixture.notificationChannels = [channel];
    return sendJSON(response, channel);
  }
  if (path === "/api/notifications/email/verify") {
    const channel = fixture.notificationChannels.find(item => item.id === body.channel_id);
    if (!channel || body.code !== "123456") return sendJSON(response, {detail: "notification_verification_invalid"}, 400);
    channel.status = "active";
    channel.verified_at = stamp;
    return sendJSON(response, {id: channel.id, status: "active"});
  }
  if (method === "DELETE") {
    fixture.notificationChannels = fixture.notificationChannels.filter(item => item.id !== path.split("/").at(-1));
    return sendJSON(response, {revoked: true});
  }
  return sendJSON(response, {enabled: true, push_configured: false, email_configured: true, vapid_public_key: null, channels: clone(fixture.notificationChannels), deliveries: [], receipt_scope: "provider_acceptance_only"});
}
async function exerciseEventArchive({fixture, click, fieldValue, wait, evaluate}) {
  const baseEvent = clone(fixture.events[0]);
  fixture.events = Array.from({length: 115}, (_, index) => ({...clone(baseEvent), id: createHash("sha256").update(`archive-event-${index}`).digest("hex"), revision: index + 1, title: index === 114 ? "Архивный контрольный факт" : `Подтверждённый факт ${index + 1}`, occurred_at: new Date(Date.now() - index * 60000).toISOString(), read_at: null}));
  await click('#view-events [data-action="refresh"]');
  await wait('document.querySelectorAll("#view-events [data-event-open]").length===50', "First event page is bounded");
  await click('#view-events [data-action="events-more"]');
  await wait('document.querySelectorAll("#view-events [data-event-open]").length===100', "Second event page");
  await click('#view-events [data-action="events-more"]');
  await wait('document.querySelectorAll("#view-events [data-event-open]").length===115', "Full event archive beyond fifty");
  await exerciseDelayedEventList({fixture, click, wait, evaluate});
  await click(`#view-events [data-event-open="${fixture.events[114].id}"]`);
  await wait('document.querySelector("#dialog-content").textContent.includes("Сумма операции")', "Structured event source details");
  assert.ok(await evaluate('document.querySelector("#dialog-content").textContent.includes("125,50")'));
  await click('#dialog-content [data-action="event-destination"]');
  await wait('!document.querySelector("#view-asset").hidden && location.hash.includes("synthetic-a")', "Exact source instrument deep link");
  await fieldValue("#global-search-form", "q", "Архивный контрольный");
  await evaluate('document.querySelector("#global-search-form").requestSubmit()');
  await wait('document.querySelector("#view-search [data-event-open]")', "Server search finds an older archived event");
  assert.ok(fixture.requests.some(item => item.path === "/api/events" && new URLSearchParams(item.query).get("query") === "Архивный контрольный"), "Search reads the server archive with the submitted query");
  await until(() => fixture.events[114].read_at, "The old event's explicit opening is acknowledged outside the receipt's first fifty rows");
  fixture.holdEventSummary = true;
  await click('#sidebar-nav [data-route="events"]');
  await wait('document.querySelector("#view-events [data-action=events-read-all]")?.hidden===false && !document.querySelector("#view-events [data-action=events-read-all]").disabled', "Read all is available");
  await until(() => fixture.heldEventSummaries.length === 1, "An older global summary is held before the read mutation");
  assert.equal(fixture.heldEventSummaries[0].summary.unread_total, 113, "Held summary is a real earlier observation, not a new event revision");
  await wait('document.querySelectorAll("#view-events [data-event-open]").length===115', "Opening an archived event preserves all loaded pages");
  await evaluate('window.__eventListBeforeRead=document.querySelector("#view-events .event-list");window.scrollTo({top:180,behavior:"instant"});void 0');
  await wait('window.scrollY===180', "Event archive has a saved nonzero scroll position");
  fixture.arrivingEvent = {...clone(baseEvent), id: "e".repeat(64), revision: 116, title: "Поступившее во время чтения", read_at: null, occurred_at: new Date().toISOString()};
  await click('#view-events [data-action="events-read-all"]');
  await until(() => fixture.events.length === 116 && fixture.events.filter(item => !item.read_at).length === 1, "Read-all cutoff preserves a concurrent new event");
  await wait('document.querySelector("#view-events .chip").textContent.includes("1 непрочитанных")', "New event remains unread");
  await assertEventCounterArchive({evaluate, expected: 1});
  fixture.heldEventSummaries.shift().release();
  await until(() => fixture.heldEventSummaries.length === 1, "Discarding the pre-mutation summary immediately requests the actual global count");
  assert.equal(fixture.heldEventSummaries[0].summary.unread_total, 1);
  await assertEventCounterArchive({evaluate, expected: 1});
  fixture.holdEventSummary = false;
  fixture.heldEventSummaries.shift().release();
  await wait('document.querySelector("#notifications-button").getAttribute("aria-label").includes("1 непрочитанных")', "The bell and open page share the same global unread count");
  await click('#view-events [data-news-open]');
  await wait('document.querySelector("#dialog-content").textContent.includes("Полный текст публикации")', "News article opens full source text");
  await click('#workspace-dialog [data-close-dialog]');
}
async function exerciseDelayedEventList({fixture, click, wait, evaluate}) {
  const id = fixture.events[0].id;
  fixture.holdEventReads = true;
  await click('#view-events [data-action="refresh"]');
  await until(() => fixture.heldEventReads.length === 1, "An older event page is held before a read receipt");
  assert.equal(fixture.heldEventReads[0].result.items.find(item => item.id === id).read_at, null);
  await click(`#view-events [data-event-read="${id}"]`);
  await until(() => fixture.events[0].read_at, "The explicit read commits while the earlier GET remains pending");
  await wait(`!document.querySelector('#view-events [data-event-id="${id}"]').classList.contains('unread')`, "The confirmed row changes in place before the older GET returns");
  assert.equal(await evaluate('document.querySelectorAll("#view-events [data-event-open]").length'), 115, "A fifty-row read receipt cannot replace the full archive");
  fixture.holdEventReads = false;
  fixture.heldEventReads.shift().release();
  // Wait for the explicitly requested refresh's completion, then inspect the
  // still-confirmed row. The controlled response contains its old unread value.
  await delay(300);
  await wait(`!document.querySelector('#view-events [data-event-id="${id}"]').classList.contains('unread') && document.querySelectorAll('#view-events [data-event-open]').length===115`, "A delayed event GET cannot undo a later read or truncate loaded pages");
}
async function assertEventCounterArchive({evaluate, expected}) {
  const visible = await evaluate('({text:document.querySelector("#view-events [data-event-unread]").textContent,bell:document.querySelector("#notifications-button").getAttribute("aria-label"),sameList:window.__eventListBeforeRead===document.querySelector("#view-events .event-list"),rows:document.querySelectorAll("#view-events [data-event-open]").length,unreadRows:document.querySelectorAll("#view-events [data-event-id].unread [data-event-open]").length,filter:document.querySelector("#view-events [data-event-filter][aria-pressed=true]").dataset.eventFilter,scroll:window.scrollY})');
  assert.equal(visible.text, `${expected} непрочитанных`);
  assert.ok(visible.bell.includes(`${expected} непрочитанных`), "The bell uses the same confirmed global count");
  assert.equal(visible.sameList, true, "A summary/read receipt updates counters and read marks without recreating the list");
  assert.equal(visible.rows, 115);
  assert.equal(visible.unreadRows, 0, "All rows covered by the read-all boundary are confirmed, including rows omitted from its response");
  assert.equal(visible.filter, "all");
  assert.equal(visible.scroll, 180, "Read receipts and counter polls preserve the inspected archive position");
}
async function exerciseNotificationChannels({fixture, click, fieldValue, wait, evaluate}) {
  await wait('document.querySelector("#notification-email-form [type=submit]") && !document.querySelector("#notification-email-form [type=submit]").disabled', "Configured email delivery form");
  await fieldValue("#notification-email-form", "email", "test@example.test");
  await click('#notification-email-form [type="submit"]');
  const formId = "notification-verify-00000000-0000-4000-8000-000000000801";
  await wait(`document.querySelector("#${formId} [type=submit]") && !document.querySelector("#${formId} [type=submit]").disabled`, "Pending verified-email channel");
  assert.equal(fixture.notificationChannels[0].status, "pending", "Request alone cannot opt an unverified address into delivery");
  await fieldValue(`#${formId}`, "code", "000000");
  await click(`#${formId} [type="submit"]`);
  await wait('document.querySelector("#notification-message").textContent.length>0', "Wrong verification code is visible");
  await fieldValue(`#${formId}`, "code", "123456");
  await click(`#${formId} [type="submit"]`);
  await until(() => fixture.notificationChannels[0].status === "active", "Verified channel activation");
  await wait('!document.querySelector("#notification-settings form[id^=notification-verify]")', "Verified channel state is rendered");
  await click('#notification-settings [data-action="notification-revoke"]');
  await until(() => fixture.notificationChannels.length === 0, "Explicit channel opt-out");
  await wait('document.querySelector("#notification-settings").textContent.includes("Устройства и адреса пока не подключены")', "Revoked channel removed from UI");
  assert.ok(!await evaluate('document.querySelector("#notification-settings").textContent.includes("test@example.test")'), "Full address is never retained in channel display");
}
async function exerciseNotificationRetry({fixture, click, fieldValue, wait, evaluate}) {
  const retry = '#notification-settings [data-action="resource-retry"][data-resource="notifications"]';
  await wait(`document.querySelector(${JSON.stringify(retry)})`, "An initial notification failure has a resource-specific retry");
  assert.equal(await evaluate('document.querySelector("#view-settings .view-actions [data-action=refresh]").disabled'), true, "Broker collection is in its own cooldown");
  assert.equal(await evaluate(`document.querySelector(${JSON.stringify(retry)}).disabled`), false, "Reading notifications is independent of broker collection limits");
  const previousTime = await evaluate('document.querySelector("#preferences-form").elements.quiet_start.value');
  await fieldValue("#preferences-form", "quiet_start", "21:15");
  fixture.failNotifications = false;
  const before = fixture.requests.length;
  await click(retry);
  await wait('document.querySelector("#notification-email-form") && !document.querySelector("#notification-settings .notice.error")', "The retry restores the failed notification resource");
  const retried = fixture.requests.slice(before);
  assert.equal(retried.filter(item => item.path === "/api/notifications" && item.method === "GET").length, 1);
  assert.equal(retried.filter(item => item.path === "/api/workspace/refresh" && item.method === "POST").length, 0, "A notification read must not start portfolio collection");
  assert.equal(await evaluate('document.querySelector("#preferences-form").elements.quiet_start.value'), "21:15", "An unrelated unsaved settings draft survives resource recovery");
  await fieldValue("#preferences-form", "quiet_start", previousTime);
  fixture.failNotifications = true;
  await click('#notification-settings [data-action="notifications-reload"]');
  await wait(`document.querySelector(${JSON.stringify(retry)}) && document.querySelector("#notification-email-form")`, "A failed later read reports its error alongside the last known channels");
  fixture.failNotifications = false;
  await click(retry);
  await wait('!document.querySelector("#notification-settings .notice.error")', "A second successful read removes the actual error");
}
async function exerciseAnalyticsReadConsistency({fixture, click, wait, evaluate, checkLayout, screenshot, round}) {
  fixture.periodResults = {"1y": "123456", "1w": "7654"};
  await click('#sidebar-nav [data-route="analytics"]');
  await click('#view-analytics .screen-menu [data-screen="history"]');
  const metricValues = '[...document.querySelectorAll("#view-analytics .metric-grid .main-value")].map(item=>item.textContent)';
  await wait('document.querySelector("#view-analytics [data-history-period=\\"1y\\"]") && document.querySelector("#view-analytics .metric-grid .main-value").textContent.replace(/\\s/g, "").startsWith("123456")', "The initial year has its own financial result");
  fixture.holdWorkspace = true;
  fixture.failWorkspace = true;
  await click('#view-analytics [data-period="1w"]');
  await until(() => fixture.heldWorkspace.length > 0, "The selected week is loading");
  assert.deepEqual(await evaluate(metricValues), ["—", "—", "—", "—"], "The old year's totals cannot be displayed under the selected week");
  assert.equal(await evaluate('document.querySelectorAll("#view-analytics .chart-svg").length'), 0, "Charts from another period stay out of the selected-period view");
  fixture.holdWorkspace = false;
  fixture.heldWorkspace.splice(0).forEach(release => release());
  await wait('document.querySelector("#view-analytics [data-resource=workspace]")', "The failed week read exposes a targeted retry");
  assert.deepEqual(await evaluate(metricValues), ["—", "—", "—", "—"], "Failure does not relabel cached year totals as week data");
  assert.equal(await evaluate('document.querySelector("#view-analytics [data-period=\\"1w\\"]").getAttribute("aria-pressed")'), "true");
  await screenshot(`analytics-period-error-${round}-390.png`);
  fixture.failWorkspace = false;
  const before = fixture.requests.length;
  await click('#view-analytics [data-resource="workspace"]');
  await wait('document.querySelector("#view-analytics .metric-grid .main-value").textContent.replace(/\\s/g, "").startsWith("7654") && document.querySelector("#view-analytics [data-history-period=\\"1w\\"]")', "The successful retry displays only the selected week's snapshot");
  assert.ok(fixture.requests.slice(before).some(item => item.path === "/api/workspace" && new URLSearchParams(item.query).get("history_period") === "1w"));
  assert.equal(fixture.requests.slice(before).some(item => item.path === "/api/workspace/refresh" && item.method === "POST"), false);
  await checkLayout(`analytics-period-recovered-${round}-390`, {minCharts: 1});
}
async function exerciseSearchReadConsistency({fixture, click, fieldValue, wait, evaluate}) {
  fixture.holdPublicNews = true;
  await fieldValue("#global-search-form", "q", "older-query");
  await evaluate('document.querySelector("#global-search-form").requestSubmit()');
  await until(() => fixture.heldPublicNews.length === 1, "The general news feed is deliberately waiting");
  await until(() => fixture.requests.some(item => item.path === "/api/broker/tbank/instruments/search" && new URLSearchParams(item.query).get("q") === "older-query"), "The first query starts independently of that shared feed");
  await fieldValue("#global-search-form", "q", "newer-query");
  await evaluate('document.querySelector("#global-search-form").requestSubmit()');
  await wait('document.querySelector("#view-search .view-header").textContent.includes("newer-query")', "The current route query is visible during loading");
  await wait('document.querySelector("#view-search .search-result") && !document.querySelector("#view-search .loading-panel")', "The newer query finishes while the unrelated feed is still pending");
  const searches = fixture.requests.filter(item => item.path === "/api/broker/tbank/instruments/search");
  assert.deepEqual(searches.map(item => new URLSearchParams(item.query).get("q")), ["older-query", "newer-query"], "Each explicit route starts its own search without a shared-data gate");
  fixture.holdPublicNews = false;
  fixture.heldPublicNews.splice(0).forEach(release => release());
  await wait(`${completedResourceCount("/api/public/news")} > 0`, "The shared feed finally completes");
  assert.equal(fixture.requests.filter(item => item.path === "/api/broker/tbank/instruments/search").length, 2, "A late shared read cannot launch the old query again");
  assert.equal(await evaluate('document.querySelector("#global-search").value'), "newer-query");
  assert.ok(await evaluate('document.querySelector("#view-search .view-header").textContent.includes("newer-query")'));
  await click('#sidebar-nav [data-route="goals"]');
}
async function exerciseGoalSourceContract({fixture, click, wait, evaluate, screenshot, checkLayout, round}) {
  const goal = clone(serverContracts.goal_available);
  fixture.goals = [goal];
  fixture.goalPlans = {[goal.id]: {version: 1, document: clone(serverContracts.goal_plan_document), forecast: clone(serverContracts.goal_forecast_available)}};
  await click('#view-goals [data-action="refresh"]');
  await wait('document.querySelector("#view-goals [data-goal-plan]")', "Goal fixture uses the actual calculator's source schema");
  await click('#view-goals [data-goal-plan]');
  await wait('document.querySelector("#goal-plan-result .goal-forecast-source")', "The goal scenario names its starting amount and source");
  assert.ok(await evaluate('document.querySelector("#goal-plan-result").textContent.includes("Сумма в заданном сценарии")'));
  const sourceDate = await evaluate(`window.OmniUI.date(${JSON.stringify(serverContracts.goal_forecast_available.source_as_of)}, true)`);
  assert.ok((await evaluate('document.querySelector("#goal-plan-result .goal-forecast-source").textContent')).includes(sourceDate));
  await wait('document.querySelector("#goal-plan-result .chart-plot")?.getClientRects().length', "The model scenario has its own visible numerical chart");
  await checkLayout(`goal-scenario-${round}-390`, {minCharts: 1});
  await screenshot(`goal-scenario-${round}-390.png`);
  await click('#workspace-dialog [data-close-dialog]');
  fixture.goals[0] = clone(serverContracts.goal_stale);
  fixture.goalPlans[goal.id].forecast = clone(serverContracts.goal_forecast_stale);
  await click('#view-goals [data-goal-plan]');
  await wait('document.querySelector("#goal-plan-result .goal-forecast-source")', "The reopened goal loads its actual source after the dialog placeholder");
  const staleText = await evaluate('document.querySelector("#goal-plan-result").textContent');
  assert.ok(staleText.includes("Начальная сумма устарела"), "The real stale-source refusal is displayed without a scenario result");
  const staleDate = await evaluate(`window.OmniUI.date(${JSON.stringify(serverContracts.goal_forecast_stale.source_as_of)}, true)`);
  assert.ok(staleText.includes(staleDate), "The source's original date is retained, not replaced by today's calculation date");
  assert.ok(!staleText.includes("Сумма в заданном сценарии") && !staleText.includes("Условная модель вероятности"));
  await evaluate('document.querySelector("#goal-plan-result").scrollIntoView({behavior:"instant",block:"center"})');
  await screenshot(`goal-source-stale-${round}-390.png`);
  await click('#goal-plan-result [data-route="portfolio"]');
  await wait('!document.querySelector("#workspace-dialog").open && !document.querySelector("#view-portfolio").hidden', "The source-recovery action reaches the existing account controls");
}
async function exerciseResearchSubmission({fixture,click,fieldValue,wait,evaluate}) {
  await click('#sidebar-nav [data-route="strategies"]');
  await wait('document.querySelector("#research-form [type=submit]")?.disabled===false',"Research first reads durable status and capacity");
  for (const [name,value] of Object.entries({from_at:"2026-01-01",to_at:"2026-08-01",initial_capital_rub:"100000",commission_bps:"5",slippage_bps:"10"})) await fieldValue("#research-form",name,value);
  for (const prerequisite of ["draft_required", "snapshot_required"]) {
    fixture.researchPrerequisite = prerequisite;
    await click('#research-form [type="submit"]');
    await wait('document.querySelector("[data-research-state=failed]") && document.querySelector("#research-form [type=submit]").disabled===false', "An unmet prerequisite does not become an uncertain accepted request");
    assert.ok(await evaluate('document.querySelector("[data-research-state=failed]").textContent.includes("Исследование ещё не началось")'));
    const declined = fixture.requests.findLast(item => item.path === "/api/profile/strategy/research");
    assert.ok(!fixture.requests.some(item => item.path === `/api/research/requests/${declined.body.request_id}`), "An unstarted prerequisite result does not start status polling");
    assert.equal(fixture.researchRequests.size, 0);
  }
  fixture.researchPrerequisite = null;
  const postsBeforeLoss = fixture.requests.filter(item => item.path === "/api/profile/strategy/research").length;
  fixture.researchDropBeforeAccept=true;
  await click('#research-form [type="submit"]');
  await wait('document.querySelector("[data-research-state=not_found]")',"A lost request uses its exact UUID to check server acceptance");
  const original=fixture.requests.findLast(item=>item.path==="/api/profile/strategy/research");
  assert.ok(fixture.requests.some(item=>item.path===`/api/research/requests/${original.body.request_id}`));
  assert.equal(fixture.requests.filter(item=>item.path==="/api/profile/strategy/research").length,postsBeforeLoss+1,"A missing acknowledgment cannot automatically repeat POST");
  await click('[data-action="research-retry"]');
  await wait('document.querySelector("[data-research-state=completed]") && document.querySelector("#research-form [type=submit]").disabled===false',"Explicit retry recovers the same request");
  const replay=fixture.requests.findLast(item=>item.path==="/api/profile/strategy/research");
  assert.deepEqual(replay.body,original.body,"Explicit replay keeps both UUID and every original parameter");
  assert.equal(fixture.researchRuns.length,1);
  await click('[data-research-coverage] summary');
  const coverage=await evaluate('document.querySelector("[data-research-coverage]").textContent');
  assert.ok(coverage.includes("Выплаты из API источника") && coverage.includes("история размеров лота") && coverage.includes("НКД на открытие"));
  assert.ok(!coverage.includes("bond_nkd_open_close_timing"),"Missing evidence is explained in user language");
}
async function exerciseResearchEvidence({fixture,click,wait,evaluate}) {
  await click('[data-research-action="evidence"]');
  await wait('document.querySelector("#research-evidence-form")',"Evidence import opens its owned document");
  const before=fixture.requests.filter(item=>item.path==="/api/research/evidence" && item.method==="PUT").length;
  await evaluate(`(() => {
    const input=document.querySelector('#research-evidence-form input[type="file"]');
    const transfer=new DataTransfer();
    transfer.items.add(new File([' '.repeat(1100000),JSON.stringify({assets:[]})],'synthetic-evidence.json',{type:'application/json'}));
    input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));
  })()`);
  await wait('document.querySelector("#research-evidence-form").elements.document.value.length>1100000',"A valid JSON file above the former 1MiB client limit is accepted");
  assert.equal(fixture.requests.filter(item=>item.path==="/api/research/evidence" && item.method==="PUT").length,before,"Choosing a file does not silently save it");
  await click('#research-evidence-form [type="submit"]');
  await wait('document.querySelector("#research-evidence-form").dataset.version==="1"',"Explicit import receives the saved document version");
  assert.deepEqual(fixture.researchEvidence.document,{assets:[]},"Whitespace affects file size but cannot manufacture source evidence");
  assert.equal(await evaluate('document.querySelector("#research-evidence-form").elements.document.value'),'{"assets":[]}',"The editor retains one compact saved document");
  await click('#workspace-dialog [data-close-dialog]');
}
async function exerciseResearchReload({fixture,send,click,wait,evaluate}) {
  fixture.researchLoseAcknowledgment=true;
  await click('#research-form [type="submit"]');
  await wait('document.querySelector("[data-research-state=running]")',"An accepted request survives its lost POST acknowledgment");
  const request=[...fixture.researchRequests.values()].find(item=>item.status==="running");
  const posts=fixture.requests.filter(item=>item.path==="/api/profile/strategy/research").length;
  assert.equal(fixture.requests.filter(item=>item.path==="/api/profile/strategy/research" && item.body.request_id===request.id).length,1,"An accepted request with a lost acknowledgment is submitted only once");
  assert.equal(await evaluate('document.querySelector("#research-form [type=submit]").disabled'),true);
  assert.equal(await evaluate(`Object.values(localStorage).some(value=>value.includes(${JSON.stringify(request.id)})) || Object.values(sessionStorage).some(value=>value.includes(${JSON.stringify(request.id)}))`),false,"Private request IDs stay out of browser storage");
  const readsBeforeReload=fixture.requests.filter(item=>item.path===`/api/research/requests/${request.id}`).length;
  const previousDocumentTimeOrigin=await evaluate("performance.timeOrigin");
  await send("Page.reload",{ignoreCache:true});
  await wait(`performance.timeOrigin!==${previousDocumentTimeOrigin} && document.querySelector("[data-research-state=running]") && document.querySelector('[data-action="research-check"]')?.disabled===false`,"The new document restores the server recent_request with an exact status GET");
  const readsAfterReload=fixture.requests.filter(item=>item.path===`/api/research/requests/${request.id}`).length;
  assert.ok(readsAfterReload>readsBeforeReload,"The new document verifies the exact request ID before restoring its running state");
  assert.equal(fixture.requests.filter(item=>item.path==="/api/profile/strategy/research").length,posts,"Reload never resubmits research");
  const result=completeTestResearch(fixture,request);
  await wait('document.querySelector("[data-research-state=completed]") && document.querySelector("#strategy-research").textContent.includes("Нет достаточной истории")',"Only the identified archive result is restored");
  assert.ok(fixture.requests.filter(item=>item.path===`/api/research/requests/${request.id}`).length>readsAfterReload,"Restored research uses read-only polling to discover completion");
  assert.ok(fixture.requests.some(item=>item.path===`/api/research/runs/${result.archive.id}`));
  assert.equal(fixture.requests.filter(item=>item.path==="/api/profile/strategy/research").length,posts,"Completion polling never resubmits research");
  // Another tab deleted this archive; cleanup removes its terminal request
  // after the list response, but before the restored exact-ID status read.
  fixture.researchRuns=fixture.researchRuns.filter(item=>item.id!==result.archive.id);
  Object.assign(request,{status:"deleted",run_id:null});
  fixture.removeResearchRequestBeforeRead=request.id;
  const completedDocumentTimeOrigin=await evaluate("performance.timeOrigin");
  await send("Page.reload",{ignoreCache:true});
  await wait(`performance.timeOrigin!==${completedDocumentTimeOrigin} && document.querySelector("[data-research-state=missing]") && document.querySelector("#research-form [type=submit]").disabled===false`,"A restored missing tombstone cannot permanently block a new explicit run");
  assert.equal(await evaluate('Boolean(document.querySelector("[data-action=research-retry]"))'),false,"No original body means there is no exact-request replay action");
  assert.equal(fixture.requests.filter(item=>item.path==="/api/profile/strategy/research").length,posts,"Missing restored metadata never automatically creates a new request");
}
async function exerciseResearchLateResult({fixture,click,fieldValue,wait,evaluate}) {
  for (const [name,value] of Object.entries({from_at:"2026-01-01",to_at:"2026-08-01",initial_capital_rub:"100000",commission_bps:"5",slippage_bps:"10"})) await fieldValue("#research-form",name,value);
  fixture.researchHoldAcknowledgment=true;
  await click('#research-form [type="submit"]');
  await until(()=>fixture.researchHeldAcknowledgments.length===1,"The server saved the old version but its response is delayed");
  const version=fixture.selection.version;
  await fieldValue("#strategy-form","strategy.profile.reserve_rub","5000");
  await until(()=>fixture.selection.version>version,"A newer strategy is saved before the old research response arrives");
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved"',"New strategy save acknowledged");
  fixture.researchHoldAcknowledgment=false;
  fixture.researchHeldAcknowledgments.splice(0).forEach(release=>release());
  await wait('document.querySelector("[data-research-state=completed]")?.textContent.includes("ранее выбранным условиям")',"A late old-version result stays in the archive");
  assert.equal(await evaluate('location.hash'), '#account/strategies/editor', "A late research result cannot replace the page being edited");
  assert.equal(await evaluate('document.querySelector("#strategy-research").textContent.includes("Нет достаточной истории")'),false,"The old calculation cannot replace the current editor's result");
  await click('#view-strategies .screen-menu [data-screen="research"]');
  await wait('document.querySelector("#strategy-research")?.getClientRects().length', "Research status remains reachable on its own page");
}
async function exerciseResearchPagination({fixture,click,wait,evaluate,screenshot,checkLayout,round}) {
  fixture.billing=clone(serverContracts.billing_disabled);
  const count=serverContracts.billing_disabled.plans.personal.research_runs+1;
  fixture.researchRuns=Array.from({length:count},(_,index)=>({
    id:require("node:crypto").randomUUID(),created_at:new Date(Date.now()-index*1000).toISOString(),
    strategy_version:index===count-1?fixture.selection.version-1:fixture.selection.version,
    status:"insufficient_data",metrics:{},inputs:{},
    result:{status:"insufficient_data",reason:index===count-1?"Архивная контрольная запись":"Изолированные архивные данные"}
  }));
  await click('[data-research-action="archive"]');
  await wait('document.querySelectorAll("#research-archive [data-research-operation=open]").length===50',"The archive opens a bounded first page");
  assert.ok((await evaluate('document.querySelector("#research-archive").textContent')).includes(`${count} / ${serverContracts.billing_disabled.plans.personal.research_runs}`),"Expired paid capacity keeps older records accessible");
  fixture.failResearchPage=true;
  await click('[data-action="research-archive-more"]');
  await wait('document.querySelector("#research-archive .notice.error")',"A failed next page is visible");
  assert.equal(await evaluate('document.querySelectorAll("#research-archive [data-research-operation=open]").length'),50,"Failed pagination preserves already loaded records");
  fixture.failResearchPage=false;
  while(await evaluate('Boolean(document.querySelector("[data-action=research-archive-more]"))')) {
    const before=await evaluate('document.querySelectorAll("#research-archive [data-research-operation=open]").length');
    await click('[data-action="research-archive-more"]');
    await wait(`document.querySelectorAll("#research-archive [data-research-operation=open]").length>${before}`,"Next archive page appends without duplication");
  }
  assert.equal(await evaluate('document.querySelectorAll("#research-archive [data-research-operation=open]").length'),count);
  assert.equal(await evaluate('document.querySelector("#research-form [type=submit]").disabled'),true,"Only new runs are blocked by capacity");
  await screenshot(`research-archive-${round}-390.png`);
  await checkLayout(`research-archive-${round}-390`);
  const oldest=fixture.researchRuns.at(-1);
  await click(`[data-research-run="${oldest.id}"][data-research-operation="open"]`);
  await wait(`document.querySelector("#workspace-dialog").open && location.hash.includes("/strategies/result?run=${oldest.id}") && document.querySelector("#dialog-content").textContent.includes("Архивная контрольная запись")`,"The oldest retained record opens on its own route across the former 200-record boundary");
  assert.ok(await evaluate('document.querySelector("#dialog-content").textContent.includes("Архивная версия")'));
  await click('#workspace-dialog [data-close-dialog]');
  await wait('location.hash === "#account/strategies/archive" && document.querySelector("#research-archive")?.getClientRects().length', "Back returns from a research result to its archive");
}
async function exerciseOperatorCapability({fixture,send,base,round,wait,click,evaluate,screenshot,checkLayout}) {
  assert.equal(fixture.requests.some(item=>item.path==="/api/system/metrics"),false,"Ordinary signed-in users never request operator aggregates");
  fixture.canViewOperationalMetrics=true;
  await send("Page.navigate",{url:`${base}?case=signed-read-contracts-${round}&operator=1#settings`});
  await wait('document.querySelector("#operations-settings")?.textContent.includes("Требует внимания оператора")',"The explicit server capability enables the operator panel");
  await click('#view-settings .screen-menu [data-screen="operations"]');
  await wait('document.querySelector("#operations-settings")?.getClientRects().length', "Operator evidence is opened through its actual settings menu");
  const text=await evaluate('document.querySelector("#operations-settings").textContent');
  assert.ok(text.includes("Счета без своевременного обновления") && text.includes("Неопределённый результат отправки") && text.includes("Подтверждение запуска не получено"));
  assert.ok(!text.includes("worker_not_reported") && !text.includes("stale_success_accounts"),"Operator codes are translated into meaningful statuses");
  await evaluate(`(() => {
    const panel=document.querySelector("#operations-settings");
    panel.querySelectorAll("details").forEach(item=>item.open=false);
    panel.scrollIntoView({behavior:"instant",block:"start"});
    window.scrollBy({top:-16,behavior:"instant"});
  })()`);
  await screenshot(`operator-status-${round}-390.png`);
  await checkLayout(`operator-status-${round}-390`);
  for (const [name,sectionIndex,workerIndex] of [
    ["collection",0,-1],["delivery",1,-1],
    ["workers-notifications",2,0],["workers-refresh",2,1],["workers-daily",2,2]
  ]) {
    const visible=await evaluate(`(() => {
      const sections=[...document.querySelectorAll("#operations-settings > details")];
      sections.forEach((item,index)=>item.open=index===${sectionIndex});
      const section=sections[${sectionIndex}];
      const target=${workerIndex} < 0 ? section : section.querySelectorAll(":scope > div")[${workerIndex}];
      target.scrollIntoView({behavior:"instant",block:"center"});
      const rect=target.getBoundingClientRect();
      return rect.top>=0 && rect.bottom<=document.querySelector("#mobile-nav").getBoundingClientRect().top;
    })()`);
    assert.ok(visible,"The focused operator evidence fits above mobile navigation: "+name);
    await screenshot(`operator-${name}-${round}-390.png`);
  }
  const before=fixture.requests.filter(item=>item.path==="/api/system/metrics").length;
  fixture.canViewOperationalMetrics=false;
  await evaluate('document.querySelector("#main-content").focus(); window.dispatchEvent(new Event("focus"))');
  await wait('!document.querySelector("#operations-settings")',"Capability revocation removes cached operator data");
  await click('#sidebar-nav [data-route="profile"]');
  await click('#sidebar-nav [data-route="settings"]');
  await wait('document.querySelector("#preferences-form")',"Ordinary settings remain available after operator revocation");
  assert.equal(fixture.requests.filter(item=>item.path==="/api/system/metrics").length,before,"A revoked capability prevents future aggregate reads");
}
async function exerciseReadConsistency(options) {
  const {send, configureViewport, round, base, wait, evaluate} = options;
  await configureViewport(390);
  const key = `signed-read-contracts-${round}`;
  const fixture = makeFixture("signed");
  fixture.failNotifications = true;
  fixture.refreshStatus.can_refresh = false;
  fixture.refreshStatus.retry_after_seconds = 1800;
  fixture.refreshStatus.cooldown_until = new Date(Date.now() + 1800000).toISOString();
  fixtures.set(key, fixture);
  const previousDocumentTimeOrigin = await evaluate("performance.timeOrigin");
  await send("Page.navigate", {url: `${base}?case=${key}#settings`});
  await wait(`performance.timeOrigin!==${previousDocumentTimeOrigin} && document.querySelector("#preferences-form")`, "A fresh signed-in settings document");
  const context = {...options, fixture};
  await exerciseNotificationRetry(context);
  await exerciseAnalyticsReadConsistency(context);
  await exerciseSearchReadConsistency(context);
  await exerciseGoalSourceContract(context);
  await exerciseResearchSubmission(context);
  await exerciseResearchEvidence(context);
  await exerciseResearchReload(context);
  await exerciseResearchLateResult(context);
  await exerciseResearchPagination(context);
  await exerciseOperatorCapability(context);
  console.log(`PASS read contracts round ${round}: resource retry, period isolation, search ordering, and source age from the real calculator`);
}
async function serveTestSessions({fixture, path, method, body, response}) {
  fixture.sessions ||= [{id:"00000000-0000-0000-0000-000000000991", current:true, auth_provider:"vkid", created_at:stamp, last_seen_at:stamp, expires_at:new Date(Date.now()+86400000).toISOString()}, {id:"00000000-0000-0000-0000-000000000992", current:false, auth_provider:"tid", created_at:stamp, last_seen_at:stamp, expires_at:new Date(Date.now()+86400000).toISOString()}];
  if (method === "GET") return sendJSON(response, {sessions:clone(fixture.sessions), total:fixture.sessions.length, truncated:false});
  if (path.endsWith("/revoke-others")) fixture.sessions = fixture.sessions.filter(item=>item.current);
  else if (path.endsWith("/revoke")) fixture.sessions = fixture.sessions.filter(item=>item.id!==body.session_id || item.current);
  return sendJSON(response,{revoked:true});
}
async function serveTestGoalPlan({fixture,path,method,body,response}) {
  const id = path.split("/").at(-2);
  const goal = fixture.goals.find(item=>item.id===id);
  if (!goal) return sendJSON(response,{detail:"workspace_item_not_found"},404);
  fixture.goalPlans ||= {};
  let plan=fixture.goalPlans[id] || {version:0,document:null,forecast:null};
  if(method==="PUT") {
    if(body.expected_version!==plan.version || body.expected_goal_version!==goal.version) return sendJSON(response,{detail:"settings_version_conflict"},409);
    if(fixture.holdGoalPlanSave) await new Promise(resolve => {fixture.releaseGoalPlanSave=resolve;});
    plan={version:plan.version+1,document:clone(body.document),forecast:clone(serverContracts.goal_forecast_available)};
    fixture.goalPlans[id]=plan;
  }
  return sendJSON(response,{...clone(plan),goal_id:id,goal_version:goal.version,goal_kind:goal.kind,applicable_fields:goal.kind === "income" ? ["monthly_income_rub","target_in_today_money","annual_inflation_percent"] : ["monthly_contribution_rub","annual_return_percent","annual_volatility_percent","target_in_today_money","annual_inflation_percent"]});
}
async function serveTestResearchArchive({fixture,path,method,body,url,response}) {
  fixture.researchEvidence ||= {version:0,document:{assets:[]}};
  if(path.endsWith("/evidence")) {
    if(method==="PUT") {
      if(body.expected_version!==fixture.researchEvidence.version) return sendJSON(response,{detail:"settings_version_conflict"},409);
      fixture.researchEvidence={version:fixture.researchEvidence.version+1,document:clone(body.document)};
    }
    return sendJSON(response,fixture.researchEvidence);
  }
  if (path.startsWith("/api/research/requests/")) {
    const id = path.split("/").at(-1);
    if (fixture.removeResearchRequestBeforeRead === id) {
      fixture.researchRequests.delete(id);
      delete fixture.removeResearchRequestBeforeRead;
    }
    const request = fixture.researchRequests.get(id);
    return sendJSON(response, request ? researchRequestDTO(request) : {detail: "research_request_not_found"}, request ? 200 : 404);
  }
  if (path === "/api/research/runs") return serveTestResearchPage({fixture,url,response});
  return serveTestResearchRecord({fixture,path,method,response});
}
async function serveTestResearchPage({fixture,url,response}) {
    const cursor = url.searchParams.get("cursor");
    if (cursor && fixture.failResearchPage) return sendJSON(response, {detail: "research_temporarily_unavailable"}, 503);
    const offset = cursor ? fixture.researchRuns.findIndex(item => item.id === cursor) + 1 : 0;
    if (cursor && !offset) return sendJSON(response, {detail: "research_cursor_not_found"}, 404);
    const limit = Number(url.searchParams.get("limit") || 50);
    const items = clone(fixture.researchRuns.slice(offset, offset + limit));
    const latest = [...fixture.researchRequests.values()].reverse();
    const recent = latest.find(item => item.status === "running") || latest[0];
    const limits = (fixture.billing || serverContracts.billing_disabled).entitlements;
    const payload = {items, next_cursor: offset + limit < fixture.researchRuns.length ? items.at(-1).id : null,
      capacity: {runs_used: fixture.researchRuns.length, runs_limit: limits.research_runs,
        storage_used_bytes: fixture.researchRuns.length * 1024, storage_limit_bytes: limits.research_storage_bytes},
      recent_request: recent ? researchRequestDTO(recent) : null};
    if (fixture.holdResearchReads) await new Promise(release => fixture.heldResearchReads.push(release));
    return sendJSON(response, payload);
}
function serveTestResearchRecord({fixture,path,method,response}) {
  const id = path.endsWith("/replay") ? path.split("/").at(-2) : path.split("/").at(-1);
  const item = fixture.researchRuns.find(row => row.id === id);
  if (!item) return sendJSON(response, {detail: "research_run_not_found"}, 404);
  if (method === "DELETE") {
    fixture.researchRuns = fixture.researchRuns.filter(row => row.id !== id);
    for (const request of fixture.researchRequests.values()) if (request.run_id === id) Object.assign(request, {status: "deleted", run_id: null});
    return sendJSON(response, {deleted: true});
  }
  if (path.endsWith("/replay")) return sendJSON(response, {verified: true});
  return sendJSON(response, item);
}
function serveTestExecutionPlans({fixture,path,body,response}) {
  if (path.endsWith("execution-capabilities")) return sendJSON(response, {shadow_enabled:true,sandbox_enabled:false,live_enabled:false,max_order_notional_rub:"25000",max_daily_notional_rub:"100000"});
  if (path.endsWith("/plan")) {
    assert.equal(body.expected_version, fixture.selection.version);
    assert.equal(body.mode, "shadow");
    const research = fixture.researchRuns.find(item => item.id === body.research_run_id);
    assert.ok(research, "The planner must use an owned research record");
    assert.equal(research.strategy_version,fixture.selection.version,"Research must describe the exact saved strategy");
    assert.ok(Date.now()-Date.parse(research.created_at)<86400000,"Research is within the 24-hour planning window");
    assert.equal(fixture.selection.document.profile.reserve_rub,"5000","Execution fixture needs an explicit known reserve");
    assert.equal(body.commission_bps, research.inputs.commission_bps);
    assert.equal(body.slippage_bps, research.inputs.slippage_bps);
    const payload={strategy_version:fixture.selection.version,nav_rub:"150000.25",cash_before_rub:"100000.25",cash_after_rub:"97998.25",reserve_rub:"5000",gross_turnover_rub:"2000",mode:"shadow",account_id:"synthetic-account",legs:[{action:"buy",instrument_uid:"synthetic-a",ticker:"SYNA",lots:2,lot_size:10,limit_price:"100",gross_amount_rub:"2000",commission_cap_rub:"2",tax_reserve_rub:"0"}]};
    const proposal={id:require("node:crypto").randomUUID(),version:1,status:"proposed",proposal_hash:createHash("sha256").update(JSON.stringify(payload)).digest("hex"),payload,expires_at:new Date(Date.now()+120000).toISOString()};
    fixture.executionProposals.push(proposal);
    return sendJSON(response, proposal);
  }
  const id=path.split("/").at(-2), proposal=fixture.executionProposals.find(item=>item.id===id);
  if(!proposal) return sendJSON(response,{detail:"execution_proposal_not_found"},404);
  assert.equal(body.proposal_version,proposal.version);
  assert.equal(body.proposal_hash,proposal.proposal_hash);
  assert.equal(body.expected_strategy_version,proposal.payload.strategy_version);
  let run=fixture.executions.find(item=>item.proposal_id===id);
  if(!run){run={id:require("node:crypto").randomUUID(),proposal_id:id,account_id:"synthetic-account",mode:"shadow",provider_environment:"prod",status:"created",error_code:null,created_at:stamp,updated_at:stamp,finished_at:null,legs:proposal.payload.legs.map((leg,index)=>({id:require("node:crypto").randomUUID(),leg_index:index,action:leg.action,instrument_uid:leg.instrument_uid,lots_requested:leg.lots,lots_executed:0,request_id:require("node:crypto").randomUUID(),provider_order_id:null,provider_status:null,status:"pending",submitted_at:null,last_checked_at:null,terminal_at:null}))};fixture.executions.push(run);}
  return sendJSON(response,{run:clone(run)});
}
async function serveTestBilling({fixture,path,method,body,response}) {
  fixture.billing ||= clone(serverContracts.billing_disabled);
  if(path==="/api/billing") return sendJSON(response,fixture.billing);
  if(path.endsWith("/checkout")) {
    assert.equal(typeof body.expected_offer,"string");assert.equal(Object.hasOwn(body,"amount_kopecks"),false);
    const existing=fixture.billing.payments.find(item=>item.id===body.request_id);
    if(existing)return sendJSON(response,existing);
    if(!fixture.billing.offer || body.expected_offer!==fixture.billing.offer.version)return sendJSON(response,{detail:"billing_offer_changed"},409);
    const payment={id:body.request_id,status:"pending",amount_kopecks:fixture.billing.offer.amount_kopecks,period_days:30,offer_version:body.expected_offer,created_at:stamp,updated_at:stamp,checkout_url:"https://securepayments.tinkoff.ru/synthetic-do-not-follow",entitlement_from:null,entitlement_until:null};
    fixture.billing.payments.push(payment);return sendJSON(response,payment);
  }
  const ident=path.split("/").at(-2), payment=fixture.billing.payments.find(item=>item.id===ident);
  if(!payment)return sendJSON(response,{detail:"workspace_item_not_found"},404);
  if(path.endsWith("/cancel"))payment.status="cancelled";
  else { payment.status="paid";payment.entitlement_from=stamp;payment.entitlement_until=new Date(Date.now()+30*86400000).toISOString();fixture.billing.plan="premium";fixture.billing.valid_until=payment.entitlement_until;fixture.billing.entitlements={...clone(fixture.billing.plans.premium),valid_until:payment.entitlement_until}; }
  return sendJSON(response,payment);
}
async function serveTestAssistantStatus({fixture,path,method,body,url,response}) {
  fixture.ai ||= {enabled:false,configured:false,status:"activation_disabled",connection_version:0,connection_source:"personal",provider:"ollama",base_url:"https://model.example.invalid",model:null,has_key:false,health:{status:"unchecked",checked_at:null},allowed_endpoints:["https://model.example.invalid"],max_message_length:4000,quota:{used:0,limit:30,remaining:30,resets_at:new Date(Date.now()+86400000).toISOString()}};
  fixture.conversations ||= [];
  if(path.endsWith("/status"))return sendJSON(response,fixture.ai);
  if(path==="/api/assistant/connection") {
    assert.equal(body.expected_version,fixture.ai.connection_version);
    if(method==="PUT"){Object.assign(fixture.ai,{configured:true,connection_version:fixture.ai.connection_version+1,provider:body.document.provider,base_url:body.document.base_url,model:body.document.model,has_key:Boolean(body.document.api_key)});}
    else Object.assign(fixture.ai,{configured:false,connection_version:fixture.ai.connection_version+1,has_key:false});
    return sendJSON(response,fixture.ai);
  }
  if(path.endsWith("/connection/check")) {fixture.ai.health={status:"healthy",checked_at:stamp};return sendJSON(response,fixture.ai);}
  if(path==="/api/assistant/conversations") {
    if(method==="POST"){const item={id:require("node:crypto").randomUUID(),title:body.title,version:0,messages:[],created_at:stamp,updated_at:stamp};fixture.conversations.push(item);return sendJSON(response,item,201);}
    return sendJSON(response,{items:fixture.conversations.map(({messages,...item})=>item),total:fixture.conversations.length,truncated:false});
  }
  fixture.assistantMemory ||= [];
  if (path === "/api/assistant/memory" || path.startsWith("/api/assistant/memory/")) {
    const id = path === "/api/assistant/memory" ? body?.id : path.split("/").at(-1);
    const item = fixture.assistantMemory.find(row => row.id === id);
    if (method === "GET") return sendJSON(response,{items:clone(fixture.assistantMemory),total:fixture.assistantMemory.length});
    if (method === "DELETE") { if (!item || item.version !== body.expected_version) return sendJSON(response,{detail:"settings_version_conflict"},409); fixture.assistantMemory = fixture.assistantMemory.filter(row=>row.id!==id); return sendJSON(response,{deleted:true}); }
    if (body.confirmed !== true || body.expected_version !== (item?.version || 0)) return sendJSON(response,{detail:"settings_version_conflict"},409);
    const saved = {id,content:body.content,category:body.category,version:(item?.version || 0)+1,created_at:item?.created_at || stamp,updated_at:stamp};
    fixture.assistantMemory = [...fixture.assistantMemory.filter(row=>row.id!==id),saved];
    return sendJSON(response,saved);
  }
  if (path === "/api/assistant/sources/search") return sendJSON(response,{items:body.context === "investment" ? [{id:"fixture-source",kind:"portfolio",label:"Fixture portfolio source",sha256:"a".repeat(64),scope:"selected_sources",observed_at:stamp,excerpt:"Recorded source amount 150000.5"}] : [],total:body.context === "investment" ? 1 : 0,scope:"selected_sources",web_search:false,truncated:false});
  if (path === "/api/assistant/sources/read") {
    if (body.request_id) {
      const message = fixture.conversations.flatMap(item=>item.messages).find(item=>item.request_id===body.request_id && item.role==="assistant");
      const source = message?.sources.find(item=>item.id===body.source_id);
      return sendJSON(response, source ? {...clone(source),immutable:true,web_search:false} : {detail:"assistant_source_not_found"}, source ? 200 : 404);
    }
    return sendJSON(response,{id:body.source_id,kind:"portfolio",label:"Fixture portfolio source",sha256:"a".repeat(64),scope:"selected_sources",content:{nav_rub:fixture.currentSourceValue || "150000.5",observed_at:stamp},web_search:false});
  }
  if (path.startsWith("/api/assistant/requests/")) {
    const id = path.split("/")[4], record = fixture.assistantRequests?.get(id);
    if (!record) return sendJSON(response,{detail:"assistant_request_not_found"},404);
    if (path.endsWith("/cancel")) {
      record.saved.status = "cancelled";
      const conversation = fixture.conversations.find(item=>item.id===record.saved.conversation_id);
      if (conversation) { conversation.latest_request = clone(record.saved); for (const message of conversation.messages) if (message.request_id === id) message.request_status = "cancelled"; }
      record.response.end(`event: cancelled\ndata: ${JSON.stringify({request_id:id,code:"assistant_request_cancelled"})}\n\n`);
    }
    return sendJSON(response,record.saved);
  }
  if(path==="/api/assistant/messages" || path==="/api/assistant/messages/stream"){
    assert.equal(Object.hasOwn(body,"history"),false,"Conversation history is loaded server-side");
    const conversation=fixture.conversations.find(item=>item.id===body.conversation_id);
    if(!conversation || conversation.version!==body.expected_version)return sendJSON(response,{detail:"settings_version_conflict"},409);
    assert.match(body.request_id,/^[a-f0-9-]{36}$/);
    if (path.endsWith("/stream") && fixture.holdAssistantStream) {
      const saved = {request_id:body.request_id,conversation_id:conversation.id,status:"running",reply_prefix:"Synthetic partial prefix",stream_sequence:1,sources:[],incomplete:true};
      conversation.messages.push({position:++conversation.version,role:"user",content:body.message,created_at:stamp,sources:[],request_status:"running",request_id:body.request_id});
      conversation.latest_request = clone(saved);
      fixture.assistantRequests ||= new Map(); fixture.assistantRequests.set(body.request_id,{saved,response});
      fixture.ai.quota.used++;
      response.setHeader("Content-Type","text/event-stream");
      response.write(`event: accepted\ndata: ${JSON.stringify({request_id:body.request_id,conversation_id:conversation.id})}\n\n`);
      response.write(`event: delta\ndata: ${JSON.stringify({request_id:body.request_id,reply_prefix:saved.reply_prefix,sequence:1,provisional:true})}\n\n`);
      return;
    }
    const sources = [{id:"fixture-answer-source",kind:"portfolio",label:"Synthetic saved source receipt",sha256:"b".repeat(64),content:{nav_rub:fixture.currentSourceValue || "150000.5",observed_at:stamp},scope:"selected_sources"},{label:"Legacy source receipt"}];
    conversation.messages.push({position:++conversation.version,role:"user",content:body.message,created_at:stamp,sources:[],request_status:"completed",request_id:body.request_id},{position:++conversation.version,role:"assistant",content:"Synthetic isolated model response",created_at:stamp,sources,request_status:"completed",request_id:body.request_id});
    fixture.ai.quota.used++;
    const result={reply:"Synthetic isolated model response",conversation_id:conversation.id,version:conversation.version,created_at:stamp,sources};
    if (path.endsWith("/stream")) {
      response.setHeader("Content-Type","text/event-stream");
      response.write(`event: accepted\ndata: ${JSON.stringify({request_id:body.request_id,conversation_id:conversation.id})}\n\n`);
      response.write(`event: delta\ndata: ${JSON.stringify({request_id:body.request_id,reply_prefix:"Synthetic isolated",sequence:1,provisional:true})}\n\n`);
      response.end(`event: complete\ndata: ${JSON.stringify({request_id:body.request_id,result})}\n\n`);
      return;
    }
    return sendJSON(response,result);
  }
  const id=path.split("/").at(-1),item=fixture.conversations.find(row=>row.id===id);
  if(!item)return sendJSON(response,{detail:"workspace_item_not_found"},404);
  if(method==="DELETE"){
    if(fixture.holdAssistantDelete) await new Promise(resolve => { fixture.releaseAssistantDelete=resolve; });
    fixture.conversations=fixture.conversations.filter(row=>row.id!==id);
    return sendJSON(response,{deleted:true});
  }
  const eligible=item.messages.filter(message=>!url.searchParams.has("before") || message.position<Number(url.searchParams.get("before")));
  const messages=eligible.slice(-50);return sendJSON(response,{...item,messages,next_before:eligible.length>50?messages[0].position:null});
}

async function exerciseAssistantAndBilling({fixture,click,fieldValue,wait,evaluate,checkLayout}) {
  await click('#view-assistant [data-screen="conversation"]');
  assert.equal(await evaluate('document.querySelector("#assistant-history-context").textContent === window.OMNICIO_I18N.t("assistant.history_context_help")'), true, "The context selector explains the history scope enforced by the server");
  await click('#view-assistant [data-screen="memory"]');
  await wait('document.querySelector("#assistant-memory-form")', "Explicit memory editor is available with AI disabled");
  await fieldValue("#assistant-memory-form", "content", "Prefer explanations with source timestamps");
  const writesBeforeMemory = fixture.requests.filter(item => item.method === "POST" && item.path === "/api/assistant/memory").length;
  await click('#assistant-memory-form [type="submit"]');
  assert.equal(fixture.requests.filter(item => item.method === "POST" && item.path === "/api/assistant/memory").length, writesBeforeMemory, "Memory requires explicit checkbox confirmation");
  await click('#assistant-memory-form [name="confirmed"]');
  await click('#assistant-memory-form [type="submit"]');
  await until(()=>fixture.assistantMemory?.length === 1, "Confirmed memory is saved independently of model activation");
  await wait('document.querySelector("[data-memory-edit]")', "Saved memory has an edit consumer");
  await click('[data-memory-edit]');
  await fieldValue("#assistant-memory-form", "content", "Keep source timestamps in explanations");
  await click('#assistant-memory-form [name="confirmed"]');
  await click('#assistant-memory-form [type="submit"]');
  await until(()=>fixture.assistantMemory[0]?.version === 2, "Memory edits use version preconditions");
  await click('#view-assistant [data-screen="sources"]');
  await wait('document.querySelector("#assistant-sources-form")', "Selected-source search has its own screen");
  await fieldValue("#assistant-sources-form", "context", "investment");
  await fieldValue("#assistant-sources-form", "query", "source");
  await click('#assistant-sources-form [type="submit"]');
  await wait('document.querySelector("[data-assistant-source]")', "Source search returns actual selected-source metadata");
  assert.equal(fixture.requests.filter(item=>item.path === "/api/assistant/messages/stream").length, 0, "Memory and source review never activate or call the external model");
  await click('[data-assistant-source]');
  await wait('document.querySelector(".source-document")?.textContent.includes("150000.5")', "Reading a selected source displays server-returned data");
  await click('#workspace-dialog [data-close-dialog]');
  await wait('!document.querySelector("#workspace-dialog").open', "Back closes source detail");
  await click('#view-assistant [data-screen="memory"]');
  await click('[data-memory-delete]');
  await click('[data-memory-delete-confirm]');
  await until(()=>fixture.assistantMemory.length === 0, "Confirmed deletion removes owned memory");
  await wait('!document.querySelector("#workspace-dialog").open', "Memory confirmation closes after the server result");
  await click('#view-assistant [data-action="assistant-connect"]');
  await wait('document.querySelector("#assistant-connection-form")',"Personal AI connection editor");
  await fieldValue("#assistant-connection-form","model","synthetic-model");
  await fieldValue("#assistant-connection-form","api_key","synthetic-private-key");
  await click('#assistant-connection-form [type="submit"]');
  await wait('document.querySelector("#assistant-connection-form")?.dataset.version==="1"',"AI connection save readback");
  assert.equal(await evaluate('document.querySelector("#assistant-connection-form").elements.api_key.value'),"","Stored provider key is never rendered");
  assert.equal(await evaluate('document.querySelector("[data-action=assistant-health]").disabled'),true,"Disabled activation cannot perform a provider probe");
  await click('#workspace-dialog [data-close-dialog]');
  fixture.ai.enabled=true;
  await click('#view-assistant [data-action="assistant-connect"]');
  await wait('document.querySelector("[data-action=assistant-health]")?.disabled===false',"Operator activation is read back");
  await click('#workspace-dialog [data-close-dialog]');
  await click('#view-assistant [data-action="assistant-new"]');
  await until(()=>fixture.conversations.length===1,"Create owned conversation");
  await wait('!document.querySelector("#assistant-form textarea").disabled',"Activated synthetic model");
  await fieldValue("#assistant-form","message","Explain my portfolio");
  await click('#assistant-form [type="submit"]');
  await wait('document.querySelector("#chat-messages").textContent.includes("Synthetic isolated model response")',"Durable assistant result");
  assert.equal(fixture.ai.quota.used,1);
  const last=fixture.requests.findLast(item=>item.path==="/api/assistant/messages/stream");
  assert.equal(last.body.context,"general");assert.equal(last.body.include_news,false);
  fixture.currentSourceValue = "999999999";
  await click('#chat-messages [data-assistant-source-request]');
  await wait('document.querySelector("#dialog-content .source-document")?.textContent.includes("150000.5")', "Saved answers open their original source facts");
  assert.equal(await evaluate('document.querySelector("#dialog-content .source-document").textContent.includes("999999999")'), false, "A newer portfolio value cannot replace the source of an older answer");
  const sourceRead = fixture.requests.findLast(item=>item.path === "/api/assistant/sources/read");
  assert.deepEqual(sourceRead.body, {source_id:"fixture-answer-source",request_id:last.body.request_id}, "Immutable source read carries its owning response ID");
  await click('#workspace-dialog [data-close-dialog]');
  await wait('!document.querySelector("#workspace-dialog").open', "Back restores the original conversation after source reading");
  fixture.holdAssistantStream = true;
  await fieldValue("#assistant-form", "message", "Exercise cancellation without a second send");
  await click('#assistant-form [type="submit"]');
  await wait('document.querySelector(".assistant-prefix")?.textContent === "Synthetic partial prefix"', "Incremental prefix is rendered from the SSE payload");
  assert.ok(await evaluate('document.querySelector(".assistant-stream").textContent.includes("Предварительный текст")'), "Unfinished text cannot appear as a confirmed answer");
  const cancelRequest = fixture.requests.findLast(item=>item.path === "/api/assistant/messages/stream").body.request_id;
  await click('[data-action="assistant-cancel"]');
  await until(()=>fixture.assistantRequests.get(cancelRequest)?.saved.status === "cancelled", "Stop calls the explicit server cancellation endpoint");
  await wait('document.querySelector(".assistant-stream")?.textContent.includes("Запрос остановлен") && !document.querySelector("#assistant-form textarea").disabled', "Cancellation state is read back and the editor is released");
  await click('[data-action="assistant-request-read"]');
  assert.equal(fixture.requests.filter(item=>item.path === "/api/assistant/messages/stream").length, 2, "Readback and cancellation cannot silently resend the question");
  await fieldValue("#assistant-form", "message", "");
  fixture.holdAssistantStream = false;
  await click('#sidebar-nav [data-route="home"]');
  await click('#sidebar-nav [data-route="assistant"]');
  await wait('document.querySelector("#chat-messages").textContent.includes("Synthetic isolated model response")',"History returns after navigation");
  await click('#view-assistant [data-action="chat-clear"]');
  await click('#workspace-dialog [data-action="assistant-delete-confirm"]');
  await until(()=>fixture.conversations.length===0,"Delete owned conversation");
  assert.equal(fixture.ai.quota.used,2,"Deleting conversation does not reset accepted request quota");
  await wait('!document.querySelector("#workspace-dialog").open && document.querySelector("[data-action=assistant-new]")?.disabled===false',"Deletion finishes in the original dialog");
  await click('#view-assistant [data-action="assistant-new"]');
  await until(()=>fixture.conversations.length===1,"Create conversation for deletion race");
  await wait('document.querySelector("[data-action=chat-clear]")',"New conversation becomes selected");
  fixture.holdAssistantDelete=true;
  await click('#view-assistant [data-action="chat-clear"]');
  await click('#workspace-dialog [data-action="assistant-delete-confirm"]');
  await until(()=>typeof fixture.releaseAssistantDelete==="function","Deletion request is pending");
  await click('#workspace-dialog [data-close-dialog]');
  await click('#view-assistant [data-action="assistant-connect"]');
  await wait('document.querySelector("#assistant-connection-form")',"Another dialog opens while deletion is pending");
  fixture.holdAssistantDelete=false;
  fixture.releaseAssistantDelete();
  await until(()=>fixture.conversations.length===0,"Delayed deletion is confirmed");
  await wait('document.querySelector("[data-action=assistant-new]")?.disabled===false',"Deletion result updates the original conversation");
  assert.equal(await evaluate('document.querySelector("#workspace-dialog").open && Boolean(document.querySelector("#assistant-connection-form"))'),true,"Late conversation deletion cannot close a different dialog");
  await click('#workspace-dialog [data-close-dialog]');
  await click('#sidebar-nav [data-route="profile"]');
  await wait('document.querySelector("#view-profile [data-session-revoke]")',"Own session list");
  const other=fixture.sessions.find(item=>!item.current);
  await click(`#view-profile [data-session-revoke="${other.id}"]`);
  await until(()=>fixture.sessions.length===1,"Revoke another session");
  fixture.billing.configured=true;fixture.billing.offer=clone(serverContracts.billing_enabled.offer);
  await click('#view-profile .screen-menu [data-screen="plan"]');
  await wait('document.querySelector("#billing-checkout-form")',"Configured hosted checkout");
  const comparison=await evaluate('[...document.querySelectorAll(".plan-comparison tbody tr")].map(row=>[...row.querySelectorAll("td")].map(cell=>cell.textContent))');
  assert.deepEqual(comparison[0],[String(serverContracts.billing_enabled.plans.personal.research_runs),String(serverContracts.billing_enabled.plans.premium.research_runs)],"The two archive limits come from the actual billing contract");
  assert.ok(comparison[1][0].includes(String(serverContracts.billing_enabled.plans.personal.research_storage_bytes/1048576)) && comparison[1][1].includes(String(serverContracts.billing_enabled.plans.premium.research_storage_bytes/1048576)),"Storage is shown in MiB from the server's entitlement values");
  await fieldValue("#billing-checkout-form","receipt_email","receipt@example.test");
  await click('#billing-checkout-form [name="accept_offer"]');
  await click('#billing-checkout-form [type="submit"]');
  await wait('[...document.querySelectorAll("#dialog-content a")].some(link => link.href.startsWith("https://securepayments.tinkoff.ru/"))',"Signed server checkout link");
  assert.equal(fixture.billing.plan,"personal","A checkout link alone never activates a plan");
  await click('#dialog-content [data-billing-operation="reconcile"]');
  await until(()=>fixture.billing.plan==="premium","Only bank confirmation activates entitlement");
  await wait('document.querySelector("#dialog-content").textContent.includes("Premium")',"Confirmed plan readback");
  await checkLayout("payments-and-assistant");
  await click('#workspace-dialog [data-close-dialog]');
  await exercisePendingBillingCancellation({fixture, click, wait, evaluate});
  await exerciseBillingInitializationRecovery({fixture,click,wait,evaluate,checkLayout});
}
async function exercisePendingBillingCancellation({fixture, click, wait, evaluate}) {
  const pending = ["pending", "uncertain"].map(status => ({...clone(fixture.billing.payments[0]), id: require("node:crypto").randomUUID(), status, cancel_attempted_at: stamp, entitlement_from: null, entitlement_until: null}));
  fixture.billing.payments.push(...pending);
  await click('#view-profile .screen-menu [data-screen="plan"]');
  for (const payment of pending) {
    const selector = `#dialog-content [data-billing-id="${payment.id}"]`;
    await wait(`document.querySelector(${JSON.stringify(selector)})`, "Cancellation awaiting bank confirmation is visible: " + payment.status);
    const row = await evaluate(`(() => { const item=document.querySelector(${JSON.stringify(selector)}).closest('li'); return {text:item.textContent, checkout:Boolean(item.querySelector('a')), cancel:Boolean(item.querySelector('[data-billing-operation="cancel"]')), reconcile:Boolean(item.querySelector('[data-billing-operation="reconcile"]'))}; })()`);
    assert.ok(row.text.includes("Итог платежа пока не подтверждён") && row.text.includes("Сверить с банком"), "Payment cancellation directs the user to bank reconciliation");
    assert.ok(!row.text.includes("теневого плана") && !row.text.includes("модельные исполнения"), "Payment cancellation cannot display investment execution instructions");
    assert.deepEqual({checkout:row.checkout, cancel:row.cancel, reconcile:row.reconcile}, {checkout:false, cancel:false, reconcile:true}, "Unconfirmed cancellation offers readback without another payment or cancellation");
  }
  await click('#workspace-dialog [data-close-dialog]');
}
async function exerciseBillingInitializationRecovery({fixture,click,wait,evaluate,checkLayout}) {
  const original=fixture.billing.payments[0];
  const absent={...clone(original),id:require("node:crypto").randomUUID(),status:"uncertain",cancel_attempted_at:null,
    init_started_at:stamp,checkout_expires_at:day(1),recovery_not_before:new Date(Date.now()+60000).toISOString(),resolution:null};
  const unsent={...clone(original),id:require("node:crypto").randomUUID(),status:"cancelled",checkout_url:null,init_started_at:null,
    resolution:"initialization_not_started",recovery_not_before:null};
  const resolved={...clone(unsent),id:require("node:crypto").randomUUID(),resolution:"provider_order_absent"};
  fixture.billing.payments.push(absent,unsent,resolved);
  const before=fixture.requests.length;
  await click('#view-profile .screen-menu [data-screen="plan"]');
  await wait('document.querySelector("#dialog-content").textContent.includes("отправка запроса на оплату в банк не начиналась")',"An unsent initialization has its actual local resolution");
  const text=await evaluate('document.querySelector("#dialog-content").textContent');
  assert.ok(text.includes("Результат начала оплаты не подтверждён") && text.includes("подтверждающих проверок банка"),"Ambiguous and resolved initialization have distinct explanations");
  const deadline=await evaluate(`window.OmniUI.date(${JSON.stringify(absent.recovery_not_before)},true)`);
  assert.ok(text.includes(deadline),"The earliest safe reconciliation time is explicit");
  const row=await evaluate(`document.querySelector('[data-billing-id="${absent.id}"]').closest('li').querySelector('a')===null`);
  assert.equal(row,true,"Expired checkout URLs are never offered again");
  assert.equal(fixture.requests.slice(before).some(item=>item.method!=="GET"),false,"Opening a recovery state makes no payment, cancellation or reconciliation mutation");
  await checkLayout("billing-initialization-recovery");
  await click('#workspace-dialog [data-close-dialog]');
}
async function exerciseExecutionPlanner({fixture,click,fieldValue,wait,evaluate,screenshot,checkLayout,round}) {
  await fieldValue('#strategy-form','strategy.profile.reserve_rub','5000');
  await wait('document.querySelector("#view-strategies [data-action=execution-plan]")?.disabled===true',"Planner is blocked while edited parameters are unsaved");
  await until(()=>fixture.selection.document.profile.reserve_rub==="5000","Explicit reserve is saved before planning");
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved" && document.querySelector("#view-strategies [data-action=execution-plan]")?.disabled===false',"Planner becomes available after the same strategy version is acknowledged");
  fixture.researchRuns=[{id:require("node:crypto").randomUUID(),strategy_version:fixture.selection.version,status:"computed",created_at:new Date().toISOString(),metrics:{net_return_percent:"1.25"},inputs:{commission_bps:"10",slippage_bps:"20"}}];
  const prepare = async () => {
    await click('#view-strategies .screen-menu [data-screen="plan"]');
    await wait('document.querySelector("#execution-plan-form")', "Saved research and current account planning inputs");
    await click('#execution-plan-form [type="submit"]');
    await wait('document.querySelector("#execution-review-consent")', "Review exact plan before confirmation");
  };
  await prepare();
  assert.equal(fixture.executions.length,0,"Calculating a plan cannot start execution");
  await click('#dialog-content [data-action="execution-confirm"]');
  await wait('document.querySelector("#execution-plan-message").classList.contains("error")',"Explicit review consent is required");
  assert.equal(fixture.requests.filter(item=>item.path.endsWith("/confirm")).length,0,"Missing consent cannot send confirmation");
  await screenshot(`execution-review-${round}-390.png`);
  await click('#execution-review-consent');
  await click('#dialog-content [data-action="execution-confirm"]');
  await wait('document.querySelector("#dialog-content [data-action=recovery-dispatch]") && !document.querySelector("#dialog-content [data-action=recovery-dispatch]").disabled', "Confirmation opens the newly persisted execution ID");
  assert.equal(fixture.executions.length,1);
  const run=fixture.executions[0],leg=run.legs[0];
  assert.equal(leg.lots_executed,0,"Confirmation alone cannot dispatch the first leg");
  await checkLayout("shadow-execution-before-dispatch-390");
  await click('#dialog-content [data-action="recovery-dispatch"]');
  await until(()=>leg.status==="shadow_filled","Explicit shadow dispatch records a simulated fill");
  assert.equal(run.status,"succeeded","Shadow completion uses the server terminal status");
  await wait('!document.querySelector("#dialog-content [data-action=recovery-dispatch]") && document.querySelector("#dialog-content").textContent.includes("Завершено")',"The acknowledged terminal plan displays completion and has no next-step action");
  const dispatched=fixture.requests.filter(item=>item.path.endsWith("/dispatch"));
  assert.equal(dispatched.length,1);
  assert.equal(dispatched[0].body.expected_leg_id,leg.id,"Dispatch carries the exact reviewed pending leg UUID");
  assert.equal(leg.provider_order_id,null,"Shadow dispatch never invents a real broker order ID");
  assert.equal(leg.lots_executed,leg.lots_requested);
  const shadowDetails = await evaluate('document.querySelector("#dialog-content").textContent');
  for (const label of ["ID заявки брокера", "Статус брокера", "Последняя сверка", "Запрошенная отмена подтверждается состоянием брокера"]) assert.ok(!shadowDetails.includes(label), "Shadow details do not imply broker state: " + label);
  assert.ok(shadowDetails.includes("Уже записанные модельные исполнения сохранятся в журнале"), "Shadow cancellation explains the separate model ledger");
  assert.ok(shadowDetails.includes(run.id) && shadowDetails.includes(leg.request_id), "Model execution and request IDs remain visible");
  await screenshot(`execution-shadow-result-${round}-390.png`);
  await click('#workspace-dialog [data-close-dialog]');
  await prepare();
  await click('#execution-review-consent');
  await click('#dialog-content [data-action="execution-confirm"]');
  await wait('document.querySelector("#dialog-content [data-action=recovery-cancel]") && !document.querySelector("#dialog-content [data-action=recovery-cancel]").disabled',"A second unfilled shadow plan can be cancelled");
  await click('#dialog-content [data-action="recovery-cancel"]');
  await click('#dialog-content [data-action="recovery-cancel-confirm"]');
  await until(()=>fixture.executions[1].status==="cancelled","Cancel closes the unfilled shadow plan");
  assert.equal(fixture.executions[1].legs[0].lots_executed,0);
  assert.equal(fixture.requests.filter(item=>item.path.endsWith("/dispatch")).length,1,"Cancelling a pending shadow plan cannot execute it");
  await click('#workspace-dialog [data-close-dialog]');
  await click('#view-strategies .screen-menu [data-screen="executions"]');
  await wait('document.querySelectorAll("#dialog-content [data-recovery-id]").length===2',"Both terminal plans remain in execution history");
  await click('#workspace-dialog [data-close-dialog]');
  fixture.holdResearchReads=true;
  await click('#view-strategies .screen-menu [data-screen="plan"]');
  await until(()=>fixture.heldResearchReads.length>0,"Delayed planner prerequisites are in flight");
  await click('#workspace-dialog [data-close-dialog]');
  fixture.holdResearchReads=false;
  fixture.heldResearchReads.splice(0).forEach(release=>release());
  await delay(250);
  assert.equal(await evaluate('document.querySelector("#workspace-dialog").open'),false,"A late prerequisite response cannot reopen a dismissed planner");
}
async function exerciseEnglishLocale({send,configureViewport,round,base,wait,click,evaluate,fieldValue,checkLayout,screenshot}) {
  await configureViewport(390);
  const key=`signed-language-${round}`,fixture=makeFixture("signed");
  fixture.prefs.document.display_name="Портфель · Тестовый пользователь";
  fixtures.set(key,fixture);
  await send("Page.navigate",{url:`${base}?case=${key}#settings`});
  await wait('document.querySelector("#preferences-form") && document.documentElement.lang==="ru"',"Initial Russian account interface");
  const profileName=fixture.prefs.document.display_name;
  await fieldValue("#preferences-form","locale","en");
  await click('#preferences-form [type="submit"]');
  await until(()=>fixture.prefs.document.locale==="en","Language choice is persisted to the server");
  await wait('document.documentElement.lang==="en" && document.querySelector("#view-settings h1").textContent==="Settings"',"English settings and document language");
  assert.equal(await evaluate('document.querySelector("#profile-name").textContent'),profileName,"Language switching preserves the exact user name");
  assert.equal(await evaluate('document.querySelector("#global-search").getAttribute("aria-label")'),"Search assets, companies, and news");
  await screenshot(`settings-english-${round}-390.png`);
  const labels={home:"Overview",portfolio:"Portfolio",market:"Market",strategies:"Strategies",assistant:"AI assistant",goals:"Goals",analytics:"Analytics",events:"Events",profile:"Profile",settings:"Settings"};
  for(const [view,label]of Object.entries(labels)) {
    await click(`#sidebar-nav [data-route="${view}"]`);
    await wait(`!document.querySelector('#view-${view}').hidden && document.querySelector('#sidebar-nav [data-route="${view}"] span').textContent===${JSON.stringify(label)}`,"English navigation: "+view);
    if(view==="home") {
      await wait('document.querySelector("#view-home .main-value").textContent.includes("150,000")',"English number formatting follows the saved language");
      assert.ok(await evaluate('document.querySelector("#view-home").textContent.includes("Тестовая компания")'),"Issuer names remain in their original language");
    }
    if(view==="strategies") {
      await click('#view-strategies .screen-menu [data-screen="catalog"]');
      await wait('document.querySelector("[data-select-strategy=balanced] strong").textContent==="Balanced"',"Canonical preset title is translated by ID");
      assert.equal(await evaluate('document.querySelector("#view-strategies .strategy-note").textContent'),"Allocation across asset classes with a preference for lower historical volatility.","The visible canonical preset description is translated exactly");
    }
    await checkLayout(`english-${view}-${round}-390`);
    await exerciseScreenPages({view, label: `english-${view}-${round}-390`, click, wait, evaluate, checkLayout, screenshot, width: 390});
  }
  const origin=await evaluate("performance.timeOrigin");
  await send("Page.reload");
  await wait(`performance.timeOrigin!==${origin} && document.documentElement.lang==="en" && document.querySelector("#preferences-form")`,"Saved English preference survives reload");
  assert.equal(await evaluate('document.querySelector("#profile-name").textContent'),profileName);
  await fieldValue("#preferences-form","locale","ru");
  await click('#preferences-form [type="submit"]');
  await until(()=>fixture.prefs.document.locale==="ru","Russian choice persists");
  await wait('document.documentElement.lang==="ru" && document.querySelector("#view-settings h1").textContent==="Настройки"',"Russian interface is restored without a reload");
  assert.equal(await evaluate('document.querySelector("#profile-name").textContent'),profileName);
  assert.equal(fixture.selection.version,1,"Changing language cannot mutate investment strategy versions");
  console.log(`PASS locale round ${round}: every tab, catalogue metadata, real-source names, numeric format, reload and reversible language choice`);
}
async function exerciseGoalPlan({fixture,click,fieldValue,wait}) {
  await click('#view-goals [data-goal-plan]');
  await wait('document.querySelector("#goal-plan-form")',"Saved goal assumptions editor");
  for(const [name,value] of Object.entries({monthly_contribution_rub:"100",annual_return_percent:"0",annual_volatility_percent:"0",annual_inflation_percent:"0"}))await fieldValue("#goal-plan-form",name,value);
  fixture.holdGoalPlanSave=true;
  await click('#goal-plan-form [type="submit"]');
  await until(()=>typeof fixture.releaseGoalPlanSave==="function","Goal plan save is pending");
  await wait('Array.from(document.querySelector("#goal-plan-form").elements).every(control=>control.disabled)',"All displayed assumptions are immutable during their save");
  fixture.holdGoalPlanSave=false;
  fixture.releaseGoalPlanSave();
  await wait('document.querySelector("#goal-plan-form").dataset.version==="1"',"Goal plan versioned save");
  await wait('Array.from(document.querySelector("#goal-plan-form").elements).every(control=>!control.disabled)',"Goal plan controls become editable after exact saved result");
  assert.equal(fixture.goalPlans[fixture.goals[0].id].document.monthly_contribution_rub,"100");
  await click('#goal-plan-form [data-close-dialog]');
  await click('#view-goals [data-goal-plan]');
  await wait('document.querySelector("#goal-plan-form")?.elements.monthly_contribution_rub.value==="100"',"Assumptions survive reopening");
  await click('#goal-plan-form [data-close-dialog]');
}
async function serveTestAuthLogout({
  fixture,
  response
}) {
  fixture.mode = "guest";
  response.statusCode = 204;
  return response.end();
}
async function exerciseCanonicalNavigation({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout}) {
  await configureViewport(390);
  const guestKey = `guest-canonical-${round}`;
  fixtures.set(guestKey, makeFixture("guest"));
  await send("Page.navigate", {url: `${base}?case=${guestKey}#demo/market/reference?currency=CNY&reference_period=1y`});
  for (let attempt = 0; attempt < 3; attempt += 1) {
    await wait('!document.querySelector("#view-market").hidden && !document.querySelector("#app-shell").hidden && document.querySelector("[name=cbr_currency]")?.value === "CNY"', "Demo deep link survives repeated reload");
    assert.equal(await evaluate('document.querySelector("#public-site").hidden'), true);
    assert.equal(await evaluate('document.querySelector("[name=cbr_period]").value'), "1y");
    assert.equal(await evaluate('location.hash'), "#demo/market/reference?currency=CNY&reference_period=1y");
    if (attempt < 2) { const origin = await evaluate("performance.timeOrigin"); await send("Page.reload"); await wait(`performance.timeOrigin !== ${origin}`, "A new demo document loaded"); }
  }
  await checkLayout(`canonical-demo-${round}`);
  await click('#view-market [data-screen="news"]');
  await wait('location.hash === "#demo/market/news" && document.querySelector("#view-market [data-screen-content=news]")?.getClientRects().length', "Market news is a standalone screen");
  assert.equal(await evaluate('document.querySelector("#view-market [data-screen-content=reference]").getClientRects().length'), 0, "Unselected data panels are not visible");
  await evaluate("history.back()");
  await wait('location.hash.includes("reference") && document.querySelector("[name=cbr_currency]").value === "CNY" && document.querySelector("[name=cbr_period]").value === "1y"', "Back restores currency and period");
  await click('[data-action="leave-tour"]');
  await wait('!document.querySelector("#public-site").hidden', "Leaving demo returns to the public root");
  await click('.public-nav [data-public-page="features"]');
  await wait('location.hash === "#public/features"', "Public menu is a page route");
  assert.deepEqual(await evaluate('[...document.querySelectorAll("#public-content > section")].filter(element=>element.getClientRects().length).map(element=>element.id)'), ["features"]);
  assert.equal(await evaluate("document.querySelectorAll('a[href^=\"/legal/\"][target=\"_blank\"]').length"), 0, "Internal legal pages keep browser Back available");
  await evaluate("history.back()");
  await wait('location.hash === "#public/welcome"', "Public page Back restores the welcome screen");
  const lateKey = `signed-late-session-${round}`;
  const late = makeFixture("signed"); late.holdMe = true; fixtures.set(lateKey, late);
  await send("Page.navigate", {url: `${base}?case=${lateKey}#public/welcome`});
  await until(()=>typeof late.releaseMe === "function", "Session verification is deliberately pending");
  await click('[data-action="tour"]');
  await click('#sidebar-nav [data-route="market"]');
  await click('#view-market [data-screen="reference"]');
  late.holdMe = false; late.releaseMe();
  await delay(250);
  assert.equal(await evaluate("location.hash"), "#demo/market/reference", "A late successful session response cannot override an explicit demo route");
  assert.equal(await evaluate('document.querySelector("#profile-name").textContent'), "Знакомство", "Demo does not display the authenticated account's name");
  const failureKey = `signed-session-retry-${round}`;
  const failure = makeFixture("signed"); failure.failMe = true; fixtures.set(failureKey, failure);
  await send("Page.navigate", {url: `${base}?case=${failureKey}#account/settings/broker`});
  await wait('document.querySelector("#startup-state [data-action=session-retry]")', "Temporary session failure has an explicit retry");
  assert.equal(await evaluate('document.querySelector("#public-site").hidden'), true, "A network error must not show an unauthenticated landing page");
  assert.equal(await evaluate("location.hash"), "#account/settings/broker");
  failure.failMe = false;
  await click('[data-action="session-retry"]');
  await wait('!document.querySelector("#app-shell").hidden && document.querySelector("#broker-settings")?.getClientRects().length', "Retry restores the requested settings screen");
  assert.equal(await evaluate('document.querySelector("#preferences-form")?.getClientRects().length || 0'), 0, "Broker settings do not expose the unrelated preference form");
  await click('#sidebar-nav [data-route="goals"]');
  await wait('document.querySelector("#view-goals [data-action=goal-create]")', "Goal list is ready");
  await click('#view-goals [data-action="goal-create"]');
  await wait('document.querySelector("#goal-form") && document.querySelector("#workspace-dialog").open', "Goal creation is an addressable screen");
  await fieldValue("#goal-form", "title", "Unsubmitted navigation draft");
  await fieldValue("#goal-form", "kind", "income");
  assert.ok((await evaluate("location.hash")).startsWith("#account/goals/create"));
  await evaluate('document.querySelector("#workspace-dialog").scrollTop = 180');
  await wait('history.state.dialogScroll > 100', "The routed form records its own scroll position");
  const dialogScroll = await evaluate('document.querySelector("#workspace-dialog").scrollTop');
  await click('#workspace-dialog [data-close-dialog]');
  await wait('!document.querySelector("#workspace-dialog").open && location.hash === "#account/goals"', "Back closes the form and restores the list");
  await evaluate("history.forward()");
  await wait('document.querySelector("#workspace-dialog").open && document.querySelector("#goal-form")?.elements.title.value === "Unsubmitted navigation draft"', "Forward restores the unsaved draft");
  assert.equal(await evaluate('document.querySelector("#goal-form").elements.progress_source.value'), "income", "Draft restoration rebuilds the source options for the restored goal kind");
  await wait(`Math.abs(document.querySelector("#workspace-dialog").scrollTop - ${dialogScroll}) < 2`, "Forward restores the long form's own scroll position");
  await fieldValue("#goal-form", "title", "");
  await fieldValue("#goal-form", "kind", "capital");
  await click('#workspace-dialog [data-close-dialog]');
  await wait('!document.querySelector("#workspace-dialog").open', "Draft was returned to its initial state");
  assert.equal(failure.requests.filter(item=>item.method === "POST" && item.path === "/api/goals").length, 0, "Navigating and restoring a draft cannot create a goal");
  console.log(`PASS canonical navigation round ${round}: repeated demo reload, public screens, Back, control restoration, late bootstrap, retry and draft history`);
}
async function exerciseIndependentPageLoads({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout}) {
  await configureViewport(390);
  const key = `signed-independent-reads-${round}`;
  const fixture = makeFixture("signed");
  fixture.holdPublicNews = true;
  fixture.holdNotifications = true;
  fixtures.set(key, fixture);
  await send("Page.navigate", {url: `${base}?case=${key}#account/asset?uid=synthetic-a`});
  await until(() => fixture.heldPublicNews.length === 1, "The asset page's unrelated general news request is held");
  await wait('document.querySelector("#view-asset .chart-plot")?.getClientRects().length && document.querySelector("#view-asset [data-market-quote] .main-value")?.textContent.includes("251,75")', "Quotes and the chart arrive before the general news feed");
  assert.equal(fixture.heldPublicNews.length, 1, "The unrelated response has not been released to make the chart pass");
  await checkLayout(`independent-asset-${round}`, {minCharts: 1});
  await fieldValue("#global-search-form", "q", "SYNA");
  await evaluate('document.querySelector("#global-search-form").requestSubmit()');
  await wait('document.querySelector("#view-search .search-result")?.getClientRects().length && !document.querySelector("#view-search .loading-panel")', "Instrument search also finishes independently of the general feed");
  assert.equal(fixture.heldPublicNews.length, 1);
  const newsId = "a".repeat(64);
  await evaluate(`location.hash = ${JSON.stringify("#account/events/news?news=" + newsId + "&news_source=public")}`);
  await wait('document.querySelector("#workspace-dialog").open && document.querySelector("#dialog-content").textContent.includes("Подтверждённый текст")', "A news deep link reads its own article without waiting for the general feed");
  assert.equal(fixture.heldPublicNews.length, 1);
  await click('#workspace-dialog [data-close-dialog]');
  await wait('!document.querySelector("#workspace-dialog").open', "The independent article returns through Back");
  fixture.holdPublicNews = false;
  fixture.heldPublicNews.splice(0).forEach(release => release());
  await click('#sidebar-nav [data-route="settings"]');
  await until(() => fixture.heldNotifications.length === 1, "Notification delivery is deliberately pending");
  await click('#view-settings .screen-menu [data-screen="support"]');
  await wait("document.querySelector('#workspace-support a[href^=\"mailto:\"]')?.getClientRects().length && !document.querySelector('#workspace-support .loading-panel')", "Support arrives before unrelated notification delivery");
  assert.equal(fixture.heldNotifications.length, 1);
  const completed = await evaluate(completedResourceCount("/api/notifications"));
  fixture.holdNotifications = false;
  fixture.heldNotifications.splice(0).forEach(release => release());
  await wait(`${completedResourceCount("/api/notifications")} > ${completed}`, "The delayed notification read completes after support");
  await wait("document.querySelector('#workspace-support a[href^=\"mailto:\"]')?.getClientRects().length && !document.querySelector('#workspace-support .loading-panel')", "A late background repaint preserves the loaded contact");
  assert.equal(await evaluate("location.hash"), "#account/settings/support");
  await checkLayout(`independent-support-${round}`);
  console.log(`PASS independent reads round ${round}: asset, search, article and support become usable before unrelated responses`);
}
async function exerciseStartupRecovery({send, configureViewport, base, wait, click, evaluate, checkLayout, screenshot}) {
  await configureViewport(390);
  const destination = "#account/settings/appearance";
  const missingKey = "signed-startup-missing";
  const missing = makeFixture("signed");
  missing.missingBundle = "/assets/i18n.js";
  fixtures.set(missingKey, missing);
  await send("Page.navigate", {url: `${base}?case=${missingKey}${destination}`});
  await wait('document.querySelector("#startup-state")?.dataset.status === "unavailable" && document.querySelector("[data-startup-reload]")?.getClientRects().length', "A missing translation bundle has an independent recovery screen");
  assert.equal(await evaluate("window.OMNICIO_I18N === undefined"), true, "The missing bundle is not replaced with a permissive mock translator");
  assert.equal(await evaluate("location.hash"), destination);
  assert.equal(missing.requests.length, 0, "Incompatible startup cannot read or mutate the account");
  await checkLayout("startup-missing-390");
  missing.missingBundle = "";
  const firstOrigin = await evaluate("performance.timeOrigin");
  await click("[data-startup-reload]");
  await wait(`performance.timeOrigin !== ${firstOrigin} && document.querySelector('#preferences-form [name="locale"]')?.getClientRects().length`, "An explicit startup retry reopens the requested personal page");
  assert.equal(await evaluate("location.hash"), destination);
  await wait("Boolean(navigator.serviceWorker.controller)", "The cache regression uses the actual installed service worker");
  await evaluate(`(async () => {
    const resource = "/assets/workspace.js?build=" + ${JSON.stringify(build)};
    const source = await (await fetch(resource)).text();
    const legacy = source + "\\n{const {compiledBuild, ...legacy} = window.OmniUI; window.OmniUI = Object.freeze(legacy);}";
    const cache = await caches.open("omnicio-public-" + ${JSON.stringify(build)});
    await cache.put(resource, new Response(legacy, {headers: {"Content-Type": "text/javascript"}}));
    await caches.open("synthetic-startup-preserved");
    sessionStorage.setItem("synthetic-startup-preserved", "retained");
  })()`);
  const cachedKey = "signed-startup-cached";
  const cached = makeFixture("signed");
  fixtures.set(cachedKey, cached);
  await send("Page.navigate", {url: `${base}?case=${cachedKey}${destination}`});
  await wait('document.querySelector("#startup-state")?.dataset.status === "unavailable"', "A cached workspace without a build marker is rejected before routing");
  assert.equal(await evaluate("window.OmniUI.compiledBuild === undefined && typeof window.OmniUI.parseRoute === 'function'"), true, "The marker itself is mandatory even when old exports happen to be callable");
  assert.equal(cached.requests.length, 0);
  const cachedOrigin = await evaluate("performance.timeOrigin");
  await screenshot("startup-cache-recovery-390.png");
  assert.equal(await evaluate("performance.timeOrigin"), cachedOrigin, "Startup recovery never starts an automatic reload cycle");
  await click("[data-startup-reload]");
  await wait(`performance.timeOrigin !== ${cachedOrigin} && window.OmniUI?.compiledBuild === ${JSON.stringify(build)} && document.querySelector('#preferences-form [name="locale"]')?.getClientRects().length`, "Manual recovery evicts the corrupted public cache and starts compatible modules");
  assert.equal(await evaluate("location.hash"), destination);
  assert.equal(await evaluate('sessionStorage.getItem("synthetic-startup-preserved")'), "retained", "Recovery does not clear session state");
  assert.equal(await evaluate('(async () => (await caches.keys()).includes("synthetic-startup-preserved"))()'), true, "Only OMNICIO public asset caches may be removed");
  await evaluate('(async () => {sessionStorage.removeItem("synthetic-startup-preserved");await caches.delete("synthetic-startup-preserved");})()');
  const htmlKey = "signed-startup-old-html";
  const html = makeFixture("signed");
  html.legacyHtml = true;
  html.missingBundle = "/version.js";
  fixtures.set(htmlKey, html);
  await send("Page.navigate", {url: `${base}?case=${htmlKey}${destination}`});
  await wait('document.querySelector("#startup-state")?.dataset.status === "unavailable" && document.querySelector("#public-site").hidden && document.querySelector("#app-shell").hidden', "Old HTML receives a newly created recovery surface and cannot show the obsolete homepage");
  assert.equal(html.requests.length, 0);
  assert.equal(await evaluate('document.querySelector("#startup-state img").getAttribute("src")'), "/assets/brand/omnicio-logo.png");
  assert.equal(await evaluate("window.OMNICIO_RELEASE === undefined"), true);
  html.legacyHtml = false;
  const htmlOrigin = await evaluate("performance.timeOrigin");
  await evaluate('void Object.defineProperty(window, "caches", {get() {throw new DOMException("Storage is unavailable", "SecurityError");}})');
  await click("[data-startup-reload]");
  await wait(`performance.timeOrigin !== ${htmlOrigin} && document.querySelector('#preferences-form [name="locale"]')?.getClientRects().length`, "Recovery still reloads if the public cache API is unavailable");
  assert.equal(await evaluate("location.hash"), destination);
  assert.equal(await evaluate("window.OMNICIO_RELEASE === undefined"), true, "Stamped script URLs and matching modules remain sufficient when version.js is unavailable");
  assert.ok(html.requests.length > 0 && html.requests.every(item => item.clientBuild === build), "The compiled build identifies API requests without optional release metadata");
  console.log("PASS startup recovery: missing bundle, legacy public cache, old HTML, unavailable cache API and preserved deep links");
}
async function exerciseSafeUpdate({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout}) {
  await configureViewport(390);
  const key = `signed-update-${round}`;
  const fixture = makeFixture("signed");
  fixture.serverBuild = `${build}-new-server`;
  fixtures.set(key, fixture);
  await send("Page.navigate", {url: `${base}?case=${key}#account/goals/create`});
  await wait('document.querySelector("#workspace-dialog").open && document.querySelector("#goal-form") && !document.querySelector("#dialog-update-banner").hidden', "A changed server build is visible inside a routed form");
  await fieldValue("#goal-form", "title", "Typed update draft");
  await fieldValue("#goal-form", "kind", "income");
  await fieldValue("#goal-form", "target_amount_rub", "123456.789");
  await fieldValue("#goal-form", "allocation_percent", "10");
  await click('#goal-form [type="submit"]');
  await wait('document.querySelector("#goal-message").classList.contains("error")', "A stale client explains the blocked mutation");
  assert.equal(fixture.requests.filter(item=>item.path === "/api/goals" && item.method === "POST").length, 0, "A stale build cannot send a new goal write");
  assert.ok(fixture.requests.every(item=>item.clientBuild === build), "Every API request identifies the actual browser build");
  await checkLayout(`update-review-${round}`);
  fixture.holdMe = true;
  const firstOrigin = await evaluate("performance.timeOrigin");
  await click('#dialog-update-banner [data-action="pwa-update"]');
  await until(()=>typeof fixture.releaseMe === "function", "The updated document verifies its profile before draft restoration");
  await wait(`performance.timeOrigin !== ${firstOrigin} && !document.querySelector("#startup-state").hidden`, "Explicit application update reloads the same route");
  const saved = await evaluate('JSON.parse(sessionStorage.getItem("omnicio-update-drafts"))');
  assert.equal(saved.public_id, fixture.user);
  assert.ok(saved.expires_at > Date.now() && saved.expires_at <= Date.now() + 1800000);
  assert.deepEqual(saved.drafts, {"goal-form:":{title:"Typed update draft",kind:"income",target_amount_rub:"123456.789",progress_source:"income",allocation_percent:"10"}}, "Only changed whitelisted inputs are stored; no saved snapshot or untouched API-backed field is included");
  assert.equal(await evaluate('Boolean(document.querySelector("#goal-form"))'), false, "Private forms are not restored before /api/me confirms the same profile");
  fixture.holdMe = false; fixture.releaseMe(); delete fixture.releaseMe;
  await wait('document.querySelector("#goal-form")?.elements.title.value === "Typed update draft"', "The verified profile receives its typed draft after update");
  assert.equal(await evaluate('document.querySelector("#goal-form").elements.target_amount_rub.value'), "123456.789");
  assert.equal(await evaluate('document.querySelector("#goal-form").elements.progress_source.value'), "income", "Updated goal forms restore a valid type-specific source");
  assert.equal(await evaluate('location.hash'), "#account/goals/create");
  assert.equal(await evaluate('sessionStorage.getItem("omnicio-update-drafts")'), null, "The temporary stored copy is consumed once");
  assert.equal(fixture.goals.length, 0, "Restoring fields never saves a goal automatically");
  const previousUser = fixture.user;
  fixture.holdMe = true;
  const secondOrigin = await evaluate("performance.timeOrigin");
  await click('#dialog-update-banner [data-action="pwa-update"]');
  await until(()=>typeof fixture.releaseMe === "function", "A changed session is deliberately awaiting verification");
  await wait(`performance.timeOrigin !== ${secondOrigin}`, "The second explicit update creates a new document");
  assert.equal(await evaluate('JSON.parse(sessionStorage.getItem("omnicio-update-drafts")).public_id'), previousUser);
  // Switch identity after the old document leaves, before the held verification replies.
  fixture.user = "000000124";
  fixture.holdMe = false; fixture.releaseMe(); delete fixture.releaseMe;
  await wait('document.querySelector("#workspace-dialog").open && document.querySelector("#goal-form")?.elements.title.value === ""', "A different verified profile cannot receive the previous draft");
  assert.equal(await evaluate('sessionStorage.getItem("omnicio-update-drafts")'), null);
  const expired = {version:1,public_id:fixture.user,expires_at:Date.now()-1,drafts:{"goal-form:":{title:"Expired draft"}}};
  await evaluate(`sessionStorage.setItem("omnicio-update-drafts", ${JSON.stringify(JSON.stringify(expired))})`);
  const thirdOrigin = await evaluate("performance.timeOrigin");
  await send("Page.reload");
  await wait(`performance.timeOrigin !== ${thirdOrigin} && document.querySelector("#goal-form")?.elements.title.value === ""`, "Expired drafts are discarded");
  const filtered = {version:1,public_id:fixture.user,expires_at:Date.now()+60000,drafts:{"goal-form:":{title:"Allowed field",credential:"NEVER_RESTORE",nav_rub:"999999999"},"assistant-form:":{context:"investment",include_news:true},"research-evidence-form:":{document:"NEVER_RESTORE"}}};
  await evaluate(`sessionStorage.setItem("omnicio-update-drafts", ${JSON.stringify(JSON.stringify(filtered))})`);
  const fourthOrigin = await evaluate("performance.timeOrigin");
  await send("Page.reload");
  await wait(`performance.timeOrigin !== ${fourthOrigin} && document.querySelector("#goal-form")?.elements.title.value === "Allowed field"`, "Restoration validates the field allowlist again");
  assert.equal(await evaluate('document.body.textContent.includes("NEVER_RESTORE")'), false);
  assert.equal(fixture.requests.filter(item=>!["GET","HEAD"].includes(item.method)).length, 0, "Build checks and draft restoration never replay a mutation");
  await fieldValue("#goal-form", "title", "");
  await click('#workspace-dialog [data-close-dialog]');
  await wait('!document.querySelector("#workspace-dialog").open', "The restored form can return through the normal Back control");
  await click('#sidebar-nav [data-route="assistant"]');
  await click('#view-assistant [data-screen="conversation"]');
  await wait('document.querySelector("#assistant-form")?.elements.context.value === "investment"', "The verified profile also restores the chosen assistant context");
  assert.equal(await evaluate('document.querySelector("#assistant-form").elements.include_news.disabled'), false, "Related assistant controls follow the restored context without a change event");
  assert.equal(await evaluate('document.querySelector("#assistant-form").elements.include_news.checked'), true);
  assert.equal(await evaluate('document.querySelector("#assistant-form").elements.research_run_id.disabled'), false);
  assert.equal(fixture.requests.filter(item=>!["GET","HEAD"].includes(item.method)).length, 0, "Restoring dependent controls cannot save preferences or send a question");
  await click('#assistant-form [name="include_news"]');
  await fieldValue("#assistant-form", "context", "general");
  await evaluate(`sessionStorage.setItem("omnicio-update-drafts", ${JSON.stringify(JSON.stringify(filtered))})`);
  await click('#profile-button');
  await click('#profile-menu [data-action="logout"]');
  await wait('!document.querySelector("#public-site").hidden && !document.querySelector("#workspace-dialog").open', "Logout finishes after the update tests");
  assert.equal(await evaluate('sessionStorage.getItem("omnicio-update-drafts")'), null, "Logout removes every stored update draft");
  console.log(`PASS safe update round ${round}: build guard, same-profile restoration, different-profile isolation, TTL, field allowlist and logout cleanup`);
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
const screenPages = {
  portfolio: [["history", 1, 0], ["structure", 0, 0], ["positions", 0, 1], ["income", 0, 0], ["operations", 0, 1]],
  market: [["reference", 1, 0], ["watchlist", 0, 0], ["positions", 0, 1], ["news", 0, 0]],
  strategies: [["catalog", 0, 0], ["editor", 0, 0], ["assessment", 0, 0], ["research", 0, 0]],
  analytics: [["history", 1, 0], ["performance", 0, 0], ["income", 0, 0], ["risk", 0, 0]],
  profile: [["personal", 0, 0], ["identities", 0, 0], ["sessions", 0, 0], ["delete", 0, 0]],
  settings: [["appearance", 0, 0], ["notifications", 0, 0], ["broker", 0, 0], ["recovery", 0, 0], ["about", 0, 0], ["support", 0, 0]],
  assistant: [["conversation", 0, 0], ["history", 0, 0], ["memory", 0, 0], ["sources", 0, 0]]
};
async function exerciseScreenPages({view, label, click, wait, evaluate, checkLayout, screenshot, width}) {
  for (const [screen, minCharts, minTables] of screenPages[view] || []) {
    await click(`#view-${view} .screen-menu [data-screen="${screen}"]`);
    const selector = `#view-${view} [data-screen-content="${screen}"]`;
    await wait(`location.hash.startsWith(${JSON.stringify(`#account/${view}/${screen}`)}) && document.querySelector(${JSON.stringify(selector)})?.getClientRects().length`, `${label}: open ${screen} through its menu`);
    if (minCharts) await wait(`document.querySelector(${JSON.stringify(selector + " .chart-plot")})?.getClientRects().length`, `${label}/${screen}: confirmed observations render a chart`);
    if (minTables) await wait(`document.querySelector(${JSON.stringify(selector + " .table-scroll tbody tr")})?.getClientRects().length`, `${label}/${screen}: real rows render a table`);
    const visible = await evaluate(`[...document.querySelectorAll(${JSON.stringify(`#view-${view} [data-screen-content]`)})].filter(element=>element.getClientRects().length).map(element=>element.dataset.screenContent)`);
    assert.ok(visible.length > 0 && visible.every(value => value === screen), `${label}/${screen}: only the selected information page is visible`);
    if (view === "strategies" && screen === "editor") assert.equal(await evaluate('Boolean(document.querySelector("#strategy-form")?.getClientRects().length)'), true, "The strategy editor has its own reachable page");
    if (view === "settings" && screen === "support") await wait("document.querySelector('#workspace-support a[href^=\"mailto:\"]')", "Support displays the configured user-initiated contact");
    await checkLayout(`${label}/${screen}`, {minCharts, minTables});
    if (width === 390 && (minCharts || minTables)) await screenshot(`${view}-${screen}-${label.replaceAll(/[^a-z0-9-]/gi, "-")}.png`);
  }
  if (screenPages[view]) {
    await click(`#sidebar-nav [data-route="${view}"]`);
    await wait(`location.hash === ${JSON.stringify(`#account/${view}`)}`, `${label}: return to section overview`);
  }
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
  fixture.extendedWorkflows = width === 390;
  fixture.holdMarketStream = width === 390;
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
    await exerciseScreenPages({view, label: `${view} ${round}/${width}`, click, wait, evaluate, checkLayout, screenshot, width});
  }
  assert.equal(await evaluate('document.querySelector("#assistant-form textarea").disabled'), true, "Disconnected AI cannot fabricate answers");
  if (width === 390) await exerciseAssistantAndBilling({fixture,click,fieldValue,wait,evaluate,checkLayout});
  await click('#sidebar-nav [data-route="market"]');
  await fieldValue("#global-search-form", "q", "SYNA");
  await evaluate('document.querySelector("#global-search-form").requestSubmit()');
  await wait('document.querySelector("#view-search .search-result")', "Real search response");
  await click('#view-search [data-asset]');
  await wait('document.querySelector("#view-asset .chart-svg")', "Asset chart");
  if (fixture.holdMarketStream) {
    await until(() => fixture.marketStreams?.size === 1, "The browser has opened the actual market event contract");
    await evaluate('document.querySelector("#view-asset .chart-svg").focus()');
    const focusedChart = await evaluate('document.activeElement.id');
    fixture.holdMarketStream = false;
    for (const response of fixture.marketStreams) response.write(serverContracts.instrument_market_event);
    await wait('document.querySelector("#view-asset [data-market-quote] .main-value").textContent.includes("251,75")', "A real server tick updates the displayed price while the chart is focused");
    assert.equal(await evaluate('document.activeElement.id'), focusedChart, "A quote tick preserves the chart being inspected");
  }
  await wait('document.querySelector("#view-asset [data-market-quote] .main-value").textContent.includes("251,75") && document.querySelector("#view-asset [data-market-source]").textContent.includes("Текущая котировка")', "FastAPI's market event changes the REST price from 250.25 to 251.75 and labels it live");
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
  if (width === 390) {
    await until(() => fixture.marketStreams?.size === 1, "Only the current instrument stream remains open");
    for (const response of fixture.marketStreams) response.write(serverContracts.instrument_status_event);
    await until(() => fixture.marketStreams.size === 0, "The server's terminal status closes the browser stream");
    await wait('document.querySelector("#view-asset [data-market-source]").textContent.includes("Восстанавливаем поток")', "The terminal source state remains visible while the chart has focus");
  }
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
  if (width === 390) await exerciseExecutionPlanner({fixture, click, fieldValue, wait, evaluate, screenshot, checkLayout, round});
  configureGoalCases(fixture, round, width);
  await exerciseGoalCRUD({
    fixture,
    click,
    fieldValue,
    wait,
    evaluate
  });
  await click('#sidebar-nav [data-route="events"]');
  if (width === 390) await exerciseEventArchive({fixture, click, fieldValue, wait, evaluate});
  await click('#view-events [data-action="events-read-all"]');
  await until(() => fixture.events.every(item => item.read_at), "Durable read receipts");
  await click('#sidebar-nav [data-route="settings"]');
  await wait('document.querySelector("#preferences-form")', "Preferences form");
  if (width === 390) await exerciseNotificationChannels({fixture, click, fieldValue, wait, evaluate});
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
  const browserStorage = await evaluate('({local:Object.keys(localStorage),session:Object.keys(sessionStorage),lastRoute:localStorage.getItem("omnicio-last-route")})');
  assert.deepEqual(browserStorage.session, [], "Private session data never enters sessionStorage");
  assert.ok(browserStorage.local.every(key => ["omnicio-theme", "omnicio-last-route"].includes(key)), "Only display preferences and a sanitized page route may enter localStorage");
  if (browserStorage.lastRoute) {
    assert.equal(browserStorage.lastRoute.includes("?"), false, "The persistent last page cannot include personal IDs or search values");
    assert.equal(await evaluate('localStorage.getItem("omnicio-last-route") === window.OmniUI.routeHash(window.OmniUI.resumeRoute(window.OmniUI.parseRoute(localStorage.getItem("omnicio-last-route"))))'), true, "The persistent page passes the same resume allowlist as startup");
  }
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
    editorPresent:Boolean(document.querySelector('#strategy-form')),
    editorVisible:Boolean(document.querySelector('#strategy-form')?.getClientRects().length)
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
  assert.equal(state.editorPresent, true, "Browsing sources preserves the current strategy form");
  assert.equal(state.editorVisible, false, "The current strategy editor has a separate page from its source catalogue");
  if (focused) assert.equal(state.focused, "strategy-tab-" + pane, "Keyboard tab selection preserves focus on the selected tab");
}
async function exerciseStrategyTabs({
  fixture,
  click,
  evaluate,
  send,
  wait
}) {
  await click('#view-strategies .screen-menu [data-screen="catalog"]');
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
  await fieldValue("#goal-form", "target_date", day(-365).slice(0,10));
  await click('#goal-form [type="submit"]');
  await until(() => fixture.goals.length === 1, "Create goal on server");
  if (fixture.goalWriteConsentAfterCommit) await reconcileGoalConsentError(options);
  await wait('!document.querySelector("#workspace-dialog").open', "Goal saved");
  assert.equal(fixture.goals[0].manual_amount_rub, "100");
  if (fixture.extendedWorkflows) await exerciseGoalPlan(options);
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
async function exerciseInterruptedRecoveryRead({fixture, click, wait, evaluate}) {
  fixture.holdExecutionReads = true;
  await click('[data-action="recovery-reload"]');
  await until(() => fixture.heldExecutionReads.length > 0, "Terminal history verification is in flight before pagehide");
  try {
    await evaluate('window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true}))');
    await wait('document.querySelector("#recovery-settings").textContent.includes("История исполнений недоступна") && !document.querySelector("#recovery-settings .loading-panel") && document.querySelector("#recovery-settings [data-action=recovery-reload]")?.disabled===false', "Aborted history readback ends loading with an explicit unknown state and retry");
    assert.equal(await evaluate('Boolean(document.querySelector("#recovery-settings .recovery-row"))'), false, "Cancelled verification cannot restore the previous terminal history as authoritative");
    assert.equal(await evaluate('document.querySelector("[data-action=disconnect-start]").disabled'), true, "Disconnect stays blocked after cancellation has finished, not only while loading");
  } finally {
    fixture.holdExecutionReads = false;
    fixture.heldExecutionReads.splice(0).forEach(release => release());
  }
  const historyReadsBeforeResume = fixture.requests.filter(item => item.method === "GET" && item.path === "/api/portfolio/executions").length;
  await evaluate('window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true}))');
  await until(() => fixture.requests.filter(item => item.method === "GET" && item.path === "/api/portfolio/executions").length > historyReadsBeforeResume, "Restored page starts a new execution readback");
  await wait('document.querySelector("#recovery-settings [data-action=recovery-reload]")?.disabled===false && !document.querySelector("#recovery-settings .loading-panel")', "Automatic page restoration finishes before a manual history retry");
  await click('[data-action="recovery-reload"]');
  await wait('document.querySelector(\'#recovery-settings [data-recovery-id="synthetic-run"] strong\')?.textContent==="Отменено" && document.querySelector("[data-action=disconnect-start]").disabled===false', "Only a new successful terminal readback restores disconnect after cancellation");
}
async function exerciseRefreshRecovery({
  fixture,
  click,
  wait,
  evaluate,
  checkLayout
}) {
  const creationCountBefore = fixture.requests.filter(item => item.method === "POST" && /proposals|advance|executions$/.test(item.path)).length;
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
  fixture.holdExecutionReads = true;
  await click('[data-action="recovery-reload"]');
  await until(() => fixture.heldExecutionReads.length > 0, "Execution history readback is in flight");
  try {
    assert.equal(await evaluate('document.querySelector("[data-action=disconnect-start]").disabled'), true, "Pending history readback blocks disconnect even when the previous history was terminal");
    assert.equal(await evaluate('Boolean(document.querySelector(\'[data-recovery-id="synthetic-run"]\'))'), false, "The active execution has not arrived before the held response");
  } finally {
    fixture.holdExecutionReads = false;
    fixture.heldExecutionReads.splice(0).forEach(release => release());
  }
  await wait('document.querySelector(\'[data-recovery-id="synthetic-run"]\')', "Authoritative active execution history");
  assert.equal(await evaluate('document.querySelector("[data-action=disconnect-start]").disabled'), true, "Active order blocks a simple broker disconnect");
  await click('[data-action="recovery-open"]');
  await wait('document.querySelector(".recovery-leg")', "Persisted execution details");
  assert.ok(await evaluate('document.querySelector(".recovery-leg").textContent.includes("ID заявки брокера") && document.querySelector(".recovery-leg").textContent.includes("synthetic-order")'), "Live recovery still displays the persisted broker order");
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
  await exerciseInterruptedRecoveryRead({fixture, click, wait, evaluate});
  await click('[data-action="mandate-revoke"]');
  await click('[data-action="mandate-revoke-confirm"]');
  await wait('!document.querySelector("#workspace-dialog").open && !document.querySelector("[data-action=mandate-revoke]")', "Server-side mandate revoked");
  assert.equal(fixture.mandate, null);
  assert.equal(fixture.requests.filter(item => item.method === "POST" && /proposals|advance|executions$/.test(item.path)).length, creationCountBefore, "Legacy recovery must never create or advance a plan");
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
