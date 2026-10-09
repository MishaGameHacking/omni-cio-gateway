/* Observable browser contracts, served by an isolated synthetic API. No production requests. */
"use strict";

const assert = require("node:assert/strict");
const vm = require("node:vm");
const {
  createHash,
  createECDH,
  randomUUID
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
const renderedResult = spawnSync(process.env.OMNICIO_PYTHON || "python", ["-c", "import json; from pathlib import Path; from omnicio import __version__; from omnicio.web_assets import render_web_assets; build='smoke-'+__version__; print(json.dumps({'version':__version__,'build':build,'assets':render_web_assets(Path('web'),build)}))"], {
  cwd: root,
  env: {...process.env, PYTHONPATH: join(root, "src")},
  encoding: "utf8",
  maxBuffer: 8 * 1024 * 1024
});
assert.equal(renderedResult.status, 0, "Browser assets use the production renderer: " + renderedResult.stderr);
const {version, build, assets: publicAssets} = JSON.parse(renderedResult.stdout);
const configRealm = vm.createContext({});
vm.runInContext(publicAssets["assets/config.js"], configRealm);
const clientConfig = configRealm.OMNICIO_CONFIG;
// Extracted production functions share the real config. Browser VMs model the
// actual window/globalThis alias instead of maintaining two unrelated globals.
const sourceContext = bindings => {
  const context = {C: clientConfig, OMNICIO_CONFIG: clientConfig, ...bindings.window, ...bindings};
  if (Object.hasOwn(bindings, "window")) context.window = context;
  return vm.createContext(context);
};
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
const pushFixtureCurve = createECDH("prime256v1");
pushFixtureCurve.generateKeys();
const pushFixtureKey = pushFixtureCurve.getPublicKey().toString("base64url");
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
    notificationDeliveries: [],
    pushConfigured: true,
    failPush: false,
    holdPush: false,
    heldPush: [],
    pushSequence: 0,
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
      news: clone(serverContracts.refresh_news_cases.not_requested.news),
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
  run: ({url,response,fixture}) => {
    const quote = fixture.precisionCase ? JSON.parse(fixture.precisionCase.market_event.split("\ndata: ")[1].trim()) : marketEvent;
    return sendJSON(response,{items:(url.searchParams.get("instrument_uids") || "").split(",").filter(Boolean).map(uid=>({...quote,instrument_uid:uid,metadata_status:"available"})),source:"T-Invest",observed_at:stamp,refresh_after_seconds:10});
  }
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
// A dropped public connection exercises the real worker fetch-failure path.
let publicNetworkUnavailable = false;
let unavailablePublicAsset = "";
const publicRequestDiagnostics = [];
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
    if (url.pathname.startsWith("/api/")) return await serveTestApiRequest(request, response, url);
    response.once("finish", () => {
      publicRequestDiagnostics.push({path: url.pathname, build: url.searchParams.get("build"), status: response.statusCode, responseBuild: response.getHeader("X-Omnicio-Build") || null, contentType: response.getHeader("Content-Type") || null, destination: request.headers["sec-fetch-dest"] || null});
      if (publicRequestDiagnostics.length > 100) publicRequestDiagnostics.shift();
    });
    if (publicNetworkUnavailable) { request.socket.destroy(); return; }
    const page = new URL(request.headers.referer || url.href);
    const fixture = fixtures.get((url.pathname === "/" ? url : page).searchParams.get("case"));
    if (unavailablePublicAsset === url.pathname || fixture?.missingBundle === url.pathname) {
      response.statusCode = 404;
      return response.end();
    }
    let path = url.pathname;
    if (path === "/") path = "/index.html";
    let file = join(root, "web", path.replace(/^\/assets\//, "").replace(/^\//, ""));
    if (path.startsWith("/assets/brand/")) file = path === "/assets/brand/omnicio-logo.png" ? join(root,"assets","brand","omnicio-logo.png") : join(root, "assets", "brand", "web", path.split("/").at(-1));
    const assetKey = path.replace(/^\//, "");
    const rendered = publicAssets[assetKey];
    if (rendered === undefined && (!file.startsWith(root) || !existsSync(file))) {
      response.statusCode = 404;
      return response.end();
    }
    response.setHeader("X-Omnicio-Build", build);
    response.setHeader("Content-Type", {
      ".html": "text/html; charset=utf-8",
      ".js": "text/javascript",
      ".css": "text/css",
      ".png": "image/png",
      ".webmanifest": "application/manifest+json"
    }[extname(file)] || "application/octet-stream");
    let content = rendered === undefined ? readFileSync(file) : rendered;
    if (path.startsWith("/legal/") && path.endsWith(".html")) content = content.toString("utf8").replaceAll("__OMNICIO_BUILD__", build);
    if (fixture?.legacyHtml && path === "/index.html") content = content.replace(/<main id="startup-state"[\s\S]*?<\/main>/, "").replace('<div id="public-site" hidden>', '<div id="public-site">');
    response.end(content);
  } catch (error) {
    response.statusCode = 500;
    response.end("Synthetic test server failure");
    console.error(error.message);
  }
});
const displayContracts = () => {
  const context = sourceContext({
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
  quotePrecisionContracts(ui);
  assetQuotePrecisionContracts(ui);
  quoteChartPrecisionContracts(ui);
  goalVersionContracts(ui);
  chartAxisContracts(ui);
  researchMathContracts(ui, context.window.OMNICIO_I18N);
  presetMathContracts(ui, context.window.OMNICIO_I18N);
  viewportSizeContracts();
  console.log("PASS display contracts: unknown values, source escaping, privacy, real-series requirements and locale");
};
function presetMathContracts(ui, i18n) {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  const strategyMethodLabels ="), app.indexOf("  const assessmentIsCurrent ="));
  const renderers = app.slice(app.indexOf("  function renderSelectionHTMLNotice("), app.indexOf("  function renderAssessmentValue("));
  const context = sourceContext({U: ui, T: i18n.t, H: i18n.html, esc: ui.escape,
    infoRows: ui.infoRows, format: ui.format, percent: ui.percent, money: ui.money, date: ui.date,
    number: ui.number, policyFields: () => [],
    renderFundamentalMetricsHTMLLi2: value => `<li>${ui.escape(context.requirement(value))}</li>`});
  vm.runInContext(source + renderers + "\nglobalThis.selection=selectionHTML; globalThis.requirement=humanRequirement; globalThis.amount=researchSourceAmount;", context);
  for (const locale of ["ru", "en"]) {
    ui.setLocale(locale);
    const ladder = context.selection(serverContracts.research_ladder_result.selection);
    assert.equal((ladder.match(/data-ladder-rung="/g) || []).length, 5);
    assert.ok(ladder.includes(ui.escape(i18n.t("research.ladder.rung_unfilled", {rung: 3}))));
    assert.ok(ladder.includes(ui.escape(ui.percent("60"))), "Missing years retain their actual cash allocation");
    const dividends = context.selection(serverContracts.research_dividend_result.selection);
    assert.ok(dividends.includes("data-dividend-coverage") && dividends.includes("600 USD"));
    assert.ok(dividends.includes(ui.escape(i18n.t("research.dividend.scope"))));
    assert.ok(!dividends.includes("[object Object]") && !dividends.includes("undefined") && !dividends.includes("NaN"));
    assert.equal(context.requirement("missing:cashflow_coverage_incomplete"), i18n.t("research.cashflow.coverage_incomplete"));
    assert.ok(context.requirement("missing:dividend_cashflow_coverage").includes(i18n.t("research.dividend.coverage_fact")));
  }
  assert.equal(context.amount("1000.0000000001", "USD"), "1000.0000000001 USD", "Coverage amounts retain source decimal precision");
  assert.equal(context.amount("600.000", "USD"), "600 USD");
  assert.equal(context.amount("NaN", "USD"), "—");
  console.log("PASS preset mathematics: actual calendar rungs, exact issuer cashflows, provenance and translated missing evidence");
}
function researchMathContracts(ui, i18n) {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const helpers = app.slice(app.indexOf("  const researchCashProjectionHTML ="), app.indexOf("  const researchWindowHTML ="));
  const freshnessCheck = app.slice(app.indexOf("  const assessmentIsCurrent ="), app.indexOf("  const renderAssessment ="));
  const context = sourceContext({U: ui, T: i18n.t, H: i18n.html, esc: ui.escape,
    infoRows: ui.infoRows, format: ui.format, percent: ui.percent, money: ui.money, date: ui.date,
    renderFundamentalMetricsHTMLLi2: value => `<li>${ui.escape(value)}</li>`, Date, Number});
  vm.runInContext(helpers + freshnessCheck + "\nglobalThis.renderOutcomes=researchOutcomesHTML; globalThis.renderCash=researchCashProjectionHTML; globalThis.renderWindow=researchOutcomeWindowHTML; globalThis.current=assessmentIsCurrent;", context);
  const result = serverContracts.research_outcomes_result;
  assert.equal(result.historical_outcomes.horizons[0].profit_frequency_percent, "50");
  for (const locale of ["ru", "en"]) {
    ui.setLocale(locale);
    const html = context.renderOutcomes(result);
    assert.ok(html.includes(ui.escape(i18n.t("research.outcomes.title"))));
    assert.ok(html.includes(ui.escape(i18n.t("research.outcomes.scope"))), "Observed frequency retains its non-forecast scope in both languages");
    assert.ok(html.includes(ui.escape(ui.percent("50"))));
    assert.ok(html.includes(ui.escape(i18n.t("research.outcomes.too_few"))), "Insufficient longer horizons retain their actual counts and reason");
    assert.ok(html.includes(ui.escape(i18n.t("research.outcomes.interval"))));
    assert.ok(!html.includes("undefined") && !html.includes("NaN"));
    const weekly = result.historical_outcomes.horizons[1];
    const unavailable = context.renderWindow({...weekly, profit_frequency_percent: "99.999"});
    assert.ok(!unavailable.includes("99.999"), "An unavailable estimate cannot become a displayed percentage even if a stale value is present");
    const cash = context.renderCash(serverContracts.research_cash_result);
    assert.ok(cash.includes(ui.escape(i18n.t("research.cash.no_observations"))));
    assert.ok(!cash.includes("chart-path") && !cash.includes("data-research-outcome-sessions"));
    const incomplete = context.renderCash(serverContracts.research_cash_incomplete_result);
    assert.ok(incomplete.includes(ui.escape(i18n.t("research.cash.conditions_missing"))));
  }
  const observed = Date.now();
  const assessment = {strategy_version: 7, captured_at: new Date(observed).toISOString(), valid_until: new Date(observed + 300000).toISOString(), checks: []};
  assert.equal(context.current(assessment, 7), true);
  assert.equal(context.current(assessment, 8), false, "A newer remote strategy version cannot inherit a still-recent old assessment");
  assert.equal(context.current({...assessment, captured_at: new Date(observed - 600000).toISOString(), valid_until: new Date(observed - 300000).toISOString()}, 7), false);
  assert.equal(context.current({...assessment, valid_until: undefined}, 7), false);
  assert.equal(context.current({...assessment, captured_at: new Date(observed + 60000).toISOString(), valid_until: new Date(observed + 360000).toISOString()}, 7), false);
  let clock = observed, expire;
  const panel = {innerHTML: ""};
  Object.assign(context, {state: {generation: 1, loading: new Set(), errors: {}, strategy: {assessment, server: {version: 7}}},
    Date: class extends Date { static now() { return clock; } }, setTimeout: callback => { expire = callback; return 1; }, clearTimeout() {},
    $: () => panel, freshness: ui.freshness, selectionHTML: () => "", renderAssessmentDetailsSummary: () => ""});
  const render = app.slice(app.indexOf("  const renderAssessment ="), app.indexOf("  const assessStrategy ="));
  vm.runInContext(render + "\nglobalThis.renderAssessmentNow=renderAssessment;", context);
  assert.ok(!context.renderAssessmentNow().includes("data-assessment-expired"));
  assert.equal(typeof expire, "function");
  clock += 300001;
  expire();
  assert.ok(panel.innerHTML.includes("data-assessment-expired"), "The assessment expires locally without a network refresh or form rerender");
  console.log("PASS research contracts: real calculator results, historical frequency limits, explicit cash model and expiring account assessment");
}
async function ledgerPaginationContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  async function loadLedgerPage()"), app.indexOf("  function supportAddress("));
  const state = {generation: 1, view: "portfolio", data: {ledger: {items: [{id: "old"}], next_cursor: "cursor-old"}}, errors: {}, loading: new Set(), resourceVersions: new Map([["ledger", 1]])};
  let resolveRead, requests = 0, merges = 0;
  const context = sourceContext({state, encodeURIComponent, isCancelled: () => false, renderPortfolio() {},
    api: () => { requests += 1; return new Promise(resolve => { resolveRead = resolve; }); },
    mergePage: (before, after) => { merges += 1; return {...after, items: [...before.items, ...after.items]}; }});
  vm.runInContext(source + "\nglobalThis.load=loadLedgerPage;", context);
  const pending = context.load();
  const corrected = {items: [{id: "corrected"}], next_cursor: "cursor-new"};
  state.data.ledger = corrected;
  resolveRead({items: [{id: "stale-page"}], next_cursor: null});
  await pending;
  assert.equal(state.data.ledger, corrected, "A late page from the prior snapshot cannot replace a corrected first page");
  assert.equal(merges, 0);
  const oldMore = context.load();
  state.resourceVersions.set("ledger", 2);
  const newError = Object.assign(new Error("Newer first-page reload failed"), {code: "request_timeout"});
  state.errors.ledger = newError;
  resolveRead({items: [{id: "old-more"}], next_cursor: null});
  await oldMore;
  assert.equal(state.errors.ledger, newError, "An older page cannot erase a failed newer refresh and its recovery action");
  assert.equal(merges, 0);
  context.api = async () => { requests += 1; throw Object.assign(new Error("history changed"), {code: "workspace_operation_history_changed"}); };
  await context.load();
  assert.equal(state.errors.ledger.code, "workspace_operation_history_changed");
  await context.load();
  assert.equal(requests, 3, "A rejected frozen cursor requires a first-page reload instead of repeating it");
  assert.equal(state.loading.has("ledger-more"), false);
  console.log("PASS ledger pagination contracts: corrected snapshots and explicit cursor restart");
}
async function searchAndAssetPaginationContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  const runSearch ="), app.indexOf("  const mergePage ="))
    + app.slice(app.indexOf("  const loadSearchPage ="), app.indexOf("  const archiveNewsItem ="))
    + app.slice(app.indexOf("  const loadAssetNewsPage ="), app.indexOf("  const assetSideHTML ="));
  const page = (id, cursor = "next") => ({items: [{id}], next_cursor: cursor});
  const state = {generation: 1, view: "search", tour: false, searchSequence: 1, searchQuery: "old", route: {q: "old"},
    loading: new Set(), errors: {}, resourceVersions: new Map(), searchPages: {events: page("old-event"), news: null}, searchFailures: {}};
  const pending = [];
  const context = sourceContext({state, encodeURIComponent, safeSegment: encodeURIComponent, isCancelled: () => false,
    renderSearch() {}, renderAsset() {}, $: () => ({value: "", removeAttribute() {}}),
    routeSearchQuery: () => state.route.q, api: () => new Promise(resolve => pending.push(resolve)),
    mergePage: (before, after) => ({...after, items: [...before.items, ...after.items]})});
  vm.runInContext(source + "\nglobalThis.search=runSearch; globalThis.more=loadSearchPage; globalThis.assetMore=loadAssetNewsPage;", context);
  const oldPage = context.more("events");
  const finishOldPage = pending.shift();
  state.route.q = "new";
  const newSearch = context.search("new");
  pending.splice(0).forEach((finish, index) => finish(page("new-" + index)));
  await newSearch;
  const newEvents = state.searchPages.events;
  finishOldPage(page("obsolete-event", null));
  await oldPage;
  assert.equal(state.searchPages.events, newEvents, "An earlier query page cannot merge into a new search");
  assert.equal(state.loading.has("search-events"), false, "Changing a query cannot leave its pagination permanently disabled");
  const currentPage = context.more("events");
  assert.equal(pending.length, 1, "The new query can request its next page after the old read settles");
  pending.shift()(page("new-event-page", null));
  await currentPage;
  assert.deepEqual(state.searchPages.events.items.map(item => item.id), ["new-1", "new-event-page"]);
  state.route.q = "pending";
  const oldSearch = context.search("pending");
  state.route.q = "";
  await context.search("");
  pending.splice(0).forEach(finish => finish(page("obsolete-result")));
  await oldSearch;
  assert.equal(state.loading.has("search"), false, "Clearing an in-flight query restores the empty search screen");
  assert.equal(state.searchResults.length, 0);
  state.view = "asset";
  state.asset = {uid: "a", news: page("a-first")};
  state.resourceVersions.set("asset", 1);
  const oldAssetPage = context.assetMore();
  const currentAsset = {uid: "b", news: page("b-first")};
  state.asset = currentAsset;
  state.resourceVersions.set("asset", 2);
  pending.shift()(page("a-obsolete", null));
  await oldAssetPage;
  assert.equal(state.asset, currentAsset);
  assert.equal(state.asset.news.items[0].id, "b-first");
  assert.equal(state.loading.has("asset-news-more"), false, "Leaving an asset cannot lock every subsequent news archive");
  const staleAssetPage = context.assetMore();
  assert.equal(pending.length, 1);
  const refreshed = page("b-refreshed", "fresh-cursor");
  currentAsset.news = refreshed;
  currentAsset.newsError = new Error("A newer refresh failed");
  state.resourceVersions.set("asset", 3);
  pending.shift()(page("b-obsolete", null));
  await staleAssetPage;
  assert.equal(currentAsset.news, refreshed, "An old cursor cannot replace a newer first page for the same instrument");
  assert.equal(currentAsset.newsError.message, "A newer refresh failed", "An obsolete page cannot erase the current retry state");
  const validAssetPage = context.assetMore();
  pending.shift()(page("b-new-page", null));
  await validAssetPage;
  assert.deepEqual(currentAsset.news.items.map(item => item.id), ["b-refreshed", "b-new-page"]);
  state.asset.news = page("b-later");
  const previousAccount = context.assetMore();
  state.generation += 1;
  state.loading = new Set(["asset-news-more"]);
  pending.shift()(page("other-account-page", null));
  await previousAccount;
  assert.equal(state.loading.has("asset-news-more"), true, "Old-account cleanup cannot release a new account's pending request");
  console.log("PASS search and asset pagination: changed queries, empty searches, instrument switches, refresh races and session isolation");
}
async function visibleRefreshContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const start = app.indexOf("  const stopVisibleRefresh =");
  const scheduler = start < 0 ? "" : app.slice(start, app.indexOf("  const stopQuoteStream =", start));
  const navigation = app.slice(app.indexOf("  const navigate ="), app.indexOf("  const loadNavigationScreen ="));
  const refresh = app.slice(app.indexOf("  const refreshVisibleData ="), app.indexOf('  window.addEventListener("focus",'));
  const state = {generation: 1, user: {public_id: "000000123"}, mode: "account", view: "home", route: {}, viewState: {}, navigationSequence: 0, devicePush: {status: "active"}, requests: new Set()};
  const timers = new Map(), reads = [];
  let sequence = 0, checks = 0, statusReads = 0, editing = false;
  const node = {setAttribute() {}, focus() {}};
  const schedule = (callback, delay) => { const id = ++sequence; timers.set(id, {callback, delay}); return id; };
  const context = sourceContext({state, document: {visibilityState: "visible", activeElement: null}, navigator: {onLine: true},
    window: {setTimeout: schedule}, setTimeout: schedule, clearTimeout: id => timers.delete(id), T: value => value,
    U: {navigation: [["home", "Home"], ["portfolio", "Portfolio"]]}, $: selector => selector === "dialog[open]" ? null : node, $$: () => [],
    resolveNavigationRoute: (view, detail) => ({view, ...detail}),
    saveNavigationPosition() {}, captureScreenDrafts() {}, closeRouteDialogs() {}, closeDrawer() {}, stopQuoteStream() {}, stopTableQuotes() {},
    restoreRouteControls() {}, updateRouteHistory() {}, renderNav() {}, renderCurrent() {}, restoreNavigationScroll() {},
    loadNavigationScreen: async () => {}, scheduleTableQuotes() {}, scheduleEventSummary() {}, refreshPushDevice: async () => {},
    verifySession: async () => { checks += 1; }, hasPending: () => editing,
    resumeWorkspaceRefresh: async canAdopt => { assert.equal(canAdopt(), true); statusReads += 1; },
    loadForView: async (view, route, force) => reads.push({view, force})});
  vm.runInContext("let freshnessTimer=null, freshnessBusy=false;\n" + scheduler + navigation + refresh + "\nglobalThis.go=navigate;", context);
  context.go("home", {mode: "account"});
  assert.equal(timers.size, 1, "Initial authenticated route entry starts periodic data refresh without a focus event");
  const initial = [...timers.keys()][0];
  assert.equal(timers.get(initial).delay, 60000, "Background page refresh remains bounded to the existing interval");
  context.go("portfolio", {mode: "account"});
  assert.equal([...timers.keys()][0], initial, "Frequent navigation cannot postpone refresh indefinitely");
  const tick = async () => {
    const [id, timer] = [...timers.entries()][0];
    timers.delete(id);
    timer.callback();
    await new Promise(resolve => setImmediate(resolve));
  };
  await tick();
  assert.equal(checks, 1);
  assert.deepEqual(reads, [{view: "portfolio", force: true}], "The timer refreshes the current page after rechecking the session");
  assert.equal(statusReads, 1, "The same visible cycle reads autonomous collection status without a manual refresh");
  assert.equal(timers.size, 1, "A completed refresh schedules its next observation");
  editing = true;
  await tick();
  assert.equal(reads.length, 1, "An active draft prevents background replacement of the editor");
  assert.equal(checks, 2, "Session verification continues while a draft is being edited");
  assert.equal(timers.size, 1);
  editing = false;
  state.requests.add({omnicioMutation: true});
  await tick();
  assert.equal(reads.length, 1, "A pending form submission cannot be replaced by a background page refresh");
  assert.equal(statusReads, 1, "Drafts and active mutations also defer collection-status adoption");
  state.requests.clear();
  await tick();
  assert.equal(reads.length, 2, "Background refresh resumes after the submission settles");
  assert.equal(checks, 4);
  state.mode = "public";
  await tick();
  assert.equal(checks, 4, "Public mode does not perform private background reads");
  assert.equal(timers.size, 0);
  context.go("home", {mode: "account"});
  assert.equal(timers.size, 1, "Returning from a public page restarts periodic account refresh");
  context.document.visibilityState = "hidden";
  await tick();
  assert.equal(checks, 4, "Hidden documents do not start refresh requests");
  assert.equal(timers.size, 0);
  context.document.visibilityState = "visible";
  context.go("portfolio", {mode: "account"});
  context.loadForView = async () => { state.generation += 1; };
  const beforeChange = statusReads;
  await tick();
  assert.equal(statusReads, beforeChange, "A session change during the view read cannot start an old cycle's status request");
  context.loadForView = async () => { state.requests.add({omnicioMutation: true}); };
  await tick();
  assert.equal(statusReads, beforeChange, "A mutation started during the view read prevents subsequent status adoption");
  state.requests.clear();
  console.log("PASS visible refresh: initial account entry, navigation deadlines, ongoing polling, draft preservation and public/hidden boundaries");
}
async function payoutDisplayContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const context = sourceContext({window: {}, Intl, URL, URLSearchParams});
  vm.runInContext(readFileSync(join(root, "web", "i18n.js"), "utf8"), context);
  vm.runInContext(readFileSync(join(root, "web", "workspace.js"), "utf8"), context);
  const ui = context.window.OmniUI, i18n = context.window.OMNICIO_I18N;
  const details = serverContracts.payout_visualization;
  const payouts = Object.fromEntries(details.payouts.map(item => [item.provider_key, item]));
  const original = JSON.stringify(details), dialogs = [], receipts = [];
  const state = {generation: 1, eventRequest: 1};
  let activeEvent;
  Object.assign(context, {U: ui, T: i18n.t, H: i18n.html, esc: ui.escape, date: ui.date,
    money: ui.money, infoRows: ui.infoRows, button: ui.button, state,
    views: new Set(["asset", "events", "goals"]), $: () => ({open: true}),
    enterRouteScreen: () => false, requireUser: () => true, api: async () => activeEvent,
    openDialog: (title, html) => dialogs.push({title, html}), markEvents: ids => receipts.push(...ids),
    isCancelled: () => false, humanError: error => error.message});
  const source = app.slice(app.indexOf("  const eventSourceLabel ="), app.indexOf("  const openNews ="))
    + app.slice(app.indexOf("  function renderAssetFinePrint("), app.indexOf("  function renderUpdateSaveStatusValue("));
  vm.runInContext(source + "\nglobalThis.row=renderAssetFinePrint; globalThis.section=renderAssetDetailsSummary2; globalThis.open=openEvent; globalThis.sourceHTML=eventSourceHTML;", context);
  assert.ok(payouts.scheduled.expected_at && payouts.paid.actual_at && payouts.record_only.record_at);
  assert.equal(payouts.ambiguous_scheduled.identity_status, "ambiguous", "The actual serializer exposes the disputed source identity");
  assert.equal(payouts.ambiguous_scheduled.identity_reason, "co_observed_anchor_collision");
  assert.ok(!Object.hasOwn(payouts.scheduled, "identity_status"), "Unambiguous legacy rows retain their existing DTO");
  assert.ok(!Object.hasOwn(payouts.scheduled, "payment_date") && !Object.hasOwn(payouts.scheduled, "effective_at"), "The browser must use the real payout date fields");
  for (const locale of ["ru", "en"]) {
    ui.setLocale(locale);
    const planned = context.row(payouts.scheduled), paid = context.row(payouts.paid);
    assert.ok(planned.includes(ui.escape(ui.date(payouts.scheduled.expected_at))), "The scheduled payout displays the expected date emitted by the actual HTTP route");
    assert.ok(planned.includes(ui.escape(i18n.t("events.expected"))));
    assert.ok(!planned.includes(ui.escape(ui.date(payouts.scheduled.actual_at))), "A non-paid source cannot turn an actual_at field into a payment confirmation");
    assert.ok(paid.includes(ui.escape(ui.date(payouts.paid.actual_at))) && paid.includes(ui.escape(i18n.t("payout.date.actual"))), "Explicit paid status uses and labels its actual payment date");
    assert.ok(!paid.includes(ui.escape(ui.date(payouts.paid.expected_at))), "The actual payment date takes precedence over the old schedule");
    const fallback = context.row(payouts.paid_expected);
    assert.ok(fallback.includes(ui.escape(ui.date(payouts.paid_expected.expected_at))) && fallback.includes(ui.escape(i18n.t("events.expected"))), "A missing actual date may only retain an explicitly planned date");
    for (const key of ["record_only", "undated"]) {
      const html = context.row(payouts[key]);
      assert.ok(html.includes(ui.escape(i18n.t("payout.date.unknown"))), "The UI says when the payment date is unconfirmed");
      for (const value of [payouts[key].record_at, payouts[key].announced_at].filter(Boolean)) assert.ok(!html.includes(ui.escape(ui.date(value))), "Record and announcement dates are never shown as payment dates");
    }
    for (const value of [undefined, null, "", false, 0, "invalid-time"]) {
      assert.ok(context.row({...payouts.paid, actual_at: value, expected_at: value}).includes(ui.escape(i18n.t("payout.date.unknown"))), "Malformed or missing date fields remain unknown");
    }
    const normal = context.section({payouts: [payouts.scheduled, payouts.paid]});
    assert.ok(normal.includes(i18n.html("Подтверждённые события выплат")), "Ordinary source records preserve their existing section");
    const ambiguous = context.section(details);
    assert.ok(ambiguous.includes(i18n.html("payout.identity.ambiguous")) && ambiguous.includes(i18n.html("payout.identity.note")));
    assert.ok(!ambiguous.includes(i18n.html("Подтверждённые события выплат")), "A disputed source group is never labelled confirmed");
    const disputedPaid = context.row(payouts.ambiguous_paid);
    assert.ok(disputedPaid.includes(ui.escape(ui.date(payouts.ambiguous_paid.actual_at))) && disputedPaid.includes(i18n.html("payout.date.source")));
    assert.ok(disputedPaid.includes(i18n.html("payout.identity.unconfirmed")) && !disputedPaid.includes(i18n.html("payout.date.actual")), "A disputed paid record is labelled as a source claim, not a confirmed payment");
    for (const [key, label] of [["scheduled", "asset.dividend"], ["record_only", "asset.coupon"], ["undated", "asset.bond_event"]]) {
      assert.ok(context.row(payouts[key]).startsWith(`<p class="fine-print">${i18n.html(label)} · `), "The real payout type has a localized label in both languages");
      assert.notEqual(i18n.t(label), label);
    }
    const unsafe = '<img src=x onerror="alert(1)">';
    for (const type of [undefined, null, "unknown_source_type", "constructor", "__proto__", unsafe]) {
      const html = context.row({...payouts.scheduled, event_type: type});
      assert.ok(html.startsWith(`<p class="fine-print">${i18n.html("Выплата")} · `), "Unknown and unsafe provider type codes have a neutral translated label");
      if (type) assert.ok(!html.includes(ui.escape(type)) && !html.includes(type), "Raw internal or untrusted type codes are not displayed");
    }
    for (const [key, event] of Object.entries(serverContracts.payout_event_cases)) {
      activeEvent = event;
      await context.open(event.id);
      const dialog = dialogs.at(-1);
      assert.strictEqual(state.eventDetail, event, "Presentation preserves the original event and destination");
      if (key === "normal") {
        assert.equal(dialog.title, event.title);
        assert.ok(dialog.html.includes(ui.escape(event.detail)) && dialog.html.includes(ui.escape(ui.date(event.source.expected_at))));
        assert.ok(dialog.html.includes(ui.escape(ui.money(event.source.amount_per_security, 2, event.source.currency, false))), "An undisputed source keeps its original amount");
      } else {
        assert.equal(dialog.title, i18n.t("payout.identity.ambiguous"));
        assert.ok(dialog.html.includes(i18n.html("payout.identity.note")), "Old direct links and the new warning explain the same source uncertainty");
        assert.ok(!dialog.html.includes(ui.escape(event.title)) && !dialog.html.includes(ui.escape(event.detail)) && !dialog.html.includes("999.19"), "Superseded financial claims cannot survive in the old title or description");
        assert.ok(!dialog.html.includes(ui.escape(ui.date(event.occurred_at))) && !dialog.html.includes(ui.escape(ui.date(event.occurred_at, true))), "The old calendar event time cannot look like a confirmed payment date");
        if (event.source.expected_at) assert.ok(!dialog.html.includes(ui.escape(ui.date(event.source.expected_at))) && !dialog.html.includes(ui.escape(ui.money(event.source.amount_per_security, 2, event.source.currency, false))));
      }
      assert.ok(dialog.html.includes("synthetic-a") && dialog.html.includes("event-destination"), "Source identity and the instrument path remain available");
      assert.ok(!dialog.html.includes("undefined") && !dialog.html.includes("NaN"));
    }
    for (const key of ["payout.date.actual", "payout.date.source", "payout.date.unknown", "payout.identity.ambiguous", "payout.identity.note", "payout.identity.unconfirmed"]) assert.notEqual(i18n.t(key), key, "Each new state has authored text in both languages");
  }
  activeEvent = {...serverContracts.payout_event_cases.superseded, read_at: null};
  await context.open(activeEvent.id);
  assert.deepEqual(receipts, [activeEvent.id], "Opening an uncertainty warning preserves the existing read receipt flow");
  assert.equal(JSON.stringify(details), original, "Rendering does not rewrite source evidence");
  console.log("PASS payout display: real private DTO, actual/planned/unknown dates, no record-date substitution, ambiguous source labels and safe historical event links");
}
async function payoutEventHistoryContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  const eventReadEpoch ="), app.indexOf("  const workspacePeriod ="))
    + app.slice(app.indexOf("  const eventsPath ="), app.indexOf("  const goalPreview ="))
    + app.slice(app.indexOf("  const mergePage ="), app.indexOf("  const loadSearchPage ="))
    + app.slice(app.indexOf("  const eventIsRead ="), app.indexOf("  const paintEventRow ="))
    + app.slice(app.indexOf("  const loadEventPage ="), app.indexOf("  const eventSourceLabel ="))
    + app.slice(app.indexOf("  function renderEventsHTMLEventTitleButton("), app.indexOf("  function renderHomeGoalsGoalsPreviewList("));
  const normal = clone(serverContracts.payout_event_cases.normal);
  const warning = clone(serverContracts.payout_event_cases.ambiguous);
  const superseded = clone(serverContracts.payout_event_cases.superseded);
  const alias = {...normal, id: superseded.id, title: "Obsolete payout", detail: "Obsolete financial claim 777.77"};
  const valid = {...normal, title: "Another valid payout for the same instrument", occurred_at: "2026-09-01T00:00:00Z"};
  const older = {...normal, id: "d".repeat(64), kind: "broker_operation", title: "Retained older operation", occurred_at: "2026-08-01T00:00:00Z", source: {type: "operation", amount: "42", currency: "RUB"}};
  const incoming = {items: [warning], next_cursor: null, read_all_before: 20, unread_count: 1};
  const state = {};
  const context = sourceContext({state, console, safeSegment: encodeURIComponent, T: value => value, H: value => value,
    esc: value => String(value), date: value => value, icon: () => "", U: {},
    document: {activeElement: null}, $: selector => selector === "#workspace-freshness" ? {} : null,
    renderCurrent() {}, renderEvents() {}, adoptPreferences() {}, adoptStrategy() {}, mergeGoalList: value => value,
    renderAdoptWorkspaceValue: () => "", isCancelled: error => error.name === "AbortError", dataError: name => `<p data-error="${name}">Refresh is unconfirmed</p>`});
  vm.runInContext(source + "\nglobalThis.load=loadResource; globalThis.more=loadEventPage; globalThis.rows=eventsHTML;", context);
  const reset = (items = [alias, valid]) => Object.assign(state, {generation: 1, navigationSequence: 1, eventFilter: "all", mode: "account", view: "events", user: {public_id: "000000123"},
    eventHistoryExtended: false, eventWrites: new Set(), resourceVersions: new Map(), resourceRequests: new Map(), loading: new Set(), errors: {},
    data: {events: {items: clone(items), next_cursor: "older", read_all_before: 20}}});
  const freshValid = {...valid, read_at: "2026-10-08T11:00:00Z"};
  const records = new Map([[alias.id, superseded], [valid.id, freshValid]]);
  for (const resource of ["events", "workspace"]) {
    reset();
    const reads = [];
    let collision = false;
    context.api = async path => {
      reads.push(path);
      if (path.includes("cursor=")) return {items: [clone(older)], next_cursor: "still-older", read_all_before: 20};
      if (path.startsWith("/api/events/")) return clone(collision ? records.get(path.split("/").at(-1)) : [alias, valid].find(item => path.endsWith(item.id)));
      return resource === "workspace" ? {events: clone(incoming), overview: {observed_at: "2026-10-08T12:00:00Z"}} : clone(incoming);
    };
    await context.more();
    assert.equal(state.eventHistoryExtended, true, "The regression starts with an actually appended event page");
    assert.ok(state.data.events.items.some(item => item.id === alias.id));
    const retainedOperation = state.data.events.items.find(item => item.id === older.id);
    collision = true;
    reads.length = 0;
    await context.load(resource, `/api/${resource}`, {force: true});
    await new Promise(resolve => setImmediate(resolve));
    const items = state.data.events.items;
    assert.ok(!items.some(item => item.id === alias.id), "An authoritative refresh removes the cached alias superseded by an ambiguity warning");
    assert.ok(items.some(item => item.id === warning.id));
    assert.equal(items.find(item => item.id === valid.id).read_at, freshValid.read_at, "A valid other-anchor payout for the same instrument survives with its authoritative read receipt");
    assert.equal(items.find(item => item.id === older.id), retainedOperation, "Unrelated appended history and its read receipt remain intact");
    assert.equal(state.data.events.next_cursor, "still-older", "Reconciliation preserves the appended history continuation");
    assert.equal(state.data.events.read_all_before, 20, "Source-only supersession is reconciled even without a new revision ceiling");
    assert.deepEqual(reads.filter(path => /^\/api\/events\/[a-f0-9]{64}$/.test(path)).sort(), [alias.id, valid.id].map(id => `/api/events/${id}`).sort(), "Only omitted cached payouts need individual authoritative reads");
    assert.ok(!context.rows(false).includes(alias.detail), "The real feed renderer cannot retain the old financial claim");
  }
  reset([alias, valid, older]);
  state.eventHistoryExtended = true;
  context.api = async path => path.endsWith(alias.id) ? {...superseded, source: {...alias.source, superseded_by: valid.id}} : {...incoming, items: [freshValid]};
  await context.load("events", "/api/events", {force: true});
  assert.ok(!state.data.events.items.some(item => item.id === alias.id), "Ordinary consolidation also removes an alias without an ambiguity reason or revision change");
  const failure = Object.assign(new Error("source_unavailable"), {status: 503});
  for (const resource of ["events", "workspace"]) {
    reset([alias, valid, older]);
    state.eventHistoryExtended = true;
    const before = state.data.events;
    context.api = async path => {
      if (path.endsWith(alias.id)) throw failure;
      if (path.endsWith(valid.id)) return freshValid;
      return resource === "workspace" ? {events: incoming} : incoming;
    };
    const result = await context.load(resource, `/api/${resource}`, {force: true});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(result === null, resource === "events", "An event failure cannot fail the successful unrelated workspace read");
    assert.equal(state.data.events, before, "A partly failed readback cannot certify or replace the retained history");
    assert.equal(state.errors.events, failure);
    assert.ok(context.rows(true).includes('data-error="events"') && !context.rows(false).includes(alias.detail), "Both the compact feed and full event list expose failure instead of unverified financial claims");
    let finishRead;
    context.api = async path => {
      if (path.endsWith(alias.id)) return new Promise(resolve => { finishRead = resolve; });
      if (path.endsWith(valid.id)) return freshValid;
      return resource === "workspace" ? {events: incoming} : incoming;
    };
    const retry = context.load(resource, `/api/${resource}`, {force: true});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(state.errors.events, failure, "Starting a retry cannot remove the uncertainty before payout readback succeeds");
    assert.ok(!context.rows(true).includes(alias.detail) && !context.rows(false).includes(alias.detail));
    finishRead(superseded);
    await retry;
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(state.errors.events, undefined);
    assert.ok(!state.data.events.items.some(item => item.id === alias.id));
  }
  reset([alias, valid]);
  context.api = async path => path.endsWith(alias.id) ? superseded : path.endsWith(valid.id) ? freshValid : {items: [older], next_cursor: "next-history-page", read_all_before: 20};
  await context.more();
  assert.ok(!state.data.events.items.some(item => item.id === alias.id), "The first pagination response also reconciles aliases hidden since page one");
  assert.ok(state.data.events.items.some(item => item.id === valid.id) && state.data.events.items.some(item => item.id === older.id));
  assert.equal(state.data.events.next_cursor, "next-history-page");
  reset([alias, valid, older]);
  state.eventHistoryExtended = true;
  const priorEvents = state.data.events;
  const workspace = {events: incoming, overview: {nav_rub: "12345.67", observed_at: "2026-10-08T12:00:00Z"}, goals: {items: [{id: "current-goal"}]}, connection: {connected: true, account_id: "current-account"}};
  let failRead;
  context.api = async path => {
    if (path.endsWith(alias.id)) return new Promise((resolve, reject) => { failRead = reject; });
    if (path.endsWith(valid.id)) return freshValid;
    return workspace;
  };
  assert.equal(await context.load("workspace", "/api/workspace", {force: true}), workspace);
  assert.equal(state.data.workspace.overview.nav_rub, "12345.67", "Workspace valuation adopts immediately while event readback is pending");
  assert.equal(state.data.goals, workspace.goals);
  assert.equal(state.data.connection, workspace.connection);
  assert.equal(state.data.events, priorEvents, "Unconfirmed events do not replace retained history while the workspace becomes usable");
  failRead(failure);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(state.errors.events, failure);
  assert.equal(state.errors.workspace, undefined, "An event-detail outage remains isolated from successful valuation, goals and connection data");
  assert.equal(state.data.workspace, workspace);
  reset([alias, valid]);
  state.eventHistoryExtended = true;
  const held = [];
  let hold = true;
  context.api = async path => {
    if (path.includes("cursor=")) return {items: [older], next_cursor: "winning-page-cursor", read_all_before: 20};
    if (path.startsWith("/api/events/")) {
      const event = records.get(path.split("/").at(-1));
      return hold ? new Promise(resolve => held.push(() => resolve(event))) : event;
    }
    return incoming;
  };
  const prePaginationRefresh = context.load("events", "/api/events", {force: true});
  await new Promise(resolve => setImmediate(resolve));
  const winningPagination = context.more();
  hold = false;
  held.forEach(resolve => resolve());
  await Promise.all([prePaginationRefresh, winningPagination]);
  assert.ok(!state.data.events.items.some(item => item.id === alias.id), "Pagination that supersedes an in-flight refresh must itself remove the retired payout claim");
  assert.ok(state.data.events.items.some(item => item.id === valid.id) && state.data.events.items.some(item => item.id === older.id));
  assert.equal(state.data.events.next_cursor, "winning-page-cursor");
  const many = Array.from({length: 9}, (_, index) => ({...valid, id: (index + 32).toString(16).padStart(64, "0")}));
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const deferredFixture = () => {
    reset(many);
    state.eventHistoryExtended = true;
    const pending = [], reads = [];
    let active = 0, peak = 0;
    context.api = async path => {
      if (!/^\/api\/events\/[a-f0-9]{64}$/.test(path)) return path === "/api/workspace" ? {events: incoming} : incoming;
      reads.push(path);
      active += 1;
      peak = Math.max(peak, active);
      const item = many.find(event => path.endsWith(event.id));
      return new Promise((resolve, reject) => pending.push({
        resolve: () => { active -= 1; resolve(clone(item)); },
        reject: () => { active -= 1; reject(failure); }
      }));
    };
    return {pending, reads, peak: () => peak};
  };
  const overlap = deferredFixture();
  const oldRefresh = context.load("events", "/api/events", {force: true});
  await tick();
  assert.equal(overlap.pending.length, 4);
  const newRefresh = context.load("workspace", "/api/workspace", {force: true});
  overlap.pending.shift().reject();
  await tick();
  assert.equal(overlap.reads.length, 4, "An early rejection cannot start another batch while the other three requests remain active");
  while (overlap.pending.length) {
    overlap.pending.splice(0).forEach(item => item.resolve());
    await tick();
  }
  await Promise.all([oldRefresh, newRefresh]);
  assert.equal(overlap.peak(), 4, "Overlapping workspace/event refreshes share a global four-request bound");
  assert.equal(overlap.reads.length, 4 + many.length, "A superseded refresh starts no later batches and the current refresh reads each omitted payout once");
  assert.ok(state.data.events.items.some(item => item.id === warning.id));
  assert.equal(state.errors.events, undefined, "An old refresh failure cannot replace the current result");
  for (const interruption of ["navigation", "logout", "read_receipt"]) {
    const fixture = deferredFixture();
    const before = state.data.events;
    const refreshing = context.load("events", "/api/events", {force: true});
    await tick();
    if (interruption === "navigation") state.navigationSequence += 1;
    else if (interruption === "logout") state.generation += 1;
    else if (interruption === "read_receipt") {
      state.resourceVersions.set("eventReads", 1);
      state.data.events = {...before, items: before.items.map(item => ({...item, read_confirmed: true}))};
    }
    const protectedHistory = state.data.events;
    fixture.pending.splice(0).forEach(item => item.resolve());
    await refreshing;
    assert.equal(state.data.events, protectedHistory, "A late readback cannot overwrite a newer navigation, account, read receipt or pagination result: " + interruption);
    assert.equal(fixture.reads.length, 4, "An invalidated readback stops before another request batch: " + interruption);
  }
  console.log("PASS payout event history: real private DTOs, appended cache supersession, valid same-instrument history, read receipts, failure visibility and bounded stale-read cancellation");
}
async function evidenceFileReadContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  const openResearchEvidence ="), app.indexOf("  const saveResearchEvidence ="));
  const state = {generation: 1, eventRequest: 0};
  const messages = [];
  const dialog = {open: true};
  let fileChange;
  const form = {isConnected: true, elements: {document: {value: ""}, evidence_file: {addEventListener(type, handler) { assert.equal(type, "change"); fileChange = handler; }}}};
  const context = sourceContext({state, enterRouteScreen: () => false, requireUser: () => true,
    T: value => value, H: value => value, esc: value => value, U: {loading: value => value},
    openDialog: () => { state.eventRequest += 1; },
    api: async () => ({version: 1, document: {assets: []}}), isCancelled: () => false,
    $: selector => selector === "#workspace-dialog" ? dialog : selector === "#research-evidence-form" ? form : {},
    showMessage: (_element, text) => messages.push(text)});
  vm.runInContext(source + "\nglobalThis.openEvidence=openResearchEvidence;", context);
  await context.openEvidence();
  assert.equal(typeof fileChange, "function", "The production evidence form binds the actual file reader");
  const selectFile = (size = 20) => {
    let finish, fail;
    const text = new Promise((resolve, reject) => { finish = resolve; fail = reject; });
    const pending = fileChange({target: {files: [{size, text: () => text}]}});
    return {pending, finish, fail};
  };
  const first = selectFile(), second = selectFile();
  second.finish("newer source"); await second.pending;
  first.finish("older source"); await first.pending;
  assert.equal(form.elements.document.value, "newer source", "A slower previous selection cannot replace the selected evidence");
  const edited = selectFile();
  form.elements.document.value = "Manual correction";
  edited.finish("File before correction"); await edited.pending;
  assert.equal(form.elements.document.value, "Manual correction", "A file completion preserves intervening manual input");
  const failed = selectFile(); failed.fail(new Error("Synthetic file access failure")); await failed.pending;
  assert.equal(messages.at(-1), "research.evidence_file_failed", "A read failure becomes a visible recoverable form error");
  const detached = selectFile(); state.eventRequest += 1;
  detached.finish("Previous form"); await detached.pending;
  assert.equal(form.elements.document.value, "Manual correction", "A prior form cannot accept a late read after navigation");
  await context.openEvidence();
  const oversized = selectFile(clientConfig.limits.researchEvidenceBytes + 1);
  await oversized.pending;
  assert.equal(messages.at(-1), "research.evidence_too_large", "The shared byte limit rejects oversized evidence before reading");
  console.log("PASS evidence file reader: selection ordering, manual edits, navigation, errors and byte limits");
}
function dialogCloseContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const state = {view: "goals", route: {mode: "account", view: "goals", screen: "create", goal_id: "goal-a", overlay: ""}};
  const handlers = new Map(), queuedClose = [], navigations = [];
  let routed = true, captured = 0, backed = 0;
  const dialog = {id: "workspace-dialog", open: true, dataset: {},
    classList: {contains: name => name === "route-dialog" && routed},
    addEventListener: (name, handler) => handlers.set(name, handler),
    showModal() { this.open = true; },
    close() {
      if (!this.open) return;
      this.open = false;
      // HTML close() clears open immediately and queues the close event for a later task.
      queuedClose.push(() => handlers.get("close")());
    }};
  const context = sourceContext({state,
    $$: selector => selector === "dialog[open]" && !dialog.open ? [] : [dialog],
    saveNavigationPosition() {}, captureScreenDrafts() { captured += 1; },
    routeBack() { backed += 1; },
    navigate(view, route, options) {
      context.closeRoutes();
      state.view = view;
      state.route = route;
      navigations.push({view, route, options});
    }});
  const source = app.slice(app.indexOf("  const closeRouteDialogs ="), app.indexOf("  const sessionSurfaceContent ="))
    + app.slice(app.indexOf('  for (const dialog of $$("dialog")) {'), app.indexOf("  observeDialogHeader();"));
  vm.runInContext(source + "\nglobalThis.closeRoutes=closeRouteDialogs;", context);

  dialog.close(); // A successful save closes the shared creation dialog.
  state.route.screen = "plan";
  dialog.showModal(); // The next editor opens before the old close task is delivered.
  queuedClose.shift()();
  assert.equal(navigations.length, 0, "A prior close event cannot navigate away from the reopened editor");
  assert.equal(dialog.open, true, "A prior close event cannot close the new dialog");
  assert.equal(state.route.screen, "plan", "The new goal plan retains its addressable route");

  dialog.close();
  queuedClose.shift()();
  assert.equal(navigations.length, 1, "A current close still leaves its routed editor");
  assert.equal(state.route.screen, "");
  assert.equal(state.route.goal_id, "goal-a", "Normal close retains the selected goal");
  assert.equal(navigations[0].options.replace, true, "Normal close replaces the closed route");

  state.route.screen = "edit";
  dialog.showModal();
  context.closeRoutes();
  assert.equal(dialog.dataset.routeClosing, "true");
  state.route.screen = "plan";
  dialog.showModal();
  queuedClose.shift()();
  assert.equal(dialog.dataset.routeClosing, undefined, "A navigation close marker is consumed even after reopening");
  assert.equal(navigations.length, 1, "A queued navigation close cannot replace the current route");
  assert.equal(dialog.open, true);
  dialog.close();
  queuedClose.shift()();
  assert.equal(navigations.length, 2, "The consumed marker cannot swallow the next genuine close");

  routed = false;
  state.route = {...state.route, screen: "archive", overlay: "help"};
  dialog.showModal();
  dialog.close();
  queuedClose.shift()();
  assert.equal(state.route.screen, "archive", "Closing an overlay preserves its underlying screen");
  assert.equal(state.route.overlay, "");
  assert.equal(navigations.length, 3);
  dialog.showModal();
  dialog.close();
  queuedClose.shift()();
  assert.equal(navigations.length, 3, "A plain dialog without a route does not navigate");

  dialog.showModal();
  let prevented = false;
  handlers.get("cancel")({preventDefault() { prevented = true; }});
  assert.equal(prevented, true, "Escape keeps the existing explicit navigation path");
  assert.equal(captured, 1);
  assert.equal(backed, 1);
  context.closeRoutes();
  queuedClose.shift()();
  assert.equal(dialog.dataset.routeClosing, undefined);
  assert.equal(navigations.length, 3, "Closing for history navigation cannot trigger a second navigation");
  console.log("PASS dialog close lifecycle: queued old events preserve reopened editors, navigation markers are consumed, and current close, overlay, cancel and history paths remain effective");
}
async function assetBackgroundChartContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const state = {generation: 1, user: {public_id: "000000123"}, mode: "account", view: "asset",
    route: {uid: "a"}, asset: {uid: "a", name: "Initial source", ticker: "A"},
    assetTab: "chart", assetPeriod: "1m", prefs: {draft: {watchlist: [], mask_balances: false}},
    data: {}, errors: {}, loading: new Set(), resourceRequests: new Map(), resourceVersions: new Map(), eventFilter: "payments"};
  const document = {body: {matches: () => false}, activeElement: null};
  let chart, locale = "ru", sidebarText = "", serial = 0;
  const watch = {dataset: {}, attributes: {}, setAttribute(key, value) { this.attributes[key] = value; }};
  const header = {h1: {}, p: {}, ".asset-logo": {}, "[data-watch]": watch};
  const container = {dataset: {}, set innerHTML(value) {
    if (document.activeElement === chart) document.activeElement = document.body;
    chart = {id: ++serial, selected: "last", label: locale, content: value,
      matches: () => false, focus() { document.activeElement = this; }};
  }};
  const sidebar = {set innerHTML(value) { sidebarText = value; }};
  const context = sourceContext({state, document, T: value => value, I: {getLocale: () => locale},
    $: (selector, parent) => parent === header ? header[selector] : ({"#view-asset": container,
      ".asset-detail-header": header, "[data-asset-sidebar]": sidebar, ".chart-svg": chart})[selector] || null,
    isWatched: uid => state.prefs.draft.watchlist.some(item => item.instrument_uid === uid),
    assetPricing: asset => ({asset}), assetSideHTML: () => state.prefs.draft.mask_balances ? "masked source balance" : "visible source balance",
    assetFrameHTML: () => "new chart source", assetChartHTML() {}, assetOverviewHTML() {}, assetMetricsHTML() {}, assetNewsHTML() {},
    resourceSnapshot: async (_name, payload) => payload, adoptLoadedResource() {}, isCancelled: () => false,
    captureScreenMenuFocus() {}, restoreScreenMenuFocus() {}, updateIdentity() {}, renderConnectionBanner() {},
    updateRefreshControls() {}, renderInstallPromotion() {}, U: {bindCharts() {}}});
  for (const name of ["Home", "Portfolio", "Market", "Strategies", "Assistant", "Goals", "Analytics", "Events", "Profile", "Settings", "Search", "Install"]) context["render" + name] = () => {};
  const source = app.slice(app.indexOf("  const loadResource ="), app.indexOf("  const resourceSnapshot ="))
    + app.slice(app.indexOf("  const refreshAssetChartContext ="), app.indexOf("  const tradingLabel ="))
    + app.slice(app.indexOf("  const renderCurrent ="), app.indexOf("  const updateLanguageControls ="));
  vm.runInContext(source + "\nglobalThis.load=loadResource; globalThis.paint=renderCurrent;", context);
  const pendingRead = name => {
    let resolve, reject;
    context.api = () => new Promise((yes, no) => { resolve = yes; reject = no; });
    const promise = context.load(name, "/api/" + name, {force: true});
    return {promise, resolve, reject};
  };
  context.paint();
  chart.focus();
  chart.selected = "first";
  const inspected = chart;
  for (const name of ["news", "workspace", "visualization", "preferences", "connection", "notifications"]) {
    const read = pendingRead(name);
    read.resolve({observed: name});
    await read.promise;
    assert.equal(chart, inspected, "A late generic resource must not replace the inspected asset SVG: " + name);
    assert.equal(document.activeElement, inspected, "The actual generic completion path retains chart focus: " + name);
    assert.equal(chart.selected, "first", "The selected historical observation survives unrelated source arrival");
    assert.equal(state.data[name].observed, name, "Keeping the chart cannot discard the newly received resource");
  }
  const failure = pendingRead("news");
  failure.reject(Object.assign(new Error("source_unavailable"), {status: 503}));
  await failure.promise;
  assert.equal(chart, inspected, "An unrelated source error also preserves the chart");
  assert.equal(state.errors.news.status, 503);
  state.prefs.draft.watchlist = [{instrument_uid: "a"}];
  state.prefs.draft.mask_balances = true;
  const preferences = pendingRead("preferences");
  preferences.resolve({observed: "changed preferences"});
  await preferences.promise;
  assert.equal(chart, inspected, "Personal display changes do not discard the public-price observation");
  assert.equal(sidebarText, "masked source balance", "The sidebar is repainted with current privacy state");
  assert.equal(watch.attributes["aria-pressed"], "true", "Late preferences update the retained watch control");
  assert.equal(watch.attributes["aria-label"], "Удалить из избранного");
  locale = "en";
  const translated = pendingRead("preferences");
  translated.resolve({observed: "new locale"});
  await translated.promise;
  assert.notEqual(chart, inspected, "Changed locale invalidates chart labels instead of retaining the old language");
  assert.equal(chart.label, "en");
  for (const change of [() => { state.assetPeriod = "1y"; }, () => { state.assetTab = "overview"; }, () => { state.route.uid = "b"; state.asset = {uid: "b", name: "Other source", ticker: "B"}; }]) {
    const previous = chart;
    change();
    const read = pendingRead("news");
    read.resolve({observed: "new view context"});
    await read.promise;
    assert.notEqual(chart, previous, "Different period, pane or instrument cannot reuse the previous chart");
  }
  const beforeExplicit = chart;
  context.paint();
  assert.notEqual(chart, beforeExplicit, "Explicit route and market rendering keeps the full repaint default");
  const stale = pendingRead("news");
  const beforeGeneration = chart;
  state.generation += 1;
  stale.resolve({observed: "obsolete account"});
  await stale.promise;
  assert.equal(chart, beforeGeneration, "An old account's resource cannot repaint the current surface");
  assert.notEqual(state.data.news?.observed, "obsolete account");
  console.log("PASS asset background chart: actual generic source completions preserve SVG, focus and selection; errors, privacy, watch state, locale and route invalidation remain correct");
}
function assetPayoutDisclosureContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const state = {route: {uid: "a"}, asset: {uid: "a", name: "Initial source", ticker: "A", payoutText: "Planned payout: old date"}, assetTab: "chart", assetPeriod: "1m"};
  const document = {activeElement: null, body: {}};
  let disclosure;
  const replacePayout = text => {
    if (disclosure?.contains(document.activeElement)) document.activeElement = document.body;
    const next = {open: false, textContent: text, contains: element => element === next.summary};
    next.summary = {focus(options) { this.focusOptions = options; document.activeElement = this; }};
    disclosure = next;
  };
  const container = {dataset: {}, set innerHTML(text) { replacePayout(text); }};
  const sidebar = {set innerHTML(text) { replacePayout(text); }};
  const header = {h1: {}, p: {}, ".asset-logo": {}, "[data-watch]": {dataset: {}, setAttribute() {}}};
  const context = sourceContext({state, document, T: value => value, I: {getLocale: () => "ru"}, isWatched: () => false,
    $: (selector, parent) => {
      if (parent === header) return header[selector];
      if (selector === "summary") return parent.summary;
      return {"#view-asset": container, "[data-asset-payouts]": disclosure, "[data-asset-sidebar]": sidebar, ".asset-detail-header": header, ".chart-svg": {}}[selector];
    }, assetPricing: asset => ({asset}), assetSideHTML: ({asset}) => asset.payoutText,
    assetFrameHTML: ({asset}) => asset.payoutText, assetChartHTML: () => "", assetOverviewHTML: () => "", assetMetricsHTML: () => "", assetNewsHTML: () => ""});
  const source = app.slice(app.indexOf("  const refreshAssetChartContext ="), app.indexOf("  const tradingLabel ="));
  vm.runInContext(source + "\nglobalThis.render=renderAsset;", context);
  context.render();
  disclosure.open = true;
  disclosure.summary.focus();
  for (const preserveChart of [true, false, true, false]) {
    const previous = disclosure;
    state.asset.payoutText = "Corrected source payment; ambiguous identity: " + preserveChart;
    context.render({preserveChart});
    assert.notEqual(disclosure, previous, "Late renders must replace stale payout content with the newly received source records");
    assert.equal(disclosure.open, true, "Both sidebar enrichment and full background repaint retain an opened same-asset disclosure");
    assert.equal(document.activeElement, disclosure.summary, "The replacement disclosure retains keyboard focus");
    assert.equal(disclosure.summary.focusOptions.preventScroll, true);
    assert.equal(disclosure.textContent, state.asset.payoutText, "Open-state preservation cannot preserve obsolete dates or financial assertions");
    assert.ok(!disclosure.textContent.includes("old date"));
  }
  const otherControl = {};
  disclosure.open = false;
  document.activeElement = otherControl;
  context.render({preserveChart: true});
  assert.equal(disclosure.open, false, "A deliberately closed disclosure remains closed");
  assert.equal(document.activeElement, otherControl, "A payout repaint does not steal focus from another control");
  disclosure.open = true;
  disclosure.summary.focus();
  state.route.uid = "b";
  state.asset = {uid: "b", name: "Other source", ticker: "B", payoutText: "Another instrument's payout"};
  context.render({preserveChart: true});
  assert.equal(disclosure.open, false, "Switching instruments starts with a fresh disclosure state");
  assert.notEqual(document.activeElement, disclosure.summary, "Focus from another instrument is not carried into the new disclosure");
  assert.equal(disclosure.textContent, state.asset.payoutText);
  console.log("PASS payout disclosure: repeated late sidebar/full repaints retain same-asset open state and focus while replacing source content; instrument switches reset it");
}
async function newsMonitoringContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const context = sourceContext({window: {}, Intl, console, URLSearchParams});
  vm.runInContext(readFileSync(join(root, "web", "i18n.js"), "utf8"), context);
  vm.runInContext(readFileSync(join(root, "web", "workspace.js"), "utf8"), context);
  const ui = context.window.OmniUI, i18n = context.window.OMNICIO_I18N;
  const cases = serverContracts.refresh_news_cases;
  const connection = {connected: true, environment: "prod", account_id: "synthetic-account", account_name: "Synthetic account"};
  const state = {generation: 1, user: {public_id: "000000123"}, refresh: {sequence: 1, busy: false},
    data: {connection, workspace: {connection, overview: {observed_at: cases.received.observed_at, status: "stale"}}}, errors: {}};
  const banner = {innerHTML: "", hidden: true, classList: {toggle() {}}}, sourceStatus = {textContent: ""};
  let reloads = 0, polls = 0;
  Object.assign(context, {state, U: ui, T: i18n.t, H: i18n.html, esc: ui.escape, date: ui.date, format: ui.format, infoRows: ui.infoRows, button: ui.button,
    $: selector => selector === "#connection-banner" ? banner : selector === "[data-news-monitor-status]" ? sourceStatus : null,
    humanError: error => error.message, brokerDisconnectDescription: () => "Disconnect help", disconnectBlocked: () => false,
    renderConnectionBannerValue: () => i18n.t("action.refresh"), renderConnectionBannerValue2: () => "workspace-refresh", renderConnectionBannerValue3: () => "",
    updateRefreshControls() {}, clearTimeout() {}, isCancelled: () => false,
    reloadWorkspaceObservation: async () => { reloads += 1; }, scheduleRefreshPoll: () => { polls += 1; }});
  const source = app.slice(app.indexOf("  const refreshActive ="), app.indexOf("  const refreshUnavailable ="))
    + app.slice(app.indexOf("  const workspaceRefreshText ="), app.indexOf("  const scheduleRefreshPoll ="))
    + app.slice(app.indexOf("  const adoptRefreshStatus ="), app.indexOf("  const requestWorkspaceRefresh ="))
    + app.slice(app.indexOf("  const connectionStatusText ="), app.indexOf("  const portfolioRows ="))
    + app.slice(app.indexOf("  const brokerSettingsHTML ="), app.indexOf("  const assistantHealthLabel ="));
  vm.runInContext(source + "\nglobalThis.newsText=workspaceNewsText; globalThis.paint=renderConnectionBanner; globalThis.sourceHTML=brokerSettingsHTML; globalThis.adopt=adoptRefreshStatus; globalThis.resume=resumeWorkspaceRefresh;", context);
  for (const locale of ["ru", "en"]) {
    ui.setLocale(locale);
    for (const [status, result] of Object.entries(cases)) {
      assert.equal(result.news.status, status, "The browser consumes the real server's news status");
      assert.ok(!Object.hasOwn(result.news, "next_cursor") && !Object.hasOwn(result.news, "error"), "Internal broker traversal details do not enter the browser DTO");
      state.data.refreshStatus = result;
      const text = context.newsText(true);
      assert.ok(text.includes(i18n.t(`news.monitor.${status}`)));
      assert.ok(text.includes(i18n.t("news.monitor.scope")), "Every detailed status states the held-instrument broker-feed boundary in both languages");
      assert.ok(!text.includes("undefined") && !text.includes("NaN") && !text.includes("synthetic-private-provider-cursor"));
      if (result.news.observed_at) assert.ok(text.includes(i18n.t("news.monitor.observed", {time: ui.date(result.news.observed_at, true)})), "Failed scans retain the actual last successful page time");
      const html = context.sourceHTML();
      assert.ok(html.includes("data-news-monitor-status") && html.includes(ui.escape(text)), "The existing broker settings render the actual escaped source status");
      context.paint();
      assert.ok(banner.innerHTML.includes(ui.escape(i18n.t("Последнее наблюдение устарело. Значения помечены временем получения; обновите данные."))), "News status cannot hide stale portfolio data");
      if (["partial", "unavailable"].includes(status)) {
        assert.ok(banner.innerHTML.includes(ui.escape(context.newsText())));
        assert.ok(!text.includes(i18n.t("news.monitor.received")), "Partial scans and outages never claim a completed feed check");
      }
      state.data.workspace.overview.status = "available";
      context.paint();
      assert.equal(banner.hidden, !["partial", "unavailable"].includes(status), "Only news gaps add a banner when financial data is available");
      state.data.workspace.overview.status = "stale";
    }
    state.data.refreshStatus = {...cases.received, news: {...cases.received.news, documents_new: 0}};
    assert.ok(context.newsText(true).includes(i18n.t("news.monitor.saved", {count: ui.format(0, 0)})), "Zero newly saved items is an explicit write count, not proof that no news exists");
    state.data.refreshStatus.news = {...cases.received.news, scope: "unconfirmed_source", documents_new: 999};
    assert.ok(context.newsText(true).includes(i18n.t("news.monitor.unknown")) && !context.newsText(true).includes("999"), "An unrecognized scope cannot inherit a successful feed claim");
    state.data.refreshStatus.news = {...cases.received.news, documents_new: null, observed_at: "invalid-time"};
    assert.ok(!context.newsText(true).includes(i18n.t("news.monitor.saved", {count: ui.format(0, 0)})), "Missing counts stay unknown");
    assert.ok(!context.newsText(true).includes("invalid-time"));
  }
  state.data.refreshStatus = cases.partial;
  await context.adopt(cases.received, {generation: 1, sequence: 1});
  assert.equal(sourceStatus.textContent, context.newsText(true), "A status-only change updates the existing paragraph in place");
  assert.equal(reloads, 0, "News-only completion does not reload financial views or editors");
  assert.equal(polls, 0, "Completed source status does not create an extra polling loop");
  const accepted = sourceStatus.textContent;
  await context.adopt(cases.unavailable, {generation: 0, sequence: 1});
  assert.equal(sourceStatus.textContent, accepted, "An older account cannot replace current news status");
  await context.adopt(cases.unavailable, {generation: 1, sequence: 1, canAdopt: () => false});
  assert.equal(sourceStatus.textContent, accepted, "A draft or mutation started during a background GET prevents late adoption");
  let finishRead, guard = true;
  context.api = () => new Promise(resolve => { finishRead = resolve; });
  const pending = context.resume(() => guard);
  guard = false;
  finishRead(cases.unavailable);
  await pending;
  assert.equal(sourceStatus.textContent, accepted, "The actual status GET carries its live editing guard through the response");
  state.tour = true;
  context.paint();
  assert.equal(banner.hidden, true, "Private monitoring status stays hidden in the public tour");
  console.log("PASS news monitoring: real refresh DTO, bilingual scope, partial/outage truthfulness, retained source time, in-place updates and session/draft boundaries");
}
function settingsRecoveryContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const context = sourceContext({window: {}, Intl, URLSearchParams});
  vm.runInContext(readFileSync(join(root, "web", "i18n.js"), "utf8"), context);
  vm.runInContext(readFileSync(join(root, "web", "workspace.js"), "utf8"), context);
  const ui = context.window.OmniUI, i18n = context.window.OMNICIO_I18N;
  const state = {view: "settings", route: {screen: "appearance"}, data: {}, formDrafts: {},
    prefs: {server: defaultPreferences(), draft: defaultPreferences().document, dirty: true, busy: false, error: {status: 0, code: "request_interrupted"}}};
  const notice = () => ({innerHTML: "", hidden: !state.prefs.error});
  const sections = [0, 1].map(() => ({dataset: {}, notices: [], insertAdjacentHTML(position, html) {
    if (html.includes('data-save-error="prefs"')) this.notices.push(notice());
  }}));
  const form = {id: "preferences-form"};
  const status = {dataset: {}, textContent: "", closest: () => form};
  const view = {set innerHTML(html) {
    sections.forEach(section => { section.notices = []; });
    if (html.includes('data-save-error="prefs"')) sections[1].notices.push(notice());
  }};
  Object.assign(context, {state, U: ui, I: i18n, T: i18n.t, H: i18n.html, esc: ui.escape, select: ui.select, field: ui.field, heading: ui.heading, button: ui.button, infoRows: ui.infoRows,
    $: selector => ({"#view-settings": view, "#preferences-form": form, "[data-release-version]": {textContent: version}}[selector] || null),
    $$: selector => selector === ":scope > section" ? sections : selector === '[data-save-status="prefs"]' ? [status] : selector === '[data-save-error="prefs"]' ? sections.flatMap(section => section.notices) : [],
    humanError: error => error.code, captureScreenDrafts() {}, restoreEditableForm() {}, restoreScreenDrafts() {}, addScreenNavigation() {},
    brokerSettingsHTML: () => "", recoveryPanelHTML: () => "", notificationContentsHTML: () => "", operationalMetricsHTML: () => ""});
  const source = app.slice(app.indexOf("  const updateSaveStatus ="), app.indexOf("  const applySavedEffects ="))
    + app.slice(app.indexOf("  const saveErrorHTML ="), app.indexOf("  const preservePersonal ="))
    + app.slice(app.indexOf("  const renderSettings ="), app.indexOf("  const brokerSettingsHTML ="))
    + app.slice(app.indexOf("  function layoutSettings("), app.indexOf("  function layoutProfile("))
    + app.slice(app.indexOf("  function applyScreenLayout("), app.indexOf("  function incomePaneHTML("))
    + app.slice(app.indexOf("  function renderUpdateSaveStatusValue("), app.indexOf("  function renderStrategiesStrategyOption("));
  vm.runInContext(source + "\nconst screenLayoutHandlers={settings:layoutSettings}; globalThis.render=renderSettings;", context);
  for (const locale of ["ru", "en"]) {
    ui.setLocale(locale);
    for (const error of [{status: 0, code: "request_interrupted"}, {status: 503, code: "source_unavailable"}, {status: 409, code: "settings_version_conflict"}]) {
      state.prefs.error = error;
      context.render();
      const visible = sections[0].notices[0];
      assert.equal(sections[0].hidden, false, "The appearance screen is the actual visible section");
      assert.equal(status.dataset.state, error.status === 409 ? "conflict" : "error");
      assert.ok(visible.innerHTML.includes('data-action="prefs-reload"'), "Rerendering unconfirmed settings keeps recovery controls in the visible Appearance section");
      assert.equal(visible.innerHTML.includes('data-action="prefs-retry"'), error.status !== 409, "Interrupted writes retain readback; version conflicts require explicit reload");
      assert.equal(visible.hidden, false);
    }
    state.prefs.error = null;
    state.prefs.dirty = false;
    context.render();
    assert.equal(status.dataset.state, "saved");
    assert.equal(sections[0].notices[0].hidden, true);
    assert.equal(sections[0].notices[0].innerHTML, "", "Confirmed settings remove obsolete recovery actions");
  }
  console.log("PASS settings recovery: rerendered Appearance controls, interrupted/failed/conflicting writes and confirmed-state cleanup in both languages");
}
async function offlineQuoteContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const start = app.indexOf("  const quoteForConnection =");
  const helper = start < 0 ? "" : app.slice(start, app.indexOf("  const startQuoteStream =", start));
  const stream = app.slice(app.indexOf("  const startQuoteStream ="), app.indexOf("  const clearPrivateState ="));
  const tables = app.slice(app.indexOf("  function adoptTableQuotes("), app.indexOf("  async function pollTableQuotes()"));
  const events = app.slice(app.indexOf('  window.addEventListener("offline",'), app.indexOf('  prefersDark.addEventListener("change",'));
  const stamp = "2026-10-08T12:00:00Z";
  const quote = {instrument_uid: "a", last_price: "123.000000001", quote_status: "live", quote_time: stamp, observed_at: stamp, price_unit: "currency", price_currency: "RUB"};
  const state = {generation: 1, user: {public_id: "000000123"}, view: "asset", asset: {uid: "a", market: {...quote}}, quotes: {a: {...quote}}, session: {status: "authenticated"}};
  const source = {innerHTML: "live"}, price = {innerHTML: quote.last_price}, callbacks = {}, streams = [];
  class EventSourceFixture {
    constructor() { this.listeners = {}; streams.push(this); }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    close() { this.closed = true; }
  }
  const context = sourceContext({state, navigator: {onLine: false}, document: {visibilityState: "visible"}, EventSource: EventSourceFixture,
    window: {EventSource: EventSourceFixture, addEventListener: (name, callback) => { callbacks[name] = callback; }},
    $: selector => ({"[data-market-source]": source, "[data-market-quote]": price}[selector] || {}), $$: () => [],
    T: value => value, assetPricing: asset => ({market: asset.market}), assetQuoteHTML: value => value.market.last_price,
    freshness: (name, at, status) => status, safeSegment: encodeURIComponent, encodeURIComponent,
    clearTimeout() {}, setTimeout: () => 1, toast() {}, lockSession() {}, refreshVisibleData() {}, scheduleTableQuotes() {}, scheduleEventSummary() {}, paintTableQuotes() {},
    stopQuoteStream: () => { if (streams.length) streams.at(-1).close(); }});
  vm.runInContext("let quoteStream=null, quoteFailures=0, quoteReconnectTimer=null;\n" + helper + stream + tables + events
    + "\nglobalThis.accept=adoptTableQuotes; globalThis.unavailable=markTableQuotesUnavailable;", context);
  callbacks.offline();
  assert.equal(state.asset.market.quote_status, "offline", "An offline event immediately removes the live label from the asset");
  assert.equal(state.quotes.a.quote_status, "offline", "Remembered table quotes cannot remain live while offline");
  assert.equal(source.innerHTML, "offline", "The existing source indicator updates without replacing the chart");
  assert.equal(price.innerHTML, quote.last_price);
  assert.equal(state.asset.market.quote_time, stamp, "Connectivity loss cannot fabricate a new observation timestamp");
  context.accept([{...quote, last_price: "123.000000002"}], ["a"]);
  assert.equal(state.quotes.a.quote_status, "offline", "A delayed pre-offline response cannot restore a live badge");
  const assetLoad = app.slice(app.indexOf("  const loadAsset ="), app.indexOf("  const fundamentalMetricsHTML ="));
  state.resourceVersions = new Map();
  state.assetPeriod = "1m";
  Object.assign(state.asset, {details: {}, facts: {}, news: {items: []}});
  let finishAsset;
  Object.assign(context, {renderAsset: () => true, U: {bindCharts() {}}, api: () => new Promise(resolve => { finishAsset = resolve; })});
  vm.runInContext(assetLoad + "\nglobalThis.loadAssetNow=loadAsset;", context);
  const pendingAsset = context.loadAssetNow("a");
  finishAsset(quote);
  await pendingAsset;
  assert.equal(state.asset.market.quote_status, "offline", "An asset REST response received offline cannot claim a live source");
  assert.equal(state.asset.market.quote_time, stamp);
  context.navigator.onLine = true;
  callbacks.online();
  assert.equal(state.asset.market.quote_status, "connecting", "Restored connectivity waits for source confirmation");
  assert.equal(state.quotes.a.quote_status, "offline", "Online alone does not certify previously received table data");
  context.accept([quote], ["a"]);
  assert.equal(state.quotes.a.quote_status, "live", "A new source response can restore table freshness");
  streams.at(-1).listeners.market({data: JSON.stringify({...quote, observed_at: "2026-10-08T12:00:01Z"})});
  assert.equal(state.asset.market.quote_status, "live");
  streams.at(-1).listeners.status({data: JSON.stringify({state: "disconnected"})});
  assert.equal(state.asset.market.quote_status, "reconnect", "An explicit source disconnect removes the live badge while retrying");
  context.unavailable(["a"]);
  assert.equal(state.quotes.a.quote_status, "unavailable", "A failed or timed-out batch retains its unavailable source status");
  assert.equal(state.quotes.a.last_price, quote.last_price);
  console.log("PASS offline quotes: source/table state, exact retained values, late responses, reconnect confirmation and source failures");
}
async function assistantConversationContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const lifecycle = app.slice(app.indexOf("  const loadAssistantConversation ="), app.indexOf("  const openAssistantConnection ="));
  const sending = app.slice(app.indexOf("  const reportAssistantFailure ="), app.indexOf("  function assistantRequestHTML()"));
  const readback = app.slice(app.indexOf("  async function readAssistantRequest("), app.indexOf("  function assistantMemoryChoice("));
  const pending = new Map();
  const conversation = id => ({id, title: id, version: 0, messages: [], next_before: null});
  const state = {generation: 1, view: "assistant", assistantBusy: false, assistantConversation: conversation("old"), assistantRequest: {id: "old-request", conversation_id: "old", status: "uncertain", reply_prefix: "Old private context"}, chat: [], route: {}, data: {assistantStatus: {enabled: true, configured: true}}, eventRequest: 1};
  const dialog = {open: true, close() { this.open = false; }};
  let delayReads = true;
  let delayReadbacks = false;
  let delayConversationWrites = false;
  let requestSequence = 0;
  let reportedFailures = 0;
  const context = sourceContext({
    state, requireUser: () => true, safeSegment: encodeURIComponent, renderAssistant() {},
    T: value => value, H: value => value, esc: value => value, button: () => "", openDialog() {},
    updateViewRoute: route => { state.route = route; }, loadResource: async () => {},
    $: selector => selector === "#workspace-dialog" ? dialog : null,
    crypto: {randomUUID: () => `new-request-${++requestSequence}`},
    assistantDraftFromForm: () => ({message: "A question for the selected conversation", context: "general"}),
    ensureAssistantConversation: async () => {}, paintAssistantRequest() {},
    readAssistantStream() {}, isCancelled: () => false, humanError: error => error.message,
    toast: () => { reportedFailures++; }, showMessage: () => { reportedFailures++; },
    api: async (path, options = {}) => {
      if (path === "/api/assistant/conversations") return delayConversationWrites ? new Promise(resolve => pending.set("create", resolve)) : conversation("created");
      if (options.method === "DELETE") return delayConversationWrites ? new Promise(resolve => pending.set("delete", resolve)) : {deleted: true};
      if (path === "/api/assistant/messages/stream") return new Promise((resolve, reject) => { pending.set("stream", resolve); pending.set("streamError", reject); });
      if (path.startsWith("/api/assistant/requests/")) return delayReadbacks ? new Promise((resolve, reject) => { pending.set("readback", resolve); pending.set("readbackError", reject); }) : {request_id: state.assistantRequest.id, conversation_id: state.assistantConversation.id, status: "cancelled"};
      const id = path.split("/").at(-1).split("?")[0];
      if (!delayReads) return conversation(id);
      return new Promise(resolve => pending.set(id, resolve));
    }
  });
  vm.runInContext(lifecycle + sending + readback + "\nglobalThis.load=loadAssistantConversation;globalThis.create=newAssistantConversation;globalThis.remove=deleteAssistantConversation;globalThis.send=sendAssistant;globalThis.readRequest=readAssistantRequest;", context);
  const loadingEmpty = context.load("empty");
  pending.get("empty")(conversation("empty"));
  await loadingEmpty;
  assert.equal(state.assistantRequest, null, "A conversation without a request cannot retain another conversation's provisional answer or cancel action");

  state.assistantRequest = {id: "old-request", conversation_id: "empty", status: "uncertain"};
  const loadingOld = context.load("old");
  await context.create();
  pending.get("old")({...conversation("old"), latest_request: {request_id: "old-request", conversation_id: "old", status: "uncertain"}});
  await loadingOld;
  assert.equal(state.assistantConversation.id, "created", "An earlier conversation read cannot replace a newly created conversation");
  assert.equal(state.assistantRequest, null, "A new conversation starts without old request controls");
  assert.equal(state.route.conversation, "created");

  state.assistantRequest = {id: "created-request", conversation_id: "created", status: "cancelled"};
  state.assistantDeleteConfirmation = {id: "created", sequence: state.eventRequest};
  await context.remove(true);
  assert.equal(state.assistantConversation, null);
  assert.equal(state.assistantRequest, null, "Deleting a conversation also removes its request and provisional text");

  delayReadbacks = delayConversationWrites = true;
  for (const operation of ["delete", "create"]) {
    state.assistantConversation = conversation("readback-race");
    state.assistantRequest = {id: "pending-readback", conversation_id: "readback-race", status: "uncertain"};
    state.assistantDeleteConfirmation = {id: "readback-race", sequence: state.eventRequest};
    const readbackResult = context.readRequest(false);
    const writing = operation === "delete" ? context.remove(true) : context.create();
    if (operation === "delete") pending.get("readback")({request_id: "pending-readback", conversation_id: "readback-race", status: "completed"});
    else pending.get("readbackError")(new Error("stale_readback_failure"));
    await until(() => pending.has(operation), "The conversation mutation awaits its response");
    await Promise.resolve();
    assert.equal(state.assistantBusy, true, "An old readback cannot unlock an in-flight conversation mutation");
    assert.equal(pending.has("readback-race"), false, "A late readback cannot launch history that resurrects a deleted conversation");
    assert.equal(await readbackResult, undefined, "A superseded readback cannot confirm the current conversation's request state");
    assert.equal(reportedFailures, 0, "A stale readback error cannot appear on a new conversation");
    pending.get(operation)(operation === "delete" ? {deleted: true} : conversation("created"));
    await writing;
  }
  delayReadbacks = delayConversationWrites = false;
  state.assistantConversation = conversation("history-race");
  state.assistantRequest = {id: "history-readback", conversation_id: "history-race", status: "uncertain"};
  const historyReadback = context.readRequest(false);
  await until(() => pending.has("history-race"), "A completed request readback starts its history reconciliation");
  await context.create();
  pending.get("history-race")(conversation("history-race"));
  assert.equal(await historyReadback, undefined, "Readback ownership is checked again after waiting for history");
  assert.equal(state.assistantConversation.id, "created");

  state.view = "home";
  state.assistantConversation = conversation("selected");
  const loadingOther = context.load("other");
  const sendingQuestion = context.send({reportValidity: () => true});
  await until(() => pending.has("stream"), "The isolated assistant send reaches its stream request");
  assert.equal(state.assistantRequest.conversation_id, "selected");
  pending.get("other")(conversation("other"));
  await loadingOther;
  assert.equal(state.assistantConversation.id, "selected", "A pre-send history response cannot move an active question to another conversation");
  assert.equal(state.assistantRequest.id, "new-request-1");
  delayReads = false;
  state.assistantRequest.status = "cancelled";
  pending.get("stream")();
  await sendingQuestion;
  assert.equal(state.assistantBusy, false);
  for (const outcome of ["stream", "streamError"]) {
    pending.delete("stream");
    const cancelledSend = context.send({reportValidity: () => true});
    await until(() => pending.has("stream"), "The request awaiting cancellation starts its stream");
    const releaseCancelled = pending.get(outcome);
    await context.readRequest(true);
    assert.equal(state.assistantBusy, false, "Confirmed cancellation allows a new question before the old connection has closed");
    pending.delete("stream");
    const nextSend = context.send({reportValidity: () => true});
    await until(() => pending.has("stream"), "The next question starts before the cancelled connection closes");
    const activeId = state.assistantRequest.id;
    releaseCancelled(new Error("old_stream_interrupted"));
    await cancelledSend;
    assert.equal(state.assistantBusy, true, "A late completion or failure from the cancelled stream cannot unlock the new question");
    assert.equal(state.assistantRequest.id, activeId, "The old stream cannot replace the active request");
    assert.equal(state.assistantRequest.status, "running");
    assert.equal(reportedFailures, 0, "An old connection error does not become an error on the new question");
    state.assistantRequest.status = "cancelled";
    pending.get("stream")();
    await nextSend;
  }
  console.log("PASS assistant conversation isolation: empty, created and deleted histories clear old request state; earlier reads cannot replace a new conversation or active send");
}
async function assistantMemoryReconciliationContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  function assistantMemoryForm("), app.indexOf("  async function saveAssistantMemory("));
  const saved = {id: "saved-note", version: 1, category: "preference", content: "Explain source timestamps"};
  const state = {generation: 1, view: "assistant", assistantMemoryDraftId: saved.id, data: {assistantMemory: {items: [saved]}}};
  let rendered = "", cleared = 0, failures = 0;
  const context = sourceContext({state, crypto: {randomUUID: () => "next-note"}, T: value => value, H: value => value, esc: value => value, select: () => "", loadResource: async () => {}, clearScreenDraft: () => { cleared++; }, humanError: () => "Unconfirmed", $: () => ({}), showMessage: () => { failures++; }, renderAssistant: () => { rendered = context.form(); }});
  vm.runInContext(source + "\nglobalThis.form=assistantMemoryForm;globalThis.reconcile=reconcileAssistantMemory;", context);
  const form = {dataset: {id: saved.id, version: "0"}};
  await context.reconcile(form, saved, new Error("lost_ack"), 1);
  assert.equal(cleared, 1);
  assert.ok(rendered.includes('data-id="next-note"'), "After a confirmed lost creation response, the next memory form must use a fresh ID instead of recreating the saved note");
  assert.equal(failures, 0);
  state.assistantMemoryDraftId = "unconfirmed-note";
  await context.reconcile({dataset: {id: "unconfirmed-note", version: "0"}}, saved, new Error("lost_ack"), 1);
  assert.equal(state.assistantMemoryDraftId, "unconfirmed-note", "An unconfirmed result retains its original idempotency ID for reconciliation");
  assert.equal(cleared, 1);
  assert.equal(failures, 1);
  console.log("PASS assistant memory reconciliation: confirmed creation advances the next draft ID; an uncertain creation retains its identity");
}
async function strategyInputContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const between = (from, to) => {
    const start = app.indexOf(from);
    const end = app.indexOf(to, start + from.length);
    assert.ok(start >= 0 && end > start, from);
    return app.slice(start, end);
  };
  const source = [
    between("  const writePayload = ", "  const editPreferences = "),
    between("  const documentChanged = ", "  const redistribute = "),
    between("  const updateStrategyField = ", "  const stepField = "),
    between("  function renderUpdateStrategyFieldValue(", "  function renderStepFieldValue("),
    between("  const strategySaveUnavailable = ", "  const updateStrategySaveControls = "),
    between("  const reloadVersioned = ", "  const saveErrorHTML = "),
    between("  function adoptStrategy(", "  const strategySaveUnavailable = "),
    between("  function renderUpdateSaveStatusValue(", "  function renderUpdateSaveStatusValue5(")
  ].join("\n");

  function numericInput(name, value, valid = true, badInput = false) {
    const attributes = new Map();
    return {
      name, value, type: "number", nativeValid: valid, badInput, customError: "",
      get validity() { return {valid: this.nativeValid && !this.customError, badInput: this.badInput}; },
      setAttribute(name, value) { attributes.set(name, value); },
      removeAttribute(name) { attributes.delete(name); },
      setCustomValidity(value) { this.customError = value; },
      getAttribute(name) { return attributes.get(name); }
    };
  }

  function fixture() {
    const document = {
      profile: {reserve_rub: "5000", horizon_months: "24", max_drawdown_percent: "20"},
      policy: {turnover_budget_percent: "20"},
      rules: {rating_caps: {AAA: "0.1234"}}, customized: false
    };
    const state = {generation: 1, user: {public_id: "123456789"}, locked: false, data: {},
      strategy: {server: {version: 1, document: structuredClone(document)}, draft: structuredClone(document),
        invalidInputs: {}, revision: 0, dirty: false, busy: false, error: null}};
    let present = true, hold = false, release;
    let remote = structuredClone(state.strategy.server);
    const writes = [], controls = [], statuses = [];
    const form = {elements: controls, checkValidity: () => controls.every(input => input.validity.valid)};
    const context = sourceContext({
      state, structuredClone, clone: structuredClone, same: (a, b) => JSON.stringify(a) === JSON.stringify(b),
      $: () => present ? form : null, window: {setTimeout: () => 1}, clearTimeout() {},
      updateSaveStatus() { statuses.push({dirty: state.strategy.dirty, error: state.strategy.error?.message || null}); },
      applySavedEffects() { statuses.push({dirty: state.strategy.dirty, error: state.strategy.error?.message || null}); },
      validRecord: record => Number.isInteger(record?.version) && !!record.document,
      isCancelled: () => false, renderCurrent() {}, toast() {}, T: value => value, humanError: error => error.message,
      api: async (_url, options) => {
        if (!options) return {selection: structuredClone(remote)};
        writes.push(structuredClone(options.body));
        if (hold) await new Promise(resolve => { release = resolve; });
        remote = {version: options.body.expected_version + 1, document: structuredClone(options.body.document)};
        return {selection: structuredClone(remote)};
      }
    });
    vm.runInContext(source + `
      globalThis.edit = updateStrategyField;
      globalThis.save = () => saveVersioned("strategy");
      globalThis.retry = () => retryVersioned("strategy");
      globalThis.reload = () => reloadVersioned("strategy", true);
      globalThis.blocked = () => strategySaveUnavailable(state.strategy);
      globalThis.status = () => state.strategy.error ? renderUpdateSaveStatusValue(state.strategy) : renderUpdateSaveStatusValue4(state.strategy);
    `, context);
    return {state, context, writes, controls, statuses,
      add(name, value, valid = true, badInput = false) {
        const input = numericInput(name, value, valid, badInput);
        controls.push(input);
        return input;
      },
      removeForm() { present = false; },
      restoreForm() { present = true; },
      holdNextWrite() { hold = true; },
      releaseWrite() { hold = false; release(); },
      remote(record) { remote = structuredClone(record); }
    };
  }

  async function exercise() {
    const active = fixture();
    const amount = active.add("strategy.profile.reserve_rub", "6000");
    active.context.edit(amount);
    active.holdNextWrite();
    const pending = active.context.save();
    assert.equal(active.writes.length, 1);
    amount.value = "";
    amount.nativeValid = false;
    amount.badInput = true;
    active.context.edit(amount);
    active.removeForm();
    active.releaseWrite();
    await pending;

    assert.equal(active.writes.length, 1, "No subsequent PUT after an invalid edit and route change");
    assert.equal(active.state.strategy.draft.profile.reserve_rub, "6000", "Incomplete input cannot change the numeric draft");
    assert.equal(active.state.strategy.server.document.profile.reserve_rub, "6000");
    assert.equal(active.state.strategy.invalidInputs[amount.name], "");
    assert.equal(active.context.status(), "error", "Late ACK cannot claim saved while input is invalid");
    assert.equal(active.context.blocked(), true, "Research and execution remain blocked");
    assert.equal(active.state.strategy.dirty, true);

    active.restoreForm();
    amount.value = "6000";
    amount.nativeValid = true;
    amount.badInput = false;
    active.context.edit(amount);
    assert.equal(active.context.status(), "saved", "Correction to the last actual value recovers without a duplicate write");
    assert.equal(active.writes.length, 1);
    amount.value = "";
    active.context.edit(amount);
    await active.context.save();
    assert.equal(active.writes.at(-1).document.profile.reserve_rub, null, "Intentional valid clearing still saves unknown");
    assert.equal(active.context.status(), "saved");
    assert.equal(Object.hasOwn(active.writes.at(-1).document, "invalidInputs"), false, "Browser validation metadata is never part of the wire document");

    const multiple = fixture();
    const invalidAmount = multiple.add("strategy.profile.reserve_rub", "", false, true);
    const fractionalMonths = multiple.add("strategy.profile.horizon_months", "6.5", false);
    multiple.context.edit(invalidAmount);
    multiple.context.edit(fractionalMonths);
    assert.equal(multiple.state.strategy.draft.profile.horizon_months, "24", "Integer-only terms are never silently floored");
    invalidAmount.value = "5000";
    invalidAmount.nativeValid = true;
    invalidAmount.badInput = false;
    multiple.context.edit(invalidAmount);
    multiple.removeForm();
    await multiple.context.save();
    assert.equal(multiple.writes.length, 0);
    assert.equal(multiple.state.strategy.dirty, true, "Recovering one field cannot hide another invalid field");
    assert.equal(multiple.context.status(), "error");
    multiple.remote({version: 2, document: structuredClone(multiple.state.strategy.draft)});
    await multiple.context.retry();
    assert.equal(multiple.context.status(), "error", "Successful reconciliation cannot clear validation metadata");
    assert.equal(multiple.context.blocked(), true);
    assert.equal(multiple.state.strategy.invalidInputs[fractionalMonths.name], "6.5");
    multiple.remote({version: 3});
    await multiple.context.reload();
    assert.equal(multiple.state.strategy.invalidInputs[fractionalMonths.name], "6.5", "An incomplete read response cannot discard pending input");
    multiple.remote({version: 2, document: structuredClone(multiple.state.strategy.draft)});
    await multiple.context.reload();
    assert.equal(Object.keys(multiple.state.strategy.invalidInputs).length, 0, "Explicit server reload discards invalid input");
    assert.equal(multiple.context.status(), "saved");

    const exact = fixture();
    for (const [name, value] of [["strategy.profile.reserve_rub", "123456789.12345678"], ["strategy.policy.turnover_budget_percent", "20.375"], ["strategy.profile.max_drawdown_percent", "0.1234"]]) {
      exact.context.edit(exact.add(name, value));
    }
    await exact.context.save();
    assert.equal(exact.writes.length, 1);
    assert.equal(exact.writes[0].document.profile.reserve_rub, "123456789.12345678");
    assert.equal(exact.writes[0].document.profile.max_drawdown_percent, "0.1234");
    assert.equal(exact.writes[0].document.policy.turnover_budget_percent, "20.375");
    const rating = exact.add("strategy.rules.rating_caps.AAA", "", false);
    exact.context.edit(rating);
    await exact.context.save();
    assert.equal(exact.writes.length, 1, "Clearing a required numeric rule cannot save null");
    assert.equal(exact.state.strategy.draft.rules.rating_caps.AAA, "0.1234");
    console.log("PASS actual-source strategy numeric input: held ACK, removed DOM, valid null, exact decimals, integer rejection, multiple invalid fields, reconciliation and explicit reload.");
  }
  await exercise();
}
function startupBuildContracts() {
  for (const [bundleBuild, releaseBuild] of [["__OMNICIO_BUILD__", undefined], [build, undefined], [build, build]]) {
    const reachedApplication = new Error("compatible modules reached document initialization");
    const document = {currentScript: {src: `http://127.0.0.1/assets/app.js?build=${bundleBuild}`}, documentElement: {dataset: {}}, querySelector: selector => selector === "#startup-state" ? {} : null};
    const context = sourceContext({window: {}, document, URL, getComputedStyle: () => ({getPropertyValue: () => JSON.stringify(bundleBuild)})});
    if (releaseBuild) context.window.OMNICIO_RELEASE = {build: releaseBuild};
    for (const name of ["config", "i18n", "workspace"]) vm.runInContext(readFileSync(join(root, "web", `${name}.js`), "utf8").replaceAll("__OMNICIO_BUILD__", bundleBuild), context);
    context.window.OMNICIO_I18N = {...context.window.OMNICIO_I18N, apply() { throw reachedApplication; }};
    const app = readFileSync(join(root, "web", "app.js"), "utf8").replaceAll("__OMNICIO_BUILD__", bundleBuild);
    assert.throws(() => vm.runInContext(app, context), error => error === reachedApplication, "A coherent raw/dev or stamped bundle starts without relying on optional version.js metadata");
  }
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const boundary = app.slice(app.indexOf("  function compatibleStartup("), app.indexOf("  async function reloadStartup("));
  let paletteBuild = JSON.stringify(build);
  const context = sourceContext({compiledBuild: build, window: {}, URL,
    document: {querySelector: () => ({}), documentElement: {}, currentScript: {src: `http://127.0.0.1/assets/app.js?build=${build}`}},
    getComputedStyle: () => ({getPropertyValue: () => paletteBuild})});
  vm.runInContext(boundary + "\nglobalThis.compatible=compatibleStartup;", context);
  const translations = {compiledBuild: build, t() {}, html() {}, apply() {}, getLocale() {}};
  const ui = {compiledBuild: build, parseRoute() {}, routeHash() {}, resumeRoute() {}};
  assert.equal(context.compatible(translations, ui, clientConfig), true);
  for (const value of ["", JSON.stringify(build + "-stale"), "unquoted-build", "null"]) {
    paletteBuild = value;
    assert.equal(context.compatible(translations, ui, clientConfig), false, "Missing, stale and malformed palette identity cannot start the account");
  }
  paletteBuild = JSON.stringify(build);
  for (const config of [undefined, {...clientConfig, compiledBuild: build + "-stale"}]) assert.equal(context.compatible(translations, ui, config), false, "Missing or stale configuration cannot start the account");
  console.log("PASS startup build contracts: coherent bundles, independent metadata, missing/stale configuration and CSS identity");
}
function goalRouteContracts(ui) {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const opener = app.slice(app.indexOf("  const openGoal ="), app.indexOf("  const updateGoalFields ="));
  const entry = app.slice(app.indexOf("  function enterRouteScreen("), app.indexOf("  async function restoreRouteOverlay("));
  const state = {view: "goals", route: ui.parseRoute("#account/goals/create"), data: {goals: {items: [{id: "goal-a", title: "A"}, {id: "goal-b", title: "B"}]}}};
  const navigations = [], opened = [];
  const context = sourceContext({state, navigate: (...args) => navigations.push(args), requireUser: () => true, goalDocument: goal => goal || {}, T: value => value, H: value => value, esc: String, field: () => "", select: () => "", openDialog: (...args) => opened.push(args), updateGoalFields() {}});
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
function quotePrecisionContracts(ui) {
  const clean = text => text.replaceAll("\u00a0", " ").replaceAll("\u202f", " ");
  const cases = [
    ["0.00345", "currency", "0,00345 ₽", "RUB 0.00345"],
    ["0.000000001", "currency", "0,000000001 ₽", "RUB 0.000000001"],
    ["99.999", "percent_nominal", "99,999 % номинала", "99.999 % of face value"],
    ["123456.000000001", "points", "123 456,000000001 пунктов", "123,456.000000001 points"],
    ["10000000.000000001", "currency", "10 000 000,000000001 ₽", "RUB 10,000,000.000000001"],
    ["9223372036854775807.999999999", "currency", "9 223 372 036 854 775 807,999999999 ₽", "RUB 9,223,372,036,854,775,807.999999999"]
  ];
  for (const [locale, column] of [["ru", 2], ["en", 3]]) {
    ui.setLocale(locale);
    for (const item of cases) assert.equal(clean(ui.marketPrice(item[0], item[1], "RUB")), item[column], "Quotation precision is visible in " + locale);
  }
  ui.setLocale("en");
  assert.equal(ui.format("9007199254740993.123456789", 9), "9,007,199,254,740,993.123456789", "Validated decimal strings cannot be rounded through Number before formatting");
  assert.equal(clean(ui.money("9007199254740993.123456789", 9, "RUB", false)), "RUB 9,007,199,254,740,993.123456789");
  assert.equal(ui.money("10000000.000000001", 9, "", false), "10,000,000.000000001", "Unknown currency keeps the source digits without inventing a currency");
  assert.equal(ui.marketPrice(1e-9, "points"), "0.000000001 points", "Already numeric nano values remain supported");
  ui.setPrivacy(true);
  for (const unit of ["currency", "percent_nominal", "points", "per_nominal", "unknown"]) {
    assert.equal(ui.marketPrice("0.00345", unit, "RUB", true), "••••••", "Personal values respect privacy for every unit");
    assert.equal(ui.marketPrice("not-a-price", unit, "RUB", true), "—", "Privacy cannot turn an unknown price into an implied known value");
  }
  assert.equal(clean(ui.marketPrice("0.00345", "currency", "RUB", false)), "RUB 0.00345", "Public market prices remain visible when personal balances are masked");
  ui.setPrivacy(false);
  ui.setLocale("ru");
  console.log("PASS quote precision: nano, currency, nominal percent, points, exact decimal strings, locales and privacy");
}
function assetQuotePrecisionContracts(ui) {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const start = app.indexOf("  const quotationNanos =");
  assert.ok(start >= 0, "Asset extrema use the source decimal contract");
  const source = app.slice(start, app.indexOf("  const assetChartMarkup =", start));
  const context = sourceContext({number: ui.number, marketPrice: ui.marketPrice, money: ui.money, percent: ui.percent, esc: ui.escape, T: value => value, H: value => value, renderAssetValue: () => ""});
  vm.runInContext(source + "\nglobalThis.pricing=assetPricing;globalThis.quote=assetQuoteHTML;globalThis.extreme=assetPriceExtreme;", context);
  const smaller = "10000000.000000001", larger = "10000000.000000002";
  assert.equal(Number(smaller), Number(larger), "The fixture exposes two source prices that Number cannot distinguish");
  for (const values of [[smaller, larger], [larger, smaller]]) {
    const candles = values.map(value => ({open: value, close: value, high: value, low: value}));
    const price = context.pricing({market: {last_price: smaller, price_unit: "currency", price_currency: "RUB", candles}});
    assert.equal(price.current, smaller, "The asset header and Last price retain the source string");
    assert.equal(price.high, larger, "High selects the exact source decimal in either candle order");
    assert.equal(price.low, smaller, "Low selects the exact source decimal in either candle order");
    assert.ok(context.quote(price).includes("10\u00a0000\u00a0000,000000001"));
  }
  for (const value of [null, undefined, false, "0", "-1", "NaN", "Infinity", "1e-9", "0.0000000001", "12345678901234567890"]) assert.equal(context.extreme([{high: value}], "high"), null, "Out-of-contract OHLC remains unknown");
  assert.equal(context.extreme([{low: "0.000000001"}], "low"), "0.000000001");
  assert.equal(context.extreme([{high: "9223372036854775807.999999999"}], "high"), "9223372036854775807.999999999", "The full positive int64/nano source range is comparable without Number");
  for (const [open, last, expected] of [[larger, smaller, "-0.000000001"], [smaller, larger, "0.000000001"], [smaller, smaller, "0"], ["1.000000001", "0.999999999", "-0.000000002"], ["250", "251.75", "1.75"]]) {
    const price = context.pricing({market: {last_price: last, price_unit: "currency", price_currency: "RUB", candles: [{open}]}});
    assert.equal(price.change, expected, "Visible absolute change preserves the exact source difference");
    assert.ok(context.quote(price).includes(ui.marketPrice(expected, "currency", "RUB")), "The exact delta reaches the asset quote consumer");
  }
  for (const open of [null, undefined, "0", "-1", "NaN", "1e-9"]) assert.equal(context.pricing({market: {last_price: smaller, candles: [{open}]}}).change, null, "Missing or invalid opening price cannot produce a delta");
  const cash = context.quote({market: {cash_price: "0.000000001", cash_price_currency: "RUB"}, current: "1", change: null, changePercent: null, priceUnit: "points", currency: "RUB"});
  assert.ok(cash.includes("0,000000001"), "The displayed cash price does not round a positive source price to zero");
  console.log("PASS asset source prices: raw current, exact high/low and absolute change, cash price");
}
function quoteChartPrecisionContracts(ui) {
  const first = "10000000.000000001", last = "10000000.000000002";
  const markup = ui.chart([{time: "2026-01-01T00:00:00Z", close: first}, {time: "2026-01-02T00:00:00Z", close: last}], {timeKey: "time", valueKey: "close", currency: "RUB", personal: false});
  assert.ok(markup.includes("10\u00a0000\u00a0000,000000002"), "Initial chart readout uses the last raw observation");
  const listeners = new Map(), attributes = new Map();
  const readout = {firstElementChild: {}, lastElementChild: {}};
  const element = {setAttribute() {}};
  const hover = {setAttribute() {}, querySelector: () => element};
  const block = {querySelector: () => readout, querySelectorAll: () => []};
  const svg = {dataset: {chart: /data-chart="([^"]+)"/.exec(markup)[1]}, querySelector: () => hover, closest: () => block, addEventListener: (name, handler) => listeners.set(name, handler), setAttribute: (name, value) => attributes.set(name, value), getBoundingClientRect: () => ({left: 0, width: 480})};
  ui.bindCharts({querySelectorAll: () => [svg]});
  listeners.get("keydown")({key: "Home", preventDefault() {}});
  assert.ok(readout.lastElementChild.textContent.includes("10\u00a0000\u00a0000,000000001"), "Keyboard selection preserves the first source decimal");
  assert.ok(attributes.get("aria-label").includes("10\u00a0000\u00a0000,000000001"), "Accessible readout uses the same source observation");
  listeners.get("pointermove")({clientX: 480});
  assert.ok(readout.lastElementChild.textContent.includes("10\u00a0000\u00a0000,000000002"), "Pointer selection preserves the last source decimal");
  assert.ok(attributes.get("aria-label").includes("10\u00a0000\u00a0000,000000002"));
  console.log("PASS source chart readouts: initial, keyboard, pointer and accessibility retain exact decimal strings");
}
function eventReadReceiptContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const start = app.indexOf("  const eventIsRead =");
  const end = app.indexOf("  const paintEventRow =", start);
  assert.ok(start >= 0 && end > start, "Read receipt contracts exercise the actual application reconciliation");
  const context = sourceContext({});
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
  const counts = sourceContext({state, number: value => value == null ? null : Number(value)});
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
  const context = sourceContext({
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
async function browserProtocolContracts() {
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
  let protocolNow = 0;
  const context = sourceContext({WebSocket: SyntheticSocket, setTimeout, clearTimeout, performance: {now: () => protocolNow}, until: (read, label) => until(read, label, 6)});
  vm.runInContext(source.slice(from, to) + "\nglobalThis.connect=protocolClient;globalThis.session=browserSession;", context);
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
  socket.emit("message", {data: JSON.stringify({method: "Page.javascriptDialogClosed", sessionId: "target"})});
  const read = client.send("Runtime.evaluate", {expression: "document.readyState"}, "target");
  const rejected = assert.rejects(read, error => error.method === "Runtime.evaluate" && error.code === -32000 && error.protocolMessage === "Inspected target navigated or closed");
  socket.emit("message", {data: JSON.stringify({id: socket.sent.at(-1).id, error: {code: -32000, message: "Inspected target navigated or closed"}})});
  await rejected;
  assert.equal(socket.sent.filter(item => item.method === "Runtime.evaluate").length, 1, "The transport never replays an evaluation");
  await assert.rejects(client.send("Runtime.evaluate", {expression: "document.readyState"}, "target", 5), /CDP timeout: Runtime.evaluate/, "A stalled read respects the remaining navigation budget");
  assert.equal(socket.sent.filter(item => item.method === "Runtime.evaluate").length, 2, "A read timeout cannot replay its command");
  client.close();
  for (const method of ["Page.navigate", "Page.reload"]) {
    let frames = 0, reads = 0, actions = 0;
    const navigationParams = method === "Page.navigate" ? {url: "http://127.0.0.1/?case=next"} : {ignoreCache: true};
    const send = context.session({send: async (command, params, sessionId) => {
      assert.equal(sessionId, "target");
      if (command === "Page.getFrameTree") return {frameTree: {frame: {id: "main", loaderId: ++frames < 3 ? "old" : "new"}}};
      if (command === method) { assert.deepEqual(params, navigationParams); actions += 1; return {frameId: "main", loaderId: "new"}; }
      assert.equal(command, "Runtime.evaluate");
      assert.equal(params.expression, "document.readyState", "Only a fixed read-only readiness expression may be retried");
      reads += 1;
      if (reads === 1) throw Object.assign(new Error("Context changed"), {method: command, code: -32000, protocolMessage: "Inspected target navigated or closed"});
      return {result: {value: reads === 2 ? "loading" : "interactive"}};
    }}, "target");
    await send(method, navigationParams);
    assert.equal(actions, 1, "Navigation is issued once while the new document becomes readable");
    assert.equal(reads, 3, "A changed loader alone cannot acknowledge a loading document");
  }
  const sameDocumentCalls = [];
  const sameDocument = context.session({send: async command => {
    sameDocumentCalls.push(command);
    return command === "Page.getFrameTree" ? {frameTree: {frame: {id: "main", loaderId: "same"}}} : {};
  }}, "target");
  await sameDocument("Page.navigate", {url: "http://127.0.0.1/#next"});
  assert.deepEqual(sameDocumentCalls, ["Page.getFrameTree", "Page.navigate"], "Same-document navigation does not wait for a nonexistent new loader");
  for (const failure of [
    {navigation: {errorText: "net::ERR_CONNECTION_REFUSED"}, message: /did not open a document/},
    {navigation: {isDownload: true}, message: /did not open a document/},
    {frame: {id: "other", loaderId: "new"}, message: /changed the inspected main frame/},
    {frame: {id: "main"}, message: /loader identity is missing/},
    {frame: {id: "main", loaderId: ""}, message: /loader identity is missing/},
    {evaluation: {exceptionDetails: {text: "Context unavailable"}}, message: /readiness evaluation failed/},
    {evaluation: {result: {value: null}}, message: /readiness is missing/}
  ]) {
    let frames = 0, actions = 0, reads = 0;
    const failed = context.session({send: async command => {
      if (command === "Page.getFrameTree") return {frameTree: {frame: ++frames === 1 ? {id: "main", loaderId: "old"} : failure.frame || {id: "main", loaderId: "new"}}};
      if (command === "Page.navigate") { actions += 1; return failure.navigation || {frameId: "main", loaderId: "new"}; }
      assert.equal(command, "Runtime.evaluate");
      reads += 1;
      return failure.evaluation || {result: {value: "interactive"}};
    }}, "target");
    await assert.rejects(failed("Page.navigate", {url: "http://127.0.0.1/?case=invalid"}), failure.message);
    assert.equal(actions, 1, "Invalid navigation evidence cannot replay the action");
    assert.equal(reads, failure.evaluation ? 1 : 0, "Malformed navigation, frame or readiness evidence fails immediately");
  }
  let actions = 0;
  const unchanged = context.session({send: async command => {
    if (command === "Page.getFrameTree") return {frameTree: {frame: {id: "main", loaderId: "old"}}};
    actions += 1;
    return {loaderId: "new"};
  }}, "target");
  await assert.rejects(unchanged("Page.reload"), /Timed out: New document after Page.reload/);
  assert.equal(actions, 1, "An unchanged document times out without replaying the reload");
  for (const failure of [new Error("Application read failed"), Object.assign(new Error("Other protocol error"), {method: "Runtime.evaluate", code: -32000, protocolMessage: "Other failure"})]) {
    let frames = 0;
    const failed = context.session({send: async command => {
      if (command === "Page.getFrameTree") return {frameTree: {frame: {id: "main", loaderId: ++frames === 1 ? "old" : "new"}}};
      if (command === "Page.reload") return {};
      throw failure;
    }}, "target");
    await assert.rejects(failed("Page.reload"), error => error === failure, "Other errors are never treated as pending navigation");
  }
  const budgets = [];
  const expired = context.session({send: async (command, params, sessionId, timeout) => {
    budgets.push(timeout);
    protocolNow += 8000;
    return command === "Page.getFrameTree" ? {frameTree: {frame: {id: "main", loaderId: "old"}}} : {};
  }}, "target");
  await assert.rejects(expired("Page.reload"), /Timed out: New document after Page.reload/);
  assert.deepEqual(budgets, [15000, 7000], "Slow commands share one deadline and no request starts after it");
  console.log("PASS browser protocol: native dialog failure, exact command diagnostics, new-document acknowledgement, same-document navigation, bounded read-only retry and no action replay");
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
const resolveStyleTokens = (value, palette, visited = []) => {
  assert.equal(typeof value, "string", "A checked style property must exist");
  const resolved = value.replace(/var\((--[\w-]+)(?:,\s*([^()]*))?\)/g, (_, name, fallback) => {
    assert.ok(!visited.includes(name), "CSS token references cannot form a cycle: " + name);
    return resolveStyleTokens(palette[name] ?? fallback, palette, [...visited, name]);
  });
  if (resolved !== value) return resolveStyleTokens(resolved, palette, visited);
  assert.ok(!resolved.includes("var("), "Every checked CSS token resolves: " + resolved);
  return resolved;
};
const styleContracts = () => {
  const css = readFileSync(join(root, "web", "app.css"), "utf8");
  const tokens = readFileSync(join(root, "web", "tokens.css"), "utf8");
  const styles = tokens + "\n" + css;
  const declared = new Set([...styles.matchAll(/(--[\w-]+)\s*:/g)].map(item => item[1]));
  for (const reference of styles.matchAll(/var\((--[\w-]+)(,)?/g)) assert.ok(declared.has(reference[1]) || reference[2], "CSS custom property must exist or have a fallback: " + reference[1]);
  assert.ok(!/#[a-f0-9]{3,8}\b/i.test(css), "All authored colors have one palette source");
  const base = cssRule(tokens, ":root");
  assert.equal(JSON.parse(base["--omnicio-build"]), "__OMNICIO_BUILD__", "The stylesheet participates in startup release integrity");
  for (const color of ["--browser-theme-dark", "--browser-theme-light"]) assert.match(base[color], /^#[a-f0-9]{6}$/i, "Public chrome has one literal theme token");
  for (const selector of [":root", ":root[data-theme=light]"]) {
    const palette = {...base, ...cssRule(tokens, selector)};
    for (const text of ["--text", "--muted", "--subtle", "--blue-light", "--green", "--red", "--purple", "--gold"]) {
      for (const surface of ["--bg", "--panel", "--panel-deep", "--panel-hover"]) assertTextContrast(resolveStyleTokens(palette[text], palette), resolveStyleTokens(palette[surface], palette), selector + " " + text + " on " + surface);
    }
    assertTextContrast("#ffffff", resolveStyleTokens(palette["--blue"], palette), selector + " selected controls");
  }
  for (const selector of [".button.primary", ".button.primary:hover", ".vk-provider", ".vk-provider:hover", ".strategy-option .strategy-icon"]) {
    const rule = cssRule(css, selector);
    for (const background of resolveStyleTokens(rule.background, base).match(/#[a-f0-9]{6}\b/gi) || []) assertTextContrast("#ffffff", background, selector);
  }
  const avatar = cssRule(css, ".avatar");
  for (const background of resolveStyleTokens(avatar.background, base).match(/#[a-f0-9]{6}\b/gi)) assertTextContrast(resolveStyleTokens(avatar.color, base), background, "Profile avatar text");
  console.log("PASS style contracts: declared tokens and normal-text contrast in both themes");
};
function workerBindingDatabase() {
  const values = new Map(), stores = new Set();
  const database = {
    objectStoreNames: {contains: name => stores.has(name)},
    createObjectStore: name => { stores.add(name); },
    close() {},
    transaction() {
      const transaction = {};
      let pending = 0, completed = false;
      const request = operation => {
        const result = {};
        pending += 1;
        queueMicrotask(() => {
          result.result = operation();
          result.onsuccess?.({target: result});
          pending -= 1;
          queueMicrotask(() => { if (!pending && !completed) { completed = true; transaction.oncomplete?.(); } });
        });
        return result;
      };
      transaction.objectStore = () => ({get: key => request(() => values.get(key)), put: (value, key) => request(() => values.set(key, structuredClone(value))), delete: key => request(() => values.delete(key))});
      return transaction;
    }
  };
  return {values, indexedDB: {open() {
    const request = {};
    queueMicrotask(() => {
      request.result = database;
      if (!stores.size) request.onupgradeneeded?.({target: request});
      request.onsuccess?.({target: request});
    });
    return request;
  }}};
}
const workerContract = async () => {
  const handlers = new Map();
  const tasks = [];
  const notifications = [];
  const opened = [];
  const bindings = workerBindingDatabase();
  const cacheStores = new Map();
  const fetches = [], writes = [], repairTimers = new Map();
  let activated = 0, storageFailure = false, networkFailure = false;
  let responseBuild = build, responseStatus = 200, responseUrl = null, fetchGate = null;
  const origin = "https://example.test";
  const cacheName = "omnicio-public-" + build;
  const publicPaths = ["/offline.html", "/assets/config.js", "/assets/tokens.css", "/assets/i18n.js", "/assets/app.css", "/assets/app.js", "/assets/workspace.js", "/assets/brand/omnicio-logo.png"];
  const publicUrls = publicPaths.map(path => origin + path + "?build=" + encodeURIComponent(build));
  const requestUrl = value => new URL(typeof value === "string" ? value : value.url, origin).href;
  const cacheStorage = {
    async open(name) {
      if (storageFailure) throw new Error("Synthetic storage failure");
      if (!cacheStores.has(name)) cacheStores.set(name, new Map());
      const values = cacheStores.get(name);
      return {
        match: async request => values.get(requestUrl(request))?.clone(),
        put: async (request, response) => { const key = requestUrl(request); writes.push(key); values.set(key, response.clone()); }
      };
    },
    keys: async () => [...cacheStores.keys()],
    delete: async name => cacheStores.delete(name),
    async match(request) {
      for (const values of cacheStores.values()) {
        const response = values.get(requestUrl(request));
        if (response) return response.clone();
      }
      return undefined;
    }
  };
  const context = vm.createContext({
    location: {origin},
    addEventListener: (name, handler) => handlers.set(name, handler),
    registration: {showNotification: async (title, options) => notifications.push({title, options: clone(options)})},
    clients: {matchAll: async () => [], openWindow: async path => opened.push(path), claim: async () => {}},
    skipWaiting: async () => { activated += 1; },
    caches: cacheStorage, indexedDB: bindings.indexedDB, URL, AbortController, MessageChannel,
    setTimeout(handler, ms) {
      if (ms !== clientConfig.timing.publicCacheRepairMs) return setTimeout(handler, ms);
      const timer = {};
      repairTimers.set(timer, handler);
      return timer;
    },
    clearTimeout(timer) { if (!repairTimers.delete(timer)) clearTimeout(timer); },
    async fetch(request, options) {
      const url = requestUrl(request);
      fetches.push({url, options});
      if (networkFailure) throw new Error("Synthetic offline network");
      if (fetchGate) await Promise.race([fetchGate, new Promise((_, reject) => {
        if (options.signal.aborted) reject(new Error("Synthetic aborted fetch"));
        else options.signal.addEventListener("abort", () => reject(new Error("Synthetic aborted fetch")), {once: true});
      })]);
      const body = publicAssets[new URL(url).pathname.replace(/^\//, "")] || "Public brand asset";
      const response = new Response(body, {status: responseStatus, headers: responseBuild === null ? {} : {"X-Omnicio-Build": responseBuild}});
      Object.defineProperty(response, "url", {value: responseUrl || url});
      return response;
    },
    importScripts(...urls) {
      for (const url of urls) {
        const parsed = new URL(url, origin);
        assert.equal(parsed.origin, origin);
        assert.equal(parsed.searchParams.get("build"), build);
        const source = publicAssets[parsed.pathname.replace(/^\//, "")];
        assert.ok(source, "The worker imports the actual compiled public asset");
        vm.runInContext(source, context);
      }
    }
  });
  context.self = context;
  const self = context;
  try {
    vm.runInContext(publicAssets["sw.js"], context);
    assert.equal(context.window, undefined, "Worker imports do not rely on a browser window");
    handlers.get("install")({waitUntil: task => tasks.push(task)});
    await Promise.all(tasks);
    assert.deepEqual([...cacheStores.get(cacheName).keys()].sort(), [...publicUrls].sort());
    assert.ok(fetches.every(({options}) => options.credentials === "omit" && options.cache === "no-store" && options.redirect === "error"), "Only explicit public requests enter the cache");
    assert.equal(repairTimers.size, 0, "Completed installation releases its deadline");
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
    const workerMessage = async (data, messageOrigin = origin) => {
      let receipt;
      const pending = [];
      handlers.get("message")({origin: messageOrigin, data, ports: [{postMessage: value => { receipt = clone(value); }}], waitUntil: task => pending.push(task)});
      await Promise.all(pending);
      return receipt;
    };
    const repair = () => workerMessage({type: "REPAIR_PUBLIC_CACHE", build});
    const initialFetches = fetches.length, initialWrites = writes.length;
    assert.deepEqual(await repair(), {handled: true, ok: true});
    assert.equal(fetches.length, initialFetches, "A coherent complete cache requires no network repair");
    assert.equal(writes.length, initialWrites, "Normal startup does not rewrite its public cache");
    assert.equal(await workerMessage({type: "REPAIR_PUBLIC_CACHE", build: "wrong-build"}), undefined);
    assert.equal(await workerMessage({type: "REPAIR_PUBLIC_CACHE", build}, "https://untrusted.invalid"), undefined);
    cacheStores.delete(cacheName);
    let releaseFetch;
    fetchGate = new Promise(resolve => { releaseFetch = resolve; });
    const repairs = [repair(), repair()];
    await until(() => fetches.length === initialFetches + publicUrls.length, "Concurrent repair requests share one fetch batch");
    releaseFetch();
    assert.deepEqual(await Promise.all(repairs), [{handled: true, ok: true}, {handled: true, ok: true}]);
    fetchGate = null;
    assert.equal(writes.length, initialWrites + publicUrls.length);
    assert.deepEqual([...cacheStores.get(cacheName).keys()].sort(), [...publicUrls].sort(), "Recovery repopulates the full offline shell with the unchanged worker");
    // Reproduce manual recovery deleting a cache after an older fill obtained
    // its handle. The new startup joins that fill and must receive a usable name.
    cacheStores.get(cacheName).delete(publicUrls[1]);
    const beforeRaceFetches = fetches.length;
    fetchGate = new Promise(resolve => { releaseFetch = resolve; });
    const olderRepair = repair();
    await until(() => fetches.length === beforeRaceFetches + 1, "An older repair holds one missing asset fetch");
    cacheStores.delete(cacheName);
    const recoveryRepair = repair();
    releaseFetch();
    assert.deepEqual(await Promise.all([olderRepair, recoveryRepair]), [{handled: true, ok: true}, {handled: true, ok: true}]);
    fetchGate = null;
    assert.deepEqual([...cacheStores.get(cacheName).keys()].sort(), [...publicUrls].sort(), "A coalesced recovery fills the current named cache, including assets lost from the detached old handle");
    networkFailure = true;
    let navigation;
    handlers.get("fetch")({request: {url: origin + "/?private=session", method: "GET", mode: "navigate"}, respondWith: task => { navigation = task; }});
    const offline = await navigation;
    assert.equal(offline.headers.get("X-Omnicio-Build"), build);
    assert.match(await offline.text(), /data-offline-retry/, "The repaired cache can serve the real public offline page");
    assert.ok(!writes.some(url => url.includes("private=session")), "Navigation and session HTML cannot enter the repair cache");
    networkFailure = false;
    for (const failure of ["missing-header", "stale-header", "bad-status", "foreign-url", "storage"]) {
      cacheStores.delete(cacheName);
      const before = writes.length;
      responseBuild = failure === "missing-header" ? null : failure === "stale-header" ? "old-build" : build;
      responseStatus = failure === "bad-status" ? 503 : 200;
      responseUrl = failure === "foreign-url" ? "https://untrusted.invalid/assets/app.js" : null;
      storageFailure = failure === "storage";
      assert.deepEqual(await repair(), {handled: true, ok: false}, "Public repair reports " + failure);
      assert.equal(writes.length, before, "No unvalidated response is published after " + failure);
    }
    storageFailure = false; responseBuild = build; responseStatus = 200; responseUrl = null;
    fetchGate = new Promise(() => {});
    const timedOut = repair();
    await until(() => repairTimers.size === 1, "A stalled repair has one bounded deadline");
    for (const expire of repairTimers.values()) expire();
    assert.deepEqual(await timedOut, {handled: true, ok: false});
    fetchGate = null;
    assert.equal(repairTimers.size, 0);
    assert.deepEqual(await repair(), {handled: true, ok: true}, "Failure releases the single-flight guard so a later online repair can succeed");
    const bindingA = "00000000-0000-4000-9000-000000000001";
    const bindingB = "00000000-0000-4000-9000-000000000002";
    assert.deepEqual(await workerMessage({type: "PUSH_BINDING", binding_id: bindingA, locale: "ru"}), {handled: true, ok: true, binding_id: bindingA});
    assert.deepEqual([...bindings.values.values()], [{binding_id: bindingA, locale: "ru"}], "The worker stores only an opaque delivery binding and the interface language");
    assert.deepEqual(await workerMessage({type: "PUSH_BINDING", binding_id: "not-a-binding"}), {handled: true, ok: false});
    assert.equal([...bindings.values.values()][0].binding_id, bindingA, "Invalid messages fail without changing the existing binding");
    assert.equal(await workerMessage({type: "PUSH_BINDING", binding_id: bindingB}, "https://untrusted.invalid"), undefined);
    assert.equal([...bindings.values.values()][0].binding_id, bindingA, "A foreign-origin message cannot change the installation owner");
    for (const url of ["https://untrusted.invalid/#events", "/#events?event=" + "a".repeat(64), "/?credential=secret#events", "/#settings"]) {
      handlers.get("push")({data: {json: () => ({title: "PRIVATE GOAL", body: "PRIVATE AMOUNT", url, tag: "a".repeat(64), binding_id: bindingA})}, waitUntil: task => tasks.push(task)});
    }
    await Promise.all(tasks);
    assert.deepEqual(notifications.map(item => item.options.data.url), ["/#account/events", "/#account/events/detail?event=" + "a".repeat(64), "/#account/events", "/#account/settings/notifications"]);
    assert.ok(notifications.every(item => item.title === "OMNICIO" && !item.options.body.includes("PRIVATE")), "Lock-screen push never shows private source content");
    let closed = false;
    handlers.get("notificationclick")({notification: {data: {url: "https://untrusted.invalid/"}, close: () => {closed = true;}}, waitUntil: task => tasks.push(task)});
    await Promise.all(tasks);
    assert.equal(closed, true);
    assert.deepEqual(opened, ["/#account/events"]);
    await workerMessage({type: "PUSH_BINDING", binding_id: bindingB, locale: "en"});
    assert.deepEqual(await workerMessage({type: "CLEAR_PUSH_BINDING", binding_id: bindingA}), {handled: true, ok: true, cleared: false}, "A delayed old-account cleanup cannot erase the new binding");
    assert.equal([...bindings.values.values()][0].binding_id, bindingB);
    handlers.get("push")({data: {json: () => ({url: "/#account/events/detail?event=" + "b".repeat(64), binding_id: bindingA, body: "PRIVATE OLD ACCOUNT"})}, waitUntil: task => tasks.push(task)});
    await Promise.all(tasks);
    assert.equal(notifications.at(-1).options.data.url, "/#account/events", "An old account's notification never carries its detail into the current installation");
    assert.equal(notifications.at(-1).options.data.binding_id, null);
    assert.ok(notifications.at(-1).options.body.startsWith("New information"));
    const messages = [], navigated = [];
    let focused = 0;
    self.clients.matchAll = async () => [{url: origin + "/legal/privacy.html", focused: true}, {url: "https://untrusted.invalid/", focused: true}, {
      url: origin + "/?case=draft#account/goals/create", focused: false, visibilityState: "visible",
      postMessage: (data, ports) => { messages.push(data); ports[0].postMessage({handled: true, navigated: false}); ports[0].close(); },
      navigate: async path => navigated.push(path), focus: async () => { focused += 1; }
    }];
    handlers.get("notificationclick")({notification: {data: {url: "/#account/events/detail?event=" + "c".repeat(64), binding_id: bindingB}, close() {}}, waitUntil: task => tasks.push(task)});
    await Promise.all(tasks);
    assert.equal(messages.at(-1).type, "OPEN_NOTIFICATION");
    assert.equal(messages.at(-1).binding_id, bindingB);
    assert.equal(messages.at(-1).url, "/#account/events/detail?event=" + "c".repeat(64));
    assert.equal(focused, 1);
    assert.deepEqual(navigated, [], "A ready app's deliberate refusal preserves its unsaved draft; the worker does not override it");
    assert.deepEqual(opened, ["/#account/events"], "An existing app that handled the click cannot spawn a duplicate tab");
    const stalled = {
      url: origin + "/#account/goals/create", draft: "A preserved local draft", focused: true,
      postMessage: (_data, ports) => { ports[0].close(); },
      navigate: async path => { navigated.push(path); stalled.url = path; stalled.draft = ""; },
      focus: async () => { focused += 1; }
    };
    self.clients.matchAll = async () => [stalled];
    handlers.get("notificationclick")({notification: {data: {url: "/#account/events", binding_id: bindingB}, close() {}}, waitUntil: task => tasks.push(task)});
    await Promise.all(tasks);
    assert.equal(focused, 2, "An unresponsive or older app still receives focus");
    assert.deepEqual(navigated, [], "No acknowledgement is not permission to replace an existing document");
    assert.equal(stalled.url, origin + "/#account/goals/create");
    assert.equal(stalled.draft, "A preserved local draft");
    assert.deepEqual(opened, ["/#account/events"], "The worker cannot open another tab when an existing app does not acknowledge");
    assert.deepEqual(await workerMessage({type: "CLEAR_PUSH_BINDING", binding_id: bindingB}), {handled: true, ok: true, cleared: true});
    assert.equal(bindings.values.size, 0, "Only the matching binding is cleared after a logout or explicit revocation");
    console.log("PASS service worker: versioned cache repair, offline recovery, bounded failures, private-cache isolation, origin checks and safe notifications");
  } finally {
    for (const expire of repairTimers.values()) expire();
    repairTimers.clear();
    handlers.clear();
    cacheStores.clear();
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
const screenshotEvidenceNames = new Set(["portfolio-2-320.png", "market-2-320.png", "strategies-2-390.png", "strategies-custom-2-390.png", "auth-2-390.png", "auth-2-320.png", "failure-state.png", "payout-source-normal-ru-320.png", "payout-source-ambiguous-ru-320.png", "payout-source-normal-en-320.png", "payout-source-ambiguous-en-320.png"]);
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
  const workerDiagnostics = {errors: [], registrations: [], versions: []};
  const workerObservers = {
    "ServiceWorker.workerErrorReported": params => { workerDiagnostics.errors = [...workerDiagnostics.errors, params.errorMessage].slice(-20); },
    "ServiceWorker.workerRegistrationUpdated": params => { workerDiagnostics.registrations = params.registrations; },
    "ServiceWorker.workerVersionUpdated": params => { workerDiagnostics.versions = [...workerDiagnostics.versions, ...params.versions].slice(-20); }
  };
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
    // Worker-global failures do not reach the page's error event. Keep bounded
    // native CDP evidence so an install failure has a concrete diagnostic.
    if (Object.hasOwn(workerObservers, message.method)) workerObservers[message.method](message.params);
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
    if (message.error) waiter.reject(Object.assign(new Error(`CDP ${waiter.method}: ${message.error.message}`), {method: waiter.method, code: message.error.code, protocolMessage: message.error.message}));else waiter.done(message.result);
  });
  return {
    get nativeDialog() { return nativeDialog; },
    get workerDiagnostics() { return workerDiagnostics; },
    send(method, params = {}, sessionId, timeout = 15000) {
      if (nativeDialog && nativeDialog.sessionId === sessionId && method !== "Browser.close") return Promise.reject(dialogError(method));
      return new Promise((done, reject) => {
        const id = ++sequence;
        const timer = setTimeout(() => {
          pending.delete(id);
          reject(new Error("CDP timeout: " + method));
        }, timeout);
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
const browserSession = (client, sessionId) => async (method, params = {}) => {
  if (!["Page.navigate", "Page.reload"].includes(method)) return client.send(method, params, sessionId);
  const label = "New document after " + method;
  const deadline = performance.now() + 15000;
  const command = (name, options = {}) => {
    const remaining = deadline - performance.now();
    if (remaining <= 0) throw new Error("Timed out: " + label);
    return client.send(name, options, sessionId, remaining);
  };
  const previous = (await command("Page.getFrameTree")).frameTree.frame;
  if (!previous.id || typeof previous.loaderId !== "string") throw new Error("Main frame identity is missing");
  const result = await command(method, params);
  if (result.errorText || result.isDownload) throw new Error(`${method} did not open a document: ${result.errorText || "download"}`);
  if (method === "Page.navigate" && !result.loaderId) return result;
  await until(async () => {
    const current = (await command("Page.getFrameTree")).frameTree.frame;
    if (current.id !== (result.frameId || previous.id)) throw new Error("Navigation changed the inspected main frame");
    if (current.loaderId === previous.loaderId) return false;
    if (typeof current.loaderId !== "string" || !current.loaderId) throw new Error("New document loader identity is missing");
    try {
      const document = await command("Runtime.evaluate", {expression: "document.readyState", returnByValue: true, awaitPromise: false});
      if (document.exceptionDetails) throw new Error("Document readiness evaluation failed: " + document.exceptionDetails.text);
      if (!["loading", "interactive", "complete"].includes(document.result?.value)) throw new Error("Document readiness is missing");
      return document.result.value !== "loading";
    } catch (error) {
      if (error.method === "Runtime.evaluate" && error.code === -32000 && error.protocolMessage === "Inspected target navigated or closed") return false;
      throw error;
    }
  }, label);
  return result;
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
    const send = browserSession(client, sessionId);
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
    await send("ServiceWorker.enable");
    await send("Page.addScriptToEvaluateOnNewDocument", {
      source: 'window.__browserErrors=[];window.__cspViolations=[];addEventListener("error",e=>window.__browserErrors.push(e.error?.stack||e.message));addEventListener("unhandledrejection",e=>window.__browserErrors.push(e.reason?.stack||String(e.reason)));addEventListener("securitypolicyviolation",e=>window.__cspViolations.push(e.effectiveDirective));'
    });
    await send("Page.addScriptToEvaluateOnNewDocument", {source: `(${installPushBrowserFixture.toString()})(${JSON.stringify(pushFixtureKey)})`});
    await send("Page.addScriptToEvaluateOnNewDocument", {source: `(${installPromptBrowserFixture.toString()})()`});
    const evaluate = async expression => {
      const result = await send("Runtime.evaluate", {
        expression,
        returnByValue: true,
        awaitPromise: true
      });
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text + ": " + (result.exceptionDetails.exception?.description || ""));
      return result.result.value;
    };
    const revealScreenMenu = async selector => evaluate(`(() => {
      const element=document.querySelector(${JSON.stringify(selector)});
      const picker=element?.closest('.screen-menu')?.closest('.screen-menu-picker:not([open])');
      if (!picker) return;
      const summary=picker.querySelector(':scope > summary');
      if (!summary?.getClientRects().length) throw new Error('Section menu has no visible summary');
      summary.click();
      if (!picker.open || !element.getClientRects().length) throw new Error('Section menu did not reveal its links');
    })()`);
    const revealControl = async selector => {
      await revealScreenMenu(selector);
      const section = await evaluate(`(() => { const matches=[...document.querySelectorAll(${JSON.stringify(selector)})]; const element=matches.find(item=>item.getClientRects().length) || matches[0]; if (!element || element.getClientRects().length) return null; return element.closest("[data-screen-content]")?.dataset.screenContent || null; })()`);
      if (!section) return;
      const menuSelector = `.view:not([hidden]) .screen-menu [data-route][data-screen="${section}"]`;
      await revealScreenMenu(menuSelector);
      await evaluate(`(() => { const menu=document.querySelector(${JSON.stringify(menuSelector)}); if(!menu?.getClientRects().length) throw new Error("No visible section menu for requested control"); menu.click(); })()`);
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
        serviceWorker: client.workerDiagnostics,
        publicRequests: publicRequestDiagnostics,
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
        serviceWorker: client.workerDiagnostics,
        publicRequests: publicRequestDiagnostics,
        bodyText: documentState.bodyText?.slice(0, 3500),
        requests
      }, null, 2));
    };
    await exerciseStartupRecovery({send, configureViewport, base, wait, click, evaluate, checkLayout, screenshot});
    await exerciseInstallability({send, configureViewport, base, wait, evaluate});
    await exerciseInstallation({send, configureViewport, base, wait, click, evaluate, checkLayout, screenshot});
    await exercisePushLifecycle({send, configureViewport, base, wait, click, evaluate, fieldValue, checkLayout, screenshot});
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
      await exerciseAssetEnrichment({send, round, base, wait, evaluate, checkLayout});
      await exercisePayoutDisplay({send, configureViewport, round, base, wait, click, evaluate, checkLayout, screenshot});
      await exerciseSafeUpdate({send, configureViewport, round, base, wait, click, evaluate, fieldValue, checkLayout});
      await exerciseQuotePrecision({send, configureViewport, round, base, wait, click, evaluate, checkLayout, screenshot});
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
    await payoutDisplayContracts();
    await payoutEventHistoryContracts();
    assetPayoutDisclosureContracts();
    dialogCloseContracts();
    await evidenceFileReadContracts();
    await assetBackgroundChartContracts();
    await ledgerPaginationContracts();
    await searchAndAssetPaginationContracts();
    await visibleRefreshContracts();
    await newsMonitoringContracts();
    settingsRecoveryContracts();
    await offlineQuoteContracts();
    await assistantConversationContracts();
    await assistantMemoryReconciliationContracts();
    await strategyInputContracts();
    await installLifecycleContracts();
    await installPromptInterleavingContracts();
    await pushEndpointContracts();
    await pushContextContracts();
    await pushBindingReceiptContracts();
    await pushPermissionReadFailureContracts();
    await deletedDraftContracts();
    await browserProtocolContracts();
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
    captured_at: new Date().toISOString(),
    valid_until: new Date(Date.now() + 300000).toISOString(),
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
  await holdAssetEnrichment(fixture, "details");
  return sendJSON(response, {
    status: "observed",
    current_holding: {status: fixture.closedPosition ? "not_held" : "held", quantity: fixture.closedPosition ? "0" : positions[0].quantity, observed_at: stamp},
    latest: {
      ...positions[0],
      captured_at: stamp
    },
    sources: [],
    payouts: fixture.assetPayouts || [],
    history: []
  });
}
async function serveTestMarketInstruments({
  response,
  fixture
}) {
  await holdAssetEnrichment(fixture, "facts");
  return sendJSON(response, {
    instrument_uid: "synthetic-a",
    currency: "rub",
    name: fixture.enrichmentName || (fixture.precisionCase ? "Synthetic precision contract" : "Тестовая компания A"),
    ticker: fixture.enrichmentTicker || "SYNA",
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
    if (!fixture.holdMarketStream) response.write(fixture.precisionCase?.market_event || serverContracts.instrument_market_event);
    return;
  }
  if (fixture.precisionCase) return sendJSON(response, fixture.precisionCase.market);
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
  if (uid) await holdAssetEnrichment(fixture, "news");
  const items = fixture.news.filter(item => (!uid || item.instrument_uids.includes(uid)) && JSON.stringify(item).toLowerCase().includes(query));
  const offset = Number(url.searchParams.get("cursor") || 0);
  const limit = Number(url.searchParams.get("limit") || 50);
  return sendJSON(response, {items: clone(items.slice(offset, offset + limit)), next_cursor: offset + limit < items.length ? String(offset + limit) : null, scanned_items: Math.min(limit, items.length - offset), instrument_uid: uid, source: "Изолированный источник", observed_at: stamp, status: items.length ? "received" : "empty"});
}
async function holdAssetEnrichment(fixture, kind) {
  if (fixture.holdAssetParts?.has(kind)) await new Promise(release => fixture.heldAssetParts.set(kind, release));
}
async function serveTestNotifications({fixture, path, body, method, response}) {
  if (path === "/api/notifications" && fixture.holdNotifications) await new Promise(release => fixture.heldNotifications.push(release));
  if (path === "/api/notifications" && fixture.failNotifications) return sendJSON(response, {detail: "synthetic_notification_read_failure"}, 503);
  if (path === "/api/notifications/push") return serveTestPush({fixture, body, response});
  if (path === "/api/notifications/push/test") {
    const channel = fixture.notificationChannels.find(item => item.id === body.channel_id && item.current_session);
    if (!channel) return sendJSON(response, {detail: "notification_channel_not_found"}, 404);
    if (channel.status !== "active") return sendJSON(response, {detail: "notification_channel_inactive"}, 409);
    const delivery = {id: `fixture-push-test-${fixture.notificationDeliveries.length + 1}`, kind: "test", status: "queued", attempts: 0, created_at: stamp, next_attempt_at: stamp, channel: {kind: "push", label: channel.label}};
    fixture.notificationDeliveries.push(delivery);
    return sendJSON(response, {id: delivery.id, status: "queued"});
  }
  if (method === "DELETE") {
    const channel = fixture.notificationChannels.find(item => item.id === path.split("/").at(-1));
    if (channel) { channel.status = "revoked"; channel.current_session = false; channel.binding_id = null; }
    return sendJSON(response, {revoked: true});
  }
  if (path === "/api/notifications" && method === "GET") return sendJSON(response, {enabled: true, push_configured: fixture.pushConfigured, email_configured: false, vapid_public_key: fixture.pushConfigured ? pushFixtureKey : null, channels: clone(fixture.notificationChannels.filter(item => !fixture.hideRevokedChannels || item.status !== "revoked")), deliveries: clone(fixture.notificationDeliveries), receipt_scope: "provider_acceptance_only"});
  return sendJSON(response, {detail: "synthetic_notification_route_missing"}, 404);
}
async function serveTestPush({fixture, body, response}) {
  const owner = fixture.user;
  if (fixture.holdPush) await new Promise(release => fixture.heldPush.push(release));
  if (owner !== fixture.user || fixture.mode === "guest") return sendJSON(response, {detail: "profile_context_changed"}, 409);
  if (fixture.failPush) return sendJSON(response, {detail: "notification_push_unavailable"}, 503);
  if (fixture.pushConflict) return sendJSON(response, {detail: "notification_device_conflict"}, 409);
  assert.ok(["enable", "sync"].includes(body.intent), "The UI makes explicit activation distinguishable from passive synchronization");
  const fingerprint = createHash("sha256").update(body.subscription.endpoint).digest("hex");
  let channel = fixture.notificationChannels.find(item => item.endpoint_fingerprint === fingerprint);
  if (channel?.status === "revoked" && body.intent === "sync") return sendJSON(response, {id: channel.id, status: "revoked", binding_id: null, current_session: false});
  if (!channel) {
    fixture.pushSequence += 1;
    channel = {id: `00000000-0000-4000-8000-${String(800 + fixture.pushSequence).padStart(12, "0")}`, kind: "push", label: body.label, endpoint_fingerprint: fingerprint};
    fixture.notificationChannels.push(channel);
  }
  channel.status = "active";
  channel.current_session = true;
  channel.binding_id ||= randomUUID();
  channel.verified_at = stamp;
  return sendJSON(response, {id: channel.id, status: channel.status, binding_id: channel.binding_id, current_session: true});
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
async function exerciseNotificationChannels({fixture, click, wait, evaluate}) {
  await click('#view-settings .screen-menu [data-screen="notifications"]');
  await wait('document.querySelector("#notification-settings [data-device-push-state]")', "The notification page exposes this device's actual delivery state");
  assert.equal(await evaluate('document.querySelectorAll("#notification-email-form, form[id^=notification-verify]").length'), 0, "Push setup does not ask the user for email, SMS or external credentials");
  assert.equal(fixture.requests.filter(item => item.path.startsWith("/api/notifications/email/")).length, 0);
}
async function exerciseNewsMonitoring({fixture, click, wait, evaluate, checkLayout, screenshot, round}) {
  const original = clone(fixture.refreshStatus);
  const refreshPosts = () => fixture.requests.filter(item => item.path === "/api/workspace/refresh" && item.method === "POST").length;
  const before = refreshPosts();
  await click('#view-settings [data-screen="broker"]');
  for (const status of ["received", "partial", "unavailable"]) {
    fixture.refreshStatus = {...original, status: "succeeded", news: clone(serverContracts.refresh_news_cases[status].news)};
    await evaluate('document.querySelector("#main-content").focus(); window.dispatchEvent(new Event("focus"))');
    const expected = await evaluate(`window.OMNICIO_I18N.t(${JSON.stringify("news.monitor." + status)})`);
    await wait(`document.querySelector("[data-news-monitor-status]")?.textContent.includes(${JSON.stringify(expected)})`, "The current news status arrives through the visible refresh GET");
    assert.ok(await evaluate('document.querySelector("[data-news-monitor-status]").textContent.includes(window.OMNICIO_I18N.t("news.monitor.scope"))'), "The settings show the limited broker-feed coverage");
    if (status !== "received") assert.ok(await evaluate(`!document.querySelector("#connection-banner").hidden && document.querySelector("#connection-banner").textContent.includes(${JSON.stringify(expected)})`), "News gaps are visible alongside usable account data");
    await checkLayout(`news-monitoring-${status}-${round}-390`);
  }
  assert.equal(refreshPosts(), before, "Checking autonomous news status never enqueues a portfolio refresh");
  await screenshot(`news-monitoring-unavailable-${round}-390.png`);
  fixture.refreshStatus = original;
  await evaluate('document.querySelector("#main-content").focus(); window.dispatchEvent(new Event("focus"))');
  await wait('document.querySelector("[data-news-monitor-status]")?.textContent.includes(window.OMNICIO_I18N.t("news.monitor.not_requested"))', "The isolated case restores its original collection state");
  await click('#sidebar-nav [data-route="settings"]');
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
  await wait('document.querySelector("#notification-settings [data-device-push-state]") && !document.querySelector("#notification-settings .notice.error")', "The retry restores the failed notification resource");
  const retried = fixture.requests.slice(before);
  assert.equal(retried.filter(item => item.path === "/api/notifications" && item.method === "GET").length, 1);
  assert.equal(retried.filter(item => item.path === "/api/workspace/refresh" && item.method === "POST").length, 0, "A notification read must not start portfolio collection");
  assert.equal(await evaluate('document.querySelector("#preferences-form").elements.quiet_start.value'), "21:15", "An unrelated unsaved settings draft survives resource recovery");
  await fieldValue("#preferences-form", "quiet_start", previousTime);
  fixture.failNotifications = true;
  await click('#notification-settings [data-action="notifications-reload"]');
  await wait(`document.querySelector(${JSON.stringify(retry)}) && document.querySelector("#notification-settings [data-device-push-state]")`, "A failed later read reports its error alongside the last known channels");
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
async function exerciseResearchMathematics({fixture,click,wait,evaluate,configureViewport,checkLayout,screenshot,round}) {
  const run = fixture.researchRuns[0];
  const original = clone(run);
  const open = async () => {
    await click('#strategy-research [data-research-operation="open"]');
    await wait('document.querySelector("#workspace-dialog").open && location.hash.includes("/strategies/result")', "The saved research has its own addressable result screen");
  };
  const close = async () => {
    await click('#workspace-dialog [data-close-dialog]');
    await wait('!document.querySelector("#workspace-dialog").open && !location.hash.includes("/strategies/result")', "Back navigation finishes before the next research result opens");
  };
  const revealSection = async marker => {
    await evaluate('new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))');
    const selector = "#dialog-content [" + marker + "]";
    const visible = await evaluate(`(() => {
      const section = document.querySelector(${JSON.stringify(selector)});
      section.scrollIntoView({behavior:'instant',block:'start'});
      const heading = section.querySelector(':scope > summary, :scope > h3');
      const rect = heading.getBoundingClientRect();
      const dialog = document.querySelector('#workspace-dialog');
      const header = dialog.querySelector('.dialog-header').getBoundingClientRect();
      return {width:innerWidth,height:innerHeight,top:rect.top,bottom:rect.bottom,headerBottom:header.bottom,headerTop:header.top,
        scrollportTop:dialog.getBoundingClientRect().top+dialog.clientTop,
        hittable:heading.contains(document.elementFromPoint(rect.left+rect.width/2,rect.top+rect.height/2))};
    })()`);
    assert.ok(visible.headerTop <= visible.scrollportTop + 1, 'The sticky header covers the top of the scrollport: ' + marker);
    assert.ok(visible.top >= visible.headerBottom, 'The research heading is below the sticky header: ' + marker);
    assert.ok(visible.bottom <= visible.height, 'The complete research heading fits the viewport: ' + marker);
    assert.equal(visible.hittable, true, 'The research heading is not covered by another element: ' + marker);
    console.log(`PASS research heading ${round}/${marker}: ${JSON.stringify(visible)}`);
  };
  Object.assign(run, {result: {...clone(serverContracts.research_outcomes_result), strategy_version: run.strategy_version}, status: "computed", metrics: clone(serverContracts.research_outcomes_result.metrics)});
  await open();
  await wait('document.querySelector("#dialog-content [data-research-outcomes]")', "The UI receives the actual calculator's historical-outcome schema");
  await click('#dialog-content [data-research-outcome-sessions="1"] summary');
  const actual = await evaluate(`document.querySelector('#dialog-content [data-research-outcome-sessions="1"]').textContent`);
  assert.ok(actual.includes("Историческая частота прибыли") && actual.includes("50") && actual.includes("95% интервал исторической частоты"));
  await click('#dialog-content [data-research-outcome-sessions="5"] summary');
  const insufficient = await evaluate(`document.querySelector('#dialog-content [data-research-outcome-sessions="5"]').textContent`);
  assert.ok(insufficient.includes("12") && insufficient.includes("Полных непересекающихся окон недостаточно"), "The longer horizon shows real window counts without inventing a percentage");
  for (const width of [390, 320, 1366]) {
    await configureViewport(width);
    await revealSection("data-research-outcomes");
    await checkLayout(`research-math-${round}-${width}`, {minCharts: 1});
    await screenshot(`research-math-${round}-${width}.png`);
  }
  await configureViewport(390);
  await close();
  for (const [key, incomplete] of [["research_cash_result", false], ["research_cash_incomplete_result", true]]) {
    const result = clone(serverContracts[key]);
    Object.assign(run, {result: {...result, strategy_version: run.strategy_version}, status: result.status, metrics: result.metrics});
    await open();
    await wait('document.querySelector("#dialog-content [data-research-cash-model]")', "A cash-only result uses the separate real model contract");
    const text = await evaluate('document.querySelector("#dialog-content").textContent');
    assert.ok(text.includes("Денежная модель не содержит рыночных наблюдений"));
    assert.equal(await evaluate('Boolean(document.querySelector("#dialog-content .chart-path"))'), false, "A cash model cannot fabricate a market chart");
    if (incomplete) assert.ok(text.includes("Резерв вне инвестиций") && text.includes("готовность стратегии не подтверждена"));
    for (const width of [390, 320]) {
      await configureViewport(width);
      await checkLayout(`research-cash-${incomplete}-${round}-${width}`);
      await screenshot(`research-cash-${incomplete}-${round}-${width}.png`);
    }
    await configureViewport(390);
    await close();
  }
  for (const [key, marker, label] of [["research_ladder_result", "data-ladder-rungs", "ladder"], ["research_dividend_result", "data-dividend-coverage", "dividends"]]) {
    const result = clone(serverContracts[key]);
    Object.assign(run, {result: {...result, strategy_version: run.strategy_version}, status: result.status, metrics: result.metrics});
    await open();
    await wait(`document.querySelector('#dialog-content [${marker}]')`, "The real preset calculator has its own detailed output");
    await click(`#dialog-content details:has([${marker}]) > summary`);
    await click(`#dialog-content [${marker}] > summary`);
    const details = await evaluate(`document.querySelector('#dialog-content [${marker}]').textContent`);
    if (label === "ladder") assert.ok(details.includes("Ступень 5") && details.includes("Заполненная доля"));
    else assert.ok(details.includes("600 USD") && details.includes("не гарантирует будущие выплаты"));
    for (const width of [390, 320, 1366]) {
      await configureViewport(width);
      await revealSection(marker);
      await checkLayout(`research-${label}-${round}-${width}`);
      await screenshot(`research-${label}-${round}-${width}.png`);
    }
    await configureViewport(390);
    await close();
  }
  Object.assign(run, original);
  await open();
  await wait('document.querySelector("#dialog-content").textContent.includes("Нет достаточной истории")', "The original isolated request remains intact after result-display contracts");
  await close();
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
  await exerciseNewsMonitoring(context);
  await exerciseNotificationRetry(context);
  await exerciseAnalyticsReadConsistency(context);
  await exerciseSearchReadConsistency(context);
  await exerciseGoalSourceContract(context);
  await exerciseResearchSubmission(context);
  await exerciseResearchMathematics(context);
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
  assert.equal(await evaluate('Boolean(document.querySelector(".assistant-stream"))'), false, "Deleting a conversation removes its cancelled request and provisional answer");
  await click('#view-assistant [data-action="assistant-new"]');
  await until(()=>fixture.conversations.length===1,"Create conversation for deletion race");
  await wait('document.querySelector("[data-action=chat-clear]")',"New conversation becomes selected");
  assert.equal(await evaluate('Boolean(document.querySelector(".assistant-stream"))'), false, "A new conversation has no controls for a request from the previous conversation");
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
  for (const channel of fixture.notificationChannels) {
    if (channel.kind === "push" && channel.current_session) Object.assign(channel, {status: "revoked", binding_id: null, current_session: false});
  }
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
async function exercisePayoutDisplay({send, configureViewport, round, base, wait, click, evaluate, checkLayout, screenshot}) {
  await configureViewport(320);
  const locale = round === 1 ? "ru" : "en";
  const key = `signed-payout-display-${round}`, fixture = makeFixture("signed");
  fixture.prefs.document.locale = locale;
  fixture.enrichmentName = "Payout contract company";
  fixture.events = Object.values(clone(serverContracts.payout_event_cases));
  fixtures.set(key, fixture);
  const target = `${base}?case=${key}`;
  for (const disputed of [false, true]) {
    fixture.assetPayouts = clone(serverContracts.payout_visualization.payouts.filter(item => (item.identity_status === "ambiguous") === disputed));
    const cohort = disputed ? "ambiguous" : "normal";
    const navigation = await send("Page.navigate", {url: `${target}&payout=${cohort}#account/asset?uid=synthetic-a`});
    assert.ok(navigation.loaderId, "Each payout source cohort loads a new document");
    const summary = disputed ? "payout.identity.ambiguous" : "Подтверждённые события выплат";
    await wait(`document.documentElement.lang === ${JSON.stringify(locale)} && document.querySelector('#view-asset h1')?.textContent === 'Payout contract company' && document.querySelector('#view-asset [data-asset-payouts] summary')?.textContent === window.OMNICIO_I18N.t(${JSON.stringify(summary)}) && !document.querySelector('#view-asset .loading-panel')`, "The asset receives the expected payout source cohort: " + cohort);
    assert.equal(await evaluate('document.querySelector("#view-asset [data-asset-payouts]").open'), false, "The new payout disclosure starts closed before its single native click");
    await click("#view-asset [data-asset-payouts] summary");
    await wait('document.querySelector("#view-asset [data-asset-payouts]").open', "Payment records have a visible disclosure path");
    const text = await evaluate('document.querySelector("#view-asset [data-asset-payouts]").textContent');
    const labels = disputed ? ["payout.identity.ambiguous", "payout.identity.note", "payout.identity.unconfirmed", "payout.date.source"] : ["Подтверждённые события выплат", "events.expected", "payout.date.actual", "payout.date.unknown"];
    for (const label of labels) assert.ok(text.includes(await evaluate(`window.OMNICIO_I18N.t(${JSON.stringify(label)})`)), "The real disclosure contains its labelled source status: " + label);
    if (disputed) assert.ok(!text.includes(await evaluate('window.OMNICIO_I18N.t("Подтверждённые события выплат")')));
    const dated = fixture.assetPayouts.find(item => item.status === "paid" && item.actual_at);
    assert.ok(text.includes(await evaluate(`window.OmniUI.date(${JSON.stringify(dated.actual_at)})`)), "The actual payment date survives the real source read and DOM rendering");
    assert.ok(!text.includes(await evaluate(`window.OmniUI.date(${JSON.stringify(dated.record_at)})`)), "The disclosure does not substitute the record date");
    await evaluate('document.querySelector("#view-asset [data-asset-payouts]").scrollIntoView({block:"start"})');
    await checkLayout(`payout-source-${disputed ? "ambiguous" : "normal"}-${locale}-320`);
    await screenshot(`payout-source-${disputed ? "ambiguous" : "normal"}-${locale}-320.png`);
  }
  for (const kind of ["superseded", "ambiguous"]) {
    const event = serverContracts.payout_event_cases[kind];
    await send("Page.navigate", {url: `${target}#account/events/detail?event=${event.id}`});
    await wait('document.querySelector("#workspace-dialog").open && document.querySelector("#dialog-title").textContent === window.OMNICIO_I18N.t("payout.identity.ambiguous") && !document.querySelector("#dialog-content .loading-panel")', "The old event bookmark resolves to the uncertainty notice");
    const text = await evaluate('document.querySelector("#dialog-content").textContent');
    assert.ok(text.includes(await evaluate('window.OMNICIO_I18N.t("payout.identity.note")')) && text.includes("synthetic-a"));
    assert.ok(!text.includes(event.detail) && !text.includes("999.19"), "A historic direct link cannot display superseded financial claims");
    assert.ok(!text.includes(await evaluate(`window.OmniUI.date(${JSON.stringify(event.occurred_at)}, true)`)));
    await checkLayout(`payout-event-${kind}-${locale}-320`);
    await screenshot(`payout-event-${kind}-${locale}-320.png`);
  }
  await click('#dialog-content [data-action="event-destination"]');
  await wait('location.hash === "#account/asset?uid=synthetic-a" && document.querySelector("#view-asset [data-asset-payouts]")', "The warning retains its real instrument navigation");
  console.log(`PASS payout source display round ${round}: real DTO dates, visible uncertain records and safe historical event links at 320px in ${locale}`);
}
async function exerciseAssetEnrichment({send, round, base, wait, evaluate, checkLayout}) {
  const key = `signed-late-asset-${round}`;
  const fixture = makeFixture("signed");
  fixture.holdAssetParts = new Set(["details", "facts", "news"]);
  fixture.heldAssetParts = new Map();
  fixture.holdPublicNews = true;
  fixture.holdWorkspace = true;
  fixture.closedPosition = true;
  fixture.enrichmentName = "Late source company";
  fixture.enrichmentTicker = "LATE";
  fixtures.set(key, fixture);
  await send("Page.navigate", {url: `${base}?case=${key}#account/asset?uid=synthetic-a`});
  await until(() => fixture.heldAssetParts.size === 3, "All auxiliary asset responses are deliberately held");
  await until(() => fixture.heldPublicNews.length === 1 && fixture.heldWorkspace.length === 1, "Generic news and resumed workspace reads remain in flight independently of the asset");
  await wait('document.querySelector("#view-asset .chart-svg") && document.querySelector("#view-asset [data-market-quote] .main-value")?.textContent.includes("251,75")', "The chart is usable while details, facts and news are still pending");
  await evaluate('window.__enrichmentChart = document.querySelector("#view-asset .chart-svg"); window.__enrichmentChart.focus()');
  await send("Input.dispatchKeyEvent", {type: "keyDown", key: "Home", code: "Home", windowsVirtualKeyCode: 36});
  const selected = await evaluate('document.querySelector("#view-asset .chart-readout").textContent');
  const aria = await evaluate('window.__enrichmentChart.getAttribute("aria-label")');
  for (const [path, flag, pending] of [["/api/public/news", "holdPublicNews", "heldPublicNews"], ["/api/workspace", "holdWorkspace", "heldWorkspace"]]) {
    const completed = await evaluate(completedResourceCount(path));
    fixture[flag] = false;
    fixture[pending].splice(0).forEach(release => release());
    await wait(`${completedResourceCount(path)} > ${completed}`, "The intentionally late generic response completes: " + path);
    await checkLayout(`asset-enrichment-background-${path.split("/").at(-1)}-${round}`, {minCharts: 1});
    assert.equal(await evaluate('document.querySelector("#view-asset .chart-svg") === window.__enrichmentChart && document.activeElement === window.__enrichmentChart'), true, "Generic resource completion cannot replace the chart or its focus: " + path);
    assert.equal(await evaluate('document.querySelector("#view-asset .chart-readout").textContent'), selected, "The selected candle survives the actual generic repaint: " + path);
    assert.equal(await evaluate('window.__enrichmentChart.getAttribute("aria-label")'), aria, "The accessible selected observation survives the generic repaint: " + path);
  }
  const ready = {
    details: `Object.fromEntries([...document.querySelectorAll('#view-asset [data-asset-sidebar] .info-row')].map(row=>[row.querySelector('dt').textContent,row.querySelector('dd').textContent]))['Стоимость в портфеле'] === window.OmniUI.money('0')`,
    facts: `document.querySelector('#view-asset [data-asset-sidebar]').textContent.includes('11,25')`,
    news: `document.querySelector('#view-asset h1').textContent === 'Late source company' && document.querySelector('#view-asset .asset-detail-header p').textContent === 'LATE'`
  };
  for (const kind of ["details", "facts", "news"]) {
    fixture.holdAssetParts.delete(kind);
    fixture.heldAssetParts.get(kind)();
    fixture.heldAssetParts.delete(kind);
    await wait(ready[kind], "The late " + kind + " response updates its actual consumer");
    assert.equal(await evaluate('document.querySelector("#view-asset .chart-svg") === window.__enrichmentChart && document.activeElement === window.__enrichmentChart'), true, "Auxiliary asset data cannot replace the chart or its focus");
    assert.equal(await evaluate('document.querySelector("#view-asset .chart-readout").textContent'), selected, "The inspected first candle remains selected after " + kind);
    assert.equal(await evaluate('window.__enrichmentChart.getAttribute("aria-label")'), aria, "The selected accessible observation remains intact");
  }
  assert.equal(await evaluate('document.querySelector("#view-asset .asset-detail-header .asset-logo").textContent'), "L");
  assert.deepEqual(await evaluate('(() => { const watch=document.querySelector("#view-asset .asset-detail-header [data-watch]"); return [watch.dataset.watchName,watch.dataset.watchTicker]; })()'), ["Late source company", "LATE"], "The existing watch control receives the same final source metadata");
  await checkLayout(`asset-enrichment-${round}`, {minCharts: 1});
  await evaluate('delete window.__enrichmentChart');
  console.log(`PASS asset enrichment round ${round}: late generic news/workspace and held details/facts/news update their consumers while preserving the chosen candle, SVG and focus`);
}
function installPromptBrowserFixture() {
  if (new URLSearchParams(location.search).get("case") !== "guest-installation") return;
  // Only the controlled prompt scenario replaces the native dialog. The
  // separate manifest/installability scenario keeps the real browser event.
  window.addEventListener("beforeinstallprompt", event => {
    if (!event.isTrusted) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
}
function installPushBrowserFixture(publicKey) {
  const params = new URLSearchParams(location.search);
  if (!(params.get("case") || "").startsWith("push-")) return;
  const bytes = Uint8Array.from(atob(publicKey.replaceAll("-", "+").replaceAll("_", "/")), char => char.charCodeAt(0));
  const fixture = {permission: params.get("push_permission") || "default", permissionCalls: 0, subscribeCalls: 0, unsubscribeCalls: 0, holdPermission: false, subscription: null};
  const subscription = (endpoint, key = bytes) => ({
    endpoint,
    options: {applicationServerKey: key.buffer.slice(0)},
    toJSON: () => ({endpoint, expirationTime: null, keys: {p256dh: publicKey, auth: "AQEBAQEBAQEBAQEBAQEBAQ"}}),
    async unsubscribe() { fixture.unsubscribeCalls += 1; if (fixture.subscription?.endpoint === endpoint) fixture.subscription = null; return true; }
  });
  fixture.setSubscription = (endpoint, oldKey = false) => { fixture.subscription = subscription(endpoint, oldKey ? Uint8Array.from(bytes, value => value ^ 1) : bytes); };
  if (params.has("push_existing")) fixture.setSubscription("https://fcm.googleapis.com/fcm/send/fixture-existing", params.get("push_existing") === "old-key");
  const manager = {
    async getSubscription() {
      return fixture.subscription;
    },
    async subscribe(options) {
      fixture.subscribeCalls += 1;
      fixture.lastSubscribeOptions = {userVisibleOnly: options.userVisibleOnly, key: Array.from(options.applicationServerKey)};
      fixture.subscription = subscription(`https://fcm.googleapis.com/fcm/send/fixture-new-${fixture.subscribeCalls}`);
      return fixture.subscription;
    }
  };
  class TestNotification {
    static get permission() { return fixture.permission; }
    static async requestPermission() {
      fixture.permissionCalls += 1;
      if (fixture.holdPermission) await new Promise(resolve => { fixture.releasePermission = resolve; });
      fixture.permission = fixture.permissionResult || "granted";
      return fixture.permission;
    }
  }
  Object.defineProperty(window, "Notification", {configurable: true, value: TestNotification});
  Object.defineProperty(ServiceWorkerRegistration.prototype, "pushManager", {configurable: true, get: () => manager});
  window.__pushFixture = fixture;
}
async function installLifecycleContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const status = app.slice(app.indexOf("  const installStatus ="), app.indexOf("  const installContentsHTML ="));
  const actions = app.slice(app.indexOf("  const dismissInstall ="), app.indexOf("  const deliveryStateLabels ="));
  const installState = {prompt: null, installed: false, dismissed: false, busy: false, result: ""};
  const stored = new Map();
  let opens = 0, prompts = 0, installed = false;
  const navigator = {userAgent: "Chrome", platform: "Win32", maxTouchPoints: 0};
  const context = sourceContext({installState, navigator, installedDisplay: () => installed, H: value => value, localStorage: {setItem: (key, value) => stored.set(key, value)}, renderInstallState() {}, openInstall: () => { opens += 1; }});
  vm.runInContext(status + actions + "\nglobalThis.installActions={installStatus,installInstructionsHTML,dismissInstall,promptInstall};", context);
  const api = context.installActions;
  assert.equal(api.installStatus(), "manual", "No retained browser event means instructions, not a fake installation button");
  await api.promptInstall();
  assert.equal(opens, 1);
  let complete;
  installState.prompt = {prompt: async () => { prompts += 1; }, userChoice: new Promise(resolve => { complete = resolve; })};
  const pending = api.promptInstall();
  assert.equal(installState.prompt, null, "The native event is consumed before awaiting the user's choice");
  assert.equal(api.installStatus(), "pending");
  await api.promptInstall();
  assert.equal(prompts, 1, "Repeated clicks cannot invoke a single-use native prompt twice");
  complete({outcome: "dismissed"});
  await pending;
  assert.equal(installState.dismissed, true);
  assert.equal(stored.get("omnicio-install-dismissed"), "true");
  assert.equal(installState.result, "dismissed");
  await api.promptInstall();
  assert.equal(opens, 2, "Dismissing the promotion still leaves the permanent instruction path usable");
  assert.equal(prompts, 1);
  installState.prompt = {prompt: async () => { throw new Error("Browser no longer permits the prompt"); }};
  await api.promptInstall();
  assert.equal(installState.result, "unavailable");
  assert.equal(installState.busy, false);
  installed = true;
  assert.equal(api.installStatus(), "installed", "Standalone/fullscreen detection suppresses another installation offer");
  for (const [agent, platform, touches, expected] of [["iPhone", "iPhone", 5, "ios"], ["Safari", "MacIntel", 5, "ios"], ["Android", "Linux", 5, "android"], ["Chrome", "Win32", 0, "desktop"]]) {
    Object.assign(navigator, {userAgent: agent, platform, maxTouchPoints: touches});
    assert.ok(api.installInstructionsHTML().includes(`data-install-platform="${expected}"`), "Manual installation steps match the actual device capability, including iPad desktop user agents");
  }
  console.log("PASS actual installation lifecycle: single-use prompt, dismissal, persistent entry, installed display and platform instructions");
}
async function installPromptInterleavingContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const actions = app.slice(app.indexOf("  const dismissInstall ="), app.indexOf("  const deliveryStateLabels ="));
  const listener = app.slice(app.indexOf('  window.addEventListener("beforeinstallprompt"'), app.indexOf('  window.addEventListener("appinstalled"'));
  for (const isolated of [false, true]) {
    const handlers = [];
    const installState = {prompt: null, installed: false, dismissed: false, busy: false, result: ""};
    const context = sourceContext({installState, URLSearchParams, location: {search: `?case=${isolated ? "guest-installation" : "guest-installability"}`}, window: {addEventListener: (_name, callback) => handlers.push(callback)}, renderInstallState() {}, openInstall() {}, localStorage: {setItem() {}}});
    vm.runInContext(`(${installPromptBrowserFixture.toString()})();` + actions + listener + "\nglobalThis.promptInstall=promptInstall;", context);
    const dispatch = event => {
      event.preventDefault = () => { event.defaultPrevented = true; };
      event.stopImmediatePropagation = () => { event.stopped = true; };
      for (const handle of handlers) {
        handle(event);
        if (event.stopped) break;
      }
    };
    let prompts = 0, nativePrompts = 0, complete;
    const controlled = {isTrusted: false, prompt: async () => { prompts += 1; }, userChoice: new Promise(resolve => { complete = resolve; })};
    dispatch(controlled);
    assert.equal(controlled.defaultPrevented, true, "The actual application consumes the controlled event");
    const native = {isTrusted: true, prompt: async () => { nativePrompts += 1; throw new Error("Native prompt requires browser user activation"); }};
    dispatch(native);
    const pending = context.promptInstall();
    if (isolated) {
      assert.equal(installState.busy, true, "A late native event cannot replace the controlled pending choice");
      assert.equal(prompts, 1);
      assert.equal(nativePrompts, 0);
      complete({outcome: "accepted"});
      await pending;
      assert.equal(installState.result, "accepted");
    } else {
      await pending;
      assert.equal(installState.result, "unavailable", "Without fixture isolation the late native event reproduces the observed failure");
      assert.equal(prompts, 0);
      assert.equal(nativePrompts, 1, "The real installability scenario does not intercept native events");
    }
    assert.equal(installState.busy, false);
  }
  console.log("PASS actual install prompt interleaving: only the controlled fixture isolates late native events");
}
async function pushEndpointContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  const pushFingerprint ="), app.indexOf("  const withPushDeviceLock ="));
  const context = sourceContext({URL, crypto: require("node:crypto").webcrypto, TextEncoder});
  vm.runInContext(source + "\nglobalThis.fingerprint=pushFingerprint;", context);
  const endpoint = "https://fcm.googleapis.com/fcm/send/fixture-device?token=one";
  const expected = createHash("sha256").update(endpoint).digest("hex");
  assert.equal(await context.fingerprint({endpoint}), expected);
  assert.equal(await context.fingerprint({endpoint: "https://FCM.GoogleApis.com:443/fcm/send/fixture-device?token=one"}), expected, "Default ports and host casing share the server's canonical endpoint identity");
  assert.notEqual(await context.fingerprint({endpoint: endpoint.replace("token=one", "token=two")}), expected, "Distinct endpoint query tokens must remain different devices");
  console.log("PASS actual push endpoint identity: canonical origin, default port and significant provider query");
}
async function pushContextContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  const pushContext ="), app.indexOf("  const inspectPushDevice ="));
  const bytes = Uint8Array.from(Buffer.from(pushFixtureKey, "base64url"));
  const subscription = {endpoint: "https://fcm.googleapis.com/fcm/send/fixture-owner-a", options: {applicationServerKey: bytes.buffer}, toJSON: () => ({endpoint: "https://fcm.googleapis.com/fcm/send/fixture-owner-a"})};
  const data = {vapid_public_key: pushFixtureKey, channels: []};
  for (const [boundary, changed] of ["subscription", "receipt"].flatMap(boundary => ["generation", "identity"].map(changed => [boundary, changed]))) {
    const state = {generation: 1, user: {public_id: "000000123"}, locked: false, tour: false, devicePush: {status: "checking", channel: null, bindingId: null}};
    const writes = [], bindings = [];
    let releaseSubscription, releaseReceipt;
    const registration = {pushManager: {getSubscription: () => boundary === "subscription" ? new Promise(resolve => { releaseSubscription = resolve; }) : Promise.resolve(subscription)}, active: {postMessage: (...args) => bindings.push(args)}};
    const api = async (path, options) => { writes.push({path, options, publicId: state.user.public_id}); return new Promise(resolve => { releaseReceipt = resolve; }); };
    const context = sourceContext({state, navigator: {serviceWorker: {ready: Promise.resolve(registration)}}, window: {}, Uint8Array, URL, atob, crypto: require("node:crypto").webcrypto, TextEncoder, setTimeout, clearTimeout, api, T: value => value});
    vm.runInContext(source + "\nglobalThis.pushTest={pushContext,readPushSubscription};", context);
    const pending = context.pushTest.readPushSubscription(data, context.pushTest.pushContext(), true);
    await until(() => boundary === "subscription" ? releaseSubscription : releaseReceipt, "The actual push helper reaches its controlled " + boundary + " boundary");
    if (changed === "generation") state.generation += 1;
    else state.user = {public_id: "000000124"};
    state.devicePush = {status: "checking", channel: null, bindingId: null};
    if (boundary === "subscription") releaseSubscription(subscription);
    else releaseReceipt({id: "channel-a", status: "active", current_session: true, binding_id: "00000000-0000-4000-9000-000000000001"});
    await pending;
    assert.deepEqual(state.devicePush, {status: "checking", channel: null, bindingId: null}, "A late " + boundary + " result cannot mutate the next account's device state");
    assert.equal(bindings.length, 0, "An obsolete account cannot install its worker binding after a context switch");
    assert.equal(writes.length, boundary === "subscription" ? 0 : 1);
    if (writes.length) assert.equal(writes[0].publicId, "000000123", "An already sent request retains the old verified owner and is never replayed for the new one");
  }
  console.log("PASS actual push owner context: delayed subscription and server receipt cannot cross account generations");
}
async function pushBindingReceiptContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  const pushContext ="), app.indexOf("  const readPushSubscription ="));
  const channelId = "00000000-0000-4000-8000-000000000801";
  const bindingId = "00000000-0000-4000-9000-000000000001";
  const cases = [
    {status: "active", messages: 1},
    {workerAccepted: false, error: "service_worker_unavailable", status: "granted-pending", messages: 1},
    {currentSession: false, status: "granted-pending", messages: 0},
    {matchingBinding: false, error: "service_worker_unavailable", status: "granted-pending", messages: 1},
    {id: "invalid-channel", error: "notification_channel_invalid", status: "checking", messages: 0},
    {bindingId: "invalid-binding", error: "notification_channel_invalid", status: "checking", messages: 0}
  ];
  for (const scenario of cases) {
    const state = {generation: 1, user: {public_id: "000000123"}, locked: false, tour: false, devicePush: {status: "checking", channel: null, bindingId: null}};
    const messages = [];
    const registration = {active: {postMessage(message, ports) { messages.push(message); ports[0].postMessage({handled: true, ok: scenario.workerAccepted !== false, binding_id: scenario.matchingBinding === false ? "00000000-0000-4000-9000-000000000099" : message.binding_id}); ports[0].close(); }}};
    const context = sourceContext({state, I: {getLocale: () => "en"}, MessageChannel, setTimeout, clearTimeout, crypto: require("node:crypto").webcrypto, TextEncoder, URL});
    vm.runInContext(source + "\nglobalThis.pushTest={pushContext,adoptPushReceipt};", context);
    const receipt = {id: scenario.id || channelId, status: "active", current_session: scenario.currentSession !== false, binding_id: scenario.bindingId || bindingId};
    const pending = context.pushTest.adoptPushReceipt(receipt, {endpoint: "https://fcm.googleapis.com/fcm/send/fixture-receipt"}, registration, context.pushTest.pushContext());
    if (scenario.error) await assert.rejects(pending, {message: scenario.error});
    else await pending;
    assert.equal(state.devicePush.status, scenario.status, "The active state requires valid channel IDs, the current server session and a durable worker acknowledgement for the same binding");
    assert.equal(messages.length, scenario.messages);
    if (messages.length) assert.deepEqual(Object.keys(messages[0]).sort(), ["binding_id", "locale", "type"], "The worker receives no profile ID, source values or account content");
  }
  console.log("PASS actual push acknowledgement: current-session receipt and positive worker persistence are both required");
}
async function pushPermissionReadFailureContracts() {
  const app = readFileSync(join(root, "web", "app.js"), "utf8");
  const source = app.slice(app.indexOf("  const inspectPushDevice ="), app.indexOf("  const removeCurrentSubscription ="));
  for (const [permission, previousStatus, expected] of [["denied", "active", "denied"], ["default", "active", "default"], ["granted", "active", "active"], ["granted", "revoked", "revoked"], ["granted", "checking", "error"]]) {
    const failure = Object.assign(new Error("Server read failed"), {status: 503});
    const saved = {push_configured: true, channels: [{id: "00000000-0000-4000-8000-000000000801", status: "active"}]};
    const state = {user: {public_id: "000000123"}, devicePush: {status: previousStatus, pending: null}, data: {notifications: saved}, errors: {notifications: failure}, resourceRequests: new Map()};
    const reads = [];
    const context = sourceContext({state, Notification: {permission}, pushSupported: () => true, pushContext: () => ({}), currentPushContext: () => true, isCancelled: () => false, renderNotificationPanel() {}, loadResource: async (...args) => { reads.push(args); return saved; }});
    vm.runInContext(source + "\nglobalThis.refresh=refreshPushDevice;", context);
    await context.refresh();
    assert.equal(state.devicePush.status, expected, `Observed ${permission} browser permission and previous ${previousStatus} state remain truthful after a failed server read`);
    assert.equal(state.devicePush.error, failure, "The actual server error remains visible alongside the observed permission");
    assert.equal(state.devicePush.pending, null);
    assert.equal(state.data.notifications, saved, "A failed read does not fabricate a different set of server channels");
    assert.equal(reads.length, 1);
    assert.equal(reads[0][1], "/api/notifications");
  }
  console.log("PASS actual push permission failure: denied/default override cached active; granted preserves known state and the server error");
}
async function exerciseInstallability({send, configureViewport, base, wait, evaluate}) {
  const key = "guest-installability";
  fixtures.set(key, makeFixture("guest"));
  await configureViewport(390);
  await send("Page.navigate", {url: `${base}?case=${key}#public/welcome`});
  await wait('document.querySelector("#public-site")?.hidden===false && document.readyState==="complete"', "The real public application is ready for the browser installability check");
  await evaluate('navigator.serviceWorker.ready.then(() => true)');
  const manifest = await send("Page.getAppManifest");
  const installability = await send("Page.getInstallabilityErrors");
  const logo = readFileSync(join(root, "assets", "brand", "omnicio-logo.png"));
  const evidence = {manifest, installability, canonical_logo_sha256: createHash("sha256").update(logo).digest("hex")};
  writeFileSync(join(artifacts, "installability.json"), JSON.stringify(evidence, null, 2));
  console.log("INSTALLABILITY " + JSON.stringify(evidence));
  assert.deepEqual(manifest.errors, [], "Chromium parses the actual deployed manifest without errors");
  assert.equal(new URL(manifest.url).pathname, "/manifest.webmanifest");
  assert.deepEqual(JSON.parse(manifest.data), JSON.parse(publicAssets["manifest.webmanifest"]), "Installability uses the canonical production-rendered manifest, not a test substitute");
  assert.equal(evidence.canonical_logo_sha256, "d9c44905a77858882d99e948a647705afa853fd11cfd01efd37528645b8ca12f", "The installation check retains the approved original logo");
  assert.deepEqual(installability.installabilityErrors, [], "Chromium accepts the actual manifest and its declared original icon");
  console.log("PASS actual manifest and original brand installability");
}
async function exerciseInstallation({send, configureViewport, base, wait, click, evaluate, checkLayout, screenshot}) {
  const key = "guest-installation";
  fixtures.set(key, makeFixture("guest"));
  await evaluate('localStorage.removeItem("omnicio-install-dismissed")');
  await configureViewport(320);
  await send("Page.navigate", {url: `${base}?case=${key}#public/welcome`});
  await wait('document.querySelector("#public-site [data-install-promotion]")?.hidden===false', "A first visit offers installation through an explicit user control");
  await click('#public-site [data-action="pwa-install-later"]');
  await wait('[...document.querySelectorAll("[data-install-promotion]")].every(item=>item.hidden)', "Dismissal hides the optional promotion");
  await click('.public-nav [data-public-page="install"]');
  await wait('location.hash==="#public/install" && document.querySelector("#install [data-install-state]")', "The permanent installation entry remains reachable after dismissal");
  await checkLayout("installation manual 320");
  await screenshot("installation-manual-320.png");
  const origin = await evaluate("performance.timeOrigin");
  await send("Page.reload");
  await wait(`performance.timeOrigin!==${origin} && document.querySelector('#install [data-install-state]')`, "The install page is an independently reloadable route");
  assert.equal(await evaluate('localStorage.getItem("omnicio-install-dismissed")'), "true");
  await evaluate('(() => {const event=new Event("beforeinstallprompt",{cancelable:true});window.__installCalls=0;event.prompt=async()=>{window.__installCalls+=1;};event.userChoice=new Promise(resolve=>{window.__resolveInstall=resolve;});dispatchEvent(event);window.__installPrevented=event.defaultPrevented;})()');
  await wait('document.querySelector("#install [data-install-state=available]")', "A real retained-event consumer offers the browser installation prompt");
  assert.equal(await evaluate("window.__installPrevented"), true);
  await click('#install [data-action="pwa-install"]');
  await wait('document.querySelector("#install [data-install-state=pending]")', "The pending native prompt cannot be invoked twice");
  assert.equal(await evaluate("window.__installCalls"), 1);
  await evaluate('window.__resolveInstall({outcome:"accepted"});void 0');
  await wait('document.querySelector("#install [data-install-state=manual]")', "A browser acceptance is not invented proof of installation");
  await evaluate('dispatchEvent(new Event("appinstalled"));void 0');
  await wait('document.querySelector("#install [data-install-state=installed]")', "The browser installation event confirms the installed state");
  assert.equal(await evaluate('document.querySelectorAll("#install [data-action=pwa-install]").length'), 0);
  await configureViewport(390);
  await screenshot("installation-confirmed-390.png");
  console.log("PASS browser installation: dismiss, permanent link, reload, native single-use prompt and installed acknowledgement");
}
const pushPanel = "#notification-settings [data-device-push-state]";
async function openPushFixture({send, configureViewport, base, wait}, suffix, {permission = "default", existing = "", configure = () => {}} = {}) {
  const key = `push-${suffix}`, fixture = makeFixture("signed");
  configure(fixture);
  fixtures.set(key, fixture);
  await configureViewport(390);
  const query = new URLSearchParams({case: key, push_permission: permission});
  if (existing) query.set("push_existing", existing);
  await send("Page.navigate", {url: `${base}?${query}#account/settings/notifications`});
  await wait(`document.querySelector(${JSON.stringify(pushPanel)})`, "Current-device push panel: " + suffix);
  return fixture;
}
const pushWrites = fixture => fixture.requests.filter(item => item.path === "/api/notifications/push" && item.method === "POST");
const waitPushState = (wait, status) => wait(`document.querySelector(${JSON.stringify(pushPanel)})?.dataset.devicePushState===${JSON.stringify(status)}`, "Current-device state: " + status);
async function exercisePushLifecycle(context) {
  const {wait, click, evaluate, screenshot} = context;
  const fixture = await openPushFixture(context, "default");
  await waitPushState(wait, "default");
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 0, "Opening the page cannot ask for OS permission");
  assert.equal(pushWrites(fixture).length, 0);
  fixture.holdPush = true;
  await click('#notification-settings [data-action="notification-push"]');
  await until(() => fixture.heldPush.length === 1, "Browser permission and subscription exist while server activation is held");
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 1);
  assert.equal(await evaluate("window.__pushFixture.subscribeCalls"), 1);
  assert.equal(await evaluate(`document.querySelector(${JSON.stringify(pushPanel)}).dataset.devicePushState==="active"`), false, "A granted browser permission is not proof of an active account channel");
  fixture.holdPush = false;
  fixture.heldPush.shift()();
  await waitPushState(wait, "active");
  assert.equal(pushWrites(fixture)[0].body.intent, "enable");
  assert.equal(pushWrites(fixture)[0].profile, fixture.user);
  assert.equal(await evaluate("window.__pushFixture.lastSubscribeOptions.userVisibleOnly"), true);
  await click('#notification-settings [data-action="notification-push-test"]');
  await wait('document.querySelector("[data-push-test-status=queued]")', "A test message acknowledges only its server queue receipt");
  assert.equal(fixture.notificationDeliveries[0].status, "queued");
  assert.equal(fixture.notificationDeliveries[0].attempts, 0);
  await evaluate('document.querySelector("#notification-settings").scrollIntoView({block:"center",behavior:"instant"});void 0');
  await screenshot("push-test-queued-390.png");
  await click('#notification-settings [data-action="notification-revoke"]');
  await until(() => fixture.notificationChannels[0].status === "revoked", "Explicit opt-out reaches the server");
  await wait('window.__pushFixture.unsubscribeCalls===1 && document.querySelector("#notification-settings [data-device-push-state]")?.dataset.devicePushState!=="active"', "Opt-out removes this browser subscription and its active indication");
  await exerciseExistingPush(context);
  await exercisePushFailures(context);
  await exercisePushNotificationNavigation(context);
  await exerciseLatePushPermission(context);
  console.log("PASS push browser lifecycle: explicit permission, server receipt, queued test, opt-out, passive sync, rotation, errors and logout isolation");
}
async function exerciseExistingPush(context) {
  const {wait, click, evaluate} = context;
  const existing = await openPushFixture(context, "existing", {permission: "granted", existing: "current"});
  await waitPushState(wait, "active");
  assert.ok(pushWrites(existing).length > 0);
  assert.ok(pushWrites(existing).every(item => item.body.intent === "sync"), "An already granted subscription is silently reconciled without a new opt-in");
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 0);
  assert.equal(await evaluate("window.__pushFixture.subscribeCalls"), 0);
  const revoked = await openPushFixture(context, "revoked", {permission: "granted", existing: "current", configure: fixture => {
    fixture.pushSequence = 1;
    fixture.hideRevokedChannels = true;
    fixture.notificationChannels.push({id: "00000000-0000-4000-8000-000000000801", kind: "push", label: "This device", status: "revoked", current_session: false, binding_id: null, endpoint_fingerprint: createHash("sha256").update("https://fcm.googleapis.com/fcm/send/fixture-existing").digest("hex")});
  }});
  await waitPushState(wait, "revoked");
  assert.equal(revoked.notificationChannels[0].status, "revoked", "Passive sync cannot reverse explicit opt-out");
  assert.ok(pushWrites(revoked).length > 0, "The exact sync receipt remains authoritative when the revoked channel is outside the bounded GET list");
  assert.ok(pushWrites(revoked).every(item => item.body.intent === "sync"));
  await click('#notification-settings [data-action="notification-push"]');
  await waitPushState(wait, "active");
  assert.equal(pushWrites(revoked).at(-1).body.intent, "enable");
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 0, "Re-enabling a channel with granted OS permission does not ask for it again");
  const rotated = await openPushFixture(context, "rotation", {permission: "granted", existing: "old-key"});
  await waitPushState(wait, "granted-pending");
  assert.equal(await evaluate("window.__pushFixture.unsubscribeCalls"), 0, "A passive read cannot replace an incompatible VAPID subscription");
  assert.equal(pushWrites(rotated).length, 0);
  await click('#notification-settings [data-action="notification-push"]');
  await waitPushState(wait, "active");
  assert.equal(await evaluate("window.__pushFixture.unsubscribeCalls"), 1);
  assert.equal(await evaluate("window.__pushFixture.subscribeCalls"), 1);
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 0);
  assert.equal(pushWrites(rotated).at(-1).body.intent, "enable");
}
async function exercisePushFailures(context) {
  const {wait, click, evaluate} = context;
  const denied = await openPushFixture(context, "denied", {permission: "denied"});
  await waitPushState(wait, "denied");
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 0, "A denied permission is explained without repeated browser prompts");
  assert.equal(pushWrites(denied).length, 0);
  assert.equal(await evaluate('Boolean(document.querySelector("#notification-settings [data-action=notification-push]:not(:disabled)"))'), false);
  const refusal = await openPushFixture(context, "permission-refusal");
  await waitPushState(wait, "default");
  await evaluate('window.__pushFixture.permissionResult="denied";void 0');
  await click('#notification-settings [data-action="notification-push"]');
  await waitPushState(wait, "denied");
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 1, "The user's explicit refusal ends this permission attempt");
  assert.equal(await evaluate("window.__pushFixture.subscribeCalls"), 0);
  assert.equal(pushWrites(refusal).length, 0);
  const failed = await openPushFixture(context, "server-error", {permission: "granted", existing: "current", configure: fixture => { fixture.failPush = true; }});
  await waitPushState(wait, "error");
  assert.equal(failed.notificationChannels.length, 0);
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 0);
  failed.failPush = false;
  await click('#notification-settings [data-action="push-retry"]');
  await waitPushState(wait, "active");
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 0);
  await openPushFixture(context, "device-conflict", {permission: "granted", existing: "current", configure: fixture => { fixture.pushConflict = true; }});
  await waitPushState(wait, "error");
  assert.equal(await evaluate('document.querySelector("#app-shell").hidden'), false, "A device binding conflict is not an invalid authentication session");
  assert.equal(await evaluate("window.__pushFixture.permissionCalls"), 0);
}
async function exerciseLatePushPermission(context) {
  const {wait, click, evaluate} = context;
  const fixture = await openPushFixture(context, "late-permission");
  await waitPushState(wait, "default");
  await evaluate("window.__pushFixture.holdPermission=true;void 0");
  await click('#notification-settings [data-action="notification-push"]');
  await wait('typeof window.__pushFixture.releasePermission==="function"', "The user's permission choice is still pending");
  await click("#profile-button");
  await click('#profile-menu [data-action="logout"]');
  await wait('document.querySelector("#public-site").hidden===false', "Logout clears the pending action's account context");
  await evaluate('window.__pushFixture.releasePermission();void 0');
  await wait('window.__pushFixture.permission==="granted"', "The old browser permission result arrives after logout");
  assert.equal(pushWrites(fixture).length, 0, "A late permission result cannot attach a device after its owner session ended");
  assert.equal(await evaluate("window.__pushFixture.subscribeCalls"), 0);
}
async function sendNotificationToPage(evaluate, data) {
  return evaluate(`(async () => {const registration=await navigator.serviceWorker.ready;const channel=new MessageChannel();const reply=new Promise(resolve=>{channel.port1.onmessage=event=>{channel.port1.close();resolve(event.data);};});navigator.serviceWorker.dispatchEvent(new MessageEvent("message",{origin:location.origin,source:registration.active,data:${JSON.stringify({type: "OPEN_NOTIFICATION", ...data})},ports:[channel.port2]}));return reply;})()`);
}
async function exercisePushNotificationNavigation(context) {
  const {wait, click, evaluate, fieldValue, screenshot} = context;
  const fixture = await openPushFixture(context, "notification-navigation", {permission: "granted", existing: "current"});
  await waitPushState(wait, "active");
  const bindingId = fixture.notificationChannels[0].binding_id;
  const url = "/#account/events/detail?event=" + fixture.events[0].id;
  await click('#sidebar-nav [data-route="goals"]');
  await wait('document.querySelector("#view-goals [data-action=goal-create]")', "The notification destination test starts from a real editable page");
  await click('#view-goals [data-action="goal-create"]');
  await fieldValue("#goal-form", "title", "Unsaved notification draft");
  await evaluate('window.__notificationDraftForm=document.querySelector("#goal-form");window.__notificationDraftForm.elements.title.focus();void 0');
  const reply = await sendNotificationToPage(evaluate, {url, binding_id: bindingId});
  assert.equal(reply.handled, true, "The app acknowledges a deliberate refusal so the worker cannot navigate over it");
  assert.equal(reply.navigated, false);
  assert.equal(await evaluate("location.hash"), "#account/goals/create");
  assert.equal(await evaluate('document.querySelector("#goal-form")===window.__notificationDraftForm'), true);
  assert.equal(await evaluate('document.querySelector("#goal-form").elements.title.value'), "Unsaved notification draft");
  assert.equal(await evaluate('document.activeElement===document.querySelector("#goal-form").elements.title'), true);
  await screenshot("push-preserved-draft-390.png");
  await fieldValue("#goal-form", "title", "");
  await click('#goal-form [data-close-dialog]');
  await wait('!document.querySelector("#workspace-dialog").open', "Only the user's own action leaves the draft page");
  const stale = await sendNotificationToPage(evaluate, {url, binding_id: randomUUID()});
  assert.equal(stale.handled, true);
  await wait('location.hash==="#account/events"', "An obsolete device binding opens only the current account's generic event page");
  assert.equal(await evaluate('document.querySelector("#workspace-dialog").open'), false, "A stale binding cannot open its personal event detail");
  await evaluate("delete window.__notificationDraftForm;void 0");
}
async function exerciseStartupRecovery({send, configureViewport, base, wait, click, evaluate, checkLayout, screenshot}) {
  await configureViewport(390);
  const destination = "#account/settings/appearance";
  const publicUrls = ["/offline.html", "/assets/config.js", "/assets/tokens.css", "/assets/i18n.js", "/assets/app.css", "/assets/app.js", "/assets/workspace.js", "/assets/brand/omnicio-logo.png"].map(path => path + "?build=" + encodeURIComponent(build));
  const waitPublicCache = label => until(() => evaluate(`(async () => {
    const name = "omnicio-public-" + ${JSON.stringify(build)};
    if (!(await caches.keys()).includes(name)) return false;
    const cache = await caches.open(name);
    const responses = await Promise.all(${JSON.stringify(publicUrls)}.map(url => cache.match(url)));
    return responses.every(response => response?.ok && response.headers.get("X-Omnicio-Build") === ${JSON.stringify(build)});
  })()`), label);

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
  await waitPublicCache("Initial installation has a complete verified public shell");
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
  await waitPublicCache("Manual startup recovery repopulates the offline shell without a worker reinstall");
  for (const item of [
    {name: "missing-config", asset: "config.js", missing: true},
    {name: "stale-config", asset: "config.js", missing: false},
    {name: "missing-tokens", asset: "tokens.css", missing: true},
    {name: "stale-tokens", asset: "tokens.css", missing: false}
  ]) {
    const key = "signed-startup-" + item.name;
    const fixture = makeFixture("signed");
    const path = "/assets/" + item.asset;
    fixture.missingBundle = item.missing ? path : "";
    // The worker may finish a prior startup check concurrently; the missing
    // response must also fail its independent request, not only page referrers.
    unavailablePublicAsset = fixture.missingBundle;
    fixtures.set(key, fixture);
    const resource = path + "?build=" + encodeURIComponent(build);
    const source = publicAssets[path.slice(1)].replaceAll(build, build + "-stale");
    await evaluate(`(async () => {
      const cache = await caches.open("omnicio-public-" + ${JSON.stringify(build)});
      if (${item.missing}) await cache.delete(${JSON.stringify(resource)});
      else await cache.put(${JSON.stringify(resource)}, new Response(${JSON.stringify(source)}, {headers: {"Content-Type": ${JSON.stringify(item.asset.endsWith(".css") ? "text/css" : "text/javascript")}, "X-Omnicio-Build": ${JSON.stringify(build)}}}));
    })()`);
    await send("Page.navigate", {url: `${base}?case=${key}${destination}`});
    await wait('document.querySelector("#startup-state")?.dataset.status === "unavailable" && document.querySelector("[data-startup-reload]")?.getClientRects().length', "A " + item.name + " asset fails before private startup");
    assert.equal(fixture.requests.length, 0, item.name + " cannot start an API read or mutation");
    assert.equal(await evaluate("location.hash"), destination);
    if (item.asset === "config.js") assert.equal(await evaluate("window.OMNICIO_CONFIG?.compiledBuild || null"), item.missing ? null : build + "-stale");
    else assert.equal(await evaluate('getComputedStyle(document.documentElement).getPropertyValue("--omnicio-build").trim()'), item.missing ? "" : JSON.stringify(build + "-stale"));
    fixture.missingBundle = "";
    unavailablePublicAsset = "";
    const timeOrigin = await evaluate("performance.timeOrigin");
    await click("[data-startup-reload]");
    await wait(`performance.timeOrigin !== ${timeOrigin} && document.querySelector('#preferences-form [name="locale"]')?.getClientRects().length`, "Explicit retry restores " + item.name + " without losing the destination");
    assert.equal(await evaluate("location.hash"), destination);
    assert.ok(fixture.requests.length > 0 && fixture.requests.every(request => request.clientBuild === build));
    await waitPublicCache("Recovered " + item.name + " has all eight verified offline assets");
  }
  const workerUrl = await evaluate('(async () => (await navigator.serviceWorker.ready).active.scriptURL)()');
  const offlineKey = "signed-startup-offline";
  const offline = makeFixture("signed");
  fixtures.set(offlineKey, offline);
  publicNetworkUnavailable = true;
  try {
    await send("Page.navigate", {url: `${base}?case=${offlineKey}${destination}`});
    await wait('document.body.classList.contains("offline-page") && document.querySelector("[data-offline-retry]")?.getClientRects().length && Boolean(window.OmniUI)', "A network failure after recovery opens the real cached offline shell");
    assert.equal(await evaluate("location.hash"), destination);
    assert.equal(await evaluate("window.OMNICIO_CONFIG.compiledBuild"), build);
    assert.equal(await evaluate('JSON.parse(getComputedStyle(document.documentElement).getPropertyValue("--omnicio-build"))'), build);
    assert.equal(await evaluate('Boolean(document.querySelector("#app-shell"))'), false, "The public offline shell contains no retained account document");
    assert.equal(offline.requests.length, 0, "Offline fallback never asks the API to reconstruct private account data");
    assert.equal(await evaluate('(async () => (await navigator.serviceWorker.ready).active.scriptURL)()'), workerUrl);
  } finally { publicNetworkUnavailable = false; }
  const offlineOrigin = await evaluate("performance.timeOrigin");
  await click("[data-offline-retry]");
  await wait(`performance.timeOrigin !== ${offlineOrigin} && document.querySelector('#preferences-form [name="locale"]')?.getClientRects().length`, "The visible offline retry returns to the same authenticated destination once the connection works");
  assert.equal(await evaluate("location.hash"), destination);
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
  console.log("PASS startup recovery: missing/stale configuration and palette, cache repair, real offline fallback and retry, old HTML, storage failure and preserved deep links");
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
function expectedQuoteText(value, unit, currency, locale) {
  const options = {maximumFractionDigits: 9};
  if (unit === "currency") Object.assign(options, {style: "currency", currency});
  const amount = new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", options).format(value);
  const suffixes = locale === "ru" ? {percent_nominal: "% номинала", points: "пунктов"} : {percent_nominal: "% of face value", points: "points"};
  return unit === "currency" ? amount : amount + " " + suffixes[unit];
}
async function exerciseQuotePrecision({send, configureViewport, round, base, wait, click, evaluate, checkLayout, screenshot}) {
  const locale = round === 1 ? "ru" : "en";
  await configureViewport(round === 1 ? 320 : 390);
  assert.deepEqual(serverContracts.market_precision_cases.map(item => item.key), ["tiny", "nano", "percent", "points", "large", "int64"], "Precision cases are generated by the real market REST and SSE endpoints");
  for (const precision of serverContracts.market_precision_cases) {
    await exerciseQuotePrecisionCase({send, round, base, wait, click, evaluate, checkLayout, screenshot, locale, precision});
  }
  console.log(`PASS market precision round ${round}: actual REST and SSE, batch table, nano and exact extrema, chart keyboard and narrow layout in ${locale}`);
}
async function exerciseQuotePrecisionCase({send, round, base, wait, click, evaluate, checkLayout, screenshot, locale, precision}) {
  const key = `signed-precision-${round}-${precision.key}`;
  const fixture = makeFixture("signed");
  fixture.precisionCase = precision;
  fixture.holdMarketStream = true;
  fixture.holdAssetParts = new Set(["facts"]);
  fixture.heldAssetParts = new Map();
  fixture.prefs.document.locale = locale;
  fixtures.set(key, fixture);
  const {price_unit: unit, price_currency: currency} = precision.expected;
  const text = value => expectedQuoteText(value, unit, currency, locale);
  const expected = text(precision.expected.last_price);
  await send("Page.navigate", {url: `${base}?case=${key}#account/market/positions`});
  await wait(`document.documentElement.lang === ${JSON.stringify(locale)} && document.querySelector('#view-market [data-table-quote="synthetic-a"] strong')?.textContent === ${JSON.stringify(expected)}`, "Batch quote preserves exact source digits: " + precision.key);
  await checkLayout(`precision-table-${precision.key}-${locale}`, {minTables: 1});
  await click('#view-market [data-asset="synthetic-a"]');
  await wait(`document.querySelector('#view-asset [data-market-quote] .main-value')?.textContent === ${JSON.stringify(text(precision.market.last_price))} && document.querySelector('#view-asset .chart-svg')`, "Actual REST quote and candles retain their precision: " + precision.key);
  await until(() => fixture.marketStreams?.size === 1 && fixture.heldAssetParts.has("facts"), "The initial precision stream is open while auxiliary facts remain held");
  const initialStream = [...fixture.marketStreams][0];
  fixture.holdAssetParts.delete("facts");
  fixture.heldAssetParts.get("facts")();
  fixture.heldAssetParts.delete("facts");
  await wait('document.querySelector("#view-asset h1")?.textContent === "Synthetic precision contract" && !document.querySelector("#view-asset .loading-panel")', "The precision asset has completed its auxiliary reads");
  await until(() => fixture.marketStreams.size === 1 && !fixture.marketStreams.has(initialStream), "The final active stream has replaced the closed initial response");
  assert.equal(await evaluate('document.querySelector("#view-asset .chart-readout strong").textContent'), text(precision.expected.last_close), "Initial chart readout shows the exact last source observation");
  if (unit !== "currency" && precision.market.cash_price !== null) assert.ok((await evaluate('document.querySelector("#view-asset [data-market-quote] .fine-print").textContent')).includes(expectedQuoteText(precision.market.cash_price, "currency", precision.market.cash_price_currency, locale)), "The REST cash price preserves its displayed source digits");
  await evaluate('document.querySelector("#view-asset .chart-svg").focus()');
  const focused = await evaluate('document.activeElement.dataset.chart');
  fixture.holdMarketStream = false;
  for (const response of fixture.marketStreams) response.write(precision.market_event);
  await wait(`document.querySelector('#view-asset [data-market-quote] .main-value')?.textContent === ${JSON.stringify(expected)}`, "Actual SSE replaces the previous REST price without rounding: " + precision.key);
  assert.equal(await evaluate('document.activeElement.dataset.chart'), focused, "Exact quote updates preserve the chart being inspected");
  assert.equal((await evaluate('document.querySelector("#view-asset [data-market-quote] .value-change").textContent')).split(" · ")[0], text(precision.expected.absolute_change), "The displayed absolute change matches the independent Decimal source difference");
  if (unit !== "currency" && precision.expected.cash_price !== null) assert.ok((await evaluate('document.querySelector("#view-asset [data-market-quote] .fine-print").textContent')).includes(expectedQuoteText(precision.expected.cash_price, "currency", precision.market.cash_price_currency, locale)), "The SSE cash price preserves its displayed source digits");
  for (const [keyName, keyCode, price] of [["Home", 36, precision.expected.first_close], ["End", 35, precision.expected.last_close]]) {
    await send("Input.dispatchKeyEvent", {type: "keyDown", key: keyName, code: keyName, windowsVirtualKeyCode: keyCode});
    assert.equal(await evaluate('document.querySelector("#view-asset .chart-readout strong").textContent'), text(price), "Keyboard selection keeps each exact source observation");
    assert.ok((await evaluate('document.querySelector("#view-asset .chart-svg").getAttribute("aria-label")')).includes(text(price)), "Accessible chart values match the selected source observation");
  }
  await checkLayout(`precision-asset-${precision.key}-${locale}`, {minCharts: 1});
  const bounds = await evaluate(`(() => {
    const card=document.querySelector("#view-asset .asset-chart-card").getBoundingClientRect();
    return [...document.querySelectorAll("#view-asset [data-market-quote] .main-value,#view-asset .chart-readout,#view-asset .chart-readout strong")].map(element=>{const rect=element.getBoundingClientRect();return {text:element.textContent,inside:rect.left>=card.left-1 && rect.right<=card.right+1,unclipped:element.scrollWidth<=element.clientWidth+1};});
  })()`);
  assert.ok(bounds.every(item => item.inside && item.unclipped), "The full source price and chart readout remain visible inside the narrow card: " + JSON.stringify(bounds));
  if (["large", "int64"].includes(precision.key)) await screenshot(`precision-${precision.key}-${round}-${locale}.png`);
  await click('#view-asset [data-asset-tab="metrics"]');
  const labels = locale === "ru" ? ["Последняя цена", "Максимум периода", "Минимум периода"] : ["Last price", "Period high", "Period low"];
  await wait(`document.querySelector('#view-asset .asset-tab-content')?.textContent.includes(${JSON.stringify(labels[0])}) && !document.querySelector('#view-asset .asset-tab-content .loading-panel')`, "The metrics screen is ready for exact source values");
  const metrics = await evaluate('Object.fromEntries([...document.querySelectorAll("#view-asset .asset-tab-content .info-row")].map(row=>[row.querySelector("dt")?.textContent,row.querySelector("dd")?.textContent]))');
  for (const [index, value] of [precision.expected.last_price, precision.expected.high, precision.expected.low].entries()) assert.equal(metrics[labels[index]], text(value), "Asset metrics preserve the source price for " + labels[index]);
  assert.equal(fixture.requests.filter(item => !["GET", "HEAD"].includes(item.method)).length, 0, "Reading precise market prices cannot write personal data");
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
async function exerciseCompactScreenMenu({send, configureViewport, round, click, wait, evaluate, checkLayout, screenshot, fixture}) {
  await click('#view-strategies .screen-menu [data-screen="editor"]');
  await wait('location.hash.endsWith("/strategies/editor") && document.querySelector("#strategy-form")?.getClientRects().length', "Compact navigation opens the existing strategy editor route");
  const before = await evaluate('({hash:location.hash,history:history.length,value:document.querySelector("#allocation-shares").value})');
  const saved = clone(fixture.selection);
  const writes = strategyWrites(fixture);
  assert.equal(await evaluate('document.querySelector("#view-strategies .screen-menu-picker").open'), false);
  assert.ok(await evaluate('document.querySelector("#view-strategies .screen-menu-toggle").textContent.includes("Моя настройка")'));
  await evaluate('document.querySelector("#view-strategies .screen-menu-toggle").focus()');
  assert.equal(await evaluate('document.activeElement.matches("#view-strategies .screen-menu-toggle")'), true);
  for (const [key, code, virtualKey, expected] of [["Enter", "Enter", 13, true], [" ", "Space", 32, false]]) {
    const nativeKey = {key, code, windowsVirtualKeyCode: virtualKey};
    // Chromium creates the native Enter keypress only when keyDown carries text.
    const text = key === "Enter" ? "\r" : key;
    await send("Input.dispatchKeyEvent", {...nativeKey, type: "keyDown", text, unmodifiedText: text});
    await send("Input.dispatchKeyEvent", {...nativeKey, type: "keyUp"});
    await wait(`document.querySelector('#view-strategies .screen-menu-picker').open===${expected}`, "Native keyboard activation toggles the section summary: " + code);
  }
  assert.deepEqual(await evaluate('({hash:location.hash,history:history.length,value:document.querySelector("#allocation-shares").value})'), before, "Opening a menu cannot navigate or change a draft");
  for (const width of [1366, 960, 961, 390, 320]) {
    await configureViewport(width);
    await wait(`innerWidth===${width} && document.querySelector('#view-strategies .screen-menu-picker').dataset.compact===${JSON.stringify(String(width <= 960))} && document.querySelector('#view-strategies .screen-menu-picker').open===${width > 960}`, "The menu matches its breakpoint without a page reload");
    const focus = await evaluate(`(() => {const picker=document.querySelector('#view-strategies .screen-menu-picker');const active=document.activeElement;return {expected:active===picker.querySelector(${JSON.stringify(width > 960 ? '.screen-menu [aria-current="page"]' : '.screen-menu-toggle')}),visible:active.getClientRects().length>0,tag:active.tagName,id:active.id,classes:active.className,compact:picker.dataset.compact,open:picker.open};})()`);
    assert.equal(focus.expected && focus.visible, true, `Responsive changes keep keyboard focus on a visible navigation control at ${width}px: ${JSON.stringify(focus)}`);
    assert.deepEqual(await evaluate('({hash:location.hash,history:history.length,value:document.querySelector("#allocation-shares").value})'), before);
    await evaluate('window.scrollTo({top:0,behavior:"instant"})');
    if (width <= 390) {
      const placement = await evaluate('(() => {const field=document.querySelector("#allocation-shares").getBoundingClientRect();const nav=document.querySelector("#mobile-nav").getBoundingClientRect();return {top:field.top,bottom:field.bottom,navTop:nav.top};})()');
      assert.ok(placement.top >= 0 && placement.bottom <= placement.navTop, "The first allocation control is visible above mobile navigation with the menu closed");
    }
    await checkLayout(`compact-strategy-${round}/${width}`);
    await screenshot(`strategy-compact-${round}-${width}.png`);
  }
  for (const linkFocused of [false, true]) {
    await wait('document.querySelector("#research-form [type=submit]")?.disabled===false', "Research prerequisites are ready before refresh");
    fixture.holdResearchReads = true;
    await click('#view-strategies [data-action="refresh"]');
    await until(() => fixture.heldResearchReads.length > 0, "A refresh has a delayed research response");
    assert.equal(await evaluate('document.querySelector("#research-form [type=submit]").disabled'), true, "The held response keeps research prerequisites pending");
    const selector = linkFocused ? '.screen-menu [data-screen="research"]' : '.screen-menu-toggle';
    await evaluate(`(() => {const picker=document.querySelector('#view-strategies .screen-menu-picker');picker.open=${linkFocused};picker.querySelector(${JSON.stringify(selector)}).focus();window.__menuBeforeRead=picker;})()`);
    fixture.holdResearchReads = false;
    fixture.heldResearchReads.splice(0).forEach(release => release());
    await wait('document.querySelector("#view-strategies .screen-menu-picker")!==window.__menuBeforeRead && document.querySelector("#research-form [type=submit]")?.disabled===false', "Late research data is acknowledged on the existing screen");
    assert.equal(await evaluate(`document.activeElement===document.querySelector('#view-strategies .screen-menu-picker').querySelector(${JSON.stringify(selector)}) && document.activeElement.getClientRects().length>0`), true, "A late response preserves the same visible menu control");
    assert.equal(await evaluate('document.querySelector("#view-strategies .screen-menu-picker").open'), linkFocused, "A late response preserves the compact menu disclosure");
    assert.deepEqual(await evaluate('({hash:location.hash,history:history.length,value:document.querySelector("#allocation-shares").value})'), before);
  }
  await evaluate('document.querySelector("#allocation-shares").focus()');
  for (const width of [1366, 320]) {
    await configureViewport(width);
    await wait(`document.querySelector('#view-strategies .screen-menu-picker').dataset.compact===${JSON.stringify(String(width <= 960))}`, "Resize with focus outside the menu");
    assert.equal(await evaluate('document.activeElement.id'), "allocation-shares", "Responsive navigation cannot steal focus from the strategy editor");
  }
  assert.deepEqual(fixture.selection, saved, "Changing screen density does not replace the strategy");
  assert.equal(strategyWrites(fixture), writes, "Responsive navigation and late reads cannot save the strategy");
  console.log(`PASS compact section menu round ${round}: native keyboard, breakpoint focus, late-response focus/disclosure, editor focus, stable route/draft and visible mobile fields`);
}
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
    if (view === "strategies" && width === 320) await exerciseCompactScreenMenu({send, configureViewport, round, click, wait, evaluate, checkLayout, screenshot, fixture});
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
  if (width === 390) await exerciseStrategyNumericFields({fixture, click, fieldValue, wait, evaluate});
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
  const browserStorage = await evaluate('({local:Object.keys(localStorage),session:Object.keys(sessionStorage),lastRoute:localStorage.getItem("omnicio-last-route"),installDismissed:localStorage.getItem("omnicio-install-dismissed")})');
  assert.deepEqual(browserStorage.session, [], "Private session data never enters sessionStorage");
  const unexpectedStorageKeys = browserStorage.local.filter(key => !["omnicio-theme", "omnicio-last-route", "omnicio-install-dismissed"].includes(key));
  assert.deepEqual(unexpectedStorageKeys, [], "Only display preferences, the installation dismissal and a sanitized page route may enter localStorage");
  if (browserStorage.local.includes("omnicio-install-dismissed")) assert.equal(browserStorage.installDismissed, "true", "The installation preference stores only the dismissal flag, without identifiers or content");
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
async function exerciseStrategyNumericFields({fixture, click, fieldValue, wait, evaluate}) {
  const saved = clone(fixture.selection.document);
  const writes = strategyWrites(fixture);
  const keys = ["yield_margin_pp", "fund_wrapper_cap_percent"];
  for (const key of keys) {
    await fieldValue("#strategy-form", `strategy.rules.${key}`, "");
    assert.equal(await evaluate(`document.querySelector('[name="strategy.rules.${key}"]').validity.valueMissing`), true, "Required rules are validated by the real rendered input");
  }
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="error"', "Invalid rule input blocks autosave visibly");
  await click('#sidebar-nav [data-route="portfolio"]');
  await wait('!document.querySelector("#view-portfolio").hidden', "Leaving the strategy editor finishes before returning");
  await click('#sidebar-nav [data-route="strategies"]');
  await wait('!document.querySelector("#view-strategies").hidden && document.querySelector("#strategy-form")', "The editor is rebuilt after navigation");
  await delay(700);
  assert.equal(strategyWrites(fixture), writes, "Removing and rebuilding the form cannot save invalid rules as null");
  assert.deepEqual(fixture.selection.document, saved, "Invalid input preserves all previously saved parameters");
  for (const [index, key] of keys.entries()) {
    assert.equal(await evaluate(`document.querySelector('[name="strategy.rules.${key}"]').getAttribute('aria-invalid')`), "true", "Validation survives the rebuilt editor");
    await fieldValue("#strategy-form", `strategy.rules.${key}`, saved.rules[key]);
    if (index === 0) assert.equal(await evaluate('document.querySelector("[data-save-status=strategy]").dataset.state'), "error", "Repairing one rule cannot hide the other invalid rule");
  }
  await wait('document.querySelector("[data-save-status=strategy]").dataset.state==="saved"', "Restoring the original valid rules clears the local error");
  await delay(700);
  assert.equal(strategyWrites(fixture), writes, "Repairing back to saved values requires no duplicate write");
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
