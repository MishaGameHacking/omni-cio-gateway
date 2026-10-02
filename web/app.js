(() => {
  "use strict";

  const authCard = document.querySelector("#auth-card");
  const profilePanel = document.querySelector("#profile-panel");
  const vkidForm = document.querySelector("#vkid-form");
  const vkidLogin = document.querySelector("#vkid-login");
  const authMessage = document.querySelector("#auth-message");
  const accessEyebrow = document.querySelector("#access-eyebrow");
  const accessLead = document.querySelector("#access-lead");
  const accessScope = document.querySelector("#access-scope");
  const homeLoginTitle = document.querySelector("#home-login-title");
  const homeLoginNote = document.querySelector("#home-login-note");
  const accountModeBadge = document.querySelector("#account-mode-badge");
  const investmentProfileForm = document.querySelector("#investment-profile-form");
  const investmentProfileVersion = document.querySelector("#investment-profile-version");
  const investmentProfileCreated = document.querySelector("#investment-profile-created");
  const investmentProfileMessage = document.querySelector("#investment-profile-message");
  const investmentProfileSave = document.querySelector("#investment-profile-save");
  const profileReserveRub = document.querySelector("#profile-reserve-rub");
  const profileWithdrawalRub = document.querySelector("#profile-withdrawal-rub");
  const profileHorizonMonths = document.querySelector("#profile-horizon-months");
  const profileMaxDrawdown = document.querySelector("#profile-max-drawdown");
  const profileLiquidityDays = document.querySelector("#profile-liquidity-days");
  const profileAllowBelowGrade = document.querySelector("#profile-allow-below-grade");

  const profileId = document.querySelector("#profile-id");
  const drawerProfileId = document.querySelector("#drawer-profile-id");
  const profilePageId = document.querySelector("#profile-page-id");
  const supportProfileId = document.querySelector("#support-profile-id");
  const settingsProfileId = document.querySelector("#settings-profile-id");
  const settingsProfileRole = document.querySelector("#settings-profile-role");
  const settingsRegistrationState = document.querySelector("#settings-registration-state");
  const logoutButton = document.querySelector("#logout");
  const deleteAccountStart = document.querySelector("#delete-account-start");
  const deleteAccountForm = document.querySelector("#delete-account-form");
  const deleteAccountProfileId = document.querySelector("#delete-account-profile-id");
  const deleteAccountConfirmation = document.querySelector("#delete-account-confirmation");
  const deleteAccountIrreversible = document.querySelector("#delete-account-irreversible");
  const deleteAccountCancel = document.querySelector("#delete-account-cancel");
  const deleteAccountSubmit = document.querySelector("#delete-account-submit");
  const deleteAccountMessage = document.querySelector("#delete-account-message");
  const appBack = document.querySelector("#app-back");
  const appMenuToggle = document.querySelector("#app-menu-toggle");
  const appDrawer = document.querySelector("#app-drawer");
  const drawerBackdrop = document.querySelector("#drawer-backdrop");
  const drawerClose = document.querySelector("#drawer-close");
  const fullscreenToggle = document.querySelector("#fullscreen-toggle");
  const fullscreenStatus = document.querySelector("#fullscreen-status");
  const copySupportDiagnostics = document.querySelector("#copy-support-diagnostics");
  const supportCopyMessage = document.querySelector("#support-copy-message");

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
  const homeFxState = document.querySelector("#home-fx-state");

  const usdRubCard = document.querySelector("#usd-rub-card");
  const usdRubState = document.querySelector("#usd-rub-state");
  const usdRubPrice = document.querySelector("#usd-rub-price");
  const usdRubChange = document.querySelector("#usd-rub-change");
  const usdRubNote = document.querySelector("#usd-rub-note");
  const usdRubSource = document.querySelector("#usd-rub-source");
  const usdRubTime = document.querySelector("#usd-rub-time");
  const usdRubCbr = document.querySelector("#usd-rub-cbr");
  const usdRubCbrDate = document.querySelector("#usd-rub-cbr-date");
  const usdRubCbrNextRow = document.querySelector("#usd-rub-cbr-next-row");
  const usdRubCbrNext = document.querySelector("#usd-rub-cbr-next");
  const usdRubCbrNextDate = document.querySelector("#usd-rub-cbr-next-date");

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
  const portfolioRetry = document.querySelector("[data-portfolio-retry]");

  const analysisRefresh = document.querySelector("#analysis-refresh");
  const analysisStatus = document.querySelector("#analysis-status");
  const analysisContent = document.querySelector("#analysis-content");
  const analysisCash = document.querySelector("#analysis-cash");
  const analysisCount = document.querySelector("#analysis-count");
  const analysisCoverage = document.querySelector("#analysis-coverage");
  const analysisObservations = document.querySelector("#analysis-observations");
  const analysisClasses = document.querySelector("#analysis-classes");
  const analysisSectors = document.querySelector("#analysis-sectors");
  const analysisSecurities = document.querySelector("#analysis-securities");
  const analysisSources = document.querySelector("#analysis-sources");
  const intelligenceStatus = document.querySelector("#intelligence-status");
  const intelligenceRisks = document.querySelector("#intelligence-risks");
  const intelligencePayouts = document.querySelector("#intelligence-payouts");
  const intelligenceSources = document.querySelector("#intelligence-sources");

  const owlState = document.querySelector("#owl-state");
  const owlLastRefresh = document.querySelector("#owl-last-refresh");
  const owlFxStatus = document.querySelector("#owl-fx-status");
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
    decisions: "Решения",
    system: "Система",
    connections: "Интеграции",
    profile: "Профиль",
    settings: "Настройки",
    support: "Поддержка",
  };

  let currentView = "home";
  let currentProfileId = "";
  let pendingTbankCredential = null;
  let pendingTbankEnvironment = null;
  let deferredInstallPrompt = null;
  let tbankIsConnected = false;
  let portfolioLoaded = false;
  let portfolioRequestInFlight = false;
  let lastPortfolioSnapshot = null;
  let lastPortfolioRefreshAt = 0;
  let analysisInFlight = false;
  let analysisGeneration = 0;
  let lastAnalysisAt = 0;
  let owlTimer = null;
  let usdRubEventSource = null;
  let usdRubFallbackTimer = null;
  let navigationDepth = 0;

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

  const renderAccessMode = (config) => {
    const registrationOpen = config && config.registration_enabled === true;
    const capacity = Number(config && config.registration_max_users) || 1;
    accessEyebrow.textContent = "Персональный инвестиционный кабинет";
    accessLead.textContent = registrationOpen
      ? `Новый пользователь, прошедший VK ID, занимает один из ${capacity} доступных пользовательских слотов. Данные и брокерские подключения изолированы по профилям.`
      : "Регистрация новых аккаунтов закрыта. Уже зарегистрированный пользователь может продолжать вход через свой VK ID.";
    accessScope.textContent = registrationOpen
      ? `Регистрация: лимит ${capacity}`
      : "Регистрация: закрыта";
    homeLoginTitle.textContent = "Вход через VK ID";
    homeLoginNote.textContent = "Только пользовательские права · защищённая сессия OmniCIO";
    accountModeBadge.textContent = "User";
    if (settingsRegistrationState) {
      settingsRegistrationState.textContent = registrationOpen
        ? `Открыта · лимит ${capacity}`
        : "Закрыта";
    }
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

  const mobileDrawerMode = () => window.matchMedia("(max-width: 820px)").matches;

  const closeDrawer = () => {
    document.body.classList.remove("drawer-open");
    appMenuToggle.setAttribute("aria-expanded", "false");
    if (mobileDrawerMode()) {
      appDrawer.setAttribute("aria-hidden", "true");
    } else {
      appDrawer.removeAttribute("aria-hidden");
    }
  };

  const openDrawer = () => {
    if (!mobileDrawerMode()) {
      return;
    }
    drawerBackdrop.hidden = false;
    document.body.classList.add("drawer-open");
    appMenuToggle.setAttribute("aria-expanded", "true");
    appDrawer.setAttribute("aria-hidden", "false");
  };

  const renderView = (view, {scroll = true} = {}) => {
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

    viewPanels.forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.viewPanel !== view);
    });

    appBack.classList.toggle("hidden", view === "home" && navigationDepth === 0);

    if (scroll) {
      window.scrollTo({top: 0, behavior: "auto"});
    }

    if (view === "portfolio" && tbankIsConnected && !portfolioLoaded) {
      void loadPortfolioData();
    }
    if (
      view === "decisions"
      && tbankIsConnected
      && Date.now() - lastAnalysisAt >= 5 * 60 * 1000
    ) {
      void loadAnalysis();
    }
  };

  const viewUrl = (view) => {
    const url = new URL(location.href);
    url.searchParams.delete("auth");
    url.searchParams.delete("auth_error");
    if (view === "home") {
      url.searchParams.delete("view");
    } else {
      url.searchParams.set("view", view);
    }
    return `${url.pathname}${url.search}`;
  };

  const saveCurrentScrollState = () => {
    if (!history.state?.omnicio) {
      return;
    }
    history.replaceState(
      {...history.state, scrollY: window.scrollY},
      "",
      location.href,
    );
  };

  const navigateToView = (view, {replace = false} = {}) => {
    if (!VIEW_TITLES[view]) {
      return;
    }
    if (view === currentView && !replace) {
      closeDrawer();
      return;
    }

    saveCurrentScrollState();
    const nextDepth = replace ? navigationDepth : navigationDepth + 1;
    const state = {omnicio: true, view, depth: nextDepth, scrollY: 0};
    if (replace) {
      history.replaceState(state, "", viewUrl(view));
    } else {
      history.pushState(state, "", viewUrl(view));
    }
    navigationDepth = nextDepth;
    renderView(view);
    closeDrawer();
  };

  const initializeNavigation = () => {
    const params = new URLSearchParams(location.search);
    const requested = params.get("view");
    const initialView = requested && VIEW_TITLES[requested] ? requested : "home";
    const existingDepth = Number(history.state?.depth);
    navigationDepth = history.state?.omnicio && Number.isFinite(existingDepth)
      ? Math.max(0, existingDepth)
      : 0;
    history.replaceState(
      {omnicio: true, view: initialView, depth: navigationDepth, scrollY: 0},
      "",
      viewUrl(initialView),
    );
    renderView(initialView, {scroll: false});
    closeDrawer();
  };

  const goBack = () => {
    closeDrawer();
    if (navigationDepth > 0 && history.state?.omnicio) {
      history.back();
      return;
    }
    if (currentView !== "home") {
      navigateToView("home", {replace: true});
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

  const formatClock = (value) => {
    if (!value) {
      return "—";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return new Intl.DateTimeFormat("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  };

  const formatCalendarDate = (value) => {
    if (!value) {
      return "—";
    }
    const date = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }).format(date);
  };

  const renderUsdRubStreamStatus = (state) => {
    usdRubCard.classList.toggle("is-offline", state === "disconnected");
    usdRubCard.classList.toggle("is-error", state === "unavailable");

    if (state === "disconnected") {
      setStateBadge(usdRubState, "Нет подключения", "state-next");
      setStateBadge(homeFxState, "Нет подключения", "state-next");
      usdRubNote.textContent = "Подключите T-Invest, чтобы получать оперативную котировку.";
      owlFxStatus.textContent = "нет подключения";
      return;
    }

    if (state === "reconnect") {
      setStateBadge(usdRubState, "Нужен токен", "state-next");
      setStateBadge(homeFxState, "Нужен токен", "state-next");
      usdRubNote.textContent = "T-Invest отклонил сохранённый токен. Переподключите счёт.";
      owlFxStatus.textContent = "нужно переподключение";
      return;
    }

    setStateBadge(usdRubState, "Переподключение", "state-next");
    setStateBadge(homeFxState, "Переподключение", "state-next");
    usdRubNote.textContent = usdRubPrice.textContent === "—"
      ? "T-Invest временно не отдаёт котировку. Повторяем запрос с паузой."
      : "Поток временно недоступен. Показана последняя полученная котировка.";
    owlFxStatus.textContent = "переподключение";
  };

  const renderUsdRubQuote = (snapshot) => {
    usdRubCard.classList.remove("is-offline", "is-error");

    usdRubPrice.textContent = formatMoney({
      currency: snapshot.currency,
      value: String(snapshot.price),
    });

    if (snapshot.change !== null && snapshot.change_percent !== null) {
      const changeMoney = formatMoney(
        {currency: snapshot.currency, value: String(snapshot.change)},
        {sign: true},
      );
      usdRubChange.textContent = `${changeMoney} · ${formatPercent(
        snapshot.change_percent,
        {sign: true},
      )}`;
      applySignedClass(usdRubChange, snapshot.change);
    } else {
      usdRubChange.textContent = "Изменение к закрытию недоступно";
      usdRubChange.classList.remove("value-positive", "value-negative");
    }

    const live = snapshot.status === "live";
    setStateBadge(
      usdRubState,
      live ? "Оперативно" : "Последняя котировка",
      live ? "state-ok" : "state-next",
    );
    setStateBadge(
      homeFxState,
      live ? "Работает" : "Последняя цена",
      live ? "state-ok" : "state-next",
    );

    usdRubSource.textContent = snapshot.source === "dealer"
      ? "T-Invest · дилер"
      : "T-Invest · биржа";
    usdRubTime.textContent = formatClock(snapshot.quote_time);
    usdRubNote.textContent = live
      ? "Рыночная котировка T-Invest. Она может отличаться от Google/Morningstar и курса ЦБ РФ."
      : "Последняя доступная котировка T-Invest. Она может отличаться от Google/Morningstar и курса ЦБ РФ.";
    owlFxStatus.textContent = live
      ? `оперативно · ${formatClock(snapshot.quote_time)}`
      : `последняя · ${formatClock(snapshot.quote_time)}`;

    if (snapshot.cbr_reference) {
      usdRubCbr.textContent = formatMoney({
        currency: snapshot.cbr_reference.currency,
        value: String(snapshot.cbr_reference.value),
      });
      usdRubCbrDate.textContent = `официальный курс на ${formatCalendarDate(
        snapshot.cbr_reference.effective_date,
      )}`;
    } else {
      usdRubCbr.textContent = "Недоступен";
      usdRubCbrDate.textContent = "Справочный источник временно не отвечает";
    }

    if (snapshot.cbr_next_reference) {
      usdRubCbrNext.textContent = formatMoney({
        currency: snapshot.cbr_next_reference.currency,
        value: String(snapshot.cbr_next_reference.value),
      });
      usdRubCbrNextDate.textContent = `вступает в силу ${formatCalendarDate(
        snapshot.cbr_next_reference.effective_date,
      )}`;
      usdRubCbrNextRow.classList.remove("hidden");
    } else {
      usdRubCbrNextRow.classList.add("hidden");
      usdRubCbrNext.textContent = "—";
      usdRubCbrNextDate.textContent = "—";
    }
  };

  const loadUsdRubSnapshot = async () => {
    if (!tbankIsConnected) {
      renderUsdRubStreamStatus("disconnected");
      return;
    }
    try {
      const snapshot = await api("/api/market/usd-rub", {method: "GET"});
      renderUsdRubQuote(snapshot);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      renderUsdRubStreamStatus(error.status === 409 ? "reconnect" : "unavailable");
    }
  };

  const stopUsdRubStream = () => {
    if (usdRubEventSource) {
      usdRubEventSource.close();
      usdRubEventSource = null;
    }
    if (usdRubFallbackTimer !== null) {
      window.clearInterval(usdRubFallbackTimer);
      usdRubFallbackTimer = null;
    }
  };

  const startUsdRubStream = () => {
    if (!tbankIsConnected || usdRubEventSource || usdRubFallbackTimer !== null) {
      if (!tbankIsConnected) {
        renderUsdRubStreamStatus("disconnected");
      }
      return;
    }

    if (!("EventSource" in window)) {
      void loadUsdRubSnapshot();
      usdRubFallbackTimer = window.setInterval(() => {
        if (document.visibilityState === "visible") {
          void loadUsdRubSnapshot();
        }
      }, 5 * 1000);
      return;
    }

    const stream = new EventSource("/api/market/usd-rub/stream");
    usdRubEventSource = stream;

    stream.addEventListener("quote", (event) => {
      try {
        renderUsdRubQuote(JSON.parse(event.data));
      } catch {
        renderUsdRubStreamStatus("unavailable");
      }
    });

    stream.addEventListener("status", (event) => {
      try {
        const payload = JSON.parse(event.data);
        renderUsdRubStreamStatus(payload.state || "unavailable");
      } catch {
        renderUsdRubStreamStatus("unavailable");
      }
    });

    stream.onerror = () => {
      renderUsdRubStreamStatus("unavailable");
    };
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
        void loadPortfolioData({force: true});
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
      const blockedLots = numericValue(position.blocked_lots);
      if (position.blocked || blockedLots > 0) {
        const blocked = document.createElement("em");
        blocked.className = "position-blocked";
        blocked.textContent = blockedLots > 0
          ? `Есть блокировка · заявками: ${formatQuantity(position.blocked_lots)}`
          : "Есть биржевая блокировка";
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

  const showPortfolioMode = (mode) => {
    portfolioLoading.classList.toggle("hidden", mode !== "loading");
    portfolioDisconnected.classList.toggle("hidden", mode !== "disconnected");
    portfolioError.classList.toggle("hidden", mode !== "error");
    portfolioContent.classList.toggle("hidden", mode !== "content");
  };

  const renderPortfolio = (snapshot) => {
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

    lastPortfolioSnapshot = snapshot;
    lastPortfolioRefreshAt = Date.now();
    portfolioLoaded = true;
    updateOwlState(snapshot.refreshed_at);
    updateGuard(snapshot);
    showPortfolioMode("content");
    setStateBadge(portfolioStateBadge, "Данные получены", "state-ok");
    setStateBadge(homePortfolioState, "Работает", "state-ok");
  };

  const loadPortfolioData = async ({force = false} = {}) => {
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
      const snapshot = await api("/api/broker/tbank/portfolio", {method: "GET"});
      renderPortfolio(snapshot);
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

  const resetAnalysis = () => {
    analysisGeneration += 1;
    lastAnalysisAt = 0;
    analysisContent.classList.add("hidden");
    [
      analysisObservations,
      analysisClasses,
      analysisSectors,
      analysisSecurities,
      analysisSources,
      intelligenceRisks,
      intelligencePayouts,
      intelligenceSources,
    ].forEach((element) => element.replaceChildren());
    setStateBadge(intelligenceStatus, "Ожидает ежедневный снимок", "state-next");
    analysisStatus.textContent = "Обновите анализ после проверки подключения T-Invest.";
  };

  const renderAnalysisAllocations = (container, allocations) => {
    container.replaceChildren();
    if (!allocations?.length) {
      appendEmptyState(container, "Для этого распределения пока нет оценённых данных.");
      return;
    }

    allocations.forEach((item) => {
      const row = document.createElement("div");
      row.className = "allocation-row analysis-allocation-row";

      const label = document.createElement("div");
      label.className = "allocation-label";
      const name = document.createElement("strong");
      name.textContent = item.label;
      const percent = document.createElement("span");
      percent.textContent = item.nav_percent === null
        ? "—"
        : formatPercent(item.nav_percent);
      label.append(name, percent);

      const amount = document.createElement("div");
      amount.className = "allocation-value";
      amount.textContent = formatMoney({currency: "RUB", value: item.value_rub});

      row.append(label, amount);
      container.append(row);
    });
  };

  const analysisSourceNode = (source) => {
    const label = typeof source.name === "string" && source.name
      ? source.name
      : "Источник";
    try {
      const url = new URL(source.url);
      if (
        url.protocol === "https:"
        && url.hostname === "developer.tbank.ru"
        && url.pathname.startsWith("/invest/")
      ) {
        const link = document.createElement("a");
        link.textContent = label;
        link.href = url.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        return link;
      }
    } catch {
      // A malformed source URL is rendered as inert text, never as a link.
    }
    const text = document.createElement("span");
    text.textContent = label;
    return text;
  };

  const renderAnalysis = (snapshot) => {
    const report = snapshot.analysis;
    const sourceItems = Array.isArray(snapshot.sources) ? snapshot.sources : [];
    const sources = new Map(sourceItems.map((source) => [source.id, source]));

    analysisCash.textContent = report.rub_cash_unblocked === null
      ? "Не подтверждены"
      : formatMoney({currency: "RUB", value: report.rub_cash_unblocked});
    analysisCount.textContent = String(report.security_count);
    analysisCoverage.textContent = report.sector_coverage_percent === null
      ? "Не определено"
      : formatPercent(report.sector_coverage_percent);

    analysisObservations.replaceChildren();
    (report.observations || []).forEach((observation) => {
      const card = document.createElement("article");
      card.className = "analysis-observation";
      card.dataset.priority = String(observation.priority);

      const title = document.createElement("h4");
      title.textContent = observation.title;
      const detail = document.createElement("p");
      detail.textContent = observation.detail;
      const references = document.createElement("div");
      references.className = "analysis-references";

      (observation.source_ids || []).forEach((id) => {
        const source = sources.get(id);
        if (source) {
          references.append(analysisSourceNode(source));
        }
      });

      card.append(title, detail);
      if (references.childElementCount) {
        card.append(references);
      }
      analysisObservations.append(card);
    });
    if (!analysisObservations.childElementCount) {
      appendEmptyState(
        analysisObservations,
        "Дополнительных наблюдений по текущему снимку нет.",
      );
    }

    renderAnalysisAllocations(analysisClasses, report.classes);
    renderAnalysisAllocations(analysisSectors, report.sectors);

    analysisSecurities.replaceChildren();
    (report.securities || []).forEach((security) => {
      const row = document.createElement("tr");

      const instrument = document.createElement("td");
      const name = document.createElement("strong");
      name.textContent = security.name;
      const note = document.createElement("small");
      note.textContent = [
        security.ticker || security.uid,
        INSTRUMENT_LABELS[security.instrument_type] || security.instrument_type,
        security.blocked ? "Есть блокировка" : "",
        security.for_qual_investor === true ? "Для квалифицированных инвесторов" : "",
      ].filter(Boolean).join(" · ");
      instrument.append(name, note);

      const sector = document.createElement("td");
      sector.textContent = security.sector || "Не определён";

      const value = document.createElement("td");
      value.textContent = security.value_rub === null
        ? "Нет подтверждённой оценки в ₽"
        : formatMoney({currency: "RUB", value: security.value_rub});

      const weight = document.createElement("td");
      weight.textContent = security.nav_percent === null
        ? "—"
        : formatPercent(security.nav_percent);

      row.append(instrument, sector, value, weight);
      analysisSecurities.append(row);
    });

    if (!analysisSecurities.childElementCount) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 4;
      empty.textContent = "Ненулевых позиций в инструментах пока нет.";
      row.append(empty);
      analysisSecurities.append(row);
    }

    analysisSources.replaceChildren();
    sourceItems.forEach((source) => {
      const row = document.createElement("div");
      const details = document.createElement("small");
      const state = {
        received: "Получено",
        partial: "Часть данных недоступна",
        not_requested: "Не запрашивалось",
      }[source.status] || "Не подтверждено";
      details.textContent = [
        state,
        formatDateTime(source.retrieved_at),
        Array.isArray(source.methods) ? source.methods.join(", ") : "",
      ].filter(Boolean).join(" · ");
      row.append(analysisSourceNode(source), details);
      analysisSources.append(row);
    });

    const analysisState = {
      needs_reconciliation: "Нужна сверка счёта",
      partial: "Частичное покрытие",
      observed: "Структура получена; проверка эмитентов не завершена",
    }[report.status] || "Статус анализа не подтверждён";
    const environment = snapshot.environment === "sandbox" ? "Песочница" : "Биржа";
    analysisStatus.textContent = [
      analysisState,
      environment,
      snapshot.account_name,
      formatDateTime(snapshot.refreshed_at),
    ].filter(Boolean).join(" · ");

    analysisContent.classList.remove("hidden");
    lastAnalysisAt = Date.now();
  };

  const RISK_REASON_LABELS = {
    tbank_bond_event_contains_default_date: "T-Invest содержит подтверждённую дату дефолта",
    credit_rating_feed_not_verified: "Разрешённый источник кредитного рейтинга не подключён",
    fundamental_data_missing: "Фундаментальные показатели отсутствуют",
    fundamental_data_stale: "Фундаментальные показатели устарели",
    provider_evidence_stale: "Доказательства давно не обновлялись",
    provider_evidence_partial: "Часть доказательных источников недоступна",
    fund_look_through_not_verified: "Состав фонда не подтверждён",
    fixed_charge_coverage_ratio_below_one: "FCCR ниже 1",
    ebitda_negative: "EBITDA отрицательная",
    free_cash_flow_negative_with_debt: "Свободный денежный поток отрицательный при наличии долга",
    current_ratio_below_one: "Коэффициент текущей ликвидности ниже 1",
    net_interest_margin_mrq_negative: "Чистая процентная маржа отрицательная",
    roe_negative: "ROE отрицательный",
    roa_negative: "ROA отрицательный",
  };

  const metricProfileLabel = (value) => ({
    corporate: "корпоративные метрики",
    bank_like: "bank-like метрики",
    unknown: "профиль метрик не определён",
  }[value] || "");

  const intelligenceLabel = (value) => ({
    data_missing: "Данных недостаточно",
    normal: "Норма",
    watch: "Наблюдение",
    elevated: "Повышенный риск",
    critical: "Критический риск",
    confirmed_default: "Подтверждённый дефолт",
    received: "Получено",
    fresh: "Актуально",
    stale: "Устарело",
    not_applicable: "Не применяется",
    partial: "Частично",
    unavailable: "Недоступно",
    announced: "Объявлено",
    scheduled: "Запланировано",
    cancelled: "Отменено",
    paid: "Исполнено",
    defaulted: "Дефолт",
    observed: "Наблюдается",
  }[value] || String(value || "—"));

  const renderIntelligence = (snapshot) => {
    intelligenceRisks.replaceChildren();
    (snapshot.risks || []).forEach((risk) => {
      const row = document.createElement("tr");
      const instrument = document.createElement("td");
      const title = document.createElement("strong");
      title.textContent = risk.ticker || risk.instrument_uid || "Инструмент";
      const detail = document.createElement("small");
      const reasons = Array.isArray(risk.reasons)
        ? risk.reasons.map((reason) => RISK_REASON_LABELS[reason] || reason).join(" · ")
        : "";
      detail.textContent = [
        INSTRUMENT_LABELS[risk.instrument_type] || risk.instrument_type,
        risk.sector || "Сектор не подтверждён",
        metricProfileLabel(risk.evidence?.metric_profile),
        reasons,
      ].filter(Boolean).join(" · ");
      instrument.append(title, detail);

      const state = document.createElement("td");
      state.textContent = intelligenceLabel(risk.state || "data_missing");
      const rating = document.createElement("td");
      rating.textContent = intelligenceLabel(risk.rating_status || "data_missing");
      const fundamentals = document.createElement("td");
      fundamentals.textContent = intelligenceLabel(risk.fundamental_status || "data_missing");
      row.append(instrument, state, rating, fundamentals);
      intelligenceRisks.append(row);
    });
    if (!intelligenceRisks.childElementCount) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 4;
      empty.textContent = "Risk assessment появится после ежедневного доказательного снимка.";
      row.append(empty);
      intelligenceRisks.append(row);
    }

    intelligencePayouts.replaceChildren();
    (snapshot.payouts || []).forEach((event) => {
      const row = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = [
        event.instrument_uid || "Инструмент",
        {
          dividend: "дивиденд",
          coupon: "купон",
          bond_event: "событие облигации",
        }[event.event_type] || event.event_type,
      ].filter(Boolean).join(" · ");
      const details = document.createElement("small");
      const amount = event.amount === null || event.amount === undefined
        ? ""
        : formatMoney({currency: event.currency || "", value: event.amount});
      details.textContent = [
        intelligenceLabel(event.status),
        amount,
        event.expected_at ? "ожидается " + formatDateTime(event.expected_at) : "",
        event.actual_at ? "факт " + formatDateTime(event.actual_at) : "",
        event.record_at ? "реестр " + formatDateTime(event.record_at) : "",
      ].filter(Boolean).join(" · ");
      row.append(title, details);
      intelligencePayouts.append(row);
    });
    if (!intelligencePayouts.childElementCount) {
      appendEmptyState(
        intelligencePayouts,
        "В сохранённом окне нет подтверждённых календарных событий.",
      );
    }

    intelligenceSources.replaceChildren();
    (snapshot.sources || []).forEach((source) => {
      const row = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = (source.provider || "Источник") + " · " + (source.document_type || "document");
      const details = document.createElement("small");
      details.textContent = [
        intelligenceLabel(source.freshness_status),
        source.retrieved_at ? "получено " + formatDateTime(source.retrieved_at) : "",
        Number.isFinite(Number(source.versions)) ? "версий: " + source.versions : "",
      ].filter(Boolean).join(" · ");
      row.append(title, details);
      intelligenceSources.append(row);
    });
    if (!intelligenceSources.childElementCount) {
      appendEmptyState(intelligenceSources, "Evidence ещё не сохранён.");
    }

    const missing = (snapshot.risks || []).filter((item) => item.state === "data_missing").length;
    const defaults = (snapshot.risks || []).filter(
      (item) => item.state === "confirmed_default"
    ).length;
    if (defaults > 0) {
      setStateBadge(
        intelligenceStatus,
        "Подтверждённый дефолт: " + defaults,
        "state-error",
      );
    } else if (snapshot.snapshot_freshness === "stale") {
      setStateBadge(intelligenceStatus, "Доказательства устарели", "state-next");
    } else if (missing > 0 || snapshot.rating_feed_status === "data_missing") {
      setStateBadge(intelligenceStatus, "Неполные данные: " + missing, "state-next");
    } else if (snapshot.status === "pending") {
      setStateBadge(intelligenceStatus, "Ожидает ежедневный снимок", "state-next");
    } else {
      setStateBadge(intelligenceStatus, "Доказательства получены", "state-ok");
    }
  };

  const loadIntelligence = async () => {
    try {
      const snapshot = await api("/api/portfolio/intelligence", {method: "GET"});
      renderIntelligence(snapshot);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      intelligenceRisks.replaceChildren();
      intelligencePayouts.replaceChildren();
      intelligenceSources.replaceChildren();
      setStateBadge(intelligenceStatus, "Evidence временно недоступен", "state-error");
    }
  };

  const loadAnalysis = async () => {
    if (!tbankIsConnected) {
      resetAnalysis();
      analysisStatus.textContent = "Подключите счёт T-Invest для живого анализа.";
      void loadIntelligence();
      return;
    }
    void loadIntelligence();
    if (analysisInFlight) {
      return;
    }

    const generation = analysisGeneration;
    analysisInFlight = true;
    analysisRefresh.disabled = true;
    analysisStatus.textContent = "Проверяем позиции, деньги и справочники T-Invest…";

    try {
      const snapshot = await api("/api/broker/tbank/analysis", {method: "GET"});
      if (generation === analysisGeneration && tbankIsConnected) {
        renderAnalysis(snapshot);
      }
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      if (generation === analysisGeneration) {
        resetAnalysis();
        analysisStatus.textContent = error.status === 409
          ? "Проверьте подключение и действительность токена T-Invest."
          : "Анализ не получен. Данные не подтверждены; попробуйте обновить позже.";
      }
    } finally {
      analysisInFlight = false;
      analysisRefresh.disabled = false;
    }
  };

  const renderTbankSummary = (status) => {
    resetAnalysis();
    homeConnectionCard.classList.remove("is-offline", "is-error");
    topConnectionIndicator.classList.remove("is-offline", "is-error");
    tbankIsConnected = Boolean(status.connected);

    if (!status.connected) {
      portfolioLoaded = false;
      lastPortfolioSnapshot = null;
      lastPortfolioRefreshAt = 0;
      overviewAccount.textContent = "T-Invest не подключён";
      overviewConnectionText.textContent = "Подключите read-only API-токен в разделе «Интеграции».";
      homeConnectionCard.classList.add("is-offline");
      topConnectionIndicator.classList.add("is-offline");
      topConnectionText.textContent = "T-Invest не подключён";
      setStateBadge(homeTbankState, "Не подключено", "state-next");
      setStateBadge(homePortfolioState, "Нет подключения", "state-next");
      setStateBadge(portfolioStateBadge, "Нет подключения", "state-next");
      stopUsdRubStream();
      renderUsdRubStreamStatus("disconnected");
      updateOwlState(null);
      updateGuard(null);
      hunterResults.replaceChildren();
      showMessage(hunterMessage, "Подключите T-Invest, чтобы искать инструменты.");
      showPortfolioMode("disconnected");
      return;
    }

    const environment = status.environment === "sandbox" ? "Песочница" : "Биржа";
    const accountName = status.account_name || "Брокерский счёт";
    overviewAccount.textContent = accountName;
    overviewConnectionText.textContent = `${environment} · соединение подтверждено`;
    topConnectionText.textContent = "T-Invest подключён";
    setStateBadge(homeTbankState, "Работает", "state-ok");
    showMessage(hunterMessage, "");
    startUsdRubStream();
    if (!portfolioLoaded) {
      setStateBadge(homePortfolioState, "Загружаем", "");
      setStateBadge(portfolioStateBadge, "Загружаем", "");
      updateOwlState(null);
      updateGuard(null);
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
    resetAnalysis();
    overviewAccount.textContent = "Не удалось проверить подключение";
    overviewConnectionText.textContent = "Обновите страницу или попробуйте позже.";
    homeConnectionCard.classList.add("is-error");
    topConnectionIndicator.classList.add("is-error");
    topConnectionText.textContent = "Ошибка T-Invest";
    tbankIsConnected = false;
    portfolioLoaded = false;
    lastPortfolioSnapshot = null;
    lastPortfolioRefreshAt = 0;
    stopUsdRubStream();
    renderUsdRubStreamStatus("unavailable");
    setStateBadge(homeTbankState, "Ошибка", "state-error");
    setStateBadge(homePortfolioState, "Ошибка", "state-error");
    setStateBadge(tbankStatusBadge, "Ошибка", "state-error");
    setStateBadge(portfolioStateBadge, "Ошибка", "state-error");
    setStateBadge(owlState, "Ошибка", "state-error");
    setStateBadge(guardState, "Ошибка", "state-error");
    owlLastRefresh.textContent = "—";
    guardBlockedPositions.textContent = "—";
    guardBlockedCash.textContent = "—";
    guardLargestClass.textContent = "—";
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

  const renderInvestmentProfile = (profile) => {
    showMessage(investmentProfileMessage, "");
    if (!profile) {
      investmentProfileVersion.textContent = "Не заполнен";
      investmentProfileCreated.textContent = "Версия ещё не сохранена";
      return;
    }

    investmentProfileVersion.textContent = `v${profile.version}`;
    investmentProfileCreated.textContent = `Сохранено: ${formatDateTime(profile.created_at)}`;
    profileReserveRub.value = String(profile.reserve_rub);
    profileWithdrawalRub.value = String(profile.planned_withdrawal_rub);
    profileHorizonMonths.value = String(profile.horizon_months);
    profileMaxDrawdown.value = String(profile.max_drawdown_percent);
    profileLiquidityDays.value = String(profile.liquidity_horizon_days);
    profileAllowBelowGrade.checked = profile.allow_below_investment_grade === true;
  };

  const loadInvestmentProfile = async () => {
    try {
      const result = await api("/api/profile/investment", {method: "GET"});
      renderInvestmentProfile(result.profile || null);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      showMessage(
        investmentProfileMessage,
        "Не удалось загрузить инвестиционные ограничения.",
        true,
      );
    }
  };

  const showProfile = (profile) => {
    currentProfileId = profile.public_id;
    profileId.textContent = profile.public_id;
    drawerProfileId.textContent = profile.public_id;
    profilePageId.textContent = profile.public_id;
    supportProfileId.textContent = profile.public_id;
    settingsProfileId.textContent = profile.public_id;
    deleteAccountProfileId.textContent = profile.public_id;
    settingsProfileRole.textContent = profile.role === "user" ? "Пользователь" : profile.role;
    authCard.classList.add("hidden");
    profilePanel.classList.remove("hidden");
    initializeNavigation();
    void loadTbankStatus();
    void loadInvestmentProfile();
  };

  const showAuth = () => {
    profilePanel.classList.add("hidden");
    authCard.classList.remove("hidden");
  };

  const showCallbackResult = () => {
    const params = new URLSearchParams(location.search);
    const authError = params.get("auth_error");

    if (authError === "registration") {
      showMessage(authMessage, "Регистрация новых аккаунтов сейчас закрыта. Уже зарегистрированный пользователь может войти через свой VK ID.", true);
    } else if (authError === "capacity") {
      showMessage(authMessage, "Свободных пользовательских аккаунтов сейчас нет: текущий лимит регистрации уже заполнен.", true);
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
    let config = null;
    try {
      config = await api("/api/auth/config", {method: "GET"});
      renderAccessMode(config);
    } catch {
      // A valid existing session can still be rendered if public config is temporarily unavailable.
    }

    try {
      const me = await api("/api/me", {method: "GET"});
      showProfile(me);
      return;
    } catch (error) {
      if (error.status !== 401) {
        showMessage(authMessage, "Не удалось проверить сессию. Обновите страницу.", true);
      }
    }

    showAuth();
    showCallbackResult();

    if (!config) {
      vkidLogin.disabled = true;
      showMessage(authMessage, "Сервис авторизации временно недоступен.", true);
      return;
    }

    if (config.auth_provider !== "vkid" || !config.login_enabled) {
      vkidLogin.disabled = true;
      showMessage(
        authMessage,
        "VK ID ещё не настроен для текущего режима доступа.",
        true,
      );
    }
  };

  const fullscreenDisplayMode = () => (
    window.matchMedia("(display-mode: fullscreen)").matches
  );

  const standaloneMode = () => (
    fullscreenDisplayMode()
    || window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true
  );

  const refreshScreenState = () => {
    if (fullscreenDisplayMode()) {
      fullscreenStatus.textContent = "Полноэкранный режим приложения";
      fullscreenToggle.classList.add("hidden");
      return;
    }
    if (document.fullscreenElement) {
      fullscreenStatus.textContent = "Полноэкранный режим браузера";
      fullscreenToggle.textContent = "Выйти из полного экрана";
      fullscreenToggle.classList.remove("hidden");
      return;
    }
    if (document.fullscreenEnabled && document.documentElement.requestFullscreen) {
      fullscreenStatus.textContent = standaloneMode()
        ? "Режим приложения · можно скрыть системные панели"
        : "Браузер · полный экран включается по нажатию";
      fullscreenToggle.textContent = "На весь экран";
      fullscreenToggle.classList.remove("hidden");
      return;
    }
    fullscreenStatus.textContent = standaloneMode()
      ? "Режим приложения"
      : "Полный экран недоступен в этом браузере";
    fullscreenToggle.classList.add("hidden");
  };

  const refreshInstallState = () => {
    if (standaloneMode()) {
      installStatus.textContent = fullscreenDisplayMode()
        ? "Установлено · полноэкранный режим"
        : "Установлено и открыто как приложение";
      installButton.classList.add("hidden");
      refreshScreenState();
      return;
    }

    if (deferredInstallPrompt) {
      installStatus.textContent = "Можно установить без адресной строки браузера";
      installButton.classList.remove("hidden");
      refreshScreenState();
      return;
    }

    installStatus.textContent = "Открыто в браузере";
    installButton.classList.add("hidden");
    refreshScreenState();
  };

  hunterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void searchHunter();
  });

  document.addEventListener("visibilitychange", () => {
    const visible = document.visibilityState === "visible";
    const stale = Date.now() - lastPortfolioRefreshAt >= 5 * 60 * 1000;

    if (!visible) {
      stopUsdRubStream();
      return;
    }

    if (tbankIsConnected) {
      startUsdRubStream();
    }
    if (tbankIsConnected && stale && !portfolioRequestInFlight) {
      void loadPortfolioData({force: true});
    }
  });

  portfolioRefresh.addEventListener("click", () => {
    void loadPortfolioData({force: true});
  });

  portfolioRetry.addEventListener("click", () => {
    void loadPortfolioData({force: true});
  });

  analysisRefresh.addEventListener("click", () => {
    void loadAnalysis();
  });

  desktopNavItems.forEach((item) => {
    item.addEventListener("click", () => navigateToView(item.dataset.view));
  });

  viewLinks.forEach((item) => {
    item.addEventListener("click", () => navigateToView(item.dataset.goView));
  });

  appMenuToggle.addEventListener("click", () => {
    if (document.body.classList.contains("drawer-open")) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });

  drawerClose.addEventListener("click", closeDrawer);
  drawerBackdrop.addEventListener("click", closeDrawer);
  appBack.addEventListener("click", goBack);

  window.addEventListener("resize", () => {
    if (!mobileDrawerMode()) {
      closeDrawer();
    }
  });

  window.addEventListener("popstate", (event) => {
    const state = event.state;
    if (!state?.omnicio || !VIEW_TITLES[state.view]) {
      return;
    }
    navigationDepth = Math.max(0, Number(state.depth) || 0);
    renderView(state.view, {scroll: false});
    closeDrawer();
    window.requestAnimationFrame(() => {
      window.scrollTo({top: Math.max(0, Number(state.scrollY) || 0), behavior: "auto"});
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && document.body.classList.contains("drawer-open")) {
      closeDrawer();
      appMenuToggle.focus();
    }
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

  fullscreenToggle.addEventListener("click", async () => {
    fullscreenToggle.disabled = true;
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else if (document.fullscreenEnabled && document.documentElement.requestFullscreen) {
        try {
          await document.documentElement.requestFullscreen({navigationUI: "hide"});
        } catch {
          await document.documentElement.requestFullscreen();
        }
      }
    } catch {
      fullscreenStatus.textContent = "Браузер не разрешил полноэкранный режим";
    } finally {
      fullscreenToggle.disabled = false;
      refreshScreenState();
    }
  });

  document.addEventListener("fullscreenchange", refreshScreenState);

  copySupportDiagnostics.addEventListener("click", async () => {
    const release = window.OMNICIO_RELEASE || {};
    const diagnostic = [
      `OmniCIO v${release.version || "—"}`,
      `build ${release.build || "—"}`,
      `profile ${currentProfileId || "—"}`,
    ].join("\n");

    try {
      await navigator.clipboard.writeText(diagnostic);
      showMessage(supportCopyMessage, "Диагностика скопирована.");
    } catch {
      showMessage(supportCopyMessage, "Не удалось скопировать. Укажите ID профиля вручную.", true);
    }
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

  investmentProfileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage(investmentProfileMessage, "");

    if (!investmentProfileForm.reportValidity()) {
      return;
    }

    investmentProfileSave.disabled = true;
    try {
      const result = await api("/api/profile/investment", {
        method: "PUT",
        body: JSON.stringify({
          reserve_rub: profileReserveRub.value,
          planned_withdrawal_rub: profileWithdrawalRub.value,
          horizon_months: Number(profileHorizonMonths.value),
          max_drawdown_percent: profileMaxDrawdown.value,
          liquidity_horizon_days: Number(profileLiquidityDays.value),
          allow_below_investment_grade: profileAllowBelowGrade.checked,
        }),
      });
      renderInvestmentProfile(result.profile);
      showMessage(
        investmentProfileMessage,
        "Новая версия ограничений сохранена. Предыдущие версии остаются в журнале.",
      );
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      if (error.status === 409) {
        showMessage(
          investmentProfileMessage,
          "Для новых финансовых параметров нужны обновлённые документы. Выйдите из аккаунта и войдите через VK ID снова, приняв актуальные версии.",
          true,
        );
        return;
      }
      if (error.status === 409) {
        showMessage(
          investmentProfileMessage,
          "Требуется обновить согласие с правилами. Выйдите из аккаунта и снова войдите через VK ID.",
          true,
        );
        return;
      }
      if (error.status === 422) {
        showMessage(
          investmentProfileMessage,
          "Проверьте резерв, горизонт и допустимую просадку.",
          true,
        );
        return;
      }
      showMessage(
        investmentProfileMessage,
        "Не удалось сохранить профиль. Действующая версия не изменена.",
        true,
      );
    } finally {
      investmentProfileSave.disabled = false;
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

  const closeDeleteAccountForm = () => {
    deleteAccountForm.classList.add("hidden");
    deleteAccountStart.setAttribute("aria-expanded", "false");
    deleteAccountConfirmation.value = "";
    deleteAccountIrreversible.checked = false;
    deleteAccountSubmit.disabled = false;
    deleteAccountCancel.disabled = false;
    showMessage(deleteAccountMessage, "");
  };

  deleteAccountStart.addEventListener("click", () => {
    const opening = deleteAccountForm.classList.contains("hidden");
    if (!opening) {
      closeDeleteAccountForm();
      return;
    }

    deleteAccountForm.classList.remove("hidden");
    deleteAccountStart.setAttribute("aria-expanded", "true");
    showMessage(deleteAccountMessage, "");
    deleteAccountConfirmation.focus();
  });

  deleteAccountCancel.addEventListener("click", () => {
    closeDeleteAccountForm();
    deleteAccountStart.focus();
  });

  deleteAccountForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage(deleteAccountMessage, "");

    const confirmation = deleteAccountConfirmation.value.trim();
    if (confirmation !== currentProfileId) {
      showMessage(
        deleteAccountMessage,
        "ID профиля не совпадает. Введите текущий девятизначный ID полностью.",
        true,
      );
      return;
    }
    if (!deleteAccountIrreversible.checked) {
      showMessage(
        deleteAccountMessage,
        "Подтвердите, что понимаете необратимость удаления.",
        true,
      );
      return;
    }

    deleteAccountSubmit.disabled = true;
    deleteAccountCancel.disabled = true;
    deleteAccountStart.disabled = true;
    stopUsdRubStream();

    try {
      await api("/api/account/delete", {
        method: "POST",
        body: JSON.stringify({
          confirm_public_id: confirmation,
          confirm_irreversible: true,
        }),
      });
      pendingTbankCredential = null;
      location.replace("/");
    } catch (error) {
      deleteAccountSubmit.disabled = false;
      deleteAccountCancel.disabled = false;
      deleteAccountStart.disabled = false;
      if (error.status === 401) {
        location.reload();
        return;
      }
      if (error.status === 400) {
        showMessage(
          deleteAccountMessage,
          "Подтверждение не принято. Проверьте ID профиля и попробуйте снова.",
          true,
        );
        return;
      }
      showMessage(
        deleteAccountMessage,
        "Аккаунт не удалён. Обновите страницу и повторите попытку.",
        true,
      );
    }
  });

  logoutButton.addEventListener("click", async () => {
    stopUsdRubStream();
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
  startOwl();
  void loadState();
})();
