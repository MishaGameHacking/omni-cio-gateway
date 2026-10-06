(() => {
  "use strict";
  const U = window.OmniUI;
  const {escape: esc, icon, money, percent, number, date, format, button, empty, heading, cardHeader, chart, periods, field, select, help, infoRows, freshness} = U;
  const $ = (selector, parent = document) => parent.querySelector(selector);
  const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
  const clone = (value) => structuredClone(value);
  const state = {
    user: null, config: null, generation: 0, locked: false, tour: false, view: "home", route: {},
    data: {}, errors: {}, loading: new Set(), requests: new Set(), resourceVersions: new Map(),
    homePeriod: "1m", portfolioPeriod: "1y", assetPeriod: "1m", assetTab: "chart", asset: null,
    assetFilter: "all", sort: "name", sortDirection: 1, eventFilter: "all", eventQuery: "all",
    searchQuery: "", searchResults: [], searchSequence: 0, cbrCurrency: "USD", cbrPeriod: "1m",
    prefs: {server: null, draft: null, revision: 0, dirty: false, busy: false, error: null, timer: null},
    strategy: {server: null, draft: null, revision: 0, dirty: false, busy: false, error: null, intent: "edit", timer: null, assessment: null, research: null},
    chat: [], assistantBusy: false, drawerReturn: null, verifying: false, authMode: "login",
  };
  const views = new Set([...U.navigation.map(([key]) => key), "asset", "search"]);
  const assetTypes = [["all", "Все"], ["share", "Акции"], ["bond", "Облигации"], ["etf", "Фонды"], ["currency", "Валюта"], ["other", "Другое"]];
  const strategyIcons = {balanced: ["portfolio", "#2b86ff"], conservative: ["shield", "#8645d8"], aggressive: ["analytics", "#f24964"], income: ["wallet", "#ef9b32"], growth: ["market", "#2f82ff"], buffett: ["shield", "#27c963"], bogle: ["building", "#af9a53"], dalio: ["portfolio", "#a04eed"], ladder: ["building", "#23ace9"], dividends: ["wallet", "#f26333"]};
  const strategyTaglines = {balanced: "Сочетание риска и доходности", conservative: "Сохранение капитала", aggressive: "Потенциал роста", income: "Регулярные выплаты", growth: "Долгосрочный рост", buffett: "Качество и устойчивость", bogle: "Широкий рынок и издержки", dalio: "Распределение рисков", ladder: "Постепенное погашение", dividends: "Источники выплат"};
  let themeChoice = "dark";
  try { const saved = localStorage.getItem("omnicio-theme"); if (["dark", "light", "system"].includes(saved)) themeChoice = saved; } catch { /* Theme storage is optional; no private data is stored. */ }
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
  const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
  const contextError = () => Object.assign(new Error("profile_context_changed"), {status: 409, code: "profile_context_changed"});
  const safeSegment = (value) => {
    const text = String(value ?? "");
    if (!text || text.length > 128 || text !== text.trim() || /[\\/?#\u0000-\u001f\u007f]/u.test(text)) throw new Error("invalid_instrument");
    return encodeURIComponent(text);
  };
  const apiPath = (path) => {
    if (typeof path !== "string" || !path.startsWith("/api/")) throw new TypeError("Only same-origin API requests are supported");
    const url = new URL(path, location.origin);
    if (url.origin !== location.origin || !url.pathname.startsWith("/api/") || url.hash || url.username || url.password) throw new TypeError("Invalid API origin");
    return url;
  };
  const privateRequest = (path) => !["/api/auth/config", "/api/auth/vkid/start", "/api/auth/tid/start", "/api/strategy/catalog", "/api/public/market-reference", "/api/public/news"].some((allowed) => path.split("?")[0] === allowed);
  const api = async (path, {method = "GET", body, timeout = 30000, bootstrap = false} = {}) => {
    const url = apiPath(path);
    if (state.locked && !bootstrap) throw contextError();
    if (state.tour && privateRequest(path) && path !== "/api/me") throw Object.assign(new Error("tour_requires_login"), {status: 401});
    if (!navigator.onLine && !["GET", "HEAD"].includes(method)) throw Object.assign(new Error("offline_write_not_sent"), {status: 0, definite: true});
    const generation = state.generation;
    const profile = state.user?.public_id;
    const controller = new AbortController();
    state.requests.add(controller);
    let timedOut = false;
    const timer = window.setTimeout(() => { timedOut = true; controller.abort(); }, timeout);
    const headers = new Headers({Accept: "application/json"});
    if (body !== undefined) headers.set("Content-Type", "application/json");
    if (profile && !bootstrap) headers.set("X-Omnicio-Profile", profile);
    try {
      const response = await fetch(url, {method, headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: "same-origin", cache: "no-store", redirect: "error", signal: controller.signal});
      const payload = response.status === 204 ? null : await response.json().catch(() => null);
      if (generation !== state.generation || (profile && state.user?.public_id !== profile)) throw contextError();
      if (state.locked && !bootstrap) throw contextError();
      if (!response.ok) {
        const code = typeof payload?.detail === "string" ? payload.detail : "request_failed";
        const error = Object.assign(new Error(code), {status: response.status, code});
        const requestId = response.headers.get("X-Request-ID") || "";
        if (/^[a-f0-9]{32}$/.test(requestId)) error.requestId = requestId;
        if (profile && (response.status === 401 || ["profile_context_changed", "profile_context_required", "settings_owner_conflict", "strategy_account_context_changed"].includes(code))) {
          lockSession(response.status === 401 ? "Сессия завершилась. Войдите снова, чтобы продолжить." : "Аккаунт в браузере изменился. Старые данные очищены. Проверьте текущую сессию.");
          throw contextError();
        }
        throw error;
      }
      if (payload?.public_id && profile && payload.public_id !== profile) {
        lockSession("Сервер вернул другой аккаунт. Старые данные очищены; требуется проверка сессии.");
        throw contextError();
      }
      if (response.status !== 204 && (!payload || typeof payload !== "object")) throw Object.assign(new Error("invalid_server_response"), {status: 502});
      return payload;
    } catch (error) {
      if (timedOut) throw Object.assign(new Error("request_timeout"), {status: 0, uncertain: method !== "GET"});
      throw error;
    } finally {
      clearTimeout(timer); state.requests.delete(controller);
    }
  };
  const humanError = (error) => {
    const reasons = {
      offline_write_not_sent: "Нет сети. Изменение не отправлено. Подключитесь к интернету и повторите.",
      request_timeout: "Сервер не успел ответить. Проверьте сохранённое состояние перед повтором.",
      invalid_server_response: "Получен неполный ответ сервера. Повторите загрузку.",
      tour_requires_login: "Для этого действия войдите в личный аккаунт.",
      profile_context_changed: "Сессия изменилась. Подтвердите текущий аккаунт.",
      settings_version_conflict: "Данные изменились в другой вкладке. Загрузите сохранённую версию перед следующей правкой.",
      strategy_assessment_busy: "Расчёт уже выполняется. Подождите и повторите через несколько секунд.",
      strategy_account_evidence_unavailable: "Не удалось получить согласованные данные счёта. Обновите подключение и повторите расчёт.",
      assistant_not_configured: "ИИ-провайдер ещё не подключён.", assistant_unavailable: "ИИ-провайдер сейчас не отвечает. Сообщение не получило ответа.",
      "T-Invest is not connected": "Подключите свой счёт T-Invest в настройках.",
      "stored T-Invest credential was rejected": "Срок действия API-токена истёк или доступ отозван. Проверьте подключение.",
      "T-Invest token rejected": "API-токен не прошёл проверку. Проверьте значение и выбранную среду.",
      "legal acknowledgments are required": "Подтвердите ознакомление с документами.",
      updated_legal_consent_required: "Условия сервиса обновились. Войдите повторно и подтвердите актуальные документы.",
      goal_allocation_exceeded: "Сумма долей активных целей превышает 100%. Уменьшите долю этой цели.",
    };
    const fallback = error?.status === 422 ? "Проверьте поля и допустимые значения. Сервер не принял изменение." : error?.status === 429 ? "Слишком много запросов. Подождите немного и повторите." : error?.status === 409 ? "Сохранённое состояние изменилось. Обновите данные перед повтором." : error?.status === 401 ? "Войдите в личный аккаунт." : "Не удалось получить подтверждение сервера. Проверьте соединение и повторите загрузку.";
    return reasons[error?.code || error?.message] || fallback;
  };
  const isCancelled = (error) => error?.name === "AbortError" || error?.message === "profile_context_changed";
  const toast = (message, isError = false) => {
    const item = document.createElement("div"); item.className = `toast${isError ? " error" : ""}`; item.textContent = message;
    $("#toast-region").append(item); window.setTimeout(() => item.remove(), isError ? 7000 : 4200);
  };
  const showMessage = (element, text, isError = false) => {
    if (!element) return; element.textContent = text; element.classList.toggle("error", isError); element.classList.toggle("success", !isError && Boolean(text));
  };
  const openDialog = (title, content) => {
    const dialog = $("#workspace-dialog"); $("#dialog-title").textContent = title; $("#dialog-content").innerHTML = content;
    if (!dialog.open) dialog.showModal(); U.bindCharts(dialog); return dialog;
  };
  const requireUser = () => { if (!state.user || state.tour) { openAuth(); return false; } return !state.locked; };
  const clearPrivateState = () => {
    state.generation += 1;
    for (const controller of state.requests) controller.abort();
    state.requests.clear(); state.resourceVersions.clear(); state.loading.clear();
    clearTimeout(state.prefs.timer); clearTimeout(state.strategy.timer);
    state.user = null; state.data = {}; state.errors = {}; state.chat = []; state.asset = null; state.searchResults = [];
    state.prefs = {server: null, draft: null, revision: 0, dirty: false, busy: false, error: null, timer: null};
    state.strategy = {server: null, draft: null, revision: 0, dirty: false, busy: false, error: null, intent: "edit", timer: null, assessment: null, research: null};
    state.assistantBusy = false; state.brokerPreview = null; state.brokerSequence = (state.brokerSequence || 0) + 1; U.setPrivacy(false);
    for (const view of $$(".view")) view.replaceChildren();
    $("#profile-name").textContent = "Мой профиль"; $("#profile-avatar").textContent = "О"; $("#global-search").value = "";
    $("#dialog-content").replaceChildren(); $("#toast-region").replaceChildren();
    for (const dialog of $$("dialog[open]")) dialog.close();
    closeDrawer(false); $("#profile-menu").hidden = true;
  };
  const lockSession = (message) => {
    if (state.locked) return;
    clearPrivateState(); state.locked = true; state.tour = false;
    $("#app-shell").hidden = true; $("#public-site").hidden = false;
    $("#session-message").textContent = message; $("#session-dialog").showModal();
  };
  const applyTheme = (choice) => {
    if (!["dark", "light", "system"].includes(choice)) return;
    themeChoice = choice;
    const actual = choice === "system" ? (prefersDark.matches ? "dark" : "light") : choice;
    document.documentElement.dataset.theme = actual;
    $("meta[name=theme-color]").content = actual === "dark" ? "#071421" : "#eff4fa";
    for (const item of $$("[data-theme-choice]")) item.setAttribute("aria-pressed", String(item.dataset.themeChoice === choice));
    try { localStorage.setItem("omnicio-theme", choice); } catch { /* Display preference only. */ }
  };
  const renderNav = () => {
    $("#sidebar-nav").innerHTML = U.navigation.map(([key, title]) => `<a class="nav-link" href="#${key}" data-route="${key}"${state.view === key || (key === "market" && ["asset", "search"].includes(state.view)) ? ' aria-current="page"' : ""}>${icon(key)}<span>${title}</span></a>`).join("");
    $("#mobile-nav").innerHTML = [["home", "Главная"], ["market", "Рынок"], ["assistant", "ИИ"], ["strategies", "Стратегии"]].map(([key, title]) => `<a href="#${key}" data-route="${key}"${state.view === key || (key === "market" && ["asset", "search"].includes(state.view)) ? ' aria-current="page"' : ""}>${icon(key)}<span>${title}</span></a>`).join("");
  };
  const openDrawer = () => {
    state.drawerReturn = document.activeElement; $("#app-sidebar").inert = false; $("#app-sidebar").dataset.open = "true";
    $("#drawer-backdrop").hidden = false; $("#app-menu-toggle").setAttribute("aria-expanded", "true");
    $(".app-main").inert = true; $("#mobile-nav").inert = true; document.body.style.overflow = "hidden";
    $("#drawer-close").focus();
  };
  function closeDrawer(restore = true) {
    delete $("#app-sidebar").dataset.open; $("#app-sidebar").inert = window.innerWidth <= 960; $("#drawer-backdrop").hidden = true;
    $("#app-menu-toggle").setAttribute("aria-expanded", "false");
    $(".app-main").inert = false; $("#mobile-nav").inert = false; document.body.style.overflow = "";
    if (restore && state.drawerReturn?.isConnected) state.drawerReturn.focus();
    state.drawerReturn = null;
  }
  const parseRoute = () => {
    const hash = location.hash.slice(1); const [name, query] = hash.split("?");
    const params = new URLSearchParams(query || "");
    return {view: views.has(name) ? name : "home", uid: params.get("uid") || "", q: params.get("q") || ""};
  };
  const navigate = (view, detail = {}, {replace = false, fromHistory = false} = {}) => {
    if (!views.has(view)) return;
    if (!state.user && !state.tour) { openAuth(); return; }
    closeDrawer(false); $("#profile-menu").hidden = true; $("#profile-button").setAttribute("aria-expanded", "false");
    if (state.view === "settings" && view !== "settings") { resetBrokerPreview(); const credential = $('#broker-form [name="credential"]'); if (credential) credential.value = ""; }
    state.view = view; state.route = detail;
    const query = new URLSearchParams();
    if (view === "asset" && detail.uid) query.set("uid", detail.uid);
    if (view === "search" && detail.q) query.set("q", detail.q);
    const hash = `#${view}${query.size ? `?${query}` : ""}`;
    if (!fromHistory && location.hash !== hash) history[replace ? "replaceState" : "pushState"]({view}, "", hash);
    for (const element of $$("[data-view]")) element.hidden = element.dataset.view !== view;
    document.title = `${U.navigation.find(([key]) => key === view)?.[1] || (view === "asset" ? "Актив" : "Поиск")} · OMNICIO`;
    renderNav(); renderCurrent(); void loadForView(view, detail);
    $("#main-content").focus({preventScroll: true}); window.scrollTo({top: 0, behavior: "instant"});
  };
  const showApp = (tour = false) => {
    state.tour = tour; $("#public-site").hidden = true; $("#app-shell").hidden = false; $("#tour-notice").hidden = !tour;
    updateIdentity(); const route = parseRoute(); navigate(route.view, route, {replace: true});
  };
  const loadResource = async (name, path, {force = false, ...options} = {}) => {
    if (!force && state.data[name] !== undefined) return state.data[name];
    if (state.loading.has(name) && !force) return null;
    const sequence = (state.resourceVersions.get(name) || 0) + 1; state.resourceVersions.set(name, sequence);
    const generation = state.generation; state.loading.add(name); delete state.errors[name];
    try {
      const payload = await api(path, options);
      if (generation !== state.generation || state.resourceVersions.get(name) !== sequence) return null;
      state.data[name] = payload;
      if (name === "workspace") adoptWorkspace(payload);
      if (name === "preferences") adoptPreferences(payload);
      if (name === "strategy") adoptStrategy(payload);
      return payload;
    } catch (error) {
      if (generation === state.generation && state.resourceVersions.get(name) === sequence && !isCancelled(error)) state.errors[name] = error;
      return null;
    } finally { if (generation === state.generation && state.resourceVersions.get(name) === sequence) state.loading.delete(name); }
  };
  const adoptWorkspace = (payload) => {
    if (payload.preferences) adoptPreferences(payload.preferences);
    if (payload.goals) state.data.goals = payload.goals;
    if (payload.events) state.data.events = payload.events;
    if (payload.connection) state.data.connection = payload.connection;
    $("#workspace-freshness").textContent = payload.overview?.observed_at ? `T-Invest · ${date(payload.overview.observed_at, true)} МСК · Стоимость по последнему наблюдению` : "Подключите данные счёта, чтобы увидеть свой портфель.";
  };
  const loadForView = async (view, detail = {}, force = false) => {
    const generation = state.generation;
    if (state.tour) {
      if (["home", "market", "events", "asset"].includes(view)) await loadResource("news", "/api/public/news", {force});
      if (view === "strategies") await loadResource("catalog", "/api/strategy/catalog", {force});
      if (view === "market") await loadResource("marketReference", `/api/public/market-reference?currency=${state.cbrCurrency}&period=${state.cbrPeriod}`, {force});
    } else {
      const requests = [];
      if (["home", "market", "events", "asset"].includes(view)) requests.push(loadResource("news", "/api/public/news", {force}));
      if (view === "profile") requests.push(loadResource("identities", "/api/auth/identities", {force}));
      if (["home", "portfolio", "analytics", "goals", "events", "settings", "profile"].includes(view)) requests.push(loadResource("workspace", "/api/workspace", {force}));
      if (["home", "portfolio", "analytics", "market"].includes(view)) requests.push(loadResource("visualization", "/api/portfolio/visualization?history_limit=365", {force}));
      if (["home", "strategies", "analytics"].includes(view)) requests.push(loadResource("strategy", "/api/profile/strategy", {force}), loadResource("catalog", "/api/strategy/catalog", {force}));
      if (view === "strategies") requests.push(loadResource("investmentProfile", "/api/profile/investment", {force}), loadResource("balancingPolicy", "/api/profile/balancing", {force}));
      if (["market", "home"].includes(view)) requests.push(loadResource("marketReference", `/api/public/market-reference?currency=${state.cbrCurrency}&period=${state.cbrPeriod}`, {force}));
      if (["market", "asset"].includes(view)) requests.push(loadResource("preferences", "/api/preferences", {force}), loadResource("connection", "/api/broker/tbank", {force}));
      if (["settings", "profile"].includes(view)) requests.push(loadResource("preferences", "/api/preferences", {force}), loadResource("connection", "/api/broker/tbank", {force}));
      if (view === "assistant") requests.push(loadResource("assistantStatus", "/api/assistant/status", {force}));
      if (view === "events") requests.push(loadResource("events", "/api/events?limit=50&category=all", {force}));
      if (view === "goals") requests.push(loadResource("goals", "/api/goals", {force}));
      if (view === "analytics") requests.push(loadResource("analysis", "/api/broker/tbank/analysis", {force, timeout: 45000}));
      await Promise.allSettled(requests);
      if (view === "asset" && detail.uid) { try { await loadAsset(detail.uid, force); } catch (error) { if (!isCancelled(error)) { state.asset = null; $("#view-asset").innerHTML = empty("Некорректный инструмент", "Откройте актив из портфеля или результатов поиска.", "", "", "info", true); } } return; }
      if (view === "search") { await runSearch(detail.q || ""); return; }
    }
    if (generation === state.generation && state.view === view) renderCurrent();
  };
  const dataError = (name, label = "Не удалось загрузить данные") => state.errors[name] ? `<div class="notice error"><strong>${esc(label)}</strong><p>${esc(humanError(state.errors[name]))}</p>${button("Повторить загрузку", "refresh", {small: true})}</div>` : "";
  const updateIdentity = () => {
    const name = state.prefs.draft?.display_name?.trim() || (state.tour ? "Знакомство" : "Мой профиль");
    $("#profile-name").textContent = name; $("#profile-avatar").textContent = name[0]?.toLocaleUpperCase("ru-RU") || "О";
    const unread = number(state.data.events?.unread_count) || 0; $("#notification-dot").hidden = unread === 0 || state.tour || Boolean(state.data.events?.alerts_suppressed);
    $("#notifications-button").setAttribute("aria-label", unread ? `Уведомления: ${unread} непрочитанных` : "Уведомления");
  };
  const renderConnectionBanner = () => {
    const banner = $("#connection-banner"); const ws = state.data.workspace; const connection = state.data.connection || ws?.connection;
    if (state.tour || state.locked) { banner.hidden = true; return; }
    let text = ""; let error = false;
    if (state.errors.workspace) { text = humanError(state.errors.workspace); error = true; }
    else if (connection && !connection.connected) text = "Подключите T-Invest, чтобы увидеть стоимость, состав и аналитику своего портфеля.";
    else if (connection?.environment === "sandbox") text = "Подключена тестовая среда T-Invest. Эти данные относятся к тестовому счёту.";
    else if (ws?.overview?.status === "stale") text = "Последнее наблюдение устарело. Значения помечены временем получения; обновите данные.";
    else if (ws?.overview?.status === "partial") text = "Получена только часть данных счёта. Некоторые показатели пока не рассчитаны.";
    banner.hidden = !text; banner.classList.toggle("error", error);
    banner.innerHTML = text ? `<span>${esc(text)}</span>${button(connection?.connected ? "Обновить" : "Подключить", connection?.connected ? "refresh" : "connect", {small: true})}` : "";
  };
  const portfolioRows = () => {
    const stored = state.data.visualization?.latest?.positions;
    return (Array.isArray(stored) ? stored : []).map((item) => ({...item, uid: item.instrument_uid, name: item.name || item.ticker || item.instrument_uid, price: item.current_price_value, currency: String(item.current_price_currency || item.currency || "").toUpperCase(), change: item.daily_change_percent ?? null}));
  };
  const filteredRows = () => {
    const matching = portfolioRows().filter((item) => state.assetFilter === "all" || (state.assetFilter === "other" ? !["share", "bond", "etf", "currency"].includes(item.instrument_type) : item.instrument_type === state.assetFilter));
    return matching.sort((a, b) => {
      if (state.sort === "name") return state.sortDirection * a.name.localeCompare(b.name, "ru");
      const key = {price: "price", change: "change", share: "nav_percent", value: "value_rub"}[state.sort];
      const left = number(a[key]); const right = number(b[key]);
      if (left === null) return right === null ? 0 : 1; if (right === null) return -1;
      return state.sortDirection * (left - right);
    });
  };
  const filtersHTML = (scope = "assets") => `<div class="filters" aria-label="Тип актива">${assetTypes.map(([key, title]) => `<button class="filter-button" data-asset-filter="${key}" data-filter-scope="${scope}" aria-pressed="${state.assetFilter === key}">${title}</button>`).join("")}</div>`;
  const assetsTable = (compact = true) => {
    if (state.tour) return empty("Ваши активы будут здесь", "Войдите и подключите свой счёт. Цены и доли появятся из источника.", "login", "Войти");
    if (state.errors.visualization) return dataError("visualization");
    const rows = filteredRows();
    if (!rows.length) return empty(portfolioRows().length ? "Нет активов этого типа" : "Активы пока не получены", portfolioRows().length ? "Выберите другой фильтр." : "Состав счёта появится после подключения и первого наблюдения.", portfolioRows().length ? "" : "connect", "Подключить счёт");
    const headers = [["name", "Название"], ["price", "Цена"], ["change", "Изменение"], ["share", "Доля"]];
    return `<div class="table-scroll"><table class="asset-table${compact ? "" : " full-table"}"><thead><tr>${headers.map(([key, label]) => `<th scope="col"${key === state.sort ? ` aria-sort="${state.sortDirection > 0 ? "ascending" : "descending"}"` : ""}><button data-sort="${key}">${label}${key === state.sort ? icon("down", true) : ""}</button></th>`).join("")}${compact ? "" : '<th class="hide-on-mobile" scope="col">Стоимость</th><th scope="col"><span class="sr-only">Избранное</span></th>'}</tr></thead><tbody>${(compact ? rows.slice(0, 5) : rows).map((item) => `<tr><td><button class="asset-name" data-asset="${esc(item.uid)}"><span class="asset-logo">${esc((item.ticker || item.name).slice(0, 1))}</span><span>${esc(item.name)}${compact ? "" : `<small class="asset-ticker">${esc(item.ticker || item.instrument_type)}</small>`}</span></button></td><td>${esc(money(item.price, 2, item.currency, false))}</td><td class="${number(item.change) === null ? "muted" : number(item.change) >= 0 ? "positive" : "negative"}" title="${item.change === null ? "Изменение цены за день не получено от источника" : "Изменение цены за день"}">${esc(percent(item.change, true))}</td><td>${esc(percent(item.nav_percent))}</td>${compact ? "" : `<td class="hide-on-mobile">${esc(money(item.value_rub))}</td><td>${watchButton(item)}</td>`}</tr>`).join("")}</tbody></table></div>`;
  };
  const selectedPreset = () => {
    const id = state.strategy.draft?.base_preset_id;
    const catalog = state.data.catalog;
    return [...(catalog?.presets || []), ...(catalog?.legacy_presets || [])].find((item) => item.id === id);
  };
  const strategyTitle = () => state.strategy.draft?.customized ? "Моя настройка" : selectedPreset()?.title || "Выберите стратегию";
  const homeStrategy = () => {
    const document = state.strategy.draft; const horizon = number(document?.profile?.horizon_months);
    return `${cardHeader("Моя стратегия")}<div class="strategy-current">${icon("strategies")}<strong>${esc(strategyTitle())}</strong><button class="icon-button" data-route="strategies" aria-label="Настройки стратегии">${icon("settings", true)}</button></div><div class="strategy-chips"><span class="chip">${document ? `Просадка: ${esc(percent(document.profile.max_drawdown_percent))}` : "Ваши условия"}</span><span class="chip">${horizon ? `${esc(format(horizon / 12, 1))} лет` : "Ваш горизонт"}</span></div><p class="strategy-note">${document ? "Проверка состава и ограничений на данных вашего счёта." : "Выберите подход и уточните личные параметры, чтобы начать расчёты."}</p><button class="button secondary full" data-route="strategies">Настроить стратегию ${icon("arrow", true)}</button>`;
  };
  const eventItems = () => {
    const news = (state.data.news?.items || []).map((item) => ({...item, occurred_at: item.published_at, news: true, read_at: item.published_at, severity: "info"}));
    const rows = [...(state.data.events?.items || []), ...news].sort((a, b) => (new Date(b.occurred_at).getTime() || 0) - (new Date(a.occurred_at).getTime() || 0));
    if (state.eventFilter === "important") return rows.filter((item) => ["warning", "critical", "high"].includes(item.severity));
    if (state.eventFilter === "assets") return rows.filter((item) => ["portfolio", "payments"].includes(item.category));
    if (state.eventFilter === "market") return rows.filter((item) => item.category === "market");
    return rows;
  };
  const eventsHTML = (compact = true) => {
    const rows = eventItems();
    if (!rows.length) return empty(state.eventFilter === "market" ? "Новостной источник не подключён" : "Нет новых событий", state.eventFilter === "market" ? "Система не подставляет заголовки. События счёта появятся после подключения данных." : "Подтверждённые события портфеля и целей появятся здесь.", "", "", "events");
    return `<div class="event-list">${(compact ? rows.slice(0, 4) : rows).map((item) => `<article class="event-item${item.read_at ? "" : " unread"}"><span class="event-icon">${icon(({payments: "wallet", goals: "goals", portfolio: "market"})[item.category] || "events", true)}</span><div class="event-item-body"><h3>${item.news ? U.sourceLink(item.url, item.title) : `<button class="event-title-button" data-event-open="${esc(item.id)}">${esc(item.title)}</button>`}</h3>${!compact && item.detail ? `<p>${esc(item.detail)}</p>` : ""}<div class="event-meta"><span>${esc(date(item.occurred_at, true))}</span>${item.news && state.data.news?.freshness === "cached" ? "<span>· сохранённый ответ источника</span>" : ""}${typeof item.source === "string" ? `<span>· ${esc(item.source)}</span>` : ""}${item.read_at ? "" : '<span class="status-dot"></span>'}</div></div>${!compact && !item.read_at ? `<button class="icon-button" data-event-read="${esc(item.id)}" aria-label="Отметить прочитанным">${icon("check", true)}</button>` : ""}</article>`).join("")}</div>`;
  };
  const goalPreview = (goal) => `<article class="goal-preview"><span class="event-icon">${icon(goal.kind === "income" ? "wallet" : "building", true)}</span><div class="goal-preview-body"><h3>${esc(goal.title)}</h3><p>${esc(money(goal.progress?.amount_rub))} из ${esc(money(goal.target_amount_rub))}</p>${U.progress(goal.progress?.percent)}</div></article>`;
  const homeGoals = () => {
    const goals = (state.data.goals?.items || []).filter((item) => item.status === "active");
    return `${cardHeader("Цели", "goals", "")}${goals.length ? `<div class="goals-preview-list">${goals.slice(0, 2).map(goalPreview).join("")}</div>` : empty("Начните с цели", "Укажите сумму и срок. Прогресс рассчитывается по выбранному источнику.", "goal-create", "Добавить цель", "goals")}<button class="button secondary full" data-route="goals">Все цели ${icon("arrow", true)}</button>`;
  };
  const renderHome = () => {
    const ws = state.data.workspace; const overview = ws?.overview || {}; const performance = ws?.performance || {}; const income = ws?.income || {};
    const monthly = Array.isArray(income.by_month) ? income.by_month : []; const latestMonth = monthly.at(-1);
    const incomeCurve = monthly.map((item) => ({...item, time: `${item.month}-01`}));
    const history = U.filteredSeries(overview.history, state.homePeriod);
    const result = number(performance.investment_result_rub);
    const resultText = result === null ? "Подключите счёт для расчёта" : `${money(result)} · результат за период`;
    $("#view-home").innerHTML = `<h1 class="sr-only">Главная — обзор портфеля</h1><div class="dashboard-top"><section class="card summary-card"><p class="card-label">Общая стоимость</p><p class="main-value">${esc(money(overview.nav_rub))}</p><div class="value-change ${result === null ? "" : result >= 0 ? "positive" : "negative"}">${esc(resultText)}</div>${overview.observed_at ? `<p class="data-footnote">T-Invest · ${esc(date(overview.observed_at, true))} МСК</p>` : ""}${chart(history, {label: "Стоимость портфеля", compact: true})}${periods("home", state.homePeriod)}</section><section class="card allocation-card">${cardHeader("Структура портфеля")}${U.allocation(overview.allocations, overview.nav_rub)}</section><div class="metric-stack"><section class="card metric-card"><p class="card-label">Доходность</p><p class="main-value">${esc(percent(performance.return_percent, true))}</p><p class="metric-note">${performance.return_percent === null || performance.return_percent === undefined ? "Для процента нужна подтверждённая методика и полная история потоков." : `${esc(date(performance.from))} — ${esc(date(performance.to))}`}</p>${result !== null ? `<p class="metric-note">Результат: <span class="${result >= 0 ? "positive" : "negative"}">${esc(money(result))}</span></p>` : ""}</section><section class="card metric-card secondary-metric"><p class="card-label">Пассивный доход</p><p class="main-value">${esc(money(latestMonth?.total_rub))}</p><p class="metric-note">${latestMonth ? `Получено до налоговых списаний · ${esc(date(`${latestMonth.month}-01`))}` : "Выплаты до налоговых списаний: данных пока нет"}</p>${incomeCurve.length > 1 ? chart(incomeCurve, {timeKey: "time", valueKey: "total_rub", label: "Полученные выплаты по месяцам", tone: "purple", compact: true}) : ""}</section></div><section class="card strategy-card">${homeStrategy()}</section></div><div class="dashboard-bottom"><section class="card">${cardHeader("Мои активы", "portfolio")}${filtersHTML()}${assetsTable()}<p class="data-footnote">${state.data.visualization?.latest?.captured_at ? `T-Invest · ${esc(date(state.data.visualization.latest.captured_at, true))} МСК` : "Только данные вашего подключённого счёта"}</p></section><section class="card">${cardHeader("Новости и события", "events", "")}${eventFilters()}${eventsHTML()}</section><section class="card goals-overview">${homeGoals()}</section></div>${!ws && state.loading.has("workspace") ? U.loading("Получаем состояние вашего кабинета…") : ""}`;
  };
  const eventFilters = () => `<div class="filters" aria-label="Фильтр событий">${[["important", "Важное"], ["assets", "Мои активы"], ["market", "Рынок"], ["all", "Все"]].map(([key, title]) => `<button class="filter-button" data-event-filter="${key}" aria-pressed="${state.eventFilter === key}">${title}</button>`).join("")}</div>`;
  const renderPortfolio = () => {
    const overview = state.data.workspace?.overview || {}; const performance = state.data.workspace?.performance || {};
    $("#view-portfolio").innerHTML = `${heading("Портфель", state.data.connection?.account_name || "Стоимость, структура и активы вашего счёта", button("Обновить", "refresh", {small: true}) + button("Подключение", "connect", {small: true}))}<div class="metric-grid">${[["Стоимость портфеля", money(overview.nav_rub)], ["Свободные средства", money(overview.free_cash_rub)], ["Результат за период", money(performance.investment_result_rub)], ["Активов", portfolioRows().length ? String(portfolioRows().length) : "—"]].map(([title, value]) => `<article class="card"><p class="card-label">${title}</p><strong class="main-value">${esc(value)}</strong></article>`).join("")}</div><div class="two-column"><section class="card">${cardHeader("Стоимость портфеля")}${chart(U.filteredSeries(overview.history, state.portfolioPeriod))}${periods("portfolio", state.portfolioPeriod)}<p class="data-footnote">График стоимости включает пополнения и выводы. Он не является графиком доходности.</p></section><section class="card">${cardHeader("Структура портфеля")}${U.allocation(overview.allocations, overview.nav_rub)}${freshness("T-Invest", overview.observed_at, overview.status)}</section></div><section class="card section-gap">${cardHeader("Мои активы")}${filtersHTML()}${assetsTable(false)}</section>${dataError("workspace")}`;
  };
  const newsHTML = () => {
    const rows = state.data.news?.items || [];
    if (!rows.length) return empty("Новостной источник пока недоступен", "Повторите обновление. Заголовки не заменяются примерами.", "", "", "events");
    return `<div class="event-list">${rows.slice(0, 8).map((item) => `<article class="event-item"><span class="event-icon">${icon("events", true)}</span><div class="event-item-body"><h3>${U.sourceLink(item.url, item.title)}</h3><span class="event-meta">Банк России · ${esc(date(item.published_at, true))}</span></div></article>`).join("")}</div>${freshness("Официальная лента Банка России", state.data.news.fetched_at, state.data.news.freshness === "cached" ? "Сохранённый ответ источника" : "")}`;
  };
  const indicatorCards = (reference) => {
    const data = reference?.indicators;
    return `<div class="market-indicators">${[["key_rate", "Ключевая ставка", "%"], ["usd_rub", "Доллар США", "₽"], ["eur_rub", "Евро", "₽"]].map(([key, title, unit]) => `<article class="card"><p class="card-label">${title}</p><strong class="indicator-value">${data?.[key] ? `${esc(format(data[key].value, key === "key_rate" ? 2 : 4))} ${unit}` : "—"}</strong><p class="indicator-date">${data?.[key]?.effective_date ? `Действует с ${esc(date(data[key].effective_date))}` : "Нет данных от источника"}</p></article>`).join("")}</div>`;
  };
  const watchlist = () => state.prefs.draft?.watchlist || [];
  const isWatched = (uid) => watchlist().some((item) => item.instrument_uid === uid);
  const watchButton = (item) => `<button class="icon-button" data-watch="${esc(item.uid || item.instrument_uid)}" data-watch-name="${esc(item.name || item.ticker || "Актив")}" data-watch-ticker="${esc(item.ticker || "")}" aria-label="${isWatched(item.uid || item.instrument_uid) ? "Удалить из избранного" : "Добавить в избранное"}" aria-pressed="${isWatched(item.uid || item.instrument_uid)}">${icon("star", true)}</button>`;
  const renderMarket = () => {
    const reference = state.data.marketReference;
    $("#view-market").innerHTML = `${heading("Рынок", "Официальные показатели и инструменты из подключённого источника", button("Обновить", "refresh", {small: true}))}${indicatorCards(reference)}<div class="two-column section-gap"><section class="card">${cardHeader("Курсы Банка России")}<div class="button-group">${select("cbr_currency", "Валюта", [["USD", "Доллар США"], ["EUR", "Евро"], ["CNY", "Китайский юань"]], state.cbrCurrency)}${select("cbr_period", "Период", [["1m", "Месяц"], ["3m", "Три месяца"], ["1y", "Год"]], state.cbrPeriod)}</div>${chart(reference?.history?.points, {timeKey: "effective_date", valueKey: "value", label: `Официальный курс ${state.cbrCurrency}`, personal: false})}${freshness("Банк России · официальный курс", reference?.history?.fetched_at || reference?.indicators?.fetched_at)}<p class="data-footnote">Официальный справочный курс отличается от биржевой котировки.</p></section><section class="card">${cardHeader("Избранное")}${watchlist().length ? `<div class="search-results">${watchlist().map((item) => `<div class="search-result"><button class="asset-name" data-asset="${esc(item.instrument_uid)}"><span class="asset-logo">${esc((item.ticker || item.name).slice(0, 1))}</span><span>${esc(item.name)}<small class="asset-ticker">${esc(item.ticker)}</small></span></button>${watchButton(item)}</div>`).join("")}</div>` : empty("Сохраните интересные активы", "Найдите компанию или тикер через поиск и нажмите звёздочку. Избранное сохраняется в аккаунте.", "", "", "star")}${!state.data.connection?.connected ? `<div class="notice">Для поиска инструментов и биржевых графиков подключите T-Invest.<div class="form-actions">${button("Подключить источник", "connect", {primary: true, small: true})}</div></div>` : ""}</section></div><section class="card section-gap">${cardHeader("Активы вашего счёта")}${filtersHTML()}${assetsTable(false)}</section>${dataError("marketReference")}<section class="card section-gap">${cardHeader("Новости Банка России")}${newsHTML()}</section>`;
  };
  const runSearch = async (query) => {
    const trimmed = String(query).trim().slice(0, 64); state.searchQuery = trimmed;
    $("#global-search").value = trimmed;
    const sequence = ++state.searchSequence; const generation = state.generation;
    if (!trimmed) { state.searchResults = []; renderSearch(); return; }
    if (state.tour) { renderSearch(); return; }
    state.loading.add("search"); delete state.errors.search; renderSearch();
    try {
      const payload = await api(`/api/broker/tbank/instruments/search?q=${encodeURIComponent(trimmed)}`);
      if (sequence !== state.searchSequence || generation !== state.generation) return;
      state.searchResults = Array.isArray(payload.items) ? payload.items : [];
    } catch (error) { if (!isCancelled(error) && sequence === state.searchSequence && generation === state.generation) state.errors.search = error; }
    finally { if (sequence === state.searchSequence && generation === state.generation) { state.loading.delete("search"); if (state.view === "search") renderSearch(); } }
  };
  const renderSearch = () => {
    const localEvents = (state.data.events?.items || []).filter((item) => `${item.title} ${item.detail}`.toLocaleLowerCase("ru-RU").includes(state.searchQuery.toLocaleLowerCase("ru-RU")));
    let content;
    if (state.tour) content = empty("Поиск доступен после входа", "Результаты приходят из API вашего подключённого источника.", "login", "Войти", "search", true);
    else if (state.loading.has("search")) content = U.loading("Ищем инструменты…");
    else if (state.errors.search) content = `<div class="notice error">${esc(humanError(state.errors.search))}<div class="form-actions">${button("Проверить подключение", "connect", {small: true})}</div></div>`;
    else if (!state.searchQuery) content = empty("Что найдём?", "Введите название компании, тикер или слово из события в строке поиска.", "", "", "search", true);
    else if (!state.searchResults.length && !localEvents.length) content = empty("Ничего не найдено", "Уточните название или попробуйте биржевой тикер.", "", "", "search", true);
    else content = `<div class="search-results">${state.searchResults.map((item) => `<button class="search-result" data-asset="${esc(item.uid || item.instrument_uid)}" data-asset-name="${esc(item.name)}" data-asset-ticker="${esc(item.ticker)}"><span class="asset-logo">${esc((item.ticker || item.name || "А").slice(0, 1))}</span><span><strong>${esc(item.name)}</strong><small>${esc(item.ticker)} · ${esc(({share: "Акция", bond: "Облигация", etf: "Фонд", currency: "Валюта"})[item.instrument_type] || item.instrument_type || "Инструмент")}</small></span>${icon("chevron", true)}</button>`).join("")}${localEvents.map((item) => `<button class="search-result" data-event-open="${esc(item.id)}">${icon("events")}<span><strong>${esc(item.title)}</strong><small>Событие · ${esc(date(item.occurred_at))}</small></span>${icon("chevron", true)}</button>`).join("")}</div>`;
    $("#view-search").innerHTML = `${heading("Поиск", state.searchQuery ? `Результаты для «${state.searchQuery}»` : "Инструменты, компании и события")}<section class="card">${content}</section>`;
  };
  const loadAsset = async (uid, force = false) => {
    const segment = safeSegment(uid); const generation = state.generation;
    const asset = state.asset?.uid === uid ? state.asset : {uid, name: portfolioRows().find((item) => item.uid === uid)?.name || watchlist().find((item) => item.instrument_uid === uid)?.name || state.searchResults.find((item) => (item.uid || item.instrument_uid) === uid)?.name || "Инструмент", ticker: portfolioRows().find((item) => item.uid === uid)?.ticker || watchlist().find((item) => item.instrument_uid === uid)?.ticker || state.searchResults.find((item) => (item.uid || item.instrument_uid) === uid)?.ticker || "", market: null, details: null};
    state.asset = asset; asset.loading = true; asset.error = null; renderAsset();
    const requestedPeriod = state.assetPeriod;
    const sequence = (state.resourceVersions.get("asset") || 0) + 1; state.resourceVersions.set("asset", sequence);
    const requests = [api(`/api/market/instruments/${segment}?period=${encodeURIComponent(requestedPeriod)}`)];
    if (!asset.details || force) requests.push(api(`/api/portfolio/instruments/${segment}/visualization?history_limit=365`));
    const results = await Promise.allSettled(requests);
    if (generation !== state.generation || state.resourceVersions.get("asset") !== sequence || state.asset?.uid !== uid || state.assetPeriod !== requestedPeriod) return;
    if (results[0].status === "fulfilled") asset.market = results[0].value;
    else if (!isCancelled(results[0].reason)) { asset.market = null; asset.error = results[0].reason; }
    if (results[1]?.status === "fulfilled") { asset.details = results[1].value; asset.name = asset.details.latest?.name || asset.name; asset.ticker = asset.details.latest?.ticker || asset.ticker; }
    asset.loading = false;
    if (state.view === "asset") { renderAsset(); U.bindCharts($("#view-asset")); }
  };
  const renderAsset = () => {
    const asset = state.asset;
    if (!asset || asset.uid !== state.route.uid) { $("#view-asset").innerHTML = U.loading("Получаем данные актива…"); return; }
    const market = asset.market; const details = asset.details; const latest = details?.latest || {};
    const candles = Array.isArray(market?.candles) ? market.candles : [];
    const current = number(market?.last_price); const initial = number(candles[0]?.open);
    const change = current !== null && initial !== null && initial !== 0 ? current - initial : null;
    const changePercent = change !== null ? change / initial * 100 : null;
    const searched = state.searchResults.find((item) => (item.uid || item.instrument_uid) === asset.uid);
    const currency = String(latest.current_price_currency || latest.currency || market?.currency || searched?.currency || "").toUpperCase();
    const chartContent = `<div class="main-value">${esc(money(current, 2, currency, false))}</div><p class="value-change ${change === null ? "" : change >= 0 ? "positive" : "negative"}">${change === null ? "Изменение за период не рассчитано" : `${esc(money(change, 2, currency, false))} (${esc(percent(changePercent, true))}) за выбранный период`}</p>${periods("asset", state.assetPeriod, true)}${asset.loading ? U.loading("Загружаем биржевой график…") : chart(candles, {timeKey: "time", valueKey: "close", label: `Цена ${asset.name}`, personal: false, currency})}${freshness(market?.source || "T-Invest", market?.quote_time || market?.observed_at, market?.quote_status)}<p class="data-footnote">${currency ? "" : "Валюта цены не получена от источника. "}${market?.trading_status ? `Режим торгов: ${esc(tradingLabel(market.trading_status))}. ` : ""}${state.assetPeriod === "all" ? "Доступная история источника. " : ""}${market?.history_note ? esc(market.history_note) + " " : ""}График показывает цены закрытия свечей.</p>`;
    let content = chartContent;
    if (state.assetTab === "overview") content = `${infoRows([["Название", asset.name], ["Тикер", asset.ticker || "—"], ["Тип", ({share: "Акция", bond: "Облигация", etf: "Фонд", currency: "Валюта"})[latest.instrument_type] || "Не получен"], ["В портфеле", money(latest.value_rub)], ["Доля", percent(latest.nav_percent)], ["Количество", format(latest.quantity, 8)]])}${details ? `<p class="data-footnote">Данные позиции · ${esc(date(latest.captured_at, true))} МСК</p>` : '<p class="notice">Инструмент не найден в истории вашего счёта. Биржевой график доступен независимо от наличия позиции.</p>'}`;
    if (state.assetTab === "metrics") content = `${infoRows([["Открытие периода", money(candles[0]?.open, 2, currency, false)], ["Максимум периода", money(candles.length ? Math.max(...candles.map((item) => number(item.high)).filter((item) => item !== null)) : null, 2, currency, false)], ["Минимум периода", money(candles.length ? Math.min(...candles.map((item) => number(item.low)).filter((item) => item !== null)) : null, 2, currency, false)], ["Последняя цена", money(current, 2, currency, false)], ["Время цены", market?.quote_time ? `${date(market.quote_time, true)} МСК` : "—"], ["Свечей в периоде", candles.length ? String(candles.length) : "—"], ["Режим торгов", tradingLabel(market?.trading_status)]])}<p class="data-footnote">Показатели рассчитаны только по полученным свечам выбранного периода.</p>`;
    if (state.assetTab === "news") content = details?.sources?.length ? `<h3 class="panel-title">Документы и источники</h3><ul class="source-list">${details.sources.map((item) => `<li>${U.sourceLink(item.source_url, item.document_type || item.provider || "Источник")}<p class="data-footnote">${esc(date(item.retrieved_at, true))}</p></li>`).join("")}</ul>` : `<h3 class="panel-title">Общерыночные новости Банка России</h3><p class="fine-print">Это официальный общий источник, а не лента отдельного эмитента.</p>${newsHTML()}`;
    $("#view-asset").innerHTML = `<div class="breadcrumb"><button class="icon-button" data-action="asset-back" aria-label="Назад к рынку">${icon("back")}</button><span>График актива</span></div><div class="asset-detail-header"><span class="asset-logo">${esc((asset.ticker || asset.name).slice(0, 1))}</span><div><h1>${esc(asset.name)}</h1><p>${esc(asset.ticker || "Инструмент T-Invest")}</p></div>${watchButton(asset)}</div><div class="asset-detail-layout"><section class="card asset-chart-card"><div class="tab-bar" role="tablist" aria-label="Карточка актива">${[["overview", "Обзор"], ["chart", "График"], ["metrics", "Показатели"], ["news", "Новости"]].map(([key, label]) => `<button class="tab-button" role="tab" data-asset-tab="${key}" aria-selected="${state.assetTab === key}">${label}</button>`).join("")}</div><div class="asset-tab-content" role="tabpanel">${asset.error ? `<div class="notice error">${esc(humanError(asset.error))}${button("Повторить", "asset-refresh", {small: true})}</div>` : ""}${content}</div></section><section class="card">${cardHeader("Основные показатели")}${infoRows([["Открытие", money(candles[0]?.open, 2, currency, false)], ["Максимум", money(candles.length ? Math.max(...candles.map((item) => number(item.high)).filter((item) => item !== null)) : null, 2, currency, false)], ["Стоимость в портфеле", money(latest.value_rub)], ["Доля портфеля", percent(latest.nav_percent)], ["Заблокировано лотов", latest.blocked_lots === undefined ? "—" : format(latest.blocked_lots)]])}<p class="notice">${esc(latest.risk_state ? riskLabel(latest.risk_state) : "Для оценки риска нужны данные об эмитенте и инструменте.")}</p>${details?.payouts?.length ? `<details><summary class="details-summary">Подтверждённые события выплат</summary>${details.payouts.slice(0, 12).map((item) => `<p class="fine-print">${esc(item.event_type || "Выплата")} · ${esc(date(item.payment_date || item.effective_at))}</p>`).join("")}</details>` : ""}</section></div>`;
  };
  const tradingLabel = (value) => ({SECURITY_TRADING_STATUS_NORMAL_TRADING: "Основная сессия", SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING: "Торги недоступны", SECURITY_TRADING_STATUS_CLOSING_PERIOD: "Закрытие сессии", SECURITY_TRADING_STATUS_BREAK_IN_TRADING: "Перерыв в торгах", SECURITY_TRADING_STATUS_OPENING_AUCTION_PERIOD: "Аукцион открытия", SECURITY_TRADING_STATUS_CLOSING_AUCTION: "Аукцион закрытия"})[value] || (value ? "Режим получен от биржи" : "Нет данных");
  const riskLabel = (value) => ({data_missing: "Недостаточно данных для полной оценки риска.", restricted: "Для инструмента действуют ограничения. Проверьте условия доступа.", observed: "Показаны фактические данные инструмента.", review_required: "Требуется дополнительная проверка данных."})[value] || "Оценка требует проверки исходных данных.";
  const validRecord = (record) => record && Number.isInteger(record.version) && record.version >= 0 && record.document && typeof record.document === "object";
  function adoptPreferences(payload) {
    if (!validRecord(payload)) return;
    const slot = state.prefs;
    if (slot.dirty || slot.busy || (slot.server && slot.server.version > payload.version)) return;
    slot.server = clone(payload); slot.draft = clone(payload.document); slot.error = null;
    U.setPrivacy(Boolean(payload.document.mask_balances));
    U.setLocale?.(payload.document.locale);
    applyTheme(payload.document.theme); updateIdentity();
  }
  function adoptStrategy(payload) {
    const selection = payload?.selection;
    const slot = state.strategy;
    if (slot.dirty || slot.busy) return;
    if (selection !== null && selection !== undefined && !validRecord(selection)) return;
    if (slot.server && (selection?.version || 0) < slot.server.version) return;
    slot.server = selection ? clone(selection) : null; slot.draft = selection ? clone(selection.document) : null; slot.error = null;
  }
  const updateSaveStatus = (kind) => {
    const slot = state[kind]; const status = slot.error ? (slot.error.status === 409 ? "conflict" : "error") : slot.busy ? "saving" : slot.dirty ? "pending" : slot.server ? "saved" : "empty";
    const text = ({conflict: "Конфликт версий", error: "Изменения не подтверждены", saving: "Сохраняем…", pending: "Есть несохранённые изменения", saved: "Сохранено на сервере", empty: "Пока не сохранено"})[status];
    for (const element of $$(`[data-save-status="${kind}"]`)) { element.dataset.state = status; element.textContent = text; }
    if (kind === "strategy") {
      const unavailable = !slot.server || slot.dirty || slot.busy || Boolean(slot.error);
      const assess = $('[data-action="assess-strategy"]'); if (assess) assess.disabled = unavailable || state.loading.has("assessment");
      const research = $('#research-form [type="submit"]'); if (research) research.disabled = unavailable || state.loading.has("research");
      const title = $(".strategy-heading h2"); if (title) title.textContent = strategyTitle();
      for (const option of $$("[data-select-strategy]")) option.setAttribute("aria-pressed", String(!slot.draft?.customized && option.dataset.selectStrategy === slot.draft?.base_preset_id));
      for (const tab of $$('[data-action="strategy-catalog"],[data-action="strategy-custom"]')) tab.setAttribute("aria-selected", String(tab.dataset.action === "strategy-custom" ? Boolean(slot.draft?.customized) : !slot.draft?.customized));
    }
    for (const element of $$(`[data-save-error="${kind}"]`)) {
      element.hidden = !slot.error;
      element.innerHTML = slot.error ? `<p>${esc(humanError(slot.error))}</p><div class="button-group">${button("Загрузить сохранённое", `${kind}-reload`, {small: true})}${slot.error.status === 409 ? "" : button("Проверить и повторить", `${kind}-retry`, {small: true})}</div>` : "";
    }
  };
  const applySavedEffects = (kind) => {
    if (kind === "prefs") {
      U.setPrivacy(Boolean(state.prefs.draft?.mask_balances)); U.setLocale?.(state.prefs.draft?.locale); updateIdentity();
    }
    updateSaveStatus(kind);
  };
  const writePayload = (kind, version, document, intent) => kind === "strategy" ? {expected_public_id: state.user.public_id, expected_version: version, intent, document} : {expected_version: version, document};
  const recordFrom = (kind, payload) => kind === "strategy" ? payload?.selection : payload;
  const acceptWrite = (kind, slot, saved, revision) => {
    if (!validRecord(saved)) throw Object.assign(new Error("invalid_server_response"), {status: 502});
    slot.server = clone(saved);
    if (slot.revision === revision) { slot.draft = clone(saved.document); slot.dirty = false; }
    slot.error = null; applySavedEffects(kind);
  };
  const saveVersioned = async (kind) => {
    const slot = state[kind];
    if (slot.busy || !slot.dirty || slot.error || !slot.draft || !state.user || state.locked) return;
    if (kind === "prefs" && !slot.server) return;
    const activeForm = $(`#${kind === "strategy" ? "strategy-form" : "preferences-form"}`);
    if (activeForm && !activeForm.checkValidity()) { slot.error = Object.assign(new Error("invalid_values"), {status: 422}); updateSaveStatus(kind); return; }
    const generation = state.generation; const path = kind === "strategy" ? "/api/profile/strategy" : "/api/preferences";
    slot.busy = true; updateSaveStatus(kind);
    try {
      while (slot.dirty && !slot.error && generation === state.generation && state[kind] === slot) {
        const revision = slot.revision; const document = clone(slot.draft); const expected = slot.server?.version || 0; const intent = slot.intent || "edit";
        try {
          const result = await api(path, {method: "PUT", body: writePayload(kind, expected, document, intent)});
          if (generation !== state.generation || state[kind] !== slot) return;
          const saved = recordFrom(kind, result);
          if (!validRecord(saved) || saved.version <= expected) throw Object.assign(new Error("invalid_server_response"), {status: 502});
          acceptWrite(kind, slot, saved, revision);
        } catch (error) {
          if (generation !== state.generation || isCancelled(error) || state[kind] !== slot) return;
          slot.error = error;
          if (!error.definite && (!error.status || error.status >= 500)) {
            try {
              const reconciliation = await api(path);
              if (generation !== state.generation || state[kind] !== slot) return;
              const actual = recordFrom(kind, reconciliation);
              if (validRecord(actual) && actual.version > expected && same(actual.document, document)) acceptWrite(kind, slot, actual, revision);
              else if (validRecord(actual) && actual.version > expected) slot.error = Object.assign(new Error("settings_version_conflict"), {status: 409});
            } catch (readError) { if (isCancelled(readError)) return; }
          }
          if (slot.error) break;
        }
      }
    } finally {
      if (generation === state.generation && state[kind] === slot) { slot.busy = false; updateSaveStatus(kind); }
    }
  };
  const scheduleSave = (kind) => {
    const slot = state[kind]; clearTimeout(slot.timer); updateSaveStatus(kind);
    slot.timer = window.setTimeout(() => { void saveVersioned(kind); }, 600);
  };
  const editPreferences = (change) => {
    if (!requireUser()) return false;
    if (!state.prefs.server || !state.prefs.draft) { toast("Сначала загрузите настройки с сервера. Начальные значения не будут сохранены поверх неизвестных данных.", true); return false; }
    if (state.prefs.error?.status === 409) { toast(humanError(state.prefs.error), true); return false; }
    const draft = clone(state.prefs.draft); change(draft);
    if (same(draft, state.prefs.draft)) return true;
    state.prefs.draft = draft; state.prefs.revision += 1; state.prefs.dirty = true; state.prefs.error = null;
    applySavedEffects("prefs"); scheduleSave("prefs"); return true;
  };
  const reloadVersioned = async (kind, discard = false) => {
    const slot = state[kind];
    if (slot.busy) { toast("Дождитесь завершения отправленного изменения."); return; }
    if (slot.dirty && !discard) {
      openDialog("Загрузить сохранённые данные?", `<p class="help-copy">Правки этой вкладки будут заменены текущей серверной версией.</p><div class="form-actions">${button("Загрузить с сервера", `${kind}-discard`, {primary: true})}<button class="button secondary" data-close-dialog>Отмена</button></div>`); return;
    }
    try {
      const generation = state.generation; const payload = await api(kind === "strategy" ? "/api/profile/strategy" : "/api/preferences");
      if (generation !== state.generation) return;
      slot.dirty = false; slot.error = null; slot.revision += 1;
      if (kind === "strategy") { adoptStrategy(payload); state.data.strategy = payload; slot.assessment = null; slot.research = null; }
      else adoptPreferences(payload);
      renderCurrent();
    } catch (error) { if (!isCancelled(error)) toast(humanError(error), true); }
  };
  const retryVersioned = async (kind) => {
    const slot = state[kind]; if (slot.busy || !slot.draft) return;
    try {
      const generation = state.generation; const payload = await api(kind === "strategy" ? "/api/profile/strategy" : "/api/preferences");
      if (generation !== state.generation) return;
      const actual = recordFrom(kind, payload);
      if ((actual?.version || 0) !== (slot.server?.version || 0)) {
        if (validRecord(actual) && same(actual.document, slot.draft)) { acceptWrite(kind, slot, actual, slot.revision); return; }
        slot.error = Object.assign(new Error("settings_version_conflict"), {status: 409}); updateSaveStatus(kind); return;
      }
      slot.error = null; await saveVersioned(kind);
    } catch (error) { if (!isCancelled(error)) { slot.error = error; updateSaveStatus(kind); } }
  };
  const saveErrorHTML = (kind) => `<div class="notice error" data-save-error="${kind}"${state[kind].error ? "" : " hidden"}></div>`;
  const preservePersonal = (document) => {
    const current = state.strategy.draft;
    for (const key of ["reserve_rub", "planned_withdrawal_rub"]) document.profile[key] = current?.profile?.[key] ?? state.data.investmentProfile?.profile?.[key] ?? null;
    document.policy.securities_tax_rate_percent = current?.policy?.securities_tax_rate_percent ?? state.data.balancingPolicy?.policy?.securities_tax_rate_percent ?? null;
    return document;
  };
  const chooseStrategy = (id) => {
    if (!requireUser()) return;
    if (state.loading.has("strategy") || state.loading.has("investmentProfile") || state.loading.has("balancingPolicy") || state.errors.strategy || state.errors.investmentProfile || state.errors.balancingPolicy || !Object.hasOwn(state.data, "strategy")) {
      toast("Сначала должны загрузиться сохранённая стратегия и личные условия. Повторите загрузку.", true); return;
    }
    if (state.strategy.error?.status === 409) { toast(humanError(state.strategy.error), true); return; }
    const preset = state.data.catalog?.presets?.find((item) => item.id === id); if (!preset) return;
    const document = preservePersonal(clone(preset.document));
    if (same(document, state.strategy.draft)) return;
    const slot = state.strategy; slot.draft = document; slot.dirty = true; slot.intent = "select"; slot.revision += 1; slot.error = null; slot.assessment = null; slot.research = null;
    renderStrategies(); scheduleSave("strategy");
  };
  const customizeStrategy = () => {
    if (!requireUser()) return;
    const slot = state.strategy;
    const custom = slot.server?.custom_document || slot.draft;
    if (!custom) { toast("Сначала выберите один из готовых подходов."); return; }
    slot.draft = preservePersonal(clone(custom)); slot.draft.customized = true; slot.intent = "edit"; slot.revision += 1; slot.dirty = true; slot.error = null; slot.assessment = null; slot.research = null;
    renderStrategies(); scheduleSave("strategy");
  };
  const policyFields = [
    ["max_instrument_percent", "Один инструмент", "%", 100, "Максимальная доля одного инструмента. Превышение отмечается в проверке состава; это не предел убытка."],
    ["max_sector_percent", "Один сектор", "%", 100, "Ограничение концентрации в одном секторе. Нужны данные о секторе каждого инструмента."],
    ["max_issuer_percent", "Один эмитент", "%", 100, "Суммарная доля бумаг одного эмитента. Малый лимит требует большего числа доступных инструментов."],
    ["max_group_percent", "Одна группа компаний", "%", 100, "Доля связанных эмитентов. Без подтверждённых связей полная проверка невозможна."],
    ["max_share_percent", "Акции — предел", "%", 100, "Верхняя граница доли акций. Целевые доли задаются отдельно в распределении."],
    ["max_bond_percent", "Облигации — предел", "%", 100, "Верхняя граница доли облигаций. Кредитный и процентный риски сохраняются."],
    ["max_etf_percent", "Фонды — предел", "%", 100, "Верхняя граница доли фондов. Состав фонда проверяется отдельно при наличии данных."],
    ["max_below_grade_percent", "Ниже инвест. уровня", "%", 100, "Максимальная доля бумаг ниже выбранного рейтингового уровня. Рейтинг не является вероятностью прибыли."],
    ["max_unknown_percent", "Неизвестные данные", "%", 100, "Допустимая доля инструментов с неполной классификацией. Неизвестное не означает безопасное."],
    ["max_term_months", "Срок инструментов", "мес.", 1200, "Предельный срок до погашения в условиях модели. Для проверки нужна дата погашения."],
    ["turnover_budget_percent", "Оборот портфеля", "%", 100, "Предел оборота в расчётном предложении. Сам по себе не включает исполнение сделок."],
    ["max_daily_turnover_participation_percent", "Участие в обороте", "%", 100, "Ограничение доли заявки в наблюдаемом дневном обороте. Требует данных ликвидности."],
    ["securities_tax_rate_percent", "Личная налоговая ставка", "%", 100, "Укажите ставку, применимую к вашей ситуации. Неизвестная ставка остаётся пустой и не заменяется предположением."],
    ["uncertainty_haircut_percent", "Запас на неопределённость", "%", 100, "Заданный запас в модели, а не статистически доказанная вероятность или гарантия."],
    ["credit_loss_haircut_percent", "Запас на кредитный риск", "%", 100, "Пользовательский параметр допустимого сценария потерь. Без данных эмитента это не прогноз дефолта."],
    ["no_trade_band_percent", "Порог отклонения долей", "%", 100, "Небольшие отклонения можно не перестраивать. Увеличение порога уменьшает частоту расчётной ребалансировки."],
    ["min_replace_benefit_rub", "Минимальный эффект замены", "₽", 1000000000000, "Минимальный расчётный эффект после заданных затрат. Сохранение значения не создаёт сделки."],
  ];
  const strategyField = (section, key, title, unit, max, helpText, value) => {
    const name = `strategy.${section}.${key}`;
    const step = key.includes("months") || key.includes("days") ? "1" : "any";
    return `<div class="field"><span>${esc(title)}${help(title, helpText)}</span><div class="touch-input"><button type="button" class="step-button" data-step-field="${name}" data-step-direction="-1" aria-label="Уменьшить: ${esc(title)}">−</button><input name="${name}" aria-label="${esc(title)}, ${esc(unit)}" type="number" inputmode="decimal" min="${key === "horizon_months" ? "1" : "0"}" max="${max}" step="${step}" value="${esc(value ?? "")}" placeholder="Не указано"><button type="button" class="step-button" data-step-field="${name}" data-step-direction="1" aria-label="Увеличить: ${esc(title)}">+</button><small>${esc(unit)}</small></div></div>`;
  };
  const renderStrategies = () => {
    const catalog = state.data.catalog; const slot = state.strategy; const document = slot.draft; const preset = selectedPreset();
    if (!catalog) { $("#view-strategies").innerHTML = `${heading("Стратегии", "Выбор подхода и личные ограничения")}${state.errors.catalog ? dataError("catalog") : U.loading("Получаем каталог стратегий…")}`; return; }
    const list = `<aside class="card strategy-catalog"><h2>Выбор стратегии</h2><div class="tab-bar" role="tablist" aria-label="Источник стратегии"><button class="tab-button" role="tab" data-action="strategy-catalog" aria-selected="${!document?.customized}">Готовые стратегии</button><button class="tab-button" role="tab" data-action="strategy-custom" aria-selected="${Boolean(document?.customized)}">Моя настройка</button></div>${catalog.presets.map((item) => { const [symbol, color] = strategyIcons[item.id] || ["strategies", "#3689ff"]; return `<button class="strategy-option" data-select-strategy="${esc(item.id)}" aria-pressed="${document?.base_preset_id === item.id && !document?.customized}"><span class="strategy-icon" style="--strategy-color:${color}">${icon(symbol)}</span><span class="strategy-option-body"><strong>${esc(item.title)}</strong><small>${esc(strategyTaglines[item.id] || item.description)}</small></span>${icon(document?.base_preset_id === item.id && !document?.customized ? "check" : "chevron", true)}</button>`; }).join("")}</aside>`;
    let editor;
    if (!document) editor = `<section class="card">${state.errors.strategy ? dataError("strategy") : empty("Выберите свой подход", "Изучите описание и выберите стратегию. Личные суммы не подставляются из шаблона; их задаёте вы.", state.tour ? "login" : "", "Войти", "strategies", true)}<p class="notice">Расчёты проверяют условия на данных, доступных системе. Ни одна стратегия не гарантирует сохранность капитала или прибыль.</p></section>`;
    else editor = `<div class="strategy-editor"><section class="card"><div class="strategy-heading"><h2>${esc(strategyTitle())}</h2><span class="save-status" data-save-status="strategy"></span></div><p class="strategy-note section-gap">${esc(preset?.description || "Ваши сохранённые параметры стратегии")}</p>${saveErrorHTML("strategy")}<form id="strategy-form"><div class="allocation-sliders">${[["shares", "Акции"], ["bonds", "Облигации"], ["funds", "Фонды"], ["cash", "Деньги"]].map(([key, label], index) => `<div class="range-row"><label class="range-label" for="allocation-${key}"><i class="legend-dot" style="background:${U.colors[index]}"></i>${label}</label><input id="allocation-${key}" type="range" min="0" max="100" step="1" value="${document.allocation[key]}" data-allocation="${key}"${document.locked.includes(key) || document.excluded.includes(key) ? " disabled" : ""}><output for="allocation-${key}">${document.allocation[key]}%</output></div>`).join("")}</div><p class="data-footnote">Сумма долей всегда 100%. Изменение одной доли пропорционально перераспределяет остальные незакреплённые доли.</p><details><summary class="details-summary">Закрепить или исключить классы</summary><div class="allocation-flags">${[["shares", "Акции"], ["bonds", "Облигации"], ["funds", "Фонды"], ["cash", "Деньги"]].map(([key, label]) => `<div class="allocation-flag-row"><span>${label}</span><label><input type="checkbox" data-allocation-lock="${key}"${document.locked.includes(key) ? " checked" : ""}${document.excluded.includes(key) ? " disabled" : ""}>Закрепить</label><label><input type="checkbox" data-allocation-exclude="${key}"${document.excluded.includes(key) ? " checked" : ""}>Исключить</label></div>`).join("")}</div></details><h3 class="panel-title section-gap">Ваши условия</h3><div class="field-grid">${strategyField("profile", "reserve_rub", "Резерв вне инвестиций", "₽", 1000000000000, "Личная сумма, которую следует сохранить доступной. Укажите реальное значение; пустое поле означает неизвестные условия.", document.profile.reserve_rub)}${strategyField("profile", "planned_withdrawal_rub", "Планируемый вывод", "₽", 1000000000000, "Запланированная потребность в деньгах. При смене готовой стратегии эта сумма сохраняется.", document.profile.planned_withdrawal_rub)}${strategyField("profile", "horizon_months", "Инвестиционный горизонт", "мес.", 1200, "Срок вашей цели. Более длинный срок не исключает убытки и потребность в резерве.", document.profile.horizon_months)}${strategyField("profile", "max_drawdown_percent", "Допустимая просадка", "%", 100, "Ваша готовность к временному снижению капитала. Это условие модели, а не гарантированный предел потерь.", document.profile.max_drawdown_percent)}${strategyField("profile", "liquidity_horizon_days", "Срок доступности денег", "дней", 36500, "За сколько дней вам могут понадобиться деньги. Фактическая ликвидность инструментов проверяется отдельно.", document.profile.liquidity_horizon_days)}</div><label class="check-field section-gap"><input type="checkbox" name="strategy.profile.allow_below_investment_grade"${document.profile.allow_below_investment_grade ? " checked" : ""}><span>Рассматривать бумаги ниже инвестиционного рейтинга. Это повышенный кредитный риск.</span></label><details><summary class="details-summary">Ограничения портфеля</summary><div class="field-grid">${policyFields.map(([key, title, unit, max, detail]) => strategyField("policy", key, title, unit, max, detail, document.policy[key])).join("")}</div></details><details><summary class="details-summary">Рейтинги и условия доходности</summary><p class="fine-print">Доли по рейтинговым категориям — верхние границы. Рейтинговый уровень не равен вероятности успеха.</p><div class="field-grid">${select("strategy.rules.yield_floor", "Условие доходности", [["none", "Не задавать"], ["key_rate", "От ключевой ставки"]], document.rules.yield_floor, "Порог применяется только при наличии сопоставимых данных о доходности инструмента и ключевой ставке.")}${strategyField("rules", "yield_margin_pp", "Надбавка к ставке", "п.п.", 100, "Заданная надбавка к официальной ключевой ставке для фильтра условий. Это не обещание доходности.", document.rules.yield_margin_pp)}${strategyField("rules", "fund_wrapper_cap_percent", "Доля одного фонда", "%", 100, "Дополнительный предел для отдельного фонда. Не отменяет проверки его состава.", document.rules.fund_wrapper_cap_percent)}${(catalog.rating_levels || []).map((grade) => field({name: `strategy.rules.rating_caps.${grade}`, label: `Рейтинг ${grade}, максимум %`, type: "number", min: 0, max: 100, step: "0.01", required: true, value: document.rules.rating_caps[grade]})).join("")}</div></details></form><details><summary class="details-summary">Методика и источники</summary><p class="help-copy">${esc(preset?.risk || "Проверяйте ограничения и полноту данных.")}</p><ul class="source-list">${(catalog.sources || []).filter((item) => !preset?.source_ids || preset.source_ids.includes(item.id)).map((item) => `<li>${U.sourceLink(item.url, item.title)}</li>`).join("")}</ul></details></section><section class="card"><div class="card-header"><h2>Проверка на вашем счёте</h2>${button("Рассчитать", "assess-strategy", {primary: true, small: true, extra: state.loading.has("assessment") || slot.busy || slot.dirty ? "disabled" : ""})}</div><p class="fine-print">Проверяются распределение и ограничения по фактическому составу. Расчёт не сохраняет новые условия и не создаёт сделки.</p><div id="strategy-assessment">${renderAssessment()}</div></section><section class="card"><h3 class="panel-title">Исследование на истории</h3><p class="fine-print">Задайте период, расчётный капитал и издержки. Система использует полученные наблюдения и отделяет проверочный период. Вероятность будущей прибыли из результата не выводится.</p>${researchForm()}<div id="strategy-research">${renderResearch()}</div></section></div>`;
    $("#view-strategies").innerHTML = `${heading("Стратегии", "Десять подходов. Ваши цели, ограничения и данные.", button("Обновить", "refresh", {small: true}))}<div class="strategy-layout">${list}${editor}</div>${dataError("investmentProfile")}${dataError("balancingPolicy")}`;
    updateSaveStatus("strategy"); U.bindCharts($("#view-strategies"));
  };
  const documentChanged = () => { const slot = state.strategy; slot.draft.customized = true; slot.intent = "edit"; slot.revision += 1; slot.dirty = true; if (slot.error?.status !== 409) slot.error = null; slot.assessment = null; slot.research = null; updateSaveStatus("strategy"); scheduleSave("strategy"); };
  const redistribute = (document, key, requested) => {
    const keys = ["shares", "bonds", "funds", "cash"];
    const others = keys.filter((item) => item !== key && !document.locked.includes(item) && !document.excluded.includes(item));
    const fixed = keys.filter((item) => item !== key && !others.includes(item)).reduce((sum, item) => sum + document.allocation[item], 0);
    const target = Math.max(0, Math.min(100 - fixed, Math.round(requested)));
    if (!others.length && target !== 100 - fixed) return false;
    document.allocation[key] = target;
    const remaining = 100 - fixed - target;
    const weight = others.reduce((sum, item) => sum + document.allocation[item], 0);
    const rows = others.map((item) => ({key: item, value: weight ? document.allocation[item] / weight * remaining : remaining / others.length}));
    rows.forEach((item) => { document.allocation[item.key] = Math.floor(item.value); });
    const rest = 100 - keys.reduce((sum, item) => sum + document.allocation[item], 0);
    rows.sort((a, b) => (b.value % 1) - (a.value % 1) || a.key.localeCompare(b.key));
    rows.slice(0, rest).forEach((item) => { document.allocation[item.key] += 1; }); return true;
  };
  const updateAllocation = (key, value) => {
    const slot = state.strategy; if (!slot.draft || slot.error?.status === 409) return;
    const before = clone(slot.draft.allocation);
    if (!redistribute(slot.draft, key, value)) { toast("Все остальные доли закреплены. Сначала освободите одну из них."); return; }
    if (same(before, slot.draft.allocation)) return;
    for (const input of $$("[data-allocation]")) { input.value = slot.draft.allocation[input.dataset.allocation]; input.nextElementSibling.textContent = `${input.value}%`; }
    documentChanged();
  };
  const renderAssessment = () => {
    if (state.loading.has("assessment")) return U.loading("Проверяем данные и ограничения счёта…");
    if (state.errors.assessment) return `<div class="notice error">${esc(humanError(state.errors.assessment))}</div>`;
    const result = state.strategy.assessment;
    if (!result) return empty("Проверка ещё не выполнена", "Сохраните параметры и запустите расчёт. Неполные данные будут отмечены отдельно.", "", "", "analytics");
    return `${freshness("Состав T-Invest", result.captured_at)}<div class="assessment-metrics section-gap"><div class="assessment-metric"><span>Стоимость счёта</span><strong>${esc(money(result.nav_rub))}</strong></div><div class="assessment-metric"><span>Проверок</span><strong>${result.checks?.length || 0}</strong></div><div class="assessment-metric"><span>Вероятность прибыли</span><strong>—</strong></div></div><p class="fine-print section-gap">${esc(result.probability_reason || "Проверка ограничений не оценивает вероятность будущей прибыли.")}</p>${(result.checks || []).map((item) => `<details><summary class="details-summary"><span class="${item.state === "pass" || item.state === "within_limit" ? "positive" : item.state === "fail" || item.state === "breach" ? "negative" : "muted"}">${esc(item.title)}</span> · ${esc(({pass: "Соответствует", within_limit: "В пределах", breach: "Превышение", fail: "Не соответствует", unknown: "Недостаточно данных", data_missing: "Нет данных", blocked: "Ограничение", missing: "Нет данных", not_applicable: "Не применяется"})[item.state] || item.state)}</summary><p class="fine-print">${esc(item.detail)}</p>${infoRows([["Наблюдаемое значение", typeof item.value === "object" ? "Составное условие" : item.value], ["Ограничение", typeof item.limit === "object" ? "Составное условие" : item.limit]])}</details>`).join("")}${result.selection ? `<details><summary class="details-summary">Результат подбора по фактам</summary><p class="fine-print">${esc(result.selection.reason || result.selection.status || "Подбор зависит от подтверждённых данных инструментов.")}</p>${Array.isArray(result.selection.candidates) ? `<div class="search-results">${result.selection.candidates.map((item) => `<div class="notice">${esc(item.name || item.ticker || item.instrument_uid)} · ${esc(item.status || "Проверено")}</div>`).join("")}</div>` : ""}</details>` : ""}`;
  };
  const assessStrategy = async () => {
    if (!requireUser()) return;
    const slot = state.strategy; if (!slot.server || slot.dirty || slot.busy || slot.error) { toast("Сначала дождитесь подтверждённого сохранения стратегии.", true); return; }
    const version = slot.server.version; const revision = slot.revision; const generation = state.generation;
    state.loading.add("assessment"); delete state.errors.assessment; slot.assessment = null; $("#strategy-assessment").innerHTML = renderAssessment();
    try {
      const result = await api("/api/profile/strategy/account-assessment", {method: "POST", timeout: 60000, body: {expected_public_id: state.user.public_id, expected_version: version}});
      if (generation !== state.generation || version !== slot.server?.version || revision !== slot.revision) return;
      slot.assessment = result;
    } catch (error) { if (generation === state.generation && !isCancelled(error)) state.errors.assessment = error; }
    finally { if (generation === state.generation) { state.loading.delete("assessment"); const container = $("#strategy-assessment"); if (container) container.innerHTML = renderAssessment(); } }
  };
  const researchForm = () => `<form id="research-form" class="research-form"><div class="field-grid">${field({name: "from_at", label: "Начало периода", type: "date", required: true})}${field({name: "to_at", label: "Конец периода", type: "date", required: true})}${field({name: "initial_capital_rub", label: "Расчётный капитал, ₽", type: "number", min: ".01", max: 1000000000000, step: ".01", required: true, helpText: "Капитал для исторического исследования. Это явно заданное условие расчёта, а не сумма реальных денег на вашем счёте."})}${field({name: "commission_bps", label: "Комиссия, базисных пунктов", type: "number", min: "0", max: "10000", step: ".01", required: true, helpText: "Один базисный пункт равен 0,01%. Укажите фактические или исследуемые издержки; значение не подставляется автоматически."})}${field({name: "slippage_bps", label: "Проскальзывание, базисных пунктов", type: "number", min: "0", max: "10000", step: ".01", required: true, helpText: "Дополнительная разница между наблюдаемой и расчётной ценой. Реальное проскальзывание заранее неизвестно."})}</div><div class="form-actions"><button class="button primary" type="submit"${state.strategy.dirty || state.strategy.busy || state.loading.has("research") ? " disabled" : ""}>Проверить на истории</button></div><p id="research-message" class="form-message" role="status"></p></form>`;
  const researchMetricLabels = {net_return_percent: "Результат за период", max_drawdown_percent: "Максимальная просадка", annualized_volatility_percent: "Волатильность, годовая", var_95_percent: "VaR, уровень 95%", expected_shortfall_95_percent: "Средние потери в хвосте 5%", transaction_costs_rub: "Заданные издержки", trades: "Расчётных сделок", ending_cash_rub: "Остаток средств"};
  const renderResearch = () => {
    if (state.loading.has("research")) return U.loading("Исследуем доступную историю…");
    const result = state.strategy.research;
    if (!result) return "";
    if (result.status !== "computed") return `<div class="notice warning"><strong>Недостаточно данных для исследования</strong><p>${esc(result.reason || (result.limitations || []).join(" ") || "Не получена достаточная история цен и доступности инструментов.")}</p></div>`;
    return `<div class="section-gap"><h3 class="panel-title">${esc(result.return_label || "Результат исторического исследования")}</h3>${result.complete_strategy_coverage === false ? `<p class="notice warning">Покрыта часть стратегии: ${esc(percent(result.research_asset_weight_percent))} в инструментах. Остаток расчётного капитала сохранён деньгами.</p>` : ""}<p class="research-period">${esc(date(result.period?.from))} — ${esc(date(result.period?.to))} · ${esc(format(result.period?.observations, 0))} наблюдений</p><div class="assessment-metrics">${Object.entries(researchMetricLabels).map(([key, label]) => `<div class="assessment-metric"><span>${label}</span><strong>${esc(key.endsWith("_percent") ? percent(result.metrics?.[key]) : key.endsWith("_rub") ? money(result.metrics?.[key], 0, "RUB", false) : format(result.metrics?.[key], 0))}</strong></div>`).join("")}</div>${chart(result.equity_curve, {timeKey: "time", valueKey: "nav_rub", label: "Расчётная стоимость на исторических данных", personal: false})}<p class="notice">${esc(result.probability_reason || "Результат на прошлом периоде не оценивает вероятность будущей прибыли.")}</p>${result.period?.test_from ? `<p class="fine-print">Проверочный период начинается ${esc(date(result.period.test_from))}. В нём ${esc(format(result.period.test_observations, 0))} наблюдений.</p>` : ""}${result.benchmark ? `<details><summary class="details-summary">Сравнение: ${esc(result.benchmark.name)}</summary>${infoRows(Object.entries(researchMetricLabels).filter(([key]) => result.benchmark.metrics?.[key] !== undefined).map(([key, label]) => [label, key.endsWith("_percent") ? percent(result.benchmark.metrics[key]) : format(result.benchmark.metrics[key], 2)]))}</details>` : ""}${result.missing_requirements?.length ? `<ul class="risk-list">${result.missing_requirements.map((item) => `<li>${esc(typeof item === "string" ? item : item.title || item.reason || "Недостаточное покрытие")}</li>`).join("")}</ul>` : ""}${result.limitations?.length ? `<details open><summary class="details-summary">Границы результата</summary><ul class="risk-list">${result.limitations.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></details>` : ""}${result.sources?.length ? `<ul class="source-list">${result.sources.map((item) => `<li>${U.sourceLink(item.url || item.source_url, item.label || item.title || item.provider || "Источник")}</li>`).join("")}</ul>` : ""}</div>`;
  };
  const goalReason = (goal) => {
    const source = ({portfolio: "Выделенная доля портфеля", income: "Полученные выплаты до налоговых списаний", manual: "Сумма указана вами"})[goal.progress_source] || "Источник прогресса";
    return number(goal.progress?.amount_rub) === null ? "Источник ещё не предоставил данные для расчёта прогресса." : source;
  };
  const renderGoals = () => {
    const goals = state.data.goals?.items || [];
    $("#view-goals").innerHTML = `${heading("Цели", "Капитал, сроки и прогресс из выбранного источника", button("Добавить цель", "goal-create", {primary: true}) + button("Обновить", "refresh", {small: true}))}${state.errors.goals ? dataError("goals") : goals.length ? `<div class="goal-grid">${goals.map((goal) => `<article class="card goal-card" data-goal-id="${esc(goal.id)}"><div class="card-header"><span class="event-icon">${icon(goal.kind === "income" ? "wallet" : "building", true)}</span><span class="chip">${esc(({active: "Активная", completed: "Завершена", archived: "В архиве"})[goal.status])}</span></div><h2 class="panel-title">${esc(goal.title)}</h2><strong class="goal-amount">${esc(money(goal.progress?.amount_rub))}</strong><p class="value-subtitle">из ${esc(money(goal.target_amount_rub))}${goal.kind === "income" ? " полученных выплат" : ""}</p>${U.progress(goal.progress?.percent)}<p class="fine-print">${esc(goalReason(goal))}${goal.allocation_percent ? ` · ${esc(percent(goal.allocation_percent))}` : ""}</p><div class="goal-footer"><span>${goal.target_date ? `К ${esc(date(goal.target_date))}` : "Без фиксированного срока"}</span><div class="goal-actions"><button class="icon-button" data-goal-edit="${esc(goal.id)}" aria-label="Изменить цель ${esc(goal.title)}">${icon("settings", true)}</button><button class="icon-button" data-goal-delete="${esc(goal.id)}" aria-label="Удалить цель ${esc(goal.title)}">${icon("trash", true)}</button></div></div>${goal.progress?.as_of ? `<p class="data-footnote">${esc(date(goal.progress.as_of, true))} МСК</p>` : ""}</article>`).join("")}</div>` : `<section class="card">${empty("У каждой цели есть первый шаг", "Задайте сумму и срок. Можно выделить часть портфеля, учитывать реальные выплаты или внести накопленную сумму вручную.", "goal-create", "Создать первую цель", "goals", true)}</section>`}<p class="notice section-gap">Доли активных целей проверяет сервер. Прогресс по портфелю зависит от стоимости счёта; выплаты учитываются до отдельных налоговых списаний.</p>`;
  };
  const localToday = () => new Intl.DateTimeFormat("en-CA", {timeZone: "Europe/Moscow", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date());
  const goalDocument = (goal) => goal ? Object.fromEntries(["title", "kind", "target_amount_rub", "target_date", "start_date", "progress_source", "allocation_percent", "manual_amount_rub", "status"].map((key) => [key, goal[key]])) : {title: "", kind: "capital", target_amount_rub: "", target_date: null, start_date: localToday(), progress_source: "portfolio", allocation_percent: "", manual_amount_rub: null, status: "active"};
  const openGoal = (id = "") => {
    if (!requireUser()) return;
    const goal = (state.data.goals?.items || []).find((item) => item.id === id);
    if (id && !goal) { toast("Цель не найдена. Обновите список.", true); return; }
    const document = goalDocument(goal);
    openDialog(goal ? "Настройка цели" : "Новая цель", `<form id="goal-form" class="goal-form" data-goal-id="${esc(id)}" data-goal-version="${goal?.version || 0}">${field({name: "title", label: "Название цели", value: document.title, required: true, placeholder: "Что вы хотите осуществить?"})}<div class="field-grid">${select("kind", "Тип цели", [["capital", "Накопить капитал"], ["income", "Получить выплаты"]], document.kind)}${field({name: "target_amount_rub", label: "Целевая сумма, ₽", type: "number", min: ".01", max: "1000000000000", step: ".01", value: document.target_amount_rub, required: true})}${field({name: "start_date", label: "Начало отсчёта", type: "date", value: document.start_date, required: true})}${field({name: "target_date", label: "Плановая дата", type: "date", value: document.target_date || "", hint: "Можно оставить пустой"})}${select("progress_source", "Источник прогресса", [[document.kind === "income" ? "income" : "portfolio", document.kind === "income" ? "Полученные выплаты" : "Часть портфеля"], ["manual", "Указать вручную"]], document.progress_source)}${select("status", "Состояние", [["active", "Активная"], ["completed", "Завершена"], ["archived", "В архиве"]], document.status)}${field({name: "allocation_percent", label: "Доля источника, %", type: "number", min: ".01", max: "100", step: ".01", value: document.allocation_percent || "", helpText: "Какая доля портфеля или подтверждённых выплат относится к этой цели. Общая доля активных целей не может превышать 100%."})}${field({name: "manual_amount_rub", label: "Уже накоплено вручную, ₽", type: "number", min: "0", max: "1000000000000", step: ".01", value: document.manual_amount_rub ?? "", helpText: "Сумма, которую вы подтверждаете сами. Она не выдаётся за полученную из брокерского API."})}</div><p id="goal-source-note" class="fine-print"></p><div class="form-actions"><button class="button primary" type="submit">${goal ? "Сохранить цель" : "Создать цель"}</button><button class="button secondary" type="button" data-close-dialog>Отмена</button></div><p id="goal-message" class="form-message" role="status"></p></form>`);
    updateGoalFields();
  };
  const updateGoalFields = (kindChanged = false) => {
    const form = $("#goal-form"); if (!form) return;
    const kind = form.elements.kind.value; const source = form.elements.progress_source;
    if (kindChanged) {
      const isManual = source.value === "manual";
      source.innerHTML = `<option value="${kind === "income" ? "income" : "portfolio"}">${kind === "income" ? "Полученные выплаты" : "Часть портфеля"}</option><option value="manual">Указать вручную</option>`;
      if (isManual) source.value = "manual";
    }
    const manual = source.value === "manual";
    form.elements.allocation_percent.disabled = manual; form.elements.allocation_percent.required = !manual;
    form.elements.manual_amount_rub.disabled = !manual; form.elements.manual_amount_rub.required = manual;
    $("#goal-source-note").textContent = manual ? "Вы явно задаёте накопленную сумму. Её можно обновить в любое время." : kind === "income" ? "Прогресс — фактически полученные выплаты с даты начала, до отдельных налоговых списаний, умноженные на выбранную долю." : "Прогресс — выбранная доля наблюдаемой стоимости портфеля. Он меняется вместе с рынком и движением денег.";
  };
  const saveGoal = async (form) => {
    if (!requireUser() || !form.reportValidity()) return;
    const controls = form.elements; const source = controls.progress_source.value;
    const document = {title: controls.title.value.trim(), kind: controls.kind.value, target_amount_rub: controls.target_amount_rub.value, target_date: controls.target_date.value || null, start_date: controls.start_date.value, progress_source: source, allocation_percent: source === "manual" ? null : controls.allocation_percent.value, manual_amount_rub: source === "manual" ? controls.manual_amount_rub.value : null, status: controls.status.value};
    if (document.target_date && document.target_date < document.start_date) { showMessage($("#goal-message"), "Плановая дата не может быть раньше начала отсчёта.", true); return; }
    const submit = form.querySelector("[type=submit]"); submit.disabled = true; const generation = state.generation;
    try {
      const id = form.dataset.goalId; const path = id ? `/api/goals/${safeSegment(id)}` : "/api/goals";
      await api(path, {method: id ? "PUT" : "POST", body: id ? {expected_version: Number(form.dataset.goalVersion), document} : {document}});
      if (generation !== state.generation) return;
      $("#workspace-dialog").close(); await loadResource("goals", "/api/goals", {force: true});
      if (generation !== state.generation) return;
      toast("Цель сохранена на сервере."); if (["goals", "home"].includes(state.view)) renderCurrent();
    } catch (error) {
      if (!isCancelled(error)) {
        showMessage($("#goal-message"), humanError(error), true);
        if (!error.status || error.status >= 500) { form.dataset.uncertain = "true"; $("#goal-message").innerHTML = `Результат сохранения не подтверждён. Проверьте список целей перед повтором.<div class="form-actions">${button("Проверить список", "goal-reconcile", {small: true})}</div>`; }
      }
    } finally { if (form.isConnected && generation === state.generation) submit.disabled = form.dataset.uncertain === "true"; }
  };
  const confirmGoalDelete = (id) => {
    if (!requireUser()) return;
    const goal = state.data.goals?.items?.find((item) => item.id === id); if (!goal) return;
    openDialog("Удалить цель?", `<p class="help-copy">Цель «${esc(goal.title)}» будет удалена из вашего аккаунта. Данные брокерского счёта это действие не изменяет.</p><div class="form-actions"><button class="button danger" data-goal-delete-confirm="${esc(goal.id)}" data-version="${goal.version}">Удалить цель</button><button class="button secondary" data-close-dialog>Отмена</button></div><p id="goal-delete-message" class="form-message" role="status"></p>`);
  };
  const renderEvents = () => {
    const data = state.data.events; const unread = number(data?.unread_count) || 0;
    $("#view-events").innerHTML = `${heading("События", "Подтверждённые изменения портфеля, выплат и целей", button("Обновить", "refresh", {small: true}) + (unread ? button("Прочитать все", "events-read-all", {small: true}) : ""))}<section class="card"><div class="card-header"><h2>Лента событий</h2><span class="chip">${unread} непрочитанных</span></div>${eventFilters()}${state.errors.events ? dataError("events") : eventsHTML(false)}</section>${data?.alerts_suppressed ? '<p class="notice section-gap">Сейчас действуют тихие часы. События доступны в ленте; уведомления подавлены вашими настройками.</p>' : ""}<div class="notice section-gap">Уведомления показываются внутри OMNICIO. Email, SMS и push-доставка не подключены. Категории, дайджест и тихие часы настраиваются в аккаунте.<div class="form-actions">${button("Настроить уведомления", "settings", {route: true, small: true})}</div></div>${data?.digest?.frequency && data.digest.frequency !== "off" ? `<section class="card section-gap"><h2 class="panel-title">${data.digest.frequency === "daily" ? "Дневной" : "Недельный"} дайджест</h2><p class="fine-print">С ${esc(date(data.digest.from))}: ${esc(format(data.digest.count, 0))} событий. Дайджест доступен в кабинете.</p>${infoRows(Object.entries(data.digest.by_category || {}).map(([key, value]) => [({portfolio: "Портфель", payments: "Выплаты", goals: "Цели", system: "Система"})[key] || key, format(value, 0)]))}</section>` : ""}`;
  };
  const markEvents = async (ids) => {
    if (!requireUser() || !ids.length) return;
    const generation = state.generation;
    try { const result = await api("/api/events/read", {method: "POST", body: {ids, read: true}}); if (generation !== state.generation) return; state.data.events = result; updateIdentity(); if (["events", "home"].includes(state.view)) renderCurrent(); }
    catch (error) { if (!isCancelled(error)) toast(humanError(error), true); }
  };
  const openEvent = (id) => {
    const event = state.data.events?.items?.find((item) => item.id === id); if (!event) return;
    const rawTarget = typeof event.target === "string" ? event.target.replace(/^#/, "") : "";
    const target = rawTarget === "income" ? "analytics" : rawTarget;
    openDialog(event.title, `<p class="help-copy">${esc(event.detail || "Подтверждённое событие вашего аккаунта.")}</p><p class="fine-print">${esc(date(event.occurred_at, true))} МСК${typeof event.source === "string" ? ` · ${esc(event.source)}` : ""}</p>${views.has(target) ? button("Открыть раздел", target, {route: true, primary: true}) : ""}`);
    if (!event.read_at) void markEvents([id]);
  };
  const renderAnalytics = () => {
    const ws = state.data.workspace; const performance = ws?.performance || {}; const income = ws?.income || {}; const analysis = state.data.analysis?.analysis;
    const result = number(performance.investment_result_rub);
    $("#view-analytics").innerHTML = `${heading("Аналитика", "Результат, денежные потоки и полнота исходных данных", button("Обновить", "refresh", {small: true}))}<div class="metric-grid">${[["Финансовый результат", money(result)], ["Чистые пополнения", money(performance.net_contributions_rub)], ["Полученные выплаты", money(income.total_rub)], ["Налоги", money(performance.taxes_rub)]].map(([label, value]) => `<section class="card"><p class="card-label">${label}</p><p class="main-value">${esc(value)}</p></section>`).join("")}</div><div class="two-column"><section class="card">${cardHeader("Стоимость по наблюдениям")}${chart(ws?.overview?.history)}${freshness("T-Invest", ws?.overview?.observed_at, ws?.overview?.status)}<p class="data-footnote">Изменение стоимости включает движение денег. Доходность не выводится из разницы крайних точек.</p></section><section class="card">${cardHeader("Из чего складывается результат")}${infoRows([["Стоимость в начале", money(performance.start_nav_rub)], ["Стоимость в конце", money(performance.end_nav_rub)], ["Изменение стоимости", money(performance.nav_change_rub)], ["Чистые пополнения / выводы", money(performance.net_contributions_rub)], ["Результат после внешних потоков", money(performance.investment_result_rub)], ["Комиссии за период", money(performance.fees_rub)], ["Налоговые списания", money(performance.taxes_rub)]])}<p class="data-footnote">${performance.from ? `${esc(date(performance.from))} — ${esc(date(performance.to))}. ` : ""}Метод: изменение стоимости минус внешние денежные потоки. Комиссии и налоги уже отражаются в результате; повторно они не вычитаются.</p></section></div><div class="two-column section-gap"><section class="card">${cardHeader("Выплаты до налоговых списаний")}${income.by_month?.length ? chart(income.by_month.map((item) => ({...item, time: `${item.month}-01`})), {timeKey: "time", valueKey: "total_rub", label: "Подтверждённые выплаты по месяцам", tone: "purple"}) : empty("История выплат пока недоступна", "Для расчёта нужны подтверждённые операции брокера.", "", "", "wallet")}${infoRows([["Купоны", money(income.coupons_rub)], ["Дивиденды", money(income.dividends_rub)], ["Прочие доходы", money(income.other_income_rub)], ["Погашения капитала", money(income.redemptions_rub)]])}<p class="data-footnote">Погашение возвращает капитал и не включается в доход. Налоговые списания учитываются отдельно в финансовом результате.</p></section><section class="card">${cardHeader("Полнота данных и риски")}${analysis ? `${infoRows([["Инструментов", format(analysis.security_count, 0)], ["Оценены по стоимости", format(analysis.valued_security_count, 0)], ["Покрытие по секторам", percent(analysis.sector_coverage_percent)]])}${(analysis.observations || []).map((item) => `<details><summary class="details-summary">${esc(item.title)}</summary><p class="fine-print">${esc(item.detail)}</p></details>`).join("")}` : empty("Анализ ещё не получен", "Проверьте подключение счёта и наличие наблюдений.", "connect", "Проверить подключение", "analytics")}${dataError("analysis")}</section></div>${performance.status === "unavailable" ? '<p class="notice section-gap">Финансовый результат не рассчитан: недостаточно подтверждённых снимков или истории денежных потоков. Пропуски не заменяются нулями.</p>' : ""}<section class="card section-gap">${cardHeader("Проверка выбранной стратегии", "strategies", "Открыть")}<p class="fine-print">${esc(strategyTitle())}. Подробные ограничения, проверка состава и исследование на истории находятся в разделе стратегий.</p></section>`;
  };
  const renderProfile = () => {
    if (state.tour) { $("#view-profile").innerHTML = `${heading("Профиль")}<section class="card">${empty("Ваш личный аккаунт", "Войдите через T-ID или VK ID, чтобы настроить профиль.", "login", "Войти", "profile", true)}</section>`; return; }
    const prefs = state.prefs.draft; const user = state.user;
    $("#view-profile").innerHTML = `${heading("Профиль", "Личные настройки и доступ к аккаунту")}<div class="settings-layout"><section class="card"><div class="profile-summary"><span class="avatar">${esc((prefs?.display_name || "О").slice(0, 1).toUpperCase())}</span><div><h2>${esc(prefs?.display_name || "Мой профиль")}</h2><p>Профиль ${esc(user?.public_id)} · ${user?.role === "owner" ? "Владелец" : "Пользователь"}</p></div></div>${prefs ? `<form id="profile-form">${field({name: "display_name", label: "Как к вам обращаться", value: prefs.display_name || "", placeholder: "Ваше имя"})}<div class="form-actions"><button class="button primary" type="submit">Сохранить имя</button><span class="save-status" data-save-status="prefs"></span></div>${saveErrorHTML("prefs")}</form>` : `${U.loading("Загружаем профиль…")}${dataError("preferences")}`}<div class="form-actions"><button class="button secondary" data-action="copy-profile">${icon("copy", true)}Копировать ID профиля</button></div></section><section class="card"><h2 class="panel-title">Способы входа</h2>${infoRows([["T-ID", state.data.identities?.providers?.includes("tid") ? "Привязан к аккаунту" : state.config?.tid_enabled ? "Можно подключить" : "Не подключён на сервере"], ["VK ID", state.data.identities?.providers?.includes("vkid") ? "Привязан к аккаунту" : state.config?.login_enabled ? "Можно подключить" : "Не подключён на сервере"], ["Подключённый счёт", state.data.connection?.account_name || "Нет подключения"]])}<p class="fine-print section-gap">Вход подтверждает личный аккаунт OMNICIO. Подключение брокерских данных настраивается отдельно.</p><div class="form-actions">${button("Подключить способ входа", "link-identity", {small: true})}${button("Настройки", "settings", {route: true, small: true})}${button("Выйти", "logout", {small: true})}</div></section><section class="card wide"><h2 class="panel-title">Удаление аккаунта</h2><p class="fine-print">Удаляются профиль OMNICIO, его настройки, сессии и сохранённое подключение. Операция требует подтверждения ID вашего профиля.</p><button class="button danger" data-action="delete-account">Удалить аккаунт</button></section></div>`;
    updateSaveStatus("prefs");
  };
  const renderSettings = () => {
    if (state.tour) { $("#view-settings").innerHTML = `${heading("Настройки")}<section class="card">${empty("Настройки сохраняются в аккаунте", "Для источников данных, уведомлений и личных предпочтений войдите в OMNICIO.", "login", "Войти", "settings", true)}</section>`; return; }
    const prefs = state.prefs.draft;
    const preferences = prefs ? `<form id="preferences-form"><section class="card"><div class="card-header"><h2>Оформление и приватность</h2><span class="save-status" data-save-status="prefs"></span></div><div class="field-grid">${select("theme", "Тема", [["system", "Как на устройстве"], ["dark", "Тёмная"], ["light", "Светлая"]], prefs.theme)}${select("locale", "Формат чисел и дат", [["ru", "Русский · 1 234,56"], ["en", "English · 1,234.56"]], prefs.locale, "Меняется только формат чисел и дат. Язык интерфейса — русский.")}</div>${U.switchControl("mask_balances", "Скрывать личные суммы", "Маскирует баланс, суммы целей и персональные графики на экране.", prefs.mask_balances)}</section><section class="card section-gap"><h2 class="panel-title">Уведомления в кабинете</h2>${U.switchControl("notify_portfolio", "Портфель", "Изменения и состояния подключённого счёта.", prefs.notifications.portfolio)}${U.switchControl("notify_payments", "Выплаты", "Подтверждённые купоны, дивиденды и другие поступления.", prefs.notifications.payments)}${U.switchControl("notify_goals", "Цели", "Прогресс и события ваших целей.", prefs.notifications.goals)}${U.switchControl("notify_system", "Система", "Подключение данных и важные состояния сервиса.", prefs.notifications.system)}<p class="notice">Настройки управляют событиями внутри OMNICIO. Внешняя доставка email, SMS и push пока не подключена.</p><div class="field-grid section-gap">${select("digest_frequency", "Дайджест в кабинете", [["off", "Выключен"], ["daily", "За день"], ["weekly", "За неделю"]], prefs.digest_frequency)}${select("quiet_timezone", "Часовой пояс тихих часов", [["Europe/Moscow", "Москва · UTC+3"], ["Etc/UTC", "UTC"]], prefs.quiet_hours.timezone)}</div>${U.switchControl("quiet_enabled", "Тихие часы", "События остаются в ленте, но не выделяются как новые уведомления в заданное время.", prefs.quiet_hours.enabled)}<div class="field-grid">${field({name: "quiet_start", label: "Начало", type: "time", value: prefs.quiet_hours.start, required: true})}${field({name: "quiet_end", label: "Конец", type: "time", value: prefs.quiet_hours.end, required: true})}</div><div class="form-actions"><button class="button primary" type="submit">Сохранить настройки</button><span class="save-status" data-save-status="prefs"></span></div>${saveErrorHTML("prefs")}</section></form>` : `<section class="card">${state.errors.preferences || state.errors.workspace ? dataError(state.errors.preferences ? "preferences" : "workspace") : U.loading("Загружаем сохранённые настройки…")}</section>`;
    $("#view-settings").innerHTML = `${heading("Настройки", "Источники, оформление и события — под вашим контролем", button("Обновить", "refresh", {small: true}))}<div class="settings-layout"><div>${preferences}</div><div><section class="card" id="broker-settings"><h2 class="panel-title">Подключение T-Invest</h2>${brokerSettingsHTML()}</section><section class="card section-gap"><h2 class="panel-title">Персональный ИИ</h2><p class="fine-print">Статус и интерфейс ИИ находятся в отдельном разделе. Переписка текущего сеанса хранится только в памяти вкладки.</p>${button("Открыть ИИ-помощника", "assistant", {route: true, small: true})}</section><section class="card section-gap"><h2 class="panel-title">О приложении</h2>${infoRows([["Версия", $("[data-release-version]").textContent], ["Сборка", window.OMNICIO_RELEASE?.build || "Не получена"], ["Язык интерфейса", "Русский"]])}<div class="form-actions">${button("Условия использования", "legal", {small: true})}${button("Мой профиль", "profile", {route: true, small: true})}</div></section></div></div>`;
    updateSaveStatus("prefs");
  };
  const brokerSettingsHTML = () => {
    const connection = state.data.connection;
    if (!connection) return state.errors.connection ? dataError("connection") : U.loading("Проверяем подключение…");
    if (connection.connected) return `<div class="connection-state"><span class="provider-mark">T</span><div><strong>${esc(connection.account_name || "Счёт T-Invest")}</strong><small>${connection.environment === "sandbox" ? "Тестовая среда" : "Основной счёт"}</small></div><span class="status-dot"></span></div>${infoRows([["ID счёта", connection.account_id], ["Проверен", connection.verified_at ? `${date(connection.verified_at, true)} МСК` : "—"]])}<p class="fine-print section-gap">Токен хранится на сервере и не возвращается в браузер. Для замены счёта сначала отключите текущее подключение.</p><div class="form-actions">${button("Обновить данные", "refresh", {small: true})}${button("Отключить", "disconnect-start", {small: true})}</div>`;
    return `<p class="fine-print">Добавьте личный токен API T-Invest. Проверка покажет доступные счета; затем вы явно выберете нужный.</p><form id="broker-form" class="connection-steps"><label class="field"><span>API-токен ${help("API-токен", "Создайте токен в личном кабинете T-Invest для чтения данных. Токен вводится только после входа в OMNICIO, проверяется сервером и хранится зашифрованным. Не передавайте его в переписке.")}</span><input type="password" name="credential" autocomplete="off" minlength="20" maxlength="4096" required placeholder="Вставьте токен" spellcheck="false"></label>${select("environment", "Среда источника", [["prod", "Основной счёт"], ["sandbox", "Тестовая среда"]], "prod")}<label class="check-field"><input type="checkbox" name="accept_personal_terms" required><span>Подтверждаю доступ к своим данным на условиях <a href="/legal/terms.html" target="_blank" rel="noopener">использования сервиса</a>.</span></label><button class="button primary" type="submit">Проверить токен</button><div id="broker-accounts"></div><p id="broker-message" class="form-message" role="status"></p></form>`;
  };
  const renderAssistant = () => {
    const status = state.data.assistantStatus;
    const configured = Boolean(status?.configured);
    const chat = state.chat.map((item) => `<article class="chat-message ${item.role === "user" ? "user" : ""}"><small>${item.role === "user" ? "Вы" : "OMNICIO · ИИ"}</small>${esc(item.content)}${item.sources?.length ? `<ul class="source-list">${item.sources.map((source) => `<li>${U.sourceLink(source.url, source.label)}</li>`).join("")}</ul>` : ""}</article>`).join("");
    $("#view-assistant").innerHTML = `${heading("ИИ-помощник", "Объяснения, контекст портфеля и ваши вопросы", button("Проверить подключение", "refresh", {small: true}))}<div class="assistant-layout"><section class="card chat-card"><div class="assistant-status">${icon("assistant")}<strong>Персональный помощник</strong><span class="chip">${configured ? "Подключён" : "Не подключён"}</span>${configured ? `<span class="fine-print">${esc(status.model)}</span>` : ""}</div><div id="chat-messages" class="chat-messages" role="log" aria-label="Переписка с ИИ">${chat || empty(configured ? "Что вы хотите понять?" : "Подключите ИИ-провайдера", configured ? "Задайте вопрос о понятиях или выберите контекст своего портфеля." : "Интерфейс готов к работе. Ответы появятся после настройки настоящего провайдера на сервере.", "", "", "assistant", true)}${state.assistantBusy ? U.loading("Помощник готовит ответ…") : ""}</div><form id="assistant-form"><div class="assistant-context">${select("context", "Контекст вопроса", [["general", "Общий вопрос"], ["portfolio", "Данные моего портфеля"]], "general")}<p class="fine-print">Контекст портфеля отправляется только по вашему выбору. Переписка доступна до перезагрузки вкладки и очищается при выходе.</p></div><div class="chat-compose"><textarea name="message" aria-label="Сообщение помощнику" maxlength="4000" required placeholder="Задайте свой вопрос…"${!configured || state.assistantBusy || state.tour ? " disabled" : ""}></textarea><button class="button primary" type="submit" aria-label="Отправить сообщение"${!configured || state.assistantBusy || state.tour ? " disabled" : ""}>${icon("arrow")}<span>Отправить</span></button></div><p id="assistant-message" class="form-message chat-form-message" role="status"></p></form>${dataError("assistantStatus")}</section><aside class="card assistant-side"><h2 class="panel-title">Начать с вопроса</h2><div class="assistant-prompts">${["Как читать структуру моего портфеля?", "Что означает просадка?", "Какие данные нужны для оценки стратегии?"].map((text) => `<button class="button secondary" data-chat-prompt="${esc(text)}"${!configured ? " disabled" : ""}>${esc(text)}</button>`).join("")}</div><p class="section-gap">ИИ помогает разбираться в данных. Его ответ не подтверждает цену, результат расчёта или исполнение сделки.</p>${state.chat.length ? button("Очистить переписку", "chat-clear", {small: true, extra: state.assistantBusy ? "disabled" : ""}) : ""}</aside></div>`;
  };
  const sendAssistant = async (form) => {
    if (!requireUser() || state.assistantBusy || !state.data.assistantStatus?.configured) return;
    const message = form.elements.message.value.trim(); if (!message) return;
    const context = form.elements.context.value;
    const history = state.chat.slice(-20).map(({role, content}) => ({role, content}));
    while (history.reduce((sum, item) => sum + item.content.length, 0) > 24000) history.shift();
    const generation = state.generation; state.chat.push({role: "user", content: message}); state.assistantBusy = true; renderAssistant();
    try {
      const result = await api("/api/assistant/messages", {method: "POST", timeout: 120000, body: {message, context, history}});
      if (generation !== state.generation) return;
      if (typeof result.reply !== "string" || !result.reply.trim()) throw Object.assign(new Error("invalid_server_response"), {status: 502});
      state.chat.push({role: "assistant", content: result.reply, sources: result.sources || []}); state.assistantBusy = false;
      if (state.view === "assistant") { renderAssistant(); $("#chat-messages").scrollTop = $("#chat-messages").scrollHeight; }
    } catch (error) {
      if (generation !== state.generation || isCancelled(error)) return;
      state.assistantBusy = false;
      if (state.view === "assistant") { renderAssistant(); showMessage($("#assistant-message"), humanError(error), true); }
      else toast(humanError(error), true);
    }
  };
  const renderCurrent = () => {
    if (state.locked || (!state.user && !state.tour)) return;
    updateIdentity(); renderConnectionBanner();
    const renderers = {home: renderHome, portfolio: renderPortfolio, market: renderMarket, strategies: renderStrategies, assistant: renderAssistant, goals: renderGoals, analytics: renderAnalytics, events: renderEvents, profile: renderProfile, settings: renderSettings, asset: renderAsset, search: renderSearch};
    renderers[state.view]?.(); U.bindCharts($(`#view-${state.view}`));
  };
  const renderPublicCatalog = (catalog) => {
    const target = $("#public-strategy-list");
    if (!catalog?.presets) { target.innerHTML = '<p class="muted">Каталог временно не загрузился. Повторите открытие страницы.</p>'; return; }
    target.innerHTML = catalog.presets.map((item) => { const [symbol] = strategyIcons[item.id] || ["strategies"]; return `<button class="public-strategy-card" data-public-strategy="${esc(item.id)}">${icon(symbol)}<strong>${esc(item.title)}</strong><small>${esc(strategyTaglines[item.id] || item.description)}</small></button>`; }).join("");
  };
  const renderAuthConfig = () => {
    const config = state.config;
    const vkEnabled = Boolean(config?.login_enabled);
    const tidEnabled = Boolean(config?.tid_enabled);
    $("#tid-login").disabled = !tidEnabled; $("#vkid-login").disabled = !vkEnabled;
    $("#tid-state").textContent = tidEnabled ? "" : "T-ID ещё не подключён на сервере";
    $("#vkid-state").textContent = vkEnabled ? "" : "VK ID временно недоступен";
    const registration = !config ? "Не удалось проверить доступность регистрации." : config.registration_enabled ? "Новый аккаунт создаётся после подтверждения личности, если регистрация доступна." : "Регистрация новых аккаунтов сейчас закрыта. Существующие пользователи могут войти.";
    $("#registration-state").textContent = registration;
    $("#public-access-status").textContent = registration;
  };
  function openAuth(mode = "login", linkCurrent = false) {
    closeDrawer(false); state.authMode = mode; state.authLink = Boolean(linkCurrent && state.user);
    for (const dialog of $$("dialog[open]")) if (dialog.id !== "auth-dialog" && dialog.id !== "session-dialog") dialog.close();
    $("#auth-title").innerHTML = state.authLink ? "Подключите ещё один<br>способ входа" : mode === "register" ? "Добро пожаловать!<br>Создайте аккаунт" : "Добро пожаловать!<br>Войдите в аккаунт";
    $("#auth-explanation").textContent = state.authLink ? "Подтвердите вторую учётную запись у провайдера. Она будет связана с текущим профилем OMNICIO." : mode === "register" ? "Подтвердите личность через T-ID или VK ID. Создание аккаунта зависит от доступности регистрации." : "Используйте свой T-ID или VK ID, чтобы открыть личный кабинет.";
    for (const tab of $$("[data-auth-mode]")) tab.setAttribute("aria-selected", String(tab.dataset.authMode === mode));
    renderAuthConfig(); showMessage($("#auth-message"), "");
    if (!$("#auth-dialog").open) $("#auth-dialog").showModal();
  }
  const startAuth = async (form, provider) => {
    if (!["tid", "vkid"].includes(provider) || !form.reportValidity()) return;
    const payload = Object.fromEntries(["accept_privacy", "accept_personal_data", "accept_terms", "confirm_age_18"].map((key) => [key, form.elements[key].checked]));
    if (!Object.values(payload).every(Boolean)) return;
    if (state.authLink) payload.link_current_account = true;
    $("#tid-login").disabled = true; $("#vkid-login").disabled = true;
    showMessage($("#auth-message"), "Переходим к подтверждению личности…");
    try {
      const result = await api(`/api/auth/${provider}/start`, {method: "POST", body: payload});
      const url = new URL(result.authorize_url);
      const host = provider === "tid" ? "id.tbank.ru" : "id.vk.ru";
      if (url.protocol !== "https:" || url.hostname !== host || (url.port && url.port !== "443") || url.username || url.password) throw new Error("invalid_authorization_url");
      location.assign(url.href);
    } catch (error) {
      if (!isCancelled(error)) { renderAuthConfig(); showMessage($("#auth-message"), error?.message === "invalid_authorization_url" ? "Адрес авторизации не прошёл проверку. Вход остановлен." : humanError(error), true); }
    }
  };
  const verifySession = async () => {
    if (!state.user || state.locked || state.verifying || document.visibilityState !== "visible") return;
    state.verifying = true;
    try { await api("/api/me"); } catch (error) { if (!isCancelled(error) && error?.status !== 401) { const banner = $("#connection-banner"); banner.hidden = false; banner.textContent = "Не удалось повторно проверить сессию. Изменения будут подтверждаться сервером."; } }
    finally { state.verifying = false; }
  };
  const callbackMessage = () => {
    const params = new URLSearchParams(location.search); const code = params.get("auth_error");
    if (params.has("auth") || code) history.replaceState(history.state, "", `${location.pathname}${location.hash}`);
    if (!code) return;
    const labels = {registration: "Регистрация новых аккаунтов сейчас закрыта.", capacity: "Свободных мест для новых аккаунтов пока нет.", provider: "Провайдер входа временно недоступен. Повторите позже.", account: "Этот аккаунт сейчас недоступен.", identity_conflict: "Этот способ входа уже связан с другим аккаунтом.", link_conflict: "Эта учётная запись уже привязана к другому профилю."};
    openAuth(); showMessage($("#auth-message"), labels[code] || "Авторизация не завершена. Попробуйте ещё раз.", true);
  };
  const bootstrap = async () => {
    const generation = state.generation;
    const results = await Promise.allSettled([api("/api/auth/config", {bootstrap: true}), api("/api/me", {bootstrap: true}), api("/api/strategy/catalog", {bootstrap: true})]);
    if (generation !== state.generation) return;
    if (results[0].status === "fulfilled") state.config = results[0].value;
    renderAuthConfig();
    if (results[2].status === "fulfilled") { state.data.catalog = results[2].value; renderPublicCatalog(results[2].value); }
    else renderPublicCatalog(null);
    if (results[1].status === "fulfilled" && /^\d{9}$/.test(results[1].value.public_id)) {
      state.locked = false; state.user = results[1].value; showApp();
    } else if (!state.tour) {
      $("#public-site").hidden = false; $("#app-shell").hidden = true;
      if (results[1].status === "rejected" && results[1].reason?.status !== 401) $("#public-access-status").textContent = "Сессию не удалось проверить. Повторите вход после восстановления соединения.";
    }
    callbackMessage();
  };
  const resetBrokerPreview = () => {
    state.brokerPreview = null; state.brokerSequence = (state.brokerSequence || 0) + 1;
    const container = $("#broker-accounts"); if (container) container.replaceChildren();
  };
  const previewBroker = async (form) => {
    if (!requireUser() || !form.reportValidity()) return;
    resetBrokerPreview();
    const credential = form.elements.credential.value.trim(); const environment = form.elements.environment.value;
    const sequence = state.brokerSequence; const generation = state.generation; const submit = form.querySelector("[type=submit]");
    submit.disabled = true; showMessage($("#broker-message"), "Проверяем токен и список счетов…");
    try {
      const result = await api("/api/broker/tbank/accounts", {method: "POST", timeout: 45000, body: {credential, environment, accept_personal_terms: true}});
      if (generation !== state.generation || sequence !== state.brokerSequence || !form.isConnected || credential !== form.elements.credential.value.trim() || environment !== form.elements.environment.value) return;
      const accounts = Array.isArray(result.accounts) ? result.accounts : [];
      state.brokerPreview = {credential, environment, accounts};
      $("#broker-accounts").innerHTML = accounts.length ? `${select("account_id", "Ваш счёт", [["", "Выберите счёт"], ...accounts.map((item) => [item.id, `${item.name} · ${item.id}`])], "")}<div class="form-actions">${button("Подключить выбранный счёт", "broker-connect", {primary: true})}</div>` : '<p class="notice">У токена нет доступных счетов.</p>';
      showMessage($("#broker-message"), accounts.length ? "Токен проверен. Выберите счёт для подключения." : "Доступные счета не получены.", !accounts.length);
    } catch (error) { if (!isCancelled(error)) showMessage($("#broker-message"), humanError(error), true); }
    finally { if (form.isConnected && generation === state.generation) submit.disabled = false; }
  };
  const connectBroker = async (control) => {
    if (!requireUser()) return;
    const form = $("#broker-form"); const preview = state.brokerPreview;
    if (!form || !preview || preview.credential !== form.elements.credential.value.trim() || preview.environment !== form.elements.environment.value || !form.elements.accept_personal_terms.checked) { resetBrokerPreview(); showMessage($("#broker-message"), "Данные изменились. Проверьте токен повторно.", true); return; }
    const accountId = form.elements.account_id?.value;
    if (!preview.accounts.some((item) => item.id === accountId)) { showMessage($("#broker-message"), "Выберите один из доступных счетов.", true); return; }
    control.disabled = true; const generation = state.generation;
    let connected = null;
    try {
      connected = await api("/api/broker/tbank", {method: "PUT", timeout: 45000, body: {credential: preview.credential, environment: preview.environment, account_id: accountId, accept_personal_terms: true}});
    } catch (error) {
      if (isCancelled(error) || generation !== state.generation) return;
      if (!error.status || error.status >= 500) {
        try { const current = await api("/api/broker/tbank"); if (current.connected && current.account_id === accountId && current.environment === preview.environment) connected = current; } catch (readError) { if (isCancelled(readError)) return; }
      }
      if (!connected) { showMessage($("#broker-message"), humanError(error), true); control.disabled = false; return; }
    }
    if (generation !== state.generation) return;
    form.elements.credential.value = ""; resetBrokerPreview(); state.data.connection = connected;
    delete state.data.workspace; delete state.data.visualization; delete state.data.analysis;
    toast("Счёт подключён. Загружаем реальные данные."); renderSettings();
    await loadResource("workspace", "/api/workspace", {force: true});
    if (generation === state.generation && state.view === "settings") renderCurrent();
  };
  const clearBrokerState = async () => {
    const user = state.user; const config = state.config; clearPrivateState(); state.user = user; state.config = config; state.locked = false; state.tour = false; showApp();
  };
  const hasPending = () => state.prefs.dirty || state.prefs.busy || state.strategy.dirty || state.strategy.busy;
  const logout = async () => {
    if (!state.user) { state.tour = false; clearPrivateState(); $("#app-shell").hidden = true; $("#public-site").hidden = false; return; }
    if (hasPending() && !window.confirm("Есть несохранённые изменения. Выйти и закрыть их?")) return;
    try { await api("/api/auth/logout", {method: "POST"}); clearPrivateState(); state.tour = false; state.locked = false; $("#app-shell").hidden = true; $("#public-site").hidden = false; history.replaceState(null, "", "/"); sessionChannel?.postMessage({type: "session-cleared"}); await bootstrap(); }
    catch (error) { if (!isCancelled(error)) toast(humanError(error), true); }
  };
  const showAccountDeletion = () => {
    if (!requireUser()) return;
    openDialog("Удаление аккаунта", `<p class="help-copy">Для удаления введите ID текущего профиля: <strong>${esc(state.user.public_id)}</strong>.</p><form id="delete-account-form">${field({name: "confirm_public_id", label: "ID вашего профиля", required: true})}<label class="check-field section-gap"><input type="checkbox" name="confirm_irreversible" required><span>Подтверждаю удаление профиля и понимаю, что восстановление через интерфейс недоступно.</span></label><div class="form-actions"><button class="button danger" type="submit">Удалить аккаунт</button><button class="button secondary" type="button" data-close-dialog>Отмена</button></div><p id="delete-account-message" class="form-message" role="status"></p></form>`);
  };
  const toggleWatch = (control) => {
    const uid = control.dataset.watch;
    if (!uid) return;
    const updated = editPreferences((document) => {
      const existing = document.watchlist.findIndex((item) => item.instrument_uid === uid);
      if (existing >= 0) document.watchlist.splice(existing, 1);
      else document.watchlist.push({instrument_uid: uid, ticker: control.dataset.watchTicker || "", name: control.dataset.watchName || uid});
    });
    if (updated) {
      for (const element of $$("[data-watch]")) if (element.dataset.watch === uid) { element.setAttribute("aria-pressed", String(isWatched(uid))); element.setAttribute("aria-label", isWatched(uid) ? "Удалить из избранного" : "Добавить в избранное"); }
      if (state.view === "market") { renderMarket(); U.bindCharts($("#view-market")); }
    }
  };
  const updateStrategyField = (input) => {
    const slot = state.strategy; if (!slot.draft || slot.error?.status === 409) return;
    const path = input.name.split(".").slice(1);
    if (path.length < 2 || path.length > 3 || !["profile", "policy", "rules"].includes(path[0])) return;
    let parent = slot.draft;
    for (const key of path.slice(0, -1)) { if (!Object.hasOwn(parent, key) || !parent[key] || typeof parent[key] !== "object") return; parent = parent[key]; }
    const key = path.at(-1); if (!Object.hasOwn(parent, key)) return;
    const value = input.type === "checkbox" ? input.checked : input.value === "" ? null : input.value;
    if (parent[key] === value) return; parent[key] = value; documentChanged();
  };
  const stepField = (control) => {
    const input = document.getElementsByName(control.dataset.stepField)[0];
    if (!input || input.disabled) return;
    const value = input.value;
    if (value === "") { input.focus(); toast("Сначала укажите исходное значение. Неизвестная сумма не заменяется нулём."); return; }
    if (!/^\d+(\.\d{1,8})?$/.test(value)) { input.focus(); return; }
    const [whole, fraction = ""] = value.split("."); const precise = BigInt(whole) * 100000000n + BigInt(fraction.padEnd(8, "0"));
    const amount = input.name.endsWith("_rub") ? 1000n : input.name.endsWith("horizon_months") ? 12n : 1n;
    const adjusted = precise + BigInt(control.dataset.stepDirection) * amount * 100000000n;
    const maximum = BigInt(Math.trunc(Number(input.max || "1000000000000"))) * 100000000n;
    const minimum = BigInt(input.min || "0") * 100000000n;
    const bounded = adjusted < minimum ? minimum : adjusted > maximum ? maximum : adjusted;
    const decimal = String(bounded % 100000000n).padStart(8, "0").replace(/0+$/, "");
    input.value = `${bounded / 100000000n}${decimal ? `.${decimal}` : ""}`; input.dispatchEvent(new Event("input", {bubbles: true}));
  };
  const runResearch = async (form) => {
    if (!requireUser() || !form.reportValidity()) return;
    const slot = state.strategy;
    if (!slot.server || slot.dirty || slot.busy || slot.error) { showMessage($("#research-message"), "Дождитесь сохранения выбранной стратегии.", true); return; }
    const from = form.elements.from_at.value; const to = form.elements.to_at.value;
    if (from >= to) { showMessage($("#research-message"), "Конец периода должен быть позже начала.", true); return; }
    const generation = state.generation; const revision = slot.revision; const version = slot.server.version;
    state.loading.add("research"); slot.research = null; const submit = form.querySelector("[type=submit]"); submit.disabled = true;
    $("#strategy-research").innerHTML = renderResearch(); showMessage($("#research-message"), "");
    try {
      const result = await api("/api/profile/strategy/research", {method: "POST", timeout: 120000, body: {expected_public_id: state.user.public_id, expected_version: version, from_at: `${from}T00:00:00Z`, to_at: `${to}T23:59:59Z`, initial_capital_rub: form.elements.initial_capital_rub.value, commission_bps: form.elements.commission_bps.value, slippage_bps: form.elements.slippage_bps.value}});
      if (generation !== state.generation || revision !== slot.revision || slot.server?.version !== version) return;
      slot.research = result;
    } catch (error) { if (generation === state.generation && !isCancelled(error)) showMessage($("#research-message"), humanError(error), true); }
    finally { if (generation === state.generation) { state.loading.delete("research"); if (submit.isConnected) submit.disabled = false; const target = $("#strategy-research"); if (target) { target.innerHTML = renderResearch(); U.bindCharts(target); } } }
  };
  const actions = {
    login: () => openAuth(), register: () => openAuth("register"), tour: () => showApp(true),
    "leave-tour": () => { clearPrivateState(); state.tour = false; $("#app-shell").hidden = true; $("#public-site").hidden = false; history.replaceState(null, "", "#welcome"); void bootstrap(); },
    connect: () => { if (requireUser()) { navigate("settings"); window.setTimeout(() => $("#broker-settings")?.scrollIntoView({block: "start", behavior: "smooth"}), 100); } },
    refresh: async () => {
      if (hasPending()) { toast("Сначала завершите сохранение или загрузите серверную версию через сообщение об ошибке.", true); return; }
      await loadForView(state.view, state.route, true);
    },
    language: () => openDialog("Язык интерфейса", '<p class="help-copy">Русский</p><p class="fine-print">Формат чисел и дат можно изменить в настройках личного аккаунта.</p>'),
    premium: () => openDialog("Возможности вашего плана", `<p class="help-copy">Сейчас доступен личный кабинет OMNICIO: портфель, стратегии, цели, аналитика, события и настройки.</p><p class="notice">Платный тариф и приём оплаты ещё не подключены. Интерфейс не принимает платёжные данные.</p><div class="form-actions">${button("Открыть настройки", "settings", {route: true, primary: true})}</div>`),
    legal: () => openDialog("Документы", '<ul class="source-list"><li><a href="/legal/terms.html" target="_blank" rel="noopener">Условия использования</a></li><li><a href="/legal/privacy.html" target="_blank" rel="noopener">Политика конфиденциальности</a></li><li><a href="/legal/consent.html" target="_blank" rel="noopener">Обработка персональных данных</a></li></ul>'),
    "goal-create": () => openGoal(), "goal-reconcile": async () => { $("#workspace-dialog").close(); navigate("goals"); await loadForView("goals", {}, true); },
    "events-read-all": () => markEvents((state.data.events?.items || []).filter((item) => !item.read_at).map((item) => item.id)),
    "strategy-custom": customizeStrategy,
    "strategy-catalog": () => { $(".strategy-catalog")?.scrollIntoView({block: "start", behavior: "smooth"}); },
    "assess-strategy": assessStrategy,
    "strategy-reload": () => reloadVersioned("strategy"), "strategy-discard": () => { $("#workspace-dialog").close(); return reloadVersioned("strategy", true); }, "strategy-retry": () => retryVersioned("strategy"),
    "prefs-reload": () => reloadVersioned("prefs"), "prefs-discard": () => { $("#workspace-dialog").close(); return reloadVersioned("prefs", true); }, "prefs-retry": () => retryVersioned("prefs"),
    "broker-connect": connectBroker,
    "disconnect-start": () => {
      if (!requireUser()) return;
      if (hasPending()) { toast("Перед отключением завершите сохранение настроек.", true); return; }
      openDialog("Отключить T-Invest?", `<p class="help-copy">Токен подключения будет удалён. Новые данные счёта перестанут поступать. Для восстановления потребуется повторное подключение.</p><div class="form-actions">${button("Отключить источник", "disconnect-confirm", {primary: true})}<button class="button secondary" data-close-dialog>Отмена</button></div><p id="disconnect-message" class="form-message" role="status"></p>`);
    },
    "disconnect-confirm": async (control) => {
      control.disabled = true;
      try { await api("/api/broker/tbank", {method: "DELETE"}); await clearBrokerState(); toast("Источник отключён."); }
      catch (error) { if (!isCancelled(error)) { showMessage($("#disconnect-message"), humanError(error), true); control.disabled = false; } }
    },
    "asset-refresh": () => state.asset && loadAsset(state.asset.uid, true),
    "asset-back": () => { if (history.state?.view === "asset" && history.length > 1) history.back(); else navigate("market"); },
    "copy-profile": async () => { if (!state.user) return; try { await navigator.clipboard.writeText(state.user.public_id); toast("ID профиля скопирован."); } catch { openDialog("ID профиля", `<p class="help-copy">${esc(state.user.public_id)}</p>`); } },
    "delete-account": showAccountDeletion, logout,
    "chat-clear": () => { state.chat = []; renderAssistant(); },
    "link-identity": () => openAuth("login", true),
  };
  document.addEventListener("click", async (event) => {
    const control = event.target.closest("button,a[data-route],a[data-public-open]");
    if (!control || control.disabled) return;
    try {
      if (control.hasAttribute("data-close-dialog")) { event.preventDefault(); control.closest("dialog")?.close(); return; }
      if (control.dataset.help) { event.preventDefault(); $("#help-title").textContent = control.dataset.helpTitle; $("#help-content").textContent = control.dataset.help; $("#help-dialog").showModal(); return; }
      if (control.dataset.themeChoice) {
        event.preventDefault(); const choice = control.dataset.themeChoice;
        if (state.user && !state.tour) { if (editPreferences((document) => { document.theme = choice; })) applyTheme(choice); }
        else applyTheme(choice);
        return;
      }
      if (control.dataset.publicOpen) { event.preventDefault(); showApp(true); navigate(control.dataset.publicOpen); return; }
      if (control.dataset.route) { event.preventDefault(); for (const dialog of $$("dialog[open]")) if (dialog.id !== "session-dialog") dialog.close(); navigate(control.dataset.route); return; }
      if (control.dataset.authMode) { event.preventDefault(); openAuth(control.dataset.authMode, state.authLink); return; }
      if (control.dataset.asset) { event.preventDefault(); state.assetPeriod = "1m"; state.assetTab = "chart"; navigate("asset", {uid: control.dataset.asset}); return; }
      if (control.dataset.assetTab) { event.preventDefault(); state.assetTab = control.dataset.assetTab; renderAsset(); U.bindCharts($("#view-asset")); return; }
      if (control.dataset.watch) { event.preventDefault(); toggleWatch(control); return; }
      if (control.dataset.assetFilter) { event.preventDefault(); state.assetFilter = control.dataset.assetFilter; renderCurrent(); return; }
      if (control.dataset.sort) { event.preventDefault(); if (state.sort === control.dataset.sort) state.sortDirection *= -1; else { state.sort = control.dataset.sort; state.sortDirection = 1; } renderCurrent(); $(`[data-sort="${state.sort}"]`, $(`#view-${state.view}`))?.focus({preventScroll: true}); return; }
      if (control.dataset.period) {
        event.preventDefault(); const scope = control.dataset.periodScope;
        if (scope === "asset") { state.assetPeriod = control.dataset.period; if (state.asset) await loadAsset(state.asset.uid); }
        else { state[`${scope}Period`] = control.dataset.period; renderCurrent(); }
        return;
      }
      if (control.dataset.eventFilter) { event.preventDefault(); state.eventFilter = control.dataset.eventFilter; renderCurrent(); return; }
      if (control.dataset.eventOpen) { event.preventDefault(); openEvent(control.dataset.eventOpen); return; }
      if (control.dataset.eventRead) { event.preventDefault(); await markEvents([control.dataset.eventRead]); return; }
      if (control.dataset.goalEdit) { event.preventDefault(); openGoal(control.dataset.goalEdit); return; }
      if (control.dataset.goalDelete) { event.preventDefault(); confirmGoalDelete(control.dataset.goalDelete); return; }
      if (control.dataset.goalDeleteConfirm) {
        event.preventDefault(); control.disabled = true;
        try { await api(`/api/goals/${safeSegment(control.dataset.goalDeleteConfirm)}`, {method: "DELETE", body: {expected_version: Number(control.dataset.version)}}); $("#workspace-dialog").close(); await loadResource("goals", "/api/goals", {force: true}); renderCurrent(); toast("Цель удалена."); }
        catch (error) { if (!isCancelled(error)) { showMessage($("#goal-delete-message"), humanError(error), true); control.disabled = false; } }
        return;
      }
      if (control.dataset.selectStrategy) { event.preventDefault(); chooseStrategy(control.dataset.selectStrategy); return; }
      if (control.dataset.publicStrategy) {
        event.preventDefault(); const preset = state.data.catalog?.presets?.find((item) => item.id === control.dataset.publicStrategy); if (!preset) return;
        openDialog(preset.title, `<p class="help-copy">${esc(preset.description)}</p><p class="notice">${esc(preset.risk)}</p><p class="fine-print">Параметры подхода можно изменить после входа. Название не является обещанием результата.</p><div class="form-actions">${button("Открыть личный кабинет", "login", {primary: true})}</div>`); return;
      }
      if (control.dataset.stepField) { event.preventDefault(); stepField(control); return; }
      if (control.dataset.chatPrompt) { event.preventDefault(); const input = $("#assistant-form")?.elements.message; if (input && !input.disabled) { input.value = control.dataset.chatPrompt; input.focus(); } return; }
      if (control.dataset.action && actions[control.dataset.action]) { event.preventDefault(); await actions[control.dataset.action](control); }
    } catch (error) { if (!isCancelled(error)) toast(humanError(error), true); }
  });
  document.addEventListener("input", (event) => {
    const input = event.target;
    if (input.dataset.allocation) { updateAllocation(input.dataset.allocation, Number(input.value)); return; }
    if (input.name?.startsWith("strategy.") && input.type !== "checkbox") { updateStrategyField(input); return; }
    if (input.closest("#broker-form") && ["credential", "environment"].includes(input.name)) resetBrokerPreview();
  });
  document.addEventListener("change", async (event) => {
    const input = event.target;
    if (input.name?.startsWith("strategy.")) { updateStrategyField(input); return; }
    if (input.dataset.allocationLock || input.dataset.allocationExclude) {
      const document = state.strategy.draft; if (!document) return;
      const key = input.dataset.allocationLock || input.dataset.allocationExclude;
      const fieldName = input.dataset.allocationLock ? "locked" : "excluded";
      if (input.checked) {
        if (fieldName === "excluded") {
          const next = clone(document); next.locked = next.locked.filter((item) => item !== key);
          if (!redistribute(next, key, 0)) { input.checked = false; toast("Освободите другую долю, прежде чем исключать этот класс."); return; }
          document.allocation = next.allocation; document.locked = next.locked;
        }
        if (!document[fieldName].includes(key)) document[fieldName].push(key);
      } else document[fieldName] = document[fieldName].filter((item) => item !== key);
      documentChanged(); renderStrategies(); return;
    }
    if (input.closest("#goal-form") && ["kind", "progress_source"].includes(input.name)) { updateGoalFields(input.name === "kind"); return; }
    if (input.closest("#broker-form") && input.name === "environment") { resetBrokerPreview(); return; }
    if (["cbr_currency", "cbr_period"].includes(input.name)) {
      if (input.name === "cbr_currency") state.cbrCurrency = input.value; else state.cbrPeriod = input.value;
      await loadResource("marketReference", `/api/public/market-reference?currency=${state.cbrCurrency}&period=${state.cbrPeriod}`, {force: true});
      if (state.view === "market") { renderMarket(); U.bindCharts($("#view-market")); }
    }
  });
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.id || !["auth-form", "global-search-form", "strategy-form", "goal-form", "profile-form", "preferences-form", "broker-form", "assistant-form", "research-form", "delete-account-form"].includes(form.id)) return;
    event.preventDefault();
    try {
      if (form.id === "auth-form") { await startAuth(form, event.submitter?.value || "vkid"); return; }
      if (form.id === "global-search-form") { navigate("search", {q: form.elements.q.value.trim().slice(0, 64)}); return; }
      if (form.id === "strategy-form") { await saveVersioned("strategy"); return; }
      if (form.id === "goal-form") { await saveGoal(form); return; }
      if (form.id === "profile-form") { const value = form.elements.display_name.value.trim(); if (value.length > 80) { toast("Имя должно быть не длиннее 80 символов.", true); return; } editPreferences((document) => { document.display_name = value; }); return; }
      if (form.id === "preferences-form") {
        if (!form.reportValidity()) return;
        const controls = form.elements;
        const changed = editPreferences((document) => { document.theme = controls.theme.value; document.locale = controls.locale.value; document.mask_balances = controls.mask_balances.checked; document.digest_frequency = controls.digest_frequency.value; document.quiet_hours = {enabled: controls.quiet_enabled.checked, start: controls.quiet_start.value, end: controls.quiet_end.value, timezone: controls.quiet_timezone.value}; for (const key of ["portfolio", "payments", "goals", "system"]) document.notifications[key] = controls[`notify_${key}`].checked; });
        if (changed) applyTheme(controls.theme.value); return;
      }
      if (form.id === "broker-form") { await previewBroker(form); return; }
      if (form.id === "assistant-form") { await sendAssistant(form); return; }
      if (form.id === "research-form") { await runResearch(form); return; }
      if (form.id === "delete-account-form") {
        if (!requireUser() || !form.reportValidity()) return;
        const confirmation = form.elements.confirm_public_id.value.trim();
        if (confirmation !== state.user.public_id) { showMessage($("#delete-account-message"), "ID не совпадает с текущим профилем.", true); return; }
        const submit = form.querySelector("[type=submit]"); submit.disabled = true;
        try { await api("/api/account/delete", {method: "POST", body: {confirm_public_id: confirmation, confirm_irreversible: form.elements.confirm_irreversible.checked}}); clearPrivateState(); state.tour = false; state.locked = false; $("#app-shell").hidden = true; $("#public-site").hidden = false; sessionChannel?.postMessage({type: "session-cleared"}); toast("Аккаунт удалён."); await bootstrap(); }
        catch (error) { if (!isCancelled(error)) { showMessage($("#delete-account-message"), humanError(error), true); submit.disabled = false; } }
      }
    } catch (error) { if (!isCancelled(error)) toast(humanError(error), true); }
  });
  $("#app-menu-toggle").addEventListener("click", openDrawer);
  $("#drawer-close").addEventListener("click", () => closeDrawer());
  $("#drawer-backdrop").addEventListener("click", () => closeDrawer());
  $("#notifications-button").addEventListener("click", () => navigate("events"));
  $("#profile-button").addEventListener("click", () => { const menu = $("#profile-menu"); menu.hidden = !menu.hidden; $("#profile-button").setAttribute("aria-expanded", String(!menu.hidden)); if (!menu.hidden) $("[role=menuitem]", menu).focus(); });
  $("#public-menu-toggle").addEventListener("click", () => { const nav = $(".public-nav"); const expanded = nav.dataset.open !== "true"; nav.dataset.open = String(expanded); $("#public-menu-toggle").setAttribute("aria-expanded", String(expanded)); });
  $(".public-nav").addEventListener("click", (event) => { if (event.target.closest("a")) { delete $(".public-nav").dataset.open; $("#public-menu-toggle").setAttribute("aria-expanded", "false"); } });
  $("#session-reload").addEventListener("click", async () => { $("#session-dialog").close(); state.locked = false; await bootstrap(); });
  $("#session-dialog").addEventListener("cancel", (event) => event.preventDefault());
  $("#auth-dialog").addEventListener("close", () => { $("#auth-form").reset(); });
  document.addEventListener("pointerdown", (event) => { if (!event.target.closest("#profile-menu,#profile-button")) { $("#profile-menu").hidden = true; $("#profile-button").setAttribute("aria-expanded", "false"); } });
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k" && !$("#app-shell").hidden) { event.preventDefault(); $("#global-search").focus(); }
    if (event.key === "Escape") {
      if (!$("#drawer-backdrop").hidden) { event.preventDefault(); closeDrawer(); }
      if (!$("#profile-menu").hidden) { $("#profile-menu").hidden = true; $("#profile-button").setAttribute("aria-expanded", "false"); $("#profile-button").focus(); }
      delete $(".public-nav").dataset.open; $("#public-menu-toggle").setAttribute("aria-expanded", "false");
    }
    if (!$("#drawer-backdrop").hidden && event.key === "Tab") {
      const focusable = $$("a[href],button:not([disabled])", $("#app-sidebar")).filter((element) => element.getClientRects().length);
      const first = focusable[0]; const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    const tab = event.target.closest('[role="tab"]');
    if (tab && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      const tabs = $$('[role="tab"]', tab.closest('[role="tablist"]')); const index = tabs.indexOf(tab);
      const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      event.preventDefault(); tabs[next].focus(); tabs[next].click();
    }
    if (!$("#profile-menu").hidden && ["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) {
      const items = $$('[role="menuitem"]', $("#profile-menu")); const index = items.indexOf(document.activeElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      event.preventDefault(); items[next].focus();
    }
  });
  const historyNavigation = () => {
    if (!state.user && !state.tour) return;
    const route = parseRoute();
    if (route.view !== state.view || route.uid !== (state.route.uid || "") || route.q !== (state.route.q || "")) navigate(route.view, route, {fromHistory: true});
  };
  window.addEventListener("popstate", historyNavigation); window.addEventListener("hashchange", historyNavigation);
  window.addEventListener("focus", () => { void verifySession(); });
  window.addEventListener("pageshow", (event) => { if (event.persisted) void verifySession(); });
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") void verifySession(); });
  window.addEventListener("beforeunload", (event) => { if (hasPending()) { event.preventDefault(); event.returnValue = ""; } });
  window.addEventListener("pagehide", () => { for (const controller of state.requests) controller.abort(); resetBrokerPreview(); const input = $('#broker-form [name="credential"]'); if (input) input.value = ""; });
  window.addEventListener("resize", () => { if (window.innerWidth > 960 && !$("#drawer-backdrop").hidden) closeDrawer(false); $("#app-sidebar").inert = window.innerWidth <= 960 && $("#drawer-backdrop").hidden; });
  window.addEventListener("offline", () => toast("Нет соединения. Новые данные и изменения требуют сети.", true));
  window.addEventListener("online", () => { toast("Соединение восстановлено. Обновите данные, чтобы проверить состояние."); void verifySession(); });
  prefersDark.addEventListener("change", () => { if (themeChoice === "system") applyTheme("system"); });
  let sessionChannel = null;
  try { sessionChannel = new BroadcastChannel("omnicio-session"); sessionChannel.addEventListener("message", (event) => { if (event.data?.type === "session-cleared" && state.user) lockSession("Сессия завершена в другой вкладке. Данные очищены."); }); } catch { /* Server profile preconditions remain authoritative without BroadcastChannel. */ }
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      const build = new URL(document.querySelector('script[src*="app.js"]').src).searchParams.get("build") || "";
      void navigator.serviceWorker.register(`/sw.js?build=${encodeURIComponent(build)}`).catch(() => { /* Network use remains available without offline assets. */ });
    });
  }
  if (window.OMNICIO_RELEASE && /^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$/.test(window.OMNICIO_RELEASE.version)) {
    for (const element of $$("[data-release-version]")) element.textContent = window.OMNICIO_RELEASE.version;
    for (const element of $$("[data-app-build]")) element.textContent = window.OMNICIO_RELEASE.build || "";
  }
  $("#app-sidebar").inert = window.innerWidth <= 960;
  applyTheme(themeChoice); renderNav(); void bootstrap();
})();
