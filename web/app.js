(() => {
  "use strict";

  const authCard = document.querySelector("#auth-card");
  const profilePanel = document.querySelector("#profile-panel");
  const vkidForm = document.querySelector("#vkid-form");
  const vkidLogin = document.querySelector("#vkid-login");
  const authMessage = document.querySelector("#auth-message");

  const profileId = document.querySelector("#profile-id");
  const settingsProfileId = document.querySelector("#settings-profile-id");
  const logoutButton = document.querySelector("#logout");

  const tbankForm = document.querySelector("#tbank-form");
  const tbankAccountForm = document.querySelector("#tbank-account-form");
  const tbankEnvironment = document.querySelector("#tbank-environment");
  const tbankToken = document.querySelector("#tbank-token");
  const tbankAccount = document.querySelector("#tbank-account");
  const tbankTermsAck = document.querySelector("#tbank-terms-ack");
  const tbankCheck = document.querySelector("#tbank-check");
  const tbankConnect = document.querySelector("#tbank-connect");
  const tbankConnected = document.querySelector("#tbank-connected");
  const tbankDisconnect = document.querySelector("#tbank-disconnect");
  const tbankAccountLabel = document.querySelector("#tbank-account-label");
  const tbankMessage = document.querySelector("#tbank-message");
  const tbankStatusBadge = document.querySelector("#tbank-status-badge");

  const overviewAccount = document.querySelector("#overview-account");
  const overviewConnectionText = document.querySelector("#overview-connection-text");
  const homeConnectionCard = document.querySelector("#home-connection-card");
  const homeTbankState = document.querySelector("#home-tbank-state");
  const topConnectionIndicator = document.querySelector("#top-connection-indicator");
  const topConnectionText = document.querySelector("#top-connection-text");
  const homePortfolioState = document.querySelector("#home-portfolio-state");

  const portfolioStateBadge = document.querySelector("#portfolio-state-badge");
  const portfolioRefresh = document.querySelector("#portfolio-refresh");
  const portfolioLoading = document.querySelector("#portfolio-loading");
  const portfolioDisconnected = document.querySelector("#portfolio-disconnected");
  const portfolioError = document.querySelector("#portfolio-error");
  const portfolioErrorText = document.querySelector("#portfolio-error-text");
  const portfolioContent = document.querySelector("#portfolio-content");
  const portfolioTotal = document.querySelector("#portfolio-total");
  const portfolioYield = document.querySelector("#portfolio-yield");
  const portfolioDaily = document.querySelector("#portfolio-daily");
  const portfolioDailyRelative = document.querySelector("#portfolio-daily-relative");
  const portfolioPositionCount = document.querySelector("#portfolio-position-count");
  const portfolioRefreshed = document.querySelector("#portfolio-refreshed");
  const assetAllocation = document.querySelector("#asset-allocation");
  const cashList = document.querySelector("#cash-list");
  const cashLoadingNote = document.querySelector("#cash-loading-note");
  const positionsList = document.querySelector("#positions-list");
  const operationsList = document.querySelector("#operations-list");
  const operationsMoreNote = document.querySelector("#operations-more-note");
  const operationsLoadMore = document.querySelector("#operations-load-more");
  const portfolioRetry = document.querySelector("[data-portfolio-retry]");

  const owlState = document.querySelector("#owl-state");
  const owlLastRefresh = document.querySelector("#owl-last-refresh");
  const hunterForm = document.querySelector("#hunter-form");
  const hunterQuery = document.querySelector("#hunter-query");
  const hunterSearch = document.querySelector("#hunter-search");
  const hunterMessage = document.querySelector("#hunter-message");
  const hunterResults = document.querySelector("#hunter-results");
  const guardState = document.querySelector("#guard-state");
  const guardBlockedPositions = document.querySelector("#guard-blocked-positions");
  const guardBlockedCash = document.querySelector("#guard-blocked-cash");
  const guardLargestClass = document.querySelector("#guard-largest-class");

  const viewTitle = document.querySelector("#view-title");
  const desktopNavItems = [...document.querySelectorAll("[data-view]")];
  const mobileNavItems = [...document.querySelectorAll("[data-mobile-view]")];
  const viewPanels = [...document.querySelectorAll("[data-view-panel]")];
  const viewLinks = [...document.querySelectorAll("[data-go-view]")];

  const themeButtons = [...document.querySelectorAll("[data-theme-option]")];
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");
  const THEME_KEY = "omnicio_theme_v2";

  const installButton = document.querySelector("#install-app");
  const installStatus = document.querySelector("#install-status");

  const VIEW_TITLES = {
    home: "Главная",
    portfolio: "Портфель",
    connections: "Подключения",
    settings: "Настройки",
  };

  let currentView = "home";
  let pendingTbankCredential = null;
  let pendingTbankEnvironment = null;
  let deferredInstallPrompt = null;
  let tbankIsConnected = false;
  let portfolioLoaded = false;
  let portfolioRequestInFlight = false;
  let nextOperationsCursor = "";
  let lastPortfolioSnapshot = null;
  let lastPortfolioRefreshAt = 0;
  let owlTimer = null;

  const api = async (path, options = {}) => {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: {"Content-Type": "application/json", ...(options.headers || {})},
      ...options,
    });
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error((body && body.detail) || "request failed");
      error.status = response.status;
      throw error;
    }
    return body;
  };

  const showMessage = (element, text, isError = false) => {
    element.textContent = text;
    element.classList.toggle("error", isError);
  };

  const setStateBadge = (element, text, state) => {
    element.textContent = text;
    element.classList.remove("state-ok", "state-next", "state-error");
    if (state) {
      element.classList.add(state);
    }
  };

  const renderReleaseInfo = () => {
    const release = window.OMNICIO_RELEASE || {};
    const version = typeof release.version === "string" && release.version ? release.version : "—";
    const build = typeof release.build === "string" && release.build ? release.build : "—";

    document.querySelectorAll("[data-app-version]").forEach((element) => {
      element.textContent = version;
    });
    document.querySelectorAll("[data-app-build]").forEach((element) => {
      element.textContent = build;
    });
  };

  const storedTheme = () => {
    try {
      const value = window.localStorage.getItem(THEME_KEY);
      return ["light", "dark", "auto"].includes(value) ? value : "light";
    } catch {
      return "light";
    }
  };

  const saveTheme = (theme) => {
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Theme persistence is optional when storage is unavailable.
    }
  };

  const resolveTheme = (preference) => {
    if (preference === "auto") {
      return systemDark.matches ? "dark" : "light";
    }
    return preference === "dark" ? "dark" : "light";
  };

  const applyTheme = (preference) => {
    const resolved = resolveTheme(preference);
    document.body.dataset.theme = resolved;
    if (themeMeta) {
      themeMeta.content = resolved === "dark" ? "#10151d" : "#f6f8fb";
    }
    themeButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeOption === preference));
    });
  };

  const setView = (view, {scroll = true} = {}) => {
    if (!VIEW_TITLES[view]) {
      return;
    }

    currentView = view;
    viewTitle.textContent = VIEW_TITLES[view];

    desktopNavItems.forEach((item) => {
      const active = item.dataset.view === view;
      item.classList.toggle("is-active", active);
      if (active) {
        item.setAttribute("aria-current", "page");
      } else {
        item.removeAttribute("aria-current");
      }
    });

    mobileNavItems.forEach((item) => {
      const active = item.dataset.mobileView === view;
      item.classList.toggle("is-active", active);
      if (active) {
        item.setAttribute("aria-current", "page");
      } else {
        item.removeAttribute("aria-current");
      }
    });

    viewPanels.forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.viewPanel !== view);
    });

    if (scroll) {
      window.scrollTo({top: 0, behavior: "auto"});
    }

    if (view === "portfolio" && tbankIsConnected && !portfolioLoaded) {
      void loadPortfolioData();
    }
  };

  const resetTbankPreview = () => {
    pendingTbankCredential = null;
    pendingTbankEnvironment = null;
    tbankAccount.replaceChildren();
    tbankAccountForm.classList.add("hidden");
  };

  const ASSET_LABELS = {
    shares: "Акции",
    bonds: "Облигации",
    funds: "Фонды",
    currencies: "Валюта и деньги",
    futures: "Фьючерсы",
    options: "Опционы",
    structured_products: "Структурные продукты",
    dfa: "ЦФА",
  };

  const INSTRUMENT_LABELS = {
    share: "Акция",
    bond: "Облигация",
    etf: "Фонд",
    currency: "Валюта",
    futures: "Фьючерс",
    option: "Опцион",
    sp: "Структурный продукт",
  };

  const numericValue = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
  };

  const formatMoney = (money, {sign = false} = {}) => {
    if (!money || typeof money.value !== "string" || !money.currency) {
      return "—";
    }
    const value = numericValue(money.value);
    try {
      const formatted = new Intl.NumberFormat("ru-RU", {
        style: "currency",
        currency: String(money.currency).toUpperCase(),
        minimumFractionDigits: 0,
        maximumFractionDigits: 4,
      }).format(value);
      return sign && value > 0 ? `+${formatted}` : formatted;
    } catch {
      const formatted = new Intl.NumberFormat("ru-RU", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 4,
      }).format(value);
      return `${sign && value > 0 ? "+" : ""}${formatted} ${money.currency}`;
    }
  };

  const formatPercent = (value, {sign = false} = {}) => {
    const number = numericValue(value);
    const formatted = new Intl.NumberFormat("ru-RU", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(number);
    return `${sign && number > 0 ? "+" : ""}${formatted}%`;
  };

  const formatQuantity = (value) => new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 8,
  }).format(numericValue(value));

  const formatDateTime = (value) => {
    if (!value) {
      return "—";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  const applySignedClass = (element, value) => {
    const number = numericValue(value);
    element.classList.remove("value-positive", "value-negative");
    if (number > 0) {
      element.classList.add("value-positive");
    } else if (number < 0) {
      element.classList.add("value-negative");
    }
  };

  const appendEmptyState = (container, text) => {
    container.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "portfolio-empty-inline";
    empty.textContent = text;
    container.append(empty);
  };

  const updateOwlState = (timestamp) => {
    if (!tbankIsConnected) {
      setStateBadge(owlState, "Нет подключения", "state-next");
      owlLastRefresh.textContent = "—";
      return;
    }

    if (!timestamp) {
      setStateBadge(owlState, "Ожидает данных", "");
      owlLastRefresh.textContent = "—";
      return;
    }

    setStateBadge(owlState, "Наблюдает", "state-ok");
    owlLastRefresh.textContent = formatDateTime(timestamp);
  };

  const updateGuard = (snapshot) => {
    if (!snapshot?.portfolio) {
      setStateBadge(guardState, "Ожидает данных", "");
      guardBlockedPositions.textContent = "—";
      guardBlockedCash.textContent = "—";
      guardLargestClass.textContent = "—";
      return;
    }

    const positions = snapshot.portfolio.positions || [];
    const blockedPositions = positions.filter((position) => position.blocked).length;
    const blockedCash = (snapshot.blocked_cash || []).filter(
      (money) => numericValue(money.value) !== 0
    );

    const totals = (snapshot.portfolio.asset_totals || []).filter(
      (item) => numericValue(item.money?.value) > 0
    );
    const total = totals.reduce((sum, item) => sum + numericValue(item.money.value), 0);
    const largest = totals.reduce((current, item) => {
      if (!current || numericValue(item.money.value) > numericValue(current.money.value)) {
        return item;
      }
      return current;
    }, null);

    guardBlockedPositions.textContent = String(blockedPositions);
    guardBlockedCash.textContent = String(blockedCash.length);
    if (largest && total > 0) {
      const share = (numericValue(largest.money.value) / total) * 100;
      guardLargestClass.textContent = `${ASSET_LABELS[largest.kind] || largest.kind} · ${share.toFixed(1)}%`;
    } else {
      guardLargestClass.textContent = "Нет данных";
    }
    setStateBadge(guardState, "Контролирует", "state-ok");
  };

  const renderHunterResults = (items) => {
    hunterResults.replaceChildren();
    if (!items?.length) {
      appendEmptyState(hunterResults, "T-Invest не нашёл доступных инструментов по этому запросу.");
      return;
    }

    items.forEach((instrument) => {
      const card = document.createElement("article");
      card.className = "hunter-result";

      const main = document.createElement("div");
      main.className = "hunter-result-main";

      const identity = document.createElement("div");
      identity.className = "hunter-result-identity";
      const ticker = document.createElement("strong");
      ticker.textContent = instrument.ticker || "—";
      const name = document.createElement("span");
      name.textContent = instrument.name || "Без названия";
      identity.append(ticker, name);

      const meta = document.createElement("div");
      meta.className = "hunter-result-meta";
      const type = document.createElement("span");
      type.textContent = INSTRUMENT_LABELS[instrument.instrument_type]
        || instrument.instrument_type
        || "Инструмент";
      const lot = document.createElement("span");
      lot.textContent = `Лот: ${Number.isFinite(Number(instrument.lot)) ? instrument.lot : "—"}`;
      meta.append(type, lot);

      main.append(identity, meta);

      const flags = document.createElement("div");
      flags.className = "hunter-result-flags";
      if (instrument.for_qual_investor) {
        const flag = document.createElement("span");
        flag.textContent = "Для квалифицированных инвесторов";
        flags.append(flag);
      }
      if (instrument.for_iis) {
        const flag = document.createElement("span");
        flag.textContent = "Доступно для ИИС";
        flags.append(flag);
      }
      if (instrument.weekend_trading) {
        const flag = document.createElement("span");
        flag.textContent = "Торги в выходные";
        flags.append(flag);
      }
      if (!flags.childElementCount) {
        const flag = document.createElement("span");
        flag.textContent = "Доступен через T-Invest API";
        flags.append(flag);
      }

      card.append(main, flags);
      hunterResults.append(card);
    });
  };

  const searchHunter = async () => {
    const query = hunterQuery.value.trim();
    showMessage(hunterMessage, "");
    hunterResults.replaceChildren();

    if (!tbankIsConnected) {
      showMessage(hunterMessage, "Сначала подключите T-Invest.", true);
      return;
    }
    if (!query || query.length > 64) {
      showMessage(hunterMessage, "Введите тикер или название инструмента.", true);
      return;
    }

    hunterSearch.disabled = true;
    const originalText = hunterSearch.textContent;
    hunterSearch.textContent = "Ищем…";
    try {
      const payload = await api(
        `/api/broker/tbank/instruments/search?q=${encodeURIComponent(query)}`,
        {method: "GET"},
      );
      renderHunterResults(payload.items || []);
      showMessage(
        hunterMessage,
        payload.items?.length
          ? `Найдено: ${payload.items.length}. Это поиск, а не инвестиционная рекомендация.`
          : "Совпадений не найдено.",
      );
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      if (error.status === 409) {
        showMessage(hunterMessage, "Подключение T-Invest нужно обновить.", true);
      } else {
        showMessage(hunterMessage, "Поиск T-Invest временно недоступен.", true);
      }
    } finally {
      hunterSearch.disabled = false;
      hunterSearch.textContent = originalText;
    }
  };

  const startOwl = () => {
    if (owlTimer !== null) {
      window.clearInterval(owlTimer);
    }

    owlTimer = window.setInterval(() => {
      if (
        document.visibilityState === "visible"
        && tbankIsConnected
        && !portfolioRequestInFlight
      ) {
        void loadPortfolioData({force: true, refreshOperations: false});
      }
    }, 5 * 60 * 1000);
  };

  const renderAllocation = (totals) => {
    assetAllocation.replaceChildren();
    const positive = (totals || []).filter((item) => numericValue(item.money?.value) > 0);
    const sum = positive.reduce((total, item) => total + numericValue(item.money.value), 0);
    if (!positive.length || sum <= 0) {
      appendEmptyState(assetAllocation, "T-Invest не вернул распределение по классам активов.");
      return;
    }

    positive
      .sort((left, right) => numericValue(right.money.value) - numericValue(left.money.value))
      .forEach((item) => {
        const value = numericValue(item.money.value);
        const share = Math.max(0, Math.min(100, (value / sum) * 100));

        const row = document.createElement("div");
        row.className = "allocation-row";

        const label = document.createElement("div");
        label.className = "allocation-label";
        const name = document.createElement("strong");
        name.textContent = ASSET_LABELS[item.kind] || item.kind;
        const percent = document.createElement("span");
        percent.textContent = `${share.toFixed(1)}%`;
        label.append(name, percent);

        const track = document.createElement("div");
        track.className = "allocation-track";
        const fill = document.createElement("div");
        fill.className = "allocation-fill";
        fill.style.width = `${share}%`;
        track.append(fill);

        const amount = document.createElement("div");
        amount.className = "allocation-value";
        amount.textContent = formatMoney(item.money);

        row.append(label, track, amount);
        assetAllocation.append(row);
      });
  };

  const renderCash = (cash, blockedCash, loadingLimits) => {
    cashList.replaceChildren();
    const blockedByCurrency = new Map(
      (blockedCash || []).map((item) => [String(item.currency).toUpperCase(), item])
    );
    if (!cash?.length) {
      appendEmptyState(cashList, "Денежные остатки отсутствуют или ещё не загружены.");
    } else {
      cash.forEach((item) => {
        const currency = String(item.currency).toUpperCase();
        const blocked = blockedByCurrency.get(currency);
        const row = document.createElement("div");
        row.className = "cash-row";

        const label = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = currency;
        const note = document.createElement("span");
        note.textContent = blocked && numericValue(blocked.value) !== 0
          ? `Заблокировано: ${formatMoney(blocked)}`
          : "Доступно на счёте";
        label.append(title, note);

        const amount = document.createElement("div");
        amount.className = "cash-value";
        amount.textContent = formatMoney(item);

        row.append(label, amount);
        cashList.append(row);
      });
    }
    cashLoadingNote.classList.toggle("hidden", !loadingLimits);
  };

  const renderPositions = (positions) => {
    positionsList.replaceChildren();
    if (!positions?.length) {
      appendEmptyState(positionsList, "В портфеле нет инструментов.");
      return;
    }

    positions.forEach((position) => {
      const row = document.createElement("div");
      row.className = "position-row";

      const name = document.createElement("div");
      name.className = "position-name";
      const ticker = document.createElement("strong");
      ticker.textContent = position.ticker || position.figi || "Инструмент";
      const type = document.createElement("span");
      type.textContent = INSTRUMENT_LABELS[position.instrument_type] || position.instrument_type || "Инструмент";
      name.append(ticker, type);
      if (position.blocked) {
        const blocked = document.createElement("em");
        blocked.className = "position-blocked";
        blocked.textContent = "Заблокировано биржей";
        name.append(blocked);
      }

      const quantity = document.createElement("div");
      quantity.className = "position-cell";
      const quantityLabel = document.createElement("span");
      quantityLabel.textContent = "Количество";
      const quantityValue = document.createElement("strong");
      quantityValue.textContent = formatQuantity(position.quantity);
      quantity.append(quantityLabel, quantityValue);

      const price = document.createElement("div");
      price.className = "position-cell";
      const priceLabel = document.createElement("span");
      priceLabel.textContent = "Текущая цена";
      const priceValue = document.createElement("strong");
      priceValue.textContent = formatMoney(position.current_price);
      price.append(priceLabel, priceValue);

      const yieldCell = document.createElement("div");
      yieldCell.className = "position-cell";
      const yieldLabel = document.createElement("span");
      yieldLabel.textContent = "Доходность";
      const yieldValue = document.createElement("strong");
      yieldValue.textContent = formatPercent(position.expected_yield_percent, {sign: true});
      applySignedClass(yieldValue, position.expected_yield_percent);
      yieldCell.append(yieldLabel, yieldValue);

      row.append(name, quantity, price, yieldCell);
      positionsList.append(row);
    });
  };

  const renderOperations = (payload, {append = false} = {}) => {
    if (!append) {
      operationsList.replaceChildren();
    }
    if (!payload || !payload.items?.length) {
      if (!append) {
        appendEmptyState(operationsList, "Исполненных операций пока нет.");
      }
      nextOperationsCursor = "";
      operationsMoreNote.classList.add("hidden");
      return;
    }

    payload.items.forEach((operation) => {
      const row = document.createElement("div");
      row.className = "operation-row";

      const main = document.createElement("div");
      main.className = "operation-main";
      const name = document.createElement("strong");
      name.textContent = operation.name || operation.description || operation.type || "Операция";
      const detail = document.createElement("span");
      detail.textContent = [operation.ticker, formatDateTime(operation.date)].filter(Boolean).join(" · ");
      main.append(name, detail);

      const amount = document.createElement("div");
      amount.className = "operation-meta";
      const amountLabel = document.createElement("span");
      amountLabel.textContent = "Сумма";
      const amountValue = document.createElement("strong");
      amountValue.textContent = formatMoney(operation.payment, {sign: true});
      applySignedClass(amountValue, operation.payment?.value);
      amount.append(amountLabel, amountValue);

      const commission = document.createElement("div");
      commission.className = "operation-meta";
      const commissionLabel = document.createElement("span");
      commissionLabel.textContent = "Комиссия";
      const commissionValue = document.createElement("strong");
      commissionValue.textContent = operation.commission
        ? formatMoney(operation.commission)
        : "—";
      commission.append(commissionLabel, commissionValue);

      row.append(main, amount, commission);
      operationsList.append(row);
    });

    nextOperationsCursor = payload.has_next ? String(payload.next_cursor || "") : "";
    operationsMoreNote.classList.toggle("hidden", !nextOperationsCursor);
  };

  const loadMoreOperations = async () => {
    if (!tbankIsConnected || !nextOperationsCursor || operationsLoadMore.disabled) {
      return;
    }
    operationsLoadMore.disabled = true;
    const originalText = operationsLoadMore.textContent;
    operationsLoadMore.textContent = "Загружаем…";
    try {
      const payload = await api(
        `/api/broker/tbank/operations?limit=30&cursor=${encodeURIComponent(nextOperationsCursor)}`,
        {method: "GET"},
      );
      renderOperations(payload, {append: true});
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      operationsLoadMore.textContent = "Не удалось. Повторить";
      return;
    } finally {
      operationsLoadMore.disabled = false;
      if (operationsLoadMore.textContent === "Загружаем…") {
        operationsLoadMore.textContent = originalText;
      }
    }
  };

  const showPortfolioMode = (mode) => {
    portfolioLoading.classList.toggle("hidden", mode !== "loading");
    portfolioDisconnected.classList.toggle("hidden", mode !== "disconnected");
    portfolioError.classList.toggle("hidden", mode !== "error");
    portfolioContent.classList.toggle("hidden", mode !== "content");
  };

  const renderPortfolio = (
    snapshot,
    operationsPayload,
    {updateOperations = true} = {},
  ) => {
    const portfolio = snapshot.portfolio;
    portfolioTotal.textContent = formatMoney(portfolio.total);
    portfolioYield.textContent = formatPercent(portfolio.expected_yield_percent, {sign: true});
    applySignedClass(portfolioYield, portfolio.expected_yield_percent);
    portfolioDaily.textContent = formatMoney(portfolio.daily_yield, {sign: true});
    applySignedClass(portfolioDaily, portfolio.daily_yield?.value);
    portfolioDailyRelative.textContent = formatPercent(portfolio.daily_yield_percent, {sign: true});
    portfolioPositionCount.textContent = String(portfolio.positions?.length || 0);
    portfolioRefreshed.textContent = `Обновлено ${formatDateTime(snapshot.refreshed_at)}`;

    renderAllocation(portfolio.asset_totals);
    renderCash(snapshot.cash, snapshot.blocked_cash, snapshot.limits_loading_in_progress);
    renderPositions(portfolio.positions);
    if (updateOperations) {
      renderOperations(operationsPayload);
    }

    lastPortfolioSnapshot = snapshot;
    lastPortfolioRefreshAt = Date.now();
    portfolioLoaded = true;
    updateOwlState(snapshot.refreshed_at);
    updateGuard(snapshot);
    showPortfolioMode("content");
    setStateBadge(portfolioStateBadge, "Данные получены", "state-ok");
    setStateBadge(homePortfolioState, "Работает", "state-ok");
  };

  const loadPortfolioData = async (
    {force = false, refreshOperations = true} = {},
  ) => {
    if (!tbankIsConnected) {
      portfolioLoaded = false;
      lastPortfolioSnapshot = null;
      lastPortfolioRefreshAt = 0;
      updateOwlState(null);
      updateGuard(null);
      showPortfolioMode("disconnected");
      setStateBadge(portfolioStateBadge, "Нет подключения", "state-next");
      setStateBadge(homePortfolioState, "Нет подключения", "state-next");
      return;
    }
    if (portfolioRequestInFlight || (portfolioLoaded && !force)) {
      return;
    }

    const hadPortfolio = portfolioLoaded;
    portfolioRequestInFlight = true;
    portfolioRefresh.disabled = true;
    if (!hadPortfolio) {
      showPortfolioMode("loading");
    }
    setStateBadge(portfolioStateBadge, "Обновляем", "");
    setStateBadge(homePortfolioState, hadPortfolio ? "Обновляем" : "Загружаем", "");

    try {
      const operationsRequest = refreshOperations
        ? api("/api/broker/tbank/operations?limit=30", {method: "GET"}).catch(() => null)
        : Promise.resolve(null);
      const [snapshot, operationsPayload] = await Promise.all([
        api("/api/broker/tbank/portfolio", {method: "GET"}),
        operationsRequest,
      ]);
      renderPortfolio(
        snapshot,
        operationsPayload,
        {updateOperations: refreshOperations},
      );
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }

      const needsReconnect = error.status === 409;
      if (hadPortfolio && lastPortfolioSnapshot) {
        portfolioLoaded = true;
        showPortfolioMode("content");
        setStateBadge(portfolioStateBadge, "Данные устарели", "state-next");
        setStateBadge(homePortfolioState, "Данные устарели", "state-next");
        setStateBadge(owlState, "Ошибка обновления", "state-next");
      } else {
        portfolioLoaded = false;
        showPortfolioMode("error");
        portfolioErrorText.textContent = needsReconnect
          ? "Подключение T-Invest устарело или токен больше не действует. Переподключите счёт."
          : "T-Invest временно не отдал данные портфеля. Попробуйте повторить запрос.";
        setStateBadge(portfolioStateBadge, "Ошибка", "state-error");
        setStateBadge(homePortfolioState, "Ошибка", "state-error");
        setStateBadge(owlState, "Ошибка", "state-error");
        updateGuard(null);
      }
    } finally {
      portfolioRequestInFlight = false;
      portfolioRefresh.disabled = false;
    }
  };

  const renderTbankSummary = (status) => {
    homeConnectionCard.classList.remove("is-offline", "is-error");
    topConnectionIndicator.classList.remove("is-offline", "is-error");
    tbankIsConnected = Boolean(status.connected);

    if (!status.connected) {
      portfolioLoaded = false;
      overviewAccount.textContent = "T-Invest не подключён";
      overviewConnectionText.textContent = "Подключите read-only API-токен в разделе «Подключения».";
      homeConnectionCard.classList.add("is-offline");
      topConnectionIndicator.classList.add("is-offline");
      topConnectionText.textContent = "T-Invest не подключён";
      setStateBadge(homeTbankState, "Не подключено", "state-next");
      setStateBadge(homePortfolioState, "Нет подключения", "state-next");
      setStateBadge(portfolioStateBadge, "Нет подключения", "state-next");
      showPortfolioMode("disconnected");
      return;
    }

    const environment = status.environment === "sandbox" ? "Песочница" : "Биржа";
    const accountName = status.account_name || "Брокерский счёт";
    overviewAccount.textContent = accountName;
    overviewConnectionText.textContent = `${environment} · соединение подтверждено`;
    topConnectionText.textContent = "T-Invest подключён";
    setStateBadge(homeTbankState, "Работает", "state-ok");
    if (!portfolioLoaded) {
      setStateBadge(homePortfolioState, "Загружаем", "");
      setStateBadge(portfolioStateBadge, "Загружаем", "");
    }
  };

  const renderTbankStatus = (status) => {
    resetTbankPreview();
    tbankToken.value = "";
    renderTbankSummary(status);

    if (!status.connected) {
      tbankConnected.classList.add("hidden");
      tbankForm.classList.remove("hidden");
      setStateBadge(tbankStatusBadge, "Не подключён", "state-next");
      return;
    }

    const environment = status.environment === "sandbox" ? "Песочница" : "Биржа";
    const accountName = status.account_name || "Брокерский счёт";
    const accountSuffix = status.account_id
      ? ` · ••••${String(status.account_id).slice(-6)}`
      : "";

    tbankAccountLabel.textContent = `${environment} · ${accountName}${accountSuffix}`;
    tbankForm.classList.add("hidden");
    tbankConnected.classList.remove("hidden");
    setStateBadge(tbankStatusBadge, "Подключено", "state-ok");
  };

  const renderTbankFailure = () => {
    overviewAccount.textContent = "Не удалось проверить подключение";
    overviewConnectionText.textContent = "Обновите страницу или попробуйте позже.";
    homeConnectionCard.classList.add("is-error");
    topConnectionIndicator.classList.add("is-error");
    topConnectionText.textContent = "Ошибка T-Invest";
    tbankIsConnected = false;
    portfolioLoaded = false;
    setStateBadge(homeTbankState, "Ошибка", "state-error");
    setStateBadge(homePortfolioState, "Ошибка", "state-error");
    setStateBadge(tbankStatusBadge, "Ошибка", "state-error");
    setStateBadge(portfolioStateBadge, "Ошибка", "state-error");
  };

  const loadTbankStatus = async () => {
    showMessage(tbankMessage, "");
    try {
      const status = await api("/api/broker/tbank", {method: "GET"});
      renderTbankStatus(status);
      if (status.connected) {
        void loadPortfolioData();
      }
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      renderTbankFailure();
      showMessage(tbankMessage, "Не удалось проверить подключение T-Invest.", true);
    }
  };

  const showProfile = (id) => {
    profileId.textContent = id;
    settingsProfileId.textContent = id;
    authCard.classList.add("hidden");
    profilePanel.classList.remove("hidden");
    setView(currentView, {scroll: false});
    void loadTbankStatus();
  };

  const showAuth = () => {
    profilePanel.classList.add("hidden");
    authCard.classList.remove("hidden");
  };

  const showCallbackResult = () => {
    const params = new URLSearchParams(location.search);
    const authError = params.get("auth_error");

    if (authError === "owner") {
      showMessage(authMessage, "Этот VK ID не имеет доступа к личному аккаунту OmniCIO.", true);
    } else if (authError === "provider") {
      showMessage(authMessage, "VK ID временно недоступен. Попробуйте позже.", true);
    } else if (authError === "account") {
      showMessage(authMessage, "Личный аккаунт OmniCIO заблокирован.", true);
    } else if (authError) {
      showMessage(authMessage, "Авторизация VK ID не завершена. Попробуйте ещё раз.", true);
    }

    if (params.has("auth") || params.has("auth_error")) {
      history.replaceState(null, "", location.pathname);
    }
  };

  const loadState = async () => {
    try {
      const me = await api("/api/me", {method: "GET"});
      showProfile(me.public_id);
      return;
    } catch (error) {
      if (error.status !== 401) {
        showMessage(authMessage, "Не удалось проверить сессию. Обновите страницу.", true);
      }
    }

    showAuth();
    showCallbackResult();

    try {
      const config = await api("/api/auth/config", {method: "GET"});
      if (config.auth_provider !== "vkid" || !config.owner_login_enabled) {
        vkidLogin.disabled = true;
        showMessage(
          authMessage,
          "VK ID ещё не настроен для этого личного аккаунта.",
          true,
        );
      }
    } catch {
      vkidLogin.disabled = true;
      showMessage(authMessage, "Сервис авторизации временно недоступен.", true);
    }
  };

  const standaloneMode = () => (
    window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true
  );

  const refreshInstallState = () => {
    if (standaloneMode()) {
      installStatus.textContent = "Установлено и открыто как приложение";
      installButton.classList.add("hidden");
      return;
    }

    if (deferredInstallPrompt) {
      installStatus.textContent = "Можно установить без адресной строки браузера";
      installButton.classList.remove("hidden");
      return;
    }

    installStatus.textContent = "Открыто в браузере";
    installButton.classList.add("hidden");
  };

  operationsLoadMore.addEventListener("click", () => {
    void loadMoreOperations();
  });

  portfolioRefresh.addEventListener("click", () => {
    void loadPortfolioData({force: true});
  });

  portfolioRetry.addEventListener("click", () => {
    void loadPortfolioData({force: true});
  });

  desktopNavItems.forEach((item) => {
    item.addEventListener("click", () => setView(item.dataset.view));
  });

  mobileNavItems.forEach((item) => {
    item.addEventListener("click", () => setView(item.dataset.mobileView));
  });

  viewLinks.forEach((item) => {
    item.addEventListener("click", () => setView(item.dataset.goView));
  });

  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const preference = button.dataset.themeOption;
      saveTheme(preference);
      applyTheme(preference);
    });
  });

  systemDark.addEventListener("change", () => {
    if (storedTheme() === "auto") {
      applyTheme("auto");
    }
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    refreshInstallState();
  });

  window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    refreshInstallState();
  });

  installButton.addEventListener("click", async () => {
    if (!deferredInstallPrompt) {
      return;
    }

    const promptEvent = deferredInstallPrompt;
    deferredInstallPrompt = null;
    installButton.disabled = true;
    try {
      await promptEvent.prompt();
      await promptEvent.userChoice;
    } finally {
      installButton.disabled = false;
      refreshInstallState();
    }
  });

  vkidForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage(authMessage, "");

    const payload = {
      accept_privacy: document.querySelector("#accept-privacy").checked,
      accept_personal_data: document.querySelector("#accept-pd").checked,
      accept_terms: document.querySelector("#accept-terms").checked,
      confirm_age_18: document.querySelector("#confirm-age-18").checked,
    };

    if (!Object.values(payload).every(Boolean)) {
      showMessage(authMessage, "Подтвердите все четыре пункта перед входом.", true);
      return;
    }

    vkidLogin.disabled = true;
    try {
      const result = await api("/api/auth/vkid/start", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!result.authorize_url) {
        throw new Error("VK ID URL is missing");
      }
      location.assign(result.authorize_url);
    } catch (error) {
      vkidLogin.disabled = false;
      if (error.status === 503) {
        showMessage(authMessage, "VK ID ещё не настроен или временно недоступен.", true);
      } else {
        showMessage(authMessage, "Не удалось начать авторизацию через VK ID.", true);
      }
    }
  });

  tbankForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage(tbankMessage, "");
    resetTbankPreview();

    const credential = tbankToken.value.trim();
    const environment = tbankEnvironment.value;

    if (credential.length < 20) {
      showMessage(tbankMessage, "Вставьте полный API-токен T-Invest.", true);
      return;
    }
    if (!tbankTermsAck.checked) {
      showMessage(tbankMessage, "Подтвердите правила и риски подключения T-Invest.", true);
      return;
    }

    tbankCheck.disabled = true;
    try {
      const result = await api("/api/broker/tbank/accounts", {
        method: "POST",
        body: JSON.stringify({
          credential,
          environment,
          accept_personal_terms: tbankTermsAck.checked,
        }),
      });

      if (!result.accounts || result.accounts.length === 0) {
        showMessage(tbankMessage, "У токена нет доступных открытых счетов.", true);
        return;
      }

      pendingTbankCredential = credential;
      pendingTbankEnvironment = environment;
      tbankToken.value = "";

      result.accounts.forEach((account) => {
        const option = document.createElement("option");
        option.value = account.id;
        const name = account.name || "Брокерский счёт";
        option.textContent = `${name} · ••••${String(account.id).slice(-6)}`;
        tbankAccount.append(option);
      });

      tbankAccountForm.classList.remove("hidden");
      showMessage(tbankMessage, "Токен проверен. Выберите счёт для подключения.");
    } catch (error) {
      resetTbankPreview();
      if (error.status === 400) {
        showMessage(tbankMessage, "T-Invest отклонил токен. Проверьте его и попробуйте снова.", true);
      } else if (error.status === 503) {
        showMessage(tbankMessage, "T-Invest API временно недоступен.", true);
      } else {
        showMessage(tbankMessage, "Не удалось проверить токен.", true);
      }
    } finally {
      tbankCheck.disabled = false;
    }
  });

  tbankAccountForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage(tbankMessage, "");

    if (!pendingTbankCredential || !pendingTbankEnvironment || !tbankAccount.value) {
      showMessage(tbankMessage, "Сначала заново проверьте API-токен.", true);
      resetTbankPreview();
      return;
    }

    tbankConnect.disabled = true;
    try {
      const status = await api("/api/broker/tbank", {
        method: "PUT",
        body: JSON.stringify({
          credential: pendingTbankCredential,
          environment: pendingTbankEnvironment,
          account_id: tbankAccount.value,
          accept_personal_terms: tbankTermsAck.checked,
        }),
      });
      renderTbankStatus(status);
      portfolioLoaded = false;
      void loadPortfolioData({force: true});
      showMessage(tbankMessage, "T-Invest подключён. Токен сохранён в зашифрованном виде.");
    } catch (error) {
      resetTbankPreview();
      tbankForm.classList.remove("hidden");
      if (error.status === 400) {
        showMessage(tbankMessage, "Не удалось подключить выбранный счёт. Проверьте токен.", true);
      } else if (error.status === 503) {
        showMessage(tbankMessage, "T-Invest API временно недоступен.", true);
      } else {
        showMessage(tbankMessage, "Подключение не сохранено.", true);
      }
    } finally {
      tbankConnect.disabled = false;
    }
  });

  tbankDisconnect.addEventListener("click", async () => {
    const confirmed = window.confirm(
      "Отключить T-Invest и удалить сохранённый токен из OmniCIO?"
    );
    if (!confirmed) {
      return;
    }

    tbankDisconnect.disabled = true;
    try {
      await api("/api/broker/tbank", {method: "DELETE"});
      renderTbankStatus({connected: false});
      portfolioLoaded = false;
      tbankTermsAck.checked = false;
      showMessage(tbankMessage, "T-Invest отключён.");
    } catch {
      showMessage(tbankMessage, "Не удалось удалить подключение.", true);
    } finally {
      tbankDisconnect.disabled = false;
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      await api("/api/auth/logout", {method: "POST"});
    } finally {
      pendingTbankCredential = null;
      location.reload();
    }
  });

  renderReleaseInfo();
  applyTheme(storedTheme());
  refreshInstallState();
  void loadState();
})();
