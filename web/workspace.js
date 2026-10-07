"use strict";

/* Shared display primitives. All financial values come from the API. */
(() => {
  "use strict";

  const I = window.OMNICIO_I18N;
  const T = (key, values) => I.t(key, values);
  const H = (key, values) => I.html(key, values);

  const colors = ["#3689ff", "#15c7ce", "#02d59b", "#efa85f", "#ad79f1", "#6ab8de"];
  const navigation = () => ([["home", T("Главная")], ["portfolio", T("Портфель")], ["market", T("Рынок")], ["strategies", T("Стратегии")], ["assistant", T("ИИ-помощник")], ["goals", T("Цели")], ["analytics", T("Аналитика")], ["events", T("События")], ["profile", T("Профиль")], ["settings", T("Настройки")]]);
  const publicPages = Object.freeze(["welcome", "features", "how-it-works", "strategies", "technology", "pricing", "about", "support"]);
  const routeScreens = Object.freeze({
    home: [], portfolio: ["positions", "history", "structure", "income", "operations"],
    market: ["reference", "watchlist", "positions", "news"],
    strategies: ["catalog", "editor", "assessment", "research", "archive", "evidence", "result", "detail", "plan", "executions"],
    assistant: ["connection", "conversation", "history", "memory", "sources"], goals: ["archive", "create", "edit", "plan"],
    analytics: ["history", "performance", "income", "risk"], events: ["detail", "news"],
    profile: ["personal", "identities", "sessions", "plan", "delete"],
    settings: ["appearance", "notifications", "broker", "recovery", "about", "operations", "support"],
    asset: [], search: []
  });
  const routeFields = Object.freeze({uid: "uid", q: "q", event: "event", goal_id: "goal", run: "run", news: "news", news_source: "news_source", preset: "preset", period: "period", tab: "tab", filter: "filter", asset_filter: "assets", event_filter: "events", currency: "currency", reference_period: "reference_period", strategy_pane: "strategy_pane", sort: "sort", direction: "direction", conversation: "conversation", overlay: "overlay"});
  const parseRoute = (hash = "", fallbackMode = "auto") => {
    const [path, query = ""] = String(hash).replace(/^#/, "").split("?");
    const parts = path.split("/").filter(Boolean);
    const explicitMode = ["public", "demo", "account"].includes(parts[0]);
    const mode = explicitMode ? parts.shift() : fallbackMode;
    const alias = {features: "features", "how-it-works": "how-it-works", "public-strategies": "strategies", technology: "technology", pricing: "pricing", about: "about", welcome: "welcome"};
    if (!explicitMode && Object.hasOwn(alias, parts[0])) return {mode: "public", view: alias[parts[0]], screen: ""};
    const view = parts.shift() || (mode === "public" ? "welcome" : "home");
    const result = {mode, view, screen: parts.shift() || "", invalid: parts.length > 0};
    if (mode === "public") result.invalid ||= !publicPages.includes(view) || Boolean(result.screen);
    else result.invalid ||= !Object.hasOwn(routeScreens, view) || Boolean(result.screen && !routeScreens[view]?.includes(result.screen));
    const params = new URLSearchParams(query);
    for (const [field, key] of Object.entries(routeFields)) {
      const value = params.get(key);
      if (value !== null) result[field] = value.slice(0, field === "q" ? 64 : 256);
    }
    return result;
  };
  const routeHash = route => {
    const mode = ["public", "demo", "account"].includes(route.mode) ? route.mode : "account";
    const query = new URLSearchParams();
    for (const [field, key] of Object.entries(routeFields)) if (route[field] !== undefined && route[field] !== null && String(route[field]) !== "") query.set(key, String(route[field]));
    return `#${mode}/${route.view || (mode === "public" ? "welcome" : "home")}${route.screen ? "/" + route.screen : ""}${query.size ? "?" + query.toString() : ""}`;
  };
  const resumeRoute = route => {
    const parsed = parseRoute(routeHash({mode: route.mode, view: route.view, screen: route.screen}));
    if (route.invalid || parsed.invalid) return {mode: "public", view: "welcome", screen: ""};
    const result = {mode: parsed.mode, view: parsed.view, screen: parsed.screen};
    if (["asset", "search"].includes(result.view)) return {...result, view: "market", screen: ""};
    const requiresIdentifier = {goals: ["edit", "plan"], events: ["detail", "news"], strategies: ["detail", "result"]};
    if (requiresIdentifier[result.view]?.includes(result.screen)) result.screen = "";
    return result;
  };
  const pendingCharts = new Map();
  let chartSequence = 0;
  let privateValuesHidden = false;
  let displayLocale = "ru-RU";
  const setLocale = locale => {
    I.setLocale(locale);
    displayLocale = locale === "en" ? "en-US" : "ru-RU";
  };
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[character]);
  const number = value => {
    if (!["string", "number"].includes(typeof value)) return null;
    if (typeof value === "string" && !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) return null;
    const result = Number(value);
    return Number.isFinite(result) ? result : null;
  };
  const format = (value, digits = 2) => {
    const numeric = number(value);
    return numeric === null ? "—" : new Intl.NumberFormat(displayLocale, {
      maximumFractionDigits: digits
    }).format(numeric);
  };
  const money = (value, digits = 0, currency = "RUB", personal = true) => {
    if (personal && privateValuesHidden && number(value) !== null) return "••••••";
    const numeric = number(value);
    if (numeric === null) return "—";
    if (!/^[A-Z]{3}$/.test(currency)) return format(numeric, digits);
    const safeCurrency = currency;
    return new Intl.NumberFormat(displayLocale, {
      style: "currency",
      currency: safeCurrency,
      maximumFractionDigits: digits
    }).format(numeric);
  };
  const percent = (value, signed = false) => {
    const numeric = number(value);
    return numeric === null ? "—" : `${renderPercentValue(signed, numeric)}${format(numeric, 2)}%`;
  };
  const date = (value, time = false) => {
    if (!value) return T("Дата не получена");
    const parsed = new Date(value);
    if (!Number.isFinite(parsed.getTime())) return T("Дата не получена");
    return new Intl.DateTimeFormat(displayLocale, {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "Europe/Moscow",
      ...(time ? {
        hour: "2-digit",
        minute: "2-digit"
      } : {})
    }).format(parsed);
  };
  const icon = (name, small = false) => {
    const safeName = /^[a-z]+$/.test(name) ? name : "info";
    return `<svg class="icon${small ? " small" : ""}" aria-hidden="true"><use href="#i-${safeName}"/></svg>`;
  };
  const external = value => {
    try {
      const url = new URL(value);
      return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
    } catch {
      return null;
    }
  };
  const sourceLink = (url, label) => {
    const safeUrl = external(url);
    return safeUrl ? `<a href="${escape(safeUrl)}" target="_blank" rel="noopener noreferrer">${escape(label)}${icon("external", true)}</a>` : escape(label);
  };
  const button = (label, action, {
    primary = false,
    route = false,
    extra = "",
    small = false
  } = {}) => `<button type="button" class="button ${primary ? "primary" : "secondary"}${small ? " small-button" : ""}" ${route ? "data-route" : "data-action"}="${escape(action)}"${extra ? renderButtonFragment(extra) : ""}>${escape(label)}</button>`;
  const empty = (title, detail, action = "", label = "", symbol = "portfolio", centered = false) => `<div class="empty-state${centered ? " center" : ""}">${icon(symbol)}<h3>${escape(title)}</h3><p>${escape(detail)}</p>${action ? button(label, action, {
    primary: true,
    small: !centered
  }) : ""}</div>`;
  const loading = (label = T("Загружаем данные…")) => `<output class="loading-panel"><span class="spinner" aria-hidden="true"></span>${escape(label)}</output>`;
  const heading = (title, detail = "", actions = "") => `<div class="view-header"><div><h1>${escape(title)}</h1>${detail ? renderHeadingP(detail) : ""}</div>${actions ? renderHeadingViewActions(actions) : ""}</div>`;
  const cardHeader = (title, route = "", label = T("Смотреть все")) => `<div class="card-header"><h2>${escape(title)}</h2>${route ? renderCardHeaderTextButton(route, label, title) : ""}</div>`;
  const periodLabels = () => ([["1d", T("1Д")], ["1w", T("1Н")], ["1m", T("1М")], ["3m", T("3М")], ["1y", T("1Г")], ["all", T("ВСЕ")]]);
  const periods = (scope, selected, includeAll = true) => `<div class="periods" aria-label="${H("Период графика")}">${periodLabels().filter(([key]) => includeAll || key !== "all").map(([key, label]) => renderPeriodsPeriodButton(key, scope, selected, label)).join("")}</div>`;
  const filteredSeries = (data, period, timeKey = "captured_at") => {
    if (!Array.isArray(data)) return [];
    const days = {
      "1d": 1,
      "1w": 7,
      "1m": 31,
      "3m": 93,
      "1y": 365
    }[period];
    if (!days) return data;
    const now = Date.now();
    const cutoff = now - days * 86400000;
    return data.filter(item => {
      const time = new Date(item[timeKey]).getTime();
      return time >= cutoff && time <= now;
    });
  };
  const mergeGoals = (incoming, current, deletedIds) => {
    const known = new Map(current.map(goal => [goal.id, goal]));
    return incoming.filter(goal => !deletedIds.has(goal.id)).map(goal => {
      const previous = known.get(goal.id);
      return previous?.version > goal.version ? previous : goal;
    });
  };
  const marketPrice = (value, unit = "currency", currency = "", personal = false) => {
    if (unit === "currency") return money(value, 2, currency, personal);
    const suffix = {percent_nominal: T("% номинала"), points: T("пунктов"), per_nominal: `${currency} ${T("за номинал")}`, unknown: T("ед. источника")}[unit] || T("ед. источника");
    return number(value) === null ? "—" : `${format(value, 2)} ${suffix}`;
  };
  const chartPoints = (rows, timeKey, valueKey, comparison, xKind) => {
    const unique = new Map();
    for (const row of Array.isArray(rows) ? rows : []) {
      const time = xKind === "model_month" ? number(row[timeKey]) : new Date(row[timeKey]).getTime();
      const value = number(row[valueKey]);
      if (time !== null && Number.isFinite(time) && value !== null) unique.set(time, {
        time,
        value,
        comparison: comparison.map(series => number(row[series.key]))
      });
    }
    return [...unique.values()].sort((left, right) => left.time - right.time);
  };
  const chartLegend = (comparison, points, label, currency, personal) => {
    if (!comparison.length) return "";
    const values = comparison.map((series, index) => `<span class="chart-comparison-${index % 2}">${escape(series.label)}: <strong data-chart-comparison="${index}">${escape(money(points.at(-1).comparison[index], 0, currency, personal))}</strong></span>`).join("");
    return `<div class="chart-legend"><span>${escape(label)}</span>${values}</div>`;
  };
  const chart = (rows, {
    timeKey = "captured_at",
    valueKey = "nav_rub",
    label = T("Стоимость портфеля"),
    personal = true,
    currency = "RUB",
    priceUnit = "currency",
    tone = "green",
    compact = false,
    comparison = [],
    xKind = "date"
  } = {}) => {
    if (personal && privateValuesHidden) return ("<div class=\"chart-empty\">" + H("Значения скрыты настройкой конфиденциальности.") + "</div>");
    const timeLabel = value => xKind === "model_month" ? T("goals.model_month", {month: format(value, 0)}) : date(value, true);
    const points = chartPoints(rows, timeKey, valueKey, comparison, xKind);
    if (points.length < 2) return ("<div class=\"chart-empty\">" + H("Для графика нужны минимум два реальных наблюдения.") + "</div>");
    const width = 480;
    const height = 180;
    const left = 1;
    const top = compact ? 12 : 0;
    const bottom = compact ? 173 : height;
    const right = width - 1;
    const values = points.flatMap(point => [point.value, ...point.comparison.filter(value => value !== null)]);
    let low = Math.min(...values);
    let high = Math.max(...values);
    const pad = (high - low || Math.max(Math.abs(high) * .005, 1)) * .1;
    low -= pad;
    high += pad;
    const x = time => left + (time - points[0].time) / (points.at(-1).time - points[0].time) * (right - left);
    const y = value => bottom - (value - low) / (high - low) * (bottom - top);
    const path = points.map((point, index) => `${index ? "L" : "M"}${x(point.time).toFixed(2)} ${y(point.value).toFixed(2)}`).join(" ");
    const id = `chart-${++chartSequence}`;
    pendingCharts.set(id, {
      points,
      x,
      y,
      right,
      left,
      width,
      label,
      currency,
      priceUnit,
      personal,
      comparison,
      timeLabel
    });
    const grid = [0, .5, 1].map(part => {
      const value = high - (high - low) * part;
      const position = y(value);
      return `<line class="chart-grid" x1="${left}" x2="${right}" y1="${position}" y2="${position}"/>`;
    }).join("");
    const compared = comparison.map((series, index) => {
      const selected = points.filter(point => point.comparison[index] !== null);
      const line = selected.map((point, pointIndex) => `${pointIndex ? "L" : "M"}${x(point.time).toFixed(2)} ${y(point.comparison[index]).toFixed(2)}`).join(" ");
      return `<path class="chart-path chart-comparison chart-comparison-${index % 2}" d="${line}"/>`;
    }).join("");
    const legend = chartLegend(comparison, points, label, currency, personal);
    return `<div class="chart-block${tone === "purple" ? " chart-purple" : ""}"><div class="chart-plot${compact ? " chart-compact" : ""}"><svg class="chart-svg" data-chart="${id}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" tabindex="0" role="group" aria-label="${escape(label)}${H(". Используйте стрелки для просмотра значений.")}">${grid}<path class="chart-area" d="${path} L${right} ${bottom} L${left} ${bottom} Z"/><path class="chart-path" d="${path}"/>${compared}<g class="chart-hover" visibility="hidden"><line class="chart-cursor" y1="${top}" y2="${bottom}"/><circle class="chart-point" r="4"/></g></svg>${compact ? "" : renderChartAxes(points, low, high, timeLabel)}</div><div class="chart-readout" aria-live="off"><span>${escape(timeLabel(points.at(-1).time))}</span><strong>${escape(marketPrice(points.at(-1).value, priceUnit, currency, personal))}</strong></div>${legend}</div>`;
  };
  const bindCharts = (container = document) => {
    for (const svg of container.querySelectorAll("svg[data-chart]")) {
      const data = pendingCharts.get(svg.dataset.chart);
      if (!data) continue;
      pendingCharts.delete(svg.dataset.chart);
      let selected = data.points.length - 1;
      const hover = svg.querySelector(".chart-hover");
      const cursor = hover.querySelector("line");
      const point = hover.querySelector("circle");
      const readout = svg.closest(".chart-block").querySelector(".chart-readout");
      const show = index => {
        selected = Math.max(0, Math.min(data.points.length - 1, index));
        const current = data.points[selected];
        const px = data.x(current.time);
        const py = data.y(current.value);
        hover.setAttribute("visibility", "visible");
        cursor.setAttribute("x1", String(px));
        cursor.setAttribute("x2", String(px));
        point.setAttribute("cx", String(px));
        point.setAttribute("cy", String(py));
        readout.firstElementChild.textContent = data.timeLabel(current.time);
        readout.lastElementChild.textContent = marketPrice(current.value, data.priceUnit, data.currency, data.personal);
        for (const item of svg.closest(".chart-block").querySelectorAll("[data-chart-comparison]")) item.textContent = money(current.comparison[Number(item.dataset.chartComparison)], 0, data.currency, data.personal);
        svg.setAttribute("aria-label", `${data.label}: ${data.timeLabel(current.time)}, ${marketPrice(current.value, data.priceUnit, data.currency, data.personal)}${T(". Стрелки меняют наблюдение.")}`);
      };
      svg.addEventListener("pointermove", event => {
        const box = svg.getBoundingClientRect();
        if (!box.width) return;
        const px = (event.clientX - box.left) / box.width * data.width;
        let closest = 0;
        let distance = Infinity;
        data.points.forEach((item, index) => {
          const delta = Math.abs(data.x(item.time) - px);
          if (delta < distance) {
            closest = index;
            distance = delta;
          }
        });
        show(closest);
      });
      svg.addEventListener("pointerleave", () => {
        if (document.activeElement !== svg) hover.setAttribute("visibility", "hidden");
      });
      svg.addEventListener("focus", () => show(selected));
      svg.addEventListener("blur", () => hover.setAttribute("visibility", "hidden"));
      svg.addEventListener("keydown", event => {
        const destinations = {
          ArrowLeft: selected - 1,
          ArrowRight: selected + 1,
          Home: 0,
          End: data.points.length - 1
        };
        if (Object.hasOwn(destinations, event.key)) {
          event.preventDefault();
          show(destinations[event.key]);
        }
      });
    }
  };
  const allocation = (items, total) => {
    const valid = (Array.isArray(items) ? items : []).filter(item => number(item.value_rub) !== null && number(item.value_rub) >= 0 && number(item.nav_percent) !== null && number(item.nav_percent) >= 0);
    if (!valid.length || number(total) === null || number(total) <= 0) return empty(T("Структура пока не рассчитана"), T("Она появится после получения полного состава портфеля."), "", "", "portfolio");
    const circumference = 2 * Math.PI * 47;
    let offset = 0;
    const arcs = valid.map((item, index) => {
      const share = Math.min(100, Math.max(0, Number(item.nav_percent)));
      const length = share / 100 * circumference;
      const result = `<circle cx="60" cy="60" r="47" stroke="${colors[index % colors.length]}" stroke-dasharray="${length} ${circumference - length}" stroke-dashoffset="${-offset}"/>`;
      offset += length;
      return result;
    }).join("");
    return `<div class="allocation-content"><div class="donut-wrap"><svg class="donut" viewBox="0 0 120 120" role="img" aria-label="${H("Структура портфеля")}"><circle cx="60" cy="60" r="47" stroke="var(--line)"/>${arcs}</svg><div class="donut-center"><span>${H("Всего")}</span><strong>${escape(money(total))}</strong></div></div><ul class="allocation-legend">${valid.map((item, index) => renderAllocationLegendDot(index, item)).join("")}</ul></div>`;
  };
  const progress = value => `<div class="progress-row"><div class="progress-track"><svg viewBox="0 0 100 4" preserveAspectRatio="none" aria-hidden="true"><rect class="progress-shape" width="${Math.max(0, Math.min(100, number(value) ?? 0))}" height="4" rx="2"/></svg></div><span>${escape(percent(value))}</span></div>`;
  const infoRows = rows => `<dl class="info-list">${rows.map(([label, value]) => renderInfoRowsInfoRow(label, value)).join("")}</dl>`;
  const help = (title, detail) => `<button type="button" class="help-button" data-help-title="${escape(title)}" data-help="${escape(detail)}" aria-label="${H("Справка:")} ${escape(title)}">${icon("info", true)}</button>`;
  const field = ({
    name,
    label,
    value = "",
    type = "text",
    min,
    max,
    step,
    required = false,
    helpText = "",
    hint = "",
    placeholder = "",
    full = false
  }) => `<label class="field${full ? " full-span" : ""}"><span>${escape(label)}${helpText ? help(label, helpText) : ""}</span><input name="${escape(name)}" type="${escape(type)}" value="${escape(value ?? "")}"${min !== undefined ? renderFieldFragment(min) : ""}${max !== undefined ? renderFieldFragment2(max) : ""}${step !== undefined ? renderFieldFragment3(step) : ""}${required ? " required" : ""}${placeholder ? renderFieldFragment4(placeholder) : ""}${type === "number" ? ' inputmode="decimal"' : ""}>${hint ? renderFieldSmall(hint) : ""}</label>`;
  const select = (name, label, choices, value, helpText = "") => `<label class="field"><span>${escape(label)}${helpText ? help(label, helpText) : ""}</span><select name="${escape(name)}">${choices.map(([key, title]) => renderSelectOption(key, value, title)).join("")}</select></label>`;
  const switchControl = (name, label, detail, checked) => `<label class="switch-row"><span><strong>${escape(label)}</strong><small>${escape(detail)}</small></span><input type="checkbox" name="${escape(name)}" role="switch"${checked ? " checked" : ""}></label>`;
  const freshness = (source, at, status = "") => `<span class="source-line">${icon("refresh", true)}<span>${escape(source || T("Источник не указан"))}${at ? renderFreshnessFragment(at) : ""}</span>${status && !["fresh", "observed", "available"].includes(status) ? renderFreshnessSourceTag(status) : ""}</span>`;
  const setPrivacy = hidden => {
    privateValuesHidden = Boolean(hidden);
  };
  const clearCharts = () => pendingCharts.clear();
  window.OmniUI = Object.freeze({
    mergeGoals,
    escape,
    number,
    format,
    money,
    percent,
    date,
    icon,
    external,
    sourceLink,
    button,
    empty,
    loading,
    heading,
    cardHeader,
    periods,
    filteredSeries,
    chart,
    bindCharts,
    allocation,
    progress,
    infoRows,
    help,
    field,
    select,
    switchControl,
    freshness,
    setPrivacy,
    setLocale,
    clearCharts,
    colors,
    get navigation() { return navigation(); },
    marketPrice,
    compiledBuild: "__OMNICIO_BUILD__",
    publicPages, routeScreens, parseRoute, routeHash, resumeRoute
  });
  if (typeof document !== "undefined") document.querySelector("[data-offline-retry]")?.addEventListener("click", () => window.location.reload());
  function renderPercentValue(signed, numeric) {
    if (signed && numeric > 0) {
      return "+";
    }
    return "";
  }
  function renderButtonFragment(extra) {
    return ` ${extra}`;
  }
  function renderHeadingP(detail) {
    return `<p>${escape(detail)}</p>`;
  }
  function renderHeadingViewActions(actions) {
    return `<div class="view-actions">${actions}</div>`;
  }
  function renderCardHeaderTextButton(route, label, title) {
    return `<button class="text-button" data-route="${escape(route)}" aria-label="${escape(label || title)}">${escape(label)} ${icon("arrow", true)}</button>`;
  }
  function renderPeriodsPeriodButton(key, scope, selected, label) {
    return `<button class="period-button" data-period="${key}" data-period-scope="${escape(scope)}" aria-pressed="${key === selected}">${label}</button>`;
  }
  function renderChartAxes(points, low, high, timeLabel = value => date(value)) {
    const step = (high - low) / 2;
    const digits = Math.max(0, Math.min(20, 1 - Math.floor(Math.log10(step))));
    const ticks = [high, high - step, low].map(value => renderChartAxis(format(value, digits))).join("");
    return `<div class="chart-value-axis">${ticks}</div><div class="chart-time-axis">${renderChartAxis(timeLabel(points[0].time))}${renderChartAxis(timeLabel(points.at(-1).time))}</div>`;
  }
  function renderChartAxis(value) {
    return `<span class="chart-axis" title="${escape(value)}">${escape(value)}</span>`;
  }
  function renderAllocationLegendDot(index, item) {
    return `<li><i class="legend-dot" data-color="${index % colors.length}"></i><span>${escape(item.label)}</span><strong>${escape(percent(item.nav_percent))}</strong></li>`;
  }
  function renderInfoRowsInfoRow(label, value) {
    return `<div class="info-row"><dt>${escape(label)}</dt><dd>${escape(value ?? "—")}</dd></div>`;
  }
  function renderFieldFragment(min) {
    return ` min="${escape(min)}"`;
  }
  function renderFieldFragment2(max) {
    return ` max="${escape(max)}"`;
  }
  function renderFieldFragment3(step) {
    return ` step="${escape(step)}"`;
  }
  function renderFieldFragment4(placeholder) {
    return ` placeholder="${escape(placeholder)}"`;
  }
  function renderFieldSmall(hint) {
    return `<small>${escape(hint)}</small>`;
  }
  function renderSelectOption(key, value, title) {
    return `<option value="${escape(key)}"${String(key) === String(value) ? " selected" : ""}>${escape(title)}</option>`;
  }
  function renderFreshnessFragment(at) {
    return ` · ${escape(date(at, true))} ${T("МСК")}`;
  }
  function renderFreshnessSourceTag(status) {
    return `<span class="source-tag">${escape({
      live: T("Текущая котировка"),
      offline: T("Недоступно"),
      invalid: T("Недоступно"),
      disconnected: T("Не подключено"),
      reconnect: T("quotes.reconnecting"),
      stale: T("Данные устарели"),
      partial: T("Частичные данные"),
      pending: T("Ожидаем данные"),
      not_connected: T("Не подключено"),
      cached: T("Сохранённый ответ"),
      unavailable: T("Недоступно"),
      delayed: T("Данные с задержкой"),
      missing: T("state.source_missing"),
      future: T("state.source_future"),
      connecting: T("state.connecting"),
      empty: T("Нет наблюдений")
    }[status] || T("Статус требует проверки"))}</span>`;
  }
})();
