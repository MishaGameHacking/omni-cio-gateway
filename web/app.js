"use strict";

(() => {
  "use strict";

  const I = window.OMNICIO_I18N;
  const T = (key, values) => I.t(key, values);
  const H = (key, values) => I.html(key, values);
  I.apply(document);

  const U = window.OmniUI;
  const {
    escape: esc,
    icon,
    money,
    marketPrice,
    percent,
    number,
    date,
    format,
    button,
    empty,
    heading,
    cardHeader,
    chart,
    periods,
    field,
    select,
    help,
    infoRows,
    freshness
  } = U;
  const $ = (selector, parent = document) => parent.querySelector(selector);
  const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
  const clone = value => structuredClone(value);
  const state = {
    user: null,
    config: null,
    generation: 0,
    locked: false,
    tour: false,
    mode: "auto",
    session: {status: "checking", error: null, sequence: 0, promise: null},
    navigationSequence: 0,
    screenDrafts: {},
    screenBaselines: {},
    viewState: {},
    quotes: {},
    outdated: false,
    view: "home",
    route: {},
    data: {},
    errors: {},
    loading: new Set(),
    requests: new Set(),
    resourceVersions: new Map(),
    resourceRequests: new Map(),
    deletedGoalIds: new Set(),
    homePeriod: "1m",
    portfolioPeriod: "1y",
    analyticsPeriod: "1y",
    assetPeriod: "1m",
    assetTab: "chart",
    strategyPane: "catalog",
    asset: null,
    assetFilter: "all",
    sort: "name",
    sortDirection: 1,
    eventFilter: "all",
    searchQuery: "",
    searchResults: [],
    searchPages: {events: null, news: null},
    searchFailures: {},
    eventDetail: null,
    eventHistoryExtended: false,
    deliveryBusy: false,
    deliveryDrafts: {},
    searchSequence: 0,
    researchRequest: null,
    researchDraft: {},
    researchArchiveDialog: null,
    cbrCurrency: "USD",
    cbrPeriod: "1m",
    prefs: {
      server: null,
      draft: null,
      revision: 0,
      dirty: false,
      busy: false,
      error: null,
      timer: null
    },
    strategy: {
      server: null,
      draft: null,
      revision: 0,
      dirty: false,
      busy: false,
      error: null,
      intent: "edit",
      timer: null,
      assessment: null,
      research: null
    },
    chat: [],
    assistantBusy: false,
    billingBusy: false,
    executionBusy: false,
    executionPlan: null,
    assistantConversation: null,
    assistantDraft: {message: "", context: "general", include_news: false, research_run_id: ""},
    drawerReturn: null,
    verifying: false,
    authMode: "login",
    pendingTheme: null
  };
  state.formDrafts = {};
  state.formBaselines = {};
  state.refresh = {
    sequence: 0,
    timer: null,
    busy: false
  };
  state.recovery = {
    id: null,
    sequence: 0,
    busy: false,
    record: null,
    uncertain: false
  };
  const views = new Set([...U.navigation.map(([key]) => key), "asset", "search"]);
  const assetTypes = () => ([["all", T("Все")], ["share", T("Акции")], ["bond", T("Облигации")], ["etf", T("Фонды")], ["currency", T("Валюта")], ["other", T("Другое")]]);
  const strategyIcons = {
    balanced: ["portfolio", "#2b86ff"],
    conservative: ["shield", "#8645d8"],
    aggressive: ["analytics", "#f24964"],
    income: ["wallet", "#ef9b32"],
    growth: ["market", "#2f82ff"],
    buffett: ["shield", "#27c963"],
    bogle: ["building", "#af9a53"],
    dalio: ["portfolio", "#a04eed"],
    ladder: ["building", "#23ace9"],
    dividends: ["wallet", "#f26333"]
  };
  const strategyTaglines = () => ({
    balanced: T("Сочетание риска и доходности"),
    conservative: T("Сохранение капитала"),
    aggressive: T("Потенциал роста"),
    income: T("Регулярные выплаты"),
    growth: T("Долгосрочный рост"),
    buffett: T("Качество и устойчивость"),
    bogle: T("Широкий рынок и издержки"),
    dalio: T("Распределение рисков"),
    ladder: T("Постепенное погашение"),
    dividends: T("Источники выплат")
  });
  let themeChoice = "dark";
  try {
    const saved = localStorage.getItem("omnicio-theme");
    if (["dark", "light", "system"].includes(saved)) themeChoice = saved;
  } catch {/* Theme storage is optional; no private data is stored. */}
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
  const stableDocument = value => Array.isArray(value) ? value.map(stableDocument) : renderStableDocumentValue(value);
  const same = (left, right) => JSON.stringify(stableDocument(left)) === JSON.stringify(stableDocument(right));
  const contextError = () => Object.assign(new Error("profile_context_changed"), {
    status: 409,
    code: "profile_context_changed"
  });
  const safeSegment = value => {
    const text = String(value ?? "");
    if (!text || text.length > 128 || text !== text.trim() || /[\\/?#\u0000-\u001f\u007f]/u.test(text)) throw new Error("invalid_instrument");
    return encodeURIComponent(text);
  };
  const apiPath = path => {
    if (typeof path !== "string" || !path.startsWith("/api/")) throw new TypeError("Only same-origin API requests are supported");
    const url = new URL(path, location.origin);
    if (url.origin !== location.origin || !url.pathname.startsWith("/api/") || url.hash || url.username || url.password) throw new TypeError("Invalid API origin");
    return url;
  };
  const privateRequest = path => !path.split("?")[0].startsWith("/api/public/news/") && !["/api/auth/config", "/api/auth/vkid/start", "/api/auth/tid/start", "/api/strategy/catalog", "/api/public/market-reference", "/api/public/news", "/api/public/support"].includes(path.split("?")[0]);
  const ensureResponseContext = ({
    generation,
    profile,
    bootstrap
  }) => {
    if (generation !== state.generation) throw contextError();
    if (profile && state.user?.public_id !== profile) throw contextError();
    if (state.locked && !bootstrap) throw contextError();
  };
  const apiFailure = (response, payload, profile) => {
    const code = typeof payload?.detail === "string" ? payload.detail : "request_failed";
    if (code === "client_build_changed") flagApplicationUpdate();
    const error = Object.assign(new Error(code), {
      status: response.status,
      code
    });
    const requestId = response.headers.get("X-Request-ID") || "";
    if (/^[a-f0-9]{32}$/.test(requestId)) error.requestId = requestId;
    const contextChanged = ["profile_context_changed", "profile_context_required", "settings_owner_conflict", "strategy_account_context_changed"].includes(code);
    if (profile && (response.status === 401 || contextChanged)) {
      lockSession(response.status === 401 ? T("Сессия завершилась. Войдите снова, чтобы продолжить.") : T("Аккаунт в браузере изменился. Старые данные очищены. Проверьте текущую сессию."));
      return contextError();
    }
    return error;
  };
  const readApiResponse = async (response, context) => {
    const payload = response.status === 204 ? null : await response.json().catch(() => null);
    ensureResponseContext(context);
    if (!response.ok) throw apiFailure(response, payload, context.profile);
    if (payload?.public_id && context.profile && payload.public_id !== context.profile) {
      lockSession(T("Сервер вернул другой аккаунт. Старые данные очищены; требуется проверка сессии."));
      throw contextError();
    }
    if (response.status !== 204 && (!payload || typeof payload !== "object")) throw Object.assign(new Error("invalid_server_response"), {
      status: 502
    });
    return payload;
  };
  const apiTransportError = (error, {
    timedOut,
    method,
    generation
  }) => {
    if (timedOut) return Object.assign(new Error("request_timeout"), {
      status: 0,
      uncertain: method !== "GET"
    });
    if (error?.name === "AbortError" && method !== "GET" && generation === state.generation) return Object.assign(new Error("request_interrupted"), {
      status: 0,
      uncertain: true
    });
    return error;
  };
  const ensureApiRequest = (path, method, bootstrap) => {
    if (state.locked && !bootstrap) throw contextError();
    const completionRequest = path.startsWith("/api/auth/") || /\/(cancel|revoke|reconcile)$/.test(path) || method === "DELETE";
    if (state.outdated && !["GET", "HEAD"].includes(method) && !completionRequest) throw Object.assign(new Error("frontend_update_required"), {status: 409, definite: true});
    if (state.tour && privateRequest(path) && path !== "/api/me") throw Object.assign(new Error("tour_requires_login"), {
      status: 401
    });
    if (!navigator.onLine && !["GET", "HEAD"].includes(method)) throw Object.assign(new Error("offline_write_not_sent"), {
      status: 0,
      definite: true
    });
  };
  const api = async (path, {
    method = "GET",
    body,
    timeout = 30000,
    bootstrap = false,
    onStream = null
  } = {}) => {
    const url = apiPath(path);
    ensureApiRequest(path, method, bootstrap);
    const context = {
      generation: state.generation,
      profile: state.user?.public_id,
      bootstrap
    };
    const controller = new AbortController();
    controller.omnicioMutation = !["GET", "HEAD"].includes(method);
    state.requests.add(controller);
    let timedOut = false;
    const timer = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeout);
    const headers = new Headers({
      Accept: "application/json",
      "X-Omnicio-Client-Build": window.OMNICIO_RELEASE?.build || "__OMNICIO_BUILD__"
    });
    if (body !== undefined) headers.set("Content-Type", "application/json");
    if (context.profile && !bootstrap) headers.set("X-Omnicio-Profile", context.profile);
    try {
      const response = await fetch(url, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal
      });
      const serverBuild = response.headers.get("X-Omnicio-Build");
      if (serverBuild && serverBuild !== (window.OMNICIO_RELEASE?.build || "__OMNICIO_BUILD__")) flagApplicationUpdate();
      if (onStream && response.ok) { ensureResponseContext(context); return await onStream(response, () => ensureResponseContext(context)); }
      return await readApiResponse(response, context);
    } catch (error) {
      throw apiTransportError(error, {
        timedOut,
        method,
        generation: context.generation
      });
    } finally {
      clearTimeout(timer);
      state.requests.delete(controller);
    }
  };
  const recoveryErrorReason = code => {
    const suffix = String(code || "").replace(/^(live|sandbox)_/, "");
    const reasons = {
      cancel_ambiguous: T("Ответ брокера на отмену не получен. Обновите состояние заявки; отмена пока не подтверждена."),
      order_not_found_yet: T("Брокер пока не вернул заявку по её сохранённому номеру. Повторите сверку позднее."),
      cancel_order_not_found: T("Брокер не подтвердил заявку при отмене. Обновите её состояние; успешная отмена не подтверждена."),
      reconcile_unavailable: T("Состояние у брокера временно недоступно. Дождитесь восстановления связи и повторите сверку."),
      account_mismatch: T("Подключён другой счёт. Для сверки требуется счёт, к которому относится запись.")
    };
    if (["request_id_mismatch", "instrument_mismatch", "lot_count_mismatch", "direction_mismatch", "order_type_mismatch"].includes(suffix)) return T("Ответ брокера не совпадает с сохранённой заявкой. Автоматическое подтверждение остановлено; проверьте заявку у брокера.");
    return reasons[suffix] || null;
  };
  const humanError = error => {
    const reasons = {
      offline_write_not_sent: T("Нет сети. Изменение не отправлено. Подключитесь к интернету и повторите."),
      frontend_update_required: T("pwa.update_before_write"),
      client_build_changed: T("pwa.update_before_write"),
      request_timeout: T("Сервер не успел ответить. Проверьте сохранённое состояние перед повтором."),
      request_interrupted: T("Отправка прервана. Проверьте сохранённое состояние перед повтором: сервер мог уже принять изменение."),
      invalid_server_response: T("Получен неполный ответ сервера. Повторите загрузку."),
      tour_requires_login: T("Для этого действия войдите в личный аккаунт."),
      profile_context_changed: T("Сессия изменилась. Подтвердите текущий аккаунт."),
      settings_version_conflict: T("Сохранённая версия изменилась. Загрузите актуальные данные перед следующей правкой."),
      strategy_assessment_busy: T("Расчёт уже выполняется. Подождите и повторите через несколько секунд."),
      research_held_universe_too_large: T("research.held_universe"),
      research_context_changed: T("research.conflict"),
      research_request_parameters_changed: T("research.conflict"),
      research_run_not_found: T("research.deleted"),
      research_archive_deleted: T("research.deleted"),
      research_window_invalid: T("research.window_invalid"),
      research_parameters_invalid: T("research.parameters_invalid"),
      research_snapshot_required: T("research.snapshot_required"),
      research_draft_required: T("research.draft_required"),
      research_cashflow_overlap_requires_complete_history: T("research.cashflow_overlap"),
      strategy_research_unavailable: T("research.source_unavailable"),
      research_replay_version_unsupported: T("research.replay_unsupported"),
      research_evidence_fields_invalid: T("research.evidence_fields"),
      research_evidence_fact_invalid: T("research.evidence_fields"),
      research_evidence_text_invalid: T("research.evidence_fields"),
      research_evidence_boolean_invalid: T("research.evidence_boolean"),
      research_evidence_number_invalid: T("research.evidence_number"),
      research_evidence_rows_invalid: T("research.evidence_rows"),
      research_evidence_source_invalid: T("research.evidence_source"),
      research_evidence_time_invalid: T("research.evidence_time"),
      research_evidence_duplicate_instrument: T("research.evidence_duplicate"),
      research_fund_weights_must_total_100: T("research.evidence_weights"),
      research_cashflow_kind_invalid: T("research.evidence_cashflow_kind"),
      research_cashflow_order_invalid: T("research.evidence_cashflow_order"),
      research_cashflow_duplicate: T("research.missing.cashflow_duplicate"),
      research_coverage_invalid: T("research.evidence_coverage"),
      research_factor_availability_invalid: T("research.evidence_factor_time"),
      research_factor_date_duplicate: T("research.missing.factors"),
      research_split_ratio_invalid: T("research.missing.split_invalid"),
      research_split_duplicate: T("research.missing.split_duplicate"),
      research_bond_nominal_invalid: T("research.evidence_nominal"),
      research_bond_date_duplicate: T("research.missing.bond_value"),
      research_archive_capacity: T("research.full"),
      research_archive_storage_capacity: T("research.full"),
      research_archive_too_large: T("research.too_large"),
      research_request_capacity: T("research.request_capacity"),
      research_request_expired: T("research.expired"),
      research_failed: T("research.failed"),
      research_cursor_not_found: T("research.cursor_missing"),
      research_request_not_found: T("research.not_found"),
      research_evidence_too_large: T("research.evidence_too_large"),
      strategy_account_evidence_unavailable: T("Не удалось получить согласованные данные счёта. Обновите подключение и повторите расчёт."),
      assistant_activation_disabled: T("Внешний ИИ пока выключен. Подключение будет активировано после приёмки системы."),
      assistant_request_running: T("Предыдущий запрос ещё выполняется. Обновите историю разговора."),
      assistant_request_uncertain: T("Результат запроса не подтверждён. Повторная отправка не выполнялась; проверьте историю."),
      assistant_request_cancelled: T("Запрос остановлен после изменения подключения или разговора."),
      assistant_daily_quota_exceeded: T("Дневной лимит запросов исчерпан. Время его обновления указано в разделе ИИ."),
      assistant_endpoint_not_allowed: T("Выберите адрес из разрешённого оператором списка."),
      assistant_context_changed: T("Подключение или выбранные данные изменились во время запроса. Обновите данные перед новым вопросом."),
      billing_not_configured: T("Оплата пока не включена оператором."),
      billing_offer_changed: T("Стоимость или условия изменились. Откройте план заново и проверьте актуальные условия."),
      billing_active_or_recent_payment: T("Уже есть действующая подписка или незавершённый платёж. Проверьте историю оплат."),
      billing_order_outcome_unknown: T("Банк пока не подтвердил итог. Выполните сверку позднее."),
      billing_payment_already_settled: T("Платёж уже завершён. Для возврата свяжитесь с оператором сервиса."),
      identity_reauthentication_required: T("Для отвязки сначала выполните свежий вход через другой привязанный способ."),
      identity_last_provider: T("Нельзя удалить последний доступный способ входа."),
      assistant_not_configured: T("ИИ-провайдер ещё не подключён."),
      assistant_unavailable: T("ИИ-провайдер сейчас не отвечает. Сообщение не получило ответа."),
      notification_push_not_configured: T("Отправка push ещё не включена администратором."),
      notification_email_not_configured: T("Отправка писем ещё не включена администратором."),
      notification_verification_rate_limited: T("Новый код можно запросить через две минуты, не более трёх раз за час."),
      notification_verification_invalid: T("Код неверен, истёк или исчерпаны пять попыток. Проверьте письмо или запросите новый код."),
      notification_endpoint_invalid: T("Сервис уведомлений этого браузера пока не поддерживается. Выберите email или другой браузер."),
      notification_channel_limit: T("Можно подключить до восьми устройств и адресов. Отключите неиспользуемый канал."),
      service_worker_unavailable: T("Браузер не завершил подготовку уведомлений. Обновите страницу и попробуйте ещё раз."),
      push_permission_denied: T("Браузер не разрешил уведомления. Разрешение можно изменить в настройках сайта в браузере."),
      "T-Invest is not connected": T("Подключите свой счёт T-Invest в настройках."),
      "stored T-Invest credential was rejected": T("Срок действия API-токена истёк или доступ отозван. Проверьте подключение."),
      "T-Invest token rejected": T("API-токен не прошёл проверку. Проверьте значение и выбранную среду."),
      "legal acknowledgments are required": T("Подтвердите ознакомление с документами."),
      updated_legal_consent_required: T("Условия сервиса обновились. Войдите повторно и подтвердите актуальные документы."),
      goal_allocation_exceeded: T("Сумма долей активных целей превышает 100%. Уменьшите долю этой цели."),
      active_live_execution_must_be_reconciled: T("Есть незавершённое исполнение. Откройте Настройки → Ранее начатые исполнения и сверьте заявку перед отключением или удалением аккаунта.")
    };
    const fallback = error?.status === 422 ? T("Проверьте поля и допустимые значения. Сервер не принял изменение.") : renderHumanErrorValue3(error);
    const code = error?.code || error?.message;
    return reasons[code] || recoveryErrorReason(code) || fallback;
  };
  const isCancelled = error => error?.name === "AbortError" || error?.message === "profile_context_changed";
  const toast = (message, isError = false) => {
    const item = document.createElement("div");
    item.className = `toast${isError ? " error" : ""}`;
    item.textContent = message;
    $("#toast-region").append(item);
    window.setTimeout(() => item.remove(), isError ? 7000 : 4200);
  };
  const showMessage = (element, text, isError = false) => {
    if (!element) return;
    element.textContent = text;
    element.classList.toggle("error", isError);
    element.classList.toggle("success", !isError && Boolean(text));
  };
  const openDialog = (title, content) => {
    captureScreenDrafts();
    const routed = dialogScreens.has(`${state.view}/${state.route.screen}`);
    if (!routed) {
      const overlay = state.route.overlay && state.route.overlay !== "auth" ? state.route.overlay : `dialog-${crypto.randomUUID()}`;
      transientDialogs.set(overlay, {title, content});
      if (state.route.overlay !== overlay) updateViewRoute({overlay});
    }
    state.eventRequest = (state.eventRequest || 0) + 1;
    state.recovery.id = null;
    state.recovery.record = null;
    state.recovery.uncertain = false;
    state.recovery.busy = false;
    state.recovery.sequence += 1;
    const dialog = $("#workspace-dialog");
    $("#dialog-title").textContent = title;
    $("#dialog-content").innerHTML = content;
    dialog.classList.toggle("route-dialog", routed);
    const close = $(".dialog-header [data-close-dialog]", dialog);
    close.innerHTML = icon(routed ? "back" : "close", true);
    close.setAttribute("aria-label", T("navigation.back"));
    restoreScreenDrafts(dialog);
    if (state.outdated) flagApplicationUpdate();
    if (!dialog.open) dialog.showModal();
    U.bindCharts(dialog);
    return dialog;
  };
  const requireUser = () => {
    if (!state.user || state.tour) {
      openAuth();
      return false;
    }
    return !state.locked;
  };
  let quoteStream = null;
  let quoteFailures = 0;
  let quoteReconnectTimer = null;
  let freshnessTimer = null;
  let freshnessBusy = false;
  const stopQuoteStream = () => {
    clearTimeout(quoteReconnectTimer);
    quoteStream?.close();
    quoteStream = null;
  };
  const startQuoteStream = () => {
    stopQuoteStream();
    if (!window.EventSource || !state.user || state.locked || state.tour || state.view !== "asset" || !state.asset?.market || document.visibilityState !== "visible" || !navigator.onLine) return;
    const uid = state.asset.uid;
    const generation = state.generation;
    const stream = new EventSource(`/api/market/instruments/${safeSegment(uid)}/stream?profile_context=${encodeURIComponent(state.user.public_id)}`);
    quoteStream = stream;
    const current = () => quoteStream === stream && generation === state.generation && state.view === "asset" && state.asset?.uid === uid && !state.locked;
    const repaint = () => {
      const container = $("#view-asset");
      // A tick must not replace a chart or focused control being inspected.
      const quote = $("[data-market-quote]", container);
      if (quote) quote.innerHTML = assetQuoteHTML(assetPricing(state.asset));
      const source = $("[data-market-source]", container);
      const market = state.asset.market;
      if (source) source.innerHTML = freshness(market.source || "T-Invest", market.quote_time || market.observed_at, market.quote_status);
      for (const row of $$(".asset-tab-content .info-row", container)) {
        const label = $("dt", row)?.textContent;
        const value = $("dd", row);
        if (value && label === T("Последняя цена")) value.textContent = marketPrice(market.last_price, market.price_unit, market.price_currency);
        if (value && label === T("Время цены")) value.textContent = date(market.quote_time, true);
      }
    };
    const reconnect = () => {
      if (!current()) return;
      stopQuoteStream();
      quoteFailures += 1;
      state.asset.market.quote_status = navigator.onLine ? "reconnect" : "offline";
      repaint();
      if (navigator.onLine && document.visibilityState === "visible") quoteReconnectTimer = setTimeout(() => {
        if (generation === state.generation && state.view === "asset" && state.asset?.uid === uid) startQuoteStream();
      }, Math.min(30000, 1000 * 2 ** Math.min(quoteFailures, 5)));
    };
    state.asset.market.quote_status = "connecting";
    repaint();
    stream.addEventListener("open", () => { if (current()) { state.asset.market.quote_status = "connecting"; repaint(); } });
    stream.addEventListener("market", event => {
      if (!current()) return;
      try {
        const payload = JSON.parse(event.data);
        const observedAt = Date.parse(payload.observed_at);
        if (payload.instrument_uid !== uid || typeof payload.observed_at !== "string" || !Number.isFinite(observedAt) || !["currency", "percent_nominal", "points", "per_nominal", "unknown"].includes(payload.price_unit)) throw new Error("invalid_market_stream");
        if (observedAt < Date.parse(state.asset.market.observed_at)) return;
        state.asset.market = {...state.asset.market, ...payload};
        quoteFailures = 0;
        repaint();
      } catch {
        reconnect();
      }
    });
    stream.addEventListener("status", event => {
      if (!current()) return;
      let status;
      try { status = JSON.parse(event.data).state; } catch { status = "invalid"; }
      if (["profile_context_changed", "unauthenticated"].includes(status)) {
        stopQuoteStream();
        lockSession(T("Сессия изменилась. Данные очищены; войдите снова."));
        return;
      }
      state.asset.market.quote_status = status;
      if (["offline", "invalid", "disconnected", "reconnect"].includes(status)) { reconnect(); return; }
      repaint();
    });
    stream.onerror = reconnect;
  };
  const clearPrivateState = () => {
    stopQuoteStream();
    stopTableQuotes();
    clearTimeout(eventSummaryTimer);
    state.quotes = {};
    state.screenDrafts = {};
    state.screenBaselines = {};
    state.authReturn = null;
    transientDialogs.clear();
    try { sessionStorage.removeItem("omnicio-update-drafts"); } catch { /* No stored draft can survive an identity reset. */ }
    clearTimeout(freshnessTimer);
    state.generation += 1;
    for (const controller of state.requests) controller.abort();
    state.requests.clear();
    state.resourceVersions.clear();
    state.resourceRequests.clear();
    state.deletedGoalIds.clear();
    state.loading.clear();
    clearTimeout(state.prefs.timer);
    clearTimeout(state.strategy.timer);
    clearTimeout(state.researchRequest?.timer);
    state.researchRequest = null;
    state.researchDraft = {};
    state.researchArchiveDialog = null;
    state.researchDisplaySequence = 0;
    clearTimeout(state.refresh.timer);
    state.refresh = {
      sequence: state.refresh.sequence + 1,
      timer: null,
      busy: false
    };
    state.recovery = {
      id: null,
      sequence: state.recovery.sequence + 1,
      busy: false,
      record: null,
      uncertain: false
    };
    state.user = null;
    state.pendingTheme = null;
    state.data = {};
    state.errors = {};
    state.formDrafts = {};
    state.formBaselines = {};
    state.chat = [];
    state.billingBusy = false;
    state.executionBusy = false;
    state.executionPlan = null;
    state.assistantConversation = null;
    state.assistantDraft = {message: "", context: "general", include_news: false, research_run_id: ""};
    state.assistantRequest = null;
    state.assistantMemorySelected = new Set();
    state.assistantMemoryDraftId = null;
    state.assistantSources = null;
    state.assistantSourceSelection = null;
    state.asset = null;
    state.strategyPane = "catalog";
    state.searchResults = [];
    state.searchPages = {events: null, news: null};
    state.searchFailures = {};
    state.eventDetail = null;
    state.eventHistoryExtended = false;
    state.deliveryBusy = false;
    state.deliveryDrafts = {};
    state.prefs = {
      server: null,
      draft: null,
      revision: 0,
      dirty: false,
      busy: false,
      error: null,
      timer: null
    };
    state.strategy = {
      server: null,
      draft: null,
      revision: 0,
      dirty: false,
      busy: false,
      error: null,
      intent: "edit",
      timer: null,
      assessment: null,
      research: null
    };
    state.assistantBusy = false;
    state.brokerPreview = null;
    state.brokerSequence = (state.brokerSequence || 0) + 1;
    U.setPrivacy(false);
    U.clearCharts();
    for (const view of $$(".view")) view.replaceChildren();
    $("#profile-name").textContent = T("Мой профиль");
    $("#profile-avatar").textContent = T("О");
    $("#global-search").value = "";
    $("#dialog-content").replaceChildren();
    $("#toast-region").replaceChildren();
    for (const dialog of $$("dialog[open]")) dialog.close();
    closeDrawer(false);
    $("#profile-menu").hidden = true;
  };
  const lockSession = message => {
    if (state.locked) return;
    clearPrivateState();
    state.locked = true;
    state.tour = false;
    $("#app-shell").hidden = true;
    state.session.status = "guest";
    state.mode = "account";
    sessionSurface();
    $("#session-message").textContent = message;
    $("#session-dialog").showModal();
  };
  const applyTheme = choice => {
    if (!["dark", "light", "system"].includes(choice)) return;
    themeChoice = choice;
    const actual = choice === "system" ? renderApplyThemeValue() : choice;
    document.documentElement.dataset.theme = actual;
    $("meta[name=theme-color]").content = actual === "dark" ? "#071421" : "#eff4fa";
    for (const item of $$("[data-theme-choice]")) item.setAttribute("aria-pressed", String(item.dataset.themeChoice === choice));
    try {
      localStorage.setItem("omnicio-theme", choice);
    } catch {/* Display preference only. */}
  };
  const renderNav = () => {
    $("#sidebar-nav").innerHTML = U.navigation.map(([key, title]) => `<a class="nav-link" href="${U.routeHash({mode: state.mode === "demo" ? "demo" : "account", view: key})}" data-route="${key}"${state.view === key || key === "market" && ["asset", "search"].includes(state.view) ? ' aria-current="page"' : ""}>${icon(key)}<span>${title}</span></a>`).join("");
    $("#mobile-nav").innerHTML = [["home", T("Главная")], ["market", T("Рынок")], ["assistant", T("ИИ")], ["strategies", T("Стратегии")]].map(([key, title]) => `<a href="${U.routeHash({mode: state.mode === "demo" ? "demo" : "account", view: key})}" data-route="${key}"${state.view === key || key === "market" && ["asset", "search"].includes(state.view) ? ' aria-current="page"' : ""}>${icon(key)}<span>${title}</span></a>`).join("");
  };
  const openDrawer = () => {
    state.drawerReturn = $("#app-menu-toggle");
    $("#app-sidebar").inert = false;
    $("#app-sidebar").dataset.open = "true";
    $("#drawer-backdrop").hidden = false;
    $("#app-menu-toggle").setAttribute("aria-expanded", "true");
    $(".app-main").inert = true;
    $("#mobile-nav").inert = true;
    document.body.classList.add("drawer-open");
    $("#drawer-close").focus();
  };
  function closeDrawer(restore = true) {
    delete $("#app-sidebar").dataset.open;
    $("#app-sidebar").inert = window.innerWidth <= 960;
    $("#drawer-backdrop").hidden = true;
    $("#app-menu-toggle").setAttribute("aria-expanded", "false");
    $(".app-main").inert = false;
    $("#mobile-nav").inert = false;
    document.body.classList.remove("drawer-open");
    if (restore && state.drawerReturn?.isConnected) state.drawerReturn.focus();
    state.drawerReturn = null;
  }
  const parseRoute = () => U.parseRoute(location.hash);
  const activeRoute = () => ({...state.route, mode: state.mode, view: state.view});
  const saveNavigationPosition = () => {
    if (!history.state?.omnicio) return;
    history.replaceState({...history.state, scroll: window.scrollY, dialogScroll: $("dialog[open]")?.scrollTop || 0}, "", location.href);
  };
  const rememberRoute = route => {
    try { localStorage.setItem("omnicio-last-route", U.routeHash(U.resumeRoute(route))); } catch { /* Navigation has no session authority. */ }
  };
  const updateRouteHistory = (view, detail, {replace, fromHistory}) => {
    const route = {...detail, mode: state.mode, view};
    const hash = U.routeHash(route);
    rememberRoute(route);
    if (fromHistory) return;
    const previous = history.state?.omnicio ? history.state : null;
    const append = location.hash !== hash && !replace;
    const scroll = replace && previous ? previous.scroll || 0 : 0;
    const dialogScroll = replace && previous ? previous.dialogScroll || 0 : 0;
    const index = (previous?.index || 0) + Number(Boolean(previous && append));
    const previousRoute = append ? location.hash : previous?.previous || null;
    const entry = {omnicio: true, view, route, scroll, dialogScroll, index, previous: previousRoute};
    history[append ? "pushState" : "replaceState"](entry, "", hash);
  };
  const restoreRouteControls = route => {
    state.assetTab = "chart";
    state.assetFilter = "all";
    state.eventFilter = "all";
    state.sort = "name";
    state.sortDirection = 1;
    state.cbrCurrency = "USD";
    state.cbrPeriod = "1m";
    state.strategyPane = "catalog";
    if (["home", "portfolio", "analytics", "asset"].includes(route.view)) state[`${route.view}Period`] = ["home", "asset"].includes(route.view) ? "1m" : "1y";
    const knownPeriods = ["1d", "1w", "1m", "3m", "1y", "all"];
    if (["home", "portfolio", "analytics", "asset"].includes(route.view) && knownPeriods.includes(route.period)) state[`${route.view}Period`] = route.period;
    if (["overview", "chart", "metrics", "news"].includes(route.tab)) state.assetTab = route.tab;
    if (assetTypes().some(([key]) => key === route.asset_filter)) state.assetFilter = route.asset_filter;
    if (["all", "important", "assets", "market"].includes(route.event_filter || route.filter)) state.eventFilter = route.event_filter || route.filter;
    if (["name", "price", "change", "share", "value"].includes(route.sort)) state.sort = route.sort;
    if (["-1", "1"].includes(String(route.direction))) state.sortDirection = Number(route.direction);
    if (["USD", "EUR", "CNY"].includes(route.currency)) state.cbrCurrency = route.currency;
    if (["1m", "3m", "1y"].includes(route.reference_period)) state.cbrPeriod = route.reference_period;
    if (["catalog", "custom"].includes(route.strategy_pane)) state.strategyPane = route.strategy_pane;
  };
  const updateViewRoute = (detail, {replace = false} = {}) => {
    saveNavigationPosition();
    state.route = {...state.route, ...detail};
    updateRouteHistory(state.view, state.route, {replace, fromHistory: false});
  };
  const routeBack = () => {
    if (history.state?.omnicio && history.state.index > 0 && history.state.previous) history.back();
    else if (state.route.screen || state.route.overlay) navigate(state.view, {mode: state.mode}, {replace: true});
    else {
      let parent = ["asset", "search"].includes(state.view) ? "market" : "home";
      if (state.mode === "public") parent = "public/welcome";
      navigate(parent, {mode: state.mode}, {replace: true});
    }
  };
  const closeRouteDialogs = () => {
    for (const dialog of $$("dialog[open]")) if (dialog.id !== "session-dialog") {
      dialog.dataset.routeClosing = "true";
      dialog.close();
    }
  };
  const sessionSurfaceContent = () => {
    if (state.session.status === "checking") return {title: T("session.checking"), content: U.loading(T("session.checking_details"))};
    const failed = state.session.status === "error";
    const title = failed ? T("session.retry_title") : T("session.signin_title");
    const message = failed ? humanError(state.session.error) : T("session.signin_details");
    const actionLabel = failed ? T("session.retry") : T("Войти");
    const action = failed ? "session-retry" : "login";
    return {title, content: `<p>${esc(message)}</p><div class="form-actions">${button(actionLabel, action, {primary: true})}${button(T("navigation.public_home"), "public-home")}</div>`};
  };
  const sessionSurface = () => {
    $("#public-site").hidden = true;
    $("#app-shell").hidden = true;
    const {title, content} = sessionSurfaceContent();
    $("#startup-state").hidden = false;
    $("#startup-state").innerHTML = `<section class="card startup-card"><img class="brand-image" src="/assets/brand/omnicio-logo.png" alt="OMNICIO"><h1>${esc(title)}</h1>${content}</section>`;
  };
  const showPublic = route => {
    $("#startup-state").hidden = true;
    $("#app-shell").hidden = true;
    $("#public-site").hidden = false;
    const page = route.view;
    const id = page === "strategies" ? "public-strategies" : page;
    for (const section of $$("#public-content > section")) section.hidden = section.id !== id;
    for (const link of $$(".public-nav [data-public-page]")) link.setAttribute("aria-current", link.dataset.publicPage === page ? "page" : "false");
    const breadcrumb = $("#public-breadcrumb");
    breadcrumb.hidden = page === "welcome";
    breadcrumb.innerHTML = `<button class="button secondary small-button" data-action="route-back">${icon("back", true)} ${H("navigation.back")}</button>`;
    document.title = `${page === "welcome" ? T("OMNICIO — ваш инвестиционный помощник") : T("public.page." + page)} · OMNICIO`;

  };
  const resolveNavigationRoute = (view, detail) => {
    let mode = detail.mode || state.mode;
    if (!detail.mode && ["public", "auto"].includes(mode)) mode = state.user ? "account" : "demo";
    const path = /^(public|demo|account)\//.test(view) ? view : `${mode}/${view}`;
    const parsed = U.parseRoute("#" + path);
    const route = {...parsed, ...detail, view: parsed.view, screen: detail.screen ?? parsed.screen};
    if (route.mode === "auto") route.mode = !state.user && state.session.status === "guest" ? "demo" : "account";
    return route;
  };
  const navigate = (view, detail = {}, {
    replace = false,
    fromHistory = false
  } = {}) => {
    const route = resolveNavigationRoute(view, detail);
    if (route.invalid) { showRouteError(); return; }
    const scrollPosition = fromHistory ? {top: history.state?.scroll || 0, dialogTop: history.state?.dialogScroll || 0} : {top: 0, dialogTop: 0};
    if (!fromHistory) saveNavigationPosition();
    captureScreenDrafts();
    state.viewState[state.view] = {...state.route};
    closeRouteDialogs();
    closeDrawer(false);
    $("#profile-menu").hidden = true;
    $("#profile-button").setAttribute("aria-expanded", "false");
    if (state.view === "settings" && (route.view !== "settings" || route.screen !== state.route.screen)) {
      resetBrokerPreview();
      const credential = $('#broker-form [name="credential"]');
      if (credential) credential.value = "";
    }
    stopQuoteStream();
    stopTableQuotes();
    state.mode = route.mode;
    state.tour = route.mode === "demo";
    state.view = route.view;
    state.route = route;
    state.navigationSequence += 1;
    const sequence = state.navigationSequence;
    restoreRouteControls(route);
    updateRouteHistory(route.view, route, {
      replace,
      fromHistory
    });
    if (route.mode === "public") { showPublic(route); restoreNavigationScroll(scrollPosition, sequence); void openRouteScreen(route); return; }
    if (route.mode === "account" && (!state.user || state.locked)) { sessionSurface(); return; }
    $("#startup-state").hidden = true;
    $("#public-site").hidden = true;
    $("#app-shell").hidden = false;
    $("#tour-notice").hidden = !state.tour;
    for (const element of $$("[data-view]")) element.hidden = element.dataset.view !== route.view;
    document.title = `${U.navigation.find(([key]) => key === route.view)?.[1] || (route.view === "asset" ? T("Актив") : T("Поиск"))} · OMNICIO`;
    renderNav();
    renderCurrent();
    void loadNavigationScreen(route, scrollPosition, sequence).catch(error => {
      if (sequence === state.navigationSequence && !isCancelled(error)) showRouteLoadError(error);
    });
    $("#main-content").focus({
      preventScroll: true
    });
    restoreNavigationScroll(scrollPosition, sequence);
    scheduleTableQuotes(100);
    scheduleEventSummary(100);
  };
  const loadNavigationScreen = async (route, scrollPosition, sequence) => {
    const resources = loadForView(route.view, route);
    const independent = routeScreenHasData(route);
    if (independent) {
      void resources.catch(error => {
        if (sequence === state.navigationSequence && !isCancelled(error)) toast(humanError(error), true);
      });
    } else await resources;
    if (sequence !== state.navigationSequence) return;
    await openRouteScreen(route);
    restoreNavigationScroll(scrollPosition, sequence);
  };
  const routeScreenHasData = route => {
    if (route.view === "settings" && route.screen === "support" || route.view === "events" && route.screen === "news") return true;
    if (route.view !== "goals") return false;
    if (route.screen === "create") return true;
    return ["edit", "plan"].includes(route.screen) && Boolean(state.data.goals?.items?.some(goal => goal.id === route.goal_id));
  };
  const restoreNavigationScroll = ({top, dialogTop}, sequence) => {
    requestAnimationFrame(() => {
      if (sequence !== state.navigationSequence) return;
      window.scrollTo({top, behavior: "instant"});
      $("dialog[open]")?.scrollTo({top: dialogTop, behavior: "instant"});
    });
  };
  const showRouteError = () => {
    $("#public-site").hidden = true;
    $("#app-shell").hidden = true;
    $("#startup-state").hidden = false;
    $("#startup-state").innerHTML = `<section class="card startup-card"><h1>${H("navigation.not_found")}</h1><p>${H("navigation.not_found_details")}</p>${button(T("navigation.public_home"), "public-home")}</section>`;
  };
  const showRouteLoadError = error => {
    const target = $(`#view-${state.view}`);
    if (target) target.innerHTML = `<section class="card">${empty(T("state.load_failed"), humanError(error), "refresh", T("Повторить загрузку"), "info", true)}</section>`;
  };
  const showApp = (tour = false) => {
    const route = parseRoute();
    const view = route.mode === "public" || route.invalid ? "home" : route.view;
    navigate(view, {...route, view, screen: views.has(view) ? route.screen : "", mode: tour ? "demo" : "account", invalid: false}, {replace: !tour});
    if (!tour) {
      void resumeWorkspaceRefresh();
      clearTimeout(freshnessTimer);
      freshnessTimer = setTimeout(() => void refreshVisibleData(), 60000);
    }
  };
  const loadResource = async (name, path, {
    force = false,
    read = null,
    ...options
  } = {}) => {
    const currentRequest = state.resourceRequests.get(name);
    if (!force && currentRequest?.path === path) return currentRequest.promise;
    if (!force && state.data[name] !== undefined) return state.data[name];
    if (name === "executions") delete state.data.executions;
    const sequence = (state.resourceVersions.get(name) || 0) + 1;
    state.resourceVersions.set(name, sequence);
    const generation = state.generation;
    const goalsSequence = state.resourceVersions.get("goals") || 0;
    state.loading.add(name);
    delete state.errors[name];
    const promise = (read ? read() : api(path, options)).then(payload => {
      if (generation !== state.generation || state.resourceVersions.get(name) !== sequence) return null;
      state.data[name] = resourceSnapshot(name, payload);
      adoptLoadedResource(name, payload, goalsSequence);
      return payload;
    }).catch(error => {
      if (generation === state.generation && state.resourceVersions.get(name) === sequence && !isCancelled(error)) state.errors[name] = error;
      return null;
    }).finally(() => {
      if (generation === state.generation && state.resourceVersions.get(name) === sequence) {
        state.loading.delete(name);
        state.resourceRequests.delete(name);
        if (state.mode !== "public" && (state.user || state.tour) && !state.locked && !document.activeElement?.matches("input,textarea,select") && !$("dialog[open]")) renderCurrent();
      }
    });
    state.resourceRequests.set(name, {path, promise});
    return promise;
  };
  const resourceSnapshot = (name, payload) => {
    if (name === "goals") return mergeGoalList(payload);
    if (name === "events") return eventSnapshot(payload);
    return payload;
  };
  const adoptWorkspace = (payload, goalsSequence) => {
    if (payload.preferences) adoptPreferences(payload.preferences);
    if (payload.goals && goalsSequence === (state.resourceVersions.get("goals") || 0)) state.data.goals = mergeGoalList(payload.goals);
    if (payload.events) state.data.events = eventSnapshot(payload.events);
    if (payload.connection) state.data.connection = payload.connection;
    $("#workspace-freshness").textContent = payload.overview?.observed_at ? `T-Invest · ${date(payload.overview.observed_at, true)} ${T("МСК · Стоимость по последнему наблюдению")}` : renderAdoptWorkspaceValue(payload);
  };
  const adoptLoadedResource = (name, payload, goalsSequence) => {
    if (name === "workspace") adoptWorkspace(payload, goalsSequence);
    if (name === "preferences") adoptPreferences(payload);
    if (name === "strategy") adoptStrategy(payload);
  };
  const workspacePeriod = (view = state.view) => {
    if (view === "home") return state.homePeriod;
    if (view === "portfolio") return state.portfolioPeriod;
    if (view === "analytics") return state.analyticsPeriod;
    return "all";
  };
  const workspacePath = () => `/api/workspace?history_period=${workspacePeriod()}`;
  const viewResources = [{
    name: "news",
    views: ["home", "market", "events", "asset", "search"],
    path: "/api/public/news",
    public: true
  }, {
    name: "identities",
    views: ["profile"],
    path: "/api/auth/identities"
  }, {
    name: "billing",
    views: ["profile"],
    path: "/api/billing"
  }, {
    name: "sessions",
    views: ["profile"],
    path: "/api/me/sessions"
  }, {
    name: "workspace",
    views: ["home", "portfolio", "analytics", "goals", "events", "settings", "profile"],
    path: workspacePath
  }, {
    name: "visualization",
    views: ["home", "portfolio", "analytics", "market"],
    path: "/api/portfolio/visualization?history_limit=365"
  }, {
    name: "strategy",
    views: ["home", "strategies", "analytics"],
    path: "/api/profile/strategy"
  }, {
    name: "catalog",
    views: ["home", "strategies", "analytics"],
    path: "/api/strategy/catalog",
    public: true
  }, {
    name: "investmentProfile",
    views: ["strategies"],
    path: "/api/profile/investment"
  }, {
    name: "balancingPolicy",
    views: ["strategies"],
    path: "/api/profile/balancing"
  }, {
    name: "marketReference",
    views: ["home", "market"],
    path: () => `/api/public/market-reference?currency=${state.cbrCurrency}&period=${state.cbrPeriod}`,
    public: true
  }, {
    name: "preferences",
    views: [...views],
    path: "/api/preferences"
  }, {
    name: "connection",
    views: ["market", "asset", "settings", "profile"],
    path: "/api/broker/tbank"
  }, {
    name: "executions",
    views: ["settings", "strategies"],
    path: "/api/portfolio/executions"
  }, {
    name: "executionCapabilities",
    views: ["settings", "strategies"],
    path: "/api/portfolio/execution-capabilities"
  }, {
    name: "assistantConversations",
    views: ["assistant"],
    path: "/api/assistant/conversations"
  }, {
    name: "researchArchive",
    views: ["strategies"],
    path: "/api/research/runs?limit=50"
  }, {
    name: "assistantResearch",
    views: ["assistant"],
    path: "/api/research/runs?limit=200",
    read: () => readResearchChoices()
  }, {
    name: "assistantMemory",
    views: ["assistant"],
    path: "/api/assistant/memory"
  }, {
    name: "assistantStatus",
    views: ["assistant"],
    path: "/api/assistant/status"
  }, {
    name: "events",
    views: ["home", "events"],
    path: () => eventsPath()
  }, {
    name: "marketArchive",
    views: ["events"],
    path: "/api/news?limit=50"
  }, {
    name: "notifications",
    views: ["settings"],
    path: "/api/notifications"
  }, {
    name: "operationalMetrics",
    views: ["settings"],
    path: "/api/system/metrics",
    operator: true
  }, {
    name: "goals",
    views: ["goals"],
    path: "/api/goals"
  }, {
    name: "ledger",
    views: ["portfolio"],
    path: "/api/workspace/operations?limit=50"
  }, {
    name: "support",
    views: [],
    path: "/api/public/support",
    public: true
  }, {
    name: "analysis",
    views: ["analytics"],
    path: "/api/broker/tbank/analysis",
    timeout: 45000
  }];
  const loadAssetView = async (uid, force) => {
    try {
      await loadAsset(uid, force);
    } catch (error) {
      if (!isCancelled(error) && state.view === "asset") {
        state.asset = null;
        $("#view-asset").innerHTML = empty(T("Некорректный инструмент"), T("Откройте актив из портфеля или результатов поиска."), "", "", "info", true);
      }
    }
  };
  const loadForView = async (view, detail = {}, force = false) => {
    const generation = state.generation;
    const sequence = state.navigationSequence;
    const current = () => generation === state.generation && sequence === state.navigationSequence && state.view === view;
    const resources = viewResources.filter(resource => resource.views.includes(view) && (!state.tour || resource.public) && (!resource.operator || state.user?.can_view_operational_metrics === true));
    const resourceWork = resources.map(resource => {
      const historyChanged = resource.name === "workspace" && state.data.workspace?.overview?.history_coverage?.period !== workspacePeriod(view);
      return loadResource(resource.name, typeof resource.path === "function" ? resource.path() : resource.path, {
        force: force || historyChanged,
        read: resource.read,
        timeout: resource.timeout || 30000
      });
    });
    if (state.view === view) renderCurrent();
    const secondary = Promise.allSettled(resourceWork);
    if (["asset", "search"].includes(view)) {
      if (current()) await renderLoadedView(view, detail, force);
      return;
    }
    await secondary;
    if (!current()) return;
    if (view === "strategies") restoreResearchRequest();
    if (view === "assistant") await loadSelectedAssistantConversation();
    if (!current()) return;
    await renderLoadedView(view, detail, force);
  };
  const renderLoadedView = async (view, detail, force) => {
    if (view === "asset" && detail.uid && !state.tour) {
      if (detail.uid === state.route.uid) await loadAssetView(detail.uid, force);
      return;
    }
    if (view === "search") {
      if ((detail.q || "") === (state.route.q || "")) await runSearch(detail.q || "");
      return;
    }
    if (!document.activeElement?.matches("input,textarea,select") && !$("dialog[open]")) renderCurrent();
    if (view === "goals" && detail.goal_id) focusGoal(detail.goal_id);
  };
  const loadSelectedAssistantConversation = async () => {
    if (state.tour || state.assistantBusy) return;
    const selected = state.route.conversation || state.assistantConversation?.id || state.data.assistantConversations?.items?.[0]?.id;
    if (!selected) return;
    try { await loadAssistantConversation(selected); }
    catch (error) { if (!isCancelled(error)) toast(humanError(error), true); }
  };
  const focusGoal = id => {
    const target = $(`[data-goal-id="${CSS.escape(id)}"]`);
    target?.scrollIntoView({block: "center", behavior: "instant"});
    target?.setAttribute("tabindex", "-1");
    target?.focus({preventScroll: true});
  };
  const dataError = (name, label = T("Не удалось загрузить данные")) => {
    if (!state.errors[name]) return "";
    const retry = button(T("Повторить загрузку"), "resource-retry", {small: true,
      extra: `data-resource="${esc(name)}"${state.loading.has(name) ? " disabled aria-busy=\"true\"" : ""}`});
    return `<div class="notice error"><strong>${esc(label)}</strong><p>${esc(humanError(state.errors[name]))}</p>${retry}</div>`;
  };
  const retryResource = async control => {
    const resource = viewResources.find(item => item.name === control.dataset.resource);
    if (!resource || state.loading.has(resource.name) || !resource.public && !requireUser() || resource.operator && state.user?.can_view_operational_metrics !== true) return;
    if (resource.name === "billing" && control.closest("#dialog-content")) {
      await openBilling();
      return;
    }
    const generation = state.generation;
    const view = state.view;
    control.disabled = true;
    control.setAttribute("aria-busy", "true");
    await loadResource(resource.name, typeof resource.path === "function" ? resource.path() : resource.path, {
      force: true,
      read: resource.read,
      timeout: resource.timeout || 30000
    });
    if (generation !== state.generation || state.view !== view) return;
    if (resource.name === "researchArchive") restoreResearchRequest();
    if (resource.name === "notifications") renderNotificationPanel();
    else if (resource.name === "support") await loadSupport($(state.mode === "public" ? "#support" : "#workspace-support"));
    else renderCurrent();
  };
  const updateIdentity = () => {
    const name = state.tour ? T("Знакомство") : state.prefs.draft?.display_name?.trim() || T("Мой профиль");
    $("#profile-name").textContent = name;
    $("#profile-avatar").textContent = name[0]?.toLocaleUpperCase("ru-RU") || T("О");
    const unread = number(state.data.eventSummary?.unread_total ?? state.data.events?.unread_count) || 0;
    $("#notification-dot").hidden = unread === 0 || state.tour || Boolean(state.data.events?.alerts_suppressed);
    $("#notifications-button").setAttribute("aria-label", unread ? `${T("Уведомления:")} ${unread} ${T("непрочитанных")}` : T("Уведомления"));
  };
  const refreshActive = result => ["queued", "running"].includes(result?.status);
  const refreshContext = () => ({
    generation: state.generation,
    sequence: ++state.refresh.sequence
  });
  const currentRefresh = context => context.generation === state.generation && context.sequence === state.refresh.sequence && Boolean(state.user) && !state.locked;
  const refreshUnavailable = () => {
    if (state.refresh.busy) return true;
    if (state.errors.refreshStatus) return false;
    const connected = state.data.connection?.connected || state.data.workspace?.connection?.connected;
    return refreshActive(state.data.refreshStatus) || Boolean(connected && state.data.refreshStatus?.can_refresh === false);
  };
  const updateRefreshControls = () => {
    const unavailable = refreshUnavailable();
    const collecting = state.refresh.busy || refreshActive(state.data.refreshStatus);
    for (const control of $$('[data-action="workspace-refresh"]')) {
      control.disabled = unavailable;
      control.setAttribute("aria-busy", String(collecting));
    }
    if (!["home", "portfolio", "analytics", "settings"].includes(state.view)) return;
    for (const control of $$('[data-view="' + state.view + '"] [data-action="refresh"]')) {
      control.disabled = unavailable;
      control.setAttribute("aria-busy", String(collecting));
    }
  };
  const workspaceRefreshText = () => {
    const result = state.data.refreshStatus;
    if (state.errors.refreshStatus) return humanError(state.errors.refreshStatus);
    if (state.refresh.busy && !refreshActive(result)) return T("Запрашиваем обновление у сервера…");
    const labels = {
      queued: T("Обновление поставлено в очередь. Источник данных подключён; ожидаем начало сбора."),
      running: T("Получаем портфель и историю операций из T-Invest. Показатели обновятся после сохранения наблюдения."),
      degraded: T("Наблюдение обновлено частично. Полнота истории операций проверяется отдельно; недоступные показатели не рассчитываются."),
      failed: T("Обновление не завершилось. Сохранённые ранее данные остаются отмечены временем наблюдения.")
    };
    let text = labels[result?.status] || "";
    const reasons = {
      consent_required: T("Примите актуальные документы, повторно выполнив вход в аккаунт."),
      worker_interrupted: T("Сбор данных прерван перезапуском сервиса; его можно повторить."),
      observation_context_changed: T("Подключение или разрешения изменились. Проверьте настройки источника."),
      observation_interrupted: T("Подключение или разрешения изменились. Проверьте настройки источника."),
      ObservationCancelled: T("Подключение или разрешения изменились. Проверьте настройки источника."),
      TBankUnavailable: T("Источник T-Invest временно недоступен."),
      TBankTokenRejected: T("Источник перестал принимать токен. Проверьте подключение."),
      BrokerConnectionError: T("Подключение изменилось. Проверьте источник данных."),
      BrokerNotConnected: T("Источник данных сейчас не подключён."),
      ValueError: T("Ответ источника не прошёл проверку согласованности.")
    };
    if (reasons[result?.reason]) text += " " + reasons[result.reason];
    if (result?.history_status === "continuation_pending") text += T(" Получена часть истории операций; следующее обновление продолжит сбор.");
    if (["opened_date_missing", "opened_date_invalid"].includes(result?.history_status)) text += T(" Источник не подтвердил дату открытия счёта; полнота истории пока неизвестна.");
    if (result?.reason === "refresh_cooldown") text += ` ${T("Следующее обновление доступно через")} ${format(result.retry_after_seconds, 0)} ${T("с.")}`;
    if (text && result?.observed_at) text += ` ${T("Последнее наблюдение:")} ${date(result.observed_at, true)} ${T("МСК.")}`;
    return text;
  };
  const scheduleRefreshPoll = (context, delay) => {
    clearTimeout(state.refresh.timer);
    state.refresh.timer = window.setTimeout(() => {
      if (currentRefresh(context)) void pollWorkspaceRefresh(context);
    }, delay);
  };
  const repaintRefreshedWorkspace = () => {
    if (["home", "portfolio", "analytics", "goals", "events"].includes(state.view)) renderCurrent();else {
      updateIdentity();
      renderConnectionBanner();
      if (state.view === "settings") {
        const target = $("#broker-settings");
        if (target) target.innerHTML = `<h2 class="panel-title">${H("Подключение T-Invest")}</h2>${brokerSettingsHTML()}`;
      }
    }
    updateRefreshControls();
  };
  const reloadWorkspaceObservation = async context => {
    const resources = [["workspace", workspacePath()], ["visualization", "/api/portfolio/visualization?history_limit=365"]];
    if (state.view === "analytics") resources.push(["analysis", "/api/broker/tbank/analysis"]);else delete state.data.analysis;
    await Promise.allSettled(resources.map(([name, path]) => loadResource(name, path, {
      force: true,
      timeout: 45000
    })));
    if (!currentRefresh(context)) return;
    state.strategy.assessment = null;
    repaintRefreshedWorkspace();
  };
  const adoptRefreshStatus = async (result, context) => {
    if (!currentRefresh(context)) return;
    const previous = state.data.refreshStatus;
    state.data.refreshStatus = result;
    delete state.errors.refreshStatus;
    renderConnectionBanner();
    updateRefreshControls();
    const changedObservation = result.observed_at && result.observed_at !== state.data.workspace?.overview?.observed_at;
    const finished = (refreshActive(previous) || state.refresh.busy) && !refreshActive(result);
    if (changedObservation || finished) await reloadWorkspaceObservation(context);
    if (!currentRefresh(context)) return;
    if (refreshActive(result)) scheduleRefreshPoll(context, 2500);else if (!result.can_refresh && result.retry_after_seconds > 0) scheduleRefreshPoll(context, Math.min(60000, result.retry_after_seconds * 1000));
  };
  const refreshFailed = (error, context) => {
    if (!currentRefresh(context) || isCancelled(error)) return;
    state.errors.refreshStatus = error;
    renderConnectionBanner();
    updateRefreshControls();
  };
  const pollWorkspaceRefresh = async context => {
    if (!currentRefresh(context)) return;
    try {
      await adoptRefreshStatus(await api("/api/workspace/refresh"), context);
    } catch (error) {
      refreshFailed(error, context);
    }
  };
  const resumeWorkspaceRefresh = async () => {
    if (!state.user || state.tour || state.locked || state.refresh.busy) return;
    const context = refreshContext();
    clearTimeout(state.refresh.timer);
    await pollWorkspaceRefresh(context);
  };
  const requestWorkspaceRefresh = async () => {
    if (!requireUser() || state.refresh.busy) return;
    const context = refreshContext();
    clearTimeout(state.refresh.timer);
    state.refresh.busy = true;
    delete state.errors.refreshStatus;
    renderConnectionBanner();
    updateRefreshControls();
    try {
      const result = await api("/api/workspace/refresh", {
        method: "POST",
        body: {
          expected_public_id: state.user.public_id,
          scope: "quick"
        }
      });
      await adoptRefreshStatus(result, context);
    } catch (error) {
      refreshFailed(error, context);
    } finally {
      if (currentRefresh(context)) {
        state.refresh.busy = false;
        renderConnectionBanner();
        updateRefreshControls();
      }
    }
  };
  const connectionStatusText = (connection, workspace) => {
    if (state.errors.workspace) return humanError(state.errors.workspace);
    const refreshText = workspaceRefreshText();
    if (refreshText) return refreshText;
    if (connection && !connection.connected) return T("Подключите T-Invest, чтобы увидеть стоимость, состав и аналитику своего портфеля.");
    if (connection?.connected && workspace && !workspace.overview?.observed_at) return T("Счёт подключён. Подтверждённое наблюдение пока не получено. Запустите обновление: история начнётся с реальных данных источника.");
    if (connection?.environment === "sandbox") return T("Подключена тестовая среда T-Invest. Эти данные относятся к тестовому счёту.");
    if (workspace?.overview?.status === "stale") return T("Последнее наблюдение устарело. Значения помечены временем получения; обновите данные.");
    if (workspace?.overview?.status === "partial") return T("Получена только часть данных счёта. Некоторые показатели пока не рассчитаны.");
    return "";
  };
  const renderConnectionBanner = () => {
    const banner = $("#connection-banner");
    const ws = state.data.workspace;
    const connection = state.data.connection || ws?.connection;
    if (state.tour || state.locked) {
      banner.hidden = true;
      return;
    }
    const text = connectionStatusText(connection, ws);
    banner.hidden = !text;
    banner.classList.toggle("error", Boolean(state.errors.workspace || state.errors.refreshStatus) || state.data.refreshStatus?.status === "failed");
    banner.innerHTML = text ? `<span>${esc(text)}</span>${button(renderConnectionBannerValue(connection), renderConnectionBannerValue2(connection), {
      small: true,
      extra: renderConnectionBannerValue3(connection)
    })}` : "";
  };
  const portfolioRows = () => {
    if (state.tour) return [];
    const stored = state.data.visualization?.latest?.positions;
    return (Array.isArray(stored) ? stored : []).map(item => ({
      ...item,
      uid: item.instrument_uid,
      name: item.name || item.ticker || item.instrument_uid,
      price: state.quotes[item.instrument_uid]?.last_price ?? null,
      currency: String(item.current_price_currency || item.currency || "").toUpperCase(),
      change: item.daily_change_percent ?? null
    }));
  };
  const filteredRows = () => {
    const matching = portfolioRows().filter(item => state.assetFilter === "all" || (state.assetFilter === "other" ? !["share", "bond", "etf", "currency"].includes(item.instrument_type) : item.instrument_type === state.assetFilter));
    return matching.sort((a, b) => {
      if (state.sort === "name") return state.sortDirection * a.name.localeCompare(b.name, "ru");
      const key = {
        price: "price",
        change: "change",
        share: "nav_percent",
        value: "value_rub"
      }[state.sort];
      const left = number(a[key]);
      const right = number(b[key]);
      if (left === null) return right === null ? 0 : 1;
      if (right === null) return -1;
      return state.sortDirection * (left - right);
    });
  };
  const filtersHTML = (scope = "assets") => `<div class="filters" aria-label="${H("Тип актива")}">${assetTypes().map(([key, title]) => renderFiltersHTMLFilterButton(key, scope, title)).join("")}</div>`;
  const assetsTable = (compact = true) => {
    if (state.tour) return empty(T("Ваши активы будут здесь"), T("Войдите и подключите свой счёт. Цены и доли появятся из источника."), "login", T("Войти"));
    if (state.errors.visualization) return dataError("visualization");
    if (!state.data.visualization && state.loading.has("visualization")) return U.loading(T("quotes.positions_loading"));
    const rows = filteredRows();
    if (!rows.length) return empty(portfolioRows().length ? T("Нет активов этого типа") : T("Активы пока не получены"), portfolioRows().length ? T("Выберите другой фильтр.") : T("Состав счёта появится после подключения и первого наблюдения."), portfolioRows().length ? "" : "connect", T("Подключить счёт"));
    const headers = [["name", T("Название")], ["price", T("Цена")], ["change", T("Изменение")], ["share", T("Доля")]];
    return `<div class="table-scroll"><table class="asset-table${compact ? "" : " full-table"}"><thead><tr>${headers.map(([key, label]) => renderAssetsTableTh(key, label)).join("")}${compact ? "" : ("<th class=\"hide-on-mobile\" scope=\"col\">" + H("Стоимость") + "</th><th scope=\"col\"><span class=\"sr-only\">" + H("Избранное") + "</span></th>")}</tr></thead><tbody>${(compact ? rows.slice(0, 5) : rows).map(item => renderAssetsTableAssetName(item, compact)).join("")}</tbody></table></div><p class="data-footnote">${H("quotes.snapshot_scope")} ${state.data.visualization?.latest?.captured_at ? esc(date(state.data.visualization.latest.captured_at, true)) + " " + H("МСК") : ""}</p>`;
  };
  const selectedPreset = (document = state.strategy.draft) => {
    const id = document?.base_preset_id;
    const catalog = state.data.catalog;
    const current = catalog?.presets?.find(item => item.id === id);
    if (current) return I.preset(current);
    const legacy = catalog?.legacy_presets?.[id];
    return legacy ? I.preset({
      id,
      ...legacy
    }) : undefined;
  };
  const strategyTitle = () => {
    if (state.tour) return T("Выберите стратегию");
    if (state.strategy.draft?.customized) return T("Моя настройка");
    return selectedPreset()?.title || T("Выберите стратегию");
  };
  const strategyEditorTitle = () => {
    const title = selectedPreset()?.title || T("Сохранённые условия");
    if (state.strategy.draft?.customized) return T("Моя настройка · основа: ") + title;
    return T("Готовая стратегия · ") + title;
  };
  const homeStrategy = () => {
    const document = state.tour ? null : state.strategy.draft;
    const horizon = number(document?.profile?.horizon_months);
    return `${cardHeader(T("Моя стратегия"))}<div class="strategy-current">${icon("strategies")}<strong>${esc(strategyTitle())}</strong><button class="icon-button" data-route="strategies" aria-label="${H("Настройки стратегии")}">${icon("settings", true)}</button></div><div class="strategy-chips"><span class="chip">${document ? renderHomeStrategyFragment(document) : T("Ваши условия")}</span><span class="chip">${horizon ? renderHomeStrategyFragment2(horizon) : T("Ваш горизонт")}</span></div><p class="strategy-note">${document ? T("Проверка состава и ограничений на данных вашего счёта.") : T("Выберите подход и уточните личные параметры, чтобы начать расчёты.")}</p><button class="button secondary full" data-route="strategies">${H("Настроить стратегию")} ${icon("arrow", true)}</button>`;
  };
  const eventsPath = () => `/api/events?limit=50&category=${state.eventFilter === "assets" ? "assets" : "all"}${state.eventFilter === "important" ? "&important_only=true" : ""}`;
  const eventItems = () => {
    const news = (state.data.news?.items || []).map(item => ({
      ...item,
      occurred_at: item.published_at,
      news: true,
      read_at: item.published_at,
      severity: "info"
    }));
    const rows = [...(state.tour ? [] : state.data.events?.items || []), ...news].sort((a, b) => (new Date(b.occurred_at).getTime() || 0) - (new Date(a.occurred_at).getTime() || 0));
    if (state.eventFilter === "important") return rows.filter(item => ["warning", "critical", "high"].includes(item.severity));
    if (state.eventFilter === "assets") return rows.filter(item => ["portfolio", "payments"].includes(item.category));
    if (state.eventFilter === "market") return news;
    return rows;
  };
  const eventsHTML = (compact = true) => {
    const rows = eventItems();
    if (state.loading.has("events") && !state.data.events && !state.tour && state.eventFilter !== "market") return U.loading(T("state.loading"));
    if (!rows.length) return empty(state.eventFilter === "market" ? T("Новостной источник не подключён") : T("Нет новых событий"), state.eventFilter === "market" ? T("Система не подставляет заголовки. События счёта появятся после подключения данных.") : T("Подтверждённые события портфеля и целей появятся здесь."), "", "", "events");
    return `<div class="event-list">${(compact ? rows.slice(0, 4) : rows).map(item => renderEventsHTMLEventItem(item, compact)).join("")}</div>`;
  };
  const goalPreview = goal => `<article class="goal-preview"><span class="event-icon">${icon(goal.kind === "income" ? "wallet" : "building", true)}</span><div class="goal-preview-body"><h3>${esc(goal.title)}</h3><p>${esc(money(goal.progress?.amount_rub))} ${H("из")} ${esc(money(goal.target_amount_rub))}</p>${U.progress(goal.progress?.percent)}</div></article>`;
  const homeGoals = () => {
    const goals = (state.tour ? [] : state.data.goals?.items || []).filter(item => item.status === "active");
    return `${cardHeader(T("Цели"), "goals", "")}${goals.length ? renderHomeGoalsGoalsPreviewList(goals) : empty(T("Начните с цели"), T("Укажите сумму и срок. Прогресс рассчитывается по выбранному источнику."), "goal-create", T("Добавить цель"), "goals")}<button class="button secondary full" data-route="goals">${H("Все цели")} ${icon("arrow", true)}</button>`;
  };
  const portfolioHistory = (overview, period) => {
    if (overview.history_coverage?.period !== period) return [];
    return overview.history || [];
  };
  const workspaceForPeriod = period => !state.tour && state.data.workspace?.overview?.history_coverage?.period === period ? state.data.workspace : undefined;
  const navCoverageHTML = (overview, period) => {
    const coverage = overview.history_coverage;
    if (!coverage || coverage.period !== period) return ("<p class=\"data-footnote\">" + H("Покрытие выбранного периода ещё не получено.") + "</p>");
    if (coverage.status === "empty") return ("<p class=\"data-footnote\">" + H("В выбранном периоде нет сохранённых наблюдений.") + "</p>");
    const range = date(coverage.returned_from, true) + " — " + date(coverage.returned_to, true) + T(" МСК");
    const observations = coverage.status === "sampled" ? `${format(coverage.returned_observations, 0)} ${T("из")} ${format(coverage.total_observations, 0)} ${T("реальных наблюдений за период")}` : `${format(coverage.returned_observations, 0)} ${T("реальных наблюдений")}`;
    return `<p class="data-footnote" data-history-period="${esc(period)}">${esc(range)}<br>${esc(observations)}. ${coverage.status === "sampled" ? T("На графике показаны последние точки временных интервалов; расчёты используют полную сохранённую историю.") : T("Глубина истории зависит от сохранённых данных.")}</p>`;
  };
  const renderHome = () => {
    captureScreenDrafts();
    const ws = workspaceForPeriod(state.homePeriod);
    const overview = state.tour ? {} : state.data.workspace?.overview || {};
    const performance = ws?.performance || {};
    const income = ws?.income || {};
    const monthly = Array.isArray(income.by_month) ? income.by_month : [];
    const latestMonth = monthly.at(-1);
    const incomeCurve = monthly.map(item => ({
      ...item,
      time: `${item.month}-01`
    }));
    const history = portfolioHistory(overview, state.homePeriod);
    const result = number(performance.investment_result_rub);
    const resultText = result === null ? T("Полная история для расчёта ещё не получена") : `${money(result)} · ${date(performance.from)} — ${date(performance.to)}`;
    $("#view-home").innerHTML = `<h1 class="sr-only">${H("Главная — обзор портфеля")}</h1><div class="dashboard-top"><section class="card summary-card"><p class="card-label">${H("Общая стоимость")}</p><p class="main-value">${esc(money(overview.nav_rub))}</p>${freshness(T("portfolio.snapshot"), overview.observed_at, overview.freshness?.status || overview.status)}<div class="value-change ${result === null ? "" : renderHomeValue(result)}">${esc(resultText)}</div>${overview.observed_at ? renderHomeDataFootnote(overview) : ""}${chart(history, {
      label: T("Стоимость портфеля"),
      compact: true
    })}${periods("home", state.homePeriod)}${navCoverageHTML(overview, state.homePeriod)}</section><section class="card allocation-card">${cardHeader(T("Структура портфеля"))}${U.allocation(overview.allocations, overview.nav_rub)}</section><div class="metric-stack"><section class="card metric-card"><p class="card-label">${H("Доходность")}</p><p class="main-value">${esc(percent(performance.return_percent, true))}</p><p class="metric-note">${performance.return_percent === null || performance.return_percent === undefined ? T("Недостаточно подтверждённых потоков или положительного вложенного капитала.") : renderHomeFragment(performance)}</p>${result !== null ? renderHomeMetricNote(result) : ""}</section><section class="card metric-card secondary-metric"><p class="card-label">${H("Пассивный доход")}</p><p class="main-value">${esc(money(latestMonth?.total_rub))}</p><p class="metric-note">${latestMonth ? renderHomeFragment3(latestMonth) : T("Выплаты до налоговых списаний: данных пока нет")}</p>${incomeCurve.length > 1 ? chart(incomeCurve, {
      timeKey: "time",
      valueKey: "total_rub",
      label: T("Полученные выплаты по месяцам"),
      tone: "purple",
      compact: true
    }) : ""}</section></div><section class="card strategy-card">${homeStrategy()}</section></div><div class="dashboard-bottom"><section class="card">${cardHeader(T("Мои активы"), "portfolio")}${filtersHTML()}${assetsTable()}<p class="data-footnote">${state.data.visualization?.latest?.captured_at ? renderHomeFragment4() : T("Только данные вашего подключённого счёта")}</p></section><section class="card">${cardHeader(T("Новости и события"), "events", "")}${eventFilters()}${eventsHTML()}</section><section class="card goals-overview">${homeGoals()}</section></div>${!ws && state.loading.has("workspace") ? U.loading(T("Получаем состояние вашего кабинета…")) : ""}`;
    applyScreenLayout("home");
  };
  const eventFilters = () => `<div class="filters" aria-label="${H("Фильтр событий")}">${[["important", T("Важное")], ["assets", T("Мои активы")], ["market", T("Рынок")], ["all", T("Все")]].map(([key, title]) => renderEventFiltersFilterButton(key, title)).join("")}</div>`;
  const renderPortfolio = () => {
    captureScreenDrafts();
    const overview = state.tour ? {} : state.data.workspace?.overview || {};
    const performance = workspaceForPeriod(state.portfolioPeriod)?.performance || {};
    $("#view-portfolio").innerHTML = `${heading(T("Портфель"), !state.tour && state.data.connection?.account_name || T("Стоимость, структура и активы вашего счёта"), button(T("Обновить"), "refresh", {
      small: true
    }) + button(T("Подключение"), "connect", {
      small: true
    }))}<div class="metric-grid">${[[T("Стоимость портфеля"), money(overview.nav_rub)], [T("Свободные средства"), money(overview.free_cash_rub)], [T("Результат за период"), money(performance.investment_result_rub)], [T("Активов"), portfolioRows().length ? String(portfolioRows().length) : "—"]].map(([title, value]) => renderPortfolioCard(title, value)).join("")}</div><div class="two-column"><section class="card">${cardHeader(T("Стоимость портфеля"))}${chart(portfolioHistory(overview, state.portfolioPeriod))}${periods("portfolio", state.portfolioPeriod)}${navCoverageHTML(overview, state.portfolioPeriod)}<p class="data-footnote">${H("График стоимости включает пополнения и выводы. Он не является графиком доходности.")}</p></section><section class="card">${cardHeader(T("Структура портфеля"))}${U.allocation(overview.allocations, overview.nav_rub)}${freshness("T-Invest", overview.observed_at, overview.freshness?.status || overview.status)}</section></div><section class="card section-gap">${cardHeader(T("Мои активы"))}${filtersHTML()}${assetsTable(false)}</section>${dataError("workspace")}`;
    applyScreenLayout("portfolio");
  };
  const newsHTML = () => {
    const rows = state.data.news?.items || [];
    if (state.loading.has("news") && !state.data.news) return U.loading(T("state.loading"));
    if (state.errors.news) return dataError("news");
    if (!rows.length) return empty(T("Новостной источник пока недоступен"), T("Повторите обновление. Заголовки не заменяются примерами."), "", "", "events");
    return `<div class="event-list">${rows.slice(0, 8).map(item => renderNewsHTMLEventItem(item)).join("")}</div>${freshness(T("Официальная лента Банка России"), state.data.news.fetched_at, state.data.news.freshness === "cached" ? "cached" : "")}`;
  };
  const indicatorCards = reference => {
    const data = reference?.indicators;
    return `<div class="market-indicators">${[["key_rate", T("Ключевая ставка"), "%"], ["usd_rub", T("Доллар США"), "₽"], ["eur_rub", T("Евро"), "₽"]].map(([key, title, unit]) => renderIndicatorCardsCard(title, data, key, unit)).join("")}</div>`;
  };
  const watchlist = () => state.tour ? [] : state.prefs.draft?.watchlist || [];
  const isWatched = uid => watchlist().some(item => item.instrument_uid === uid);
  const watchButton = item => `<button class="icon-button" data-watch="${esc(item.uid || item.instrument_uid)}" data-watch-name="${esc(item.name || item.ticker || T("Актив"))}" data-watch-ticker="${esc(item.ticker || "")}" aria-label="${isWatched(item.uid || item.instrument_uid) ? T("Удалить из избранного") : T("Добавить в избранное")}" aria-pressed="${isWatched(item.uid || item.instrument_uid)}">${icon("star", true)}</button>`;
  const renderMarket = () => {
    captureScreenDrafts();
    const reference = state.data.marketReference;
    $("#view-market").innerHTML = `${heading(T("Рынок"), T("Официальные показатели и инструменты из подключённого источника"), button(T("Обновить"), "refresh", {
      small: true
    }))}${indicatorCards(reference)}<div class="two-column section-gap"><section class="card">${cardHeader(T("Курсы Банка России"))}<div class="button-group">${select("cbr_currency", T("Валюта"), [["USD", T("Доллар США")], ["EUR", T("Евро")], ["CNY", T("Китайский юань")]], state.cbrCurrency)}${select("cbr_period", T("Период"), [["1m", T("Месяц")], ["3m", T("Три месяца")], ["1y", T("Год")]], state.cbrPeriod)}</div>${chart(reference?.history?.points, {
      timeKey: "effective_date",
      valueKey: "value",
      label: renderMarketFragment(),
      personal: false
    })}${freshness(T("Банк России · официальный курс"), reference?.history?.fetched_at || reference?.indicators?.fetched_at)}<p class="data-footnote">${H("Официальный справочный курс отличается от биржевой котировки.")}</p></section><section class="card">${cardHeader(T("Избранное"))}${watchlist().length ? renderMarketSearchResults() : empty(T("Сохраните интересные активы"), T("Найдите компанию или тикер через поиск и нажмите звёздочку. Избранное сохраняется в аккаунте."), "", "", "star")}${!state.data.connection?.connected ? renderMarketNotice() : ""}</section></div><section class="card section-gap">${cardHeader(T("Активы вашего счёта"))}${filtersHTML()}${assetsTable(false)}</section>${dataError("marketReference")}<section class="card section-gap">${cardHeader(T("Новости Банка России"))}${newsHTML()}</section>`;
    applyScreenLayout("market");
  };
  const runSearch = async query => {
    const trimmed = String(query).trim().slice(0, 64);
    state.searchQuery = trimmed;
    $("#global-search").value = trimmed;
    const sequence = ++state.searchSequence;
    const generation = state.generation;
    state.searchPages = {events: null, news: null};
    state.searchFailures = {};
    state.searchResults = [];
    if (!trimmed) {
      state.searchResults = [];
      renderSearch();
      return;
    }
    if (state.tour) {
      renderSearch();
      return;
    }
    state.loading.add("search");
    delete state.errors.search;
    renderSearch();
    const requests = [
      ["instruments", `/api/broker/tbank/instruments/search?q=${encodeURIComponent(trimmed)}`],
      ["events", `/api/events?limit=50&query=${encodeURIComponent(trimmed)}`],
      ["news", `/api/news?limit=50&query=${encodeURIComponent(trimmed)}`]
    ];
    const results = await Promise.allSettled(requests.map(([, path]) => api(path)));
    if (sequence !== state.searchSequence || generation !== state.generation || trimmed !== routeSearchQuery()) return;
    results.forEach((result, index) => {
      const name = requests[index][0];
      if (result.status === "fulfilled") {
        if (name === "instruments") state.searchResults = result.value.items || [];
        else state.searchPages[name] = result.value;
      } else if (!isCancelled(result.reason)) state.searchFailures[name] = result.reason;
    });
    state.loading.delete("search");
    if (state.view === "search") renderSearch();
  };
  const mergePage = (previous, incoming) => ({...incoming, items: [...new Map([
    ...(previous?.items || []), ...(incoming?.items || [])
  ].map(item => [item.id, item])).values()]});
  const eventSnapshot = payload => {
    if (!state.eventHistoryExtended || !state.data.events) return payload;
    const combined = mergePage(state.data.events, payload);
    combined.items.sort((left, right) => new Date(right.occurred_at) - new Date(left.occurred_at));
    combined.next_cursor = state.data.events.next_cursor;
    return combined;
  };
  const loadSearchPage = async kind => {
    if (!["events", "news"].includes(kind) || !state.searchPages[kind]?.next_cursor || state.loading.has(`search-${kind}`)) return;
    const generation = state.generation;
    const sequence = state.searchSequence;
    const cursor = state.searchPages[kind].next_cursor;
    state.loading.add(`search-${kind}`);
    renderSearch();
    try {
      const page = await api(`/api/${kind}?limit=50&query=${encodeURIComponent(state.searchQuery)}&cursor=${encodeURIComponent(cursor)}`);
      if (generation !== state.generation || sequence !== state.searchSequence) return;
      state.searchPages[kind] = mergePage(state.searchPages[kind], page);
      delete state.searchFailures[kind];
    } catch (error) {
      if (generation === state.generation && sequence === state.searchSequence && !isCancelled(error)) state.searchFailures[kind] = error;
    } finally {
      if (generation === state.generation && sequence === state.searchSequence) {
        state.loading.delete(`search-${kind}`);
        if (state.view === "search") renderSearch();
      }
    }
  };
  const archiveNewsItem = item => `<article class="event-item"><span class="event-icon">${icon("events", true)}</span><div class="event-item-body"><h3><button class="event-title-button" data-news-open="${esc(item.id)}">${esc(item.title)}</button></h3><p class="fine-print">${esc(item.summary || "")}</p><span class="event-meta">${esc(item.source || T("Источник брокера"))} · ${esc(date(item.occurred_at, true))}</span></div></article>`;
  const searchMatchesHTML = (errors, matches, more) => `${errors}<div class="search-results">${matches || empty(more ? T("В проверенной части совпадений нет") : T("Совпадений не найдено"), more ? T("Продолжите поиск в следующей части архива.") : T("Уточните название или попробуйте биржевой тикер."), "", "", "search")}</div><div class="form-actions">${more}</div><p class="data-footnote">${H("События: серверная история аккаунта. Новости: последовательный просмотр архива источника; сводка ЦБ содержит последние публичные заголовки.")}</p>`;
  const routeSearchQuery = () => String(state.route.q || "").trim().slice(0, 64);
  const renderSearch = () => {
    const selectedQuery = routeSearchQuery();
    const query = selectedQuery.toLocaleLowerCase("ru-RU");
    const localNews = query ? (state.data.news?.items || []).filter(item => `${item.title} ${item.source}`.toLocaleLowerCase("ru-RU").includes(query)) : [];
    const events = state.searchPages.events?.items || [];
    const news = state.searchPages.news?.items || [];
    const errors = Object.entries(state.searchFailures).map(([key, error]) => `<p class="notice error">${esc({instruments: T("Инструменты"), events: T("События"), news: T("Новости")}[key])}: ${esc(humanError(error))}</p>`).join("");
    const more = ["events", "news"].filter(key => state.searchPages[key]?.next_cursor).map(key => button(key === "events" ? T("Ещё события") : T("Проверить следующую часть архива новостей"), `search-more-${key}`, {small: true, extra: state.loading.has(`search-${key}`) ? " disabled" : ""})).join("");
    const matches = `${state.searchResults.map(item => renderSearchSearchResult3(item)).join("")}${events.map(item => renderSearchSearchResult(item)).join("")}${news.map(archiveNewsItem).join("")}${localNews.map(item => renderSearchSearchResult2(item)).join("")}`;
    let content;
    if (state.tour) content = `${empty(T("Полный поиск доступен после входа"), T("История событий ищется на сервере. Инструменты и архив новостей требуют подключённого источника."), "login", T("Войти"), "search", true)}${localNews.map(item => renderSearchSearchResult2(item)).join("")}`;
    else if (state.loading.has("search") || selectedQuery !== state.searchQuery) content = U.loading(T("Ищем в инструментах, событиях и архиве новостей…"));
    else if (!selectedQuery) content = empty(T("Что найдём?"), T("Введите название компании, тикер или слово из события в строке поиска."), "", "", "search", true);
    else content = searchMatchesHTML(errors, matches, more);
    $("#view-search").innerHTML = `${heading(T("Поиск"), selectedQuery ? renderSearchFragment(selectedQuery) : T("Инструменты, компании и события"))}<section class="card">${content}</section>`;
  };
  const loadAsset = async (uid, force = false) => {
    const segment = safeSegment(uid);
    const generation = state.generation;
    const asset = state.asset?.uid === uid ? state.asset : {
      uid,
      name: portfolioRows().find(item => item.uid === uid)?.name || watchlist().find(item => item.instrument_uid === uid)?.name || state.searchResults.find(item => (item.uid || item.instrument_uid) === uid)?.name || T("Инструмент"),
      ticker: portfolioRows().find(item => item.uid === uid)?.ticker || watchlist().find(item => item.instrument_uid === uid)?.ticker || state.searchResults.find(item => (item.uid || item.instrument_uid) === uid)?.ticker || "",
      market: null,
      details: null
    };
    state.asset = asset;
    asset.loading = true;
    asset.error = null;
    renderAsset();
    const requestedPeriod = state.assetPeriod;
    const sequence = (state.resourceVersions.get("asset") || 0) + 1;
    state.resourceVersions.set("asset", sequence);
    const requests = [{
      key: "market",
      promise: api(`/api/market/instruments/${segment}?period=${encodeURIComponent(requestedPeriod)}`)
    }];
    if (!asset.details || force) requests.push({
      key: "details",
      promise: api(`/api/portfolio/instruments/${segment}/visualization?history_limit=365`)
    });
    if (!asset.facts || force) requests.push({
      key: "facts",
      promise: api(`/api/market/instruments/${segment}/facts`)
    });
    if (!asset.news || force) requests.push({
      key: "news",
      promise: api(`/api/news?instrument_uid=${segment}&limit=50`)
    });
    const current = () => generation === state.generation && state.resourceVersions.get("asset") === sequence && state.asset?.uid === uid && state.assetPeriod === requestedPeriod;
    await Promise.allSettled(requests.map(async ({key, promise}) => {
      try {
        const value = await promise;
        if (!current()) return;
        asset[key] = value;
        asset[`${key}Error`] = null;
      } catch (error) {
        if (!current() || isCancelled(error)) return;
        asset[`${key}Error`] = error;
        if (key === "market") asset.error = error;
      } finally {
        if (current() && state.view === "asset") {
          if (key === "market") asset.loading = false;
          renderAsset();
          U.bindCharts($("#view-asset"));
          if (key === "market" && asset.market) startQuoteStream();
        }
      }
    }));
    if (!current()) return;
    asset.name = asset.facts?.name || asset.details?.latest?.name || asset.name;
    asset.ticker = asset.facts?.ticker || asset.details?.latest?.ticker || asset.ticker;
    asset.loading = false;
    if (state.view === "asset") {
      renderAsset();
      U.bindCharts($("#view-asset"));
      quoteFailures = 0;
      startQuoteStream();
    }
  };
  const fundamentalMetricsHTML = (asset, compact = false) => {
    const facts = asset.facts;
    if (!facts) return asset.factsError ? `<div class="notice error">${H("Финансовые показатели не загрузились.")} ${esc(humanError(asset.factsError))}${button(T("Повторить"), "asset-refresh", {
      small: true
    })}</div>` : U.loading(T("Получаем подтверждённые показатели…"));
    const metrics = (facts.metrics || []).filter(item => number(item.value) !== null);
    return `<h3 class="panel-title">${H("Финансовые показатели")}</h3>${metrics.length ? renderFundamentalMetricsHTMLInfoList(metrics, compact) : ("<p class=\"notice\">" + H("Источник не предоставил подтверждённые финансовые показатели этого инструмента.") + "</p>")}${freshness(T("Финансовые данные T-Invest"), facts.observed_at)}${!compact && facts.metrics?.length ? renderFundamentalMetricsHTMLSourceList(facts) : ""}${!compact && facts.missing_requirements?.length ? renderFundamentalMetricsHTMLDetailsSummary(facts) : ""}${!compact && facts.limitations?.length ? renderFundamentalMetricsHTMLFinePrint(facts) : ""}`;
  };
  const assetPricing = asset => {
    const market = asset.market;
    const details = asset.details;
    const latest = details?.latest || {};
    const holding = details?.current_holding;
    let position = {};
    if (holding?.status === "held") position = latest;
    else if (holding?.status === "not_held") position = {quantity: "0", value_rub: "0", nav_percent: "0", blocked_lots: "0"};
    const candles = Array.isArray(market?.candles) ? market.candles : [];
    const current = number(market?.last_price);
    const initial = number(candles[0]?.open);
    const change = current !== null && initial !== null && initial !== 0 ? current - initial : null;
    const changePercent = change !== null ? change / initial * 100 : null;
    const currency = String(market?.price_currency || "").toUpperCase();
    const priceUnit = market?.price_unit || "unknown";
    const highs = candles.map(item => number(item.high)).filter(item => item !== null);
    const lows = candles.map(item => number(item.low)).filter(item => item !== null);
    return {
      asset,
      market,
      details,
      latest,
      holding,
      position,
      candles,
      current,
      change,
      changePercent,
      priceUnit,
      currency,
      high: highs.length ? Math.max(...highs) : null,
      low: lows.length ? Math.min(...lows) : null
    };
  };
  const assetQuoteHTML = ({market, current, change, changePercent, priceUnit, currency}) => {
    const changeLabel = change === null ? T("Изменение за период не рассчитано") : `${esc(marketPrice(change, priceUnit, currency))} · ${esc(percent(changePercent, true))}`;
    const cashPrice = market?.cash_price && priceUnit !== "currency" ? `<p class="fine-print">${H("Текущая чистая цена:")} ${esc(money(market.cash_price, 2, market.cash_price_currency, false))}</p>` : "";
    return `<div class="main-value">${esc(marketPrice(current, priceUnit, currency))}</div>${cashPrice}<p class="value-change ${change === null ? "" : renderAssetValue(change)}">${changeLabel}</p>`;
  };
  const assetChartMarkup = (context) => {
    const {asset, market, candles, priceUnit, currency} = context;
    if (asset.loading) return U.loading(T("Загружаем биржевой график…"));
    if (market?.history_status === "unavailable") return `<div class="notice error">${H("market.history_unavailable")}${button(T("Повторить"), "asset-refresh", {small: true})}</div>`;
    return chart(candles, {
      timeKey: "time",
      valueKey: "close",
      label: renderAssetFragment2(asset),
      personal: false,
      priceUnit,
      currency
    });
  };
  const assetChartHTML = (context) => {
    const {market, priceUnit} = context;
    const chartMarkup = assetChartMarkup(context);
    const notes = [priceUnit === "unknown" ? T("Источник не подтвердил единицы цены.") : "", priceUnit === "percent_nominal" ? T("Цена и история — в процентах номинала, без НКД. Текущий номинал не применяется к старым свечам.") : "", priceUnit === "points" ? T("Котировки в пунктах. Денежная стоимость шага может меняться.") : "", market?.trading_status ? renderAssetFragment3(market) : "", state.assetPeriod === "all" ? T("Доступная история источника.") : "", esc(market?.history_note || ""), T("График показывает цены закрытия свечей.")].filter(Boolean).join(" ");
    return `<div data-market-quote>${assetQuoteHTML(context)}</div>${periods("asset", state.assetPeriod, true)}${chartMarkup}<div data-market-source>${freshness(market?.source || "T-Invest", market?.quote_time || market?.observed_at, market?.quote_status)}</div><p class="data-footnote">${notes}</p>`;
  };
  const assetHoldingNote = ({
    asset,
    details,
    latest
  }) => {
    if (details?.current_holding?.status === "not_held") return `<p class="notice">${H("asset.not_held")}</p>${freshness("T-Invest", details.current_holding.observed_at)}`;
    if (details?.current_holding?.status === "held") return renderAssetDataFootnote({...latest, captured_at: details.current_holding.observed_at || latest.captured_at});
    if (details) return `<p class="notice">${H("asset.holding_unknown")}</p>${renderAssetDataFootnote(latest)}`;
    if (asset.detailsError && asset.detailsError.status !== 404) return `<p class="notice error">${H("Данные позиции не загрузились:")} ${esc(humanError(asset.detailsError))}</p>`;
    if (asset.loading) return U.loading(T("Проверяем состав вашего счёта…"));
    return ("<p class=\"notice\">" + H("Инструмент не найден в истории вашего счёта. Биржевой график доступен независимо от наличия позиции.") + "</p>");
  };
  const assetOverviewHTML = context => {
    const {
      asset,
      latest,
      position
    } = context;
    const type = {
      share: T("Акция"),
      bond: T("Облигация"),
      etf: T("Фонд"),
      currency: T("Валюта")
    }[asset.facts?.instrument_type || latest.instrument_type] || T("Не получен");
    return `${infoRows([[T("Название"), asset.name], [T("Тикер"), asset.ticker || "—"], [T("Тип"), type], [T("Биржа"), asset.facts?.exchange || "—"], [T("Размер лота"), format(asset.facts?.lot, 0)], [T("В портфеле"), money(position.value_rub)], [T("Доля"), percent(position.nav_percent)], [T("Количество"), format(position.quantity, 8)]])}${assetHoldingNote(context)}`;
  };
  const assetMetricsHTML = ({
    asset,
    market,
    candles,
    current,
    priceUnit,
    currency,
    high,
    low
  }) => {
    const quoteTime = market?.quote_time ? renderAssetFragment4(market) : "—";
    const rows = [[T("Открытие периода"), marketPrice(candles[0]?.open, priceUnit, currency)], [T("Максимум периода"), marketPrice(high, priceUnit, currency)], [T("Минимум периода"), marketPrice(low, priceUnit, currency)], [T("Последняя цена"), marketPrice(current, priceUnit, currency)], [T("Время цены"), quoteTime], [T("Свечей в периоде"), candles.length ? String(candles.length) : "—"], [T("Режим торгов"), tradingLabel(market?.trading_status)]];
    return `${infoRows(rows)}<p class="data-footnote">${H("Ценовые показатели рассчитаны только по полученным свечам выбранного периода.")}</p><div class="section-gap">${fundamentalMetricsHTML(asset)}</div>`;
  };
  const assetNewsArchiveHTML = asset => {
    if (asset.newsError) return `<p class="notice error">${esc(humanError(asset.newsError))}</p>${button(T("Повторить"), "asset-refresh", {small: true})}`;
    if (!asset.news) return U.loading(T("Проверяем новости инструмента…"));
    const items = (asset.news.items || []).map(archiveNewsItem).join("") || ("<p class=\"notice\">" + H("В проверенной части архива нет публикаций об этом инструменте.") + "</p>");
    const next = asset.news.next_cursor ? button(T("Следующая часть архива"), "asset-news-more", {small: true, extra: state.loading.has("asset-news-more") ? " disabled" : ""}) : ("<p class=\"data-footnote\">" + H("Достигнут конец доступного архива источника.") + "</p>");
    return `<div class="event-list">${items}</div>${next}${freshness(asset.news.source || T("Источник брокера"), asset.news.observed_at)}`;
  };
  const assetNewsHTML = ({asset, details}) => `${details?.sources?.length ? renderAssetDetailsSummary(details) : ""}<h3 class="panel-title section-gap">${H("Новости инструмента")}</h3>${assetNewsArchiveHTML(asset)}<details class="section-gap"><summary class="details-summary">${H("Общерыночные новости Банка России")}</summary><p class="fine-print">${H("Отдельная общая лента, без привязки к эмитенту.")}</p>${newsHTML()}</details>`;
  const loadAssetNewsPage = async () => {
    const asset = state.asset;
    if (!asset?.news?.next_cursor || state.loading.has("asset-news-more")) return;
    const generation = state.generation;
    const uid = asset.uid;
    state.loading.add("asset-news-more");
    renderAsset();
    try {
      const page = await api(`/api/news?instrument_uid=${safeSegment(uid)}&limit=50&cursor=${encodeURIComponent(asset.news.next_cursor)}`);
      if (generation !== state.generation || state.asset?.uid !== uid) return;
      asset.news = mergePage(asset.news, page);
      asset.newsError = null;
    } catch (error) {
      if (generation === state.generation && state.asset?.uid === uid && !isCancelled(error)) asset.newsError = error;
    } finally {
      if (generation === state.generation && state.asset?.uid === uid) {
        state.loading.delete("asset-news-more");
        if (state.view === "asset") renderAsset();
      }
    }
  };
  const assetSideHTML = ({
    asset,
    latest,
    position,
    candles,
    priceUnit,
    currency,
    high,
    details
  }) => {
    const rows = [[T("Открытие"), marketPrice(candles[0]?.open, priceUnit, currency)], [T("Максимум"), marketPrice(high, priceUnit, currency)], [T("Стоимость в портфеле"), money(position.value_rub)], [T("Доля портфеля"), percent(position.nav_percent)], [T("Заблокировано лотов"), position.blocked_lots === undefined ? "—" : format(position.blocked_lots)]];
    const risk = position.risk_state ? riskLabel(position.risk_state) : T("Для оценки риска нужны данные об эмитенте и инструменте.");
    return `${cardHeader(T("Основные показатели"))}${infoRows(rows)}<p class="notice">${esc(risk)}</p><div class="section-gap">${fundamentalMetricsHTML(asset, true)}</div>${details?.payouts?.length ? renderAssetDetailsSummary2(details) : ""}`;
  };
  const assetFrameHTML = (context, content) => {
    const {
      asset
    } = context;
    const tabs = [["overview", T("Обзор")], ["chart", T("График")], ["metrics", T("Показатели")], ["news", T("Новости")]].map(([key, label]) => renderAssetTabButton(key, label)).join("");
    return `<div class="breadcrumb"><button class="icon-button" data-action="asset-back" aria-label="${H("Назад к рынку")}">${icon("back")}</button><span>${H("График актива")}</span></div><div class="asset-detail-header"><span class="asset-logo">${esc((asset.ticker || asset.name).slice(0, 1))}</span><div><h1>${esc(asset.name)}</h1><p>${esc(asset.ticker || T("Инструмент T-Invest"))}</p></div>${watchButton(asset)}</div><div class="asset-detail-layout"><section class="card asset-chart-card"><div class="tab-bar" role="tablist" aria-label="${H("Карточка актива")}">${tabs}</div><div class="asset-tab-content" role="tabpanel">${asset.error ? renderAssetNotice(asset) : ""}${content}</div></section><section class="card">${assetSideHTML(context)}</section></div>`;
  };
  const renderAsset = () => {
    if (!state.route.uid) { $("#view-asset").innerHTML = `${heading(T("Актив"))}<section class="card">${empty(T("Некорректный инструмент"), T("Откройте актив из портфеля или результатов поиска."), "asset-back", T("navigation.back"), "info", true)}</section>`; return; }
    const container = $("#view-asset");
    if (state.tour) {
      container.innerHTML = empty(T("Карточка инструмента"), T("Войдите и подключите источник, чтобы получить цену, историю и финансовые показатели."), "login", T("Войти"), "market", true);
      return;
    }
    const asset = state.asset;
    if (!asset || asset.uid !== state.route.uid) {
      container.innerHTML = U.loading(T("Получаем данные актива…"));
      return;
    }
    const context = assetPricing(asset);
    const renderers = {
      chart: assetChartHTML,
      overview: assetOverviewHTML,
      metrics: assetMetricsHTML,
      news: assetNewsHTML
    };
    const renderer = renderers[state.assetTab] || assetChartHTML;
    container.innerHTML = assetFrameHTML(context, renderer(context));
  };
  const tradingLabel = value => ({
    SECURITY_TRADING_STATUS_NORMAL_TRADING: T("Основная сессия"),
    SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING: T("Торги недоступны"),
    SECURITY_TRADING_STATUS_CLOSING_PERIOD: T("Закрытие сессии"),
    SECURITY_TRADING_STATUS_BREAK_IN_TRADING: T("Перерыв в торгах"),
    SECURITY_TRADING_STATUS_OPENING_AUCTION_PERIOD: T("Аукцион открытия"),
    SECURITY_TRADING_STATUS_CLOSING_AUCTION: T("Аукцион закрытия")
  })[value] || (value ? T("Режим получен от биржи") : T("Нет данных"));
  const riskLabel = value => ({
    data_missing: T("Недостаточно данных для полной оценки риска."),
    restricted: T("Для инструмента действуют ограничения. Проверьте условия доступа."),
    observed: T("Показаны фактические данные инструмента."),
    review_required: T("Требуется дополнительная проверка данных.")
  })[value] || T("Оценка требует проверки исходных данных.");
  const validRecord = record => record && Number.isInteger(record.version) && record.version >= 0 && record.document && typeof record.document === "object";
  const editablePreferenceForms = new Set(["preferences-form", "profile-form"]);
  const hasFormDrafts = () => Object.keys(state.formDrafts).length > 0;
  const formValues = form => Object.fromEntries(Array.from(form.elements).filter(input => input.name).map(input => [input.name, input.type === "checkbox" ? input.checked : input.value]));
  const restoreEditableForm = formId => {
    const form = $("#" + formId);
    if (!form) return;
    state.formBaselines[formId] = formValues(form);
    const values = state.formDrafts[formId];
    if (!values) return;
    for (const [name, value] of Object.entries(values)) {
      const input = form.elements.namedItem(name);
      if (!input) continue;
      if (input.type === "checkbox") input.checked = value;else input.value = value;
    }
  };
  const captureFormDraft = input => {
    const form = input.closest("form");
    if (!form || !editablePreferenceForms.has(form.id) || !state.prefs.server) return false;
    const values = formValues(form);
    if (same(values, state.formBaselines[form.id])) delete state.formDrafts[form.id];else state.formDrafts[form.id] = values;
    updateSaveStatus("prefs");
    return true;
  };
  const acceptFormSubmission = form => {
    state.formBaselines[form.id] = formValues(form);
    delete state.formDrafts[form.id];
    updateSaveStatus("prefs");
  };
  function adoptPreferences(payload) {
    if (!validRecord(payload)) return;
    const slot = state.prefs;
    if (slot.dirty || slot.busy || hasFormDrafts() || slot.server && slot.server.version > payload.version) return;
    slot.server = clone(payload);
    slot.draft = clone(payload.document);
    slot.error = null;
    if (state.pendingTheme && state.user && !state.tour) {
      const choice = state.pendingTheme;
      state.pendingTheme = null;
      editPreferences(document => {
        document.theme = choice;
      });
    }
    applySavedEffects("prefs");
  }
  function adoptStrategy(payload) {
    const selection = payload?.selection;
    const slot = state.strategy;
    if (slot.dirty || slot.busy) return;
    if (selection !== null && selection !== undefined && !validRecord(selection)) return;
    if (slot.server && (selection?.version || 0) < slot.server.version) return;
    slot.server = selection ? clone(selection) : null;
    slot.draft = selection ? clone(selection.document) : null;
    slot.error = null;
  }
  const strategySaveUnavailable = slot => !slot.server || slot.dirty || slot.busy || Boolean(slot.error);
  const updateStrategySaveControls = slot => {
    const unavailable = strategySaveUnavailable(slot);
    const assess = $('[data-action="assess-strategy"]');
    if (assess) assess.disabled = unavailable || state.loading.has("assessment");
    const research = $('#research-form [type="submit"]');
    if (research) research.disabled = unavailable || researchUnavailable();
    for (const input of $$("#research-form input")) input.disabled = researchPending();
    const planner = $('#view-strategies [data-action="execution-plan"]');
    if (planner) planner.disabled = unavailable || state.executionBusy;
    const title = $(".strategy-heading h2");
    if (title) title.textContent = strategyEditorTitle();
    for (const option of $$("[data-select-strategy]")) option.setAttribute("aria-pressed", String(!slot.draft?.customized && option.dataset.selectStrategy === slot.draft?.base_preset_id));
    updateCustomStrategyControls();
  };
  const updateSaveStatus = kind => {
    const slot = state[kind];
    const status = slot.error ? renderUpdateSaveStatusValue(slot) : renderUpdateSaveStatusValue4(slot);
    const text = {
      conflict: T("Конфликт версий"),
      error: T("Изменения не подтверждены"),
      saving: T("Сохраняем…"),
      pending: T("Есть несохранённые изменения"),
      saved: T("Сохранено на сервере"),
      empty: T("Пока не сохранено")
    }[status];
    for (const element of $$(`[data-save-status="${kind}"]`)) {
      const formId = element.closest("form")?.id;
      const unsubmitted = kind === "prefs" && Boolean(state.formDrafts[formId]);
      element.dataset.state = unsubmitted && !slot.error ? "pending" : status;
      element.textContent = unsubmitted && !slot.error ? T("Изменения формы не отправлены") : text;
    }
    if (kind === "strategy") updateStrategySaveControls(slot);
    for (const element of $$(`[data-save-error="${kind}"]`)) {
      element.hidden = !slot.error;
      element.innerHTML = slot.error ? `<p>${esc(humanError(slot.error))}</p><div class="button-group">${button(T("Загрузить сохранённое"), renderUpdateSaveStatusFragment(kind), {
        small: true
      })}${renderUpdateSaveStatusValue5(slot, kind)}</div>` : "";
    }
  };
  const applySavedEffects = kind => {
    if (kind === "prefs") {
      const previousLocale = I.getLocale();
      U.setPrivacy(Boolean(state.prefs.draft?.mask_balances));
      U.setLocale?.(state.prefs.draft?.locale);
      applyTheme(state.prefs.draft?.theme);
      updateIdentity();
      if (previousLocale !== I.getLocale()) {
        I.apply(document);
        updateLanguageControls();
        renderNav();
        renderAuthConfig();
        if (state.data.catalog) renderPublicCatalog(state.data.catalog);
        document.title = `${U.navigation.find(([key]) => key === state.view)?.[1] || T("Поиск")} · OMNICIO`;
        renderCurrent();
      }
    }
    updateSaveStatus(kind);
  };
  const writePayload = (kind, version, document, intent) => kind === "strategy" ? {
    expected_public_id: state.user.public_id,
    expected_version: version,
    intent,
    document
  } : {
    expected_version: version,
    document
  };
  const recordFrom = (kind, payload) => kind === "strategy" ? payload?.selection : payload;
  const acceptWrite = (kind, slot, saved, revision) => {
    if (!validRecord(saved)) throw Object.assign(new Error("invalid_server_response"), {
      status: 502
    });
    slot.server = clone(saved);
    if (slot.revision === revision) {
      slot.draft = clone(saved.document);
      slot.dirty = false;
    }
    slot.error = null;
    if (kind === "prefs" && slot.revision === revision) for (const id of ["profile-form", "preferences-form"]) if ($( "#" + id)) clearScreenDraft($("#" + id));
    applySavedEffects(kind);
  };
  const currentWrite = context => context.generation === state.generation && state[context.kind] === context.slot;
  const reconcileVersionedWrite = async context => {
    try {
      const payload = await api(context.path);
      if (!currentWrite(context)) return;
      const actual = recordFrom(context.kind, payload);
      if (!validRecord(actual) || actual.version <= context.expected) return;
      if (same(actual.document, context.document)) acceptWrite(context.kind, context.slot, actual, context.revision);else context.slot.error = Object.assign(new Error("settings_version_conflict"), {
        status: 409
      });
    } catch (error) {
      if (isCancelled(error)) return;
    }
  };
  const attemptVersionedWrite = async context => {
    const {
      kind,
      slot,
      path
    } = context;
    const attempt = {
      ...context,
      revision: slot.revision,
      document: clone(slot.draft),
      expected: slot.server?.version || 0
    };
    try {
      const result = await api(path, {
        method: "PUT",
        body: writePayload(kind, attempt.expected, attempt.document, slot.intent || "edit")
      });
      if (!currentWrite(context)) return false;
      const saved = recordFrom(kind, result);
      if (!validRecord(saved) || saved.version <= attempt.expected) throw Object.assign(new Error("invalid_server_response"), {
        status: 502
      });
      acceptWrite(kind, slot, saved, attempt.revision);
    } catch (error) {
      if (!currentWrite(context) || isCancelled(error)) return false;
      slot.error = error;
      if (!error.definite && (!error.status || error.status >= 500)) await reconcileVersionedWrite(attempt);
    }
    return !slot.error;
  };
  const canSaveVersioned = (kind, slot) => {
    if (slot.busy || !slot.dirty || slot.error || !slot.draft || !state.user || state.locked) return false;
    if (kind === "prefs" && !slot.server) return false;
    const activeForm = kind === "strategy" ? $("#strategy-form") : null;
    if (activeForm && !activeForm.checkValidity()) {
      slot.error = Object.assign(new Error("invalid_values"), {
        status: 422
      });
      updateSaveStatus(kind);
      return false;
    }
    return true;
  };
  const finishVersionedSave = context => {
    if (!currentWrite(context)) return;
    const {
      slot,
      kind
    } = context;
    slot.busy = false;
    updateSaveStatus(kind);
    if (slot.error && kind === "prefs" && !["profile", "settings"].includes(state.view)) toast(`${T("Настройки не сохранены:")} ${humanError(slot.error)} ${T("Откройте Настройки, чтобы проверить серверную версию.")}`, true);
  };
  const saveVersioned = async kind => {
    const slot = state[kind];
    if (!canSaveVersioned(kind, slot)) return;
    const context = {
      kind,
      slot,
      generation: state.generation,
      path: kind === "strategy" ? "/api/profile/strategy" : "/api/preferences"
    };
    slot.busy = true;
    updateSaveStatus(kind);
    try {
      while (slot.dirty && !slot.error && currentWrite(context)) {
        if (!(await attemptVersionedWrite(context))) break;
      }
    } finally {
      finishVersionedSave(context);
    }
  };
  const scheduleSave = kind => {
    const slot = state[kind];
    clearTimeout(slot.timer);
    updateSaveStatus(kind);
    slot.timer = window.setTimeout(() => {
      void saveVersioned(kind);
    }, 600);
  };
  const editPreferences = change => {
    if (!requireUser()) return false;
    if (!state.prefs.server || !state.prefs.draft) {
      toast(T("Сначала загрузите настройки с сервера. Начальные значения не будут сохранены поверх неизвестных данных."), true);
      return false;
    }
    if (state.prefs.error?.status === 409) {
      toast(humanError(state.prefs.error), true);
      return false;
    }
    const draft = clone(state.prefs.draft);
    change(draft);
    if (same(draft, state.prefs.draft)) return true;
    state.prefs.draft = draft;
    state.prefs.revision += 1;
    state.prefs.dirty = true;
    state.prefs.error = null;
    applySavedEffects("prefs");
    scheduleSave("prefs");
    return true;
  };
  const reloadVersioned = async (kind, discard = false) => {
    const slot = state[kind];
    if (slot.busy) {
      toast(T("Дождитесь завершения отправленного изменения."));
      return;
    }
    if ((slot.dirty || kind === "prefs" && hasFormDrafts()) && !discard) {
      openDialog(T("Загрузить сохранённые данные?"), `<p class="help-copy">${H("Правки этой вкладки будут заменены текущей серверной версией.")}</p><div class="form-actions">${button(T("Загрузить с сервера"), renderReloadVersionedFragment(kind), {
        primary: true
      })}<button class="button secondary" data-close-dialog>${H("Отмена")}</button></div>`);
      return;
    }
    try {
      const generation = state.generation;
      const payload = await api(kind === "strategy" ? "/api/profile/strategy" : "/api/preferences");
      if (generation !== state.generation) return;
      if (kind === "prefs" && !validRecord(payload)) throw Object.assign(new Error("invalid_server_response"), {
        status: 502
      });
      slot.dirty = false;
      slot.error = null;
      slot.revision += 1;
      if (kind === "strategy") {
        adoptStrategy(payload);
        state.data.strategy = payload;
        slot.assessment = null;
        slot.research = null;
      } else {
        state.formDrafts = {};
        state.formBaselines = {};
        adoptPreferences(payload);
      }
      renderCurrent();
    } catch (error) {
      if (!isCancelled(error)) toast(humanError(error), true);
    }
  };
  const retryVersioned = async kind => {
    const slot = state[kind];
    if (slot.busy || !slot.draft) return;
    try {
      const generation = state.generation;
      const payload = await api(kind === "strategy" ? "/api/profile/strategy" : "/api/preferences");
      if (generation !== state.generation) return;
      const actual = recordFrom(kind, payload);
      if ((actual?.version || 0) !== (slot.server?.version || 0)) {
        if (validRecord(actual) && same(actual.document, slot.draft)) {
          acceptWrite(kind, slot, actual, slot.revision);
          return;
        }
        slot.error = Object.assign(new Error("settings_version_conflict"), {
          status: 409
        });
        updateSaveStatus(kind);
        return;
      }
      slot.error = null;
      await saveVersioned(kind);
    } catch (error) {
      if (!isCancelled(error)) {
        slot.error = error;
        updateSaveStatus(kind);
      }
    }
  };
  const saveErrorHTML = kind => `<div class="notice error" data-save-error="${kind}"${state[kind].error ? "" : " hidden"}></div>`;
  const preservePersonal = document => {
    const current = state.strategy.draft;
    const profile = current ? current.profile : state.data.investmentProfile?.profile;
    const policy = current ? current.policy : state.data.balancingPolicy?.policy;
    for (const key of ["reserve_rub", "planned_withdrawal_rub"]) document.profile[key] = profile?.[key] ?? null;
    document.policy.securities_tax_rate_percent = policy?.securities_tax_rate_percent ?? null;
    return document;
  };
  const chooseStrategy = id => {
    if (!requireUser()) return;
    if (state.loading.has("strategy") || state.loading.has("investmentProfile") || state.loading.has("balancingPolicy") || state.errors.strategy || state.errors.investmentProfile || state.errors.balancingPolicy || !Object.hasOwn(state.data, "strategy")) {
      toast(T("Сначала должны загрузиться сохранённая стратегия и личные условия. Повторите загрузку."), true);
      return;
    }
    if (state.strategy.error?.status === 409) {
      toast(humanError(state.strategy.error), true);
      return;
    }
    const preset = state.data.catalog?.presets?.find(item => item.id === id);
    if (!preset) return;
    const document = preservePersonal(clone(preset.document));
    if (same(document, state.strategy.draft)) return;
    const slot = state.strategy;
    slot.draft = document;
    slot.dirty = true;
    slot.intent = "select";
    slot.revision += 1;
    slot.error = null;
    slot.assessment = null;
    slot.research = null;
    renderStrategies();
    scheduleSave("strategy");
  };
  const customizeStrategy = () => {
    if (!requireUser()) return;
    if (customStrategyStatus().disabled) return;
    const slot = state.strategy;
    const custom = slot.server?.custom_document || slot.draft;
    slot.draft = preservePersonal(clone(custom));
    slot.draft.customized = true;
    slot.intent = "edit";
    slot.revision += 1;
    slot.dirty = true;
    slot.error = null;
    slot.assessment = null;
    slot.research = null;
    renderStrategies();
    scheduleSave("strategy");
  };
  const setStrategyPane = pane => {
    if (!["catalog", "custom"].includes(pane)) return;
    state.strategyPane = pane;
    updateViewRoute({strategy_pane: pane});
    for (const value of ["catalog", "custom"]) {
      const selected = value === pane;
      const tab = $("#strategy-tab-" + value);
      const panel = $("#strategy-panel-" + value);
      if (tab) {
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
      }
      if (panel) panel.hidden = !selected;
    }
  };
  const customStrategyStatus = () => {
    const slot = state.strategy;
    const saved = slot.server?.custom_document;
    const label = saved ? T("Применить мою настройку") : T("Создать из текущей");
    const blocked = detail => ({
      label,
      detail,
      disabled: true
    });
    if (!state.user || state.tour || state.locked) return blocked(T("Войдите в личный аккаунт, чтобы сохранять и применять свою настройку."));
    const resources = ["strategy", "investmentProfile", "balancingPolicy"];
    if (resources.some(key => state.loading.has(key))) return blocked(T("Получаем сохранённую стратегию и личные условия…"));
    if (resources.some(key => state.errors[key]) || !Object.hasOwn(state.data, "strategy")) return blocked(T("Сохранённые условия не загружены. Повторите загрузку перед применением настройки."));
    if (slot.error) return blocked(T("Применение остановлено: ") + humanError(slot.error));
    if (slot.busy || slot.dirty) return blocked(T("Дождитесь подтверждения текущих изменений перед применением другой настройки."));
    if (!slot.draft) return blocked(T("Сначала выберите готовую стратегию: из неё можно создать личную настройку."));
    if (!saved) return {
      label,
      disabled: false,
      detail: T("Отдельная личная настройка ещё не сохранена. Создайте её из текущей стратегии, затем измените параметры в редакторе.")
    };
    const base = selectedPreset(saved)?.title || T("сохранённые условия");
    const current = preservePersonal(clone(saved));
    current.customized = true;
    if (same(current, slot.draft)) return {
      label: T("Уже применяется"),
      disabled: true,
      detail: T("Сохранённая личная настройка уже применяется. Основа: «") + base + T("». Её параметры доступны в редакторе.")
    };
    return {
      label,
      disabled: false,
      detail: T("Личная настройка сохранена на сервере. Основа: «") + base + T("». Применение сделает её текущей стратегией и сохранит ваши актуальные личные суммы.")
    };
  };
  const updateCustomStrategyControls = () => {
    const status = customStrategyStatus();
    const text = $("#strategy-custom-status");
    const control = $('[data-action="strategy-apply-custom"]');
    if (text) text.textContent = status.detail;
    if (control) {
      control.disabled = status.disabled;
      control.textContent = status.label;
    }
  };
  const strategyTabsHTML = () => {
    const tabs = [["catalog", T("Готовые стратегии")], ["custom", T("Моя настройка")]];
    return ("<div class=\"tab-bar\" role=\"tablist\" aria-label=\"" + H("Источник стратегии") + "\">") + tabs.map(([key, label]) => {
      const selected = state.strategyPane === key;
      return `<button type="button" id="strategy-tab-${key}" class="tab-button" role="tab" data-action="strategy-${key}" aria-controls="strategy-panel-${key}" aria-selected="${selected}" tabindex="${selected ? 0 : -1}">${label}</button>`;
    }).join("") + "</div>";
  };
  const policyFields = () => ([["max_instrument_percent", T("Один инструмент"), "%", 100, T("Максимальная доля одного инструмента. Превышение отмечается в проверке состава; это не предел убытка.")], ["max_sector_percent", T("Один сектор"), "%", 100, T("Ограничение концентрации в одном секторе. Нужны данные о секторе каждого инструмента.")], ["max_issuer_percent", T("Один эмитент"), "%", 100, T("Суммарная доля бумаг одного эмитента. Малый лимит требует большего числа доступных инструментов.")], ["max_group_percent", T("Одна группа компаний"), "%", 100, T("Доля связанных эмитентов. Без подтверждённых связей полная проверка невозможна.")], ["max_share_percent", T("Акции — предел"), "%", 100, T("Верхняя граница доли акций. Целевые доли задаются отдельно в распределении.")], ["max_bond_percent", T("Облигации — предел"), "%", 100, T("Верхняя граница доли облигаций. Кредитный и процентный риски сохраняются.")], ["max_etf_percent", T("Фонды — предел"), "%", 100, T("Верхняя граница доли фондов. Состав фонда проверяется отдельно при наличии данных.")], ["max_below_grade_percent", T("Ниже инвест. уровня"), "%", 100, T("Максимальная доля бумаг ниже выбранного рейтингового уровня. Рейтинг не является вероятностью прибыли.")], ["max_unknown_percent", T("Неизвестные данные"), "%", 100, T("Допустимая доля инструментов с неполной классификацией. Неизвестное не означает безопасное.")], ["max_term_months", T("Срок инструментов"), T("мес."), 1200, T("Предельный срок до погашения в условиях модели. Для проверки нужна дата погашения.")], ["turnover_budget_percent", T("Оборот портфеля"), "%", 100, T("Предел оборота в расчётном предложении. Сам по себе не включает исполнение сделок.")], ["max_daily_turnover_participation_percent", T("Участие в обороте"), "%", 100, T("Ограничение доли заявки в наблюдаемом дневном обороте. Требует данных ликвидности.")], ["securities_tax_rate_percent", T("Личная налоговая ставка"), "%", 100, T("Укажите ставку, применимую к вашей ситуации. Неизвестная ставка остаётся пустой и не заменяется предположением.")], ["uncertainty_haircut_percent", T("Запас на неопределённость"), "%", 100, T("Заданный запас в модели, а не статистически доказанная вероятность или гарантия.")], ["credit_loss_haircut_percent", T("Запас на кредитный риск"), "%", 100, T("Пользовательский параметр допустимого сценария потерь. Без данных эмитента это не прогноз дефолта.")], ["no_trade_band_percent", T("Порог отклонения долей"), "%", 100, T("Небольшие отклонения можно не перестраивать. Увеличение порога уменьшает частоту расчётной ребалансировки.")], ["min_replace_benefit_rub", T("Минимальный эффект замены"), "₽", 1000000000000, T("Минимальный расчётный эффект после заданных затрат. Сохранение значения не создаёт сделки.")]]);
  const strategyField = (section, key, title, unit, max, helpText, value) => {
    const name = `strategy.${section}.${key}`;
    const step = key.includes("months") || key.includes("days") ? "1" : "any";
    return `<div class="field"><span>${esc(title)}${help(title, helpText)}</span><div class="touch-input"><button type="button" class="step-button" data-step-field="${name}" data-step-direction="-1" aria-label="${H("Уменьшить:")} ${esc(title)}">−</button><input name="${name}" aria-label="${esc(title)}, ${esc(unit)}" type="number" inputmode="decimal" min="${key === "horizon_months" ? "1" : "0"}" max="${max}" step="${step}" value="${esc(value ?? "")}" placeholder="${H("Не указано")}"><button type="button" class="step-button" data-step-field="${name}" data-step-direction="1" aria-label="${H("Увеличить:")} ${esc(title)}">+</button><small>${esc(unit)}</small></div></div>`;
  };
  const strategyEditorHTML = ({
    document,
    preset,
    slot,
    catalog
  }) => {
    let editor;
    if (!document) editor = `<section class="card">${state.errors.strategy ? dataError("strategy") : empty(T("Выберите свой подход"), T("Изучите описание и выберите стратегию. Личные суммы не подставляются из шаблона; их задаёте вы."), renderStrategiesValue(), T("Войти"), "strategies", true)}<p class="notice">${H("Расчёты проверяют условия на данных, доступных системе. Ни одна стратегия не гарантирует сохранность капитала или прибыль.")}</p></section>`;else editor = `<div class="strategy-editor"><section class="card"><div class="strategy-heading"><h2>${esc(strategyEditorTitle())}</h2><span class="save-status" data-save-status="strategy"></span></div><p class="strategy-note section-gap">${esc(preset?.description || T("Ваши сохранённые параметры стратегии"))}</p>${saveErrorHTML("strategy")}<form id="strategy-form"><div class="allocation-sliders">${[["shares", T("Акции")], ["bonds", T("Облигации")], ["funds", T("Фонды")], ["cash", T("Деньги")]].map(([key, label], index) => renderStrategiesRangeRow(key, index, label, document)).join("")}</div><p class="data-footnote">${H("Сумма долей всегда 100%. Изменение одной доли пропорционально перераспределяет остальные незакреплённые доли.")}</p><details><summary class="details-summary">${H("Закрепить или исключить классы")}</summary><div class="allocation-flags">${[["shares", T("Акции")], ["bonds", T("Облигации")], ["funds", T("Фонды")], ["cash", T("Деньги")]].map(([key, label]) => renderStrategiesAllocationFlagRow(label, key, document)).join("")}</div></details><h3 class="panel-title section-gap">${H("Ваши условия")}</h3><div class="field-grid">${strategyField("profile", "reserve_rub", T("Резерв вне инвестиций"), "₽", 1000000000000, T("Личная сумма, которую следует сохранить доступной. Укажите реальное значение; пустое поле означает неизвестные условия."), document.profile.reserve_rub)}${strategyField("profile", "planned_withdrawal_rub", T("Планируемый вывод"), "₽", 1000000000000, T("Запланированная потребность в деньгах. При смене готовой стратегии эта сумма сохраняется."), document.profile.planned_withdrawal_rub)}${strategyField("profile", "horizon_months", T("Инвестиционный горизонт"), T("мес."), 1200, T("Срок вашей цели. Более длинный срок не исключает убытки и потребность в резерве."), document.profile.horizon_months)}${strategyField("profile", "max_drawdown_percent", T("Допустимая просадка"), "%", 100, T("Ваша готовность к временному снижению капитала. Это условие модели, а не гарантированный предел потерь."), document.profile.max_drawdown_percent)}${strategyField("profile", "liquidity_horizon_days", T("Срок доступности денег"), T("дней"), 36500, T("За сколько дней вам могут понадобиться деньги. Фактическая ликвидность инструментов проверяется отдельно."), document.profile.liquidity_horizon_days)}</div><label class="check-field section-gap"><input type="checkbox" name="strategy.profile.allow_below_investment_grade"${document.profile.allow_below_investment_grade ? " checked" : ""}><span>${H("Рассматривать бумаги ниже инвестиционного рейтинга. Это повышенный кредитный риск.")}</span></label><details><summary class="details-summary">${H("Ограничения портфеля")}</summary><div class="field-grid">${policyFields().map(([key, title, unit, max, detail]) => strategyField("policy", key, title, unit, max, detail, document.policy[key])).join("")}</div></details><details><summary class="details-summary">${H("Рейтинги и условия доходности")}</summary><p class="fine-print">${H("Доли по рейтинговым категориям — верхние границы. Рейтинговый уровень не равен вероятности успеха.")}</p><div class="field-grid">${select("strategy.rules.yield_floor", T("Условие доходности"), [["none", T("Не задавать")], ["key_rate", T("От ключевой ставки")]], document.rules.yield_floor, T("Порог применяется только при наличии сопоставимых данных о доходности инструмента и ключевой ставке."))}${strategyField("rules", "yield_margin_pp", T("Надбавка к ставке"), T("п.п."), 100, T("Заданная надбавка к официальной ключевой ставке для фильтра условий. Это не обещание доходности."), document.rules.yield_margin_pp)}${strategyField("rules", "fund_wrapper_cap_percent", T("Доля одного фонда"), "%", 100, T("Дополнительный предел для отдельного фонда. Не отменяет проверки его состава."), document.rules.fund_wrapper_cap_percent)}${(catalog.rating_levels || []).map(grade => field({
      name: renderStrategiesFragment(grade),
      label: renderStrategiesFragment2(grade),
      type: "number",
      min: 0,
      max: 100,
      step: "0.01",
      required: true,
      value: document.rules.rating_caps[grade]
    })).join("")}</div></details></form><details><summary class="details-summary">${H("Методика и источники")}</summary><p class="help-copy">${esc(preset?.risk || T("Проверяйте ограничения и полноту данных."))}</p><ul class="source-list">${(catalog.sources || []).filter(item => !preset?.source_ids || preset.source_ids.includes(item.id)).map(item => renderStrategiesLi(item)).join("")}</ul></details></section><section class="card"><div class="card-header"><h2>${H("Проверка на вашем счёте")}</h2>${button(T("Рассчитать"), "assess-strategy", {
      primary: true,
      small: true,
      extra: state.loading.has("assessment") || slot.busy || slot.dirty ? "disabled" : ""
    })}</div><p class="fine-print">${H("Проверяются распределение и ограничения по фактическому составу. Расчёт не сохраняет новые условия и не создаёт сделки.")}</p><div id="strategy-assessment">${renderAssessment()}</div></section><section class="card"><h3 class="panel-title">${H("Исследование на истории")}</h3><p class="fine-print">${H("Задайте период, расчётный капитал и издержки. Система использует полученные наблюдения и отделяет проверочный период. Вероятность будущей прибыли из результата не выводится.")}</p>${researchForm()}<div id="strategy-research">${renderResearch()}</div></section></div>`;
    return editor;
  };
  const renderStrategies = () => {
    captureScreenDrafts();
    const catalog = state.data.catalog;
    const slot = state.strategy;
    const document = state.tour ? null : slot.draft;
    const preset = state.tour ? null : selectedPreset();
    if (!catalog) {
      $("#view-strategies").innerHTML = `${heading(T("Стратегии"), T("Выбор подхода и личные ограничения"))}${state.errors.catalog ? dataError("catalog") : U.loading(T("Получаем каталог стратегий…"))}`;
      return;
    }
    const list = `<aside class="card strategy-catalog"><h2>${H("Выбор стратегии")}</h2>${strategyTabsHTML()}<div id="strategy-panel-catalog" role="tabpanel" aria-labelledby="strategy-tab-catalog" tabindex="0"${state.strategyPane === "catalog" ? "" : " hidden"}>${catalog.presets.map(raw => {
      const item = I.preset(raw);
      const [symbol] = strategyIcons[item.id] || ["strategies"];
      return renderStrategiesStrategyOption(item, document, symbol);
    }).join("")}</div><div id="strategy-panel-custom" role="tabpanel" aria-labelledby="strategy-tab-custom" tabindex="0"${state.strategyPane === "custom" ? "" : " hidden"}><output id="strategy-custom-status" class="fine-print"></output><div class="form-actions"><button type="button" class="button secondary" data-action="strategy-apply-custom" disabled>${H("Создать из текущей")}</button></div></div></aside>`;
    const editor = strategyEditorHTML({
      document,
      preset,
      slot,
      catalog
    });
    $("#view-strategies").innerHTML = `${heading(T("Стратегии"), T("Десять подходов. Ваши цели, ограничения и данные."), button(T("Обновить"), "refresh", {
      small: true
    }))}<div class="strategy-layout">${list}${editor}</div>${dataError("investmentProfile")}${dataError("balancingPolicy")}`;
    if (document) $("#view-strategies .strategy-editor")?.insertAdjacentHTML("beforeend", executionPlannerCard());
    updateSaveStatus("strategy");
    U.bindCharts($("#view-strategies"));
    applyScreenLayout("strategies");
  };
  const documentChanged = () => {
    const slot = state.strategy;
    slot.draft.customized = true;
    slot.intent = "edit";
    slot.revision += 1;
    slot.dirty = true;
    if (slot.error?.status !== 409) slot.error = null;
    slot.assessment = null;
    slot.research = null;
    updateSaveStatus("strategy");
    scheduleSave("strategy");
  };
  const redistribute = (document, key, requested) => {
    const keys = ["shares", "bonds", "funds", "cash"];
    const others = keys.filter(item => item !== key && !document.locked.includes(item) && !document.excluded.includes(item));
    const fixed = keys.filter(item => item !== key && !others.includes(item)).reduce((sum, item) => sum + document.allocation[item], 0);
    const target = Math.max(0, Math.min(100 - fixed, Math.round(requested)));
    if (!others.length && target !== 100 - fixed) return false;
    document.allocation[key] = target;
    const remaining = 100 - fixed - target;
    const weight = others.reduce((sum, item) => sum + document.allocation[item], 0);
    const rows = others.map(item => ({
      key: item,
      value: weight ? document.allocation[item] / weight * remaining : remaining / others.length
    }));
    rows.forEach(item => {
      document.allocation[item.key] = Math.floor(item.value);
    });
    const rest = 100 - keys.reduce((sum, item) => sum + document.allocation[item], 0);
    rows.sort((a, b) => b.value % 1 - a.value % 1 || a.key.localeCompare(b.key));
    rows.slice(0, rest).forEach(item => {
      document.allocation[item.key] += 1;
    });
    return true;
  };
  const updateAllocation = (key, value) => {
    const slot = state.strategy;
    if (!slot.draft || slot.error?.status === 409) return;
    const before = clone(slot.draft.allocation);
    if (!redistribute(slot.draft, key, value)) {
      toast(T("Все остальные доли закреплены. Сначала освободите одну из них."));
      return;
    }
    if (same(before, slot.draft.allocation)) return;
    for (const input of $$("[data-allocation]")) {
      input.value = slot.draft.allocation[input.dataset.allocation];
      input.nextElementSibling.textContent = `${input.value}%`;
    }
    documentChanged();
  };
  const strategyMethodLabels = () => ({
    inverse_volatility: T("По прошлому риску"),
    short_quality: T("Качество и короткий срок"),
    positive_momentum: T("Положительная динамика"),
    risk_adjusted_momentum: T("Динамика с учётом риска"),
    documented_cashflow: T("Подтверждённый денежный поток"),
    quality_value: T("Качество бизнеса и стоимость"),
    index_cost: T("Состав и расходы индексных фондов"),
    regime_risk: T("Баланс экономических режимов"),
    maturity_ladder: T("Ступени погашений"),
    covered_dividends: T("Покрытие дивидендов"),
    floating_cashflow: T("Плавающий купон")
  });
  const factLabels = () => ({
    maturity_date: T("дата погашения"),
    maturity_limit: T("предельный срок"),
    rating: T("кредитный рейтинг"),
    max_unknown_percent: T("лимит бумаг без рейтинга"),
    max_below_grade_percent: T("лимит низких рейтингов"),
    finite_bond_term: T("конечный срок облигации"),
    coupon_formula: T("формула купона"),
    roe_percent: T("рентабельность капитала"),
    debt_to_ebitda: T("долг к EBITDA"),
    free_cashflow_yield_percent: T("доходность свободного денежного потока"),
    expense_ratio_percent: T("расходы фонда"),
    index_tracking: T("следование индексу"),
    fund_constituents: T("полный состав фонда"),
    growth_beta: T("чувствительность к росту"),
    inflation_beta: T("чувствительность к инфляции"),
    factor_observations: T("наблюдения факторов"),
    volatility_percent: T("волатильность"),
    dividend_yield_percent: T("дивидендная доходность"),
    payout_ratio_percent: T("доля прибыли на дивиденды"),
    dividend_decision: T("решение о дивидендах"),
    dividend_declared: T("подтверждение дивидендов"),
    net_yield_percent: T("доходность после издержек"),
    key_rate_percent: T("ключевая ставка"),
    cashflow_yield_percent: T("доходность денежного потока"),
    historical_return_percent: T("изменение на истории"),
    training_observations: T("наблюдения обучающего периода"),
    max_drawdown_percent: T("историческая просадка"),
    price_rub: T("рублёвая цена"),
    average_daily_volume_rub: T("средний оборот"),
    lot_size: T("размер лота"),
    issuer_id: T("эмитент"),
    group_id: T("группа компаний"),
    sector: T("сектор"),
    issuer: T("эмитент"),
    group: T("группа компаний"),
    floating_coupon: T("плавающий купон"),
    coupon_formula_verified: T("проверенная формула купона"),
    perpetual: T("бессрочная облигация"),
    price_earnings_ttm: T("P/E за последние 12 месяцев"),
    market_capitalization: T("капитализация")
  });
  const selectionReasonLabels = () => ({
    historical_lot_sizes: T("research.missing.lots"),
    share_splits_and_other_actions: T("research.missing.actions"),
    dated_fund_constituents: T("research.missing.constituents"),
    bond_nkd_open_close_timing: T("research.missing.nkd"),
    unsupported_research_asset_class: T("Класс актива не поддержан этим методом"),
    dividend_history_unavailable: T("research.missing.dividends"),
    coupons_unavailable: T("research.missing.coupons"),
    bond_events_unavailable: T("research.missing.bond_events"),
    daily_accruals_unavailable: T("research.missing.accruals"),
    research_read_budget_exhausted: T("research.missing.budget"),
    coupons_read_budget_exhausted: T("research.missing.budget"),
    bond_events_read_budget_exhausted: T("research.missing.budget"),
    daily_accruals_read_budget_exhausted: T("research.missing.budget"),
    price_discontinuity_requires_review: T("research.missing.price_jump"),
    history_gap_requires_review: T("research.missing.history_gap"),
    invalid_distribution_event: T("research.missing.cashflow_invalid"),
    duplicate_distribution_event: T("research.missing.cashflow_duplicate"),
    corporate_action_time_missing: T("research.missing.action_time"),
    corporate_action_requires_adjustment: T("research.missing.action_adjustment"),
    split_evidence_invalid: T("research.missing.split_invalid"),
    duplicate_split_event: T("research.missing.split_duplicate"),
    bond_valuation_history_incomplete: T("research.missing.bond_value"),
    bond_valuation_history_invalid: T("research.missing.bond_value"),
    factor_history_invalid: T("research.missing.factors"),
    factor_history_duplicate: T("research.missing.factors"),
    unsupported_return_basis: T("research.missing.return_basis"),
    total_return_basis_not_verified: T("research.missing.total_return"),
    cashflows_require_verified_basis: T("research.missing.total_return"),
    bond_principal_and_accrual_history_required: T("research.missing.bond_principal"),
    insufficient_training_history: T("Недостаточная история для обучающего периода"),
    price_or_liquidity_missing: T("Нет подтверждённых цены или ликвидности"),
    invalid_risk_metric: T("Показатель риска не прошёл проверку"),
    historical_drawdown_limit: T("Историческая просадка превышает условие"),
    positive_documented_cashflow_required: T("Нет положительного подтверждённого денежного потока"),
    floating_coupon_required: T("Нужен плавающий купон"),
    return_on_equity_limit: T("Рентабельность капитала не отвечает условию"),
    debt_limit: T("Долговая нагрузка не отвечает условию"),
    cashflow_value_limit: T("Денежный поток не отвечает условию стоимости"),
    fund_too_concentrated: T("Недостаточное число эмитентов в фонде"),
    fund_constituent_limit: T("Доля эмитента внутри фонда превышает предел"),
    fund_expense_limit: T("Расходы фонда превышают предел"),
    insufficient_factor_history: T("Недостаточная история экономических факторов"),
    factor_exposure_not_identified: T("Влияние экономических факторов не установлено"),
    dividends_not_cashflow_covered: T("Дивиденды не подтверждены денежным потоком"),
    payout_limit: T("Доля прибыли на дивиденды не отвечает условию"),
    positive_dividend_required: T("Нет подтверждённой положительной дивидендной доходности"),
    net_yield_floor: T("Доходность после издержек ниже заданного порога"),
    historical_volatility_limit: T("Историческая волатильность превышает предел"),
    momentum_not_positive: T("Нет положительной динамики на прошлом периоде"),
    unsupported_asset_class: T("Класс актива не поддержан этим методом"),
    asset_class_excluded: T("Класс актива исключён настройками"),
    non_ruble_series: T("Нет сопоставимого рублёвого ряда"),
    lot_size_missing: T("Не подтверждён размер лота"),
    maturity_limit: T("Срок погашения не отвечает условию"),
    rating_excluded: T("Рейтинговая категория исключена"),
    below_grade_not_allowed: T("Низкий кредитный рейтинг не разрешён настройками"),
    minimum_rating: T("Рейтинг ниже заданного порога"),
    max_unknown_percent_excluded: T("Бумаги без рейтинга исключены"),
    max_below_grade_percent_excluded: T("Низкие рейтинги исключены"),
    four_economic_regimes: T("Не покрыты все четыре экономических режима")
  });
  const allocationRequirement = (key, prefix, name) => {
    const assetClass = {
      shares: T("акций"),
      bonds: T("облигаций"),
      funds: T("фондов")
    }[name || key.replace("eligible_", "")];
    if (key.startsWith("eligible_") && assetClass) return `${T("Нет подходящих")} ${assetClass} ${T("с подтверждёнными данными.")}`;
    if (prefix === "unfilled_target" && assetClass) return `${T("Целевая доля")} ${assetClass} ${T("заполнена частично.")}`;
    if (prefix === "target_above_class_cap" && assetClass) return `${T("Целевая доля")} ${assetClass} ${T("выше ограничения.")}`;
    return null;
  };
  const humanRequirement = value => {
    if (value && typeof value === "object") return humanRequirement(value.title || value.reason || "");
    const key = String(value || "");
    if (/[А-Яа-яЁё]/.test(key)) return key;
    if (selectionReasonLabels()[key]) return selectionReasonLabels()[key];
    const [prefix, name] = key.split(":");
    if (["missing", "unverified"].includes(prefix)) return factLabels()[name] ? `${T("Не подтверждены данные:")} ${factLabels()[name]}.` : T("Не подтверждён необходимый показатель источника.");
    const allocationReason = allocationRequirement(key, prefix, name);
    if (allocationReason) return allocationReason;
    if (key.startsWith("policy.")) return T("Не указан необходимый предел в настройках портфеля.");
    if (factLabels()[key]) return `${T("Не получены данные:")} ${factLabels()[key]}.`;
    return T("Требуется проверка условий и полноты исходных данных.");
  };
  const assessmentValue = (value, key = "") => {
    if (value === null || value === undefined) return "—";
    if (Array.isArray(value)) return value.map(item => assessmentValue(item)).join(", ") || "—";
    if (typeof value === "boolean") return value ? T("Да") : T("Нет");
    if (typeof value === "object") {
      const labels = {
        rub: T("Сумма"),
        percent: T("Доля"),
        complete: T("Полное покрытие"),
        total_rub: T("Всего"),
        blocked_rub: T("Заблокировано"),
        unblocked_rub: T("Доступно"),
        reserve_rub: T("Резерв"),
        withdrawals_rub: T("Выводы"),
        target_rub: T("Денежная доля"),
        allocation_capacity_rub: T("Для распределения"),
        shortfall_rub: T("Дефицит"),
        executable_budget: T("Разрешает сделку"),
        unclassified_rub: T("Не классифицировано"),
        shares: T("Акции"),
        bonds: T("Облигации"),
        funds: T("Фонды"),
        cash: T("Деньги")
      };
      return Object.entries(value).filter(([name]) => labels[name]).map(([name, item]) => `${labels[name]}: ${assessmentValue(item, name)}`).join(" · ") || T("Проверено в составе условия");
    }
    if (key === "rub" || key.endsWith("_rub")) return money(value);
    if (key === "percent" || key.endsWith("_percent")) return percent(value);
    return {
      shares: T("Акции"),
      bonds: T("Облигации"),
      funds: T("Фонды"),
      cash: T("Деньги")
    }[value] || String(value);
  };
  const selectionHTML = (selection, title = T("Подбор по подтверждённым данным")) => {
    if (!selection) return "";
    const selected = Array.isArray(selection.selected) ? selection.selected : [];
    const candidates = Array.isArray(selection.candidates) ? selection.candidates : [];
    return `<details class="section-gap"><summary class="details-summary">${esc(title)}</summary><p class="fine-print">${esc(strategyMethodLabels()[selection.method] || T("Проверка условий стратегии"))} · ${esc({
      ready: T("Данные для корзины подтверждены"),
      partial: T("Частичное покрытие"),
      insufficient_data: T("Недостаточно данных")
    }[selection.status] || T("Ожидается проверка"))} ${H("· на")} ${esc(date(selection.as_of, true))} ${H("МСК")}</p>${selection.scope ? renderSelectionHTMLNotice(selection) : ""}${selected.length ? renderSelectionHTMLPanelTitle(selected) : ("<p class=\"fine-print\">" + H("Корзина из подтверждённых инструментов пока не сформирована.") + "</p>")}${infoRows([[T("Остаток расчётной доли деньгами"), percent(selection.cash_weight_percent)]])}${selection.missing_requirements?.length ? renderSelectionHTMLRiskList(selection) : ""}${candidates.length ? renderSelectionHTMLDetailsSummary2(candidates) : ""}</details>`;
  };
  const renderAssessment = () => {
    if (state.loading.has("assessment")) return U.loading(T("Проверяем данные и ограничения счёта…"));
    if (state.errors.assessment) return `<div class="notice error">${esc(humanError(state.errors.assessment))}</div>`;
    const result = state.strategy.assessment;
    if (!result) return empty(T("Проверка ещё не выполнена"), T("Сохраните параметры и запустите расчёт. Неполные данные будут отмечены отдельно."), "", "", "analytics");
    return `${freshness(T("Состав T-Invest"), result.captured_at)}<div class="assessment-metrics section-gap"><div class="assessment-metric"><span>${H("Стоимость счёта")}</span><strong>${esc(money(result.nav_rub))}</strong></div><div class="assessment-metric"><span>${H("Проверок")}</span><strong>${result.checks?.length || 0}</strong></div><div class="assessment-metric"><span>${H("Вероятность прибыли")}</span><strong>—</strong></div></div><p class="fine-print section-gap">${esc(result.probability_reason || T("Проверка ограничений не оценивает вероятность будущей прибыли."))}</p>${(result.checks || []).map(item => renderAssessmentDetailsSummary(item)).join("")}${selectionHTML(result.selection)}`;
  };
  const assessStrategy = async () => {
    if (!requireUser() || state.loading.has("assessment")) return;
    const slot = state.strategy;
    if (!slot.server || slot.dirty || slot.busy || slot.error) {
      toast(T("Сначала дождитесь подтверждённого сохранения стратегии."), true);
      return;
    }
    const version = slot.server.version;
    const revision = slot.revision;
    const generation = state.generation;
    state.loading.add("assessment");
    delete state.errors.assessment;
    slot.assessment = null;
    updateSaveStatus("strategy");
    $("#strategy-assessment").innerHTML = renderAssessment();
    try {
      const result = await api("/api/profile/strategy/account-assessment", {
        method: "POST",
        timeout: 60000,
        body: {
          expected_public_id: state.user.public_id,
          expected_version: version
        }
      });
      if (generation !== state.generation || version !== slot.server?.version || revision !== slot.revision) return;
      slot.assessment = result;
    } catch (error) {
      if (generation === state.generation && !isCancelled(error)) state.errors.assessment = error;
    } finally {
      if (generation === state.generation) {
        state.loading.delete("assessment");
        updateSaveStatus("strategy");
        const container = $("#strategy-assessment");
        if (container) container.innerHTML = renderAssessment();
      }
    }
  };
  const researchForm = () => `<form id="research-form" class="research-form"><div class="field-grid">${field({
    name: "from_at",
    label: T("Начало периода"),
    type: "date",
    value: state.researchDraft.from_at,
    required: true
  })}${field({
    name: "to_at",
    label: T("Конец периода"),
    type: "date",
    value: state.researchDraft.to_at,
    max: new Date(Date.now() - 86400000).toISOString().slice(0, 10),
    hint: T("research.complete_day"),
    required: true
  })}${field({
    name: "initial_capital_rub",
    label: T("Расчётный капитал, ₽"),
    type: "number",
    value: state.researchDraft.initial_capital_rub,
    min: ".01",
    max: 1000000000000,
    step: ".01",
    required: true,
    helpText: T("Капитал для исторического исследования. Это явно заданное условие расчёта, а не сумма реальных денег на вашем счёте.")
  })}${field({
    name: "commission_bps",
    label: T("Комиссия, базисных пунктов"),
    type: "number",
    value: state.researchDraft.commission_bps,
    min: "0",
    max: "1000",
    step: ".01",
    required: true,
    helpText: T("Один базисный пункт равен 0,01%. Укажите фактические или исследуемые издержки; значение не подставляется автоматически.")
  })}${field({
    name: "slippage_bps",
    label: T("Проскальзывание, базисных пунктов"),
    type: "number",
    value: state.researchDraft.slippage_bps,
    min: "0",
    max: "1000",
    step: ".01",
    required: true,
    helpText: T("Дополнительная разница между наблюдаемой и расчётной ценой. Реальное проскальзывание заранее неизвестно.")
  })}</div><div class="form-actions"><button class="button primary" type="submit"${strategySaveUnavailable(state.strategy) || researchUnavailable() ? " disabled" : ""}>${H("Проверить на истории")}</button><button class="button secondary" type="button" data-research-action="archive">${H("История исследований")}</button><button class="button secondary" type="button" data-research-action="evidence">${H("Источники данных")}</button></div><output id="research-message" class="form-message"></output></form>`;
  const researchPending = () => Boolean(state.researchRequest && ["submitting", "checking", "running", "uncertain", "not_found"].includes(state.researchRequest.status));
  const researchAtCapacity = () => {
    const capacity = state.data.researchArchive?.capacity;
    return Boolean(capacity && (capacity.runs_used >= capacity.runs_limit || capacity.storage_used_bytes >= capacity.storage_limit_bytes));
  };
  const researchUnavailable = () => researchPending() || state.loading.has("researchArchive") || !state.data.researchArchive || Boolean(state.errors.researchArchive) || researchAtCapacity();
  const researchCapacityHTML = capacity => {
    if (!capacity) return "";
    const runs = `${format(capacity.runs_used, 0)} / ${format(capacity.runs_limit, 0)}`;
    const storage = `${format(capacity.storage_used_bytes / 1048576, 1)} / ${format(capacity.storage_limit_bytes / 1048576, 0)} ${T("billing.mib")}`;
    return `<div class="section-gap">${infoRows([[T("research.saved_runs"), runs], [T("research.stored_inputs"), storage]])}<p class="fine-print">${H("research.capacity_help")}</p></div>`;
  };
  const researchRequestHTML = () => {
    const request = state.researchRequest;
    if (!request) return "";
    const pending = researchPending();
    const text = {
      submitting: T("research.submitting"), checking: T("research.checking"),
      running: T("research.running"), uncertain: T("research.uncertain"),
      not_found: T("research.not_found"), completed: T("research.completed"),
      missing: T("research.restored_request_missing"),
      failed: T("research.failed"), expired: T("research.expired"),
      deleted: T("research.deleted"), conflict: T("research.conflict")
    }[request.status] || T("research.uncertain");
    const check = pending && !request.busy || request.resultPending;
    const retry = request.status === "not_found" && request.body && !request.busy;
    const warning = ["uncertain", "not_found", "missing", "failed", "expired", "conflict"].includes(request.status) || request.error;
    const error = request.error ? `<p>${esc(humanError(request.error))}</p>` : "";
    const started = request.created_at ? `<p class="fine-print">${H("research.started_at")} ${esc(date(request.created_at, true))} ${H("МСК")}</p>` : "";
    const version = request.archivedOnly ? `<p>${H("research.other_version")}</p>` : "";
    const open = request.run_id ? `<button class="button secondary small" data-research-run="${esc(request.run_id)}" data-research-operation="open">${H("Открыть")}</button>` : "";
    const checkButton = check ? button(T("research.check"), "research-check", {small: true, extra: request.busy ? "disabled" : ""}) : "";
    const retryButton = retry ? button(T("research.retry_original"), "research-retry", {small: true}) : "";
    return `<div class="notice${warning ? " warning" : ""}" data-research-state="${esc(request.status)}" role="status"><strong>${esc(text)}</strong>${error}${started}${version}<div class="form-actions">${checkButton}${retryButton}${open}</div></div>`;
  };
  const researchStateHTML = () => {
    const loading = !state.data.researchArchive && !state.errors.researchArchive ? U.loading(T("research.checking_archive")) : "";
    const capacity = researchAtCapacity() ? `<p class="notice warning">${H("research.full")}</p>` : "";
    return dataError("researchArchive") + loading + capacity + researchRequestHTML();
  };
  const researchMetricLabels = () => ({
    net_return_percent: T("Результат за период"),
    max_drawdown_percent: T("Максимальная просадка"),
    annualized_volatility_percent: T("Волатильность, годовая"),
    var_95_percent: T("VaR, уровень 95%"),
    expected_shortfall_95_percent: T("Средние потери в хвосте 5%"),
    transaction_costs_rub: T("Заданные издержки"),
    taxes_rub: T("Налоги в условной модели"),
    trades: T("Расчётных сделок"),
    ending_cash_rub: T("Остаток средств")
  });
  const researchDataCoverageHTML = rows => {
    if (!rows?.length) return "";
    const items = rows.map(item => {
      const facts = infoRows([[T("research.coverage.cashflows"), format(item.automatic_cashflow_events, 0)],
        [T("research.coverage.accruals"), format(item.daily_accrual_observations, 0)],
        [T("research.coverage.facts"), format(item.historical_fact_observations, 0)]]);
      const missing = item.missing?.length ? `<ul class="risk-list">${item.missing.map(renderFundamentalMetricsHTMLLi2).join("")}</ul>` : "";
      return `<section class="section-gap"><h4>${esc(item.instrument_uid)}</h4>${facts}<p class="fine-print">${item.total_return_verified ? H("research.coverage.user_confirmed") : H("research.coverage.incomplete")}</p>${missing}</section>`;
    }).join("");
    return `<details class="section-gap" data-research-coverage><summary class="details-summary">${H("research.coverage.title")}</summary><p class="fine-print">${H("research.coverage.scope")}</p>${items}</details>`;
  };
  const incompleteResearchHTML = result => `<div class="notice warning"><strong>${H("Недостаточно данных для исследования")}</strong><p>${esc(result.reason || (result.limitations || []).join(" ") || T("Не получена достаточная история цен и доступности инструментов."))}</p></div>${result.missing_requirements?.length ? renderResearchRiskList(result) : ""}${selectionHTML(result.selection, T("Проверка исторической выборки"))}${selectionHTML(result.current_selection, T("Отдельный подбор по сегодняшним данным"))}${result.limitations?.length ? renderResearchDetailsSummary2(result) : ""}${researchDataCoverageHTML(result.data_coverage)}${researchRobustnessHTML(result)}`;
  const renderResearch = () => {
    const status = researchStateHTML();
    const result = state.strategy.research;
    if (!result) return status;
    const otherVersion = result.archive?.strategy_version !== state.strategy.server?.version ? " · " + H("research.archive_version") : "";
    const source = result.archive?.strategy_version ? `<p class="data-footnote">${H("Версия стратегии:")} ${esc(result.archive.strategy_version)}${otherVersion}</p>` : "";
    if (result.status !== "computed") return status + source + incompleteResearchHTML(result);
    return `${status}${source}<div class="section-gap"><h3 class="panel-title">${esc(result.return_label || T("Результат исторического исследования"))}</h3>${result.complete_strategy_coverage === false ? renderResearchNotice(result) : ""}<p class="research-period">${esc(date(result.period?.from))} — ${esc(date(result.period?.to))} · ${esc(format(result.period?.observations, 0))} ${H("наблюдений")}</p><div class="assessment-metrics">${Object.entries(researchMetricLabels()).map(([key, label]) => renderResearchAssessmentMetric(label, key, result)).join("")}</div>${chart(result.equity_curve, {
      timeKey: "time",
      valueKey: "nav_rub",
      label: T("Расчётная стоимость на исторических данных"),
      personal: false
    })}<p class="notice">${esc(result.probability_reason || T("Результат на прошлом периоде не оценивает вероятность будущей прибыли."))}</p>${result.period?.test_from ? renderResearchFinePrint(result) : ""}${result.benchmark ? renderResearchDetailsSummary(result) : ""}${result.missing_requirements?.length ? renderResearchRiskList(result) : ""}${selectionHTML(result.selection, T("Корзина по данным обучающего периода"))}${selectionHTML(result.current_selection, T("Отдельный подбор по сегодняшним данным"))}${researchDataCoverageHTML(result.data_coverage)}${researchRobustnessHTML(result)}${result.limitations?.length ? renderResearchDetailsSummary2(result) : ""}${result.sources?.length ? renderResearchSourceList(result) : ""}</div>`;
  };
  const researchWindowHTML = item => {
    const result = item.status === "computed" ? infoRows([[T("Результат"), percent(item.metrics?.net_return_percent)], [T("Просадка"), percent(item.metrics?.max_drawdown_percent)]]) : ("<p class=\"notice\">" + H("Недостаточно данных для этого окна.") + "</p>");
    return `<div class="section-gap"><strong>${esc(date(item.period?.from))} — ${esc(date(item.period?.to))}</strong>${result}</div>`;
  };
  const researchRobustnessHTML = result => {
    const windows = result.robustness?.windows || [];
    const stress = result.stress_scenario;
    const windowDetails = windows.length ? `<details><summary class="details-summary">${H("Проверка на трёх временных окнах")}</summary><p class="fine-print">${esc(result.robustness.scope)}</p>${windows.map(researchWindowHTML).join("")}</details>` : "";
    const stressDetails = stress ? `<details><summary class="details-summary">${H("Стресс-сценарий")}</summary>${infoRows([[T("Стоимость перед шоком"), money(stress.base_nav_rub)], [T("После заданного шока"), money(stress.stressed_nav_rub)], [T("Потери в сценарии"), money(stress.loss_rub)]])}<p class="fine-print">${esc(stress.scope)}</p></details>` : "";
    const archive = result.archive ? `<p class="data-footnote">${H("Исследование сохранено")} ${esc(date(result.archive.created_at, true))} ${H("МСК. В истории доступны исходные данные и повторная проверка расчёта.")}</p>` : "";
    return windowDetails + stressDetails + archive;
  };
  const researchArchiveItemHTML = item => `<section class="card section-gap"><h3>${esc(date(item.created_at, true))} ${H("МСК")}</h3><p class="fine-print">${H("Версия стратегии:")} ${esc(item.strategy_version)} · ${esc(item.status === "computed" ? T("Рассчитано") : T("Данные неполные"))}</p>${infoRows([[T("Результат за период"), percent(item.metrics?.net_return_percent)]])}<div class="form-actions"><button class="button secondary small" data-research-run="${esc(item.id)}" data-research-operation="open">${H("Открыть")}</button><button class="button secondary small" data-research-run="${esc(item.id)}" data-research-operation="replay">${H("Проверить повторяемость")}</button><button class="button secondary small" data-research-run="${esc(item.id)}" data-research-operation="export">${H("Скачать входные данные")}</button><button class="button danger small" data-research-run="${esc(item.id)}" data-research-operation="delete">${H("Удалить")}</button></div></section>`;
  const openResearchArchive = async () => {
    if (enterRouteScreen("strategies", "archive", {})) return;
    if (!requireUser()) return;
    openDialog(T("История исследований"), `<div id="research-archive">${U.loading(T("research.checking_archive"))}</div>`);
    state.researchArchiveDialog = {items: [], next_cursor: null, capacity: null, busy: false, error: null,
      generation: state.generation, sequence: state.eventRequest};
    await loadResearchArchivePage(false);
  };
  const readResearchChoices = async () => {
    const first = await api("/api/research/runs?limit=200");
    const items = new Map(first.items.map(item => [item.id, item]));
    const cursors = new Set();
    const maximumPages = Math.ceil(first.capacity.runs_used / 200) + 1;
    const readNext = async cursor => {
      if (!cursor) return;
      if (cursors.has(cursor) || cursors.size >= maximumPages) throw new Error("invalid_server_response");
      cursors.add(cursor);
      const page = await api(`/api/research/runs?limit=200&cursor=${safeSegment(cursor)}`);
      for (const item of page.items) items.set(item.id, item);
      return readNext(page.next_cursor);
    };
    await readNext(first.next_cursor);
    return {...first, items: [...items.values()], next_cursor: null};
  };
  const currentResearchArchive = page => page === state.researchArchiveDialog && page.generation === state.generation && page.sequence === state.eventRequest && $("#workspace-dialog").open;
  const renderResearchArchive = page => {
    if (!currentResearchArchive(page)) return;
    const restart = page.error?.code === "research_cursor_not_found";
    const emptyState = !page.items.length && !page.busy && !page.error ? `<p class="notice">${H("Сохранённых исследований пока нет.")}</p>` : "";
    const error = page.error ? `<p class="notice error">${esc(humanError(page.error))}</p>` : "";
    const loading = page.busy ? U.loading(T("Загрузка…")) : "";
    const extra = page.busy ? "disabled" : "";
    const more = page.next_cursor && !restart ? button(T("Показать ещё"), "research-archive-more", {extra}) : "";
    const reload = restart || page.error && !page.next_cursor ? button(T("research.reload_archive"), "research-archive-reload", {extra}) : "";
    $("#research-archive").innerHTML = `<p class="fine-print">${H("Каждый запуск сохраняет версию стратегии, заданные издержки, точные входные данные и результат. Повторная проверка не обращается к внешним источникам.")}</p>${researchCapacityHTML(page.capacity)}${page.items.map(researchArchiveItemHTML).join("")}${emptyState}${error}${loading}<div class="form-actions">${more}${reload}</div>`;
  };
  const loadResearchArchivePage = async more => {
    const page = state.researchArchiveDialog;
    if (!page || !currentResearchArchive(page) || page.busy || more && !page.next_cursor) return;
    const cursor = more ? page.next_cursor : null;
    page.busy = true;
    page.error = null;
    renderResearchArchive(page);
    try {
      const query = cursor ? `&cursor=${safeSegment(cursor)}` : "";
      const payload = await api(`/api/research/runs?limit=50${query}`);
      if (!currentResearchArchive(page)) return;
      const previous = more ? page.items : [];
      page.items = [...new Map([...previous, ...payload.items].map(item => [item.id, item])).values()];
      page.next_cursor = payload.next_cursor;
      page.capacity = payload.capacity;
      if (!more) state.data.researchArchive = payload;
      else if (state.data.researchArchive) state.data.researchArchive.capacity = payload.capacity;
      delete state.errors.researchArchive;
      restoreResearchRequest();
      repaintResearch();
    } catch (error) {
      if (currentResearchArchive(page) && !isCancelled(error)) page.error = error;
    } finally {
      page.busy = false;
      renderResearchArchive(page);
    }
  };
  const openResearchEvidence = async () => {
    if (enterRouteScreen("strategies", "evidence", {})) return;
    if (!requireUser()) return;
    const generation = state.generation;
    openDialog(T("Дополнительные источники исследования"), U.loading(T("Загрузка…")));
    const sequence = state.eventRequest;
    const current = () => generation === state.generation && sequence === state.eventRequest && $("#workspace-dialog").open;
    try {
      const payload = await api("/api/research/evidence");
      if (!current()) return;
      openDialog(T("Дополнительные источники исследования"), `<form id="research-evidence-form" data-version="${payload.version}"><p class="notice">${H("Данные, которых нет у подключённых источников, можно импортировать в свой аккаунт. Для каждого факта нужны значение, реальная дата его доступности и ссылка на источник. Загруженные сведения обозначаются как предоставленные вами; ссылка сама по себе не подтверждает достоверность.")}</p><label class="field"><span>${H("research.evidence_file")}</span><input type="file" name="evidence_file" accept="application/json,.json"></label><label class="field section-gap"><span>${H("Документ исходных данных")}</span><textarea name="document" rows="14" maxlength="16777216" required spellcheck="false"></textarea></label><details><summary class="details-summary">${H("Состав документа")}</summary><p class="fine-print">${H("research.evidence_structure")}</p></details><div class="form-actions"><button class="button primary" type="submit">${H("Проверить и сохранить данные")}</button><button class="button secondary" type="button" data-close-dialog>${H("Закрыть")}</button></div><output class="form-message" id="evidence-message"></output></form>`);
      const form = $("#research-evidence-form");
      form.elements.document.value = JSON.stringify(payload.document || {assets: []});
      form.elements.evidence_file.addEventListener("change", async event => {
        const file = event.target.files?.[0];
        if (!file) return;
        if (file.size > 16 * 1024 * 1024) { showMessage($("#evidence-message"), T("research.evidence_too_large"), true); return; }
        const text = await file.text();
        if (generation === state.generation && form.isConnected) form.elements.document.value = text;
      });
    } catch (error) { if (current() && !isCancelled(error)) openDialog(T("Дополнительные источники исследования"), `<p class="notice error">${esc(humanError(error))}</p><button class="button secondary" data-research-action="evidence">${H("Повторить загрузку")}</button>`); }
  };
  const saveResearchEvidence = async form => {
    if (!requireUser() || form.dataset.busy === "true") return;
    const generation = state.generation;
    form.dataset.busy = "true";
    const control = form.querySelector('[type="submit"]');
    control.disabled = true;
    try {
      const document = JSON.parse(form.elements.document.value);
      if (new TextEncoder().encode(JSON.stringify(document)).length > 16 * 1024 * 1024) throw new Error("research_evidence_too_large");
      const saved = await api("/api/research/evidence", {method: "PUT", body: {document, expected_version: Number(form.dataset.version)}});
      if (generation !== state.generation || !form.isConnected) return;
      form.dataset.version = saved.version;
      form.elements.document.value = JSON.stringify(saved.document);
      state.strategy.research = null;
      state.researchDisplaySequence = (state.researchDisplaySequence || 0) + 1;
      repaintResearch();
      showMessage($("#evidence-message", form), T("Исходные данные сохранены. Запустите новое исследование, чтобы использовать эту версию."));
    } catch (error) { if (!isCancelled(error) && generation === state.generation && form.isConnected) showMessage($("#evidence-message", form), error instanceof SyntaxError ? T("Файл содержит некорректный JSON. Проверьте формат.") : `${humanError(error)} ${T("Проверьте сохранённую версию перед повторной отправкой.")}`, true); }
    finally { form.dataset.busy = "false"; control.disabled = false; }
  };
  const researchArchiveAction = async control => {
    if (!requireUser()) return;
    const id = safeSegment(control.dataset.researchRun);
    const action = control.dataset.researchOperation;
    const generation = state.generation;
    const sequence = state.eventRequest;
    const fromDialog = Boolean(control.closest("#dialog-content"));
    const current = () => generation === state.generation && sequence === state.eventRequest && (!fromDialog || $("#workspace-dialog").open);
    control.disabled = true;
    try {
      if (action === "delete") {
        await api(`/api/research/runs/${id}`, {method: "DELETE"});
        if (current()) {
          if (state.strategy.research?.archive?.id === control.dataset.researchRun) state.strategy.research = null;
          await openResearchArchive();
        }
        return;
      }
      const payload = await api(`/api/research/runs/${id}${action === "replay" ? "/replay" : ""}`, action === "replay" ? {method: "POST", body: {}, timeout: 60000} : {});
      if (!current()) return;
      presentArchivedResearch(payload, action);
    } catch (error) { if (current() && !isCancelled(error)) toast(humanError(error), true); }
    finally { if (control.isConnected) control.disabled = false; }
  };
  const presentArchivedResearch = (payload, action) => {
      if (action === "replay") { toast(payload.verified ? T("Расчёт повторён по сохранённым данным. Результат и контрольная сумма совпадают.") : T("Повторяемость не подтверждена."), !payload.verified); return; }
      if (action === "export") {
        const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"}));
        const link = document.createElement("a");
        link.href = url; link.download = `omnicio-research-${payload.id}.json`; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        return;
      }
      state.researchDisplaySequence = (state.researchDisplaySequence || 0) + 1;
      state.strategy.research = {...payload.result, archive: {id: payload.id, created_at: payload.created_at, strategy_version: payload.strategy_version}};
      navigate("strategies", {screen: "result", run: payload.id});
  };
  const executionPlannerCard = () => `<section class="card"><h3 class="panel-title">${H("execution.title")}</h3><p class="fine-print">${H("execution.help")}</p><div class="form-actions">${button(T("execution.prepare"), "execution-plan", {primary: true, extra: strategySaveUnavailable(state.strategy) || state.executionBusy ? "disabled" : ""})}${button(T("execution.history"), "execution-history")}</div></section>`;
  const executionProblem = code => ({
    execution_planning_read_budget_exhausted: T("execution.error.read_budget"),
    execution_policy_incomplete: T("execution.error.policy"),
    execution_current_research_required: T("execution.error.research"),
    execution_refresh_snapshot_required: T("execution.error.snapshot"),
    execution_connection_required: T("execution.error.connection"),
    execution_quote_incomplete_or_stale: T("execution.error.quote"),
    execution_quote_expired_during_plan: T("execution.error.quote"),
    execution_quote_moved_outside_limit: T("execution.error.moved"),
    execution_provider_cost_exceeds_cap: T("execution.error.cost"),
    execution_proposal_expired: T("execution.error.expired"),
    execution_deployment_disabled: T("execution.error.disabled"),
    execution_research_evidence_changed: T("execution.error.evidence"),
    execution_portfolio_changed: T("execution.error.portfolio"),
    execution_free_cash_changed: T("execution.error.portfolio"),
    execution_held_evidence_missing: T("execution.error.held"),
    execution_instrument_permission_unverified: T("execution.error.permission"),
  })[code];
  const executionError = error => executionProblem(error.code || error.message) || humanError(error);
  const openExecutionPlanner = async () => {
    if (enterRouteScreen("strategies", "plan", {})) return;
    if (!requireUser() || state.executionBusy) return;
    if (strategySaveUnavailable(state.strategy)) {
      toast(T("execution.save_first"), true);
      return;
    }
    const generation = state.generation;
    const version = state.strategy.server.version;
    openDialog(T("execution.title"), U.loading(T("execution.loading")));
    const sequence = state.eventRequest;
    state.executionPlan = null;
    let results;
    try { results = await Promise.all([readResearchChoices(), api("/api/portfolio/execution-capabilities")]); }
    catch (error) {
      if (generation === state.generation && sequence === state.eventRequest && !isCancelled(error)) openDialog(T("execution.title"), `<p class="notice error">${esc(humanError(error))}</p>${button(T("Повторить"), "route-retry")}`);
      return;
    }
    if (generation !== state.generation || sequence !== state.eventRequest || !$("#workspace-dialog").open) return;
    const [archive, caps] = results;
    state.data.executionCapabilities = caps;
    const runs = (archive.items || []).filter(item => item.strategy_version === version && item.status === "computed");
    if (!runs.length) {
      openDialog(T("execution.title"), `<p class="notice">${H("execution.no_research")}</p>`);
      return;
    }
    openDialog(T("execution.title"), `<form id="execution-plan-form" data-strategy-version="${version}"><p class="notice">${H("execution.shadow_notice")}</p>${select("research_run_id", T("execution.research"), runs.map(item => [item.id, date(item.created_at, true) + " · " + percent(item.metrics?.net_return_percent)]), runs[0].id)}<p class="fine-print">${H("execution.inputs")}</p>${infoRows([[T("execution.order_cap"), money(caps.max_order_notional_rub)], [T("execution.daily_cap"), money(caps.max_daily_notional_rub)], [T("execution.validity"), T("execution.two_minutes")]])}<div class="form-actions"><button class="button primary" type="submit">${H("execution.calculate")}</button>${button(T("execution.refresh_snapshot"), "workspace-refresh")}</div><output id="execution-plan-message" class="form-message"></output></form>`);
  };
  const executionPlanLegHTML = leg => `<article class="recovery-leg"><h3>${esc(leg.action === "buy" ? T("Покупка") : T("Продажа"))} · ${esc(leg.ticker || leg.instrument_uid)}</h3>${infoRows([[T("execution.lots"), format(leg.lots, 0)], [T("execution.lot_size"), format(leg.lot_size, 0)], [T("execution.limit"), money(leg.limit_price, 4, "RUB", false)], [T("execution.gross"), money(leg.gross_amount_rub)], [T("execution.commission"), money(leg.commission_cap_rub)], [T("execution.tax"), money(leg.tax_reserve_rub)]])}</article>`;
  const executionPlanHTML = plan => {
    const payload = plan.payload;
    return `<p class="notice">${H("execution.shadow_notice")}</p>${infoRows([[T("execution.nav"), money(payload.nav_rub)], [T("execution.cash_before"), money(payload.cash_before_rub)], [T("execution.cash_after"), money(payload.cash_after_rub)], [T("execution.reserve"), money(payload.reserve_rub)], [T("execution.turnover"), money(payload.gross_turnover_rub)], [T("execution.expires"), date(plan.expires_at, true)]])}<div class="recovery-legs">${payload.legs.map(executionPlanLegHTML).join("")}</div><p class="fine-print">${H("execution.quoted")}</p><label class="check-field section-gap"><input id="execution-review-consent" type="checkbox"><span>${H("execution.review_consent")}</span></label><div class="form-actions">${button(T("execution.confirm"), "execution-confirm", {primary: true})}${button(T("execution.recalculate"), "execution-plan")}</div><output id="execution-plan-message" class="form-message"></output>`;
  };
  const displayExecutionPlan = result => {
    if (result.status !== "blocked" && result.status !== "no_change") {
      state.executionPlan = result;
      openDialog(T("execution.review"), executionPlanHTML(result));
      return;
    }
    const items = (result.blockers || []).map(code => `<li>${esc(executionProblem(code) || code)}</li>`).join("");
    const blockers = items ? `<ul class="source-list">${items}</ul>` : "";
    openDialog(T("execution.title"), `<p class="notice">${esc(result.status === "no_change" ? T("execution.no_change") : T("execution.blocked"))}</p>${blockers}`);
  };
  const setPlanFormDisabled = (form, disabled) => {
    for (const control of $$("button", form)) control.disabled = disabled;
  };
  const calculateExecutionPlan = async form => {
    if (!requireUser() || state.executionBusy || !form.reportValidity()) return;
    const generation = state.generation;
    const sequence = state.eventRequest;
    const current = () => generation === state.generation && sequence === state.eventRequest && form.isConnected && $("#workspace-dialog").open;
    state.executionBusy = true;
    setPlanFormDisabled(form, true);
    try {
      const archive = await api(`/api/research/runs/${safeSegment(form.elements.research_run_id.value)}`);
      if (!current()) return;
      const result = await api("/api/portfolio/proposals/plan", {method: "POST", timeout: 65000, body: {
        expected_version: Number(form.dataset.strategyVersion), research_run_id: archive.id,
        commission_bps: archive.inputs.commission_bps, slippage_bps: archive.inputs.slippage_bps,
        mode: "shadow"
      }});
      if (!current()) return;
      displayExecutionPlan(result);
    } catch (error) {
      if (current() && !isCancelled(error)) showMessage($("#execution-plan-message"), executionError(error), true);
    } finally {
      if (generation === state.generation) state.executionBusy = false;
      if (form.isConnected) setPlanFormDisabled(form, false);
    }
  };
  const confirmExecutionPlan = async control => {
    if (!requireUser() || state.executionBusy || !state.executionPlan) return;
    if (!$("#execution-review-consent")?.checked) {
      showMessage($("#execution-plan-message"), T("execution.consent_required"), true);
      return;
    }
    const plan = state.executionPlan;
    const generation = state.generation;
    const sequence = state.eventRequest;
    state.executionBusy = true;
    control.disabled = true;
    try {
      const result = await api(`/api/portfolio/proposals/${safeSegment(plan.id)}/confirm`, {method: "POST", body: {
        proposal_version: plan.version, proposal_hash: plan.proposal_hash,
        expected_strategy_version: plan.payload.strategy_version
      }});
      if (generation !== state.generation) return;
      state.executionPlan = null;
      if (sequence === state.eventRequest && $("#workspace-dialog").open) {
        openDialog(T("execution.title"), U.loading(T("execution.loading")));
        state.recovery.id = result.run.id;
        await readRecoveryDetails(recoveryContext());
      }
      await reloadRecovery();
    } catch (error) {
      if (generation === state.generation && sequence === state.eventRequest && !isCancelled(error)) showMessage($("#execution-plan-message"), executionError(error), true);
    } finally {
      if (generation === state.generation) state.executionBusy = false;
      if (control.isConnected) control.disabled = false;
    }
  };
  const openExecutionHistory = async () => {
    if (enterRouteScreen("strategies", "executions", {})) return;
    if (!requireUser()) return;
    const generation = state.generation;
    openDialog(T("execution.history"), U.loading(T("execution.loading")));
    const sequence = state.eventRequest;
    await reloadRecovery();
    if (generation === state.generation && sequence === state.eventRequest && $("#workspace-dialog").open) openDialog(T("execution.history"), recoveryPanelHTML());
  };
  const dispatchExecutionLeg = async () => {
    const record = state.recovery.record;
    const next = nextExecutionLeg(record);
    if (!requireUser() || state.recovery.busy || state.recovery.uncertain || record?.mode !== "shadow" || next?.status !== "pending") return;
    const context = recoveryContext();
    state.recovery.busy = true;
    updateRecoveryControls();
    try {
      await api(`/api/portfolio/executions/${safeSegment(record.id)}/dispatch`, {method: "POST", timeout: 60000, body: {expected_leg_id: next.id}});
      if (currentRecovery(context)) await readRecoveryDetails(context);
      if (context.generation === state.generation) await reloadRecovery();
    } catch (error) {
      if (currentRecovery(context) && !isCancelled(error)) {
        state.recovery.uncertain = true;
        showMessage($("#recovery-message"), executionError(error) + " " + T("execution.read_after_error"), true);
      }
    } finally {
      if (context.generation === state.generation && context.sequence === state.recovery.sequence && context.id === state.recovery.id) state.recovery.busy = false;
      if (currentRecovery(context)) updateRecoveryControls();
    }
  };

  const goalReason = goal => {
    const source = {
      portfolio: T("Выделенная доля портфеля"),
      income: T("Полученные выплаты до налоговых списаний"),
      manual: T("Сумма указана вами")
    }[goal.progress_source] || T("Источник прогресса");
    return number(goal.progress?.amount_rub) === null ? T("Источник ещё не предоставил данные для расчёта прогресса.") : source;
  };
  const renderGoals = () => {
    captureScreenDrafts();
    const allGoals = state.tour ? [] : state.data.goals?.items || [];
    const selected = state.route.screen === "archive" ? "archive" : state.route.filter || "active";
    const goals = allGoals.filter(goal => selected === "all" || selected === "archive" ? (selected === "all" || goal.status !== "active") : goal.status === selected);
    let content = renderGoalsValue6(goals);
    if (state.loading.has("goals") && !state.data.goals) content = U.loading(T("state.loading"));
    else if (state.errors.goals) content = dataError("goals");
    $("#view-goals").innerHTML = `${heading(T("Цели"), T("Капитал, сроки и прогресс из выбранного источника"), button(T("Добавить цель"), "goal-create", {
      primary: true
    }) + button(T("Обновить"), "refresh", {
      small: true
    }))}${screenLinks("goals", [["", T("goals.active")], ["archive", T("goals.archive")]])}${content}<p class="notice section-gap">${H("Доли активных целей проверяет сервер. Прогресс по портфелю зависит от стоимости счёта; выплаты учитываются до отдельных налоговых списаний.")}</p>`;
    applyScreenLayout("goals");
  };
  const goalForecastHTML = forecast => {
    if (!forecast) return ("<p class=\"notice\">" + H("Задайте собственные предположения и сохраните план для расчёта.") + "</p>");
    const source = {portfolio: T("Выделенная доля портфеля"), income: T("Полученные выплаты до налоговых списаний"), manual: T("Сумма указана вами")}[forecast.source_kind] || T("Источник прогресса");
    const sourceHTML = `<div class="goal-forecast-source">${infoRows([[T("goals.source_amount"), money(forecast.source_amount_rub)], [T("goals.calculated_at"), date(forecast.as_of)]])}${freshness(source, forecast.source_as_of, forecast.source_status)}</div>`;
    if (forecast.status !== "available") {
      const message = {goal_target_date_required: T("Укажите дату достижения в настройках цели."), goal_progress_unavailable: T("Для расчёта нужен подтверждённый текущий прогресс."), goal_progress_stale: T("goals.source_stale"), goal_plan_horizon_out_of_range: T("Выберите будущий срок не более 30 лет.")}[forecast.reason] || T("Данных для расчёта пока недостаточно.");
      const refresh = forecast.status === "source_stale" ? `<div class="form-actions">${button(T("goals.refresh_source"), "portfolio", {route: true, small: true})}</div>` : "";
      return `${sourceHTML}<p class="notice warning">${esc(message)}</p>${refresh}`;
    }
    const simulation = forecast.simulation;
    const probabilityModel = simulation ? `<h3 class="panel-title section-gap">${H("Условная модель вероятности")}</h3>${infoRows([[T("Достигнуто в модельных траекториях"), percent(simulation.conditional_probability_percent)], [T("Точность моделирования, интервал 95%"), simulation.sampling_interval_95_percent.map(value => percent(value)).join(" — ")], [T("10-й процентиль суммы"), money(simulation.terminal_percentiles_rub["10"])], [T("Медиана суммы"), money(simulation.terminal_percentiles_rub["50"])], [T("90-й процентиль суммы"), money(simulation.terminal_percentiles_rub["90"])]])}<p class="notice warning">${H("Это доля успешных траекторий при ваших предположениях, а не установленная вероятность будущей прибыли. Модель использует независимые логнормальные доходности; кризисы, дефолты и изменение связей между активами в неё не входят. Интервал отражает только погрешность симуляции.")}</p>` : "";
    return `${sourceHTML}${chart(forecast.scenario_path || [], {timeKey: "month", valueKey: "amount_rub", xKind: "model_month", label: T("goals.scenario"), comparison: [{key: "target_rub", label: T("goals.scenario_target")}, {key: "contributions_rub", label: T("goals.scenario_contributions")}]})}<p class="fine-print">${H("goals.scenario_notice")}</p>${infoRows([[T("Расчётный срок, месяцев"), format(forecast.months, 0)], [T("Целевая сумма с инфляцией"), money(forecast.inflation_adjusted_target_rub)], [T("Сумма в заданном сценарии"), money(forecast.projected_amount_rub)], [forecast.required_monthly_kind === "income" ? T("Необходимые поступления в месяц") : T("Необходимый взнос в месяц"), money(forecast.required_monthly_rub)], [T("Месяцев до цели в сценарии"), forecast.deterministic_months_to_target ?? T("За выбранный срок не достигается")]])}${probabilityModel}<p class="fine-print">${H("Поступления — в конце месяца, оставшаяся часть текущего месяца считается отдельным периодом. Доходность задана после издержек. Для цели по выплатам рост стоимости капитала не считается доходом.")}</p>`;
  };
  const openGoalPlan = async id => {
    if (enterRouteScreen("goals", "plan", {goal_id: id})) return;
    if (!requireUser()) return;
    const generation = state.generation;
    openDialog(T("План достижения цели"), U.loading(T("state.loading")));
    const sequence = state.eventRequest;
    try {
      const saved = await api(`/api/goals/${safeSegment(id)}/plan`);
      if (generation !== state.generation || sequence !== state.eventRequest || !$("#workspace-dialog").open) return;
      const doc = saved.document || {};
      const kind = saved.goal_kind || (state.data.goals?.items || []).find(goal => goal.id === id)?.kind || "capital";
      const applicable = new Set(saved.applicable_fields || (kind === "income" ? ["monthly_income_rub", "annual_inflation_percent"] : ["monthly_contribution_rub", "annual_return_percent", "annual_volatility_percent", "annual_inflation_percent"]));
      const fields = [["monthly_contribution_rub", T("Ежемесячный взнос в капитал, ₽"), 0, 1000000000000], ["monthly_income_rub", T("Ежемесячные выплаты для цели по доходу, ₽"), 0, 1000000000000], ["annual_return_percent", T("Годовой темп роста после издержек, %"), -99, 100], ["annual_volatility_percent", T("Годовая волатильность для модели, %"), 0, 200], ["annual_inflation_percent", T("Предполагаемая инфляция, %"), -20, 100]].filter(([name]) => applicable.has(name));
      openDialog(T("План достижения цели"), `<form id="goal-plan-form" data-id="${esc(id)}" data-kind="${esc(kind)}" data-version="${saved.version}" data-goal-version="${saved.goal_version}"><p class="notice">${H("Введите собственные сценарные предположения. Эти поля не являются прогнозом OMNICIO. Ноль также нужно указать явно.")}</p>${U.switchControl("target_in_today_money", T("Цель в сегодняшних ценах"), T("Будущая целевая сумма увеличивается на заданную инфляцию."), doc.target_in_today_money ?? true)}<div class="field-grid">${fields.map(([name, label, min, max]) => field({name, label, type: "number", min, max, step: "0.0001", required: name !== "annual_volatility_percent", value: doc[name] ?? ""})).join("")}</div><div class="form-actions"><button class="button primary" type="submit">${H("Сохранить и рассчитать")}</button><button class="button secondary" type="button" data-close-dialog>${H("navigation.back")}</button></div><output class="form-message" id="goal-plan-message"></output><section id="goal-plan-result" class="section-gap">${goalForecastHTML(saved.forecast)}</section></form>`);
      updateGoalPlanFields();
    } catch (error) { if (generation === state.generation && sequence === state.eventRequest && !isCancelled(error)) openDialog(T("state.load_failed"), `<p class="notice error">${esc(humanError(error))}</p>${button(T("Повторить загрузку"), "route-retry")}`); }
  };
  function updateGoalPlanFields() {
    const form = $("#goal-plan-form");
    const inflation = form?.elements.annual_inflation_percent;
    if (inflation) { inflation.disabled = !form.elements.target_in_today_money.checked; inflation.required = !inflation.disabled; inflation.closest(".field").hidden = inflation.disabled; }
  }
  const saveGoalPlan = async form => {
    if (!requireUser() || form.dataset.busy === "true" || !form.reportValidity()) return;
    form.dataset.busy = "true";
    const generation = state.generation;
    const sequence = state.eventRequest;
    const current = () => generation === state.generation && sequence === state.eventRequest && form.isConnected && $("#workspace-dialog").open;
    const data = new FormData(form);
    const document = Object.fromEntries(["monthly_contribution_rub", "monthly_income_rub", "annual_return_percent", "annual_volatility_percent", "annual_inflation_percent"].filter(key => data.has(key) && data.get(key) !== "").map(key => [key, data.get(key)]));
    document.target_in_today_money = data.has("target_in_today_money");
    const controls = Array.from(form.elements, control => [control, control.disabled]);
    for (const [control] of controls) control.disabled = true;
    try {
      const saved = await api(`/api/goals/${safeSegment(form.dataset.id)}/plan`, {method: "PUT", body: {document, expected_version: Number(form.dataset.version), expected_goal_version: Number(form.dataset.goalVersion)}});
      if (!current()) return;
      form.dataset.version = saved.version;
      form.dataset.goalVersion = saved.goal_version;
      clearScreenDraft(form);
      $("#goal-plan-result", form).innerHTML = goalForecastHTML(saved.forecast);
      U.bindCharts(form);
      showMessage($("#goal-plan-message", form), saved.forecast?.status === "available" ? T("План сохранён; расчёт использует показанные предположения.") : T("goals.saved_without_forecast"));
    } catch (error) {
      if (!isCancelled(error) && current()) showMessage($("#goal-plan-message", form), `${humanError(error)} ${T("При конфликте или неопределённом результате закройте окно и откройте сохранённый план снова.")}`, true);
    } finally {
      form.dataset.busy = "false";
      if (current()) for (const [control, disabled] of controls) control.disabled = disabled;
    }
  };
  const localToday = () => new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Moscow",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(new Date());
  const goalDocument = goal => goal ? Object.fromEntries(["title", "kind", "target_amount_rub", "target_date", "start_date", "progress_source", "allocation_percent", "manual_amount_rub", "status"].map(key => [key, goal[key]])) : {
    title: "",
    kind: "capital",
    target_amount_rub: "",
    target_date: null,
    start_date: localToday(),
    progress_source: "portfolio",
    allocation_percent: "",
    manual_amount_rub: null,
    status: "active"
  };
  const openGoal = (id = "") => {
    if (enterRouteScreen("goals", id ? "edit" : "create", {goal_id: id})) return;
    if (!requireUser()) return;
    const goal = (state.data.goals?.items || []).find(item => item.id === id);
    if (id && !goal) {
      toast(T("Цель не найдена. Обновите список."), true);
      return;
    }
    const document = goalDocument(goal);
    openDialog(goal ? T("Настройка цели") : T("Новая цель"), `<form id="goal-form" class="goal-form" data-goal-id="${esc(id)}" data-goal-version="${goal?.version || 0}">${field({
      name: "title",
      label: T("Название цели"),
      value: document.title,
      required: true,
      placeholder: T("Что вы хотите осуществить?")
    })}<div class="field-grid">${select("kind", T("Тип цели"), [["capital", T("Накопить капитал")], ["income", T("Получить выплаты")]], document.kind)}${field({
      name: "target_amount_rub",
      label: T("Целевая сумма, ₽"),
      type: "number",
      min: ".00000001",
      max: "1000000000000",
      step: "any",
      value: document.target_amount_rub,
      required: true
    })}${field({
      name: "start_date",
      label: T("Начало отсчёта"),
      type: "date",
      value: document.start_date,
      required: true
    })}${field({
      name: "target_date",
      label: T("Плановая дата"),
      type: "date",
      value: document.target_date || "",
      hint: T("Можно оставить пустой")
    })}${select("progress_source", T("Источник прогресса"), [[document.kind === "income" ? "income" : "portfolio", document.kind === "income" ? T("Полученные выплаты") : T("Часть портфеля")], ["manual", T("Указать вручную")]], document.progress_source)}${select("status", T("Состояние"), [["active", T("Активная")], ["completed", T("Завершена")], ["archived", T("В архиве")]], document.status)}${field({
      name: "allocation_percent",
      label: T("Доля источника, %"),
      type: "number",
      min: ".00000001",
      max: "100",
      step: "any",
      value: document.allocation_percent || "",
      helpText: T("Какая доля портфеля или подтверждённых выплат относится к этой цели. Общая доля активных целей не может превышать 100%.")
    })}${field({
      name: "manual_amount_rub",
      label: T("Уже накоплено вручную, ₽"),
      type: "number",
      min: "0",
      max: "1000000000000",
      step: "any",
      value: document.manual_amount_rub ?? "",
      helpText: T("Сумма, которую вы подтверждаете сами. Она не выдаётся за полученную из брокерского API.")
    })}</div><p id="goal-source-note" class="fine-print"></p><div class="form-actions"><button class="button primary" type="submit">${goal ? T("Сохранить цель") : T("Создать цель")}</button><button class="button secondary" type="button" data-close-dialog>${H("Отмена")}</button></div><output id="goal-message" class="form-message"></output></form>`);
    updateGoalFields();
  };
  const updateGoalFields = (kindChanged = false) => {
    const form = $("#goal-form");
    if (!form) return;
    const kind = form.elements.kind.value;
    const source = form.elements.progress_source;
    if (kindChanged) {
      const isManual = source.value === "manual";
      source.innerHTML = `<option value="${kind === "income" ? "income" : "portfolio"}">${kind === "income" ? T("Полученные выплаты") : T("Часть портфеля")}</option><option value="manual">${H("Указать вручную")}</option>`;
      if (isManual) source.value = "manual";
    }
    const manual = source.value === "manual";
    form.elements.allocation_percent.disabled = manual;
    form.elements.allocation_percent.required = !manual;
    form.elements.manual_amount_rub.disabled = !manual;
    form.elements.manual_amount_rub.required = manual;
    $("#goal-source-note").textContent = manual ? T("Вы явно задаёте накопленную сумму. Её можно обновить в любое время.") : renderUpdateGoalFieldsValue(kind);
  };
  const goalWriteNeedsReadback = error => (error.code || error.message) === "updated_legal_consent_required" || !error.definite && (!error.status || error.status >= 500);
  const reportGoalSaveError = (form, error) => {
    if (!isCancelled(error)) {
      const message = form.querySelector("#goal-message");
      if (!message) return;
      showMessage(message, humanError(error), true);
      if (goalWriteNeedsReadback(error)) {
        form.dataset.uncertain = "true";
        message.innerHTML = `${esc(humanError(error))}<p>${H("Результат сохранения не подтверждён. Проверьте список целей перед повтором.")}</p><div class="form-actions">${button(T("Проверить список"), "goal-reconcile", {
          small: true
        })}</div><p data-goal-readback-status></p>`;
      }
    }
  };
  const mergeGoalList = payload => {
    if (!Array.isArray(payload?.items)) throw Object.assign(new Error("invalid_server_response"), {
      status: 502
    });
    return {
      ...payload,
      items: U.mergeGoals(payload.items, state.data.goals?.items || [], state.deletedGoalIds)
    };
  };
  const replaceGoalList = items => {
    state.resourceVersions.set("goals", (state.resourceVersions.get("goals") || 0) + 1);
    state.loading.delete("goals");
    delete state.errors.goals;
    state.data.goals = mergeGoalList({
      items
    });
  };
  const acceptSavedGoal = (saved, form) => {
    const id = form.dataset.goalId;
    if (typeof saved?.id !== "string" || !saved.id || id && saved.id !== id || !Number.isInteger(saved.version) || saved.version <= Number(form.dataset.goalVersion)) throw Object.assign(new Error("invalid_server_response"), {
      status: 502
    });
    if (state.deletedGoalIds.has(saved.id)) return false;
    const current = state.data.goals?.items || [];
    if (current.some(goal => goal.id === saved.id && goal.version > saved.version)) return false;
    const items = current.map(goal => goal.id === saved.id ? saved : goal);
    if (!current.some(goal => goal.id === saved.id)) items.push(saved);
    replaceGoalList(items);
    clearScreenDraft(form);
    return true;
  };
  const renderGoalConsumers = () => {
    if (["goals", "home"].includes(state.view)) renderCurrent();
  };
  const refreshGoalList = async generation => {
    await loadResource("goals", "/api/goals", {
      force: true
    });
    if (generation === state.generation) renderGoalConsumers();
  };
  const reconcileGoals = async control => {
    if (!requireUser() || control.disabled) return;
    const generation = state.generation;
    const dialog = $("#workspace-dialog");
    const status = control.closest("output")?.querySelector("[data-goal-readback-status]");
    const label = control.textContent;
    control.disabled = true;
    control.textContent = T("Проверяем…");
    showMessage(status, "");
    try {
      const payload = await loadResource("goals", "/api/goals", {
        force: true
      });
      if (generation !== state.generation || !control.isConnected || !dialog.open) return;
      if (!payload) {
        const error = state.errors.goals;
        showMessage(status, error ? humanError(error) : T("Проверка списка не завершена. Повторите чтение."), true);
        return;
      }
      renderGoalConsumers();
      dialog.close();
      navigate("goals");
    } finally {
      if (generation === state.generation && control.isConnected) {
        control.disabled = false;
        control.textContent = label;
      }
    }
  };
  const writeGoalDocument = (form, document) => {
    const id = form.dataset.goalId;
    const path = id ? `/api/goals/${safeSegment(id)}` : "/api/goals";
    return api(path, {
      method: id ? "PUT" : "POST",
      body: id ? {
        expected_version: Number(form.dataset.goalVersion),
        document
      } : {
        document
      }
    });
  };
  const saveGoal = async form => {
    if (!requireUser() || form.dataset.busy === "true" || form.dataset.uncertain === "true" || !form.reportValidity()) return;
    const controls = form.elements;
    const source = controls.progress_source.value;
    const document = {
      title: controls.title.value.trim(),
      kind: controls.kind.value,
      target_amount_rub: controls.target_amount_rub.value,
      target_date: controls.target_date.value || null,
      start_date: controls.start_date.value,
      progress_source: source,
      allocation_percent: source === "manual" ? null : controls.allocation_percent.value,
      manual_amount_rub: source === "manual" ? controls.manual_amount_rub.value : null,
      status: controls.status.value
    };
    if (document.target_date && document.target_date < document.start_date) {
      showMessage($("#goal-message"), T("Плановая дата не может быть раньше начала отсчёта."), true);
      return;
    }
    const submit = form.querySelector("[type=submit]");
    submit.disabled = true;
    form.dataset.busy = "true";
    const generation = state.generation;
    try {
      const saved = await writeGoalDocument(form, document);
      if (generation !== state.generation) return;
      const accepted = acceptSavedGoal(saved, form);
      renderGoalConsumers();
      if (form.isConnected) $("#workspace-dialog").close();
      if (accepted) toast(T("Цель сохранена на сервере."));
      await refreshGoalList(generation);
    } catch (error) {
      reportGoalSaveError(form, error);
    } finally {
      delete form.dataset.busy;
      if (form.isConnected && generation === state.generation) submit.disabled = form.dataset.uncertain === "true";
    }
  };
  const confirmGoalDelete = id => {
    if (!requireUser()) return;
    const goal = state.data.goals?.items?.find(item => item.id === id);
    if (!goal) return;
    openDialog(T("Удалить цель?"), `<p class="help-copy">${H("Цель «")}${esc(goal.title)}${H("» будет удалена из вашего аккаунта. Данные брокерского счёта это действие не изменяет.")}</p><div class="form-actions"><button class="button danger" data-goal-delete-confirm="${esc(goal.id)}" data-version="${goal.version}">${H("Удалить цель")}</button><button class="button secondary" data-close-dialog>${H("Отмена")}</button></div><output id="goal-delete-message" class="form-message"></output>`);
  };
  const reportGoalDeleteError = (control, error) => {
    if (!control.isConnected || isCancelled(error)) return;
    const message = $("#goal-delete-message");
    if (!message) return;
    showMessage(message, humanError(error), true);
    control.disabled = !error.definite;
    if (!error.definite) message.innerHTML = `${esc(humanError(error))}<div class="form-actions">${button(T("Проверить список"), "goal-reconcile", {
      small: true
    })}</div><p data-goal-readback-status></p>`;
  };
  const eventNewsArchiveHTML = () => {
    if (state.tour) return "";
    if (state.tour) return "";
    const archive = state.data.marketArchive;
    const articles = (archive?.items || []).map(archiveNewsItem).join("") || ("<p class=\"notice\">" + H("В загруженной части архива публикаций нет.") + "</p>");
    const content = state.errors.marketArchive ? dataError("marketArchive") : `<div class="event-list">${articles}</div>`;
    const previous = archive?.next_cursor ? button(T("Предыдущие публикации"), "news-more", {small: true, extra: state.loading.has("news-more") ? " disabled" : ""}) : "";
    return `<section class="card section-gap"><h2 class="panel-title">${H("Архив новостей источника")}</h2>${content}${previous}</section>`;
  };
  const renderEvents = () => {
    captureScreenDrafts();
    const data = state.tour ? null : state.data.events;
    const unread = state.tour ? 0 : number(state.data.eventSummary?.unread_total ?? data?.unread_count) || 0;
    const previousEvents = data?.next_cursor ? `<div class="form-actions">${button(T("Загрузить предыдущие события"), "events-more", {small: true, extra: state.loading.has("events-more") ? " disabled" : ""})}</div>` : "";
    $("#view-events").innerHTML = `${heading(T("События"), T("Подтверждённые изменения портфеля, выплат и целей"), button(T("Обновить"), "refresh", {
      small: true
    }) + (unread ? button(T("Прочитать все"), "events-read-all", {
      small: true
    }) : ""))}<section class="card"><div class="card-header"><h2>${H("Лента событий")}</h2><span class="chip">${unread} ${H("непрочитанных")}</span></div>${eventFilters()}${state.errors.events ? dataError("events") : eventsHTML(false)}${previousEvents}<p class="data-footnote">${H("«Прочитать все» охватывает историю до последнего полученного состояния. Пришедшие позже события остаются непрочитанными.")}</p></section>${eventNewsArchiveHTML()}${data?.alerts_suppressed ? ("<p class=\"notice section-gap\">" + H("Сейчас действуют тихие часы. События доступны в ленте; внешняя доставка отложена до их окончания.") + "</p>") : ""}<div class="notice section-gap">${H("Push на устройство и письма включаются отдельно после вашего согласия. Их доступность и результат отправки видны в настройках. SMS не используется.")}<div class="form-actions">${button(T("Настроить уведомления"), "settings", {
      route: true,
      small: true
    })}</div></div>${data?.digest?.frequency && data.digest.frequency !== "off" ? renderEventsCard(data) : ""}`;
    applyScreenLayout("events");
  };
  const markEvents = async ids => {
    if (!requireUser() || !ids.length) return;
    const generation = state.generation;
    try {
      const result = await api("/api/events/read", {
        method: "POST",
        body: {
          ids,
          read: true
        }
      });
      if (generation !== state.generation) return;
      state.eventHistoryExtended = false;
      state.data.events = result;
      scheduleEventSummary(100);
      updateIdentity();
      if (["events", "home"].includes(state.view)) renderCurrent();
    } catch (error) {
      if (!isCancelled(error)) toast(humanError(error), true);
    }
  };
  const readAllEvents = async () => {
    if (!requireUser() || state.loading.has("events-read-all") || !Number.isSafeInteger(state.data.events?.read_all_before)) return;
    const generation = state.generation;
    state.loading.add("events-read-all");
    try {
      const result = await api("/api/events/read-all", {method: "POST", body: {through_revision: state.data.events.read_all_before, category: "all"}});
      if (generation !== state.generation) return;
      state.eventHistoryExtended = false;
      state.data.events = result;
      scheduleEventSummary(100);
      updateIdentity();
      if (["events", "home"].includes(state.view)) renderCurrent();
    } catch (error) {
      if (!isCancelled(error)) toast(humanError(error), true);
    } finally {
      if (generation === state.generation) state.loading.delete("events-read-all");
    }
  };
  const loadEventPage = async (news = false) => {
    const name = news ? "marketArchive" : "events";
    const busy = news ? "news-more" : "events-more";
    const cursor = state.data[name]?.next_cursor;
    if (!cursor || state.loading.has(busy)) return;
    const generation = state.generation;
    state.loading.add(busy);
    renderEvents();
    try {
      const filter = state.eventFilter;
      const page = await api(`${news ? "/api/news?limit=50" : eventsPath()}&cursor=${encodeURIComponent(cursor)}`);
      if (!news && filter !== state.eventFilter) return;
      if (generation !== state.generation) return;
      state.data[name] = mergePage(state.data[name], page);
      if (!news) state.eventHistoryExtended = true;
      delete state.errors[name];
    } catch (error) {
      if (generation === state.generation && !isCancelled(error)) state.errors[name] = error;
    } finally {
      if (generation === state.generation) {
        state.loading.delete(busy);
        if (state.view === "events") renderEvents();
      }
    }
  };
  const eventSourceLabel = type => ({operation: T("Операция брокера"), payout: T("Календарь выплат"), risk: T("Оценка инструмента"), goal: T("Цель"), audit: T("Журнал аккаунта"), job: T("Сбор данных")})[type] || type || T("Серверный факт");
  const eventSourceHTML = event => {
    const source = event.source;
    if (!source || typeof source !== "object") return `<p class="fine-print">${esc(typeof source === "string" ? source : T("Источник не указан"))}</p>`;
    const rows = [[T("Источник"), eventSourceLabel(source.type)]];
    if (source.instrument_uid) rows.push([T("Инструмент"), source.instrument_uid]);
    if (source.amount !== undefined) rows.push([T("Сумма операции"), money(source.amount, 2, source.currency || "")]);
    if (source.amount_per_security != null) rows.push([T("На одну бумагу"), money(source.amount_per_security, 2, source.currency || "", false)]);
    if (source.expected_at) rows.push([T("Плановая дата выплаты"), date(source.expected_at)]);
    if (source.due_date) rows.push([T("Плановая дата цели"), date(source.due_date)]);
    if (source.state || source.status) rows.push([T("Состояние источника"), source.state || source.status]);
    const link = source.url ? `<p class="fine-print">${U.sourceLink(source.url, T("Открыть первоисточник"))}</p>` : "";
    return infoRows(rows) + link;
  };
  const eventDestinationButton = destination => {
    if (!destination || !views.has(destination.view)) return "";
    let label = T("Открыть раздел");
    if (destination.uid) label = T("Открыть инструмент");
    else if (destination.goal_id) label = T("Открыть цель");
    return button(label, "event-destination", {primary: true});
  };
  const openEvent = async id => {
    if (enterRouteScreen("events", "detail", {event: id})) return;
    if (!requireUser() || !/^[a-f0-9]{64}$/.test(id)) return;
    const generation = state.generation;
    openDialog(T("Событие"), U.loading(T("Получаем подтверждённые подробности…")));
    const request = state.eventRequest;
    try {
      const event = await api(`/api/events/${id}`);
      if (generation !== state.generation || request !== state.eventRequest || !$("#workspace-dialog").open) return;
      state.eventDetail = event;
      openDialog(event.title, `<p class="help-copy">${esc(event.detail || T("Подтверждённое событие вашего аккаунта."))}</p><p class="fine-print">${esc(date(event.occurred_at, true))} ${H("МСК")}</p>${eventSourceHTML(event)}${eventDestinationButton(event.destination)}`);
      if (!event.read_at) void markEvents([id]);
    } catch (error) {
      if (generation === state.generation && request === state.eventRequest && $("#workspace-dialog").open && !isCancelled(error)) openDialog(T("Событие недоступно"), `<p class="notice error">${esc(humanError(error))}</p>`);
    }
  };
  const openNews = async (id, source = state.route.news_source || "broker") => {
    if (enterRouteScreen("events", "news", {news: id, news_source: source})) return;
    const sequence = state.navigationSequence;
    const publicSource = state.route.news_source === "public";
    const collections = publicSource ? [] : [state.data.marketArchive, state.searchPages.news, state.asset?.news];
    let item = collections.flatMap(collection => collection?.items || []).find(row => row.id === id);
    if (!item) {
      openDialog(T("Новости"), U.loading(T("state.loading")));
      try { item = await api(`/api/${publicSource ? "public/news" : "news"}/${safeSegment(id)}`); }
      catch (error) {
        if (!isCancelled(error) && sequence === state.navigationSequence) openDialog(T("Новости"), `<p class="notice error">${esc(humanError(error))}</p>${button(T("Повторить"), "route-retry")}`);
        return;
      }
    }
    if (sequence !== state.navigationSequence) return;
    openDialog(item.title, `<p class="fine-print">${esc(item.source || T("Источник брокера"))} · ${esc(date(item.occurred_at || item.published_at, true))} ${H("МСК")}</p><p class="help-copy">${esc(item.content || item.text || item.summary || T("Источник не предоставил полный текст."))}</p>${item.source_url || item.url ? U.sourceLink(item.source_url || item.url, T("Первоисточник")) : ("<p class=\"fine-print\">" + H("Публикация предоставлена API источника; внешняя ссылка отсутствует.") + "</p>")}`);
  };
  const renderAnalytics = () => {
    captureScreenDrafts();
    const ws = workspaceForPeriod(state.analyticsPeriod);
    const performance = ws?.performance || {};
    const income = ws?.income || {};
    const analysis = state.tour ? null : state.data.analysis?.analysis;
    const result = number(performance.investment_result_rub);
    const incomePeriod = income.from ? `${esc(date(income.from))} — ${esc(date(income.to))}<br>` : "";
    $("#view-analytics").innerHTML = `${heading(T("Аналитика"), T("Результат, денежные потоки и полнота исходных данных"), button(T("Обновить"), "refresh", {
      small: true
    }))}${periods("analytics", state.analyticsPeriod)}${!ws ? ("<p class=\"notice\">" + H("Показатели выбранного периода ещё не получены. Расчёты другого периода здесь не отображаются.") + "</p>") : ""}${dataError("workspace")}<div class="metric-grid">${[[T("Финансовый результат"), money(result)], [T("Чистые пополнения"), money(performance.net_contributions_rub)], [T("Полученные выплаты"), money(income.total_rub)], [T("Налоги"), money(performance.taxes_rub)]].map(([label, value]) => renderAnalyticsCard(label, value)).join("")}</div><div class="two-column"><section class="card">${cardHeader(T("Стоимость по наблюдениям"))}${chart(ws?.overview?.history)}${navCoverageHTML(ws?.overview || {}, state.analyticsPeriod)}${freshness("T-Invest", ws?.overview?.observed_at, ws?.overview?.freshness?.status || ws?.overview?.status)}<p class="data-footnote">${H("Изменение стоимости включает движение денег. Доходность не выводится из разницы крайних точек.")}</p></section><section class="card">${cardHeader(T("Из чего складывается результат"))}${infoRows([[T("Стоимость в начале"), money(performance.start_nav_rub)], [T("Стоимость в конце"), money(performance.end_nav_rub)], [T("Изменение стоимости"), money(performance.nav_change_rub)], [T("Чистые пополнения / выводы"), money(performance.net_contributions_rub)], [T("Результат после внешних потоков"), money(performance.investment_result_rub)], [T("Комиссии за период"), money(performance.fees_rub)], [T("Налоговые списания"), money(performance.taxes_rub)]])}<p class="data-footnote">${performance.from ? renderAnalyticsFragment(performance) : ""}${H("Метод: изменение стоимости минус внешние денежные потоки. Комиссии и налоги уже отражаются в результате; повторно они не вычитаются.")}</p></section></div><div class="two-column section-gap"><section class="card">${cardHeader(T("Выплаты до налоговых списаний"))}${income.by_month?.length ? chart(income.by_month.map(item => ({
      ...item,
      time: renderAnalyticsFragment2(item)
    })), {
      timeKey: "time",
      valueKey: "total_rub",
      label: T("Подтверждённые выплаты по месяцам"),
      tone: "purple"
    }) : empty(T("История выплат пока недоступна"), T("Для расчёта нужны подтверждённые операции брокера."), "", "", "wallet")}${infoRows([[T("Купоны"), money(income.coupons_rub)], [T("Дивиденды"), money(income.dividends_rub)], [T("Прочие доходы"), money(income.other_income_rub)], [T("Погашения капитала"), money(income.redemptions_rub)]])}<p class="data-footnote">${incomePeriod}${H("Погашение возвращает капитал и не включается в доход. Налоговые списания учитываются отдельно в финансовом результате.")}</p></section><section class="card">${cardHeader(T("Полнота данных и риски"))}${analysis ? renderAnalyticsFragment3(analysis) : empty(T("Анализ ещё не получен"), T("Проверьте подключение счёта и наличие наблюдений."), "connect", T("Проверить подключение"), "analytics")}${dataError("analysis")}</section></div>${performance.status === "unavailable" ? ("<p class=\"notice section-gap\">" + H("Финансовый результат не рассчитан: недостаточно подтверждённых снимков или истории денежных потоков. Пропуски не заменяются нулями.") + "</p>") : ""}<section class="card section-gap">${cardHeader(T("Проверка выбранной стратегии"), "strategies", T("Открыть"))}<p class="fine-print">${esc(strategyTitle())}${H(". Подробные ограничения, проверка состава и исследование на истории находятся в разделе стратегий.")}</p></section>`;
    applyScreenLayout("analytics");
  };
  const billingLabel = status => ({
    creating: T("Платёж создаётся"), pending: T("Ожидает оплаты"), paid: T("Оплачен"),
    cancelled: T("Отменён"), refunded: T("Возвращён"), partial_refund: T("Частичный возврат"),
    uncertain: T("Результат требует сверки")
  })[status] || T("Статус не подтверждён");
  const billingResolutionHTML = item => {
    const resolved = {initialization_not_started: T("billing.init_not_started"), provider_order_absent: T("billing.order_absent")}[item.resolution];
    if (resolved) return `<p class="fine-print">${esc(resolved)}</p>`;
    if (!item.recovery_not_before) return "";
    return `<p class="notice warning">${H("billing.init_uncertain")} ${H("billing.absence_after", {at: date(item.recovery_not_before, true)})}</p>`;
  };
  const billingLimitsHTML = value => {
    const personal = value.plans?.personal;
    const premium = value.offer?.entitlements || value.plans?.premium;
    if (!personal || !premium) return "";
    const capacity = limits => `${format(number(limits.research_storage_bytes) === null ? null : limits.research_storage_bytes / 1048576, 0)} ${T("billing.mib")}`;
    return `<table class="plan-comparison"><caption>${H("billing.archive_limits")}</caption><thead><tr><th scope="col">${H("billing.limit")}</th><th scope="col">${H("Личный кабинет")}</th><th scope="col">Premium</th></tr></thead><tbody><tr><th scope="row">${H("billing.saved_runs")}</th><td>${esc(format(personal.research_runs, 0))}</td><td>${esc(format(premium.research_runs, 0))}</td></tr><tr><th scope="row">${H("billing.archive_size")}</th><td>${esc(capacity(personal))}</td><td>${esc(capacity(premium))}</td></tr></tbody></table><p class="fine-print">${H("billing.archive_scope")}</p>`;
  };
  const billingHistoryItemHTML = item => {
    const disabled = state.billingBusy ? " disabled" : "";
    const canOpen = item.status === "pending" && !item.cancel_attempted_at && (!item.checkout_expires_at || Date.parse(item.checkout_expires_at) > Date.now()) && U.external(item.checkout_url) && ["securepay.tinkoff.ru", "securepayments.tinkoff.ru"].includes(new URL(item.checkout_url).hostname);
    const cancelNotice = item.cancel_attempted_at && ["pending", "uncertain"].includes(item.status) ? `<p class="notice">${H("billing.cancel_pending")}</p>` : "";
    const checkoutLink = canOpen ? `<a class="button primary small" href="${esc(item.checkout_url)}" target="_blank" rel="noopener noreferrer">${H("Открыть оплату в банке")}</a>` : "";
    const cancelControl = ["creating", "pending", "uncertain"].includes(item.status) && !item.cancel_attempted_at ? `<button class="button secondary small" data-billing-id="${esc(item.id)}" data-billing-operation="cancel"${disabled}>${H("Отменить оплату")}</button>` : "";
    return `<li class="section-gap"><strong>${esc(billingLabel(item.status))} · ${esc(money(item.amount_kopecks / 100, 2, "RUB", false))}</strong><p class="fine-print">${esc(date(item.created_at, true))} ${H("МСК ·")} ${esc(format(item.period_days, 0))} ${H("дней")}</p>${billingResolutionHTML(item)}${cancelNotice}<div class="form-actions">${checkoutLink}<button class="button secondary small" data-billing-id="${esc(item.id)}" data-billing-operation="reconcile"${disabled}>${H("Сверить с банком")}</button>${cancelControl}</div></li>`;
  };
  const billingHTML = () => {
    const value = state.data.billing;
    if (!value) return dataError("billing") || U.loading(T("Проверяем план и оплаты…"));
    const active = value.plan === "premium";
    const offer = value.offer;
    const pending = (value.payments || []).some(item => ["creating", "pending", "uncertain"].includes(item.status));
    const history = (value.payments || []).map(billingHistoryItemHTML).join("");
    const activeUntil = active ? `<p>${H("Доступ действует до")} ${esc(date(value.valid_until, true))} ${H("МСК.")}</p>` : "";
    let checkout = "";
    if (offer && !active && !pending) checkout = `<form id="billing-checkout-form" data-offer="${esc(offer.version)}" data-request-id="${crypto.randomUUID()}"><h3 class="panel-title">${esc(offer.description)}</h3><p class="help-copy">${esc(money(offer.amount_kopecks / 100, 2, "RUB", false))} ${H("за")} ${esc(format(offer.period_days, 0))} ${H("дней")}</p>${field({name: "receipt_email", label: T("Email для банковского чека"), type: "email", required: true})}<label class="check-field"><input name="accept_offer" type="checkbox" required><span>${H("Подтверждаю выбранный срок и сумму.")} <a href="/legal/terms.html">${H("Условия использования")}</a></span></label><button class="button primary" type="submit"${state.billingBusy ? " disabled" : ""}>${H("Создать платёж")}</button></form>`;
    else if (!value.configured) checkout = ("<p class=\"notice\">" + H("Приём оплаты ещё не включён. Тариф появится после настройки реального терминала, стоимости и условий оператором.") + "</p>");
    return `${dataError("billing")}<p class="help-copy">${H("Текущий план:")} <strong>${active ? "Premium" : T("Личный кабинет")}</strong></p>${activeUntil}${billingLimitsHTML(value)}<p class="fine-print">${H("Портфель, цели, стратегии, аналитика и настройки доступны в личном кабинете. Автоматические списания не используются.")}</p>${checkout}<output id="billing-message" class="form-message"></output>${pending ? ("<p class=\"notice\">" + H("Есть незавершённая оплата. Сверьте её состояние перед созданием новой.") + "</p>") : ""}<details class="section-gap" ${pending ? "open" : ""}><summary class="details-summary">${H("История оплат ·")} ${(value.payments || []).length}</summary><ul class="source-list">${history || ("<li>" + H("Оплат ещё не было.") + "</li>")}</ul></details><p class="fine-print section-gap">${H("Доступ обновляется после подтверждения банка. Возврат на сайт после оплаты не подтверждает списание.")}</p>`;
  };
  const openBilling = async () => {
    if (enterRouteScreen("profile", "plan", {})) return;
    if (!requireUser()) return;
    const generation = state.generation;
    openDialog(T("План и подписка"), U.loading(T("Проверяем план и оплаты…")));
    const sequence = state.eventRequest;
    await loadResource("billing", "/api/billing", {force: true});
    if (generation === state.generation && sequence === state.eventRequest && $("#workspace-dialog").open) openDialog(T("План и подписка"), billingHTML());
  };
  const checkoutBilling = async form => {
    if (!requireUser() || state.billingBusy || !form.reportValidity()) return;
    const generation = state.generation;
    const sequence = state.eventRequest;
    state.billingBusy = true;
    form.querySelector("button").disabled = true;
    try {
      await api("/api/billing/checkout", {method: "POST", body: {
        request_id: form.dataset.requestId, expected_offer: form.dataset.offer,
        receipt_email: form.elements.receipt_email.value.trim()
      }});
      if (generation !== state.generation) return;
      state.billingBusy = false;
      if (sequence === state.eventRequest && $("#workspace-dialog").open) {
        await openBilling();
        showMessage($("#billing-message"), T("Платёж создан. Откройте защищённую страницу банка из истории оплат."));
      } else await loadResource("billing", "/api/billing", {force: true});
    } catch (error) {
      if (generation !== state.generation || isCancelled(error)) return;
      // Preserve the same request ID after uncertain transport; history is authoritative.
      await loadResource("billing", "/api/billing", {force: true});
      if (generation === state.generation && form.isConnected) showMessage($("#billing-message"), humanError(error), true);
    } finally {
      if (generation === state.generation) state.billingBusy = false;
      if (form.isConnected) form.querySelector("button").disabled = false;
    }
  };
  const billingOperation = async control => {
    if (!requireUser() || state.billingBusy) return;
    const id = control.dataset.billingId;
    const operation = control.dataset.billingOperation;
    if (!["reconcile", "cancel"].includes(operation)) return;
    if (operation === "cancel" && control.dataset.confirmed !== "true") {
      openDialog(T("Отменить оплату?"), `<p class="help-copy">${H("billing.cancel_review")}</p><button class="button danger" data-billing-id="${esc(id)}" data-billing-operation="cancel" data-confirmed="true">${H("Подтвердить отмену")}</button>`);
      return;
    }
    const generation = state.generation;
    const sequence = state.eventRequest;
    state.billingBusy = true;
    control.disabled = true;
    try {
      await api(`/api/billing/payments/${safeSegment(id)}/${operation}`, {method: "POST", body: {}});
      if (generation !== state.generation) return;
      state.billingBusy = false;
      if (sequence === state.eventRequest && $("#workspace-dialog").open) await openBilling();
      else await loadResource("billing", "/api/billing", {force: true});
    } catch (error) {
      if (!isCancelled(error) && generation === state.generation) toast(humanError(error), true);
    } finally {
      if (generation === state.generation) state.billingBusy = false;
      if (control.isConnected) control.disabled = false;
    }
  };

  const renderProfile = () => {
    captureScreenDrafts();
    if (state.tour) {
      $("#view-profile").innerHTML = `${heading(T("Профиль"))}<section class="card">${empty(T("Ваш личный аккаунт"), T("Войдите через T-ID или VK ID, чтобы настроить профиль."), "login", T("Войти"), "profile", true)}</section>`;
      return;
    }
    const prefs = state.prefs.draft;
    const user = state.user;
    $("#view-profile").innerHTML = `${heading(T("Профиль"), T("Личные настройки и доступ к аккаунту"))}<div class="settings-layout"><section class="card"><div class="profile-summary"><span class="avatar">${esc((prefs?.display_name || T("О")).slice(0, 1).toUpperCase())}</span><div><h2>${esc(prefs?.display_name || T("Мой профиль"))}</h2><p>${H("Профиль")} ${esc(user?.public_id)} · ${user?.role === "owner" ? T("Владелец") : T("Пользователь")}</p></div></div>${prefs ? renderProfileForm(prefs) : renderProfileFragment()}<div class="form-actions"><button class="button secondary" data-action="copy-profile">${icon("copy", true)}${H("Копировать ID профиля")}</button></div></section><section class="card"><h2 class="panel-title">${H("Способы входа")}</h2>${infoRows([["T-ID", state.data.identities?.providers?.includes("tid") ? T("Привязан к аккаунту") : renderProfileValue()], ["VK ID", state.data.identities?.providers?.includes("vkid") ? T("Привязан к аккаунту") : renderProfileValue2()], [T("Подключённый счёт"), state.data.connection?.account_name || T("Нет подключения")]])}<p class="fine-print section-gap">${H("Вход подтверждает личный аккаунт OMNICIO. Подключение брокерских данных настраивается отдельно.")}</p><div class="form-actions">${button(T("Подключить способ входа"), "link-identity", {
      small: true
    })}${button(T("Настройки"), "settings", {
      route: true,
      small: true
    })}${button(T("Выйти"), "logout", {
      small: true
    })}</div></section><section class="card wide"><h2 class="panel-title">${H("Удаление аккаунта")}</h2><p class="fine-print">${H("Удаляются профиль OMNICIO, его настройки, сессии и сохранённое подключение. Операция требует подтверждения ID вашего профиля.")}</p><button class="button danger" data-action="delete-account">${H("Удалить аккаунт")}</button></section></div>`;
    $("#view-profile .settings-layout").insertAdjacentHTML("beforeend", sessionsHTML() + `<section class="card"><h2 class="panel-title">${H("План и подписка")}</h2><p class="help-copy">${state.data.billing?.plan === "premium" ? "Premium" : T("Личный кабинет")}</p>${button(T("Управление планом"), "premium", {small: true})}${dataError("billing")}</section>`);
    restoreEditableForm("profile-form");
    updateSaveStatus("prefs");
    applyScreenLayout("profile");
  };
  const sessionItemHTML = item => {
    const action = item.current ? ("<span class=\"chip\">" + H("Это устройство") + "</span>") : `<button class="button secondary small" data-session-revoke="${esc(item.id)}">${H("Завершить")}</button>`;
    return `<div class="setting-row"><div><strong>${item.current ? T("Текущая сессия") : T("Другой вход")} · ${esc({vkid: "VK ID", tid: "T-ID"}[item.auth_provider] || T("Провайдер не записан"))}</strong><p class="fine-print">${H("Вход:")} ${esc(date(item.created_at, true))} ${H("· Активность:")} ${esc(date(item.last_seen_at, true))} ${H("МСК")}<br>${H("Действует до")} ${esc(date(item.expires_at, true))}</p></div>${action}</div>`;
  };
  const identityUnlinkHTML = (provider, count) => `<button class="button secondary small" data-identity-unlink="${esc(provider)}"${count < 2 ? " disabled" : ""}>${H("Отвязать")} ${provider === "tid" ? "T-ID" : "VK ID"}</button>`;
  const sessionsHTML = () => {
    const payload = state.data.sessions;
    const sessions = payload?.sessions || [];
    let content = U.loading(T("Загружаем активные сессии…"));
    if (state.errors.sessions) content = dataError("sessions");
    else if (sessions.length) content = sessions.map(sessionItemHTML).join("");
    const providers = state.data.identities?.providers || [];
    return `<section class="card wide"><div class="card-header"><h2>${H("Активные сессии")}</h2>${sessions.length > 1 ? ("<button class=\"button secondary small\" data-session-revoke=\"others\">" + H("Завершить остальные") + "</button>") : ""}</div>${content}${payload?.truncated ? ("<p class=\"notice\">" + H("Показаны последние 100 сессий. Кнопка завершения остальных применяется ко всем другим действующим сессиям.") + "</p>") : ""}</section><section class="card wide"><h2 class="panel-title">${H("Управление привязками входа")}</h2><p class="fine-print">${H("Для отвязки сначала повторно войдите через другой привязанный и доступный способ. Подтверждение действует 5 минут. Последний способ входа удалить нельзя.")}</p><div class="form-actions">${providers.map(provider => identityUnlinkHTML(provider, providers.length)).join("")}</div></section>`;
  };
  const revokeSession = async id => {
    if (!requireUser()) return;
    const generation = state.generation;
    try {
      await api(id === "others" ? "/api/me/sessions/revoke-others" : "/api/me/sessions/revoke", {method: "POST", body: id === "others" ? {} : {session_id: id}});
      if (generation !== state.generation) return;
      await loadResource("sessions", "/api/me/sessions", {force: true});
      if (state.view === "profile") renderProfile();
      toast(T("Выбранный доступ завершён."));
    } catch (error) { if (!isCancelled(error)) toast(humanError(error), true); }
  };
  const unlinkIdentity = async provider => {
    if (!requireUser() || !["tid", "vkid"].includes(provider)) return;
    const generation = state.generation;
    try {
      await api(`/api/me/identities/${provider}/unlink`, {method: "POST", body: {}});
      if (generation !== state.generation) return;
      await Promise.allSettled([loadResource("identities", "/api/auth/identities", {force: true}), loadResource("sessions", "/api/me/sessions", {force: true})]);
      if (state.view === "profile") renderProfile();
      toast(T("Привязка удалена; связанные с ней сессии завершены."));
    } catch (error) { if (!isCancelled(error)) toast(["identity_reauthentication_required", "identity_last_provider"].includes(error.code || error.message) ? T("Сначала войдите заново через другой привязанный и включённый способ. Последний доступный способ отвязать нельзя.") : humanError(error), true); }
  };
  const executionActive = execution => ["created", "running", "reconciling"].includes(execution?.status) && ["live", "sandbox", "shadow"].includes(execution?.mode);
  const activeExecutionExists = () => Boolean(state.data.executions?.has_active_live_execution || state.data.executions?.executions?.some(item => item.mode !== "shadow" && executionActive(item)));
  const disconnectBlocked = () => state.loading.has("executions") || !state.data.executions || Boolean(state.errors.executions) || activeExecutionExists();
  const executionStatus = status => ({
    created: T("План создан"),
    running: T("Есть незавершённые шаги"),
    reconciling: T("Требуется сверка"),
    succeeded: T("Завершено"),
    cancelled: T("Отменено"),
    failed: T("Ошибка"),
    pending: T("Не отправлено"),
    submitting: T("Результат отправки уточняется"),
    submitted: T("Заявка у брокера"),
    partially_filled: T("Исполнена частично"),
    filled: T("Исполнена"),
    cancel_requested: T("Отмена запрошена"),
    rejected: T("Отклонена"),
    shadow_filled: T("execution.shadow_filled")
  })[status] || T("Статус требует проверки");
  const executionMode = mode => ({
    live: T("Основной счёт"),
    sandbox: T("Тестовый счёт"),
    shadow: T("execution.shadow")
  })[mode] || T("Среда не подтверждена");
  const executionRow = execution => `<button class="recovery-row" data-action="recovery-open" data-recovery-id="${esc(execution.id)}"><span><strong>${esc(executionStatus(execution.status))}</strong><small>${esc(executionMode(execution.mode))} · ${esc(date(execution.updated_at, true))} ${H("МСК")}</small><small>${H("Счёт")} ${esc(execution.account_id)}</small></span>${icon("arrow", true)}</button>`;
  const mandateHTML = mandate => {
    if (!mandate) return "";
    return `<div class="notice section-gap"><strong>${H("Ранее выданное разрешение")}</strong>${infoRows([[T("Счёт"), mandate.account_id], [T("Действует до"), date(mandate.expires_at, true) + T(" МСК")], [T("Лимит заявки"), money(mandate.max_order_notional_rub)], [T("Дневной лимит"), money(mandate.max_daily_notional_rub)]])}<div class="form-actions">${button(T("Отозвать разрешение"), "mandate-revoke", {
      small: true
    })}</div></div>`;
  };
  const recoveryPanelHTML = () => {
    if (state.errors.executions) return `<section class="card section-gap"><h2 class="panel-title">${H("Ранее начатые исполнения")}</h2>${dataError("executions", T("История исполнений недоступна"))}<p class="fine-print">${H("Перед отключением источника требуется проверить незавершённые заявки.")}</p></section>`;
    const data = state.data.executions;
    if (!data) {
      if (state.loading.has("executions")) return `<section class="card section-gap">${U.loading(T("Проверяем ранее начатые исполнения…"))}</section>`;
      return `<section class="card section-gap"><h2 class="panel-title">${H("Ранее начатые исполнения")}</h2><p class="notice">${H("История исполнений недоступна")}</p><p class="fine-print">${H("Перед отключением источника требуется проверить незавершённые заявки.")}</p>${button(T("Проверить историю"), "recovery-reload", {small: true})}</section>`;
    }
    if (!data.executions.length && !data.live_mandate) return `<section class="card section-gap"><h2 class="panel-title">${H("Ранее начатые исполнения")}</h2><p class="fine-print">${H("execution.history_empty")}</p>${button(T("Проверить историю"), "recovery-reload", {
      small: true
    })}</section>`;
    return `<section class="card section-gap"><div class="card-header"><h2>${H("Ранее начатые исполнения")}</h2>${button(T("Обновить"), "recovery-reload", {
      small: true
    })}</div><p class="fine-print">${H("execution.history_help")}</p><div class="recovery-list">${data.executions.map(executionRow).join("")}</div>${mandateHTML(data.live_mandate)}<output id="recovery-list-message" class="form-message"></output></section>`;
  };
  const repaintRecoveryPanel = () => {
    const panel = $("#recovery-settings");
    if (panel) panel.innerHTML = recoveryPanelHTML();
    const broker = $("#broker-settings");
    if (broker && state.data.connection?.connected) broker.innerHTML = `<h2 class="panel-title">${H("Подключение T-Invest")}</h2>${brokerSettingsHTML()}`;
  };
  const reloadRecovery = async () => {
    const generation = state.generation;
    const pending = loadResource("executions", "/api/portfolio/executions", {
      force: true
    });
    if (state.user && !state.locked) repaintRecoveryPanel();
    await pending;
    if (generation === state.generation && state.user && !state.locked) repaintRecoveryPanel();
  };
  const nextExecutionLeg = execution => execution?.legs?.find(leg => !["filled", "shadow_filled", "cancelled", "rejected", "failed"].includes(leg.status));
  const recoveryButtons = execution => {
    if (!executionActive(execution)) return "";
    const next = nextExecutionLeg(execution);
    if (!next) return "";
    const pending = next.status === "pending";
    if (execution.mode === "shadow") return `<div class="form-actions">${pending ? button(T("execution.next_leg"), "recovery-dispatch", {primary: true, small: true}) : ""}${button(T("Закрыть неотправленный план"), "recovery-cancel", {small: true})}</div>`;
    const reconcile = pending ? "" : button(T("Сверить исполнение"), "recovery-reconcile", {
      small: true
    });
    return `<div class="form-actions">${reconcile}${button(pending ? T("Закрыть неотправленный план") : T("Отменить заявку"), "recovery-cancel", {
      small: true
    })}</div>`;
  };
  const executionLegHTML = (leg, mode) => {
    const action = {
      buy: T("Покупка"),
      sell: T("Продажа")
    }[leg.action] || T("Действие не определено");
    const rows = [[T("Инструмент"), leg.instrument_uid], [T("Запрошено лотов"), format(leg.lots_requested, 0)], [T("Исполнено лотов"), format(leg.lots_executed, 0)], [T("ID запроса"), leg.request_id || T("Не получен")]];
    if (mode !== "shadow") rows.push([T("ID заявки брокера"), leg.provider_order_id || T("Не подтверждён")], [T("Статус брокера"), leg.provider_status || T("Не получен")], [T("Последняя сверка"), leg.last_checked_at ? date(leg.last_checked_at, true) + T(" МСК") : T("Ещё не выполнена")]);
    return `<article class="recovery-leg"><h3>${esc(action)} · ${esc(executionStatus(leg.status))}</h3>${infoRows(rows)}</article>`;
  };
  const storedExecutionErrorHTML = code => `<p class="notice error">${esc(recoveryErrorReason(code) || T("Ранее получена ошибка. Сверьте состояние заявки перед следующим действием."))}</p>`;
  const recoveryDetailsHTML = execution => `${infoRows([[T("Состояние"), executionStatus(execution.status)], [T("Среда"), executionMode(execution.mode)], [T("Счёт"), execution.account_id], [T("ID исполнения"), execution.id], [T("Обновлено"), date(execution.updated_at, true) + T(" МСК")]])}${execution.error_code ? storedExecutionErrorHTML(execution.error_code) : ""}<div class="recovery-legs">${(execution.legs || []).map(leg => executionLegHTML(leg, execution.mode)).join("")}</div>${recoveryButtons(execution)}<div id="recovery-confirmation"></div><output id="recovery-message" class="form-message"></output><p class="fine-print section-gap">${execution.mode === "shadow" ? H("execution.cancel_pending") : H("Отмена относится к ближайшему незавершённому шагу. Запрошенная отмена подтверждается состоянием брокера; фактически исполненные лоты остаются исполненными.")}</p>`;
  const recoveryStatusButton = () => button(T("Обновить статус"), "recovery-detail-reload", {
    small: true
  });
  const updateRecoveryControls = () => {
    for (const control of $$('#dialog-content [data-action^="recovery-"]')) {
      const needsConfirmation = control.dataset.action !== "recovery-detail-reload";
      control.disabled = state.recovery.busy || state.recovery.uncertain && needsConfirmation;
    }
  };
  const recoveryContext = () => ({
    id: state.recovery.id,
    sequence: state.recovery.sequence,
    generation: state.generation
  });
  const currentRecovery = context => context.generation === state.generation && context.sequence === state.recovery.sequence && context.id === state.recovery.id && $("#workspace-dialog").open;
  const readRecoveryDetails = async context => {
    try {
      const result = await api(`/api/portfolio/executions/${safeSegment(context.id)}`);
      if (!currentRecovery(context)) return;
      state.recovery.record = result.execution;
      state.recovery.uncertain = false;
      $("#dialog-content").innerHTML = recoveryDetailsHTML(result.execution) + recoveryStatusButton();
      updateRecoveryControls();
    } catch (error) {
      if (!currentRecovery(context) || isCancelled(error)) return;
      $("#dialog-content").innerHTML = `<div class="notice error">${esc(humanError(error))}</div>${button(T("Повторить загрузку"), "recovery-detail-reload", {
        small: true
      })}`;
    }
  };
  const reloadRecoveryDetails = () => {
    if (!state.recovery.id || state.recovery.busy) return;
    state.recovery.sequence += 1;
    return readRecoveryDetails(recoveryContext());
  };
  const openRecovery = async control => {
    if (!requireUser()) return;
    const id = control.dataset.recoveryId;
    if (!state.data.executions?.executions.some(item => item.id === id)) return;
    openDialog(T("Ранее начатое исполнение"), U.loading(T("Читаем сохранённое состояние…")));
    state.recovery.id = id;
    await readRecoveryDetails(recoveryContext());
  };
  const askRecoveryCancellation = () => {
    const execution = state.recovery.record;
    if (!executionActive(execution) || state.recovery.busy || state.recovery.uncertain) return;
    const pending = nextExecutionLeg(execution)?.status === "pending";
    const description = pending ? T("Неотправленный шаг будет закрыт в сохранённом плане. Брокерская заявка для него не создаётся.") : T("Сервер запросит отмену существующей заявки. Уже исполненные лоты отменить этим действием нельзя. После запроса проверьте ответ брокера.");
    $("#recovery-confirmation").innerHTML = `<div class="notice section-gap"><p>${esc(description)}</p><div class="form-actions">${button(T("Подтвердить отмену"), "recovery-cancel-confirm", {
      small: true
    })}${button(T("Продолжить просмотр"), "recovery-cancel-dismiss", {
      small: true
    })}</div></div>`;
    $('[data-action="recovery-cancel-confirm"]').focus();
  };
  const mutateRecovery = async action => {
    if (!requireUser() || state.recovery.busy || state.recovery.uncertain || !executionActive(state.recovery.record)) return;
    const context = recoveryContext();
    state.recovery.busy = true;
    for (const control of $$('#dialog-content [data-action^="recovery-"]')) control.disabled = true;
    try {
      const result = await api(`/api/portfolio/executions/${safeSegment(context.id)}/${action}`, {
        method: "POST",
        body: {}
      });
      if (currentRecovery(context)) {
        state.recovery.record = result.execution;
        $("#dialog-content").innerHTML = recoveryDetailsHTML(result.execution) + recoveryStatusButton();
        showMessage($("#recovery-message"), T("Состояние получено с сервера: ") + executionStatus(result.execution.status));
      }
      if (context.generation === state.generation) await reloadRecovery();
    } catch (error) {
      if (currentRecovery(context) && !isCancelled(error)) {
        state.recovery.uncertain = true;
        showMessage($("#recovery-message"), humanError(error) + T(" Обновите состояние перед повтором."), true);
      }
    } finally {
      if (context.generation === state.generation) state.recovery.busy = false;
      if (currentRecovery(context)) updateRecoveryControls();
    }
  };
  const askMandateRevoke = () => {
    if (!requireUser() || !state.data.executions?.live_mandate) return;
    openDialog(T("Отозвать ранее выданное разрешение?"), `<p class="help-copy">${H("Разрешение будет отозвано на сервере. Состояние уже отправленных заявок проверяется отдельно в истории исполнений.")}</p><div class="form-actions">${button(T("Отозвать разрешение"), "mandate-revoke-confirm", {
      small: true
    })}<button class="button secondary" data-close-dialog>${H("Отмена")}</button></div><output id="mandate-message" class="form-message"></output>`);
  };
  const revokeMandate = async control => {
    if (!requireUser() || !state.data.executions?.live_mandate) return;
    const generation = state.generation;
    control.disabled = true;
    try {
      await api("/api/portfolio/live-execution/mandate", {
        method: "DELETE",
        body: {}
      });
      if (generation !== state.generation) return;
      $("#workspace-dialog").close();
      await reloadRecovery();
      if (generation === state.generation) toast(T("Разрешение отозвано на сервере."));
    } catch (error) {
      if (generation === state.generation && !isCancelled(error)) {
        showMessage($("#mandate-message"), humanError(error) + T(" Проверьте текущее разрешение перед повтором."), true);
        control.disabled = false;
      }
    }
  };
  const brokerDisconnectDescription = () => {
    if (activeExecutionExists()) return T("Есть незавершённое исполнение. Сначала проверьте заявки в панели ниже; источник нужен для их сверки и отмены.");
    if (disconnectBlocked()) return T("Перед отключением проверяем ранее начатые исполнения. Если проверка не завершится, обновите историю ниже.");
    return T("Токен хранится на сервере и не возвращается в браузер. Для замены счёта сначала отключите текущее подключение.");
  };
  const deliveryStateLabels = () => ({pending: T("Ожидает подтверждения"), active: T("Подключён"), revoked: T("Отключён"), expired: T("Нужно подключить заново"), queued: T("В очереди"), sending: T("Отправляется"), accepted: T("Принято провайдером"), uncertain: T("Результат не подтверждён"), failed: T("Не отправлено"), cancelled: T("Отменено")});
  const notificationVerificationHTML = channel => {
    if (channel.status !== "pending") return "";
    const formId = "notification-verify-" + channel.id;
    return `<form id="${esc(formId)}" data-channel-id="${esc(channel.id)}" class="section-gap"><label class="field"><span>${H("Код из письма")}</span><input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" minlength="6" maxlength="6" required value="${esc(state.deliveryDrafts[formId]?.code || "")}" aria-label="${H("Код подтверждения email")}"></label><p class="fine-print">${H("Действует до")} ${esc(date(channel.verification_expires_at, true))} ${H("МСК. Осталось попыток:")} ${esc(channel.verification_attempts_remaining ?? 5)}.</p><button class="button primary small-button" type="submit"${state.deliveryBusy ? " disabled" : ""}>${H("Подтвердить адрес")}</button></form>`;
  };
  const notificationChannelHTML = channel => {
    const revokeAttributes = ` data-channel-id="${esc(channel.id)}"${state.deliveryBusy ? " disabled" : ""}`;
    return `<article class="event-item"><span class="event-icon">${icon(channel.kind === "push" ? "events" : "profile", true)}</span><div class="event-item-body"><h3>${esc(channel.label)}</h3><p class="fine-print">${channel.kind === "push" ? "Push" : "Email"} · ${esc(deliveryStateLabels()[channel.status] || T("Состояние неизвестно"))}</p>${notificationVerificationHTML(channel)}<div class="form-actions">${button(T("Отключить"), "notification-revoke", {small: true, extra: revokeAttributes})}</div></div></article>`;
  };
  const pushAvailabilityDescription = (data, supported) => {
    if (!data.push_configured) return T("Push ещё не включён администратором.");
    if (!supported) return T("Этот браузер не поддерживает push в текущем режиме. На iPhone или iPad может потребоваться установка сайта на главный экран.");
    if (Notification.permission === "denied") return T("Разрешение заблокировано. Измените его в настройках сайта в браузере.");
    return T("Разрешение браузера запрашивается только после нажатия кнопки.");
  };
  const notificationDeliveryHTML = item => {
    const nextAttempt = item.status === "queued" ? ` ${T("· следующая попытка")} ${esc(date(item.next_attempt_at, true))} ${T("МСК")}` : "";
    const detail = item.error ? `<p class="notice error">${esc(item.error.title || T("notifications.delivery_failed"))}</p>` : "";
    const channelKind = item.channel?.kind === "push" ? "Push" : "Email";
    const channel = item.channel ? `${channelKind} · ${item.channel.label || T("notifications.channel_unavailable")}` : T("notifications.channel_unavailable");
    return `<li><p class="fine-print">${esc(channel)} · ${H("notifications.attempts")}: ${esc(item.attempts ?? 0)}</p>${detail}<strong>${esc({verification: T("Подтверждение адреса"), event: T("Событие"), digest: T("Дайджест"), operational: T("Состояние сервиса")}[item.kind] || T("Уведомление"))}</strong> · ${esc(deliveryStateLabels()[item.status] || T("Состояние неизвестно"))}<br><span class="fine-print">${esc(date(item.created_at, true))} ${H("МСК")}${nextAttempt}${item.status === "uncertain" ? T(" · повтор автоматически не отправляется; проверьте устройство или почту") : ""}</span></li>`;
  };
  const notificationContentsHTML = () => {
    const data = state.data.notifications;
    if (!data) return `<h2 class="panel-title">${H("Доставка уведомлений")}</h2>${state.errors.notifications ? dataError("notifications") : U.loading(T("Проверяем подключённые каналы…"))}`;
    const pushSupported = "Notification" in window && "PushManager" in window && "serviceWorker" in navigator && window.isSecureContext;
    const deliveries = (data.deliveries || []).map(notificationDeliveryHTML).join("");
    const deliveryList = deliveries ? `<ul class="source-list">${deliveries}</ul>` : ("<p class=\"fine-print\">" + H("Отправок ещё не было.") + "</p>");
    return `<div class="card-header"><h2>${H("Доставка уведомлений")}</h2>${button(T("Проверить состояние"), "notifications-reload", {small: true})}</div>${dataError("notifications")}<p class="fine-print">${H("Содержание портфеля и личные суммы не включаются в сообщение. Подробности открываются после входа в OMNICIO. Дневной или недельный дайджест заменяет отдельные сообщения; тихие часы откладывают доставку.")}</p><div class="form-actions">${button(T("Включить push на этом устройстве"), "notification-push", {small: true, extra: !data.push_configured || !pushSupported || state.deliveryBusy ? " disabled" : ""})}</div><p class="fine-print">${esc(pushAvailabilityDescription(data, pushSupported))}</p><form id="notification-email-form" class="section-gap"><label class="field"><span>${H("Email для уведомлений")}</span><input name="email" type="email" maxlength="254" autocomplete="email" required value="${esc(state.deliveryDrafts["notification-email-form"]?.email || "")}"${!data.email_configured ? " disabled" : ""}></label><button class="button primary small-button" type="submit"${!data.email_configured || state.deliveryBusy ? " disabled" : ""}>${H("Отправить код подтверждения")}</button><p class="fine-print">${data.email_configured ? T("Подписка включится только после подтверждения адреса. Код действует 15 минут; разрешено пять попыток.") : T("Email-доставка ещё не включена администратором.")}</p></form><output id="notification-message" class="form-message"></output><div class="event-list section-gap">${(data.channels || []).map(notificationChannelHTML).join("") || ("<p class=\"notice\">" + H("Устройства и адреса пока не подключены.") + "</p>")}</div><details class="section-gap"><summary class="details-summary">${H("История отправки")}</summary><p class="fine-print">${H("Статус «Принято провайдером» подтверждает приём сообщения сервисом, но не прочтение человеком.")}</p>${deliveryList}</details>`;
  };
  const renderNotificationPanel = () => {
    const target = $("#notification-settings");
    if (target) target.innerHTML = notificationContentsHTML();
  };
  const reloadNotifications = async () => {
    await loadResource("notifications", "/api/notifications", {force: true});
    renderNotificationPanel();
  };
  const deliveryAction = async operation => {
    if (!requireUser() || state.deliveryBusy) return;
    const generation = state.generation;
    state.deliveryBusy = true;
    renderNotificationPanel();
    try {
      await operation();
      if (generation !== state.generation) return;
      await reloadNotifications();
      if (generation === state.generation) toast(T("Состояние уведомлений обновлено."));
    } catch (error) {
      if (generation !== state.generation || isCancelled(error)) return;
      await reloadNotifications();
      if (generation === state.generation) showMessage($("#notification-message"), humanError(error), true);
    } finally {
      if (generation === state.generation) {
        state.deliveryBusy = false;
        const errorMessage = $("#notification-message")?.textContent || "";
        renderNotificationPanel();
        if (errorMessage) showMessage($("#notification-message"), errorMessage, true);
      }
    }
  };
  const enablePush = async () => {
    const publicKey = state.data.notifications?.vapid_public_key;
    if (!publicKey || !("PushManager" in window) || !("Notification" in window)) return;
    await deliveryAction(async () => {
      const generation = state.generation;
      const permission = await Notification.requestPermission();
      if (permission !== "granted") throw Object.assign(new Error("push_permission_denied"), {code: "push_permission_denied"});
      let timeout;
      const registration = await Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, reject) => { timeout = setTimeout(() => reject(Object.assign(new Error("service_worker_unavailable"), {code: "service_worker_unavailable"})), 15000); })
      ]).finally(() => clearTimeout(timeout));
      if (generation !== state.generation) return;
      const bytes = Uint8Array.from(atob(publicKey.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - publicKey.length % 4) % 4)), char => char.codePointAt(0));
      let subscription = await registration.pushManager.getSubscription();
      const previous = subscription?.options?.applicationServerKey;
      if (previous) {
        const oldKey = new Uint8Array(previous);
        if (oldKey.length !== bytes.length || oldKey.some((value, index) => value !== bytes[index])) {
          if (!await subscription.unsubscribe()) throw new Error("push_subscription_invalid");
          subscription = null;
        }
      }
      subscription ||= await registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: bytes});
      if (generation !== state.generation) return;
      await api("/api/notifications/push", {method: "POST", body: {subscription: subscription.toJSON(), label: T("Это устройство")}});
    });
  };
  const revokeNotification = async control => {
    const id = control.dataset.channelId;
    const channel = state.data.notifications?.channels?.find(item => item.id === id);
    if (!channel) return;
    await deliveryAction(async () => {
      await api(`/api/notifications/channels/${safeSegment(id)}`, {method: "DELETE"});
      if (channel.kind === "push" && "serviceWorker" in navigator) {
        const registration = await navigator.serviceWorker.getRegistration();
        const subscription = await registration?.pushManager.getSubscription();
        if (subscription) {
          const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(subscription.endpoint));
          const fingerprint = [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, "0")).join("");
          if (fingerprint === channel.endpoint_fingerprint) await subscription.unsubscribe();
        }
      }
    });
  };
  const operationalStatus = status => ({
    ok: T("ops.ok"), running: T("ops.running"), attention: T("ops.attention"),
    stopped: T("ops.stopped"), stale: T("ops.stale"), not_reported: T("ops.not_reported")
  })[status] || T("Состояние неизвестно");
  const operationalMetricsHTML = () => {
    if (state.user?.can_view_operational_metrics !== true) return "";
    const data = state.data.operationalMetrics;
    const error = dataError("operationalMetrics");
    const heading = `<div class="card-header"><h2>${H("ops.title")}</h2>${button(T("Проверить состояние"), "resource-retry", {small: true, extra: 'data-resource="operationalMetrics"'})}</div>`;
    if (!data || state.errors.operationalMetrics?.status === 403) return `<section class="card section-gap" id="operations-settings">${heading}${error || U.loading(T("ops.loading"))}</section>`;
    const observer = data.observer || {};
    const deliveries = data.notifications || {};
    const workers = Object.entries(data.workers || {}).map(([name, worker]) => {
      const interval = `${format(worker.stale_after_seconds / 60, 0)} ${T("мин.")}`;
      const title = {notifications: T("ops.notifications_worker"), portfolio_refresh: T("ops.refresh_worker"), portfolio_daily: T("ops.daily_worker")}[name] || T("ops.worker");
      return `<div class="section-gap"><h3 class="panel-title">${esc(title)}</h3>${infoRows([[T("ops.state"), operationalStatus(worker.status)], [T("ops.checked_at"), date(worker.checked_at, true)], [T("ops.completed_at"), date(worker.completed_at, true)], [T("ops.heartbeat_limit"), interval]])}</div>`;
    }).join("");
    return `<section class="card section-gap" id="operations-settings">${heading}${error}<p class="notice${data.status === "attention" ? " warning" : ""}">${esc(operationalStatus(data.status))}</p>${freshness(T("ops.server"), data.checked_at)}<p class="fine-print">${H("ops.aggregate_scope")}</p>${infoRows([[T("ops.accounts"), format(observer.connected_accounts, 0)], [T("ops.stale_accounts"), format(observer.stale_success_accounts, 0)], [T("ops.collection_failures"), format(observer.failed_24h, 0)], [T("ops.degraded"), format(observer.degraded_24h, 0)]])}<details class="section-gap"><summary class="details-summary">${H("ops.collection_queue")}</summary>${infoRows([[T("ops.queued"), format(observer.queued, 0)], [T("ops.running"), format(observer.running, 0)], [T("ops.late"), format(observer.stale, 0)], [T("ops.oldest_collection"), date(data.oldest_pending_at, true)], [T("ops.last_collection"), date(data.latest_success_at, true)]])}</details><details class="section-gap"><summary class="details-summary">${H("ops.delivery_queue")}</summary>${infoRows([[T("ops.queued"), format(deliveries.queued, 0)], [T("ops.sending"), format(deliveries.sending, 0)], [T("ops.late"), format(deliveries.stale, 0)], [T("ops.failures_day"), format(deliveries.failed_24h, 0)], [T("ops.uncertain"), format(deliveries.uncertain, 0)], [T("ops.oldest_delivery"), date(deliveries.oldest_due_at, true)], [T("ops.last_accepted"), date(deliveries.last_accepted_at, true)]])}</details><details class="section-gap"><summary class="details-summary">${H("ops.workers")}</summary>${workers}</details><p class="fine-print section-gap">${H("ops.times_msk")}</p></section>`;
  };
  const renderSettings = () => {
    captureScreenDrafts();
    if (state.tour) {
      $("#view-settings").innerHTML = `${heading(T("Настройки"))}<section class="card">${empty(T("Настройки сохраняются в аккаунте"), T("Для источников данных, уведомлений и личных предпочтений войдите в OMNICIO."), "login", T("Войти"), "settings", true)}</section>`;
      return;
    }
    const prefs = state.prefs.draft;
    const timezones = [["Europe/Moscow", T("Москва · UTC+3")], ["Etc/UTC", "UTC"]];
    if (prefs?.quiet_hours?.timezone && !timezones.some(([value]) => value === prefs.quiet_hours.timezone)) timezones.push([prefs.quiet_hours.timezone, prefs.quiet_hours.timezone]);
    const preferences = prefs ? `<form id="preferences-form"><section class="card"><div class="card-header"><h2>${H("Оформление и приватность")}</h2><span class="save-status" data-save-status="prefs"></span></div><div class="field-grid">${select("theme", T("Тема"), [["system", T("Как на устройстве")], ["dark", T("Тёмная")], ["light", T("Светлая")]], prefs.theme)}${select("locale", T("settings.language"), [["ru", T("Русский · 1 234,56")], ["en", "English · 1,234.56"]], prefs.locale, T("settings.language_help"))}</div>${U.switchControl("mask_balances", T("Скрывать личные суммы"), T("Маскирует баланс, суммы целей и персональные графики на экране."), prefs.mask_balances)}</section><section class="card section-gap"><h2 class="panel-title">${H("Уведомления в кабинете")}</h2>${U.switchControl("notify_portfolio", T("Портфель"), T("Изменения и состояния подключённого счёта."), prefs.notifications.portfolio)}${U.switchControl("notify_payments", T("Выплаты"), T("Подтверждённые купоны, дивиденды и другие поступления."), prefs.notifications.payments)}${U.switchControl("notify_goals", T("Цели"), T("Прогресс и события ваших целей."), prefs.notifications.goals)}${U.switchControl("notify_system", T("Система"), T("Подключение данных и важные состояния сервиса."), prefs.notifications.system)}<p class="notice">${H("Категории управляют лентой и подключёнными каналами доставки. Push и email требуют отдельного подключения ниже; SMS не используется.")}</p><div class="field-grid section-gap">${select("digest_frequency", T("Режим дайджеста"), [["off", T("Отдельные события")], ["daily", T("За день")], ["weekly", T("За неделю")]], prefs.digest_frequency)}${field({name: "digest_time", label: T("notifications.digest_time"), type: "time", value: prefs.digest_time || "09:00", required: true})}${select("digest_timezone", T("notifications.digest_timezone"), timezones, prefs.digest_timezone || "Europe/Moscow")}${select("quiet_timezone", T("Часовой пояс тихих часов"), timezones, prefs.quiet_hours.timezone)}</div>${U.switchControl("quiet_enabled", T("Тихие часы"), T("События остаются в ленте. Внешняя доставка откладывается до окончания тихих часов."), prefs.quiet_hours.enabled)}<div class="field-grid">${field({
      name: "quiet_start",
      label: T("Начало"),
      type: "time",
      value: prefs.quiet_hours.start,
      required: true
    })}${field({
      name: "quiet_end",
      label: T("Конец"),
      type: "time",
      value: prefs.quiet_hours.end,
      required: true
    })}</div><div class="form-actions"><button class="button primary" type="submit">${H("Сохранить настройки")}</button><span class="save-status" data-save-status="prefs"></span></div>${saveErrorHTML("prefs")}</section></form>` : `<section class="card">${renderSettingsValue2()}</section>`;
    $("#view-settings").innerHTML = `${heading(T("Настройки"), T("Источники, оформление и события — под вашим контролем"), button(T("Обновить"), "refresh", {
      small: true
    }))}<div class="settings-layout"><div>${preferences}</div><div><section class="card" id="broker-settings"><h2 class="panel-title">${H("Подключение T-Invest")}</h2>${brokerSettingsHTML()}</section><div id="recovery-settings">${recoveryPanelHTML()}</div><section class="card section-gap"><h2 class="panel-title">${H("Персональный ИИ")}</h2><p class="fine-print">${H("Статус и интерфейс ИИ находятся в отдельном разделе. История разговоров сохраняется в вашем аккаунте. Внешний провайдер включается отдельно.")}</p>${button(T("Открыть ИИ-помощника"), "assistant", {
      route: true,
      small: true
    })}</section><section class="card section-gap"><h2 class="panel-title">${H("О приложении")}</h2>${infoRows([[T("Версия"), $("[data-release-version]").textContent], [T("Сборка"), window.OMNICIO_RELEASE?.build || T("Не получена")], [T("Язык интерфейса"), I.getLocale() === "en" ? T("Английский") : T("Русский")]])}<div class="form-actions">${button(T("Условия использования"), "legal", {
      small: true
    })}${button(T("Мой профиль"), "profile", {
      route: true,
      small: true
    })}</div></section></div></div>`;
    restoreEditableForm("preferences-form");
    $("#view-settings .settings-layout > div")?.insertAdjacentHTML("beforeend", `<section class="card section-gap" id="notification-settings">${notificationContentsHTML()}</section>`);
    $("#view-settings .settings-layout > div:last-child")?.insertAdjacentHTML("beforeend", operationalMetricsHTML());
    updateSaveStatus("prefs");
    applyScreenLayout("settings");
  };
  const brokerSettingsHTML = () => {
    const connection = state.data.connection;
    if (!connection) return state.errors.connection ? dataError("connection") : U.loading(T("Проверяем подключение…"));
    if (connection.connected) return `<div class="connection-state"><span class="provider-mark">T</span><div><strong>${esc(connection.account_name || T("Счёт T-Invest"))}</strong><small>${connection.environment === "sandbox" ? T("Тестовая среда") : T("Основной счёт")}</small></div><span class="status-dot"></span></div>${infoRows([[T("ID счёта"), connection.account_id], [T("Проверен"), connection.verified_at ? renderBrokerSettingsHTMLFragment(connection) : "—"]])}<p class="fine-print section-gap">${esc(brokerDisconnectDescription())}</p><div class="form-actions">${button(T("Обновить данные"), "refresh", {
      small: true
    })}${button(T("Отключить"), "disconnect-start", {
      small: true,
      extra: disconnectBlocked() ? " disabled" : ""
    })}</div>`;
    return `<p class="fine-print">${H("Добавьте личный токен API T-Invest. Проверка покажет доступные счета; затем вы явно выберете нужный.")}</p><form id="broker-form" class="connection-steps"><label class="field"><span>${H("API-токен")} ${help(T("API-токен"), T("Создайте токен в личном кабинете T-Invest для чтения данных. Токен вводится только после входа в OMNICIO, проверяется сервером и хранится зашифрованным. Не передавайте его в переписке."))}</span><input type="password" name="credential" autocomplete="off" minlength="20" maxlength="4096" required placeholder="${H("Вставьте токен")}" spellcheck="false"></label>${select("environment", T("Среда источника"), [["prod", T("Основной счёт")], ["sandbox", T("Тестовая среда")]], "prod")}<label class="check-field"><input type="checkbox" name="accept_personal_terms" required><span>${H("Подтверждаю доступ к своим данным на условиях")} <a href="/legal/terms.html">${H("использования сервиса")}</a>.</span></label><button class="button primary" type="submit">${H("Проверить токен")}</button><div id="broker-accounts"></div><output id="broker-message" class="form-message"></output></form>`;
  };
  const assistantHealthLabel = status => {
    if (!status?.enabled) return T("Активация отложена");
    if (!status.configured) return T("Не настроен");
    return ({healthy: T("Соединение проверено"), model_missing: T("Модель не найдена"), unavailable: T("Провайдер недоступен"), checking: T("Проверяем соединение"), unchecked: T("Настроен · требуется проверка")})[status.health?.status] || T("Требуется проверка");
  };
  const assistantDraftFromForm = form => ({
    message: form.elements.message.value,
    context: form.elements.context.value,
    include_news: form.elements.include_news?.checked || false,
    research_run_id: form.elements.research_run_id?.value || ""
  });
  const updateAssistantContext = () => {
    const form = $("#assistant-form");
    if (!form) return;
    const extended = form.elements.context.value === "investment";
    for (const name of ["include_news", "research_run_id"]) if (form.elements[name]) form.elements[name].disabled = !extended || state.assistantBusy;
  };
  const assistantSidebarHTML = ({status, selected, history, enabled}) => {
    const conversationActions = selected ? `<div class="form-actions">${button(T("Обновить историю"), "assistant-history-reload", {small: true})}${button(T("Удалить разговор"), "chat-clear", {small: true, extra: state.assistantBusy ? "disabled" : ""})}</div>` : "";
    const quotaLabel = status?.quota ? esc(`${status.quota.used || 0} ${T("из")} ${status.quota.limit || 0}`) : T("Не получен");
    const quotaReset = status?.quota?.resets_at ? `${T("Обновление лимита:")} ${esc(date(status.quota.resets_at, true))} ${T("МСК")}` : "";
    return `<aside class="card assistant-side"><h2 class="panel-title">${H("Ваши разговоры")}</h2>${button(T("Новый разговор"), "assistant-new", {small: true, extra: state.assistantBusy || state.tour ? "disabled" : ""})}<div class="assistant-history section-gap">${history || ("<p class=\"fine-print\">" + H("Сохранённых разговоров ещё нет.") + "</p>")}</div>${dataError("assistantConversations")}${conversationActions}<h3 class="panel-title section-gap">${H("Лимит запросов")}</h3><p>${quotaLabel}</p><p class="fine-print">${quotaReset}</p><h3 class="panel-title section-gap">${H("Начать с вопроса")}</h3><div class="assistant-prompts">${[T("Как читать структуру моего портфеля?"), T("Что означает просадка?"), T("Какие данные нужны для оценки стратегии?")].map(text => renderAssistantButton(text, enabled)).join("")}</div><p class="section-gap fine-print">${H("Ответ ИИ не изменяет настройки и не отправляет заявки брокеру.")}</p></aside>`;
  };
  const renderAssistant = () => {
    captureScreenDrafts();
    const status = state.data.assistantStatus;
    const enabled = Boolean(status?.enabled && status?.configured && !state.tour);
    const selected = state.tour ? null : state.assistantConversation;
    const draft = state.tour ? {message: "", context: "general"} : state.assistantDraft;
    const rows = state.tour ? [] : state.data.assistantConversations?.items || [];
    const runs = state.tour ? [] : state.data.assistantResearch?.items || [];
    const requestState = value => ({running: T("Запрос выполняется"), uncertain: T("Ответ не подтверждён. Автоматической повторной отправки нет."), cancelled: T("Запрос остановлен")})[value] || "";
    const chat = (state.tour ? [] : state.chat).map(item => {
      const requestNotice = requestState(item.request_status) ? `<p class="fine-print">${esc(requestState(item.request_status))}</p>` : "";
      return `<article class="chat-message ${item.role === "user" ? "user" : ""}"><small>${item.role === "user" ? T("Вы") : T("OMNICIO · ИИ")} · ${esc(date(item.created_at, true))} ${H("МСК")}</small>${esc(item.content)}${item.sources?.length ? renderAssistantSourceList(item) : ""}${requestNotice}</article>`;
    }).join("");
    const history = rows.map(item => `<button class="recovery-row" data-assistant-conversation="${esc(item.id)}"${state.assistantBusy ? " disabled" : ""}${selected?.id === item.id ? ' aria-current="true"' : ""}><span><strong>${esc(item.title)}</strong><small>${esc(date(item.updated_at, true))} ${H("МСК")}</small></span></button>`).join("");
    const researchOptions = [["", T("Не передавать")], ...runs.map(run => [run.id, `${date(run.created_at, true)} · ${run.strategy_version || ""}`])];
    $("#view-assistant").innerHTML = `${heading(T("ИИ-помощник"), T("Разговоры и выбранные вами данные"), button(T("Настроить подключение"), "assistant-connect", {small: true}))}<div class="assistant-layout"><section class="card chat-card"><div class="assistant-status">${icon("assistant")}<strong>${esc(selected?.title || T("Персональный помощник"))}</strong><span class="chip">${esc(assistantHealthLabel(status))}</span></div>${!status?.enabled ? ("<p class=\"notice\">" + H("Внешний ИИ будет включён после завершения и проверки остальной системы. Настройки подключения и история уже доступны.") + "</p>") : ""}<div id="chat-messages" class="chat-messages" role="log" aria-label="${H("Переписка с ИИ")}">${selected?.next_before ? button(T("Предыдущие сообщения"), "assistant-history-more", {small: true, extra: state.assistantBusy ? "disabled" : ""}) : ""}${chat || empty(T("Начните новый разговор"), T("Выберите контекст и задайте вопрос после активации модели."), "", "", "assistant", true)}<div id="assistant-request">${assistantRequestHTML()}</div></div><form id="assistant-form"><div class="assistant-context">${select("context", T("Данные для этого вопроса"), [["general", T("Общий вопрос · без личных данных")], ["portfolio", T("Сводные показатели портфеля")], ["investment", T("Портфель, позиции, цели и стратегия")]], draft.context)}<div class="field-grid">${select("research_run_id", T("Сохранённое исследование"), researchOptions, draft.research_run_id)}<label class="check-field"><input name="include_news" type="checkbox"${draft.include_news ? " checked" : ""}><span>${H("Добавить последние новости Банка России")}</span></label></div><p class="fine-print">${H("Личные данные отправляются только с выбранным контекстом. История хранится в вашем аккаунте и доступна после повторного входа.")}</p><p id="assistant-history-context" class="fine-print">${H("assistant.history_context_help")}</p></div>${assistantMemoryChoices()}<div class="chat-compose"><textarea name="message" aria-label="${H("Сообщение помощнику")}" maxlength="4000" required placeholder="${H("Задайте свой вопрос…")}"${!enabled || state.assistantBusy ? " disabled" : ""}>${esc(draft.message)}</textarea><button class="button primary" type="submit"${!enabled || state.assistantBusy ? " disabled" : ""}>${H("Отправить")}</button></div><output id="assistant-message" class="form-message chat-form-message"></output></form>${dataError("assistantStatus")}</section>${assistantSidebarHTML({status, selected, history, enabled})}</div>`;
    updateAssistantContext();
    applyScreenLayout("assistant");
  };
  const loadAssistantConversation = async (id, more = false) => {
    if (!requireUser() || state.assistantBusy) return;
    const generation = state.generation;
    const sequence = state.assistantLoadSequence = (state.assistantLoadSequence || 0) + 1;
    const before = more && state.assistantConversation?.id === id ? state.assistantConversation.next_before : null;
    const cursor = before ? "&before=" + before : "";
    const payload = await api(`/api/assistant/conversations/${safeSegment(id)}?limit=50${cursor}`);
    if (generation !== state.generation || sequence !== state.assistantLoadSequence) return;
    if (payload.id !== id || !Array.isArray(payload.messages)) throw new Error("invalid_server_response");
    state.chat = more ? [...new Map([...payload.messages, ...state.chat].map(item => [item.position, item])).values()].sort((a,b) => a.position - b.position) : payload.messages;
    state.assistantConversation = payload;
    if (payload.latest_request) state.assistantRequest = {...payload.latest_request, id: payload.latest_request.request_id};
    if (state.view === "assistant") renderAssistant();
  };
  const newAssistantConversation = async () => {
    if (!requireUser() || state.assistantBusy) return;
    const generation = state.generation;
    state.assistantBusy = true;
    renderAssistant();
    let created;
    try { created = await api("/api/assistant/conversations", {method: "POST", body: {title: T("Новый разговор")}}); }
    finally {
      if (generation === state.generation) {
        state.assistantBusy = false;
        if (state.view === "assistant") renderAssistant();
      }
    }
    if (generation !== state.generation) return;
    state.assistantConversation = {...created, messages: [], next_before: null};
    updateViewRoute({screen: "conversation", conversation: created.id});
    state.chat = [];
    await loadResource("assistantConversations", "/api/assistant/conversations", {force: true});
    if (generation === state.generation && state.view === "assistant") renderAssistant();
  };
  const deleteAssistantConversation = async confirmed => {
    const selected = state.assistantConversation;
    if (!requireUser() || state.assistantBusy || !selected) return;
    if (!confirmed) {
      openDialog(T("Удалить разговор?"), `<p class="help-copy">${H("Сообщения «")}${esc(selected.title)}${H("» будут удалены из вашего аккаунта. Счётчик использованных запросов сохранится до обновления дневного лимита.")}</p>${button(T("Удалить разговор"), "assistant-delete-confirm", {primary: true})}`);
      state.assistantDeleteConfirmation = {id: selected.id, sequence: state.eventRequest};
      return;
    }
    const confirmation = state.assistantDeleteConfirmation;
    if (confirmation?.id !== selected.id || confirmation.sequence !== state.eventRequest) return;
    state.assistantDeleteConfirmation = null;
    const generation = state.generation;
    state.assistantBusy = true;
    state.assistantLoadSequence = (state.assistantLoadSequence || 0) + 1;
    renderAssistant();
    try {
      await api(`/api/assistant/conversations/${safeSegment(selected.id)}`, {method: "DELETE"});
      if (generation !== state.generation) return;
      if (state.assistantConversation?.id === selected.id) {
        state.assistantConversation = null;
        state.chat = [];
      }
      if (confirmation.sequence === state.eventRequest && $("#workspace-dialog").open) $("#workspace-dialog").close();
      await loadResource("assistantConversations", "/api/assistant/conversations", {force: true});
    } finally {
      if (generation === state.generation) {
        state.assistantBusy = false;
        if (state.view === "assistant") renderAssistant();
      }
    }
  };
  const openAssistantConnection = async () => {
    if (enterRouteScreen("assistant", "connection", {})) return;
    if (!requireUser()) return;
    const generation = state.generation;
    openDialog(T("Подключение ИИ"), U.loading(T("state.loading")));
    const sequence = state.eventRequest;
    await loadResource("assistantStatus", "/api/assistant/status", {force: true});
    if (generation !== state.generation || sequence !== state.eventRequest || !$("#workspace-dialog").open) return;
    const status = state.data.assistantStatus;
    if (!status) { openDialog(T("Подключение ИИ"), `${dataError("assistantStatus")}${button(T("Повторить"), "route-retry")}`); return; }
    const endpoints = status.allowed_endpoints || [];
    const keyPlaceholder = status.has_key ? T("Оставьте пустым, чтобы сохранить ключ") : T("Ключ провайдера");
    const connectionForm = endpoints.length ? `<form id="assistant-connection-form" data-version="${status.connection_version}">${select("provider", T("Протокол"), [["ollama", "Ollama"], ["openai_compatible", "OpenAI compatible"]], status.provider || "ollama")}${select("base_url", T("Адрес, разрешённый оператором"), endpoints.map(url => [url,url]), status.base_url || endpoints[0])}${field({name: "model", label: T("Идентификатор модели"), value: status.model || "", required: true})}<label class="field"><span>${H("API-ключ")}</span><input type="password" name="api_key" autocomplete="new-password" maxlength="4096" placeholder="${esc(keyPlaceholder)}"><small>${H("Ключ шифруется на сервере и не возвращается в интерфейс.")}</small></label><button class="button primary" type="submit">${H("Сохранить подключение")}</button><output id="assistant-connection-message" class="form-message"></output></form>` : ("<p class=\"notice\">" + H("Оператор ещё не указал разрешённые адреса моделей.") + "</p>");
    const checkedAt = status.health?.checked_at ? `${T("Последняя проверка:")} ${esc(date(status.health.checked_at,true))} ${T("МСК")}` : T("Соединение ещё не проверено.");
    openDialog(T("Подключение ИИ"), `<p class="help-copy">${esc(assistantHealthLabel(status))}</p><p class="fine-print">${H("Сервис проверяет наличие указанной модели и доступность API отдельно от сохранения настроек.")}</p>${connectionForm}<div class="form-actions">${button(T("Проверить соединение"), "assistant-health", {small: true, extra: !status.enabled || !status.configured ? "disabled" : ""})}${status.connection_version ? button(T("Удалить подключение"), "assistant-disconnect", {small: true}) : ""}</div><p class="fine-print">${checkedAt}</p>`);
  };
  const saveAssistantConnection = async form => {
    if (!requireUser() || !form.reportValidity() || form.dataset.busy === "true") return;
    const generation = state.generation;
    form.dataset.busy = "true";
    const button = form.querySelector("button");
    button.disabled = true;
    const document = {provider: form.elements.provider.value, base_url: form.elements.base_url.value, model: form.elements.model.value.trim()};
    if (form.elements.api_key.value) document.api_key = form.elements.api_key.value;
    try {
      const saved = await api("/api/assistant/connection", {method: "PUT", body: {document, expected_version: Number(form.dataset.version)}});
      if (generation !== state.generation) return;
      form.elements.api_key.value = "";
      state.data.assistantStatus = saved;
      if (form.isConnected && $("#workspace-dialog").open) await openAssistantConnection();
    } catch (error) {
      if (generation === state.generation && !isCancelled(error)) showMessage($("#assistant-connection-message"), humanError(error), true);
    } finally {
      form.dataset.busy = "false";
      if (form.isConnected) button.disabled = false;
    }
  };
  const assistantConnectionOperation = async operation => {
    if (!requireUser()) return;
    const generation = state.generation;
    const sequence = state.eventRequest;
    const saved = operation === "check" ? await api("/api/assistant/connection/check", {method: "POST", body: {}}) : await api("/api/assistant/connection", {method: "DELETE", body: {expected_version: state.data.assistantStatus?.connection_version}});
    if (generation !== state.generation) return;
    state.data.assistantStatus = saved;
    if (sequence === state.eventRequest && $("#workspace-dialog").open) await openAssistantConnection();
  };
  const ensureAssistantConversation = async (message, generation) => {
    if (state.assistantConversation) return;
    const created = await api("/api/assistant/conversations", {method: "POST", body: {title: message.slice(0, 120)}});
    if (generation === state.generation) state.assistantConversation = {...created, messages: [], next_before: null};
  };
  const reportAssistantFailure = async (error, generation) => {
    if (generation !== state.generation || isCancelled(error)) return;
    state.assistantBusy = false;
    if (state.assistantRequest) state.assistantRequest.status = "uncertain";
    if (state.assistantConversation) await loadAssistantConversation(state.assistantConversation.id).catch(() => null);
    if (generation !== state.generation) return;
    if (state.view === "assistant") {
      renderAssistant();
      showMessage($("#assistant-message"), humanError(error) + T(" Проверьте историю перед отправкой нового вопроса."), true);
    } else toast(humanError(error), true);
  };
  const sendAssistant = async form => {
    if (!requireUser() || state.assistantBusy || !state.data.assistantStatus?.enabled || !state.data.assistantStatus?.configured || !form.reportValidity()) return;
    const draft = assistantDraftFromForm(form);
    const message = draft.message.trim();
    if (!message) return;
    const generation = state.generation;
    state.assistantDraft = draft;
    state.assistantBusy = true;
    renderAssistant();
    try {
      await ensureAssistantConversation(message, generation);
      if (generation !== state.generation) return;
      const selected = state.assistantConversation;
      state.assistantBusy = true;
      renderAssistant();
      const request = {id: crypto.randomUUID(), conversation_id: selected.id, status: "running", reply_prefix: "", stream_sequence: 0};
      state.assistantRequest = request;
      updateViewRoute({screen: "conversation", conversation: selected.id}, {replace: true});
      paintAssistantRequest();
      await api("/api/assistant/messages/stream", {method: "POST", timeout: 120000, body: {
        conversation_id: selected.id, request_id: request.id, expected_version: selected.version,
        message, context: draft.context, include_news: draft.context === "investment" && draft.include_news,
        research_run_id: draft.context === "investment" ? draft.research_run_id || null : null,
        memory_ids: [...(state.assistantMemorySelected || [])]
      }, onStream: (response, ensure) => readAssistantStream(response, request, ensure)});
      if (generation !== state.generation) return;
      if (state.assistantRequest?.status === "completed") { state.assistantDraft.message = ""; const currentForm = $("#assistant-form"); if (currentForm) { currentForm.elements.message.value = ""; clearScreenDraft(currentForm); } }
      state.assistantBusy = false;
      await loadAssistantConversation(selected.id);
      await Promise.allSettled([loadResource("assistantStatus", "/api/assistant/status", {force: true}), loadResource("assistantConversations", "/api/assistant/conversations", {force: true})]);
      if (generation === state.generation && state.view === "assistant") {
        renderAssistant();
        $("#chat-messages").scrollTop = $("#chat-messages").scrollHeight;
      }
    } catch (error) {
      await reportAssistantFailure(error, generation);
    } finally { if (generation === state.generation) state.assistantBusy = false; }
  };

  function assistantRequestHTML() {
    const request = state.tour ? null : state.assistantRequest;
    if (!request) return "";
    const running = request.status === "running";
    const status = {running: T("assistant.generating"), uncertain: T("assistant.incomplete"), cancelled: T("assistant.cancelled"), completed: T("assistant.completed")}[request.status] || T("assistant.incomplete");
    const text = request.reply_prefix || "";
    const provisional = text && request.status !== "completed" ? `<p class="notice warning">${H("assistant.provisional")}</p><p class="assistant-prefix">${esc(text)}</p>` : "";
    return `<section class="assistant-stream" aria-live="polite"><p class="fine-print">${esc(status)}</p>${provisional}<div class="form-actions">${running ? button(T("assistant.stop"), "assistant-cancel", {small: true}) : ""}${request.status !== "completed" ? button(T("assistant.readback"), "assistant-request-read", {small: true}) : ""}</div></section>`;
  }
  function paintAssistantRequest() { const element = $("#assistant-request"); if (element) element.innerHTML = assistantRequestHTML(); }
  async function readAssistantStream(response, request, ensure) {
    if (!response.headers.get("Content-Type")?.includes("text/event-stream") || !response.body) throw new Error("assistant_stream_invalid");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let terminal = false;
    const accept = block => {
      const lines = block.split(/\r?\n/);
      const event = lines.find(line => line.startsWith("event:"))?.slice(6).trim();
      const json = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
      if (!json) return;
      const data = JSON.parse(json);
      if (data.request_id !== request.id) throw new Error("assistant_stream_invalid");
      if (event === "delta") {
        if (typeof data.reply_prefix !== "string" || data.reply_prefix.length > 100000 || !Number.isSafeInteger(data.sequence)) throw new Error("assistant_stream_invalid");
        if (data.sequence > request.stream_sequence) { request.reply_prefix = data.reply_prefix; request.stream_sequence = data.sequence; }
      } else if (event === "complete") { request.status = "completed"; request.result = data.result; terminal = true; }
      else if (event === "cancelled") { request.status = "cancelled"; terminal = true; }
      else if (event === "error") { request.status = "uncertain"; throw Object.assign(new Error(data.code || "assistant_unavailable"), {code: data.code}); }
      paintAssistantRequest();
    };
    try {
      while (true) {
        const {value, done} = await reader.read();
        ensure();
        buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
        if (buffer.length > 524288) throw new Error("assistant_response_too_large");
        let match;
        while ((match = /\r?\n\r?\n/.exec(buffer))) {
          const block = buffer.slice(0, match.index);
          buffer = buffer.slice(match.index + match[0].length);
          accept(block);
        }
        if (done || terminal) break;
      }
      if (!terminal) throw new Error("assistant_response_incomplete");
      return request.result;
    } finally { await reader.cancel().catch(() => null); }
  }
  async function readAssistantRequest(cancel = false) {
    const request = state.assistantRequest;
    if (!requireUser() || !request?.id) return;
    const generation = state.generation;
    try {
      const saved = await api(`/api/assistant/requests/${safeSegment(request.id)}${cancel ? "/cancel" : ""}`, cancel ? {method: "POST", body: {}} : {});
      if (generation !== state.generation || state.assistantRequest?.id !== request.id) return;
      state.assistantRequest = {...saved, id: saved.request_id || request.id};
      paintAssistantRequest();
      if (["completed", "cancelled"].includes(saved.status)) {
        state.assistantBusy = false;
        if (state.assistantConversation) await loadAssistantConversation(state.assistantConversation.id);
      }
      return saved;
    } catch (error) { if (generation === state.generation && !isCancelled(error)) showMessage($("#assistant-message"), humanError(error), true); }
  }
  function assistantMemoryChoice(item) {
    const checked = state.assistantMemorySelected?.has(item.id) ? " checked" : "";
    const disabled = state.assistantBusy ? " disabled" : "";
    return `<label class="check-field"><input type="checkbox" data-memory-select="${esc(item.id)}"${checked}${disabled}><span>${esc(item.content)}</span></label>`;
  }
  function assistantMemoryChoices() {
    const items = state.tour ? [] : state.data.assistantMemory?.items || [];
    if (!items.length) return "";
    return `<details class="section-gap"><summary class="details-summary">${H("assistant.memory_selection")}</summary>${items.map(assistantMemoryChoice).join("")}<p class="fine-print">${H("assistant.memory_selection_help")}</p></details>`;
  }
  function assistantMemoryHTML() {
    if (state.tour) return empty(T("assistant.memory"), T("assistant.memory_help"), "login", T("Войти"));
    const data = state.data.assistantMemory;
    const rows = (data?.items || []).map(item => `<article class="event-item"><div class="event-item-body"><p>${esc(item.content)}</p><p class="fine-print">${esc(item.category === "preference" ? T("assistant.preference") : T("assistant.context"))} · ${H("Версия")}: ${esc(item.version)}</p><div class="form-actions"><button class="button secondary small-button" data-memory-edit="${esc(item.id)}">${H("assistant.memory_edit")}</button><button class="button danger small-button" data-memory-delete="${esc(item.id)}">${H("Удалить")}</button></div></div></article>`).join("");
    const content = rows || `<p class="notice">${H("assistant.memory_empty")}</p>`;
    const loading = !data && !state.errors.assistantMemory;
    return `${cardHeader(T("assistant.memory"))}<p class="fine-print">${H("assistant.memory_help")}</p>${dataError("assistantMemory")}${loading ? U.loading(T("state.loading")) : content}<div id="assistant-memory-editor">${assistantMemoryForm()}</div>`;
  }
  function assistantMemoryForm(item = null) {
    return `<form id="assistant-memory-form" class="section-gap" data-id="${esc(item?.id || (state.assistantMemoryDraftId ||= crypto.randomUUID()))}" data-version="${item?.version || 0}">${select("category", T("assistant.memory_kind"), [["preference", T("assistant.preference")], ["context", T("assistant.context")]], item?.category || "preference")}<label class="field"><span>${H("assistant.memory_content")}</span><textarea name="content" maxlength="1000" rows="4" required>${esc(item?.content || "")}</textarea></label><label class="check-field"><input type="checkbox" name="confirmed" required><span>${H("assistant.memory_confirm")}</span></label><div class="form-actions"><button class="button primary" type="submit">${H("Сохранить")}</button></div><output id="assistant-memory-message" class="form-message"></output></form>`;
  }
  async function reconcileAssistantMemory(form, body, error, generation) {
    await loadResource("assistantMemory", "/api/assistant/memory", {force: true});
    if (generation !== state.generation) return;
    const actual = state.data.assistantMemory?.items?.find(item => item.id === form.dataset.id);
    const confirmed = actual && actual.content === body.content && actual.category === body.category && actual.version > Number(form.dataset.version);
    if (confirmed) {
      clearScreenDraft(form);
      if (state.view === "assistant") renderAssistant();
    } else showMessage($("#assistant-memory-message"), humanError(error), true);
  }
  async function saveAssistantMemory(form) {
    if (!requireUser() || form.dataset.busy === "true" || !form.reportValidity()) return;
    const generation = state.generation;
    const id = form.dataset.id;
    const version = Number(form.dataset.version);
    const body = {content: form.elements.content.value.trim(), category: form.elements.category.value, confirmed: form.elements.confirmed.checked, expected_version: version};
    form.dataset.busy = "true";
    form.querySelector("button[type=submit]").disabled = true;
    try {
      await api(`/api/assistant/memory${version ? "/" + safeSegment(id) : ""}`, {method: version ? "PUT" : "POST", body: version ? body : {...body, id}});
      if (generation !== state.generation) return;
      clearScreenDraft(form);
      if (!version) state.assistantMemoryDraftId = null;
      await loadResource("assistantMemory", "/api/assistant/memory", {force: true});
      if (generation === state.generation && state.view === "assistant") renderAssistant();
    } catch (error) {
      if (generation !== state.generation || isCancelled(error)) return;
      await reconcileAssistantMemory(form, body, error, generation);
    } finally { if (form.isConnected) { form.dataset.busy = "false"; form.querySelector("button[type=submit]").disabled = false; } }
  }
  async function deleteAssistantMemory(id) {
    const item = state.data.assistantMemory?.items?.find(row => row.id === id);
    if (!requireUser() || !item) return;
    const generation = state.generation;
    await api(`/api/assistant/memory/${safeSegment(id)}`, {method: "DELETE", body: {expected_version: item.version}});
    if (generation !== state.generation) return;
    state.assistantMemorySelected?.delete(id);
    await loadResource("assistantMemory", "/api/assistant/memory", {force: true});
    if (generation === state.generation) { $("#workspace-dialog").close(); renderAssistant(); }
  }
  function assistantSourcesHTML() {
    if (state.tour) return empty(T("assistant.sources"), T("assistant.sources_scope"), "login", T("Войти"));
    const selection = state.assistantSourceSelection || {context: "general", query: ""};
    const runs = state.data.assistantResearch?.items || [];
    return `${cardHeader(T("assistant.sources"))}<p class="notice">${H("assistant.sources_scope")}</p><form id="assistant-sources-form">${select("context", T("Данные для этого вопроса"), [["general", T("Общий вопрос · без личных данных")], ["portfolio", T("Сводные показатели портфеля")], ["investment", T("Портфель, позиции, цели и стратегия")]], selection.context)}${select("research_run_id", T("Сохранённое исследование"), [["", T("Не передавать")], ...runs.map(item => [item.id, date(item.created_at, true)])], selection.research_run_id || "")}<label class="check-field"><input type="checkbox" name="include_news"${selection.include_news ? " checked" : ""}><span>${H("Добавить последние новости Банка России")}</span></label>${field({name: "query", label: T("Поиск"), value: selection.query || "", required: true})}<div class="form-actions"><button class="button primary" type="submit">${H("Найти")}</button></div><output id="assistant-sources-message" class="form-message"></output></form><div id="assistant-source-results" class="section-gap">${assistantSourcesResults()}</div>`;
  }
  function assistantSourcesResults() {
    const page = state.assistantSources;
    if (!page) return "";
    return (page.items || []).map(item => `<article class="event-item"><div class="event-item-body"><h3>${esc(item.label || item.kind)}</h3><p>${esc(item.excerpt || "")}</p><button class="button secondary small-button" data-assistant-source="${esc(item.id)}">${H("Открыть")}</button></div></article>`).join("") || `<p class="notice">${H("Совпадений не найдено")}</p>`;
  }
  async function searchAssistantSources(form) {
    if (!requireUser() || form.dataset.busy === "true") return;
    const generation = state.generation;
    const context = form.elements.context.value;
    const selection = {context, include_news: context === "investment" && form.elements.include_news.checked, research_run_id: context === "investment" ? form.elements.research_run_id.value || null : null, query: form.elements.query.value.trim(), limit: 20};
    form.dataset.busy = "true";
    const target = $("#assistant-source-results");
    target.innerHTML = U.loading(T("state.loading"));
    try {
      const page = await api("/api/assistant/sources/search", {method: "POST", body: selection});
      if (generation !== state.generation || !form.isConnected) return;
      state.assistantSourceSelection = selection;
      state.assistantSources = page;
      clearScreenDraft(form);
      target.innerHTML = assistantSourcesResults();
    } catch (error) { if (generation === state.generation && !isCancelled(error)) { target.replaceChildren(); showMessage($("#assistant-sources-message"), humanError(error), true); } }
    finally { if (form.isConnected) form.dataset.busy = "false"; }
  }
  async function readAssistantSource(id, requestId = "") {
    if (!requireUser() || (!requestId && !state.assistantSourceSelection)) return;
    const {query, limit, ...selection} = state.assistantSourceSelection || {};
    const body = requestId ? {source_id: id, request_id: requestId} : {...selection, source_id: id};
    const generation = state.generation;
    openDialog(T("assistant.sources"), U.loading(T("state.loading")));
    const sequence = state.eventRequest;
    try {
      const source = await api("/api/assistant/sources/read", {method: "POST", body});
      if (generation !== state.generation || sequence !== state.eventRequest) return;
      openDialog(source.label || T("assistant.sources"), `<p class="fine-print">${H(source.immutable ? "assistant.saved_source" : "assistant.sources_scope")}</p><pre class="source-document">${esc(typeof source.content === "string" ? source.content : JSON.stringify(source.content, null, 2))}</pre>${source.url ? U.sourceLink(source.url, T("Первоисточник")) : ""}`);
    } catch (error) { if (generation === state.generation && sequence === state.eventRequest && !isCancelled(error)) openDialog(T("assistant.sources"), `<p class="notice error">${esc(humanError(error))}</p>`); }
  }

  const dialogScreens = new Set(["goals/create", "goals/edit", "goals/plan", "events/detail", "events/news", "strategies/archive", "strategies/evidence", "strategies/result", "strategies/detail", "strategies/plan", "strategies/executions", "assistant/connection", "profile/plan"]);
  const transientDialogs = new Map();
  let tableQuotesTimer = null;
  let tableQuotesBusy = false;
  let eventSummaryTimer = null;
  let eventSummaryBusy = false;
  let pwaRegistration = null;
  let acceptingUpdate = false;
  function initializeNavigation() {
    history.scrollRestoration = "manual";
    let hash = location.hash;
    const standalone = matchMedia("(display-mode: standalone)").matches || matchMedia("(display-mode: fullscreen)").matches || navigator.standalone;
    if (!hash && standalone) {
      try {
        const saved = localStorage.getItem("omnicio-last-route");
        if (saved) hash = U.routeHash(U.resumeRoute(U.parseRoute(saved)));
      } catch { /* Last route is optional. */ }
    }
    const route = U.parseRoute(hash);
    if (route.invalid) { showRouteError(); return; }
    if (route.mode === "auto") {
      if (hash) navigate(route.view, {...route, mode: "account"}, {replace: true});
      else { state.mode = "auto"; sessionSurface(); }
    } else navigate(route.view, route, {replace: true});
    const expected = window.OMNICIO_RELEASE?.build;
    if (expected && [U.compiledBuild, I.compiledBuild, "__OMNICIO_BUILD__"].some(build => build && build !== expected)) flagApplicationUpdate();
  }
  function enterRouteScreen(view, screen, detail = {}) {
    if (state.view === view && state.route.screen === screen && Object.entries(detail).every(([key, value]) => state.route[key] === value)) return false;
    navigate(view, {...detail, screen});
    return true;
  }
  async function restoreRouteOverlay(route) {
    if (route.mode === "public" && route.view === "support") {
      await loadSupport($("#support"));
      return true;
    }
    if (route.overlay === "auth") {
      openAuth(state.authMode || "login");
      return true;
    }
    const saved = transientDialogs.get(route.overlay);
    if (!saved) return false;
    openDialog(saved.title, saved.content);
    return true;
  }
  async function openResearchResult(route, sequence) {
    if (!route.run) return;
    const payload = await api(`/api/research/runs/${safeSegment(route.run)}`);
    if (sequence !== state.navigationSequence) return;
    state.strategy.research = {...payload.result, archive: {id: payload.id, created_at: payload.created_at, strategy_version: payload.strategy_version}};
    openDialog(T("Исследование на истории"), renderResearch());
  }
  const routeScreenHandlers = {
    "goals/create": () => openGoal(),
    "goals/edit": route => openGoal(route.goal_id),
    "goals/plan": route => openGoalPlan(route.goal_id),
    "events/detail": route => openEvent(route.event),
    "events/news": route => openNews(route.news),
    "strategies/archive": () => openResearchArchive(),
    "strategies/evidence": () => openResearchEvidence(),
    "strategies/detail": route => openPublicStrategy(route.preset),
    "strategies/plan": () => openExecutionPlanner(),
    "strategies/executions": () => openExecutionHistory(),
    "strategies/result": openResearchResult,
    "assistant/connection": () => openAssistantConnection(),
    "profile/plan": () => openBilling(),
    "settings/support": () => loadSupport($("#workspace-support"))
  };
  async function openRouteScreen(route) {
    if (route.mode !== "public" && route.mode !== "demo" && (!state.user || state.locked)) return;
    const sequence = state.navigationSequence;
    state.openingRoute = true;
    try {
      if (await restoreRouteOverlay(route)) return;
      if (sequence !== state.navigationSequence) return;
      const handler = routeScreenHandlers[`${route.view}/${route.screen}`];
      if (handler) await handler(route, sequence);
    } catch (error) {
      if (sequence === state.navigationSequence && !isCancelled(error)) openDialog(T("state.load_failed"), `<p class="notice error">${esc(humanError(error))}</p>${button(T("Повторить загрузку"), "route-retry")}`);
    } finally { if (sequence === state.navigationSequence) state.openingRoute = false; }
  }
  function draftKey(form) { return `${form.id}:${form.dataset.goalId || form.dataset.id || ""}`; }
  function draftForms(root = document) {
    return $$("form[id]", root).filter(form => /^(goal-form|goal-plan-form|research-evidence-form|profile-form|preferences-form|assistant-form|research-form|assistant-memory-form|assistant-sources-form)$/.test(form.id));
  }
  function draftValues(form) {
    return Object.fromEntries([...form.elements].filter(control => control.name && !["password", "file", "submit", "button", "hidden"].includes(control.type) && !/credential|token|code|secret/.test(control.name)).map(control => [control.name, control.type === "checkbox" ? control.checked : control.value]));
  }
  function captureScreenDrafts() {
    for (const form of draftForms()) {
      if (form.closest("dialog") && !form.closest("dialog").open) continue;
      const key = draftKey(form);
      const values = draftValues(form);
      if (state.screenBaselines[key] === undefined) state.screenBaselines[key] = JSON.stringify(values);
      if (JSON.stringify(values) !== state.screenBaselines[key]) state.screenDrafts[key] = values;
      else delete state.screenDrafts[key];
    }
  }
  function restoreFormFields(form, draft) {
    if (form.id === "goal-form" && draft.kind) {
      form.elements.kind.value = draft.kind;
      updateGoalFields(true);
    }
    for (const [name, value] of Object.entries(draft)) {
      const control = form.elements.namedItem(name);
      if (!control || control.type === "password" || control.type === "file") continue;
      if (control.type === "checkbox") control.checked = value === true;
      else control.value = value;
    }
    if (form.id === "goal-form") updateGoalFields();
    if (form.id === "goal-plan-form") updateGoalPlanFields();
    if (form.id === "assistant-form") updateAssistantContext();
    form.dataset.draftRestored = "true";
  }
  function restoreScreenDrafts(root) {
    if (state.tour) return;
    for (const form of draftForms(root)) {
      const key = draftKey(form);
      const draft = state.screenDrafts[key];
      if (!draft || state.screenBaselines[key] === undefined) state.screenBaselines[key] = JSON.stringify(draftValues(form));
      if (draft) restoreFormFields(form, draft);
    }
  }
  function clearScreenDraft(form) {
    const key = draftKey(form);
    delete state.screenDrafts[key];
    state.screenBaselines[key] = JSON.stringify(draftValues(form));
  }
  function screenLink(view, [key, title, detail]) {
    const selected = state.route.screen === key;
    const note = detail ? `<small>${esc(detail)}</small>` : "";
    return `<a class="screen-menu-item${selected ? " selected" : ""}" href="${U.routeHash({mode: state.mode, view, screen: key})}" data-route="${view}" data-screen="${key}"${selected ? ' aria-current="page"' : ""}><span><strong>${esc(title)}</strong>${note}</span>${icon("arrow", true)}</a>`;
  }
  function screenLinks(view, panes) {
    return `<nav class="screen-menu" aria-label="${H("navigation.sections")}">${panes.map(pane => screenLink(view, pane)).join("")}</nav>`;
  }
  function layoutMarket({root, attach}) {
    const columns = $$(":scope > .two-column > section", root);
    attach("reference", T("Курсы Банка России"), [columns[0], $(".market-indicators", root)]);
    attach("watchlist", T("Избранное"), columns[1]);
    const sections = $$(":scope > section", root);
    attach("positions", T("Активы вашего счёта"), sections[0]);
    attach("news", T("Новости Банка России"), sections[1]);
  }
  function layoutPortfolio({root, screen, panes, attach}) {
    const columns = $$(":scope > .two-column > section", root);
    attach("history", T("Стоимость портфеля"), columns[0]);
    attach("structure", T("Структура портфеля"), columns[1]);
    attach("positions", T("Мои активы"), $(":scope > section", root));
    panes.push(["income", T("Полученные выплаты")], ["operations", T("portfolio.operations")]);
    if (screen === "income") root.insertAdjacentHTML("beforeend", `<section class="card" data-screen-content="income">${cardHeader(T("Полученные выплаты"))}${incomePaneHTML()}</section>`);
    if (screen === "operations") root.insertAdjacentHTML("beforeend", `<section id="ledger-screen" class="card" data-screen-content="operations">${ledgerHTML()}</section>`);
  }
  function layoutAnalytics({root, attach}) {
    const groups = $$(":scope > .two-column", root);
    attach("history", T("Стоимость по наблюдениям"), groups[0]?.children[0]);
    attach("performance", T("Из чего складывается результат"), groups[0]?.children[1]);
    attach("income", T("Выплаты до налоговых списаний"), groups[1]?.children[0]);
    attach("risk", T("Полнота данных и риски"), groups[1]?.children[1]);
  }
  function layoutSettings({root, screen, panes, attach}) {
    if (state.tour) return;
    const form = $("#preferences-form", root);
    const sections = form ? $$(":scope > section", form) : [];
    attach("appearance", T("Оформление и приватность"), sections[0]);
    attach("notifications", T("Уведомления"), [sections[1], $("#notification-settings", root)]);
    if (sections[0]) sections[0].insertAdjacentHTML("beforeend", `<div class="form-actions"><button class="button primary" type="submit">${H("Сохранить настройки")}</button></div>${saveErrorHTML("prefs")}`);
    attach("broker", T("Подключение T-Invest"), $("#broker-settings", root));
    attach("recovery", T("Ранее начатые исполнения"), $("#recovery-settings", root));
    const right = $$(".settings-layout > div:last-child > section", root);
    for (const item of right.filter(item => !item.id)) {
      if ($('[data-action="legal"]', item)) attach("about", T("О приложении"), item);
      else item.hidden = true;
    }
    attach("operations", T("ops.title"), $("#operations-settings", root));
    panes.push(["support", T("support.title")]);
    if (screen === "support") root.insertAdjacentHTML("beforeend", `<section id="workspace-support" class="card" data-screen-content="support">${supportHTML()}</section>`);
  }
  function layoutProfile({root, attach}) {
    if (state.tour) return;
    const sections = $$(".settings-layout > section", root);
    attach("personal", T("Мой профиль"), sections[0]);
    attach("identities", T("Способы входа"), [sections[1], sections[4]]);
    attach("delete", T("Удаление аккаунта"), sections[2]);
    attach("sessions", T("Активные сессии"), sections[3]);
    attach("plan", T("План и подписка"), sections[5]);
  }
  function layoutAssistant({root, screen, panes, attach}) {
    attach("conversation", T("assistant.chat"), $(".chat-card", root));
    attach("history", T("Ваши разговоры"), $(".assistant-side", root));
    panes.push(["memory", T("assistant.memory")], ["sources", T("assistant.sources")], ["connection", T("Подключение ИИ")]);
    if (!screen) root.insertAdjacentHTML("beforeend", `<section class="card"><p class="notice">${esc(assistantHealthLabel(state.data.assistantStatus))}</p><p>${H("assistant.workspace_help")}</p></section>`);
    if (screen === "memory") root.insertAdjacentHTML("beforeend", `<section id="assistant-memory-screen" class="card" data-screen-content="memory">${assistantMemoryHTML()}</section>`);
    if (screen === "sources") root.insertAdjacentHTML("beforeend", `<section id="assistant-sources-screen" class="card" data-screen-content="sources">${assistantSourcesHTML()}</section>`);
  }
  function layoutStrategies({root, screen, panes, attach}) {
    attach("catalog", T("Готовые стратегии"), $(".strategy-catalog", root));
    const editors = $$(".strategy-editor > section", root);
    attach("editor", T("Моя настройка"), editors[0]);
    attach("assessment", T("Проверка на вашем счёте"), editors[1]);
    attach("research", T("Исследование на истории"), editors[2]);
    attach("plan", T("execution.title"), editors[3]);
    panes.push(["archive", T("Архив исследований")], ["evidence", T("Дополнительные источники исследования")], ["executions", T("execution.history")]);
    if (!state.tour && !state.strategy.draft && screen && screen !== "catalog") {
      const placeholder = $(".strategy-layout > section", root);
      if (placeholder) placeholder.hidden = false;
    }
  }
  const screenLayoutHandlers = {market: layoutMarket, portfolio: layoutPortfolio, analytics: layoutAnalytics, settings: layoutSettings, profile: layoutProfile, assistant: layoutAssistant, strategies: layoutStrategies};
  function addScreenNavigation(root, view, screen, panes) {
    root.classList.add("has-screen-menu");
    root.dataset.screen = screen;
    const label = panes.find(([key]) => key === screen)?.[1] || T("Подробности");
    const chip = screen ? `<span class="chip">${esc(label)}</span>` : "";
    root.insertAdjacentHTML("afterbegin", `<div class="screen-navigation"><button class="button secondary small-button" data-action="route-back">${icon("back", true)} ${H("navigation.back")}</button>${chip}</div>`);
    const header = $(".view-header", root);
    if (header) header.insertAdjacentHTML("afterend", screenLinks(view, panes));
    for (const wrapper of $$(".two-column,.settings-layout,.settings-layout > div,.strategy-layout,.strategy-editor,.assistant-layout", root)) wrapper.classList.add("screen-layout");
  }
  function applyScreenLayout(view) {
    if (state.view !== view) return;
    const root = $(`#view-${view}`);
    if (!root) return;
    const screen = state.route.screen || "";
    const panes = [];
    const attach = (key, title, elements) => {
      const nodes = (Array.isArray(elements) ? elements : [elements]).filter(Boolean);
      if (!nodes.length) return;
      panes.push([key, title]);
      for (const node of nodes) { node.dataset.screenContent = key; node.hidden = screen !== key; }
    };
    screenLayoutHandlers[view]?.({root, screen, panes, attach});
    if (panes.length) addScreenNavigation(root, view, screen, panes);
    for (const anchor of $$('a[href^="/legal/"]', root)) { anchor.removeAttribute("target"); anchor.removeAttribute("rel"); }
    restoreScreenDrafts(root);
  }
  function incomePaneHTML() {
    const income = state.data.workspace?.income;
    if (!income) return state.loading.has("workspace") ? U.loading(T("state.loading")) : dataError("workspace") || empty(T("История выплат пока недоступна"), T("Для расчёта нужны подтверждённые операции брокера."));
    return infoRows([[T("Купоны"), money(income.coupons_rub)], [T("Дивиденды"), money(income.dividends_rub)], [T("Прочие доходы"), money(income.other_income_rub)], [T("Погашения капитала"), money(income.redemptions_rub)]]) + `<p class="fine-print">${esc(date(income.from))} — ${esc(date(income.to))}</p>`;
  }
  function ledgerRow(item, names) {
    const instrument = item.instrument_uid ? `<button class="button secondary small-button" data-asset="${esc(item.instrument_uid)}">${esc(item.ticker || T("Инструмент"))}</button>` : "—";
    const category = names[item.category] || T("portfolio.unclassified");
    const amount = money(item.payment?.value, 2, String(item.payment?.currency || "").toUpperCase());
    return `<tr><td>${esc(date(item.operation_date, true))}</td><td>${esc(item.name || item.description || item.operation_type)}<small class="fine-print">${esc(category)}</small></td><td>${esc(amount)}</td><td>${instrument}</td></tr>`;
  }
  function ledgerHTML() {
    const data = state.data.ledger;
    if (!data) return state.errors.ledger ? dataError("ledger") : U.loading(T("state.loading"));
    const names = {contribution: T("portfolio.contribution"), withdrawal: T("portfolio.withdrawal"), fee: T("Комиссии за период"), tax: T("Налоги"), income: T("Полученные выплаты"), principal_return: T("Погашения капитала"), internal: T("portfolio.internal"), non_cash_transfer: T("portfolio.non_cash"), unclassified: T("portfolio.unclassified")};
    const rows = (data.items || []).map(item => ledgerRow(item, names)).join("");
    const table = rows ? `<div class="table-scroll"><table class="asset-table"><thead><tr><th>${H("Дата")}</th><th>${H("Операция")}</th><th>${H("Сумма")}</th><th>${H("Инструмент")}</th></tr></thead><tbody>${rows}</tbody></table></div>` : empty(T("portfolio.no_operations"), T("portfolio.no_operations_details"));
    const more = data.next_cursor ? button(T("Загрузить ещё"), "ledger-more", {small: true, extra: state.loading.has("ledger-more") ? " disabled" : ""}) : "";
    return `${cardHeader(T("portfolio.operations"))}${freshness(data.source || "T-Invest", data.observed_at, data.status)}${dataError("ledger")}<p class="fine-print">${H("portfolio.operations_notice")}</p>${table}${more}`;
  }
  async function loadLedgerPage() {
    if (!state.data.ledger?.next_cursor || state.loading.has("ledger-more")) return;
    const generation = state.generation;
    state.loading.add("ledger-more");
    try {
      const page = await api(`/api/workspace/operations?limit=50&cursor=${encodeURIComponent(state.data.ledger.next_cursor)}`);
      if (generation === state.generation) { state.data.ledger = mergePage(state.data.ledger, page); delete state.errors.ledger; }
    } catch (error) { if (generation === state.generation && !isCancelled(error)) state.errors.ledger = error; }
    finally { state.loading.delete("ledger-more"); if (generation === state.generation && state.view === "portfolio") renderPortfolio(); }
  }
  function supportAddress(value) {
    if (typeof value !== "string" || value.length > 254 || /[\s<>]/.test(value)) return "";
    const parts = value.split("@");
    if (parts.length !== 2 || !parts[0] || !parts[1]) return "";
    const domain = parts[1];
    const dot = domain.lastIndexOf(".");
    return dot > 0 && dot < domain.length - 1 ? value : "";
  }
  function supportHTML() {
    const data = state.data.support;
    if (!data) return dataError("support") || U.loading(T("state.loading"));
    const address = supportAddress(data.email);
    const compose = address ? `<a class="button primary" href="mailto:${esc(encodeURIComponent(address))}?subject=${encodeURIComponent("OMNICIO " + (window.OMNICIO_RELEASE?.version || ""))}">${H("support.compose")}</a>` : `<p class="notice">${H("support.unavailable")}</p>`;
    return `${heading(T("support.title"))}<p>${H("support.description")}</p>${infoRows([[T("support.operator"), data.name || "—"], ["Email", address || "—"], [T("Версия"), window.OMNICIO_RELEASE?.version || "—"], [T("support.route"), U.routeHash(activeRoute())]])}<p class="fine-print">${H("support.safe_details")}</p>${compose}`;
  }
  async function loadSupport(target) {
    if (!target) return;
    await loadResource("support", "/api/public/support");
    if (target.isConnected) target.innerHTML = supportHTML();
  }
  function flagApplicationUpdate() {
    state.outdated = true;
    for (const banner of $$("#update-banner,#dialog-update-banner")) {
      banner.hidden = false;
      banner.innerHTML = `<span>${H("pwa.update_available")}</span>${button(T("pwa.apply"), "pwa-update", {small: true})}`;
    }
  }
  const updateDraftFields = Object.freeze({
    "goal-form": ["title", "kind", "target_amount_rub", "target_date", "start_date", "progress_source", "allocation_percent", "manual_amount_rub", "status"],
    "goal-plan-form": ["monthly_contribution_rub", "monthly_income_rub", "annual_return_percent", "annual_volatility_percent", "annual_inflation_percent", "target_in_today_money"],
    "profile-form": ["display_name"],
    "preferences-form": ["theme", "locale", "mask_balances", "notify_portfolio", "notify_payments", "notify_goals", "notify_system", "digest_frequency", "digest_time", "digest_timezone", "quiet_timezone", "quiet_enabled", "quiet_start", "quiet_end"],
    "assistant-form": ["message", "context", "include_news", "research_run_id"]
  });
  function updateDraftPayload() {
    const drafts = {};
    const unsupported = new Set();
    for (const [key, values] of Object.entries(state.screenDrafts)) {
      const form = key.split(":")[0];
      const allowed = updateDraftFields[form];
      if (!allowed) { unsupported.add(form); continue; }
      let baseline = {};
      try { baseline = JSON.parse(state.screenBaselines[key] || "{}"); } catch { /* Ignore an unavailable initial form state. */ }
      const entered = Object.fromEntries(Object.entries(values).filter(([field, value]) => allowed.includes(field) && ["string", "boolean"].includes(typeof value) && String(value).length <= 12000 && value !== baseline[field]));
      if (Object.keys(entered).length) drafts[key] = entered;
    }
    if (state.strategy.dirty) unsupported.add("strategy-form");
    if (Object.values(state.researchDraft).some(value => value !== "")) unsupported.add("research-form");
    if ($$('input[type="password"]').some(input => input.value)) unsupported.add("credentials");
    return {drafts, unsupported: [...unsupported]};
  }
  function restoreUpdateDrafts(publicId) {
    let saved;
    try {
      const raw = sessionStorage.getItem("omnicio-update-drafts");
      if (!raw) return;
      sessionStorage.removeItem("omnicio-update-drafts");
      if (new TextEncoder().encode(raw).byteLength > 131072) return;
      saved = JSON.parse(raw);
    } catch { return; }
    if (saved.version !== 1 || saved.public_id !== publicId || !Number.isFinite(saved.expires_at) || saved.expires_at < Date.now() || saved.expires_at > Date.now() + 1800000 || !saved.drafts || typeof saved.drafts !== "object") return;
    for (const [key, values] of Object.entries(saved.drafts)) {
      const [form, entity = ""] = key.split(":");
      const fields = updateDraftFields[form];
      if (!fields || entity.length > 128 || !values || typeof values !== "object") continue;
      const restored = Object.fromEntries(Object.entries(values).filter(([name, value]) => fields.includes(name) && ["string", "boolean"].includes(typeof value) && String(value).length <= 12000));
      if (Object.keys(restored).length) state.screenDrafts[`${form}:${entity}`] = restored;
    }
    if (Object.keys(state.screenDrafts).length) toast(T("pwa.drafts_restored"));
  }
  async function confirmUpdateReadback() {
    const awaitingResult = researchPending() || state.assistantBusy || state.billingBusy || state.executionBusy || state.recovery.busy || state.prefs.busy || state.strategy.busy || [...state.requests].some(controller => controller.omnicioMutation);
    if (awaitingResult) { toast(T("pwa.finish_work"), true); return false; }
    if ($("#goal-form")?.dataset.uncertain === "true") { toast(T("pwa.goal_readback"), true); return false; }
    if (!state.assistantRequest || !["running", "uncertain"].includes(state.assistantRequest.status)) return true;
    const readback = await readAssistantRequest(false);
    if (readback && state.assistantRequest?.status !== "running") return true;
    toast(T("pwa.finish_work"), true);
    return false;
  }
  function persistUpdateDrafts(drafts) {
    try {
      sessionStorage.removeItem("omnicio-update-drafts");
      if (!Object.keys(drafts).length || !state.user) return true;
      const payload = JSON.stringify({version: 1, public_id: state.user.public_id, expires_at: Date.now() + 1800000, drafts});
      if (new TextEncoder().encode(payload).byteLength > 131072) return false;
      sessionStorage.setItem("omnicio-update-drafts", payload);
      return true;
    } catch { return false; }
  }
  function reviewUpdateLosses(unsupported, saved) {
    const labels = {"research-evidence-form": T("Дополнительные источники исследования"), "research-form": T("Исследование на истории"), "strategy-form": T("Моя настройка"), "assistant-memory-form": T("assistant.memory"), "assistant-sources-form": T("assistant.sources"), credentials: T("API-ключ")};
    const forms = unsupported.map(name => labels[name] || T("pwa.other_form"));
    if (!saved) forms.push(T("pwa.storage_unavailable"));
    const entries = forms.map(name => "<li>" + esc(name) + "</li>").join("");
    openDialog(T("pwa.review_drafts"), `<p>${H("pwa.unsupported_drafts")}</p><ul>${entries}</ul><div class="form-actions">${button(T("pwa.discard_and_update"), "pwa-update-discard", {primary: true})}<button class="button secondary" data-close-dialog>${H("Отмена")}</button></div>`);
  }
  function activateApplicationUpdate() {
    acceptingUpdate = true;
    updateViewRoute({overlay: ""}, {replace: true});
    saveNavigationPosition();
    rememberRoute(activeRoute());
    // Whitelisted typed values are restored after the same server identity is verified.
    // No provider action, response payload, evidence document or credential is replayed.
    state.screenDrafts = {};
    state.formDrafts = {};
    state.prefs.dirty = false;
    state.strategy.dirty = false;
    clearTimeout(state.prefs.timer);
    clearTimeout(state.strategy.timer);
    state.assistantDraft.message = "";
    if (pwaRegistration?.waiting) pwaRegistration.waiting.postMessage({type: "ACTIVATE_UPDATE"});
    else location.reload();
  }
  async function applyApplicationUpdate(discardUnsupported = false) {
    captureScreenDrafts();
    if (!await confirmUpdateReadback()) return;
    const {drafts, unsupported} = updateDraftPayload();
    const saved = persistUpdateDrafts(drafts);
    if ((!saved || unsupported.length) && discardUnsupported !== true) {
      reviewUpdateLosses(unsupported, saved);
      return;
    }
    activateApplicationUpdate();
  }
  function stopTableQuotes() { clearTimeout(tableQuotesTimer); tableQuotesTimer = null; }
  function scheduleTableQuotes(delay = 10000) {
    stopTableQuotes();
    if (state.mode !== "account" || !state.user || state.locked || document.visibilityState !== "visible" || !["home", "portfolio", "market"].includes(state.view)) return;
    tableQuotesTimer = setTimeout(() => void pollTableQuotes(), delay);
  }
  function adoptTableQuotes(items, uids) {
    for (const item of items || []) {
      if (uids.includes(item.instrument_uid)) state.quotes[item.instrument_uid] = item;
    }
    paintTableQuotes();
  }
  function markTableQuotesUnavailable(uids) {
    for (const uid of uids) state.quotes[uid] = {...state.quotes[uid], quote_status: "unavailable"};
    paintTableQuotes();
  }
  async function pollTableQuotes() {
    if (tableQuotesBusy || !navigator.onLine) { scheduleTableQuotes(15000); return; }
    const generation = state.generation;
    const root = $(`#view-${state.view}`);
    const uids = [...new Set($$("[data-table-quote]", root || document).filter(item => item.getClientRects().length).map(item => item.dataset.tableQuote))];
    if (!uids.length) { scheduleTableQuotes(); return; }
    tableQuotesBusy = true;
    try {
      // One batch per fifty displayed instruments, never one provider call per cell.
      for (let offset = 0; offset < uids.length; offset += 50) {
        const chunk = uids.slice(offset, offset + 50);
        const payload = await api(`/api/market/quotes?instrument_uids=${encodeURIComponent(chunk.join(","))}`);
        if (generation !== state.generation || state.tour) return;
        adoptTableQuotes(payload.items, chunk);
      }
    } catch (error) {
      if (generation === state.generation && !isCancelled(error)) markTableQuotesUnavailable(uids);
    } finally { tableQuotesBusy = false; scheduleTableQuotes(); }
  }
  function tableQuoteHTML(item) {
    const quote = state.quotes[item.uid];
    if (!quote) return `<span class="muted">${H("quotes.loading")}</span>`;
    return `<strong>${esc(marketPrice(quote.last_price, quote.price_unit || "unknown", quote.price_currency || ""))}</strong>${freshness("T-Invest", quote.quote_time || quote.observed_at, quote.quote_status)}`;
  }
  function paintTableQuotes() {
    const rows = new Map(portfolioRows().map(item => [item.uid, item]));
    for (const element of $$("[data-table-quote]")) element.innerHTML = tableQuoteHTML(rows.get(element.dataset.tableQuote) || {uid: element.dataset.tableQuote});
  }
  function scheduleEventSummary(delay = 30000) {
    clearTimeout(eventSummaryTimer);
    if (!state.user || state.mode !== "account" || state.locked || document.visibilityState !== "visible") return;
    eventSummaryTimer = setTimeout(() => void pollEventSummary(), delay);
  }
  async function pollEventSummary() {
    if (eventSummaryBusy || !navigator.onLine) { scheduleEventSummary(); return; }
    const generation = state.generation;
    eventSummaryBusy = true;
    try {
      const summary = await api("/api/events/summary");
      if (generation === state.generation && !state.tour) { state.data.eventSummary = summary; updateIdentity(); }
    } catch (error) { if (!isCancelled(error) && generation === state.generation) $("#notifications-button").title = T("events.counter_unavailable"); }
    finally { eventSummaryBusy = false; scheduleEventSummary(); }
  }
  function openPublicStrategy(id) {
    const raw = state.data.catalog?.presets?.find(item => item.id === id);
    if (!raw) { openDialog(T("Стратегии"), `<p class="notice">${H("navigation.not_found")}</p>`); return; }
    const preset = I.preset(raw);
    const sources = (state.data.catalog?.sources || []).filter(item => !preset.source_ids || preset.source_ids.includes(item.id));
    openDialog(preset.title, `<p class="help-copy">${esc(preset.description || "")}</p><p class="notice">${esc(preset.risk || "")}</p><h3>${H("Методика и источники")}</h3><ul class="source-list">${sources.map(renderStrategiesLi).join("")}</ul><p class="fine-print">${H("strategy.demo_description")}</p>${button(T("Войти"), "login", {primary: true})}`);
  }

  const renderCurrent = () => {
    if (state.locked || !state.user && !state.tour) return;
    updateIdentity();
    renderConnectionBanner();
    const renderers = {
      home: renderHome,
      portfolio: renderPortfolio,
      market: renderMarket,
      strategies: renderStrategies,
      assistant: renderAssistant,
      goals: renderGoals,
      analytics: renderAnalytics,
      events: renderEvents,
      profile: renderProfile,
      settings: renderSettings,
      asset: renderAsset,
      search: renderSearch
    };
    renderers[state.view]?.();
    updateRefreshControls();
    U.bindCharts($(`#view-${state.view}`));
  };
  const updateLanguageControls = () => {
    for (const control of $$('[data-action="language"]')) {
      const text = [...control.childNodes].find(node => node.nodeType === Node.TEXT_NODE);
      if (text) text.data = I.getLocale().toUpperCase() + " ";
    }
  };
  const chooseLocale = locale => {
    if (state.user && !state.tour) {
      if (!editPreferences(preferences => { preferences.locale = locale; })) return;
    } else {
      U.setLocale(locale);
      I.apply(document);
      updateLanguageControls();
      renderNav();
      renderAuthConfig();
      if (state.data.catalog) renderPublicCatalog(state.data.catalog);
      renderCurrent();
    }
    $("#workspace-dialog").close();
  };
  const renderPublicCatalog = catalog => {
    const target = $("#public-strategy-list");
    if (!catalog?.presets) {
      target.innerHTML = ("<p class=\"muted\">" + H("Каталог временно не загрузился. Повторите открытие страницы.") + "</p>");
      return;
    }
    for (const count of $$("[data-catalog-count]")) count.textContent = String(catalog.presets.length);
    target.innerHTML = catalog.presets.map(raw => {
      const item = I.preset(raw);
      const [symbol] = strategyIcons[item.id] || ["strategies"];
      return `<button class="public-strategy-card" data-public-strategy="${esc(item.id)}">${icon(symbol)}<strong>${esc(item.title)}</strong><small>${esc(strategyTaglines()[item.id] || item.description)}</small></button>`;
    }).join("");
  };
  const renderAuthConfig = () => {
    const config = state.config;
    const vkEnabled = Boolean(config?.vkid_enabled);
    const tidEnabled = Boolean(config?.tid_enabled);
    $("#tid-login").disabled = !tidEnabled;
    $("#vkid-login").disabled = !vkEnabled;
    $("#tid-state").textContent = tidEnabled ? "" : T("T-ID ещё не подключён на сервере");
    $("#vkid-state").textContent = vkEnabled ? "" : T("VK ID временно недоступен");
    const registration = !config ? T("Не удалось проверить доступность регистрации.") : renderAuthConfigValue(config);
    $("#registration-state").textContent = registration;
    $("#public-access-status").textContent = registration;
  };
  function openAuth(mode = "login", linkCurrent = false) {
    closeDrawer(false);
    state.authMode = mode;
    state.authLink = Boolean(linkCurrent && state.user);
    for (const dialog of $$("dialog[open]")) if (dialog.id !== "auth-dialog" && dialog.id !== "session-dialog") dialog.close();
    $("#auth-title").innerHTML = state.authLink ? (H("Подключите ещё один") + "<br>" + H("способ входа")) : renderOpenAuthValue(mode);
    $("#auth-explanation").textContent = state.authLink ? T("Подтвердите вторую учётную запись у провайдера. Она будет связана с текущим профилем OMNICIO.") : renderOpenAuthValue2(mode);
    for (const tab of $$("[data-auth-mode]")) tab.setAttribute("aria-selected", String(tab.dataset.authMode === mode));
    renderAuthConfig();
    showMessage($("#auth-message"), "");
    if (state.route.overlay !== "auth") updateViewRoute({overlay: "auth"});
    if (!$("#auth-dialog").open) $("#auth-dialog").showModal();
  }
  const startAuth = async (form, provider) => {
    if (!["tid", "vkid"].includes(provider) || !form.reportValidity()) return;
    const payload = Object.fromEntries(["accept_privacy", "accept_personal_data", "accept_terms", "confirm_age_18"].map(key => [key, form.elements[key].checked]));
    if (!Object.values(payload).every(Boolean)) return;
    const destination = state.authReturn || (state.mode === "public" ? {view: "home"} : {...state.route, overlay: ""});
    payload.return_to = "/" + U.routeHash({...destination, mode: "account"});
    if (state.authLink) payload.link_current_account = true;
    $("#tid-login").disabled = true;
    $("#vkid-login").disabled = true;
    showMessage($("#auth-message"), T("Переходим к подтверждению личности…"));
    try {
      const result = await api(`/api/auth/${provider}/start`, {
        method: "POST",
        body: payload
      });
      const url = new URL(result.authorize_url);
      const host = provider === "tid" ? "id.tbank.ru" : "id.vk.ru";
      if (url.protocol !== "https:" || url.hostname !== host || url.port && url.port !== "443" || url.username || url.password) throw new Error("invalid_authorization_url");
      location.assign(url.href);
    } catch (error) {
      if (!isCancelled(error)) {
        renderAuthConfig();
        showMessage($("#auth-message"), error?.message === "invalid_authorization_url" ? T("Адрес авторизации не прошёл проверку. Вход остановлен.") : humanError(error), true);
      }
    }
  };
  const verifySession = async () => {
    if (!state.user || state.locked || state.verifying || document.visibilityState !== "visible") return;
    state.verifying = true;
    try {
      const user = await api("/api/me");
      state.user.can_view_operational_metrics = user.can_view_operational_metrics === true;
      if (!state.user.can_view_operational_metrics) {
        delete state.data.operationalMetrics;
        delete state.errors.operationalMetrics;
        $("#operations-settings")?.remove();
      }
    } catch (error) {
      if (!isCancelled(error) && error?.status !== 401) {
        const banner = $("#connection-banner");
        banner.hidden = false;
        banner.textContent = T("Не удалось повторно проверить сессию. Изменения будут подтверждаться сервером.");
      }
    } finally {
      state.verifying = false;
    }
  };
  const callbackMessage = () => {
    const params = new URLSearchParams(location.search);
    const code = params.get("auth_error");
    if (params.has("auth") || code) history.replaceState(history.state, "", `${location.pathname}${location.hash}`);
    if (!code) return;
    const labels = {
      registration: T("Регистрация новых аккаунтов сейчас закрыта."),
      capacity: T("Свободных мест для новых аккаунтов пока нет."),
      provider: T("Провайдер входа временно недоступен. Повторите позже."),
      account: T("Этот аккаунт сейчас недоступен."),
      identity_conflict: T("Этот способ входа уже связан с другим аккаунтом."),
      link_conflict: T("Эта учётная запись уже привязана к другому профилю.")
    };
    openAuth();
    showMessage($("#auth-message"), labels[code] || T("Авторизация не завершена. Попробуйте ещё раз."), true);
  };
  const bootstrap = async () => {
    const generation = state.generation;
    const sequence = ++state.session.sequence;
    state.session.status = "checking";
    state.session.error = null;
    if (state.mode === "account" && !state.user) sessionSurface();
    const current = () => generation === state.generation && sequence === state.session.sequence;
    const config = api("/api/auth/config", {bootstrap: true}).then(value => {
      if (!current()) return;
      state.config = value;
      renderAuthConfig();
    }).catch(error => { if (current() && !isCancelled(error)) renderAuthConfig(); });
    const catalog = loadResource("catalog", "/api/strategy/catalog", {bootstrap: true}).then(value => {
      if (current()) renderPublicCatalog(value);
    });
    const session = api("/api/me", {bootstrap: true}).then(user => {
      if (!current()) return;
      if (!/^\d{9}$/.test(user.public_id)) throw new Error("invalid_session_response");
      state.user = user;
      restoreUpdateDrafts(user.public_id);
      state.locked = false;
      state.session.status = "authenticated";
      const route = parseRoute();
      if (state.mode === "auto" || route.mode === "auto") navigate(route.view, {...route, mode: "account"}, {replace: true});
      else if (state.mode === "account") navigate(route.view, route, {replace: true});
      scheduleEventSummary(100);
      void resumeWorkspaceRefresh();
    }).catch(error => {
      if (!current() || isCancelled(error)) return;
      state.session.status = error?.status === 401 ? "guest" : "error";
      state.session.error = error;
      const route = parseRoute();
      if (state.mode === "auto") {
        if (error?.status === 401) navigate("public/welcome", {}, {replace: true});
        else { state.mode = "account"; sessionSurface(); }
      } else if (state.mode === "account") sessionSurface();
      if (error?.status !== 401) $("#public-access-status").textContent = T("session.retry_title");
      // A failed verification does not turn a chosen demo/public screen into a login screen.
      if (route.mode === "account" && error?.status === 401) state.user = null;
    });
    state.session.promise = session;
    await Promise.allSettled([config, catalog, session]);
    if (!current()) return;
    callbackMessage();
  };
  const resetBrokerPreview = () => {
    state.brokerPreview = null;
    state.brokerSequence = (state.brokerSequence || 0) + 1;
    const container = $("#broker-accounts");
    if (container) container.replaceChildren();
  };
  const previewBroker = async form => {
    if (!requireUser() || !form.reportValidity()) return;
    resetBrokerPreview();
    const credential = form.elements.credential.value.trim();
    const environment = form.elements.environment.value;
    const sequence = state.brokerSequence;
    const generation = state.generation;
    const submit = form.querySelector("[type=submit]");
    submit.disabled = true;
    showMessage($("#broker-message"), T("Проверяем токен и список счетов…"));
    try {
      const result = await api("/api/broker/tbank/accounts", {
        method: "POST",
        timeout: 45000,
        body: {
          credential,
          environment,
          accept_personal_terms: true
        }
      });
      if (generation !== state.generation || sequence !== state.brokerSequence || !form.isConnected || credential !== form.elements.credential.value.trim() || environment !== form.elements.environment.value) return;
      const accounts = Array.isArray(result.accounts) ? result.accounts : [];
      state.brokerPreview = {
        credential,
        environment,
        accounts
      };
      $("#broker-accounts").innerHTML = accounts.length ? `${select("account_id", T("Ваш счёт"), [["", T("Выберите счёт")], ...accounts.map(item => [item.id, renderPreviewBrokerFragment(item)])], "")}<div class="form-actions">${button(T("Подключить выбранный счёт"), "broker-connect", {
        primary: true
      })}</div>` : ("<p class=\"notice\">" + H("У токена нет доступных счетов.") + "</p>");
      showMessage($("#broker-message"), accounts.length ? T("Токен проверен. Выберите счёт для подключения.") : T("Доступные счета не получены."), !accounts.length);
    } catch (error) {
      if (!isCancelled(error)) showMessage($("#broker-message"), humanError(error), true);
    } finally {
      if (form.isConnected && generation === state.generation) submit.disabled = false;
    }
  };
  const brokerConnectionInput = () => {
    const form = $("#broker-form");
    const preview = state.brokerPreview;
    if (!form || !preview || preview.credential !== form.elements.credential.value.trim() || preview.environment !== form.elements.environment.value || !form.elements.accept_personal_terms.checked) {
      resetBrokerPreview();
      showMessage($("#broker-message"), T("Данные изменились. Проверьте токен повторно."), true);
      return null;
    }
    const accountId = form.elements.account_id?.value;
    if (!preview.accounts.some(item => item.id === accountId)) {
      showMessage($("#broker-message"), T("Выберите один из доступных счетов."), true);
      return null;
    }
    return {
      form,
      preview,
      accountId
    };
  };
  const writeBrokerConnection = async ({
    preview,
    accountId
  }) => {
    try {
      return await api("/api/broker/tbank", {
        method: "PUT",
        timeout: 45000,
        body: {
          credential: preview.credential,
          environment: preview.environment,
          account_id: accountId,
          accept_personal_terms: true
        }
      });
    } catch (error) {
      if (isCancelled(error) || error.definite || error.status && error.status < 500) throw error;
      const current = await api("/api/broker/tbank");
      if (current.connected && current.account_id === accountId && current.environment === preview.environment) return current;
      throw error;
    }
  };
  const adoptBrokerConnection = async ({
    form,
    generation
  }, connected) => {
    if (generation !== state.generation) return;
    form.elements.credential.value = "";
    resetBrokerPreview();
    state.data.connection = connected;
    delete state.data.workspace;
    delete state.data.visualization;
    delete state.data.analysis;
    toast(T("Счёт подключён. Загружаем реальные данные."));
    renderSettings();
    await requestWorkspaceRefresh();
    if (generation !== state.generation) return;
    await loadResource("workspace", workspacePath(), {
      force: true
    });
    if (generation === state.generation && state.view === "settings") renderCurrent();
  };
  const connectBroker = async control => {
    if (!requireUser()) return;
    const input = brokerConnectionInput();
    if (!input) return;
    const context = {
      ...input,
      generation: state.generation
    };
    control.disabled = true;
    try {
      await adoptBrokerConnection(context, await writeBrokerConnection(context));
    } catch (error) {
      if (!isCancelled(error) && context.generation === state.generation) {
        showMessage($("#broker-message"), humanError(error), true);
        control.disabled = false;
      }
    }
  };
  const clearBrokerState = async () => {
    const user = state.user;
    const config = state.config;
    clearPrivateState();
    state.user = user;
    state.config = config;
    state.locked = false;
    state.tour = false;
    showApp();
  };
  const hasPending = () => researchPending() || state.assistantBusy || state.billingBusy || state.executionBusy || state.recovery.busy || state.prefs.dirty || state.prefs.busy || state.strategy.dirty || state.strategy.busy || hasFormDrafts();
  const logout = async () => {
    if (!state.user) {
      state.tour = false;
      clearPrivateState();
      $("#app-shell").hidden = true;
      $("#public-site").hidden = false;
      navigate("public/welcome", {}, {replace: true});
      return;
    }
    if (hasPending() && !window.confirm(T("Есть несохранённые изменения. Выйти и закрыть их?"))) return;
    try {
      await api("/api/auth/logout", {
        method: "POST"
      });
      clearPrivateState();
      state.session.status = "guest";
      try { localStorage.removeItem("omnicio-last-route"); } catch { /* Optional navigation state. */ }
      state.tour = false;
      state.locked = false;
      $("#app-shell").hidden = true;
      $("#public-site").hidden = false;
      navigate("public/welcome", {}, {replace: true});
      sessionChannel?.postMessage({
        type: "session-cleared"
      });
      await bootstrap();
    } catch (error) {
      if (!isCancelled(error)) toast(humanError(error), true);
    }
  };
  const showAccountDeletion = () => {
    if (!requireUser()) return;
    openDialog(T("Удаление аккаунта"), `<p class="help-copy">${H("Для удаления введите ID текущего профиля:")} <strong>${esc(state.user.public_id)}</strong>.</p><form id="delete-account-form">${field({
      name: "confirm_public_id",
      label: T("ID вашего профиля"),
      required: true
    })}<label class="check-field section-gap"><input type="checkbox" name="confirm_irreversible" required><span>${H("Подтверждаю удаление профиля и понимаю, что восстановление через интерфейс недоступно.")}</span></label><div class="form-actions"><button class="button danger" type="submit">${H("Удалить аккаунт")}</button><button class="button secondary" type="button" data-close-dialog>${H("Отмена")}</button></div><output id="delete-account-message" class="form-message"></output></form>`);
  };
  const toggleWatch = control => {
    const uid = control.dataset.watch;
    if (!uid) return;
    const updated = editPreferences(document => {
      const existing = document.watchlist.findIndex(item => item.instrument_uid === uid);
      if (existing >= 0) document.watchlist.splice(existing, 1);else document.watchlist.push({
        instrument_uid: uid,
        ticker: control.dataset.watchTicker || "",
        name: control.dataset.watchName || uid
      });
    });
    if (updated) {
      for (const element of $$("[data-watch]")) if (element.dataset.watch === uid) {
        element.setAttribute("aria-pressed", String(isWatched(uid)));
        element.setAttribute("aria-label", isWatched(uid) ? T("Удалить из избранного") : T("Добавить в избранное"));
      }
      if (state.view === "market") {
        renderMarket();
        U.bindCharts($("#view-market"));
      }
    }
  };
  const updateStrategyField = input => {
    const slot = state.strategy;
    if (!slot.draft || slot.error?.status === 409) return;
    const path = input.name.split(".").slice(1);
    if (path.length < 2 || path.length > 3 || !["profile", "policy", "rules"].includes(path[0])) return;
    let parent = slot.draft;
    for (const key of path.slice(0, -1)) {
      if (!Object.hasOwn(parent, key) || !parent[key] || typeof parent[key] !== "object") return;
      parent = parent[key];
    }
    const key = path.at(-1);
    if (!Object.hasOwn(parent, key)) return;
    const value = input.type === "checkbox" ? input.checked : renderUpdateStrategyFieldValue(input);
    if (parent[key] === value) return;
    parent[key] = value;
    documentChanged();
  };
  const stepField = control => {
    const input = document.getElementsByName(control.dataset.stepField)[0];
    if (!input || input.disabled) return;
    const value = input.value;
    if (value === "") {
      input.focus();
      toast(T("Сначала укажите исходное значение. Неизвестная сумма не заменяется нулём."));
      return;
    }
    if (!/^\d+(\.\d{1,8})?$/.test(value)) {
      input.focus();
      return;
    }
    const [whole, fraction = ""] = value.split(".");
    const precise = BigInt(whole) * 100000000n + BigInt(fraction.padEnd(8, "0"));
    const amount = input.name.endsWith("_rub") ? 1000n : renderStepFieldValue(input);
    const adjusted = precise + BigInt(control.dataset.stepDirection) * amount * 100000000n;
    const maximum = BigInt(Math.trunc(Number(input.max || "1000000000000"))) * 100000000n;
    const minimum = BigInt(input.min || "0") * 100000000n;
    const bounded = adjusted < minimum ? minimum : renderStepFieldValue2(adjusted, maximum);
    const decimal = String(bounded % 100000000n).padStart(8, "0").replace(/0{1,8}$/, "");
    input.value = `${bounded / 100000000n}${decimal ? renderStepFieldFragment(decimal) : ""}`;
    input.dispatchEvent(new Event("input", {
      bubbles: true
    }));
  };
  const currentResearchRequest = request => request === state.researchRequest && request.generation === state.generation;
  const repaintResearch = () => {
    updateStrategySaveControls(state.strategy);
    const target = $("#strategy-research");
    if (target) { target.innerHTML = renderResearch(); U.bindCharts(target); }
  };
  const newResearchRequest = (id, body = null) => ({
    id, body, generation: state.generation, revision: state.strategy.revision,
    version: state.strategy.server?.version, status: "checking", busy: false,
    displaySequence: state.researchDisplaySequence || 0,
    pollUntil: Date.now() + 120000, timer: null, error: null, resultPending: false
  });
  const restoreResearchRequest = () => {
    const recent = state.data.researchArchive?.recent_request;
    if (!state.researchRequest && recent && state.strategy.server) {
      state.researchRequest = newResearchRequest(recent.id);
      void checkResearchRequest();
    } else if (state.researchRequest) scheduleResearchCheck(state.researchRequest);
  };
  const scheduleResearchCheck = request => {
    clearTimeout(request.timer);
    if (!currentResearchRequest(request) || request.busy || !["running", "uncertain"].includes(request.status)) return;
    if (Date.now() >= request.pollUntil || state.view !== "strategies" || document.visibilityState !== "visible") return;
    request.timer = setTimeout(() => { if (currentResearchRequest(request)) void checkResearchRequest(); }, 2500);
  };
  const acceptResearchResult = (request, result, archive) => {
    request.status = "completed";
    request.run_id = archive.id;
    request.resultPending = false;
    const slot = state.strategy;
    request.archivedOnly = slot.revision !== request.revision || slot.server?.version !== request.version ||
      result.strategy_version !== request.version || slot.dirty || request.displaySequence !== (state.researchDisplaySequence || 0);
    if (!request.archivedOnly) slot.research = {...result, archive: {...archive, strategy_version: result.strategy_version}};
  };
  const readCompletedResearch = async request => {
    request.resultPending = true;
    const saved = await api(`/api/research/runs/${safeSegment(request.run_id)}`);
    if (!currentResearchRequest(request)) return;
    if (saved.id !== request.run_id || saved.result?.request_id !== request.id) throw new Error("invalid_server_response");
    acceptResearchResult(request, {...saved.result, strategy_version: saved.strategy_version},
      {id: saved.id, created_at: saved.created_at});
  };
  const adoptResearchResponse = async (request, result) => {
    if (["draft_required", "snapshot_required"].includes(result.status)) {
      request.status = "failed";
      request.error = new Error(`research_${result.status}`);
      return;
    }
    if (result.archive) {
      if (result.request_id !== request.id) throw new Error("invalid_server_response");
      acceptResearchResult(request, result, result.archive);
      return;
    }
    if (result.id !== request.id || !["running", "completed", "failed", "expired", "deleted"].includes(result.status)) throw new Error("invalid_server_response");
    Object.assign(request, {status: result.status, run_id: result.run_id, created_at: result.created_at, expires_at: result.expires_at});
    if (result.status === "completed") await readCompletedResearch(request);
    else if (result.error_code) request.error = new Error(result.error_code);
  };
  const researchReadError = (request, error) => {
    request.error = error;
    if (request.resultPending) {
      if (error.status === 404) { request.status = "deleted"; request.resultPending = false; request.run_id = null; }
      return;
    }
    if (error.code === "research_request_not_found" && !request.body) {
      request.status = "missing";
      request.error = null;
      return;
    }
    request.status = error.code === "research_request_not_found" ? "not_found" : "uncertain";
  };
  const checkResearchRequest = async () => {
    const request = state.researchRequest;
    if (!request || request.busy || !requireUser()) return;
    request.busy = true;
    request.error = null;
    clearTimeout(request.timer);
    repaintResearch();
    try {
      const result = await api(`/api/research/requests/${safeSegment(request.id)}`);
      if (!currentResearchRequest(request)) return;
      await adoptResearchResponse(request, result);
    } catch (error) {
      if (currentResearchRequest(request) && !isCancelled(error)) researchReadError(request, error);
    } finally {
      if (currentResearchRequest(request)) {
        request.busy = false;
        repaintResearch();
        scheduleResearchCheck(request);
      }
    }
  };
  const submitResearchRequest = async request => {
    if (!currentResearchRequest(request) || request.busy || !request.body) return;
    request.status = "submitting";
    request.busy = true;
    request.error = null;
    clearTimeout(request.timer);
    repaintResearch();
    try {
      const result = await api("/api/profile/strategy/research", {method: "POST", timeout: 305000, body: request.body});
      if (!currentResearchRequest(request)) return;
      await adoptResearchResponse(request, result);
      await loadResource("researchArchive", "/api/research/runs?limit=50", {force: true});
    } catch (error) {
      if (!currentResearchRequest(request) || isCancelled(error)) return;
      request.error = error;
      request.status = error.status === 409 ? "conflict" : "uncertain";
      if (error.definite || error.status >= 400 && error.status < 500 && error.status !== 409) request.status = "failed";
    } finally {
      if (currentResearchRequest(request)) {
        request.busy = false;
        request.pollUntil = Date.now() + 120000;
        repaintResearch();
        if (request.status === "uncertain") await checkResearchRequest();
        else scheduleResearchCheck(request);
      }
    }
  };
  const retryResearchRequest = async () => {
    const request = state.researchRequest;
    if (request?.status !== "not_found" || !request.body || !requireUser()) return;
    // User-selected replay keeps the exact UUID and immutable parameters. The server
    // checks the complete current strategy/account/evidence fingerprint again.
    await submitResearchRequest(request);
  };
  const runResearch = async form => {
    if (!requireUser() || researchUnavailable() || !form.reportValidity()) return;
    const slot = state.strategy;
    if (strategySaveUnavailable(slot)) {
      showMessage($("#research-message"), T("Дождитесь сохранения выбранной стратегии."), true);
      return;
    }
    const values = formValues(form);
    if (values.from_at >= values.to_at) {
      showMessage($("#research-message"), T("Конец периода должен быть позже начала."), true);
      return;
    }
    state.researchDraft = values;
    const id = crypto.randomUUID();
    const body = Object.freeze({
      request_id: id, expected_public_id: state.user.public_id, expected_version: slot.server.version,
      from_at: `${values.from_at}T00:00:00Z`, to_at: `${values.to_at}T23:59:59Z`,
      initial_capital_rub: values.initial_capital_rub,
      commission_bps: values.commission_bps, slippage_bps: values.slippage_bps
    });
    clearTimeout(state.researchRequest?.timer);
    state.researchRequest = newResearchRequest(id, body);
    slot.research = null;
    showMessage($("#research-message"), "");
    await submitResearchRequest(state.researchRequest);
  };
  const actions = {
    login: () => openAuth(),
    register: () => openAuth("register"),
    tour: () => navigate("home", {mode: "demo"}),
    "session-retry": bootstrap,
    "public-home": () => navigate("public/welcome"),
    "route-back": routeBack,
    "pwa-update": () => applyApplicationUpdate(false),
    "pwa-update-discard": () => applyApplicationUpdate(true),
    "route-retry": () => openRouteScreen(activeRoute()),
    "support": () => navigate(state.mode === "public" ? "public/support" : "settings", {screen: state.mode === "public" ? "" : "support"}),
    "leave-tour": () => navigate("public/welcome"),
    connect: () => {
      if (!state.user || state.tour) { state.authReturn = {view: "settings", screen: "broker"}; openAuth(); return; }
      navigate("settings", {screen: "broker"});
    },
    refresh: async () => {
      if (hasPending()) {
        toast(T("Сначала завершите сохранение или загрузите серверную версию через сообщение об ошибке."), true);
        return;
      }
      if (["home", "portfolio", "analytics", "settings"].includes(state.view) && (state.data.connection?.connected || state.data.workspace?.connection?.connected)) await requestWorkspaceRefresh();else await loadForView(state.view, state.route, true);
    },
    "workspace-refresh": requestWorkspaceRefresh,
    "resource-retry": retryResource,
    "execution-plan": openExecutionPlanner,
    "execution-confirm": confirmExecutionPlan,
    "execution-history": openExecutionHistory,
    "recovery-dispatch": dispatchExecutionLeg,
    "recovery-open": openRecovery,
    "recovery-reload": reloadRecovery,
    "recovery-detail-reload": reloadRecoveryDetails,
    "recovery-reconcile": () => mutateRecovery("reconcile"),
    "recovery-cancel": askRecoveryCancellation,
    "recovery-cancel-confirm": () => mutateRecovery("cancel"),
    "recovery-cancel-dismiss": () => {
      $("#recovery-confirmation").replaceChildren();
    },
    "mandate-revoke": askMandateRevoke,
    "mandate-revoke-confirm": revokeMandate,
    language: () => {
      const russian = button(T("Русский"), "language-ru", {extra: `aria-pressed="${I.getLocale() === "ru"}"`});
      const english = button("English", "language-en", {extra: `aria-pressed="${I.getLocale() === "en"}"`});
      openDialog(T("settings.language"), `<div class="form-actions">${russian}${english}</div><p class="fine-print">${H("settings.language_help")}</p>`);
    },
    "language-ru": () => chooseLocale("ru"),
    "language-en": () => chooseLocale("en"),
    premium: openBilling,
    legal: () => openDialog(T("Документы"), ("<ul class=\"source-list\"><li><a href=\"/legal/terms.html\">" + H("Условия использования") + "</a></li><li><a href=\"/legal/privacy.html\">" + H("Политика конфиденциальности") + "</a></li><li><a href=\"/legal/consent.html\">" + H("Обработка персональных данных") + "</a></li></ul>")),
    "goal-create": () => openGoal(),
    "goal-reconcile": reconcileGoals,
    "events-read-all": readAllEvents,
    "events-more": () => loadEventPage(false),
    "news-more": () => loadEventPage(true),
    "ledger-more": loadLedgerPage,
    "search-more-events": () => loadSearchPage("events"),
    "search-more-news": () => loadSearchPage("news"),
    "asset-news-more": loadAssetNewsPage,
    "notifications-reload": reloadNotifications,
    "notification-push": enablePush,
    "notification-revoke": revokeNotification,
    "event-destination": () => {
      const destination = state.eventDetail?.destination;
      if (!destination || !views.has(destination.view)) return;
      $("#workspace-dialog").close();
      navigate(destination.view, {uid: destination.uid || "", goal_id: destination.goal_id || ""});
    },
    "strategy-custom": () => setStrategyPane("custom"),
    "strategy-catalog": () => setStrategyPane("catalog"),
    "strategy-apply-custom": customizeStrategy,
    "assess-strategy": assessStrategy,
    "strategy-reload": () => reloadVersioned("strategy"),
    "strategy-discard": () => {
      $("#workspace-dialog").close();
      return reloadVersioned("strategy", true);
    },
    "strategy-retry": () => retryVersioned("strategy"),
    "prefs-reload": () => reloadVersioned("prefs"),
    "prefs-discard": () => {
      $("#workspace-dialog").close();
      return reloadVersioned("prefs", true);
    },
    "prefs-retry": () => retryVersioned("prefs"),
    "broker-connect": connectBroker,
    "disconnect-start": () => {
      if (!requireUser()) return;
      if (disconnectBlocked()) {
        toast(T("Сначала проверьте ранее начатые исполнения в настройках."), true);
        return;
      }
      if (hasPending()) {
        toast(T("Перед отключением завершите сохранение настроек."), true);
        return;
      }
      openDialog(T("Отключить T-Invest?"), `<p class="help-copy">${H("Токен подключения будет удалён. Новые данные счёта перестанут поступать. Для восстановления потребуется повторное подключение.")}</p><div class="form-actions">${button(T("Отключить источник"), "disconnect-confirm", {
        primary: true
      })}<button class="button secondary" data-close-dialog>${H("Отмена")}</button></div><output id="disconnect-message" class="form-message"></output>`);
    },
    "disconnect-confirm": async control => {
      if (disconnectBlocked()) return;
      control.disabled = true;
      try {
        await api("/api/broker/tbank", {
          method: "DELETE"
        });
        await clearBrokerState();
        toast(T("Источник отключён."));
      } catch (error) {
        if (!isCancelled(error)) {
          showMessage($("#disconnect-message"), humanError(error), true);
          control.disabled = false;
        }
      }
    },
    "asset-refresh": () => state.asset && loadAsset(state.asset.uid, true),
    "asset-back": routeBack,
    "copy-profile": async () => {
      if (!state.user) return;
      try {
        await navigator.clipboard.writeText(state.user.public_id);
        toast(T("ID профиля скопирован."));
      } catch {
        openDialog(T("ID профиля"), `<p class="help-copy">${esc(state.user.public_id)}</p>`);
      }
    },
    "delete-account": showAccountDeletion,
    logout,
    "chat-clear": () => deleteAssistantConversation(false),
    "assistant-delete-confirm": () => deleteAssistantConversation(true),
    "assistant-connect": openAssistantConnection,
    "assistant-cancel": () => readAssistantRequest(true),
    "assistant-request-read": () => readAssistantRequest(false),
    "assistant-health": () => assistantConnectionOperation("check"),
    "assistant-disconnect": () => assistantConnectionOperation("disconnect"),
    "assistant-new": newAssistantConversation,
    "research-check": checkResearchRequest,
    "research-retry": retryResearchRequest,
    "research-archive-more": () => loadResearchArchivePage(true),
    "research-archive-reload": () => loadResearchArchivePage(false),
    "assistant-history-reload": () => state.assistantConversation && loadAssistantConversation(state.assistantConversation.id),
    "assistant-history-more": () => state.assistantConversation && loadAssistantConversation(state.assistantConversation.id, true),
    "link-identity": () => openAuth("login", true)
  };
  const clickHandlers = [{
    matches: ({control}) => control.dataset.assistantConversation,
    run: ({control}) => { navigate("assistant", {screen: "conversation", conversation: control.dataset.assistantConversation}); }
  }, {
    matches: ({control}) => control.dataset.billingId,
    run: ({control}) => billingOperation(control)
  }, {
    matches: ({control}) => control.dataset.researchAction,
    run: ({control}) => control.dataset.researchAction === "archive" ? openResearchArchive() : openResearchEvidence()
  }, {
    matches: ({control}) => control.dataset.researchRun,
    run: ({control}) => researchArchiveAction(control)
  }, {
    matches: ({control}) => control.dataset.sessionRevoke,
    run: ({control}) => revokeSession(control.dataset.sessionRevoke)
  }, {
    matches: ({control}) => control.dataset.identityUnlink,
    run: ({control}) => unlinkIdentity(control.dataset.identityUnlink)
  }, {
    matches: ({control}) => control.dataset.goalPlan,
    run: ({control}) => openGoalPlan(control.dataset.goalPlan)
  }, {
    matches: ({
      control
    }) => control.dataset.closeDialog !== undefined,
    run: handleClickCloseDialog
  }, {
    matches: ({
      control
    }) => control.dataset.help,
    run: handleClickHelp
  }, {
    matches: ({
      control
    }) => control.dataset.themeChoice,
    run: handleClickTheme
  }, {
    matches: ({
      control
    }) => control.dataset.publicOpen,
    run: handleClickPublicView
  }, {
    matches: ({
      control
    }) => control.dataset.route,
    run: handleClickRoute
  }, {
    matches: ({
      control
    }) => control.dataset.authMode,
    run: handleClickAuthMode
  }, {
    matches: ({
      control
    }) => control.dataset.asset,
    run: handleClickAsset
  }, {
    matches: ({
      control
    }) => control.dataset.assetTab,
    run: handleClickAssetTab
  }, {
    matches: ({
      control
    }) => control.dataset.watch,
    run: handleClickWatchlist
  }, {
    matches: ({
      control
    }) => control.dataset.assetFilter,
    run: handleClickAssetFilter
  }, {
    matches: ({
      control
    }) => control.dataset.sort,
    run: handleClickSort
  }, {
    matches: ({
      control
    }) => control.dataset.period,
    run: handleClickPeriod
  }, {
    matches: ({
      control
    }) => control.dataset.eventFilter,
    run: handleClickEventFilter
  }, {
    matches: ({
      control
    }) => control.dataset.eventOpen,
    run: handleClickEventOpen
  }, {
    matches: ({control}) => control.dataset.newsOpen,
    run: async ({event, control}) => { event.preventDefault(); await openNews(control.dataset.newsOpen, "broker"); }
  }, {
    matches: ({
      control
    }) => control.dataset.eventRead,
    run: handleClickEventRead
  }, {
    matches: ({
      control
    }) => control.dataset.goalEdit,
    run: handleClickGoalEdit
  }, {
    matches: ({
      control
    }) => control.dataset.goalDelete,
    run: handleClickGoalDelete
  }, {
    matches: ({
      control
    }) => control.dataset.goalDeleteConfirm,
    run: handleClickGoalDeleteConfirm
  }, {
    matches: ({
      control
    }) => control.dataset.selectStrategy,
    run: handleClickStrategy
  }, {
    matches: ({
      control
    }) => control.dataset.publicStrategy,
    run: handleClickPublicStrategy
  }, {
    matches: ({
      control
    }) => control.dataset.stepField,
    run: handleClickStep
  }, {
    matches: ({
      control
    }) => control.dataset.chatPrompt,
    run: handleClickChatPrompt
  }, {
    matches: ({
      control
    }) => control.dataset.action && actions[control.dataset.action],
    run: handleClickAction
  }];
  function openAssistantMemoryEditor(id) {
    const item = state.data.assistantMemory?.items?.find(row => row.id === id);
    if (!item) return;
    captureScreenDrafts();
    $("#assistant-memory-editor").innerHTML = assistantMemoryForm(item);
    restoreScreenDrafts($("#assistant-memory-editor"));
  }
  document.addEventListener("click", async event => {
    if (event.target.closest(".skip-link")) { event.preventDefault(); $(state.mode === "public" ? "#public-content" : "#main-content").focus({preventScroll: false}); return; }
    const control = event.target.closest("button,a[data-route],a[data-public-open],a[data-public-page]");
    if (control?.dataset.publicPage) { event.preventDefault(); $(".public-nav").classList.remove("open"); navigate(`public/${control.dataset.publicPage}`); return; }
    if (!control || control.disabled) return;
    try {
      if (control.dataset.publicNews) { navigate("events", {screen: "news", news: control.dataset.publicNews, news_source: "public"}); return; }
      if (control.dataset.memoryEdit) { openAssistantMemoryEditor(control.dataset.memoryEdit); return; }
      if (control.dataset.memoryDelete) { openDialog(T("assistant.memory_delete"), `<p>${H("assistant.memory_delete_help")}</p><button class="button danger" data-memory-delete-confirm="${esc(control.dataset.memoryDelete)}">${H("Удалить")}</button>`); return; }
      if (control.dataset.memoryDeleteConfirm) { await deleteAssistantMemory(control.dataset.memoryDeleteConfirm); return; }
      if (control.dataset.assistantSource) { await readAssistantSource(control.dataset.assistantSource, control.dataset.assistantSourceRequest || ""); return; }

      const context = {
        control,
        event
      };
      const handler = clickHandlers.find(candidate => candidate.matches(context));
      if (handler) {
        await Promise.resolve(handler.run(context));
      }
    } catch (error) {
      if (!isCancelled(error)) toast(humanError(error), true);
    }
  });
  document.addEventListener("input", event => {
    const input = event.target;
    if (input.closest("#assistant-form")) state.assistantDraft = assistantDraftFromForm(input.form);
    if (input.closest("#research-form")) state.researchDraft = formValues(input.form);
    if (captureFormDraft(input)) return;
    if (input.dataset.allocation) {
      updateAllocation(input.dataset.allocation, Number(input.value));
      return;
    }
    if (input.name?.startsWith("strategy.") && input.type !== "checkbox") {
      updateStrategyField(input);
      return;
    }
    if (input.closest("#broker-form") && ["credential", "environment"].includes(input.name)) resetBrokerPreview();
  });
  const changeHandlers = [{
    matches: ({
      input
    }) => input.name?.startsWith("strategy."),
    run: handleChangeStrategyField
  }, {
    matches: ({
      input
    }) => input.dataset.allocationLock || input.dataset.allocationExclude,
    run: handleChangeAllocationFlag
  }, {
    matches: ({
      input
    }) => input.closest("#goal-form") && ["kind", "progress_source"].includes(input.name),
    run: handleChangeGoalSource
  }, {
    matches: ({
      input
    }) => input.closest("#broker-form") && input.name === "environment",
    run: handleChangeBrokerEnvironment
  }, {
    matches: ({
      input
    }) => ["cbr_currency", "cbr_period"].includes(input.name),
    run: handleChangeMarketReference
  }];
  document.addEventListener("change", async event => {
    const input = event.target;
    if (input.dataset.memorySelect) {
      state.assistantMemorySelected ||= new Set();
      if (input.checked) state.assistantMemorySelected.add(input.dataset.memorySelect);
      else state.assistantMemorySelected.delete(input.dataset.memorySelect);
      return;
    }
    if (input.closest("#goal-plan-form") && input.name === "target_in_today_money") updateGoalPlanFields();
    if (captureFormDraft(input)) return;
    const context = {
      input,
      event
    };
    const handler = changeHandlers.find(candidate => candidate.matches(context));
    if (handler) {
      await handler.run(context);
    }
  });
  const submitHandlers = [{matches: ({form}) => form.id === "assistant-memory-form", run: ({form}) => saveAssistantMemory(form)}, {matches: ({form}) => form.id === "assistant-sources-form", run: ({form}) => searchAssistantSources(form)}, {
    matches: ({form}) => form.id === "assistant-connection-form",
    run: ({form}) => saveAssistantConnection(form)
  }, {
    matches: ({form}) => form.id === "billing-checkout-form",
    run: ({form}) => checkoutBilling(form)
  }, {
    matches: ({form}) => form.id === "notification-email-form",
    run: async ({form}) => {
      if (!form.reportValidity()) return;
      const email = form.elements.email.value.trim();
      await deliveryAction(async () => {
        await api("/api/notifications/email/request", {method: "POST", body: {email}});
        delete state.deliveryDrafts[form.id];
      });
    }
  }, {
    matches: ({form}) => form.id.startsWith("notification-verify-"),
    run: async ({form}) => {
      if (!form.reportValidity()) return;
      const channel_id = form.dataset.channelId;
      const code = form.elements.code.value;
      await deliveryAction(async () => {
        await api("/api/notifications/email/verify", {method: "POST", body: {channel_id, code}});
        delete state.deliveryDrafts[form.id];
      });
    }
  }, {
    matches: ({form}) => form.id === "research-evidence-form",
    run: ({form}) => saveResearchEvidence(form)
  }, {
    matches: ({form}) => form.id === "execution-plan-form",
    run: ({form}) => calculateExecutionPlan(form)
  }, {
    matches: ({form}) => form.id === "goal-plan-form",
    run: ({form}) => saveGoalPlan(form)
  }, {
    matches: ({
      form
    }) => form.id === "auth-form",
    run: handleSubmitAuth
  }, {
    matches: ({
      form
    }) => form.id === "global-search-form",
    run: handleSubmitSearch
  }, {
    matches: ({
      form
    }) => form.id === "strategy-form",
    run: handleSubmitStrategy
  }, {
    matches: ({
      form
    }) => form.id === "goal-form",
    run: handleSubmitGoal
  }, {
    matches: ({
      form
    }) => form.id === "profile-form",
    run: handleSubmitProfile
  }, {
    matches: ({
      form
    }) => form.id === "preferences-form",
    run: handleSubmitPreferences
  }, {
    matches: ({
      form
    }) => form.id === "broker-form",
    run: handleSubmitBroker
  }, {
    matches: ({
      form
    }) => form.id === "assistant-form",
    run: handleSubmitAssistant
  }, {
    matches: ({
      form
    }) => form.id === "research-form",
    run: handleSubmitResearch
  }, {
    matches: ({
      form
    }) => form.id === "delete-account-form",
    run: handleSubmitAccountDeletion
  }];
  document.addEventListener("submit", async event => {
    const form = event.target;
    const context = {form, event};
    const handler = submitHandlers.find(candidate => candidate.matches(context));
    if (!handler) return;
    event.preventDefault();
    try {
      await handler.run(context);
    } catch (error) {
      if (!isCancelled(error)) toast(humanError(error), true);
    }
  });
  document.addEventListener("change", event => {
    const form = event.target.closest("#assistant-form");
    if (form) { state.assistantDraft = assistantDraftFromForm(form); updateAssistantContext(); }
  });
  document.addEventListener("input", event => {
    const form = event.target.closest("form");
    if (form && (form.id === "notification-email-form" || form.id.startsWith("notification-verify-"))) state.deliveryDrafts[form.id] = formValues(form);
  });
  $("#app-menu-toggle").addEventListener("click", openDrawer);
  $("#drawer-close").addEventListener("click", () => closeDrawer());
  $("#drawer-backdrop").addEventListener("click", () => closeDrawer());
  $("#notifications-button").addEventListener("click", () => navigate("events"));
  $("#profile-button").addEventListener("click", () => {
    const menu = $("#profile-menu");
    menu.hidden = !menu.hidden;
    $("#profile-button").setAttribute("aria-expanded", String(!menu.hidden));
    if (!menu.hidden) $("[role=menuitem]", menu).focus();
  });
  $("#public-menu-toggle").addEventListener("click", () => {
    const nav = $(".public-nav");
    const expanded = nav.dataset.open !== "true";
    nav.dataset.open = String(expanded);
    $("#public-menu-toggle").setAttribute("aria-expanded", String(expanded));
  });
  $(".public-nav").addEventListener("click", event => {
    if (event.target.closest("a")) {
      delete $(".public-nav").dataset.open;
      $("#public-menu-toggle").setAttribute("aria-expanded", "false");
    }
  });
  $("#session-reload").addEventListener("click", async () => {
    $("#session-dialog").close();
    state.locked = false;
    await bootstrap();
  });
  $("#session-dialog").addEventListener("cancel", event => event.preventDefault());
  $("#auth-dialog").addEventListener("close", () => {
    $("#auth-form").reset();
  });
  document.addEventListener("pointerdown", event => {
    if (!event.target.closest("#profile-menu,#profile-button")) {
      $("#profile-menu").hidden = true;
      $("#profile-button").setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("keydown", event => {
    handleSearchShortcut({
      event
    });
    handleEscape({
      event
    });
    handleDrawerFocus({
      event
    });
    const tab = event.target.closest('[role="tab"]');
    handleTabFocus({
      tab,
      event
    });
    handleProfileFocus({
      event
    });
  });
  const historyNavigation = () => {
    const route = parseRoute();
    if (route.mode === "auto") {
      route.mode = state.mode;
      if (state.mode === "public") route.mode = state.user ? "account" : "demo";
    }
    if (U.routeHash(route) !== U.routeHash(activeRoute())) navigate(route.view, route, {fromHistory: true});
  };
  for (const dialog of $$("dialog")) {
    if (dialog.id === "session-dialog") continue;
    dialog.addEventListener("scroll", () => { if (dialog.open) saveNavigationPosition(); }, {passive: true});
    dialog.addEventListener("cancel", event => { event.preventDefault(); captureScreenDrafts(); routeBack(); });
    dialog.addEventListener("close", () => {
      if (dialog.dataset.routeClosing === "true") { delete dialog.dataset.routeClosing; return; }
      if (state.route.overlay || dialog.classList.contains("route-dialog")) {
        const parent = {...state.route, screen: dialog.classList.contains("route-dialog") ? "" : state.route.screen, overlay: ""};
        navigate(state.view, parent, {replace: true});
      }
    });
  }
  let scrollSaveScheduled = false;
  window.addEventListener("scroll", () => {
    if (scrollSaveScheduled) return;
    scrollSaveScheduled = true;
    requestAnimationFrame(() => { scrollSaveScheduled = false; saveNavigationPosition(); });
  }, {passive: true});
  window.addEventListener("popstate", historyNavigation);
  window.addEventListener("hashchange", historyNavigation);
  const refreshVisibleData = async () => {
    clearTimeout(freshnessTimer);
    if (freshnessBusy || document.visibilityState !== "visible" || !navigator.onLine || !state.user || state.locked || state.mode !== "account") return;
    freshnessBusy = true;
    try {
      await verifySession();
      const editing = document.activeElement?.matches("input, textarea, select") || $("dialog[open]") || hasPending();
      if (!state.locked && state.user && !editing) await loadForView(state.view, state.route, true);
    } finally {
      freshnessBusy = false;
      if (state.user && !state.locked) freshnessTimer = setTimeout(() => void refreshVisibleData(), 60000);
    }
  };
  window.addEventListener("focus", () => {
    void refreshVisibleData();
  });
  window.addEventListener("pageshow", event => {
    if (event.persisted) {
      void refreshVisibleData();
      void resumeWorkspaceRefresh();
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") { void refreshVisibleData(); scheduleTableQuotes(100); scheduleEventSummary(100); startQuoteStream(); }
    else { stopQuoteStream(); stopTableQuotes(); clearTimeout(eventSummaryTimer); clearTimeout(freshnessTimer); }
  });
  window.addEventListener("beforeunload", event => {
    if (acceptingUpdate) return;
    captureScreenDrafts();
    saveNavigationPosition();
    if (hasPending() || Object.keys(state.screenDrafts).length || state.assistantDraft.message.trim()) {
      event.preventDefault();
    }
  });
  window.addEventListener("pagehide", () => {
    stopQuoteStream();
    stopTableQuotes();
    clearTimeout(eventSummaryTimer);
    clearTimeout(freshnessTimer);
    const pendingGoal = $("#goal-form");
    if (pendingGoal?.dataset.busy === "true") reportGoalSaveError(pendingGoal, Object.assign(new Error("request_interrupted"), {
      status: 0
    }));
    clearTimeout(state.refresh.timer);
    state.refresh.sequence += 1;
    state.refresh.busy = false;
    for (const controller of state.requests) controller.abort();
    resetBrokerPreview();
    const input = $('#broker-form [name="credential"]');
    if (input) input.value = "";
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth > 960 && !$("#drawer-backdrop").hidden) closeDrawer(false);
    $("#app-sidebar").inert = window.innerWidth <= 960 && $("#drawer-backdrop").hidden;
  });
  window.addEventListener("offline", () => { stopQuoteStream(); toast(T("Нет соединения. Новые данные и изменения требуют сети."), true); });
  window.addEventListener("online", () => {
    toast(T("Соединение восстановлено. Проверяем сессию и обновляем данные."));
    void refreshVisibleData();
    scheduleTableQuotes(100);
    scheduleEventSummary(100);
    startQuoteStream();
    if (state.session.status === "error") void bootstrap();
  });
  prefersDark.addEventListener("change", () => {
    if (themeChoice === "system") applyTheme("system");
  });
  let sessionChannel = null;
  try {
    sessionChannel = new BroadcastChannel("omnicio-session");
    sessionChannel.addEventListener("message", event => {
      if (event.data?.type === "session-cleared" && state.user) lockSession(T("Сессия завершена в другой вкладке. Данные очищены."));
    });
  } catch {/* Server profile preconditions remain authoritative without BroadcastChannel. */}
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      const build = new URL(document.querySelector('script[src*="app.js"]').src).searchParams.get("build") || "";
      void navigator.serviceWorker.register(`/sw.js?build=${encodeURIComponent(build)}`).then(registration => {
        pwaRegistration = registration;
        if (registration.waiting) flagApplicationUpdate();
        registration.addEventListener("updatefound", () => {
          const worker = registration.installing;
          worker?.addEventListener("statechange", () => { if (worker.state === "installed" && navigator.serviceWorker.controller) flagApplicationUpdate(); });
        });
      }).catch(() => {/* Network use remains available without offline assets. */});
      navigator.serviceWorker.addEventListener("controllerchange", () => { if (acceptingUpdate) location.reload(); });
    });
  }
  if (window.OMNICIO_RELEASE && /^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$/.test(window.OMNICIO_RELEASE.version)) {
    for (const element of $$("[data-release-version]")) element.textContent = window.OMNICIO_RELEASE.version;
    for (const element of $$("[data-app-build]")) element.textContent = window.OMNICIO_RELEASE.build || "";
  }
  $("#app-sidebar").inert = window.innerWidth <= 960;
  applyTheme(themeChoice);
  renderNav();
  initializeNavigation();
  void bootstrap();
  function renderStableDocumentValue(value) {
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.keys(value).sort((left, right) => left.localeCompare(right)).map(key => [key, stableDocument(value[key])]));
    }
    return value;
  }
  function renderHumanErrorValue(error) {
    if (error?.status === 401) {
      return T("Войдите в личный аккаунт.");
    }
    return T("Не удалось получить подтверждение сервера. Проверьте соединение и повторите загрузку.");
  }
  function renderHumanErrorValue2(error) {
    if (error?.status === 409) {
      return T("Сохранённое состояние изменилось. Обновите данные перед повтором.");
    }
    return renderHumanErrorValue(error);
  }
  function renderHumanErrorValue3(error) {
    if (error?.status === 429) {
      return T("Слишком много запросов. Подождите немного и повторите.");
    }
    return renderHumanErrorValue2(error);
  }
  function renderApplyThemeValue() {
    if (prefersDark.matches) {
      return "dark";
    }
    return "light";
  }
  function renderAdoptWorkspaceValue(payload) {
    if (payload.connection?.connected) {
      return T("Счёт подключён · Ожидаем первое подтверждённое наблюдение.");
    }
    return T("Подключите данные счёта, чтобы увидеть свой портфель.");
  }
  function renderConnectionBannerValue(connection) {
    if (connection?.connected) {
      return T("Обновить");
    }
    return T("Подключить");
  }
  function renderConnectionBannerValue2(connection) {
    if (connection?.connected) {
      return "workspace-refresh";
    }
    return "connect";
  }
  function renderFiltersHTMLFilterButton(key, scope, title) {
    return `<button class="filter-button" data-asset-filter="${key}" data-filter-scope="${scope}" aria-pressed="${state.assetFilter === key}">${title}</button>`;
  }
  function renderAssetsTableValue() {
    if (state.sortDirection > 0) {
      return "ascending";
    }
    return "descending";
  }
  function renderAssetsTableFragment() {
    return ` aria-sort="${renderAssetsTableValue()}"`;
  }
  function renderAssetsTableTh(key, label) {
    return `<th scope="col"${key === state.sort ? renderAssetsTableFragment() : ""}><button data-sort="${key}">${label}${key === state.sort ? icon("down", true) : ""}</button></th>`;
  }
  function renderAssetsTableAssetTicker(item) {
    return `<small class="asset-ticker">${esc(item.ticker || item.instrument_type)}</small>`;
  }
  function renderAssetsTableValue2(item) {
    if (number(item.change) >= 0) {
      return "positive";
    }
    return "negative";
  }
  function renderAssetsTableHideOnMobile(item) {
    return `<td class="hide-on-mobile">${esc(money(item.value_rub))}</td><td>${watchButton(item)}</td>`;
  }
  function renderAssetsTableAssetName(item, compact) {
    return `<tr data-position="${esc(item.uid)}"><td><button class="asset-name" data-asset="${esc(item.uid)}"><span class="asset-logo">${esc((item.ticker || item.name).slice(0, 1))}</span><span>${esc(item.name)}${compact ? "" : renderAssetsTableAssetTicker(item)}</span></button></td><td data-table-quote="${esc(item.uid)}">${tableQuoteHTML(item)}</td><td class="${number(item.change) === null ? "muted" : renderAssetsTableValue2(item)}" title="${item.change === null ? T("Изменение цены за день не получено от источника") : T("Изменение цены за день")}">${esc(percent(item.change, true))}</td><td>${esc(percent(item.nav_percent))}</td>${compact ? "" : renderAssetsTableHideOnMobile(item)}</tr>`;
  }
  function renderHomeStrategyFragment(document) {
    return `${T("Просадка:")} ${esc(percent(document.profile.max_drawdown_percent))}`;
  }
  function renderHomeStrategyFragment2(horizon) {
    return `${esc(format(horizon / 12, 1))} ${T("лет")}`;
  }
  function renderEventsHTMLEventTitleButton(item) {
    return `<button class="event-title-button" data-event-open="${esc(item.id)}">${esc(item.title)}</button>`;
  }
  function renderEventsHTMLP(item) {
    return `<p>${esc(item.detail)}</p>`;
  }
  function renderEventsHTMLSpan(item) {
    const source = typeof item.source === "object" ? {operation: T("Операция брокера"), payout: T("Календарь выплат"), risk: T("Оценка инструмента"), goal: T("Цель"), audit: T("Журнал аккаунта"), job: T("Сбор данных")}[item.source.type] || T("Серверный факт") : item.source;
    return `<span>· ${esc(source)}</span>`;
  }
  function renderEventsHTMLIconButton(item) {
    return `<button class="icon-button" data-event-read="${esc(item.id)}" aria-label="${H("Отметить прочитанным")}">${icon("check", true)}</button>`;
  }
  function renderEventsHTMLEventItem(item, compact) {
    return `<article class="event-item${item.read_at ? "" : " unread"}"><span class="event-icon">${icon({
      payments: "wallet",
      goals: "goals",
      portfolio: "market"
    }[item.category] || "events", true)}</span><div class="event-item-body"><h3>${item.news ? U.sourceLink(item.url, item.title) : renderEventsHTMLEventTitleButton(item)}</h3>${!compact && item.detail ? renderEventsHTMLP(item) : ""}<div class="event-meta"><span>${esc(date(item.occurred_at, true))}</span>${item.news && state.data.news?.freshness === "cached" ? ("<span>" + H("· сохранённый ответ источника") + "</span>") : ""}${item.source ? renderEventsHTMLSpan(item) : ""}${item.read_at ? "" : '<span class="status-dot"></span>'}</div></div>${!compact && !item.read_at ? renderEventsHTMLIconButton(item) : ""}</article>`;
  }
  function renderHomeGoalsGoalsPreviewList(goals) {
    return `<div class="goals-preview-list">${goals.slice(0, 2).map(goalPreview).join("")}</div>`;
  }
  function renderHomeValue(result) {
    if (result >= 0) {
      return "positive";
    }
    return "negative";
  }
  function renderHomeDataFootnote(overview) {
    return `<p class="data-footnote">T-Invest · ${esc(date(overview.observed_at, true))} ${H("МСК")}</p>`;
  }
  function renderHomeFragment(performance) {
    return `${esc(date(performance.from))} — ${esc(date(performance.to))}<br>${H("Modified Dietz · оценка за период с учётом времени пополнений и выводов. Не годовая ставка.")}`;
  }
  function renderHomeMetricNote(result) {
    return `<p class="metric-note">${H("Результат:")} <span class="${renderHomeValue(result)}">${esc(money(result))}</span></p>`;
  }
  function renderHomeFragment2(latestMonth) {
    return `${latestMonth.month}-01`;
  }
  function renderHomeFragment3(latestMonth) {
    return `${T("Получено до налоговых списаний ·")} ${esc(date(renderHomeFragment2(latestMonth)))}`;
  }
  function renderHomeFragment4() {
    return `T-Invest · ${esc(date(state.data.visualization.latest.captured_at, true))} ${T("МСК")}`;
  }
  function renderEventFiltersFilterButton(key, title) {
    return `<button class="filter-button" data-event-filter="${key}" aria-pressed="${state.eventFilter === key}">${title}</button>`;
  }
  function renderPortfolioCard(title, value) {
    return `<article class="card"><p class="card-label">${title}</p><strong class="main-value">${esc(value)}</strong></article>`;
  }
  function renderNewsHTMLEventItem(item) {
    return `<article class="event-item"><span class="event-icon">${icon("events", true)}</span><div class="event-item-body"><h3><button class="event-title-button" data-public-news="${esc(item.id)}">${esc(item.title)}</button></h3><span class="event-meta">${H("Банк России ·")} ${esc(date(item.published_at, true))}</span></div></article>`;
  }
  function renderIndicatorCardsValue(key) {
    if (key === "key_rate") {
      return 2;
    }
    return 4;
  }
  function renderIndicatorCardsFragment(data, key, unit) {
    return `${esc(format(data[key].value, renderIndicatorCardsValue(key)))} ${unit}`;
  }
  function renderIndicatorCardsFragment2(data, key) {
    const label = key === "key_rate" ? T("Данные на") : T("Действует с");
    return `${label} ${esc(date(data[key].effective_date))}`;
  }
  function renderIndicatorCardsCard(title, data, key, unit) {
    return `<article class="card"><p class="card-label">${title}</p><strong class="indicator-value">${data?.[key] ? renderIndicatorCardsFragment(data, key, unit) : "—"}</strong><p class="indicator-date">${data?.[key]?.effective_date ? renderIndicatorCardsFragment2(data, key) : T("Нет данных от источника")}</p></article>`;
  }
  function renderMarketFragment() {
    return `${T("Официальный курс")} ${state.cbrCurrency}`;
  }
  function renderMarketSearchResult(item) {
    return `<div class="search-result"><button class="asset-name" data-asset="${esc(item.instrument_uid)}"><span class="asset-logo">${esc((item.ticker || item.name).slice(0, 1))}</span><span>${esc(item.name)}<small class="asset-ticker">${esc(item.ticker)}</small></span></button><span data-table-quote="${esc(item.instrument_uid)}">${tableQuoteHTML({uid: item.instrument_uid})}</span>${watchButton(item)}</div>`;
  }
  function renderMarketSearchResults() {
    return `<div class="search-results">${watchlist().map(item => renderMarketSearchResult(item)).join("")}</div>`;
  }
  function renderMarketNotice() {
    return `<div class="notice">${H("Для поиска инструментов и биржевых графиков подключите T-Invest.")}<div class="form-actions">${button(T("Подключить источник"), "connect", {
      primary: true,
      small: true
    })}</div></div>`;
  }
  function renderSearchSearchResult(item) {
    return `<button class="search-result" data-event-open="${esc(item.id)}">${icon("events")}<span><strong>${esc(item.title)}</strong><small>${H("Событие ·")} ${esc(date(item.occurred_at))}</small></span>${icon("chevron", true)}</button>`;
  }
  function renderSearchSearchResult2(item) {
    return `<article class="search-result">${icon("events")}<span><strong>${U.sourceLink(item.url, item.title)}</strong><small>${esc(item.source)} · ${esc(date(item.published_at))}</small></span></article>`;
  }
  function renderSearchSearchResult3(item) {
    return `<button class="search-result" data-asset="${esc(item.uid || item.instrument_uid)}" data-asset-name="${esc(item.name)}" data-asset-ticker="${esc(item.ticker)}"><span class="asset-logo">${esc((item.ticker || item.name || T("А")).slice(0, 1))}</span><span><strong>${esc(item.name)}</strong><small>${esc(item.ticker)} · ${esc({
      share: T("Акция"),
      bond: T("Облигация"),
      etf: T("Фонд"),
      currency: T("Валюта")
    }[item.instrument_type] || item.instrument_type || T("Инструмент"))}</small></span>${icon("chevron", true)}</button>`;
  }
  function renderSearchFragment(query) {
    return `${T("Результаты для «")}${query}»`;
  }
  function renderFundamentalMetricsHTMLValue(compact, metrics) {
    if (compact) {
      return 5;
    }
    return metrics.length;
  }
  function renderFundamentalMetricsHTMLDataFootnote(item) {
    return `<small class="data-footnote">${esc(item.period)}</small>`;
  }
  function renderFundamentalMetricsHTMLValue2(item) {
    if (item.period) {
      return renderFundamentalMetricsHTMLDataFootnote(item);
    }
    return "";
  }
  function renderFundamentalMetricsHTMLFragment(item) {
    return ` ${esc(item.unit)}`;
  }
  function renderFundamentalMetricsHTMLValue3(item) {
    if (item.unit) {
      return renderFundamentalMetricsHTMLFragment(item);
    }
    return "";
  }
  function renderFundamentalMetricsHTMLInfoRow(item) {
    return `<div class="info-row"><dt>${esc(item.label)}${renderFundamentalMetricsHTMLValue2(item)}</dt><dd>${esc(format(item.value, 2))}${renderFundamentalMetricsHTMLValue3(item)}</dd></div>`;
  }
  function renderFundamentalMetricsHTMLInfoList(metrics, compact) {
    return `<dl class="info-list">${metrics.slice(0, renderFundamentalMetricsHTMLValue(compact, metrics)).map(item => renderFundamentalMetricsHTMLInfoRow(item)).join("")}</dl>`;
  }
  function renderFundamentalMetricsHTMLLi(url) {
    return `<li>${U.sourceLink(url, T("Методика и данные источника"))}</li>`;
  }
  function renderFundamentalMetricsHTMLSourceList(facts) {
    return `<ul class="source-list">${[...new Set(facts.metrics.map(item => item.source_url).filter(Boolean))].map(url => renderFundamentalMetricsHTMLLi(url)).join("")}</ul>`;
  }
  function renderFundamentalMetricsHTMLLi2(item) {
    return `<li>${esc(humanRequirement(item))}</li>`;
  }
  function renderFundamentalMetricsHTMLDetailsSummary(facts) {
    return `<details><summary class="details-summary">${H("Недостающие данные")}</summary><ul class="risk-list">${facts.missing_requirements.map(item => renderFundamentalMetricsHTMLLi2(item)).join("")}</ul></details>`;
  }
  function renderFundamentalMetricsHTMLFinePrint(facts) {
    return `<p class="fine-print">${facts.limitations.map(item => esc(item)).join(" ")}</p>`;
  }
  function renderAssetValue(change) {
    if (change >= 0) {
      return "positive";
    }
    return "negative";
  }
  function renderAssetFragment2(asset) {
    return `${T("Цена")} ${asset.name}`;
  }
  function renderAssetFragment3(market) {
    return `${T("Режим торгов:")} ${esc(tradingLabel(market.trading_status))}. `;
  }
  function renderAssetDataFootnote(latest) {
    return `<p class="data-footnote">${H("Данные позиции ·")} ${esc(date(latest.captured_at, true))} ${H("МСК")}</p>`;
  }
  function renderAssetFragment4(market) {
    return `${date(market.quote_time, true)} ${T("МСК")}`;
  }
  function renderAssetLi(item) {
    return `<li>${U.sourceLink(item.source_url, item.document_type || item.provider || T("Источник"))}<p class="data-footnote">${esc(date(item.retrieved_at, true))}</p></li>`;
  }
  function renderAssetDetailsSummary(details) {
    return `<details><summary class="details-summary">${H("Документы инструмента")}</summary><ul class="source-list">${details.sources.map(item => renderAssetLi(item)).join("")}</ul></details>`;
  }
  function renderAssetTabButton(key, label) {
    return `<button class="tab-button" role="tab" data-asset-tab="${key}" aria-selected="${state.assetTab === key}">${label}</button>`;
  }
  function renderAssetNotice(asset) {
    return `<div class="notice error">${esc(humanError(asset.error))}${button(T("Повторить"), "asset-refresh", {
      small: true
    })}</div>`;
  }
  function renderAssetFinePrint(item) {
    return `<p class="fine-print">${esc(item.event_type || T("Выплата"))} · ${esc(date(item.payment_date || item.effective_at))}</p>`;
  }
  function renderAssetDetailsSummary2(details) {
    return `<details><summary class="details-summary">${H("Подтверждённые события выплат")}</summary>${details.payouts.slice(0, 12).map(item => renderAssetFinePrint(item)).join("")}</details>`;
  }
  function renderUpdateSaveStatusValue(slot) {
    if (slot.error.status === 409) {
      return "conflict";
    }
    return "error";
  }
  function renderUpdateSaveStatusValue2(slot) {
    if (slot.server) {
      return "saved";
    }
    return "empty";
  }
  function renderUpdateSaveStatusValue3(slot) {
    if (slot.dirty) {
      return "pending";
    }
    return renderUpdateSaveStatusValue2(slot);
  }
  function renderUpdateSaveStatusValue4(slot) {
    if (slot.busy) {
      return "saving";
    }
    return renderUpdateSaveStatusValue3(slot);
  }
  function renderUpdateSaveStatusFragment(kind) {
    return `${kind}-reload`;
  }
  function renderUpdateSaveStatusFragment2(kind) {
    return `${kind}-retry`;
  }
  function renderUpdateSaveStatusValue5(slot, kind) {
    if (slot.error.status === 409) {
      return "";
    }
    return button(T("Проверить и повторить"), renderUpdateSaveStatusFragment2(kind), {
      small: true
    });
  }
  function renderReloadVersionedFragment(kind) {
    return `${kind}-discard`;
  }
  function renderStrategiesStrategyOption(item, document, symbol) {
    return `<button class="strategy-option" data-select-strategy="${esc(item.id)}" aria-pressed="${document?.base_preset_id === item.id && !document?.customized}"><span class="strategy-icon" data-preset="${esc(item.id)}">${icon(symbol)}</span><span class="strategy-option-body"><strong>${esc(item.title)}</strong><small>${esc(strategyTaglines()[item.id] || item.description)}</small></span>${icon(document?.base_preset_id === item.id && !document?.customized ? "check" : "chevron", true)}</button>`;
  }
  function renderStrategiesValue() {
    if (state.tour) {
      return "login";
    }
    return "";
  }
  function renderStrategiesRangeRow(key, index, label, document) {
    return `<div class="range-row"><label class="range-label" for="allocation-${key}"><i class="legend-dot" data-color="${index}"></i>${label}</label><input id="allocation-${key}" type="range" min="0" max="100" step="1" value="${document.allocation[key]}" data-allocation="${key}"${document.locked.includes(key) || document.excluded.includes(key) ? " disabled" : ""}><output for="allocation-${key}">${document.allocation[key]}%</output></div>`;
  }
  function renderStrategiesAllocationFlagRow(label, key, document) {
    return `<div class="allocation-flag-row"><span>${label}</span><label><input type="checkbox" data-allocation-lock="${key}"${document.locked.includes(key) ? " checked" : ""}${document.excluded.includes(key) ? " disabled" : ""}>${H("Закрепить")}</label><label><input type="checkbox" data-allocation-exclude="${key}"${document.excluded.includes(key) ? " checked" : ""}>${H("Исключить")}</label></div>`;
  }
  function renderStrategiesFragment(grade) {
    return `strategy.rules.rating_caps.${grade}`;
  }
  function renderStrategiesFragment2(grade) {
    return `${T("Рейтинг")} ${grade}${T(", максимум %")}`;
  }
  function renderStrategiesLi(source) {
    const item = I.catalogSource(source);
    return `<li>${U.sourceLink(item.url, item.title)}</li>`;
  }
  function renderSelectionHTMLNotice(selection) {
    return `<p class="notice">${esc(selection.scope)}</p>`;
  }
  function renderSelectionHTMLPanelTitle(selected) {
    return `<h4 class="panel-title section-gap">${H("Расчётные доли инструментов")}</h4>${infoRows(selected.map(item => [item.ticker || item.instrument_uid, percent(item.target_weight_percent)]))}`;
  }
  function renderSelectionHTMLRiskList(selection) {
    return `<ul class="risk-list">${selection.missing_requirements.map(item => renderFundamentalMetricsHTMLLi2(item)).join("")}</ul>`;
  }
  function renderSelectionHTMLValue(item) {
    if (item.eligible) {
      return T("Прошёл условия отбора");
    }
    return T("Не прошёл условия");
  }
  function renderSelectionHTMLLi2(reason) {
    return `<li>${esc(humanRequirement(reason))}</li>`;
  }
  function renderSelectionHTMLRiskList2(item) {
    return `<ul class="risk-list">${item.reasons.map(reason => renderSelectionHTMLLi2(reason)).join("")}</ul>`;
  }
  function renderSelectionHTMLValue2(item) {
    if (item.reasons?.length) {
      return renderSelectionHTMLRiskList2(item);
    }
    return "";
  }
  function renderSelectionHTMLFinePrint(item) {
    return `<p class="fine-print">${H("Оценка для ранжирования:")} ${esc(format(item.score, 4))}${H(". Это не вероятность прибыли.")}</p>`;
  }
  function renderSelectionHTMLValue3(item) {
    if (number(item.score) !== null) {
      return renderSelectionHTMLFinePrint(item);
    }
    return "";
  }
  function renderSelectionHTMLLi3(key, fact) {
    return `<li>${esc(factLabels()[key] || T("Показатель источника"))}: ${esc(assessmentValue(fact.value, key))} · ${esc(date(fact.available_at))} ${U.sourceLink(fact.source_url, T("Источник"))}</li>`;
  }
  function renderSelectionHTMLSourceList(item) {
    return `<ul class="source-list">${Object.entries(item.facts).map(([key, fact]) => renderSelectionHTMLLi3(key, fact)).join("")}</ul>`;
  }
  function renderSelectionHTMLValue4(item) {
    if (Object.keys(item.facts || {}).length) {
      return renderSelectionHTMLSourceList(item);
    }
    return ("<p class=\"fine-print\">" + H("Нет датированных фактов источника.") + "</p>");
  }
  function renderSelectionHTMLDetailsSummary(item) {
    return `<details><summary class="details-summary">${esc(item.ticker || item.instrument_uid)} · ${renderSelectionHTMLValue(item)}</summary>${renderSelectionHTMLValue2(item)}${renderSelectionHTMLValue3(item)}${renderSelectionHTMLValue4(item)}</details>`;
  }
  function renderSelectionHTMLDetailsSummary2(candidates) {
    return `<details><summary class="details-summary">${H("Проверенные инструменты ·")} ${candidates.length}</summary>${candidates.map(item => renderSelectionHTMLDetailsSummary(item)).join("")}</details>`;
  }
  function renderAssessmentValue(item) {
    if (item.state === "fail" || item.state === "breach") {
      return "negative";
    }
    return "muted";
  }
  function renderAssessmentDetailsSummary(item) {
    return `<details><summary class="details-summary"><span class="${item.state === "pass" || item.state === "within_limit" || item.state === "evaluated" ? "positive" : renderAssessmentValue(item)}">${esc(item.title)}</span> · ${esc({
      pass: T("Соответствует"),
      within_limit: T("В пределах"),
      breach: T("Превышение"),
      fail: T("Не соответствует"),
      unknown: T("Недостаточно данных"),
      data_missing: T("Нет данных"),
      blocked: T("Ограничение"),
      missing: T("Нет данных"),
      not_applicable: T("Не применяется"),
      evaluated: T("Проверено"),
      inapplicable: T("Не применяется")
    }[item.state] || T("Требует проверки"))}</summary><p class="fine-print">${esc(item.detail)}</p>${infoRows([[T("Наблюдаемое значение"), assessmentValue(item.value, item.key)], [T("Ограничение"), assessmentValue(item.limit, item.key)]])}</details>`;
  }
  function renderResearchNotice(result) {
    return `<p class="notice warning">${H("Покрыта часть стратегии:")} ${esc(percent(result.research_asset_weight_percent))} ${H("в инструментах. Остаток расчётного капитала сохранён деньгами.")}</p>`;
  }
  function renderResearchValue(key, result) {
    if (key.endsWith("_rub")) {
      return money(result.metrics?.[key], 0, "RUB", false);
    }
    return format(result.metrics?.[key], 0);
  }
  function renderResearchAssessmentMetric(label, key, result) {
    return `<div class="assessment-metric"><span>${label}</span><strong>${esc(key.endsWith("_percent") ? percent(result.metrics?.[key]) : renderResearchValue(key, result))}</strong></div>`;
  }
  function renderResearchFinePrint(result) {
    return `<p class="fine-print">${H("Проверочный период начинается")} ${esc(date(result.period.test_from))}${H(". В нём")} ${esc(format(result.period.test_observations, 0))} ${H("наблюдений.")}</p>`;
  }
  function renderResearchValue2(key, result) {
    if (key.endsWith("_percent")) {
      return percent(result.benchmark.metrics[key]);
    }
    return format(result.benchmark.metrics[key], 2);
  }
  function renderResearchDetailsSummary(result) {
    return `<details><summary class="details-summary">${H("Сравнение:")} ${esc(result.benchmark.name)}</summary>${infoRows(Object.entries(researchMetricLabels()).filter(([key]) => result.benchmark.metrics?.[key] !== undefined).map(([key, label]) => [label, renderResearchValue2(key, result)]))}</details>`;
  }
  function renderResearchRiskList(result) {
    return `<ul class="risk-list">${result.missing_requirements.map(item => renderFundamentalMetricsHTMLLi2(item)).join("")}</ul>`;
  }
  function renderResearchLi2(item) {
    return `<li>${esc(item)}</li>`;
  }
  function renderResearchDetailsSummary2(result) {
    return `<details open><summary class="details-summary">${H("Границы результата")}</summary><ul class="risk-list">${result.limitations.map(item => renderResearchLi2(item)).join("")}</ul></details>`;
  }
  function renderResearchLi3(item) {
    return `<li>${U.sourceLink(item.url || item.source_url, item.label || item.title || item.provider || T("Источник"))}</li>`;
  }
  function renderResearchSourceList(result) {
    return `<ul class="source-list">${result.sources.map(item => renderResearchLi3(item)).join("")}</ul>`;
  }
  function renderGoalsValue(goal) {
    if (goal.kind === "income") {
      return "wallet";
    }
    return "building";
  }
  function renderGoalsValue2(goal) {
    if (goal.kind === "income") {
      return T(" полученных выплат");
    }
    return "";
  }
  function renderGoalsFragment(goal) {
    return ` · ${esc(percent(goal.allocation_percent))}`;
  }
  function renderGoalsValue3(goal) {
    if (goal.allocation_percent) {
      return renderGoalsFragment(goal);
    }
    return "";
  }
  function renderGoalsFragment2(goal) {
    return `${T("К")} ${esc(date(goal.target_date))}`;
  }
  function renderGoalsValue4(goal) {
    if (goal.target_date) {
      return renderGoalsFragment2(goal);
    }
    return T("Без фиксированного срока");
  }
  function renderGoalsDataFootnote(goal) {
    const warning = goal.progress.status === "stale" ? `<p class="notice warning">${H("goals.source_stale")}</p>` : "";
    return `${freshness(goal.progress_source === "manual" ? T("Сумма указана вами") : "T-Invest", goal.progress.as_of, goal.progress.status)}${warning}`;
  }
  function renderGoalsValue5(goal) {
    if (goal.progress?.as_of) {
      return renderGoalsDataFootnote(goal);
    }
    return "";
  }
  function renderGoalsCard(goal) {
    return `<article class="card goal-card" data-goal-id="${esc(goal.id)}"><div class="card-header"><span class="event-icon">${icon(renderGoalsValue(goal), true)}</span><span class="chip">${esc({
      active: T("Активная"),
      completed: T("Завершена"),
      archived: T("В архиве")
    }[goal.status])}</span></div><h2 class="panel-title">${esc(goal.title)}</h2><strong class="goal-amount">${esc(money(goal.progress?.amount_rub))}</strong><p class="value-subtitle">${H("из")} ${esc(money(goal.target_amount_rub))}${renderGoalsValue2(goal)}</p>${U.progress(goal.progress?.percent)}<p class="fine-print">${esc(goalReason(goal))}${renderGoalsValue3(goal)}</p><div class="goal-footer"><span>${renderGoalsValue4(goal)}</span><div class="goal-actions"><button class="icon-button" data-goal-plan="${esc(goal.id)}" aria-label="${H("Рассчитать план")} ${esc(goal.title)}">${icon("analytics", true)}</button><button class="icon-button" data-goal-edit="${esc(goal.id)}" aria-label="${H("Изменить цель")} ${esc(goal.title)}">${icon("settings", true)}</button><button class="icon-button" data-goal-delete="${esc(goal.id)}" aria-label="${H("Удалить цель")} ${esc(goal.title)}">${icon("trash", true)}</button></div></div>${renderGoalsValue5(goal)}</article>`;
  }
  function renderGoalsGoalGrid(goals) {
    return `<div class="goal-grid">${goals.map(goal => renderGoalsCard(goal)).join("")}</div>`;
  }
  function renderGoalsCard2() {
    return `<section class="card">${empty(T("У каждой цели есть первый шаг"), T("Задайте сумму и срок. Можно выделить часть портфеля, учитывать реальные выплаты или внести накопленную сумму вручную."), "goal-create", T("Создать первую цель"), "goals", true)}</section>`;
  }
  function renderGoalsValue6(goals) {
    if (goals.length) {
      return renderGoalsGoalGrid(goals);
    }
    return renderGoalsCard2();
  }
  function renderUpdateGoalFieldsValue(kind) {
    if (kind === "income") {
      return T("Прогресс — фактически полученные выплаты с даты начала, до отдельных налоговых списаний, умноженные на выбранную долю.");
    }
    return T("Прогресс — выбранная доля наблюдаемой стоимости портфеля. Он меняется вместе с рынком и движением денег.");
  }
  function renderEventsValue(data) {
    if (data.digest.frequency === "daily") {
      return T("Дневной");
    }
    return T("Недельный");
  }
  function renderEventsCard(data) {
    return `<section class="card section-gap"><h2 class="panel-title">${renderEventsValue(data)} ${H("дайджест")}</h2><p class="fine-print">${H("С")} ${esc(date(data.digest.from))}: ${esc(format(data.digest.count, 0))} ${H("событий. Дайджест доступен в кабинете.")}</p>${infoRows(Object.entries(data.digest.by_category || {}).map(([key, value]) => [{
      portfolio: T("Портфель"),
      payments: T("Выплаты"),
      goals: T("Цели"),
      system: T("Система")
    }[key] || key, format(value, 0)]))}</section>`;
  }
  function renderAnalyticsCard(label, value) {
    return `<section class="card"><p class="card-label">${label}</p><p class="main-value">${esc(value)}</p></section>`;
  }
  function renderAnalyticsFragment(performance) {
    return `${esc(date(performance.from))} — ${esc(date(performance.to))}. `;
  }
  function renderAnalyticsFragment2(item) {
    return `${item.month}-01`;
  }
  function renderAnalyticsDetailsSummary(item) {
    return `<details><summary class="details-summary">${esc(item.title)}</summary><p class="fine-print">${esc(item.detail)}</p></details>`;
  }
  function renderAnalyticsFragment3(analysis) {
    return `${infoRows([[T("Инструментов"), format(analysis.security_count, 0)], [T("Оценены по стоимости"), format(analysis.valued_security_count, 0)], [T("Покрытие по секторам"), percent(analysis.sector_coverage_percent)]])}${(analysis.observations || []).map(item => renderAnalyticsDetailsSummary(item)).join("")}`;
  }
  function renderProfileForm(prefs) {
    return `<form id="profile-form">${field({
      name: "display_name",
      label: T("Как к вам обращаться"),
      value: prefs.display_name || "",
      placeholder: T("Ваше имя")
    })}<div class="form-actions"><button class="button primary" type="submit">${H("Сохранить имя")}</button><span class="save-status" data-save-status="prefs"></span></div>${saveErrorHTML("prefs")}</form>`;
  }
  function renderProfileFragment() {
    return `${U.loading(T("Загружаем профиль…"))}${dataError("preferences")}`;
  }
  function renderProfileValue() {
    if (state.config?.tid_enabled) {
      return T("Можно подключить");
    }
    return T("Не подключён на сервере");
  }
  function renderProfileValue2() {
    if (state.config?.vkid_enabled) {
      return T("Можно подключить");
    }
    return T("Не подключён на сервере");
  }
  function renderSettingsValue() {
    if (state.errors.preferences) {
      return "preferences";
    }
    return "workspace";
  }
  function renderSettingsValue2() {
    if (state.errors.preferences || state.errors.workspace) {
      return dataError(renderSettingsValue());
    }
    return U.loading(T("Загружаем сохранённые настройки…"));
  }
  function renderBrokerSettingsHTMLFragment(connection) {
    return `${date(connection.verified_at, true)} ${T("МСК")}`;
  }
  function renderAssistantLi(source, requestId = "") {
    const label = source.label || source.kind || T("Источник");
    if (source.id && requestId) return `<li><button class="event-title-button" data-assistant-source="${esc(source.id)}" data-assistant-source-request="${esc(requestId)}">${esc(label)}</button></li>`;
    return `<li>${source.url ? U.sourceLink(source.url, label) : esc(label)}</li>`;
  }
  function renderAssistantSourceList(item) {
    return `<ul class="source-list">${item.sources.map(source => renderAssistantLi(source, item.request_id)).join("")}</ul>`;
  }
  function renderAssistantButton(text, configured) {
    return `<button class="button secondary" data-chat-prompt="${esc(text)}"${!configured ? " disabled" : ""}>${esc(text)}</button>`;
  }
  function renderAuthConfigValue(config) {
    if (config.registration_enabled) {
      return T("Новый аккаунт создаётся после подтверждения личности, если регистрация доступна.");
    }
    return T("Регистрация новых аккаунтов сейчас закрыта. Существующие пользователи могут войти.");
  }
  function renderOpenAuthValue(mode) {
    if (mode === "register") {
      return (H("Добро пожаловать!") + "<br>" + H("Создайте аккаунт"));
    }
    return (H("Добро пожаловать!") + "<br>" + H("Войдите в аккаунт"));
  }
  function renderOpenAuthValue2(mode) {
    if (mode === "register") {
      return T("Подтвердите личность через T-ID или VK ID. Создание аккаунта зависит от доступности регистрации.");
    }
    return T("Используйте свой T-ID или VK ID, чтобы открыть личный кабинет.");
  }
  function renderPreviewBrokerFragment(item) {
    return `${item.name} · ${item.id}`;
  }
  function renderUpdateStrategyFieldValue(input) {
    if (input.value === "") {
      return null;
    }
    return input.value;
  }
  function renderStepFieldValue(input) {
    if (input.name.endsWith("horizon_months")) {
      return 12n;
    }
    return 1n;
  }
  function renderStepFieldValue2(adjusted, maximum) {
    if (adjusted > maximum) {
      return maximum;
    }
    return adjusted;
  }
  function renderStepFieldFragment(decimal) {
    return `.${decimal}`;
  }
  function renderViewValue(event) {
    if (event.key === "ArrowRight") {
      return 1;
    }
    return -1;
  }
  function renderViewValue2(event, tabs, index) {
    if (event.key === "End") {
      return tabs.length - 1;
    }
    return (index + renderViewValue(event) + tabs.length) % tabs.length;
  }
  function renderViewValue3(event) {
    if (event.key === "ArrowDown") {
      return 1;
    }
    return -1;
  }
  function renderViewValue4(event, items, index) {
    if (event.key === "End") {
      return items.length - 1;
    }
    return (index + renderViewValue3(event) + items.length) % items.length;
  }
  async function handleClickCloseDialog({event}) {
    event.preventDefault();
    captureScreenDrafts();
    routeBack();
  }
  async function handleClickHelp({
    event,
    control
  }) {
    event.preventDefault();
    $("#help-title").textContent = control.dataset.helpTitle;
    $("#help-content").textContent = control.dataset.help;
    $("#help-dialog").showModal();
  }
  async function handleClickTheme({
    event,
    control
  }) {
    event.preventDefault();
    const choice = control.dataset.themeChoice;
    if (!["dark", "light", "system"].includes(choice)) return;
    if (!state.user || state.tour || !state.prefs.server) {
      state.pendingTheme = choice;
      applyTheme(choice);
      if (state.user && !state.tour && !state.loading.has("preferences")) {
        const generation = state.generation;
        await loadResource("preferences", "/api/preferences", {
          force: true
        });
        if (generation === state.generation && state.pendingTheme && state.errors.preferences) toast(T("Тема применена на этом устройстве. Настройки аккаунта не загрузились; повторите выбор темы после восстановления связи."), true);
      }
      return;
    }
    if (editPreferences(document => {
      document.theme = choice;
    })) syncThemeForm(choice);
  }
  function syncThemeForm(choice) {
    const formId = "preferences-form";
    const baseline = state.formBaselines[formId];
    const draft = state.formDrafts[formId];
    if (baseline) baseline.theme = choice;
    if (draft) {
      draft.theme = choice;
      if (same(draft, baseline)) delete state.formDrafts[formId];
    }
    const input = $("#preferences-form [name=theme]");
    if (input) input.value = choice;
    updateSaveStatus("prefs");
  }
  async function handleClickPublicView({
    event,
    control
  }) {
    event.preventDefault();
    navigate(control.dataset.publicOpen, {mode: "demo"});
  }
  async function handleClickRoute({
    event,
    control
  }) {
    event.preventDefault();
    navigate(control.dataset.route, {screen: control.dataset.screen || ""});
  }
  async function handleClickAuthMode({
    event,
    control
  }) {
    event.preventDefault();
    openAuth(control.dataset.authMode, state.authLink);
  }
  async function handleClickAsset({
    event,
    control
  }) {
    event.preventDefault();
    state.assetPeriod = "1m";
    state.assetTab = "chart";
    navigate("asset", {
      uid: control.dataset.asset
    });
  }
  async function handleClickAssetTab({
    event,
    control
  }) {
    event.preventDefault();
    state.assetTab = control.dataset.assetTab;
    updateViewRoute({tab: state.assetTab});
    renderAsset();
    U.bindCharts($("#view-asset"));
  }
  async function handleClickWatchlist({
    event,
    control
  }) {
    event.preventDefault();
    toggleWatch(control);
  }
  async function handleClickAssetFilter({
    event,
    control
  }) {
    event.preventDefault();
    state.assetFilter = control.dataset.assetFilter;
    updateViewRoute({asset_filter: state.assetFilter});
    renderCurrent();
  }
  async function handleClickSort({
    event,
    control
  }) {
    event.preventDefault();
    if (state.sort === control.dataset.sort) state.sortDirection *= -1;else {
      state.sort = control.dataset.sort;
      state.sortDirection = 1;
    }
    updateViewRoute({sort: state.sort, direction: String(state.sortDirection)});
    renderCurrent();
    $(`[data-sort="${state.sort}"]`, $(`#view-${state.view}`))?.focus({
      preventScroll: true
    });
  }
  async function handleClickPeriod({
    event,
    control
  }) {
    event.preventDefault();
    const scope = control.dataset.periodScope;
    updateViewRoute({period: control.dataset.period});
    if (scope === "asset") {
      state.assetPeriod = control.dataset.period;
      if (state.asset) await loadAsset(state.asset.uid);
    } else if (["home", "portfolio", "analytics"].includes(scope)) {
      state[`${scope}Period`] = control.dataset.period;
      renderCurrent();
      if (!state.tour) {
        await loadResource("workspace", workspacePath(), {
          force: true
        });
        if (state.view === scope) renderCurrent();
      }
    }
  }
  async function handleClickEventFilter({
    event,
    control
  }) {
    event.preventDefault();
    state.eventFilter = control.dataset.eventFilter;
    updateViewRoute({event_filter: state.eventFilter});
    state.eventHistoryExtended = false;
    delete state.data.events;
    renderCurrent();
    if (!state.tour && state.eventFilter !== "market") await loadResource("events", eventsPath(), {force: true});
    renderCurrent();
  }
  async function handleClickEventOpen({
    event,
    control
  }) {
    event.preventDefault();
    await openEvent(control.dataset.eventOpen);
  }
  async function handleClickEventRead({
    event,
    control
  }) {
    event.preventDefault();
    await markEvents([control.dataset.eventRead]);
  }
  async function handleClickGoalEdit({
    event,
    control
  }) {
    event.preventDefault();
    openGoal(control.dataset.goalEdit);
  }
  async function handleClickGoalDelete({
    event,
    control
  }) {
    event.preventDefault();
    confirmGoalDelete(control.dataset.goalDelete);
  }
  async function handleClickGoalDeleteConfirm({
    event,
    control
  }) {
    event.preventDefault();
    control.disabled = true;
    const generation = state.generation;
    const id = control.dataset.goalDeleteConfirm;
    try {
      const result = await api(`/api/goals/${safeSegment(id)}`, {
        method: "DELETE",
        body: {
          expected_version: Number(control.dataset.version)
        }
      });
      if (generation !== state.generation) return;
      if (result !== null && result?.deleted !== true) throw Object.assign(new Error("invalid_server_response"), {
        status: 502
      });
      state.deletedGoalIds.add(id);
      replaceGoalList((state.data.goals?.items || []).filter(goal => goal.id !== id));
      renderGoalConsumers();
      if (control.isConnected) $("#workspace-dialog").close();
      toast(T("Цель удалена."));
      await refreshGoalList(generation);
    } catch (error) {
      if (generation === state.generation) reportGoalDeleteError(control, error);
    }
  }
  async function handleClickStrategy({
    event,
    control
  }) {
    event.preventDefault();
    if (state.tour) { navigate("strategies", {screen: "detail", preset: control.dataset.selectStrategy}); return; }
    chooseStrategy(control.dataset.selectStrategy);
  }
  async function handleClickPublicStrategy({event, control}) {
    event.preventDefault();
    navigate("strategies", {mode: state.mode === "account" ? "account" : "demo", screen: "detail", preset: control.dataset.publicStrategy});
  }
  async function handleClickStep({
    event,
    control
  }) {
    event.preventDefault();
    stepField(control);
  }
  async function handleClickChatPrompt({
    event,
    control
  }) {
    event.preventDefault();
    const input = $("#assistant-form")?.elements.message;
    if (input && !input.disabled) {
      input.value = control.dataset.chatPrompt;
      state.assistantDraft.message = input.value;
      input.focus();
    }
  }
  async function handleClickAction({
    event,
    control
  }) {
    event.preventDefault();
    await actions[control.dataset.action](control);
  }
  async function handleChangeStrategyField({
    input
  }) {
    updateStrategyField(input);
  }
  async function handleChangeAllocationFlag({
    input
  }) {
    const document = state.strategy.draft;
    if (!document) return;
    const key = input.dataset.allocationLock || input.dataset.allocationExclude;
    const fieldName = input.dataset.allocationLock ? "locked" : "excluded";
    if (input.checked) {
      if (fieldName === "excluded") {
        const next = clone(document);
        next.locked = next.locked.filter(item => item !== key);
        if (!redistribute(next, key, 0)) {
          input.checked = false;
          toast(T("Освободите другую долю, прежде чем исключать этот класс."));
          return;
        }
        document.allocation = next.allocation;
        document.locked = next.locked;
      }
      if (!document[fieldName].includes(key)) document[fieldName].push(key);
    } else document[fieldName] = document[fieldName].filter(item => item !== key);
    documentChanged();
    renderStrategies();
  }
  async function handleChangeGoalSource({
    input
  }) {
    updateGoalFields(input.name === "kind");
  }
  async function handleChangeBrokerEnvironment({}) {
    resetBrokerPreview();
  }
  async function handleChangeMarketReference({
    input
  }) {
    if (input.name === "cbr_currency") state.cbrCurrency = input.value;else state.cbrPeriod = input.value;
    updateViewRoute({currency: state.cbrCurrency, reference_period: state.cbrPeriod});
    await loadResource("marketReference", `/api/public/market-reference?currency=${state.cbrCurrency}&period=${state.cbrPeriod}`, {
      force: true
    });
    if (state.view === "market") {
      renderMarket();
      U.bindCharts($("#view-market"));
    }
  }
  async function handleSubmitAuth({
    form,
    event
  }) {
    await startAuth(form, event.submitter?.value || "vkid");
  }
  async function handleSubmitSearch({
    form
  }) {
    navigate("search", {
      q: form.elements.q.value.trim().slice(0, 64)
    });
  }
  async function handleSubmitStrategy({}) {
    await saveVersioned("strategy");
  }
  async function handleSubmitGoal({
    form
  }) {
    await saveGoal(form);
  }
  async function handleSubmitProfile({
    form
  }) {
    const value = form.elements.display_name.value.trim();
    if (value.length > 80) {
      toast(T("Имя должно быть не длиннее 80 символов."), true);
      return;
    }
    const accepted = editPreferences(document => {
      document.display_name = value;
    });
    if (accepted) acceptFormSubmission(form);
  }
  async function handleSubmitPreferences({
    form
  }) {
    if (!form.reportValidity()) return;
    const controls = form.elements;
    const changed = editPreferences(document => {
      document.theme = controls.theme.value;
      document.locale = controls.locale.value;
      document.mask_balances = controls.mask_balances.checked;
      document.digest_frequency = controls.digest_frequency.value;
      document.digest_time = controls.digest_time.value;
      document.digest_timezone = controls.digest_timezone.value;
      document.quiet_hours = {
        enabled: controls.quiet_enabled.checked,
        start: controls.quiet_start.value,
        end: controls.quiet_end.value,
        timezone: controls.quiet_timezone.value
      };
      for (const key of ["portfolio", "payments", "goals", "system"]) document.notifications[key] = controls[`notify_${key}`].checked;
    });
    if (changed) {
      acceptFormSubmission(form);
    }
  }
  async function handleSubmitBroker({
    form
  }) {
    await previewBroker(form);
  }
  async function handleSubmitAssistant({
    form
  }) {
    await sendAssistant(form);
  }
  async function handleSubmitResearch({
    form
  }) {
    await runResearch(form);
  }
  async function handleSubmitAccountDeletion({
    form
  }) {
    if (!requireUser() || !form.reportValidity()) return;
    const confirmation = form.elements.confirm_public_id.value.trim();
    if (confirmation !== state.user.public_id) {
      showMessage($("#delete-account-message"), T("ID не совпадает с текущим профилем."), true);
      return;
    }
    const submit = form.querySelector("[type=submit]");
    submit.disabled = true;
    try {
      await api("/api/account/delete", {
        method: "POST",
        body: {
          confirm_public_id: confirmation,
          confirm_irreversible: form.elements.confirm_irreversible.checked
        }
      });
      clearPrivateState();
      state.session.status = "guest";
      try { localStorage.removeItem("omnicio-last-route"); } catch { /* Optional navigation state. */ }
      state.tour = false;
      state.locked = false;
      $("#app-shell").hidden = true;
      $("#public-site").hidden = false;
      sessionChannel?.postMessage({
        type: "session-cleared"
      });
      toast(T("Аккаунт удалён."));
      await bootstrap();
    } catch (error) {
      if (!isCancelled(error)) {
        showMessage($("#delete-account-message"), humanError(error), true);
        submit.disabled = false;
      }
    }
  }
  function handleSearchShortcut({
    event
  }) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k" && !$("#app-shell").hidden) {
      event.preventDefault();
      $("#global-search").focus();
    }
  }
  function handleEscape({
    event
  }) {
    if (event.key === "Escape") {
      if (!$("#drawer-backdrop").hidden) {
        event.preventDefault();
        closeDrawer();
      }
      if (!$("#profile-menu").hidden) {
        $("#profile-menu").hidden = true;
        $("#profile-button").setAttribute("aria-expanded", "false");
        $("#profile-button").focus();
      }
      delete $(".public-nav").dataset.open;
      $("#public-menu-toggle").setAttribute("aria-expanded", "false");
    }
  }
  function handleDrawerFocus({
    event
  }) {
    if (!$("#drawer-backdrop").hidden && event.key === "Tab") {
      const focusable = $$("a[href],button:not([disabled])", $("#app-sidebar")).filter(element => element.getClientRects().length);
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }
  function handleTabFocus({
    tab,
    event
  }) {
    if (tab && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      const tabs = $$('[role="tab"]', tab.closest('[role="tablist"]'));
      const index = tabs.indexOf(tab);
      const next = event.key === "Home" ? 0 : renderViewValue2(event, tabs, index);
      event.preventDefault();
      tabs[next].focus();
      tabs[next].click();
    }
  }
  function handleProfileFocus({
    event
  }) {
    if (!$("#profile-menu").hidden && ["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) {
      const items = $$('[role="menuitem"]', $("#profile-menu"));
      const index = items.indexOf(document.activeElement);
      const next = event.key === "Home" ? 0 : renderViewValue4(event, items, index);
      event.preventDefault();
      items[next].focus();
    }
  }
  function renderConnectionBannerValue3(connection) {
    if (connection?.connected && refreshUnavailable()) {
      return " disabled";
    }
    return "";
  }
})();
