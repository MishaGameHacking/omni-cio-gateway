(() => {
  "use strict";

  let workspace = null;
  let hunterRequest = null;
  let hunterGeneration = 0;

  const requiredElement = (selector) => {
    const element = document.querySelector(selector);
    if (!element) {
      throw new Error(`Required UI element is missing: ${selector}`);
    }
    return element;
  };

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
  const balancingPolicyForm = document.querySelector("#balancing-policy-form");
  const balancingPolicyVersion = document.querySelector("#balancing-policy-version");
  const balancingPolicyCreated = document.querySelector("#balancing-policy-created");
  const balancingPolicyMessage = document.querySelector("#balancing-policy-message");
  const balancingPolicySave = document.querySelector("#balancing-policy-save");
  const balanceMaxInstrument = document.querySelector("#balance-max-instrument");
  const balanceMaxSector = document.querySelector("#balance-max-sector");
  const balanceMaxIssuer = document.querySelector("#balance-max-issuer");
  const balanceMaxGroup = document.querySelector("#balance-max-group");
  const balanceMaxShare = document.querySelector("#balance-max-share");
  const balanceMaxBond = document.querySelector("#balance-max-bond");
  const balanceMaxEtf = document.querySelector("#balance-max-etf");
  const balanceMaxBelowGrade = document.querySelector("#balance-max-below-grade");
  const balanceMaxUnknown = document.querySelector("#balance-max-unknown");
  const balanceMaxTerm = document.querySelector("#balance-max-term");
  const balanceTurnoverBudget = document.querySelector("#balance-turnover-budget");
  const balanceDailyParticipation = document.querySelector("#balance-daily-participation");
  const balanceTaxRate = document.querySelector("#balance-tax-rate");
  const balanceUncertaintyHaircut = document.querySelector("#balance-uncertainty-haircut");
  const balanceCreditHaircut = document.querySelector("#balance-credit-haircut");
  const balanceNoTradeBand = document.querySelector("#balance-no-trade-band");
  const balanceMinReplaceBenefit = document.querySelector("#balance-min-replace-benefit");

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
  const tbankEnvironmentSelect = requiredElement("#tbank-environment");
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
  const recoveryState = requiredElement("#recovery-state");
  const recoveryNote = requiredElement("#recovery-note");
  const recoveryBackupAt = requiredElement("#recovery-backup-at");
  const recoveryObservedAt = requiredElement("#recovery-observed-at");
  const recoverySchedule = requiredElement("#recovery-schedule");
  const recoveryWeekly = requiredElement("#recovery-weekly");
  const recoveryWeeklyAt = requiredElement("#recovery-weekly-at");
  const recoveryRefresh = requiredElement("#recovery-refresh");
  const homePortfolioTotal = requiredElement("#home-portfolio-total");
  const homeDailyChange = requiredElement("#home-daily-change");
  const homeDailyRelative = requiredElement("#home-daily-relative");
  const homeFreeCash = requiredElement("#home-free-cash");
  const homePositionCount = requiredElement("#home-position-count");
  const homeAttentionCount = requiredElement("#home-attention-count");
  const homeSnapshotTime = requiredElement("#home-snapshot-time");
  const homePortfolioSummaryState = requiredElement("#home-portfolio-summary-state");
  const homeAllocation = requiredElement("#home-allocation");
  const homeAttentionStateBadge = requiredElement("#home-attention-state");
  const homeAttentionList = requiredElement("#home-attention-list");

  const cbrMarketStrip = requiredElement("#cbr-market-strip");
  const cbrMarketStripStatus = requiredElement("#cbr-market-strip-status");
  const cbrValueElements = {
    key_rate: [...document.querySelectorAll('[data-cbr-value="key_rate"]')],
    usd_rub: [...document.querySelectorAll('[data-cbr-value="usd_rub"]')],
    eur_rub: [...document.querySelectorAll('[data-cbr-value="eur_rub"]')],
  };
  const cbrItemElements = {
    key_rate: [...document.querySelectorAll('[data-cbr-item="key_rate"]')],
    usd_rub: [...document.querySelectorAll('[data-cbr-item="usd_rub"]')],
    eur_rub: [...document.querySelectorAll('[data-cbr-item="eur_rub"]')],
  };

  const portfolioStateBadge = document.querySelector("#portfolio-state-badge");
  const portfolioRefresh = document.querySelector("#portfolio-refresh");
  const portfolioLoading = document.querySelector("#portfolio-loading");
  const portfolioDisconnected = document.querySelector("#portfolio-disconnected");
  const portfolioError = document.querySelector("#portfolio-error");
  const portfolioErrorText = document.querySelector("#portfolio-error-text");
  const portfolioDataNotice = requiredElement("#portfolio-data-notice");
  const activityList = requiredElement("#activity-list");
  const activityMessage = requiredElement("#activity-message");
  const activityRefresh = requiredElement("#activity-refresh");
  const supportRequestId = requiredElement("#support-request-id");
  const portfolioContent = document.querySelector("#portfolio-content");
  const portfolioTotal = document.querySelector("#portfolio-total");
  const portfolioYield = document.querySelector("#portfolio-yield");
  const portfolioDaily = document.querySelector("#portfolio-daily");
  const portfolioDailyRelative = document.querySelector("#portfolio-daily-relative");
  const portfolioPositionCount = document.querySelector("#portfolio-position-count");
  const portfolioRefreshed = document.querySelector("#portfolio-refreshed");
  const portfolioFreeCash = requiredElement("#portfolio-free-cash");
  const assetAllocation = document.querySelector("#asset-allocation");
  const portfolioAllocationNote = requiredElement("#portfolio-allocation-note");
  const allocationViewButtons = [...document.querySelectorAll("[data-allocation-view]")];
  const cashList = document.querySelector("#cash-list");
  const cashLoadingNote = document.querySelector("#cash-loading-note");
  const positionsList = document.querySelector("#positions-list");
  const positionsTableBody = requiredElement("#positions-table-body");
  const positionsFreshnessNote = requiredElement("#positions-freshness-note");
  const portfolioRetry = document.querySelector("[data-portfolio-retry]");
  const homeHistoryState = requiredElement("#home-history-state");
  const homeHistoryChart = requiredElement("#home-portfolio-history-chart");
  const homeHistoryFacts = requiredElement("#home-history-facts");
  const homeHistoryNote = requiredElement("#home-history-note");
  const portfolioHistoryState = requiredElement("#portfolio-history-state");
  const portfolioHistoryPeriods = requiredElement("#portfolio-history-periods");
  const portfolioHistoryPeriodButtons = [
    ...portfolioHistoryPeriods.querySelectorAll("[data-portfolio-history-days]"),
  ];
  const portfolioHistoryChart = requiredElement("#portfolio-history-chart");
  const portfolioHistoryFacts = requiredElement("#portfolio-history-facts");
  const portfolioHistoryNote = requiredElement("#portfolio-history-note");
  const portfolioDrawdownState = requiredElement("#portfolio-drawdown-state");
  const portfolioDrawdownChart = requiredElement("#portfolio-drawdown-chart");
  const portfolioDrawdownNote = requiredElement("#portfolio-drawdown-note");
  const portfolioCoverageState = requiredElement("#portfolio-coverage-state");
  const portfolioSectorCoverage = requiredElement("#portfolio-sector-coverage");
  const portfolioValuedCount = requiredElement("#portfolio-valued-count");
  const portfolioSnapshotStatus = requiredElement("#portfolio-snapshot-status");
  const portfolioSnapshotTime = requiredElement("#portfolio-snapshot-time");
  const instrumentDetail = requiredElement("#instrument-detail");
  const instrumentDetailTitle = requiredElement("#instrument-detail-title");
  const instrumentDetailSubtitle = requiredElement("#instrument-detail-subtitle");
  const instrumentDetailClose = requiredElement("#instrument-detail-close");
  const instrumentDetailLoading = requiredElement("#instrument-detail-loading");
  const instrumentDetailContent = requiredElement("#instrument-detail-content");
  const instrumentDetailValue = requiredElement("#instrument-detail-value");
  const instrumentDetailWeight = requiredElement("#instrument-detail-weight");
  const instrumentDetailPrice = requiredElement("#instrument-detail-price");
  const instrumentDetailPriceTime = requiredElement("#instrument-detail-price-time");
  const instrumentDetailQuantity = requiredElement("#instrument-detail-quantity");
  const instrumentDetailBlocked = requiredElement("#instrument-detail-blocked");
  const instrumentDetailPnl = requiredElement("#instrument-detail-pnl");
  const instrumentDetailPnlTime = requiredElement("#instrument-detail-pnl-time");
  const instrumentDetailRisk = requiredElement("#instrument-detail-risk");
  const instrumentDetailRiskTime = requiredElement("#instrument-detail-risk-time");
  const instrumentHistoryChart = requiredElement("#instrument-history-chart");
  const instrumentHistoryNote = requiredElement("#instrument-history-note");
  const instrumentEvidenceSummary = requiredElement("#instrument-evidence-summary");
  const instrumentPayouts = requiredElement("#instrument-payouts");
  const instrumentSources = requiredElement("#instrument-sources");
  const instrumentDetailMessage = requiredElement("#instrument-detail-message");
  const instrumentMarketState = requiredElement("#instrument-market-state");
  const instrumentMarketRetry = requiredElement("#instrument-market-retry");
  const instrumentMarketModeButtons = [
    ...requiredElement("#instrument-market-modes").querySelectorAll("[data-market-mode]"),
  ];
  const instrumentMarketPeriodButtons = [
    ...requiredElement("#instrument-market-periods").querySelectorAll("[data-market-period]"),
  ];
  const instrumentMarketChart = requiredElement("#instrument-market-chart");
  const instrumentMarketScrubber = requiredElement("#instrument-market-scrubber");
  const instrumentMarketTooltip = requiredElement("#instrument-market-tooltip");
  const instrumentMarketLastPrice = requiredElement("#instrument-market-last-price");
  const instrumentMarketQuoteTime = requiredElement("#instrument-market-quote-time");
  const instrumentMarketTradingStatus = requiredElement("#instrument-market-trading-status");
  const instrumentMarketSource = requiredElement("#instrument-market-source");
  const instrumentMarketNote = requiredElement("#instrument-market-note");

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
  const balancingStatus = document.querySelector("#balancing-status");
  const balancingFreeCash = document.querySelector("#balancing-free-cash");
  const balancingCandidateCount = document.querySelector("#balancing-candidate-count");
  const balancingEligibleNote = document.querySelector("#balancing-eligible-note");
  const balancingPolicyVersions = document.querySelector("#balancing-policy-versions");
  const balancingScenarios = document.querySelector("#balancing-scenarios");
  const balancingScreening = document.querySelector("#balancing-screening");
  const proposalStatus = document.querySelector("#proposal-status");
  const proposalCreateOptions = document.querySelector("#proposal-create-options");
  const proposalHistory = requiredElement("#proposal-history");
  const proposalMessage = document.querySelector("#proposal-message");
  const executionStatus = requiredElement("#execution-status");
  const executionRefresh = requiredElement("#execution-refresh");
  const executionHistory = requiredElement("#execution-history");
  const executionDetails = requiredElement("#execution-details");
  const executionMessage = requiredElement("#execution-message");
  const liveMandateStatus = requiredElement("#live-mandate-status");
  const liveMandateSummary = requiredElement("#live-mandate-summary");
  const liveMandateForm = requiredElement("#live-mandate-form");
  const liveMaxOrder = requiredElement("#live-max-order");
  const liveMaxDaily = requiredElement("#live-max-daily");
  const liveExpiresAt = requiredElement("#live-expires-at");
  const liveProfileId = requiredElement("#live-profile-id");
  const liveConfirm = requiredElement("#live-confirm");
  const liveMandateSave = requiredElement("#live-mandate-save");
  const liveMandateRevoke = requiredElement("#live-mandate-revoke");
  const liveMandateMessage = requiredElement("#live-mandate-message");

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
    events: "События",
    assets: "Поиск активов",
    strategy: "Стратегия",
    orders: "Сделки",
    payouts: "Выплаты",
    goals: "Цели",
    assistant: "Ассистент",
    notifications: "Уведомления",
    decisions: "Решения",
    system: "Система",
    connections: "Подключения",
    profile: "Профиль",
    settings: "Настройки",
    support: "Поддержка",
  };

  let currentView = "home";
  let currentProfileId = "";
  let strategyLibrary = null;
  let profileContextLost = false;
  let profileCheckInFlight = false;
  let pendingTbankCredential = null;
  let pendingTbankEnvironment = null;
  let deferredInstallPrompt = null;
  let tbankIsConnected = false;
  let portfolioLoaded = false;
  let portfolioRequestInFlight = false;
  let lastPortfolioSnapshot = null;
  let lastPortfolioLoadError = null;
  let lastPortfolioRefreshAt = 0;
  let portfolioGeneration = 0;
  let portfolioFreshnessTimer = null;
  let lastFailedRequestId = "";
  let activityRequestInFlight = false;
  let recoveryGeneration = 0;
  let recoveryTimer = null;
  let portfolioVisualizationLoaded = false;
  let portfolioVisualizationInFlight = false;
  let lastPortfolioVisualization = null;
  let selectedAllocationView = "class";
  let selectedPortfolioHistoryDays = 90;
  let instrumentDetailRequestInFlight = false;
  let instrumentDetailGeneration = 0;
  let instrumentMarketGeneration = 0;
  let instrumentMarketMode = "line";
  let instrumentMarketPeriod = "1m";
  let instrumentMarketPayload = null;
  let instrumentMarketUid = "";
  let instrumentMarketCurrency = "";
  let instrumentMarketQuoteUnit = "money";
  let instrumentMarketEventSource = null;
  let instrumentMarketRetryTimer = null;
  let instrumentMarketRetryCount = 0;
  let analysisInFlight = false;
  let analysisGeneration = 0;
  let lastAnalysisAt = 0;
  let proposalRequestInFlight = false;
  let executionRequestInFlight = false;
  let liveMandateRequestInFlight = false;
  let liveOperatorEnabled = false;
  let liveMandate = null;
  let liveOperatorMaxOrder = 0;
  let liveOperatorMaxDaily = 0;
  let connectedTbankEnvironment = null;
  let tbankAccountId = null;
  let owlTimer = null;
  let cbrIndicatorTimer = null;
  let cbrIndicatorsLoaded = false;
  let lastCbrIndicatorRefreshAt = 0;
  let navigationDepth = 0;
  const homeAttentionBuckets = {
    connection: null,
    portfolio: null,
    proposals: null,
  };

  const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  const INSTRUMENT_MARKET_MAX_RETRIES = 6;

  const apiPath = (path) => {
    if (typeof path !== "string" || !path.startsWith("/api/")) {
      throw new TypeError("API path must be same-origin and start with /api/");
    }
    const url = new URL(path, window.location.origin);
    if (
      url.origin !== window.location.origin
      || !url.pathname.startsWith("/api/")
      || url.hash
    ) {
      throw new TypeError("API path escaped the same-origin API boundary");
    }
    return url;
  };

  const uuidPathSegment = (value) => {
    const segment = String(value || "");
    if (!UUID_PATTERN.test(segment)) {
      throw new TypeError("API path UUID is invalid");
    }
    return segment.toLowerCase();
  };

  const instrumentPathSegment = (value) => {
    const segment = String(value || "");
    if (
      segment.length < 1
      || segment.length > 128
      || segment !== segment.trim()
      || /[\\/?#\u0000-\u001f\u007f]/u.test(segment)
    ) {
      throw new TypeError("Instrument path segment is invalid");
    }
    return encodeURIComponent(segment);
  };

  const executionActionSegment = (value) => {
    if (!["advance", "cancel"].includes(value)) {
      throw new TypeError("Execution action is invalid");
    }
    return value;
  };

  const apiErrorMessage = (response, body) => {
    if (body && typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
    const fallbackByStatus = {
      413: "Запрос слишком большой. Проверьте введённые данные и попробуйте снова.",
      422: "Проверьте формат и допустимые значения полей. Изменения не применены.",
      429: "Слишком много запросов. Подождите немного и повторите действие.",
      502: "Сервис временно недоступен. Изменения не подтверждены.",
      503: "Сервис временно перегружен. Изменения не подтверждены.",
      504: "Сервис не успел ответить. Проверьте состояние перед повтором.",
    };
    return fallbackByStatus[response.status] || "Запрос не выполнен. Проверьте состояние и повторите.";
  };

  const profileContextError = () => Object.assign(new Error("profile_context_changed"), {status: 409});

  const pauseProfileContext = () => {
    if (profileContextLost) return;
    profileContextLost = true;
    resetTbankPreview();
    tbankToken.value = "";
    tbankTermsAck.checked = false;
    stopCbrIndicators();
    window.clearInterval(owlTimer);
    clearTimeout(recoveryTimer);
    recoveryGeneration += 1;
    invalidatePortfolioRequest();
    resetAnalysis();
    closeDrawer();
    profilePanel.inert = true;
    profilePanel.classList.add("hidden");
    authCard.classList.add("hidden");
    requiredElement("#profile-context-panel").classList.remove("hidden");
    requiredElement("#profile-context-reload").focus();
  };

  const requireServerMode = () => {
    if (workspace?.isDemo()) throw Object.assign(new Error("demo_mode_no_server_access"), {status: 0});
  };

  const api = async (path, options = {}) => {
    requireServerMode();
    if (!navigator.onLine && !["GET", "HEAD"].includes(options.method || "GET")) throw Object.assign(new Error("Нет сети. Изменение не отправлено."), {status: 0});
    if (profileContextLost) throw profileContextError();
    const headers = new Headers(options.headers);
    headers.set("Content-Type", "application/json");
    if (currentProfileId) headers.set("X-Omnicio-Profile", currentProfileId);
    const response = await fetch(apiPath(path), {
      cache: "no-store",
      credentials: "same-origin",
      ...options,
      headers,
    });
    requireServerMode();
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (profileContextLost) throw profileContextError();
    if (!response.ok) {
      const error = new Error(apiErrorMessage(response, body));
      error.status = response.status;
      const requestId = response.headers.get("X-Request-ID") || "";
      error.requestId = /^[0-9a-f]{32}$/.test(requestId) ? requestId : "";
      if (error.requestId) {
        lastFailedRequestId = error.requestId;
        supportRequestId.textContent = error.requestId;
      }
      if ((currentProfileId && error.status === 401)
        || ["profile_context_changed", "profile_context_required", "settings_owner_conflict"].includes(error.message)) {
        pauseProfileContext();
        error.message = "profile_context_changed";
        error.status = 409;
      }
      throw error;
    }
    return body;
  };

  const errorReference = (error) => error?.requestId ? ` Код обращения: ${error.requestId}.` : "";

  const ACTIVITY_LABELS = {
    account_created: "Аккаунт создан",
    login_succeeded: "Вход через VK ID",
    tbank_connected: "Подключение T-Invest сохранено",
    tbank_disconnected: "T-Invest отключён",
    investment_profile_saved: "Профиль капитала сохранён",
    balancing_policy_saved: "Лимиты портфеля сохранены",
    support_sessions_revoked: "Сеансы входа завершены поддержкой",
  };

  const loadAccountActivity = async () => {
    if (activityRequestInFlight || !currentProfileId) return;
    activityRequestInFlight = true;
    activityRefresh.disabled = true;
    showMessage(activityMessage, "Загружаем действия…");
    try {
      const payload = await api("/api/me/activity", {method: "GET"});
      activityList.replaceChildren();
      (payload.events || []).forEach((event) => {
        if (!Object.hasOwn(ACTIVITY_LABELS, event.event_type)) return;
        const row = document.createElement("li");
        const label = document.createElement("span");
        label.textContent = ACTIVITY_LABELS[event.event_type];
        const time = document.createElement("time");
        time.dateTime = event.created_at;
        time.textContent = formatDateTime(event.created_at);
        row.append(label, time);
        activityList.append(row);
      });
      showMessage(activityMessage, activityList.children.length ? "" : "Событий пока нет.");
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      showMessage(activityMessage, "Не удалось обновить журнал. Попробуйте позже." + errorReference(error), true);
    } finally {
      activityRequestInFlight = false;
      activityRefresh.disabled = false;
    }
  };

  const showMessage = (element, text, isError = false) => {
    element.textContent = text;
    element.classList.toggle("error", isError);
  };

  const validateFormWithMessage = (form, messageElement, fallback) => {
    if (form.checkValidity()) {
      return true;
    }
    const invalid = form.querySelector(":invalid");
    form.reportValidity();
    const label = invalid?.labels?.[0]?.textContent
      ?.replace(/\s+/g, " ")
      .trim();
    showMessage(
      messageElement,
      label ? `${fallback} Поле «${label}».` : fallback,
      true,
    );
    invalid?.focus();
    return false;
  };

  const localDateTimeInputValue = (date) => {
    const pad = (value) => String(value).padStart(2, "0");
    return [
      date.getFullYear(),
      "-",
      pad(date.getMonth() + 1),
      "-",
      pad(date.getDate()),
      "T",
      pad(date.getHours()),
      ":",
      pad(date.getMinutes()),
    ].join("");
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

  const RECOVERY_STATES = {
    fresh: ["Копия создана", "Ежедневное копирование включено. Недельная копия за текущую неделю подтверждена.", "state-ok"],
    missing: ["Копия не найдена", "Наличие готовой резервной копии пока не подтверждено.", "state-error"],
    backup_stale: ["Копия устарела", "Последней подтверждённой копии больше суток. Требуется проверка сервиса.", "state-error"],
    check_stale: ["Проверка устарела", "Состояние резервных копий давно не проверялось. Показаны последние известные даты.", "state-next"],
    schedule_attention: ["Нужно внимание", "Копия есть, но ежедневное хранение семи копий не подтверждено.", "state-next"],
    weekly_attention: ["Нужно внимание", "Свежая копия есть. Недельная история пока не подтверждена — требуется проверка сервиса.", "state-next"],
    unavailable: ["Нет подтверждения", "Не удалось подтвердить состояние резервных копий. Попробуйте обновить статус позже.", "state-next"],
  };

  const loadRecoveryStatus = async () => {
    if (!currentProfileId || profilePanel.classList.contains("hidden")) return;
    const generation = ++recoveryGeneration;
    clearTimeout(recoveryTimer);
    recoveryRefresh.disabled = true;
    setStateBadge(recoveryState, "Проверяем", "");
    recoveryNote.textContent = "Проверяем состояние резервных копий…";
    recoveryWeekly.textContent = "Проверяем…";
    try {
      const payload = await api("/api/system/recovery", {method: "GET"});
      if (generation !== recoveryGeneration) return;
      const state = Object.hasOwn(RECOVERY_STATES, payload.status) ? payload.status : "unavailable";
      const [label, note, badge] = RECOVERY_STATES[state];
      setStateBadge(recoveryState, label, badge);
      recoveryNote.textContent = note;
      recoveryBackupAt.textContent = formatDateTime(payload.backup?.observed_at);
      recoveryObservedAt.textContent = formatDateTime(payload.freshness?.observed_at);
      recoverySchedule.textContent = payload.daily_schedule === true
        ? `Ежедневно · копий для хранения: ${payload.retention_copies}` : "Не подтверждено";
      recoveryWeeklyAt.textContent = formatDateTime(payload.weekly?.observed_at);
      const weeklyCopies = payload.weekly?.available_copies;
      const weeklyConfirmed = Number.isInteger(weeklyCopies) && weeklyCopies >= 1 && weeklyCopies <= 4
        && payload.weekly?.retention_copies === 4 && payload.weekly?.status === "fresh";
      const weeklyProgress = weeklyCopies < 4 ? " История пополняется по неделям." : "";
      recoveryWeekly.textContent = weeklyConfirmed
        ? `Создано ${weeklyCopies} из 4.${weeklyProgress}`
        : "Не подтверждено";
      if (state === "fresh") {
        const deadline = Math.min(Date.parse(payload.freshness?.valid_until),
          Date.parse(payload.backup?.valid_until), Date.parse(payload.weekly?.valid_until));
        const remaining = deadline - Date.parse(payload.checked_at);
        if (Number.isFinite(remaining) && remaining > 0) {
          recoveryTimer = window.setTimeout(() => { void loadRecoveryStatus(); }, Math.min(remaining + 50, 2147483647));
        }
      }
    } catch (error) {
      if (generation !== recoveryGeneration) return;
      setStateBadge(recoveryState, "Нет подтверждения", "state-next");
      recoveryNote.textContent = RECOVERY_STATES.unavailable[1] + errorReference(error);
      recoveryBackupAt.textContent = "—";
      recoveryObservedAt.textContent = "—";
      recoverySchedule.textContent = "Не подтверждено";
      recoveryWeekly.textContent = "Не подтверждено";
      recoveryWeeklyAt.textContent = "—";
    } finally {
      if (generation === recoveryGeneration) recoveryRefresh.disabled = false;
    }
  };

  const renderAccessMode = (config) => {
    const registrationOpen = config?.registration_enabled === true;
    const capacity = Number(config?.registration_max_users) || 1;
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
      return ["light", "dark", "auto"].includes(value) ? value : "auto";
    } catch {
      return "auto";
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
      themeMeta.content = resolved === "dark" ? "#07111f" : "#f4f7fb";
    }
    themeButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeOption === preference));
    });
  };

  const mobileDrawerMode = () => window.matchMedia("(max-width: 1199px)").matches;

  const closeDrawer = () => {
    const hadFocus = appDrawer.contains(document.activeElement);
    document.body.classList.remove("drawer-open");
    appDrawer.inert = mobileDrawerMode();
    drawerBackdrop.hidden = true;
    if (hadFocus && mobileDrawerMode()) appMenuToggle.focus();
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
    appDrawer.inert = false;
    drawerBackdrop.hidden = false;
    document.body.classList.add("drawer-open");
    appMenuToggle.setAttribute("aria-expanded", "true");
    appDrawer.setAttribute("aria-hidden", "false");
    drawerClose.focus();
  };

  const renderView = (view, {scroll = true} = {}) => {
    if (!VIEW_TITLES[view]) {
      return;
    }

    currentView = view;
    document.title = `${VIEW_TITLES[view]} · OmniCIO`;
    workspace?.onView(view);
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

    if (view !== "portfolio") {
      stopInstrumentMarketStream();
    } else if (
      instrumentMarketUid
      && !instrumentDetail.classList.contains("hidden")
      && document.visibilityState === "visible"
    ) {
      startInstrumentMarketStream();
    }
    if (scroll) {
      window.scrollTo({top: 0, behavior: "auto"});
    }

    if (view === "portfolio" && tbankIsConnected && !portfolioLoaded) {
      void loadPortfolioData();
    } else if (view === "portfolio" && !portfolioVisualizationLoaded) {
      void loadPortfolioVisualization();
    }
    if (view === "profile") void loadAccountActivity();
    if (view === "settings") void loadRecoveryStatus();
    if (
      ["decisions", "events", "payouts"].includes(view)
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
    viewTitle.focus({preventScroll: true});
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

  const formatExactDateTime = (value) => {
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

  const formatCbrNumber = (
    value,
    {minimumFractionDigits = 2, maximumFractionDigits = 4} = {},
  ) => {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      throw new TypeError("Bank of Russia indicator value is invalid");
    }
    return new Intl.NumberFormat("ru-RU", {
      minimumFractionDigits,
      maximumFractionDigits,
    }).format(number);
  };

  const setCbrIndicator = (key, text, title) => {
    for (const element of cbrValueElements[key] || []) {
      element.textContent = text;
    }
    for (const element of cbrItemElements[key] || []) {
      element.title = title;
    }
  };

  const renderCbrIndicators = (snapshot) => {
    const keyRate = snapshot?.key_rate;
    const usd = snapshot?.usd_rub;
    const eur = snapshot?.eur_rub;
    if (!keyRate || !usd || !eur) {
      throw new TypeError("Bank of Russia indicator payload is incomplete");
    }

    const keyRateText = `${formatCbrNumber(keyRate.value, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}%`;
    const usdText = `${formatCbrNumber(usd.value)} ₽`;
    const eurText = `${formatCbrNumber(eur.value)} ₽`;
    const source = snapshot.source === "Bank of Russia" ? "Банк России" : "ЦБ РФ";

    setCbrIndicator(
      "key_rate",
      keyRateText,
      `${source} · действует с ${formatCalendarDate(keyRate.effective_date)}`,
    );
    setCbrIndicator(
      "usd_rub",
      usdText,
      `${source} · официальный курс на ${formatCalendarDate(usd.effective_date)}`,
    );
    setCbrIndicator(
      "eur_rub",
      eurText,
      `${source} · официальный курс на ${formatCalendarDate(eur.effective_date)}`,
    );

    const cached = snapshot.freshness === "cached";
    if (!cached && snapshot.freshness !== "fresh") {
      throw new TypeError("Bank of Russia indicator freshness is invalid");
    }

    cbrMarketStrip.classList.toggle("is-unavailable", cached);
    cbrMarketStripStatus.textContent = cached
      ? (
        `Банк России временно недоступен. Последние значения: ставка ${keyRateText}, `
        + `доллар ${usdText}, евро ${eurText}.`
      )
      : (
        `Банк России: ключевая ставка ${keyRateText}, доллар ${usdText}, `
        + `евро ${eurText}.`
      );
    setStateBadge(
      homeFxState,
      cached ? "Последние данные" : "Актуально",
      cached ? "state-next" : "state-ok",
    );
    owlFxStatus.textContent = cached
      ? `последние данные · ${formatCalendarDate(usd.effective_date)}`
      : `ЦБ РФ · ${formatCalendarDate(usd.effective_date)}`;
    cbrIndicatorsLoaded = true;
    lastCbrIndicatorRefreshAt = Date.now();
  };

  const renderCbrIndicatorFailure = () => {
    cbrMarketStrip.classList.add("is-unavailable");
    if (cbrIndicatorsLoaded) {
      cbrMarketStripStatus.textContent = (
        "Банк России временно недоступен. Показаны последние успешно полученные значения."
      );
      setStateBadge(homeFxState, "Последние данные", "state-next");
      owlFxStatus.textContent = "последние полученные данные";
      return;
    }

    cbrMarketStripStatus.textContent = "Официальные показатели Банка России временно недоступны.";
    setStateBadge(homeFxState, "Недоступно", "state-next");
    owlFxStatus.textContent = "временно недоступно";
  };

  const loadCbrIndicators = async () => {
    try {
      const snapshot = await api("/api/market/cbr-indicators", {method: "GET"});
      renderCbrIndicators(snapshot);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      renderCbrIndicatorFailure();
    }
  };

  const startCbrIndicators = () => {
    void loadCbrIndicators();
    if (cbrIndicatorTimer !== null) {
      return;
    }
    cbrIndicatorTimer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void loadCbrIndicators();
      }
    }, 5 * 60 * 1000);
  };

  const stopCbrIndicators = () => {
    if (cbrIndicatorTimer !== null) {
      window.clearInterval(cbrIndicatorTimer);
      cbrIndicatorTimer = null;
    }
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

    setStateBadge(owlState, "Снимок получен", "state-ok");
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
    items = workspace?.filterAssets(items || []) || items;
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
    workspace?.decorateAssets(items);
  };

  const searchHunter = async () => {
    const query = hunterQuery.value.trim();
    const generation = ++hunterGeneration;
    hunterRequest?.abort();
    hunterRequest = new AbortController();
    hunterSearch.disabled = false;
    hunterSearch.textContent = "Найти";
    showMessage(hunterMessage, "");
    if (workspace?.isDemo()) {
      const items = workspace.demoSearch(query);
      workspace.setCatalog(items);
      renderHunterResults(items);
      showMessage(hunterMessage, `Демонстрационные инструменты: ${items.length}. Данные вымышлены.`);
      return;
    }

    if (!tbankIsConnected) {
      showMessage(hunterMessage, "Сначала подключите T-Invest.", true);
      return;
    }
    if (!query || query.length > 64) {
      showMessage(hunterMessage, "Введите тикер или название инструмента.", true);
      return;
    }

    hunterSearch.disabled = true;
    hunterSearch.textContent = "Ищем…";
    try {
      const payload = await api(
        `/api/broker/tbank/instruments/search?q=${encodeURIComponent(query)}`,
        {method: "GET", signal: hunterRequest.signal},
      );
      if (generation !== hunterGeneration) return;
      workspace?.setCatalog(payload.items || []);
      renderHunterResults(payload.items || []);
      showMessage(
        hunterMessage,
        payload.items?.length
          ? `Найдено: ${payload.items.length}. Это поиск, а не инвестиционная рекомендация.`
          : "Совпадений не найдено.",
      );
    } catch (error) {
      if (error.name === "AbortError" || generation !== hunterGeneration) return;
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
      if (generation === hunterGeneration) {
        hunterSearch.disabled = false;
        hunterSearch.textContent = "Найти";
      }
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

  const renderAllocationRows = (
    container,
    totals,
    {limit = null, emptyMessage = "T-Invest не вернул распределение по классам активов."} = {},
  ) => {
    container.replaceChildren();
    const positive = (totals || []).filter((item) => numericValue(item.money?.value) > 0);
    const sum = positive.reduce((total, item) => total + numericValue(item.money.value), 0);
    if (!positive.length || sum <= 0) {
      appendEmptyState(container, emptyMessage);
      return;
    }

    const ordered = positive
      .sort((left, right) => numericValue(right.money.value) - numericValue(left.money.value));
    const visible = Number.isInteger(limit) && limit > 0 ? ordered.slice(0, limit) : ordered;

    visible.forEach((item) => {
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
      track.setAttribute("role", "img");
      track.setAttribute(
        "aria-label",
        `${ASSET_LABELS[item.kind] || item.kind}: ${share.toFixed(1)}%`,
      );
      const fill = document.createElement("div");
      fill.className = "allocation-fill";
      fill.style.width = `${share}%`;
      track.append(fill);

      const amount = document.createElement("div");
      amount.className = "allocation-value";
      amount.textContent = formatMoney(item.money);

      row.append(label, track, amount);
      container.append(row);
    });
  };

  const renderAllocation = (totals) => {
    renderAllocationRows(assetAllocation, totals);
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

  const storedMoney = (value, currency = "RUB") => {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return "—";
    }
    return formatMoney({currency, value: String(number)});
  };

  const storedPercent = (value, {sign = false} = {}) => {
    const number = Number(value);
    return Number.isFinite(number) ? formatPercent(number, {sign}) : "—";
  };

  const riskStateLabel = (value) => ({
    data_missing: "Данных недостаточно",
    normal: "Норма",
    watch: "Наблюдение",
    elevated: "Повышенный риск",
    critical: "Критический риск",
    confirmed_default: "Подтверждённый дефолт",
  }[value] || String(value || "Не подтверждено"));

  const riskStateClass = (value) => {
    if (value === "confirmed_default" || value === "critical") {
      return "state-error";
    }
    if (value === "watch" || value === "elevated" || value === "data_missing") {
      return "state-next";
    }
    return value === "normal" ? "state-ok" : "";
  };

  const setChartFacts = (container, history) => {
    const values = history
      .map((item) => ({
        value: Number(item.nav_rub),
        capturedAt: item.captured_at,
      }))
      .filter((item) => Number.isFinite(item.value));
    const cells = [...container.querySelectorAll("dd")];
    if (!values.length || cells.length < 4) {
      cells.forEach((cell) => {
        cell.textContent = "—";
      });
      return;
    }
    const minimum = values.reduce(
      (current, item) => item.value < current.value ? item : current,
      values[0],
    );
    const maximum = values.reduce(
      (current, item) => item.value > current.value ? item : current,
      values[0],
    );
    const first = values[0];
    const last = values[values.length - 1];
    cells[0].textContent = `${storedMoney(first.value)} · ${formatDateTime(first.capturedAt)}`;
    cells[1].textContent = storedMoney(minimum.value);
    cells[2].textContent = storedMoney(maximum.value);
    cells[3].textContent = `${storedMoney(last.value)} · ${formatDateTime(last.capturedAt)}`;
  };

  const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

  const chartNode = (name, attributes = {}) => {
    const node = document.createElementNS(SVG_NAMESPACE, name);
    Object.entries(attributes).forEach(([key, value]) => {
      node.setAttribute(key, String(value));
    });
    return node;
  };

  const renderSeriesChart = (
    svg,
    points,
    {
      valueKey = "value",
      timeKey = "captured_at",
      minimumPoints = 2,
      zeroLine = false,
    } = {},
  ) => {
    svg.replaceChildren();
    const clean = (points || [])
      .map((item) => ({
        time: new Date(item?.[timeKey]).getTime(),
        value: Number(item?.[valueKey]),
      }))
      .filter((item) => Number.isFinite(item.time) && Number.isFinite(item.value));
    if (clean.length < minimumPoints) {
      return false;
    }

    const viewBox = String(svg.getAttribute("viewBox") || "0 0 900 260")
      .split(/\s+/u)
      .map(Number);
    const width = Number.isFinite(viewBox[2]) ? viewBox[2] : 900;
    const height = Number.isFinite(viewBox[3]) ? viewBox[3] : 260;
    const padX = 24;
    const padY = 20;
    const times = clean.map((item) => item.time);
    const values = clean.map((item) => item.value);
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);
    let minValue = Math.min(...values);
    let maxValue = Math.max(...values);
    if (zeroLine) {
      minValue = Math.min(minValue, 0);
      maxValue = Math.max(maxValue, 0);
    }
    if (minValue === maxValue) {
      const padding = Math.max(Math.abs(minValue) * 0.02, 1);
      minValue -= padding;
      maxValue += padding;
    }
    const timeSpan = Math.max(maxTime - minTime, 1);
    const valueSpan = Math.max(maxValue - minValue, 1);

    const x = (time) => padX + ((time - minTime) / timeSpan) * (width - padX * 2);
    const y = (value) => (
      padY + ((maxValue - value) / valueSpan) * (height - padY * 2)
    );

    for (let index = 0; index < 4; index += 1) {
      const lineY = padY + ((height - padY * 2) * index) / 3;
      const grid = chartNode("line", {
        x1: padX,
        y1: lineY,
        x2: width - padX,
        y2: lineY,
        class: "portfolio-chart-grid",
      });
      svg.append(grid);
    }
    if (zeroLine && minValue < 0 && maxValue > 0) {
      svg.append(chartNode("line", {
        x1: padX,
        y1: y(0),
        x2: width - padX,
        y2: y(0),
        class: "portfolio-chart-zero",
      }));
    }

    const path = clean
      .map((item, index) => (
        `${index === 0 ? "M" : "L"} ${x(item.time).toFixed(2)} ${y(item.value).toFixed(2)}`
      ))
      .join(" ");
    if (!zeroLine) {
      const firstPoint = clean[0];
      const lastPoint = clean[clean.length - 1];
      svg.append(chartNode("path", {
        d: `${path} L ${x(lastPoint.time).toFixed(2)} ${(height - padY).toFixed(2)} L ${x(firstPoint.time).toFixed(2)} ${(height - padY).toFixed(2)} Z`,
        class: "portfolio-chart-area",
      }));
    }
    svg.append(chartNode("path", {
      d: path,
      class: "portfolio-chart-line",
      fill: "none",
    }));

    const first = clean[0];
    const last = clean[clean.length - 1];
    [first, last].forEach((item) => {
      svg.append(chartNode("circle", {
        cx: x(item.time),
        cy: y(item.value),
        r: 4,
        class: "portfolio-chart-point",
      }));
    });
    return true;
  };

  const finiteMarketNumber = (value) => {
    if (
      value === null
      || value === undefined
      || (typeof value === "string" && !value.trim())
    ) {
      return null;
    }
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  };

  const marketPriceText = (value) => {
    const numeric = finiteMarketNumber(value);
    if (numeric === null) {
      return "—";
    }
    const formatted = new Intl.NumberFormat("ru-RU", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 9,
    }).format(numeric);
    if (instrumentMarketQuoteUnit === "point") {
      return `${formatted} п.`;
    }
    if (instrumentMarketCurrency) {
      return formatMoney({
        currency: instrumentMarketCurrency,
        value: String(value),
      });
    }
    return formatted;
  };

  const cleanMarketCandles = (candles) => (Array.isArray(candles) ? candles : [])
    .map((candle) => ({
      ...candle,
      timestamp: new Date(candle?.time).getTime(),
      openValue: finiteMarketNumber(candle?.open),
      highValue: finiteMarketNumber(candle?.high),
      lowValue: finiteMarketNumber(candle?.low),
      closeValue: finiteMarketNumber(candle?.close),
    }))
    .filter((candle) => (
      Number.isFinite(candle.timestamp)
      && candle.openValue !== null
      && candle.highValue !== null
      && candle.lowValue !== null
      && candle.closeValue !== null
      && candle.highValue >= candle.lowValue
      && candle.openValue >= candle.lowValue
      && candle.openValue <= candle.highValue
      && candle.closeValue >= candle.lowValue
      && candle.closeValue <= candle.highValue
    ))
    .sort((left, right) => left.timestamp - right.timestamp);

  const renderMarketCandles = (svg, candles) => {
    svg.replaceChildren();
    const clean = cleanMarketCandles(candles);
    if (!clean.length) {
      return false;
    }

    const viewBox = String(svg.getAttribute("viewBox") || "0 0 900 320")
      .split(/\s+/u)
      .map(Number);
    const width = Number.isFinite(viewBox[2]) ? viewBox[2] : 900;
    const height = Number.isFinite(viewBox[3]) ? viewBox[3] : 320;
    const padX = 30;
    const padY = 22;
    const plotWidth = width - padX * 2;
    const plotHeight = height - padY * 2;
    let minValue = Math.min(...clean.map((item) => item.lowValue));
    let maxValue = Math.max(...clean.map((item) => item.highValue));
    if (minValue === maxValue) {
      const padding = Math.max(Math.abs(minValue) * 0.01, 1);
      minValue -= padding;
      maxValue += padding;
    }
    const valueSpan = maxValue - minValue;
    const y = (value) => padY + ((maxValue - value) / valueSpan) * plotHeight;
    const step = plotWidth / clean.length;
    const bodyWidth = Math.max(1.5, Math.min(12, step * 0.62));

    for (let index = 0; index < 4; index += 1) {
      const lineY = padY + (plotHeight * index) / 3;
      svg.append(chartNode("line", {
        x1: padX,
        y1: lineY,
        x2: width - padX,
        y2: lineY,
        class: "portfolio-chart-grid",
      }));
    }

    clean.forEach((candle, index) => {
      const x = padX + step * (index + 0.5);
      let direction = "market-candle-flat";
      if (candle.closeValue > candle.openValue) {
        direction = "market-candle-up";
      } else if (candle.closeValue < candle.openValue) {
        direction = "market-candle-down";
      }
      const incomplete = candle.is_complete === false ? " market-candle-incomplete" : "";
      svg.append(chartNode("line", {
        x1: x,
        y1: y(candle.highValue),
        x2: x,
        y2: y(candle.lowValue),
        class: `market-candle-wick ${direction}${incomplete}`,
      }));
      const bodyTop = Math.min(y(candle.openValue), y(candle.closeValue));
      const bodyHeight = Math.max(1.5, Math.abs(y(candle.openValue) - y(candle.closeValue)));
      svg.append(chartNode("rect", {
        x: x - bodyWidth / 2,
        y: bodyTop,
        width: bodyWidth,
        height: bodyHeight,
        rx: Math.min(1.5, bodyWidth / 4),
        class: `market-candle-body ${direction}${incomplete}`,
      }));
    });
    return true;
  };

  const marketTradingStatusLabel = (value) => ({
    SECURITY_TRADING_STATUS_NORMAL_TRADING: "Основные торги",
    SECURITY_TRADING_STATUS_OPENING_PERIOD: "Открытие",
    SECURITY_TRADING_STATUS_CLOSING_PERIOD: "Закрытие",
    SECURITY_TRADING_STATUS_BREAK_IN_TRADING: "Перерыв",
    SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING: "Торги недоступны",
    SECURITY_TRADING_STATUS_SESSION_ASSIGNED: "Сессия назначена",
    SECURITY_TRADING_STATUS_SESSION_OPEN: "Сессия открыта",
    SECURITY_TRADING_STATUS_SESSION_CLOSE: "Сессия закрыта",
    SECURITY_TRADING_STATUS_DEALER_NORMAL_TRADING: "Дилерские торги",
    SECURITY_TRADING_STATUS_DEALER_BREAK_IN_TRADING: "Дилерский перерыв",
    SECURITY_TRADING_STATUS_DEALER_NOT_AVAILABLE_FOR_TRADING: "Дилерские торги недоступны",
  }[value] || String(value || "Статус не подтверждён"));

  const syncInstrumentMarketControls = () => {
    instrumentMarketModeButtons.forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.marketMode === instrumentMarketMode),
      );
    });
    instrumentMarketPeriodButtons.forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.marketPeriod === instrumentMarketPeriod),
      );
    });
  };

  const resetInstrumentMarket = (message = "Выберите инструмент для рыночного графика.") => {
    instrumentMarketGeneration += 1;
    instrumentMarketPayload = null;
    instrumentMarketChart.replaceChildren();
    instrumentMarketScrubber.min = "0";
    instrumentMarketScrubber.max = "0";
    instrumentMarketScrubber.value = "0";
    instrumentMarketScrubber.disabled = true;
    instrumentMarketTooltip.classList.add("hidden");
    instrumentMarketTooltip.textContent = "";
    instrumentMarketLastPrice.textContent = "—";
    instrumentMarketQuoteTime.textContent = "—";
    instrumentMarketTradingStatus.textContent = "—";
    instrumentMarketSource.textContent = "—";
    instrumentMarketNote.textContent = message;
    setStateBadge(instrumentMarketState, "Нет данных", "state-next");
    instrumentMarketRetry.classList.add("hidden");
  };

  const marketApiAvailabilityLabel = (availability) => {
    if (availability === true) {
      return "API: доступно";
    }
    if (availability === false) {
      return "API: недоступно";
    }
    return "API: не подтверждено";
  };

  const instrumentMarketQuoteTimeText = (quoteTime, quoteAge) => {
    if (!quoteTime) {
      return "Последняя цена недоступна";
    }
    const parts = [formatExactDateTime(quoteTime)];
    if (quoteAge !== null) {
      parts.push(`возраст ${Math.max(0, Math.trunc(quoteAge))} с`);
    }
    return parts.join(" · ");
  };

  const renderInstrumentMarketLive = (payload) => {
    const source = payload !== null && typeof payload === "object" ? payload : {};
    const quoteStatus = String(source.quote_status || "missing");
    const quoteAge = finiteMarketNumber(source.quote_age_seconds);
    instrumentMarketLastPrice.textContent = marketPriceText(source.last_price);
    instrumentMarketQuoteTime.textContent = instrumentMarketQuoteTimeText(
      source.quote_time,
      quoteAge,
    );
    const apiAvailability = marketApiAvailabilityLabel(source.api_trade_available);
    instrumentMarketTradingStatus.textContent = [
      marketTradingStatusLabel(source.trading_status),
      apiAvailability,
    ].join(" · ");

    if (quoteStatus === "live") {
      setStateBadge(instrumentMarketState, "Оперативно", "state-ok");
    } else if (quoteStatus === "stale") {
      setStateBadge(instrumentMarketState, "Котировка устарела", "state-next");
    } else if (quoteStatus === "future") {
      setStateBadge(instrumentMarketState, "Время котировки некорректно", "state-error");
    } else {
      setStateBadge(instrumentMarketState, "Цена недоступна", "state-next");
    }

    if (finiteMarketNumber(source.last_price) !== null) {
      instrumentDetailPrice.textContent = marketPriceText(source.last_price);
      instrumentDetailPriceTime.textContent = source.quote_time
        ? `T-Invest quote: ${formatExactDateTime(source.quote_time)}`
        : "T-Invest: время котировки не подтверждено";
    }
  };

  const instrumentMarketCandleNote = (candles, incompleteCount) => {
    if (!candles.length) {
      return "T-Invest не вернул свечи для выбранного периода. Последняя цена показана отдельно.";
    }
    let completionNote = "Все показанные свечи завершены.";
    if (incompleteCount) {
      completionNote = `Незавершённых: ${incompleteCount}; они отмечены пунктиром.`;
    }
    return [
      `Свечей: ${candles.length}.`,
      completionNote,
      "Время свечи и время загрузки — разные значения.",
    ].join(" ");
  };

  const renderInstrumentMarketChart = (payload) => {
    const source = payload !== null && typeof payload === "object" ? payload : {};
    instrumentMarketPayload = source;
    syncInstrumentMarketControls();
    renderInstrumentMarketLive(source);
    const candles = cleanMarketCandles(source.candles);
    const inspectable = instrumentMarketMode === "candles"
      ? candles.length > 0
      : candles.length > 1;
    instrumentMarketScrubber.min = "0";
    instrumentMarketScrubber.max = String(Math.max(0, candles.length - 1));
    instrumentMarketScrubber.value = String(Math.max(0, candles.length - 1));
    instrumentMarketScrubber.disabled = !inspectable;
    const rendered = instrumentMarketMode === "candles"
      ? renderMarketCandles(instrumentMarketChart, candles)
      : renderSeriesChart(
          instrumentMarketChart,
          candles.map((item) => ({
            time: item.time,
            value: item.closeValue,
          })),
          {
            timeKey: "time",
            valueKey: "value",
            minimumPoints: 2,
          },
        );
    if (!rendered) {
      instrumentMarketChart.replaceChildren();
    }
    const incompleteCount = candles.filter((candle) => candle.is_complete === false).length;
    instrumentMarketSource.textContent = [
      source.source || "T-Invest",
      source.observed_at ? `загружено ${formatExactDateTime(source.observed_at)}` : "",
    ].filter(Boolean).join(" · ");
    instrumentMarketNote.textContent = instrumentMarketCandleNote(
      candles,
      incompleteCount,
    );
    instrumentMarketRetry.classList.add("hidden");
  };

  const removeInstrumentMarketCrosshair = () => {
    instrumentMarketChart.querySelectorAll(".market-chart-crosshair").forEach((node) => {
      node.remove();
    });
    instrumentMarketTooltip.classList.add("hidden");
    instrumentMarketTooltip.textContent = "";
  };

  const instrumentMarketInspectionCandles = () => {
    const candles = cleanMarketCandles(instrumentMarketPayload?.candles);
    if (!candles.length || (instrumentMarketMode === "line" && candles.length < 2)) {
      return [];
    }
    return candles;
  };

  const instrumentMarketChartSize = () => {
    const viewBox = String(instrumentMarketChart.getAttribute("viewBox") || "0 0 900 320")
      .split(/\s+/u)
      .map(Number);
    return {
      width: Number.isFinite(viewBox[2]) && viewBox[2] > 0 ? viewBox[2] : 900,
      height: Number.isFinite(viewBox[3]) && viewBox[3] > 0 ? viewBox[3] : 320,
    };
  };

  const instrumentMarketInspectionX = (candles, index, width) => {
    if (instrumentMarketMode === "candles") {
      const padX = 30;
      const plotWidth = width - padX * 2;
      return padX + (plotWidth / candles.length) * (index + 0.5);
    }

    const first = candles.at(0);
    const last = candles.at(-1);
    const candle = candles.at(index);
    if (!first || !last || !candle) {
      return null;
    }
    const padX = 24;
    const plotWidth = width - padX * 2;
    const timeSpan = Math.max(last.timestamp - first.timestamp, 1);
    return padX + ((candle.timestamp - first.timestamp) / timeSpan) * plotWidth;
  };

  const showInstrumentMarketInspection = (candles, index) => {
    const candle = candles.at(index);
    if (!candle) {
      removeInstrumentMarketCrosshair();
      return;
    }
    const {width, height} = instrumentMarketChartSize();
    const x = instrumentMarketInspectionX(candles, index, width);
    if (x === null) {
      removeInstrumentMarketCrosshair();
      return;
    }

    removeInstrumentMarketCrosshair();
    instrumentMarketChart.append(chartNode("line", {
      x1: x,
      y1: 0,
      x2: x,
      y2: height,
      class: "market-chart-crosshair",
    }));
    const volumeLots = finiteMarketNumber(candle.volume_lots);
    instrumentMarketTooltip.textContent = [
      formatExactDateTime(candle.time),
      `O ${marketPriceText(candle.open)}`,
      `H ${marketPriceText(candle.high)}`,
      `L ${marketPriceText(candle.low)}`,
      `C ${marketPriceText(candle.close)}`,
      volumeLots === null
        ? "объём не подтверждён"
        : `объём ${new Intl.NumberFormat("ru-RU").format(volumeLots)} лот.`,
      candle.is_complete === false ? "свеча не завершена" : "свеча завершена",
    ].join(" · ");
    instrumentMarketTooltip.classList.remove("hidden");
  };

  const inspectInstrumentMarketChart = () => {
    const candles = instrumentMarketInspectionCandles();
    if (!candles.length) {
      removeInstrumentMarketCrosshair();
      return;
    }
    const index = Math.max(
      0,
      Math.min(
        candles.length - 1,
        Number.parseInt(instrumentMarketScrubber.value, 10) || 0,
      ),
    );
    showInstrumentMarketInspection(candles, index);
  };

  const stopInstrumentMarketStream = ({resetRetry = false} = {}) => {
    if (instrumentMarketEventSource) {
      instrumentMarketEventSource.close();
      instrumentMarketEventSource = null;
    }
    if (instrumentMarketRetryTimer !== null) {
      window.clearTimeout(instrumentMarketRetryTimer);
      instrumentMarketRetryTimer = null;
    }
    if (resetRetry) {
      instrumentMarketRetryCount = 0;
    }
  };

  const scheduleInstrumentMarketReconnect = () => {
    if (
      !instrumentMarketUid
      || currentView !== "portfolio"
      || document.visibilityState !== "visible"
    ) {
      return;
    }
    if (instrumentMarketRetryCount >= INSTRUMENT_MARKET_MAX_RETRIES) {
      setStateBadge(instrumentMarketState, "Поток остановлен", "state-next");
      instrumentMarketNote.textContent = (
        "Автоматическое переподключение остановлено после нескольких ошибок. "
        + "Последние подтверждённые данные сохранены на экране."
      );
      instrumentMarketRetry.classList.remove("hidden");
      return;
    }
    const delay = Math.min(1000 * (2 ** instrumentMarketRetryCount), 30000);
    instrumentMarketRetryCount += 1;
    instrumentMarketRetryTimer = window.setTimeout(() => {
      instrumentMarketRetryTimer = null;
      startInstrumentMarketStream();
    }, delay);
  };

  const renderInstrumentMarketStreamStatus = (state) => {
    const messages = {
      disconnected: "T-Invest не подключён.",
      reconnect: "Сохранённый T-Invest токен нужно переподключить.",
      unavailable: "Поток T-Invest временно недоступен; последняя подтверждённая цена остаётся на экране.",
      offline: "Автоматические запросы к T-Invest остановлены после нескольких ошибок. Нажмите «Повторить» для новой попытки.",
      invalid: "Идентификатор инструмента не принят поставщиком.",
    };
    const badgeText = {
      reconnect: "Нужен токен",
      disconnected: "Нет подключения",
      offline: "Поток остановлен",
    }[state] || "Degraded";
    setStateBadge(instrumentMarketState, badgeText, "state-next");
    instrumentMarketNote.textContent = messages[state] || messages.unavailable;
    if (state !== "unavailable") {
      instrumentMarketRetry.classList.remove("hidden");
    }
  };

  const instrumentMarketStreamCanStart = () => (
    !profileContextLost
    && Boolean(instrumentMarketUid)
    && instrumentMarketEventSource === null
    && instrumentMarketRetryTimer === null
    && currentView === "portfolio"
    && document.visibilityState === "visible"
  );

  const handleInstrumentMarketStreamFailure = (streamUid) => {
    if (streamUid !== instrumentMarketUid) {
      return;
    }
    stopInstrumentMarketStream();
    void verifyProfileContext();
    renderInstrumentMarketStreamStatus("unavailable");
    scheduleInstrumentMarketReconnect();
  };

  const handleInstrumentMarketEvent = (event, streamUid) => {
    if (streamUid !== instrumentMarketUid) {
      return;
    }
    try {
      const payload = JSON.parse(event.data);
      if (!instrumentMarketPayloadMatches(payload, instrumentMarketUid)) {
        throw new TypeError("Market stream instrument does not match");
      }
      instrumentMarketRetryCount = 0;
      renderInstrumentMarketLive(payload);
      instrumentMarketSource.textContent = [
        "T-Invest · серверное обновление",
        payload.observed_at ? `получено ${formatExactDateTime(payload.observed_at)}` : "",
      ].filter(Boolean).join(" · ");
    } catch {
      handleInstrumentMarketStreamFailure(streamUid);
    }
  };

  const handleInstrumentMarketStatusEvent = (event, streamUid) => {
    if (streamUid !== instrumentMarketUid) {
      return;
    }
    try {
      const payload = JSON.parse(event.data);
      const state = payload !== null && typeof payload === "object"
        ? String(payload.state || "unavailable")
        : "unavailable";
      if (state === "profile_context_changed") {
        pauseProfileContext();
        return;
      }
      renderInstrumentMarketStreamStatus(state);
      if (["disconnected", "reconnect", "invalid", "offline"].includes(state)) {
        stopInstrumentMarketStream();
      }
    } catch {
      handleInstrumentMarketStreamFailure(streamUid);
    }
  };

  const startInstrumentMarketStream = () => {
    if (!instrumentMarketStreamCanStart()) {
      return;
    }
    if (!("EventSource" in window)) {
      setStateBadge(instrumentMarketState, "Без live-потока", "state-next");
      instrumentMarketNote.textContent = (
        "Браузер не поддерживает EventSource. Историю и последнюю цену можно обновлять вручную."
      );
      instrumentMarketRetry.classList.remove("hidden");
      return;
    }

    let segment;
    try {
      segment = instrumentPathSegment(instrumentMarketUid);
    } catch {
      renderInstrumentMarketStreamStatus("invalid");
      return;
    }

    const streamUid = instrumentMarketUid;
    const stream = new EventSource(`/api/market/instruments/${segment}/stream?profile_context=${encodeURIComponent(currentProfileId)}`);
    instrumentMarketEventSource = stream;
    stream.addEventListener("market", (event) => {
      handleInstrumentMarketEvent(event, streamUid);
    });
    stream.addEventListener("status", (event) => {
      handleInstrumentMarketStatusEvent(event, streamUid);
    });
    stream.onerror = () => {
      handleInstrumentMarketStreamFailure(streamUid);
    };
  };

  const displayedInstrumentMarketPeriod = (instrumentUid) => {
    if (!instrumentMarketPayload || instrumentMarketUid !== instrumentUid) {
      return null;
    }
    return typeof instrumentMarketPayload.period === "string"
      ? instrumentMarketPayload.period
      : null;
  };

  const instrumentMarketRequestIsCurrent = (generation, instrumentUid) => (
    generation === instrumentMarketGeneration && instrumentUid === instrumentMarketUid
  );

  const instrumentMarketPayloadMatches = (payload, instrumentUid) => (
    payload !== null
    && typeof payload === "object"
    && payload.instrument_uid === instrumentUid
  );

  const renderInstrumentMarketLoadFailure = (error) => {
    if (error.status === 409) {
      renderInstrumentMarketStreamStatus(
        String(error.message || "").includes("not connected")
          ? "disconnected"
          : "reconnect",
      );
      return;
    }
    if (error.status === 422) {
      renderInstrumentMarketStreamStatus("invalid");
      return;
    }
    renderInstrumentMarketStreamStatus("unavailable");
    instrumentMarketRetry.classList.remove("hidden");
  };

  const restoreDisplayedInstrumentMarketPeriod = (displayedPeriod) => {
    if (!displayedPeriod || displayedPeriod === instrumentMarketPeriod) {
      return;
    }
    instrumentMarketPeriod = displayedPeriod;
    syncInstrumentMarketControls();
  };

  const fetchInstrumentMarketPayload = async (segment, instrumentUid, generation) => {
    const payload = await api(
      `/api/market/instruments/${segment}?period=${encodeURIComponent(instrumentMarketPeriod)}`,
      {method: "GET"},
    );
    if (!instrumentMarketRequestIsCurrent(generation, instrumentUid)) {
      return null;
    }
    if (!instrumentMarketPayloadMatches(payload, instrumentUid)) {
      throw new TypeError("Instrument market response does not match request");
    }
    return payload;
  };

  const handleInstrumentMarketLoadError = (
    error,
    generation,
    instrumentUid,
    displayedPeriod,
  ) => {
    if (error.status === 401) {
      location.reload();
      return;
    }
    if (!instrumentMarketRequestIsCurrent(generation, instrumentUid)) {
      return;
    }
    renderInstrumentMarketLoadFailure(error);
    restoreDisplayedInstrumentMarketPeriod(displayedPeriod);
  };

  const loadInstrumentMarket = async (instrumentUid, {force = false} = {}) => {
    const displayedPeriod = displayedInstrumentMarketPeriod(instrumentUid);
    let segment;
    try {
      segment = instrumentPathSegment(instrumentUid);
    } catch {
      renderInstrumentMarketStreamStatus("invalid");
      return;
    }
    if (
      !force
      && instrumentMarketPayload
      && instrumentMarketUid === instrumentUid
      && instrumentMarketPayload.period === instrumentMarketPeriod
    ) {
      startInstrumentMarketStream();
      return;
    }

    const generation = ++instrumentMarketGeneration;
    instrumentMarketUid = instrumentUid;
    instrumentMarketRetry.classList.add("hidden");
    setStateBadge(instrumentMarketState, "Загружаем", "");
    instrumentMarketNote.textContent = "Получаем биржевые свечи, последнюю цену и торговый статус T-Invest.";
    try {
      const payload = await fetchInstrumentMarketPayload(segment, instrumentUid, generation);
      if (payload === null) {
        return;
      }
      renderInstrumentMarketChart(payload);
      instrumentMarketRetryCount = 0;
      startInstrumentMarketStream();
    } catch (error) {
      handleInstrumentMarketLoadError(
        error,
        generation,
        instrumentUid,
        displayedPeriod,
      );
    }
  };

  const historyTimestamp = (item) => {
    const timestamp = new Date(item?.captured_at).getTime();
    return Number.isFinite(timestamp) ? timestamp : null;
  };

  const historySpanDays = (history) => {
    const times = (history || []).map(historyTimestamp).filter(Number.isFinite);
    if (times.length < 2) {
      return 0;
    }
    return (Math.max(...times) - Math.min(...times)) / (24 * 60 * 60 * 1000);
  };

  const historyForDays = (history, days) => {
    if (!Number.isFinite(days) || days <= 0 || !history?.length) {
      return history || [];
    }
    const latest = historyTimestamp(history[history.length - 1]);
    if (latest === null) {
      return history || [];
    }
    const cutoff = latest - days * 24 * 60 * 60 * 1000;
    return history.filter((item) => {
      const timestamp = historyTimestamp(item);
      return timestamp !== null && timestamp >= cutoff;
    });
  };

  const syncPortfolioHistoryPeriods = (history) => {
    const span = historySpanDays(history);
    const available = portfolioHistoryPeriodButtons
      .map((button) => Number(button.dataset.portfolioHistoryDays))
      .filter((days) => Number.isFinite(days) && span >= days);
    portfolioHistoryPeriodButtons.forEach((button) => {
      const days = Number(button.dataset.portfolioHistoryDays);
      const visible = Number.isFinite(days) && span >= days;
      button.classList.toggle("hidden", !visible);
      button.setAttribute(
        "aria-pressed",
        String(visible && days === selectedPortfolioHistoryDays),
      );
    });
    portfolioHistoryPeriods.classList.toggle("hidden", available.length === 0);
    if (!available.includes(selectedPortfolioHistoryDays)) {
      selectedPortfolioHistoryDays = available.length
        ? Math.max(...available)
        : Number.POSITIVE_INFINITY;
    }
    portfolioHistoryPeriodButtons.forEach((button) => {
      const days = Number(button.dataset.portfolioHistoryDays);
      button.setAttribute(
        "aria-pressed",
        String(!button.classList.contains("hidden") && days === selectedPortfolioHistoryDays),
      );
    });
  };

  const drawdownSeries = (history) => {
    let peak = null;
    return (history || [])
      .map((item) => {
        const value = Number(item.nav_rub);
        if (!Number.isFinite(value) || value < 0) {
          return null;
        }
        peak = peak === null ? value : Math.max(peak, value);
        const drawdown = peak > 0 ? ((value / peak) - 1) * 100 : 0;
        return {
          captured_at: item.captured_at,
          drawdown_percent: drawdown,
        };
      })
      .filter(Boolean);
  };

  const renderPortfolioHistory = (history) => {
    const allPoints = Array.isArray(history) ? history : [];
    syncPortfolioHistoryPeriods(allPoints);
    const points = historyForDays(allPoints, selectedPortfolioHistoryDays);
    const chartPoints = points
      .map((item) => ({
        captured_at: item.captured_at,
        value: Number(item.nav_rub),
      }))
      .filter((item) => Number.isFinite(item.value));
    const enough = renderSeriesChart(
      portfolioHistoryChart,
      chartPoints,
      {minimumPoints: 2},
    );
    const homePoints = historyForDays(allPoints, 90);
    const homeChartPoints = homePoints
      .map((item) => ({
        captured_at: item.captured_at,
        value: Number(item.nav_rub),
      }))
      .filter((item) => Number.isFinite(item.value));
    const homeEnough = renderSeriesChart(
      homeHistoryChart,
      homeChartPoints,
      {minimumPoints: 2},
    );
    setChartFacts(portfolioHistoryFacts, points);
    setChartFacts(homeHistoryFacts, homePoints);

    if (!enough) {
      setStateBadge(portfolioHistoryState, "Недостаточно истории", "state-next");
      portfolioHistoryNote.textContent = (
        chartPoints.length === 1
          ? "Есть один реальный снимок. Для линии нужно минимум два снимка того же счёта и окружения."
          : "История появится после сохранения снимков вашего счёта портфеля."
      );
    } else {
      setStateBadge(
        portfolioHistoryState,
        `Снимков: ${chartPoints.length}`,
        "state-ok",
      );
      portfolioHistoryNote.textContent = (
        "На графике указано время сохранения сводки, а не время сделки или биржевой котировки."
      );
    }

    if (!homeEnough) {
      setStateBadge(homeHistoryState, "Недостаточно истории", "state-next");
      homeHistoryNote.textContent = (
        homeChartPoints.length === 1
          ? "За последние 90 дней сохранён только один реальный снимок."
          : "За последние 90 дней недостаточно сохранённой истории для линии."
      );
    } else {
      setStateBadge(homeHistoryState, `Снимков: ${homeChartPoints.length}`, "state-ok");
      homeHistoryNote.textContent = (
        "Главная показывает до 90 дней реальных сохранённых снимков текущего счёта и окружения."
      );
    }

    const drawdowns = drawdownSeries(points);
    const drawdownReady = drawdowns.length >= 5 && renderSeriesChart(
      portfolioDrawdownChart,
      drawdowns,
      {
        valueKey: "drawdown_percent",
        minimumPoints: 5,
        zeroLine: true,
      },
    );
    if (!drawdownReady) {
      portfolioDrawdownChart.replaceChildren();
      setStateBadge(portfolioDrawdownState, "Недостаточно истории", "state-next");
      portfolioDrawdownNote.textContent = (
        "Для drawdown нужно минимум пять подтверждённых снимков одного счёта."
      );
    } else {
      const minimum = Math.min(
        ...drawdowns.map((item) => Number(item.drawdown_percent)),
      );
      setStateBadge(portfolioDrawdownState, "История подтверждена", "state-ok");
      portfolioDrawdownNote.textContent = (
        `Максимальная наблюдавшаяся просадка: ${formatPercent(minimum)}. `
        + "Расчёт только по сохранённым NAV snapshot."
      );
    }
  };

  const persistedPositionMap = () => {
    const positions = lastPortfolioVisualization?.latest?.positions;
    const result = new Map();
    if (!Array.isArray(positions)) {
      return result;
    }
    positions.forEach((item) => {
      for (const key of [item.instrument_uid, item.figi, item.catalog_instrument_uid]) {
        if (typeof key === "string" && key) {
          result.set(key, item);
        }
      }
    });
    return result;
  };

  const livePositionIdentity = (position) => (
    String(position?.instrument_uid || position?.figi || "")
  );

  const appendExposureRows = (container, rows, emptyMessage) => {
    container.replaceChildren();
    if (!rows.length) {
      appendEmptyState(container, emptyMessage);
      return;
    }
    rows.forEach((item) => {
      const row = document.createElement("div");
      row.className = "allocation-row";
      const label = document.createElement("div");
      label.className = "allocation-label";
      const title = document.createElement("strong");
      title.textContent = item.label;
      const percent = document.createElement("span");
      percent.textContent = Number.isFinite(item.percent)
        ? formatPercent(item.percent)
        : "Доля не подтверждена";
      label.append(title, percent);

      const track = document.createElement("div");
      track.className = "allocation-track";
      track.setAttribute("role", "img");
      track.setAttribute(
        "aria-label",
        `${item.label}: ${Number.isFinite(item.percent) ? formatPercent(item.percent) : "доля не подтверждена"}`,
      );
      const fill = document.createElement("div");
      fill.className = "allocation-fill";
      fill.style.width = `${Math.max(0, Math.min(100, item.percent || 0))}%`;
      track.append(fill);

      const amount = document.createElement("div");
      amount.className = "allocation-value";
      amount.textContent = storedMoney(item.value);
      row.append(label, track, amount);
      container.append(row);
    });
  };

  const visualizationExposureRows = (mode) => {
    const latest = lastPortfolioVisualization?.latest;
    const positions = Array.isArray(latest?.positions) ? latest.positions : [];
    const nav = Number(latest?.nav_rub);
    const valued = positions.filter((item) => {
      const value = Number(item.value_rub);
      return Number.isFinite(value) && value >= 0;
    });
    if (!valued.length) {
      return [];
    }

    if (mode === "position") {
      return valued
        .map((item) => {
          const value = Number(item.value_rub);
          const percent = Number(item.nav_percent);
          let resolvedPercent = percent;
          if (!Number.isFinite(resolvedPercent)) {
            resolvedPercent = nav > 0 ? value / nav * 100 : Number.NaN;
          }
          return {
            label: item.ticker || item.name || item.instrument_uid || "Инструмент",
            value,
            percent: resolvedPercent,
          };
        })
        .sort((left, right) => right.value - left.value)
        .slice(0, 12);
    }

    const groups = new Map();
    valued.forEach((item) => {
      let key = "Не определено";
      if (mode === "currency") {
        key = String(item.currency || "Не определено").toUpperCase();
      } else if (mode === "sector") {
        key = String(item.sector || "Не определено");
      }
      groups.set(key, (groups.get(key) || 0) + Number(item.value_rub));
    });
    return [...groups.entries()]
      .map(([label, value]) => ({
        label,
        value,
        percent: nav > 0 ? value / nav * 100 : Number.NaN,
      }))
      .sort((left, right) => right.value - left.value);
  };

  const renderPortfolioAllocationView = () => {
    allocationViewButtons.forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.allocationView === selectedAllocationView),
      );
    });

    if (selectedAllocationView === "class") {
      renderAllocation(lastPortfolioSnapshot?.portfolio?.asset_totals || []);
      portfolioAllocationNote.textContent = (
        "Классы активов — текущий ответ T-Invest. Сумма и доли могут включать денежные компоненты брокера."
      );
      return;
    }

    const rows = visualizationExposureRows(selectedAllocationView);
    appendExposureRows(
      assetAllocation,
      rows,
      "Для этого разреза нет подтверждённых оценённых позиций.",
    );
    const latest = lastPortfolioVisualization?.latest;
    if (selectedAllocationView === "sector") {
      const coverage = Number(latest?.sector_coverage_percent);
      portfolioAllocationNote.textContent = Number.isFinite(coverage)
        ? `Секторное покрытие сохранённого снимка: ${formatPercent(coverage)}. Неизвестные сектора остаются отдельной категорией.`
        : "Секторное покрытие не подтверждено; неизвестные сектора не распределяются по догадке.";
    } else if (selectedAllocationView === "currency") {
      portfolioAllocationNote.textContent = (
        "Валютный разрез показывает валюту инструмента для оценённых позиций; неоценённые позиции не перераспределяются."
      );
    } else {
      portfolioAllocationNote.textContent = (
        "Показаны крупнейшие оценённые позиции по сохранённому снимку. Доля относится к NAV этого snapshot."
      );
    }
  };

  const renderPortfolioCoverage = (latest) => {
    if (!latest) {
      portfolioSectorCoverage.textContent = "—";
      portfolioValuedCount.textContent = "—";
      portfolioSnapshotStatus.textContent = "—";
      portfolioSnapshotTime.textContent = "—";
      setStateBadge(portfolioCoverageState, "Нет снимка", "state-next");
      return;
    }
    const coverage = Number(latest.sector_coverage_percent);
    const valued = Number(latest.valued_security_count);
    const total = Number(latest.security_count);
    portfolioSectorCoverage.textContent = Number.isFinite(coverage)
      ? formatPercent(coverage)
      : "Не подтверждено";
    portfolioValuedCount.textContent = Number.isFinite(valued) && Number.isFinite(total)
      ? `${valued} из ${total}`
      : "—";
    portfolioSnapshotStatus.textContent = {
      observed: "Наблюдается",
      partial: "Частичное покрытие",
      needs_reconciliation: "Требуется сверка",
    }[latest.analysis_status] || String(latest.analysis_status || "Не подтверждено");
    portfolioSnapshotTime.textContent = formatDateTime(latest.captured_at);

    if (latest.analysis_status === "needs_reconciliation") {
      setStateBadge(portfolioCoverageState, "Нужна сверка", "state-error");
    } else if (latest.snapshot_freshness === "stale" || latest.analysis_status === "partial") {
      setStateBadge(portfolioCoverageState, "Неполные данные", "state-next");
    } else {
      setStateBadge(portfolioCoverageState, "Снимок получен", "state-ok");
    }
  };

  const positionRiskBadge = (persisted) => {
    const badge = document.createElement("span");
    const state = persisted?.risk_state || "data_missing";
    badge.className = "state-badge position-risk-badge";
    badge.textContent = riskStateLabel(state);
    const stateClass = riskStateClass(state);
    if (stateClass) {
      badge.classList.add(stateClass);
    }
    return badge;
  };

  const positionDetailButton = (position) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button button-secondary position-detail-button";
    button.textContent = "Детали";
    button.dataset.instrumentDetail = livePositionIdentity(position);
    if (!button.dataset.instrumentDetail) {
      button.disabled = true;
      button.title = "T-Invest не вернул стабильный идентификатор инструмента.";
    }
    return button;
  };

  const renderPositions = (positions) => {
    positionsList.replaceChildren();
    positionsTableBody.replaceChildren();
    if (!positions?.length) {
      appendEmptyState(positionsList, "В портфеле нет инструментов.");
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 7;
      cell.textContent = "В портфеле нет инструментов.";
      row.append(cell);
      positionsTableBody.append(row);
      return;
    }

    const persisted = persistedPositionMap();
    const snapshotAt = lastPortfolioVisualization?.latest?.captured_at;
    positionsFreshnessNote.textContent = [
      lastPortfolioSnapshot?.refreshed_at
        ? `Цена/доходность: чтение T-Invest ${formatDateTime(lastPortfolioSnapshot.refreshed_at)}`
        : "",
      snapshotAt
        ? `оценка/доля/risk: snapshot ${formatDateTime(snapshotAt)}`
        : "оценка/доля/risk: сохранённый snapshot пока недоступен",
    ].filter(Boolean).join(" · ");

    positions.forEach((position) => {
      const identity = livePositionIdentity(position);
      const stored = persisted.get(identity) || persisted.get(position.figi) || null;
      const titleText = position.ticker || stored?.name || position.figi || "Инструмент";
      const typeText = INSTRUMENT_LABELS[position.instrument_type]
        || position.instrument_type
        || "Инструмент";
      const valueText = storedMoney(stored?.value_rub);
      const weightText = storedPercent(stored?.nav_percent);
      const priceText = formatMoney(position.current_price);
      const yieldText = formatPercent(position.expected_yield_percent, {sign: true});
      const blockedLots = numericValue(position.blocked_lots);

      const tableRow = document.createElement("tr");
      const instrumentCell = document.createElement("td");
      const tableTitle = document.createElement("strong");
      tableTitle.textContent = titleText;
      const tableMeta = document.createElement("small");
      tableMeta.textContent = [
        stored?.name && stored.name !== titleText ? stored.name : "",
        typeText,
        formatQuantity(position.quantity) + " шт.",
      ].filter(Boolean).join(" · ");
      instrumentCell.append(tableTitle, tableMeta);

      const valueCell = document.createElement("td");
      valueCell.textContent = valueText;
      const weightCell = document.createElement("td");
      weightCell.textContent = weightText;
      const priceCell = document.createElement("td");
      priceCell.textContent = priceText;
      const yieldCell = document.createElement("td");
      yieldCell.textContent = yieldText;
      applySignedClass(yieldCell, position.expected_yield_percent);
      const stateCell = document.createElement("td");
      stateCell.append(positionRiskBadge(stored));
      if (position.blocked || blockedLots > 0) {
        const blocked = document.createElement("small");
        blocked.className = "position-blocked";
        blocked.textContent = blockedLots > 0
          ? `Блокировка: ${formatQuantity(position.blocked_lots)}`
          : "Есть блокировка";
        stateCell.append(blocked);
      }
      const actionCell = document.createElement("td");
      actionCell.append(positionDetailButton(position));
      tableRow.append(
        instrumentCell,
        valueCell,
        weightCell,
        priceCell,
        yieldCell,
        stateCell,
        actionCell,
      );
      positionsTableBody.append(tableRow);

      const card = document.createElement("article");
      card.className = "position-row portfolio-position-card";
      const name = document.createElement("div");
      name.className = "position-name";
      const ticker = document.createElement("strong");
      ticker.textContent = titleText;
      const type = document.createElement("span");
      type.textContent = [
        stored?.name && stored.name !== titleText ? stored.name : "",
        typeText,
      ].filter(Boolean).join(" · ");
      name.append(ticker, type, positionRiskBadge(stored));
      if (position.blocked || blockedLots > 0) {
        const blocked = document.createElement("em");
        blocked.className = "position-blocked";
        blocked.textContent = blockedLots > 0
          ? `Есть блокировка · заявками: ${formatQuantity(position.blocked_lots)}`
          : "Есть биржевая блокировка";
        name.append(blocked);
      }

      const cards = [
        ["Количество", formatQuantity(position.quantity)],
        ["Оценка", valueText],
        ["Доля", weightText],
        ["Текущая цена", priceText],
        ["Доходность", yieldText],
      ];
      card.append(name);
      cards.forEach(([labelText, value]) => {
        const cell = document.createElement("div");
        cell.className = "position-cell";
        const label = document.createElement("span");
        label.textContent = labelText;
        const strong = document.createElement("strong");
        strong.textContent = value;
        if (labelText === "Доходность") {
          applySignedClass(strong, position.expected_yield_percent);
        }
        cell.append(label, strong);
        card.append(cell);
      });
      const action = document.createElement("div");
      action.className = "position-card-action";
      action.append(positionDetailButton(position));
      card.append(action);
      positionsList.append(card);
    });
  };

  const resetPortfolioVisualization = (message = "История портфеля пока недоступна.") => {
    portfolioVisualizationLoaded = false;
    lastPortfolioVisualization = null;
    portfolioHistoryChart.replaceChildren();
    homeHistoryChart.replaceChildren();
    portfolioDrawdownChart.replaceChildren();
    setChartFacts(portfolioHistoryFacts, []);
    setChartFacts(homeHistoryFacts, []);
    setStateBadge(portfolioHistoryState, "Нет истории", "state-next");
    setStateBadge(homeHistoryState, "Нет истории", "state-next");
    setStateBadge(portfolioDrawdownState, "Недостаточно истории", "state-next");
    portfolioHistoryNote.textContent = message;
    homeHistoryNote.textContent = message;
    portfolioDrawdownNote.textContent = "Для drawdown нужно минимум пять подтверждённых снимков одного счёта.";
    renderPortfolioCoverage(null);
    if (lastPortfolioSnapshot) {
      renderPositions(lastPortfolioSnapshot.portfolio?.positions || []);
      renderPortfolioAllocationView();
    }
  };

  const renderPortfolioVisualization = (payload) => {
    lastPortfolioVisualization = payload;
    portfolioVisualizationLoaded = true;
    const history = Array.isArray(payload?.history) ? payload.history : [];
    renderPortfolioHistory(history);
    renderPortfolioCoverage(payload?.latest || null);
    renderPortfolioAllocationView();
    if (lastPortfolioSnapshot) {
      renderPositions(lastPortfolioSnapshot.portfolio?.positions || []);
    }
  };

  const loadPortfolioVisualization = async ({force = false} = {}) => {
    if (!tbankIsConnected || portfolioVisualizationInFlight
      || (portfolioVisualizationLoaded && !force)) {
      return;
    }
    const generation = portfolioGeneration;
    portfolioVisualizationInFlight = true;
    if (!lastPortfolioVisualization) {
      setStateBadge(portfolioHistoryState, "Загружаем", "");
      setStateBadge(homeHistoryState, "Загружаем", "");
    }
    try {
      const payload = await api(
        "/api/portfolio/visualization?history_limit=365",
        {method: "GET"},
      );
      if (generation !== portfolioGeneration || !tbankIsConnected) return;
      if (payload.latest && !matchesConnectedAccount(payload.latest)) return;
      renderPortfolioVisualization(payload);
    } catch (error) {
      if (generation !== portfolioGeneration) return;
      if (error.status === 401) {
        location.reload();
        return;
      }
      if (lastPortfolioVisualization) {
        setStateBadge(portfolioHistoryState, "История устарела", "state-next");
        setStateBadge(homeHistoryState, "История устарела", "state-next");
        portfolioHistoryNote.textContent = (
          "Не удалось обновить сохранённую историю. Показаны последние подтверждённые точки."
        );
        homeHistoryNote.textContent = portfolioHistoryNote.textContent;
      } else {
        resetPortfolioVisualization(
          "Не удалось получить сохранённую историю. Live-портфель остаётся доступен отдельно.",
        );
      }
    } finally {
      if (generation === portfolioGeneration) portfolioVisualizationInFlight = false;
    }
  };

  const livePositionForIdentity = (identity) => (
    (lastPortfolioSnapshot?.portfolio?.positions || []).find((position) => (
      position?.instrument_uid === identity || position?.figi === identity
    )) || null
  );

  const renderInstrumentDetailOverview = (latest, payload, livePosition) => {
    instrumentDetailTitle.textContent = (
      latest.ticker || latest.name || latest.instrument_uid || "Инструмент"
    );
    instrumentDetailSubtitle.textContent = [
      latest.name && latest.name !== latest.ticker ? latest.name : "",
      INSTRUMENT_LABELS[latest.instrument_type] || latest.instrument_type,
      latest.sector || "Сектор не подтверждён",
      payload.snapshot_freshness === "stale" ? "snapshot устарел" : "",
    ].filter(Boolean).join(" · ");
    instrumentDetailValue.textContent = storedMoney(latest.value_rub);
    instrumentDetailWeight.textContent = Number.isFinite(Number(latest.nav_percent))
      ? `Доля NAV: ${formatPercent(latest.nav_percent)}`
      : "Доля NAV не подтверждена";

    const livePrice = livePosition?.current_price;
    instrumentDetailPrice.textContent = livePrice
      ? formatMoney(livePrice)
      : storedMoney(
          latest.current_price_value,
          latest.current_price_currency || latest.currency || "RUB",
        );
    instrumentDetailPriceTime.textContent = livePosition && lastPortfolioSnapshot?.refreshed_at
      ? `T-Invest: ${formatDateTime(lastPortfolioSnapshot.refreshed_at)}`
      : `snapshot: ${formatDateTime(latest.captured_at)}`;
    instrumentDetailQuantity.textContent = livePosition
      ? formatQuantity(livePosition.quantity)
      : formatQuantity(latest.quantity);
    instrumentDetailBlocked.textContent = latest.blocked || Number(latest.blocked_lots) > 0
      ? `Есть блокировка · лотов: ${formatQuantity(latest.blocked_lots)}`
      : "Блокировок не зафиксировано";
  };

  const renderInstrumentDetailPnl = (livePosition) => {
    if (!livePosition) {
      instrumentDetailPnl.textContent = "—";
      instrumentDetailPnl.classList.remove("value-positive", "value-negative");
      instrumentDetailPnlTime.textContent = "Live P&L не подтверждён";
      return;
    }

    instrumentDetailPnl.textContent = formatPercent(
      livePosition.expected_yield_percent,
      {sign: true},
    );
    applySignedClass(instrumentDetailPnl, livePosition.expected_yield_percent);
    const dailyYield = formatMoney(livePosition.daily_yield, {sign: true});
    instrumentDetailPnlTime.textContent = [
      dailyYield !== "—" ? `сегодня ${dailyYield}` : "",
      lastPortfolioSnapshot?.refreshed_at
        ? `T-Invest ${formatDateTime(lastPortfolioSnapshot.refreshed_at)}`
        : "",
    ].filter(Boolean).join(" · ") || "Текущий ответ T-Invest";
  };

  const renderInstrumentDetailRisk = (latest) => {
    instrumentDetailRisk.textContent = riskStateLabel(latest.risk_state);
    instrumentDetailRisk.classList.remove("value-positive", "value-negative");
    if (["critical", "confirmed_default"].includes(latest.risk_state)) {
      instrumentDetailRisk.classList.add("value-negative");
    }
    instrumentDetailRiskTime.textContent = latest.assessed_at
      ? `оценено ${formatDateTime(latest.assessed_at)} · ${latest.assessment_freshness || "freshness unknown"}`
      : "Risk assessment отсутствует";
  };

  const renderInstrumentDetailHistory = (payload) => {
    const history = Array.isArray(payload?.history) ? payload.history : [];
    const historyReady = renderSeriesChart(
      instrumentHistoryChart,
      history,
      {valueKey: "value_rub", minimumPoints: 2},
    );
    instrumentHistoryNote.textContent = historyReady
      ? `Снимков позиции: ${history.length}. Время точки — captured_at snapshot, не биржевой timestamp.`
      : "Недостаточно сохранённых оценок позиции для линии.";
  };

  const renderInstrumentDetailEvidence = (latest) => {
    instrumentEvidenceSummary.replaceChildren();
    const reasons = Array.isArray(latest.risk_reasons) && latest.risk_reasons.length
      ? latest.risk_reasons.join(" · ")
      : "Нет подтверждённых причин";
    const evidenceItems = [
      ["Risk state", riskStateLabel(latest.risk_state)],
      ["Рейтинг", riskStateLabel(latest.rating_status)],
      ["Фундаментальные данные", riskStateLabel(latest.fundamental_status)],
      ["Источник risk", String(latest.source_status || "Не подтверждено")],
      ["Причины", reasons],
    ];
    evidenceItems.forEach(([labelText, valueText]) => {
      const row = document.createElement("div");
      const label = document.createElement("span");
      label.textContent = labelText;
      const value = document.createElement("strong");
      value.textContent = valueText;
      row.append(label, value);
      instrumentEvidenceSummary.append(row);
    });
  };

  const renderInstrumentDetailPayouts = (payload) => {
    instrumentPayouts.replaceChildren();
    (payload?.payouts || []).forEach((event) => {
      const row = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = {
        dividend: "Дивиденд",
        coupon: "Купон",
        bond_event: "Событие облигации",
      }[event.event_type] || String(event.event_type || "Событие");
      const details = document.createElement("small");
      const amount = event.amount === null || event.amount === undefined
        ? ""
        : storedMoney(event.amount, event.currency || "RUB");
      details.textContent = [
        event.status || "статус не подтверждён",
        amount,
        event.expected_at ? `ожидается ${formatDateTime(event.expected_at)}` : "",
        event.actual_at ? `факт ${formatDateTime(event.actual_at)}` : "",
      ].filter(Boolean).join(" · ");
      row.append(title, details);
      instrumentPayouts.append(row);
    });
    if (!instrumentPayouts.childElementCount) {
      appendEmptyState(instrumentPayouts, "Подтверждённых выплат или событий нет.");
    }
  };

  const renderInstrumentDetailSources = (payload) => {
    instrumentSources.replaceChildren();
    (payload?.sources || []).forEach((source) => {
      const row = document.createElement("div");
      const title = analysisSourceNode({
        name: [source.provider, source.document_type].filter(Boolean).join(" · ") || "Источник",
        url: source.source_url || "",
      });
      const details = document.createElement("small");
      details.textContent = [
        source.freshness_status || "freshness unknown",
        source.retrieved_at ? `получено ${formatDateTime(source.retrieved_at)}` : "",
        Number.isFinite(Number(source.versions)) ? `версий: ${source.versions}` : "",
      ].filter(Boolean).join(" · ");
      row.append(title, details);
      instrumentSources.append(row);
    });
    if (!instrumentSources.childElementCount) {
      appendEmptyState(instrumentSources, "Evidence sources ещё не сохранены.");
    }
  };

  const renderInstrumentDetail = (payload, requestedIdentity) => {
    const latest = payload?.latest || {};
    const livePosition = livePositionForIdentity(requestedIdentity);
    instrumentMarketCurrency = String(
      livePosition?.current_price?.currency
      || latest.current_price_currency
      || latest.currency
      || "",
    ).toUpperCase();
    instrumentMarketQuoteUnit = ["bond", "futures", "future"].includes(
      latest.instrument_type,
    )
      ? "point"
      : "money";
    renderInstrumentDetailOverview(latest, payload, livePosition);
    renderInstrumentDetailPnl(livePosition);
    renderInstrumentDetailRisk(latest);
    renderInstrumentDetailHistory(payload);
    renderInstrumentDetailEvidence(latest);
    renderInstrumentDetailPayouts(payload);
    renderInstrumentDetailSources(payload);
  };

  const openInstrumentDetail = async (instrumentUid) => {
    if (workspace?.isDemo()) { workspace.openDemoInstrument(instrumentUid); return; }
    if (instrumentDetailRequestInFlight) {
      return;
    }
    let segment;
    try {
      segment = instrumentPathSegment(instrumentUid);
    } catch {
      showMessage(
        instrumentDetailMessage,
        "T-Invest не вернул допустимый идентификатор инструмента.",
        true,
      );
      return;
    }
    const generation = ++instrumentDetailGeneration;
    instrumentDetailRequestInFlight = true;
    stopInstrumentMarketStream({resetRetry: true});
    instrumentMarketUid = instrumentUid;
    instrumentMarketCurrency = "";
    instrumentMarketQuoteUnit = "money";
    resetInstrumentMarket("Загружаем рыночные данные выбранного инструмента.");
    instrumentDetail.classList.remove("hidden");
    instrumentDetailLoading.classList.remove("hidden");
    instrumentDetailContent.classList.add("hidden");
    showMessage(instrumentDetailMessage, "");
    instrumentDetail.scrollIntoView({block: "start", behavior: "auto"});
    try {
      const payload = await api(
        `/api/portfolio/instruments/${segment}/visualization?history_limit=90`,
        {method: "GET"},
      );
      if (generation !== instrumentDetailGeneration) {
        return;
      }
      renderInstrumentDetail(payload, instrumentUid);
      instrumentDetailLoading.classList.add("hidden");
      instrumentDetailContent.classList.remove("hidden");
      void loadInstrumentMarket(instrumentUid, {force: true});
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      if (generation !== instrumentDetailGeneration) {
        return;
      }
      instrumentDetailLoading.classList.add("hidden");
      showMessage(
        instrumentDetailMessage,
        error.status === 404
          ? "Для этой позиции ещё нет сохранённой tenant-scoped истории."
          : "Не удалось загрузить детали инструмента. Торговые действия не выполнялись.",
        true,
      );
    } finally {
      if (generation === instrumentDetailGeneration) {
        instrumentDetailRequestInFlight = false;
      }
    }
  };

  const closeInstrumentDetail = () => {
    instrumentDetailGeneration += 1;
    instrumentMarketGeneration += 1;
    instrumentDetailRequestInFlight = false;
    stopInstrumentMarketStream({resetRetry: true});
    instrumentMarketUid = "";
    instrumentMarketCurrency = "";
    instrumentMarketQuoteUnit = "money";
    resetInstrumentMarket();
    instrumentDetail.classList.add("hidden");
    instrumentDetailLoading.classList.add("hidden");
    instrumentDetailContent.classList.add("hidden");
    showMessage(instrumentDetailMessage, "");
  };

  const showPortfolioMode = (mode) => {
    portfolioLoading.classList.toggle("hidden", mode !== "loading");
    portfolioDisconnected.classList.toggle("hidden", mode !== "disconnected");
    portfolioError.classList.toggle("hidden", mode !== "error");
    portfolioContent.classList.toggle("hidden", mode !== "content");
  };

  const singleRubAmount = (items) => {
    const rubItems = (items || []).filter(
      (item) => String(item?.currency || "").toUpperCase() === "RUB",
    );
    if (rubItems.length === 0) {
      return 0;
    }
    if (rubItems.length !== 1) {
      return null;
    }
    const value = Number(rubItems[0].value);
    return Number.isFinite(value) && value >= 0 ? value : null;
  };

  const homeUnblockedRub = (snapshot) => {
    if (snapshot?.limits_loading_in_progress === true) {
      return null;
    }
    const cash = singleRubAmount(snapshot?.cash);
    const blocked = singleRubAmount(snapshot?.blocked_cash);
    if (cash === null || blocked === null || blocked > cash) {
      return null;
    }
    return cash - blocked;
  };

  const homePortfolioAttention = (snapshot, {stale = false, failed = false, expired = false} = {}) => {
    const items = [];
    if (failed) {
      items.push({
        severity: "error",
        title: "Портфель не подтверждён",
        detail: "T-Invest не вернул актуальный снимок. До успешного обновления не полагайтесь на значения портфеля.",
        view: "portfolio",
      });
      return items;
    }
    if (!snapshot?.portfolio) {
      return items;
    }
    if (stale) {
      items.push({
        severity: "warning",
        title: "Данные портфеля устарели",
        detail: expired
          ? "Срок актуальности снимка истёк. Обновите данные перед принятием решения."
          : "Последний подтверждённый снимок сохранён на экране, но новое чтение T-Invest завершилось ошибкой.",
        view: "portfolio",
      });
    }
    if (snapshot.limits_loading_in_progress === true) {
      items.push({
        severity: "warning",
        title: "T-Invest обновляет денежные лимиты",
        detail: "Незаблокированные RUB пока не считаются подтверждёнными.",
        view: "portfolio",
      });
    }
    const positions = snapshot.portfolio.positions || [];
    const blockedPositions = positions.filter((position) => position.blocked).length;
    if (blockedPositions > 0) {
      items.push({
        severity: "warning",
        title: `Заблокированные позиции: ${blockedPositions}`,
        detail: "Откройте портфель, чтобы увидеть конкретные инструменты и состояние блокировки.",
        view: "portfolio",
      });
    }
    const blockedCash = (snapshot.blocked_cash || []).filter((money) => {
      const value = Number(money?.value);
      return Number.isFinite(value) && value !== 0;
    });
    if (blockedCash.length > 0) {
      items.push({
        severity: "warning",
        title: "Есть заблокированные денежные остатки",
        detail: `Валют с ненулевой блокировкой: ${blockedCash.length}.`,
        view: "portfolio",
      });
    }
    return items;
  };

  const attentionMarkerText = (severity) => {
    if (severity === "error") {
      return "×";
    }
    if (severity === "warning") {
      return "!";
    }
    return "i";
  };

  const renderHomeAttention = () => {
    const pending = Object.values(homeAttentionBuckets).includes(null);
    const items = Object.values(homeAttentionBuckets)
      .filter(Array.isArray)
      .flat()
      .sort((left, right) => {
        const rank = {error: 0, warning: 1, info: 2};
        return (rank[left.severity] ?? 3) - (rank[right.severity] ?? 3);
      });

    homeAttentionList.replaceChildren();
    homeAttentionCount.textContent = pending && items.length === 0 ? "—" : String(items.length);

    if (!items.length) {
      appendEmptyState(
        homeAttentionList,
        pending
          ? "Проверяем подключение, портфель и активные планы."
          : "Подтверждённых событий, требующих действия, сейчас нет.",
      );
      setStateBadge(
        homeAttentionStateBadge,
        pending ? "Проверяем" : "Спокойно",
        pending ? "" : "state-ok",
      );
      return;
    }

    items.slice(0, 4).forEach((item) => {
      const row = document.createElement("article");
      row.className = `attention-item attention-${item.severity || "info"}`;

      const marker = document.createElement("span");
      marker.className = "attention-marker";
      marker.setAttribute("aria-hidden", "true");
      marker.textContent = attentionMarkerText(item.severity);

      const copy = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = item.title;
      const detail = document.createElement("span");
      detail.textContent = item.detail;
      copy.append(title, detail);
      row.append(marker, copy);

      if (item.view && VIEW_TITLES[item.view]) {
        const action = document.createElement("button");
        action.type = "button";
        action.className = "attention-action";
        action.dataset.homeAttentionView = item.view;
        action.textContent = "Открыть";
        row.append(action);
      }
      homeAttentionList.append(row);
    });

    const hasError = items.some((item) => item.severity === "error");
    setStateBadge(
      homeAttentionStateBadge,
      pending ? `${items.length} · проверяем` : String(items.length),
      hasError ? "state-error" : "state-next",
    );
  };

  const setHomeAttentionBucket = (name, items) => {
    if (!(name in homeAttentionBuckets)) {
      return;
    }
    let bucket = [];
    if (items === null) {
      bucket = null;
    } else if (Array.isArray(items)) {
      bucket = items;
    }
    homeAttentionBuckets[name] = bucket;
    renderHomeAttention();
  };

  const resetHomePortfolioSummary = (message = "Ожидаем данные T-Invest") => {
    homePortfolioTotal.textContent = "—";
    homeDailyChange.textContent = "—";
    homeDailyRelative.textContent = "—";
    homeFreeCash.textContent = "—";
    homePositionCount.textContent = "—";
    homeSnapshotTime.textContent = message;
    homeDailyChange.classList.remove("value-positive", "value-negative");
    homeDailyRelative.classList.remove("value-positive", "value-negative");
    homeAllocation.replaceChildren();
    appendEmptyState(homeAllocation, message);
    setStateBadge(homePortfolioSummaryState, "Нет данных", "state-next");
  };

  const renderHomePortfolioSummary = (snapshot) => {
    const portfolio = snapshot.portfolio;
    homePortfolioTotal.textContent = formatMoney(portfolio.total);
    homeDailyChange.textContent = formatMoney(portfolio.daily_yield, {sign: true});
    applySignedClass(homeDailyChange, portfolio.daily_yield?.value);
    homeDailyRelative.textContent = formatPercent(portfolio.daily_yield_percent, {sign: true});
    applySignedClass(homeDailyRelative, portfolio.daily_yield_percent);
    homePositionCount.textContent = String(portfolio.positions?.length || 0);
    homeSnapshotTime.textContent = `Проверено ${formatDateTime(snapshot.refreshed_at)}`;

    const unblockedRub = homeUnblockedRub(snapshot);
    homeFreeCash.textContent = unblockedRub === null
      ? "Не подтверждены"
      : formatMoney({currency: "RUB", value: String(unblockedRub)});
    homeFreeCash.classList.toggle("value-unconfirmed", unblockedRub === null);

    renderAllocationRows(
      homeAllocation,
      portfolio.asset_totals,
      {
        limit: 4,
        emptyMessage: "T-Invest не вернул распределение по классам активов.",
      },
    );
    setStateBadge(homePortfolioSummaryState, "Проверено", "state-ok");
    setHomeAttentionBucket("portfolio", homePortfolioAttention(snapshot));
  };

  const clearPortfolioFreshnessTimer = () => {
    if (portfolioFreshnessTimer !== null) {
      window.clearTimeout(portfolioFreshnessTimer);
      portfolioFreshnessTimer = null;
    }
  };

  const renderPortfolioDataStatus = () => {
    clearPortfolioFreshnessTimer();
    const snapshot = lastPortfolioSnapshot;
    if (!snapshot) return;
    const error = lastPortfolioLoadError;
    const freshness = snapshot.freshness;
    const validUntil = Date.parse(freshness?.valid_until || "");
    const expired = Number.isFinite(validUntil) && Date.now() >= validUntil;
    let state = freshness?.status || "unavailable";
    if (error || expired) state = "stale";
    const labels = {
      fresh: "Данные получены",
      partial: "Часть данных уточняется",
      stale: "Нужно обновить",
      unavailable: "Время не подтверждено",
    };
    const label = labels[state] || labels.unavailable;
    [portfolioStateBadge, homePortfolioState, homePortfolioSummaryState, owlState].forEach(
      (badge) => setStateBadge(badge, label, state === "fresh" ? "state-ok" : "state-next"),
    );
    const received = formatDateTime(freshness?.observed_at || snapshot.refreshed_at);
    let note = `Снимок получен из T-Invest: ${received}. Это время чтения данных, а не время всех котировок.`;
    if (state === "stale") {
      note = error
        ? `Обновление не удалось. Показан последний снимок от ${received}.` + errorReference(error)
        : `Снимок от ${received} требует обновления. Нажмите «Обновить данные».`;
      setHomeAttentionBucket("portfolio", homePortfolioAttention(snapshot, {stale: true, expired: !error}));
    } else if (state === "partial") {
      note += " Денежные лимиты ещё уточняются; доступная сумма не подтверждена.";
    } else if (state === "unavailable") {
      note = "Время данных не подтверждено. Обновите снимок перед принятием решения.";
    }
    portfolioDataNotice.textContent = note;
    if (state !== "fresh") {
      portfolioFreeCash.textContent = "Не подтверждены";
      homeFreeCash.textContent = "Не подтверждены";
      homeFreeCash.classList.add("value-unconfirmed");
      setStateBadge(guardState, "Нужны свежие данные", "state-next");
    }
    if (!error && !expired && Number.isFinite(validUntil)) {
      portfolioFreshnessTimer = window.setTimeout(
        () => renderPortfolioDataStatus(), Math.min(2147483647, Math.max(1, validUntil - Date.now() + 50)),
      );
    }
  };

  const invalidatePortfolioRequest = () => {
    portfolioGeneration += 1;
    portfolioRequestInFlight = false;
    portfolioVisualizationInFlight = false;
    closeInstrumentDetail();
    clearPortfolioFreshnessTimer();
  };

  const renderPortfolio = (snapshot) => {
    const portfolio = snapshot.portfolio;
    lastPortfolioSnapshot = snapshot;
    lastPortfolioLoadError = null;
    portfolioTotal.textContent = formatMoney(portfolio.total);
    portfolioYield.textContent = formatPercent(portfolio.expected_yield_percent, {sign: true});
    applySignedClass(portfolioYield, portfolio.expected_yield_percent);
    portfolioDaily.textContent = formatMoney(portfolio.daily_yield, {sign: true});
    applySignedClass(portfolioDaily, portfolio.daily_yield?.value);
    portfolioDailyRelative.textContent = formatPercent(portfolio.daily_yield_percent, {sign: true});
    portfolioPositionCount.textContent = String(portfolio.positions?.length || 0);
    portfolioRefreshed.textContent = `Обновлено ${formatDateTime(snapshot.refreshed_at)}`;
    const unblockedRub = homeUnblockedRub(snapshot);
    portfolioFreeCash.textContent = unblockedRub === null
      ? "Не подтверждены"
      : storedMoney(unblockedRub);

    renderPortfolioAllocationView();
    renderCash(snapshot.cash, snapshot.blocked_cash, snapshot.limits_loading_in_progress);
    renderPositions(portfolio.positions);
    renderHomePortfolioSummary(snapshot);

    lastPortfolioRefreshAt = Date.now();
    portfolioLoaded = true;
    updateOwlState(snapshot.refreshed_at);
    updateGuard(snapshot);
    showPortfolioMode("content");
    setStateBadge(portfolioStateBadge, "Данные получены", "state-ok");
    setStateBadge(homePortfolioState, "Работает", "state-ok");
    renderPortfolioDataStatus();
    workspace?.setSnapshot(snapshot);
  };

  const renderDisconnectedPortfolio = () => {
    clearPortfolioFreshnessTimer();
    portfolioLoaded = false;
    lastPortfolioSnapshot = null;
    lastPortfolioLoadError = null;
    lastPortfolioRefreshAt = 0;
    resetPortfolioVisualization("Подключите T-Invest для сохранённой истории портфеля.");
    portfolioFreeCash.textContent = "—";
    updateOwlState(null);
    updateGuard(null);
    resetHomePortfolioSummary("Подключите T-Invest для данных портфеля.");
    setHomeAttentionBucket("portfolio", []);
    showPortfolioMode("disconnected");
    setStateBadge(portfolioStateBadge, "Нет подключения", "state-next");
    setStateBadge(homePortfolioState, "Нет подключения", "state-next");
  };

  const renderPortfolioLoadFailure = (error, hadPortfolio) => {
    lastPortfolioLoadError = error;
    const needsReconnect = error.status === 409;
    if (hadPortfolio && lastPortfolioSnapshot) {
      portfolioLoaded = true;
      showPortfolioMode("content");
      setStateBadge(portfolioStateBadge, "Данные устарели", "state-next");
      setStateBadge(homePortfolioState, "Данные устарели", "state-next");
      setStateBadge(homePortfolioSummaryState, "Данные устарели", "state-next");
      setHomeAttentionBucket(
        "portfolio",
        homePortfolioAttention(lastPortfolioSnapshot, {stale: true}),
      );
      renderPortfolioDataStatus();
      return;
    }

    portfolioLoaded = false;
    portfolioFreeCash.textContent = "—";
    showPortfolioMode("error");
    portfolioErrorText.textContent = needsReconnect
      ? "Подключение T-Invest устарело или токен больше не действует. Переподключите счёт."
      : "T-Invest временно не отдал данные портфеля. Попробуйте повторить запрос.";
    portfolioErrorText.textContent += errorReference(error);
    setStateBadge(portfolioStateBadge, "Ошибка", "state-error");
    setStateBadge(homePortfolioState, "Ошибка", "state-error");
    setStateBadge(homePortfolioSummaryState, "Ошибка", "state-error");
    resetHomePortfolioSummary("Портфель не подтверждён.");
    setStateBadge(homePortfolioSummaryState, "Ошибка", "state-error");
    setHomeAttentionBucket("portfolio", homePortfolioAttention(null, {failed: true}));
    setStateBadge(owlState, "Ошибка", "state-error");
    updateGuard(null);
  };

  const matchesConnectedAccount = (snapshot) => {
    if (snapshot.account_id === tbankAccountId
      && snapshot.environment === connectedTbankEnvironment) return true;
    renderTbankFailure();
    if (typeof snapshot.account_id === "string" && snapshot.account_id
      && ["prod", "sandbox"].includes(snapshot.environment)) void loadTbankStatus();
    return false;
  };

  const loadPortfolioData = async ({force = false} = {}) => {
    if (!tbankIsConnected) {
      renderDisconnectedPortfolio();
      return;
    }
    if (portfolioRequestInFlight || (portfolioLoaded && !force)) {
      return;
    }

    const hadPortfolio = portfolioLoaded;
    const generation = portfolioGeneration;
    portfolioRequestInFlight = true;
    portfolioRefresh.disabled = true;
    if (!hadPortfolio) {
      showPortfolioMode("loading");
      setStateBadge(homePortfolioSummaryState, "Загружаем", "");
      setHomeAttentionBucket("portfolio", null);
    } else {
      setStateBadge(homePortfolioSummaryState, "Обновляем", "");
    }
    setStateBadge(portfolioStateBadge, "Обновляем", "");
    setStateBadge(homePortfolioState, hadPortfolio ? "Обновляем" : "Загружаем", "");

    try {
      const snapshot = await api("/api/broker/tbank/portfolio", {method: "GET"});
      if (generation !== portfolioGeneration || !tbankIsConnected) return;
      if (!matchesConnectedAccount(snapshot)) return;
      renderPortfolio(snapshot);
      void loadPortfolioVisualization({force});
    } catch (error) {
      if (generation !== portfolioGeneration) return;
      if (error.status === 401) {
        location.reload();
        return;
      }

      renderPortfolioLoadFailure(error, hadPortfolio);
    } finally {
      if (generation === portfolioGeneration) {
        portfolioRequestInFlight = false;
        portfolioRefresh.disabled = false;
      }
    }
  };

  const resetAnalysis = () => {
    analysisGeneration += 1;
    analysisInFlight = false;
    analysisRefresh.disabled = false;
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
    renderBalancing({status: "pending", reason: "Обновите данные выбранного счёта"});
    renderProposalCreateOptions(null);
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

  const EVIDENCE_SOURCE_HOSTS = new Set([
    "developer.tbank.ru",
    "cbr.ru",
    "www.cbr.ru",
    "ratings.cbr.ru",
    "raexpert.ru",
    "acra-ratings.ru",
    "www.raexpert.ru",
    "www.acra-ratings.ru",
  ]);

  const analysisSourceNode = (source) => {
    const label = typeof source.name === "string" && source.name
      ? source.name
      : "Источник";
    try {
      const url = new URL(source.url);
      const tbankPathAllowed = url.hostname !== "developer.tbank.ru"
        || url.pathname.startsWith("/invest/");
      if (
        url.protocol === "https:"
        && EVIDENCE_SOURCE_HOSTS.has(url.hostname)
        && tbankPathAllowed
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
    workspace?.setAnalysis(snapshot);
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
    workspace?.setPayouts(snapshot.payouts || []);
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
      const titleText = (source.provider || "Источник")
        + " · "
        + (source.document_type || "document");
      const title = analysisSourceNode({
        name: titleText,
        url: source.source_url || "",
      });
      const details = document.createElement("small");
      details.textContent = [
        intelligenceLabel(source.freshness_status),
        source.retrieved_at ? "получено " + formatDateTime(source.retrieved_at) : "",
        Number.isFinite(Number(source.versions)) ? "версий: " + source.versions : "",
      ].filter(Boolean).join(" · ");
      row.append(title, details);
      intelligenceSources.append(row);
    });
    (snapshot.rating_sources || []).forEach((source) => {
      const row = document.createElement("div");
      const title = analysisSourceNode({
        name: source.name || "Официальный источник рейтингов",
        url: source.url || "",
      });
      const details = document.createElement("small");
      details.textContent = source.access === "public_reference"
        ? "Открытый официальный источник · автоматическое извлечение не подтверждено"
        : "Официальный структурированный feed · требуется отдельный доступ/подписка";
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

  const BALANCING_REASON_LABELS = {
    profile_required: "Сначала заполните профиль капитала",
    balancing_policy_required: "Сохраните явные лимиты балансировки",
    snapshot_required: "Нет сохранённого снимка портфеля",
    snapshot_time_missing: "Время снимка не подтверждено",
    snapshot_time_in_future: "Время снимка некорректно",
    snapshot_stale: "Снимок портфеля устарел",
    snapshot_not_observed: "Снимок требует сверки",
    broker_limits_loading: "T-Invest ещё обновляет лимиты",
    nav_unavailable: "NAV портфеля не подтверждён",
    free_cash_unavailable: "Свободные рубли не подтверждены",
    critical_evidence_missing: "Критичные доказательства неполны",
    instrument_structure_not_supported: "Структура инструмента пока не поддерживается",
    api_trade_unavailable: "Инструмент недоступен через API",
    buy_unavailable: "Покупка инструмента недоступна",
    required_tests_missing: "Есть непройденные тесты брокера",
    qualification_required: "Требуется статус квалифицированного инвестора",
    iis_not_allowed: "Инструмент недоступен для этого типа ИИС",
    issuer_identity_not_verified: "Юридический эмитент не подтверждён",
    issuer_group_not_verified: "Группа связанных компаний не подтверждена",
    fund_look_through_missing: "Состав фонда не подтверждён",
    catalog_stale: "Каталог инструмента устарел",
    account_access_stale: "Права счёта нужно обновить",
    candidate_risk_assessment_missing: "Risk assessment кандидата ещё не получен",
    quote_missing: "Свежая котировка отсутствует",
    missing_lot_cost: "Стоимость целого лота не рассчитана",
    liquidity_evidence_missing: "Ликвидность не подтверждена",
    provider_liquidity_flag_false: "Provider пометил ликвидность как недоступную",
    provider_liquidity_flag_missing: "Provider не подтвердил ликвидность",
    expected_return_model_missing: "Сценарная доходность ещё не рассчитана",
    bond_ytw_missing: "Yield-to-worst не подтверждён",
    bond_duration_missing: "Дюрация не подтверждена",
    bond_term_missing: "Срок облигации не подтверждён",
    bond_structure_missing: "Структура облигации неполна",
    rating_state_not_allowed: "Риск-состояние не допускается",
    risk_state_not_allowed: "Risk state не допускает новую позицию",
    below_grade_not_allowed: "Policy запрещает новый below-grade риск",
    unknown_rating_not_allowed: "Policy запрещает новый актив с неподтверждённым рейтингом",
    order_book_unusable: "Свежий согласованный стакан недоступен",
    live_asset_class_not_supported: "Live-enrichment этого класса актива ещё не поддерживается",
    live_enrichment_not_selected: "Инструмент не вошёл в ограниченный live-screening этого цикла",
    live_candidate_evidence_unavailable: "Live evidence кандидата временно недоступен",
    bond_option_events_unsupported: "Есть будущая оферта/call/конвертация · YTW для этой структуры пока fail-closed",
    candidate_confirmed_default: "Provider evidence подтверждает дефолт · новая покупка запрещена",
    tbank_shortlist_signal_unavailable: "Broker yield signal для shortlist временно недоступен",
    issuer_group_unverified: "Корпоративная группа не подтверждена",
    asset_class_not_allowed: "Класс актива запрещён policy",
    currency_not_allowed: "Валюта запрещена policy",
    liquidity_limit: "Не проходит лимит ликвидности",
    term_limit: "Не проходит лимит срока",
    asset_class_cap_missing: "Нет лимита класса актива",
    currency_cap_missing: "Нет лимита валюты",
    invalid_lot_size: "Некорректная лотность",
    replacement_cost_model_missing: "Налоги и издержки продажи ещё не подтверждены",
    no_eligible_positive_candidate: "Нет допустимого кандидата с положительным net-сценарием",
    integer_lot_or_policy_limits_block_all_buys: "Целые лоты или лимиты блокируют покупку",
    reserve_or_withdrawal_consumes_free_cash: "Резерв и снятия используют свободные деньги",
    no_replacement_clears_costs_and_no_trade_band: "Замена не перекрывает издержки и no-trade band",
    no_eligible_replacement: "Нет допустимой замены",
    holding_blocked: "Позиция заблокирована",
    hold_baseline: "Ничего не менять",
    integer_lot_allocation: "Распределение целыми лотами",
    net_improvement_after_costs: "Улучшение после издержек",
  };

  const BALANCING_NOTE_LABELS = {
    shortlisted_by_tbank_market_yield_signal: "Shortlist: broker yield signal; решение пересчитывается по contractual cash-flow",
    issuer_identity_from_verified_mapping: "Эмитент подтверждён сохранённой verified mapping",
    issuer_group_from_verified_mapping: "Группа взята из проверенной связи инструмента с эмитентом",
    issuer_ratings_from_tinvest_bond_by: "Кредитные рейтинги эмитента: T-Invest BondBy",
    issuer_rating_missing: "T-Invest не вернул действующий рейтинг эмитента",
    issuer_rating_time_invalid: "Дата рейтинга некорректна · рейтинг не используется",
    issuer_rating_level_unrecognized: "Шкала рейтинга не распознана · используется unknown bucket",
    issuer_rating_under_watch: "Рейтинг эмитента находится под наблюдением · новый вход блокируется",
    buy_cost_from_tinvest_get_order_price: "Покупка: комиссия и НКД из T-Invest GetOrderPrice",
    ytw_from_tinvest_fixed_cashflows: "YTW: T-Invest купоны + погашение; будущих call/convert событий нет",
    liquidity_from_tinvest_exchange_candles: "Ликвидность: завершённые биржевые дневные свечи T-Invest",
    no_future_call_or_conversion_events: "BondEvents: будущие call/convert события отсутствуют",
    expected_gain_from_contractual_cashflows: "Доход: договорные купоны + номинал минус стоимость входа",
    tax_not_applied_to_new_buy: "Налог к новой покупке не начисляется в сценарии",
  };

  const balancingReason = (value) => (
    BALANCING_REASON_LABELS[value] || String(value || "—")
  );

  const balancingNote = (value) => {
    const text = String(value || "—");
    if (BALANCING_NOTE_LABELS[text]) {
      return BALANCING_NOTE_LABELS[text];
    }
    if (text.startsWith("issuer_rating:")) {
      const [, agency, level, date] = text.split(":");
      return ["Рейтинг", agency, level, date].filter(Boolean).join(" · ");
    }
    return text;
  };

  const renderBalancing = (payload) => {
    balancingScenarios.replaceChildren();
    balancingScreening.replaceChildren();
    balancingFreeCash.textContent = payload.free_cash_rub
      ? formatMoney({currency: "RUB", value: payload.free_cash_rub})
      : "—";
    balancingCandidateCount.textContent = Number.isFinite(Number(payload.candidate_count))
      ? String(payload.candidate_count)
      : "—";
    balancingEligibleNote.textContent = Number.isFinite(Number(payload.eligible_candidate_count))
      ? `Допустимых сейчас: ${payload.eligible_candidate_count}`
      : "Допустимость ещё не рассчитана";
    balancingPolicyVersions.textContent = payload.profile_version && payload.policy_version
      ? `v${payload.profile_version} · v${payload.policy_version}`
      : "—";

    if (payload.status !== "observed") {
      const reason = balancingReason(payload.reason || payload.status);
      appendEmptyState(balancingScenarios, reason);
      appendEmptyState(
        balancingScreening,
        "Screening начнётся после выполнения обязательных условий.",
      );
      setStateBadge(balancingStatus, reason, "state-next");
      return;
    }

    const scenarioEntries = [];
    if (payload.scenarios?.hold) {
      scenarioEntries.push(["Hold", payload.scenarios.hold]);
    }
    if (payload.scenarios?.deploy_cash) {
      scenarioEntries.push(["Новые деньги", payload.scenarios.deploy_cash]);
    }
    (payload.scenarios?.replacements || []).forEach((scenario, index) => {
      scenarioEntries.push([`Замена ${index + 1}`, scenario]);
    });
    scenarioEntries.forEach(([label, scenario]) => {
      const row = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = `${label} · ${scenario.status === "feasible" ? "допустим" : "заблокирован"}`;
      const details = document.createElement("small");
      const tradeCount = Array.isArray(scenario.trades) ? scenario.trades.length : 0;
      const tradeSummary = (scenario.trades || []).map((trade) => {
        const direction = trade.action === "sell" ? "продать" : "купить";
        const ytw = trade.ytw_percent === null || trade.ytw_percent === undefined
          ? ""
          : `YTW ${trade.ytw_percent}%`;
        const tax = Number(trade.tax_rub) > 0
          ? `налог-сценарий ${formatMoney({currency: "RUB", value: trade.tax_rub})}`
          : "";
        const cost = Number(trade.estimated_cost_rub) > 0
          ? `издержки ${formatMoney({currency: "RUB", value: trade.estimated_cost_rub})}`
          : "";
        return [
          `${direction} ${trade.ticker || trade.instrument_uid}: ${trade.lots} лот.`,
          ytw,
          cost,
          tax,
        ].filter(Boolean).join(", ");
      }).join(" · ");
      details.textContent = [
        balancingReason(scenario.reason),
        `сделок: ${tradeCount}`,
        tradeSummary,
        scenario.turnover_rub !== undefined
          ? `оборот: ${formatMoney({currency: "RUB", value: scenario.turnover_rub})}`
          : "",
        scenario.residual_cash_rub !== undefined
          ? `остаток: ${formatMoney({currency: "RUB", value: scenario.residual_cash_rub})}`
          : "",
      ].filter(Boolean).join(" · ");
      row.append(title, details);
      balancingScenarios.append(row);
    });
    if (!balancingScenarios.childElementCount) {
      appendEmptyState(balancingScenarios, "Сценарии ещё не рассчитаны.");
    }

    (payload.screening || []).slice(0, 30).forEach((item) => {
      const row = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = [
        item.ticker || item.instrument_uid || "Инструмент",
        item.eligible ? "допустим" : "не допущен",
      ].join(" · ");
      const details = document.createElement("small");
      const blockers = (item.reasons || []).map(balancingReason);
      const evidenceNotes = (item.notes || []).map(balancingNote);
      const metrics = [
        item.ytw_percent !== null && item.ytw_percent !== undefined
          ? `YTW: ${item.ytw_percent}%`
          : "",
        item.duration_years !== null && item.duration_years !== undefined
          ? `дюрация: ${Number(item.duration_years).toFixed(2)} г.`
          : "",
        Number.isFinite(Number(item.liquidity_days))
          ? `ликвидность: ~${item.liquidity_days} дн.`
          : "",
        Number.isFinite(Number(item.max_liquid_lots))
          ? `лимит ликвидности: ${item.max_liquid_lots} лот.`
          : "",
        Number(item.transaction_cost_rub_per_lot) > 0
          ? `вход за лот: ${formatMoney({currency: "RUB", value: item.transaction_cost_rub_per_lot})}`
          : "",
        Number(item.expected_net_gain_rub_per_lot) !== 0
          ? `net-сценарий/лот: ${formatMoney({currency: "RUB", value: item.expected_net_gain_rub_per_lot})}`
          : "",
      ].filter(Boolean);
      const explanation = [...blockers, ...metrics, ...evidenceNotes];
      details.textContent = explanation.length
        ? explanation.join(" · ")
        : "Все текущие проверки кандидатов пройдены";
      row.append(title, details);
      balancingScreening.append(row);
    });
    if (!balancingScreening.childElementCount) {
      appendEmptyState(
        balancingScreening,
        "Каталог кандидатов пуст или ещё не прошёл доказательный screening.",
      );
    }

    if (payload.live_status === "degraded") {
      setStateBadge(balancingStatus, "Live evidence временно недоступен", "state-error");
    } else if (Number(payload.eligible_candidate_count) > 0) {
      setStateBadge(
        balancingStatus,
        `Read-only · допустимых: ${payload.eligible_candidate_count}`,
        "state-ok",
      );
    } else {
      setStateBadge(balancingStatus, "Read-only · все кандидаты заблокированы", "state-next");
    }
  };

  const PROPOSAL_STATUS_LABELS = {
    pending: "Ожидает решения",
    confirmed: "План подтверждён",
    rejected: "Отклонено",
    deferred: "Отложено",
    superseded: "Заменено новой версией",
    revoked: "Отозвано из-за изменения исходных данных",
    expired: "Срок действия истёк",
  };

  const proposalStatusLabel = (value) => (
    PROPOSAL_STATUS_LABELS[value] || String(value || "—")
  );

  const proposalScenarioLabel = (value) => (
    value === "replace" ? "Замена позиции" : "Размещение свободных денег"
  );

  const proposalTradeBoundText = (trade) => {
    if (trade.action === "sell") {
      return trade.min_proceeds_rub
        ? `min proceeds ${formatMoney({currency: "RUB", value: trade.min_proceeds_rub})}`
        : "";
    }
    return trade.max_spend_rub
      ? `max spend ${formatMoney({currency: "RUB", value: trade.max_spend_rub})}`
      : "";
  };

  const proposalTradeSummary = (trade) => {
    const action = trade.action === "sell" ? "продать" : "купить";
    const priceType = trade.limit_price_type === "point" ? "пункты" : "₽";
    const bound = proposalTradeBoundText(trade);
    return [
      `${action} ${trade.ticker || trade.instrument_uid}: ${trade.lots} лот.`,
      trade.limit_price ? `limit ${trade.limit_price} ${priceType}` : "",
      bound,
    ].filter(Boolean).join(" · ");
  };

  const renderProposalCreateOptions = (payload) => {
    proposalCreateOptions.replaceChildren();
    if (payload?.status !== "observed" || payload.live_status !== "received") {
      appendEmptyState(
        proposalCreateOptions,
        "Сначала нужен свежий полностью подтверждённый сценарий балансировки.",
      );
      return;
    }

    const addOption = (label, scenarioKind, scenario, replacedUid = null) => {
      if (
        scenario?.status !== "feasible"
        || !Array.isArray(scenario.trades)
        || !scenario.trades.length
        || !scenario.before_after
      ) {
        return;
      }
      const row = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = label;
      const details = document.createElement("small");
      details.textContent = [
        balancingReason(scenario.reason),
        ...scenario.trades.map(proposalTradeSummary),
        `expiry будет 10 мин. после фиксации`,
      ].filter(Boolean).join(" · ");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button button-primary";
      button.textContent = "Зафиксировать exact версию";
      button.dataset.proposalCreate = scenarioKind;
      if (replacedUid) {
        button.dataset.replacedInstrumentUid = replacedUid;
      }
      row.append(title, details, button);
      proposalCreateOptions.append(row);
    };

    addOption(
      "Новые деньги",
      "deploy_cash",
      payload.scenarios?.deploy_cash,
    );
    (payload.scenarios?.replacements || []).forEach((scenario) => {
      addOption(
        `Замена ${scenario.replaced_instrument_uid || "позиции"}`,
        "replace",
        scenario,
        scenario.replaced_instrument_uid || null,
      );
    });

    if (!proposalCreateOptions.childElementCount) {
      appendEmptyState(
        proposalCreateOptions,
        "Нет завершённого feasible-пакета, который можно зафиксировать.",
      );
    }
  };

  const proposalBeforeAfterText = (proposal) => {
    const before = proposal.payload?.scenario?.before_after?.before;
    const after = proposal.payload?.scenario?.before_after?.after;
    if (!before || !after) {
      return "Before/after отсутствует";
    }
    return [
      `NAV: ${formatMoney({currency: "RUB", value: before.nav_rub})} → ${formatMoney({currency: "RUB", value: after.nav_rub})}`,
      `cash: ${formatMoney({currency: "RUB", value: before.cash_rub})} → ${formatMoney({currency: "RUB", value: after.cash_rub})}`,
    ].join(" · ");
  };

  const proposalDecisionControls = (proposal) => {
    const controls = document.createElement("div");
    controls.className = "proposal-decision-controls";

    const rejectReason = document.createElement("input");
    rejectReason.type = "text";
    rejectReason.maxLength = 500;
    rejectReason.placeholder = "Причина отклонения (обязательно для «Отклонить»)";
    rejectReason.dataset.proposalRejectReason = proposal.id;

    const deferAt = document.createElement("input");
    deferAt.type = "datetime-local";
    deferAt.dataset.proposalDeferAt = proposal.id;
    deferAt.min = localDateTimeInputValue(new Date(Date.now() + 60_000));
    deferAt.setAttribute("aria-label", "Отложить предложение до даты и времени");
    deferAt.title = "Выберите будущие дату и время";

    const actions = document.createElement("div");
    actions.className = "proposal-decision-actions";
    for (const [action, label, className] of [
      ["confirm", "Подтвердить план", "button button-primary"],
      ["reject", "Отклонить", "button button-danger-secondary"],
      ["defer", "Отложить до даты", "button button-secondary"],
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = className;
      button.textContent = label;
      button.dataset.proposalDecision = action;
      button.dataset.proposalId = proposal.id;
      button.dataset.proposalVersion = String(proposal.version);
      button.dataset.proposalHash = proposal.hash;
      actions.append(button);
    }

    controls.append(rejectReason, deferAt, actions);
    return controls;
  };

  const EXECUTION_STATUS_LABELS = {
    created: "Создан",
    running: "Выполняется",
    reconciling: "Требует сверки",
    succeeded: "Завершён",
    cancelled: "Отменён",
    failed: "Ошибка",
  };

  const EXECUTION_ERROR_MESSAGES = {
    proposal_not_found: "Предложение больше недоступно. Обновите список решений.",
    proposal_not_confirmed: "Сначала подтвердите exact-версию предложения.",
    proposal_version_mismatch: "Версия предложения изменилась. Обновите список решений.",
    proposal_hash_mismatch: "Hash предложения не совпадает. Не повторяйте старое действие; обновите данные.",
    proposal_expired: "Срок действия предложения истёк. Постройте и подтвердите новую версию.",
    proposal_snapshot_stale: "Портфель изменился после предложения. Нужен новый snapshot и новое решение.",
    proposal_profile_stale: "Профиль капитала изменился. Пересчитайте предложение.",
    proposal_policy_stale: "Лимиты балансировки изменились. Пересчитайте предложение.",
    sandbox_account_mismatch: "Подключите тот же Sandbox-счёт, для которого было создано предложение.",
    sandbox_buy_lots_exceed_available: "Песочница не разрешает запрошенное количество лотов для покупки.",
    sandbox_sell_lots_exceed_available: "Песочница не подтверждает нужное количество лотов для продажи.",
    sandbox_buy_would_overspend: "Предварительная стоимость превышает max spend предложения. Заявка не отправлена.",
    sandbox_sell_below_min_proceeds: "Предварительная сумма ниже min proceeds предложения. Заявка не отправлена.",
    sandbox_submit_ambiguous: "Ответ на отправку неоднозначен. Повторная заявка запрещена; используйте «Сверить Sandbox».",
    sandbox_order_not_found_yet: "Заявка пока не найдена по сохранённому request ID. Повторная отправка запрещена.",
    sandbox_reconcile_unavailable: "T-Invest временно недоступен. Run сохранён для повторной сверки.",
    sandbox_cancel_ambiguous: "Отмена не подтверждена однозначно. Run оставлен на сверке.",
    sandbox_request_id_mismatch: "Provider вернул другой request ID. Run остановлен для безопасной сверки.",
    sandbox_instrument_mismatch: "Provider вернул другой инструмент. Run остановлен для безопасной сверки.",
    sandbox_lot_count_mismatch: "Provider вернул другое количество лотов. Run остановлен для безопасной сверки.",
    sandbox_direction_mismatch: "Provider вернул другое направление сделки. Run остановлен для безопасной сверки.",
    sandbox_order_type_mismatch: "Provider вернул не limit-заявку. Run остановлен для безопасной сверки.",
    sandbox_provider_overspend_detected: "Provider сообщил сумму выше max spend. Следующие действия остановлены.",
    sandbox_provider_min_proceeds_breach: "Provider сообщил сумму ниже min proceeds. Следующие действия остановлены.",
    live_execution_disabled: "Production live сейчас выключен server-side. Реальная заявка не отправлена.",
    live_mandate_required: "Для live-run требуется активное разрешение на exact production-счёт.",
    live_execution_already_active: "На этом production-счёте уже есть незавершённый Live-run. Сначала сверьте или отмените его; новая реальная заявка не создана.",
    live_mandate_inactive: "Live-разрешение отозвано или истекло. Новая заявка запрещена; уже отправленную можно только сверить или отменить.",
    live_account_mismatch: "Подключите exact production-счёт, для которого создано предложение и live-разрешение.",
    live_write_access_required: "T-Invest не подтвердил полный доступ к выбранному production-счёту.",
    live_canary_deploy_cash_only: "Реальное исполнение допускает только сценарий размещения свободных средств.",
    live_canary_buy_only: "Реальное исполнение пока допускает только покупки; замена и продажа остаются заблокированы.",
    live_order_notional_cap_exceeded: "Предварительная стоимость превышает лимит одной live-заявки. Заявка не отправлена.",
    live_daily_notional_cap_exceeded: "Дневной live-лимит исчерпан. Заявка не отправлена.",
    live_buy_lots_exceed_available: "T-Invest не подтверждает доступное количество лотов для live-покупки.",
    live_buy_would_overspend: "Предварительная стоимость превышает max spend подтверждённого предложения.",
    live_submit_ambiguous: "Ответ production PostOrder неоднозначен. Повторная отправка запрещена; используйте сверку по сохранённому request ID.",
    live_order_not_found_yet: "Production-заявка пока не найдена по request ID. Новая заявка не отправляется.",
    live_reconcile_unavailable: "T-Invest временно недоступен. Live-run сохранён для безопасной повторной сверки.",
    live_cancel_ambiguous: "Отмена production-заявки не подтверждена. Run остаётся на сверке.",
    live_request_id_mismatch: "T-Invest вернул другой request ID. Live-run остановлен для безопасной сверки.",
    live_instrument_mismatch: "T-Invest вернул другой инструмент. Live-run остановлен.",
    live_lot_count_mismatch: "T-Invest вернул другое количество лотов. Live-run остановлен.",
    live_direction_mismatch: "T-Invest вернул другое направление сделки. Live-run остановлен.",
    live_order_type_mismatch: "T-Invest вернул не limit-заявку. Live-run остановлен.",
    live_provider_overspend_detected: "Фактическая production-сумма выше max spend. Следующие действия остановлены.",
  };

  const executionErrorMessage = (error, fallback) => (
    EXECUTION_ERROR_MESSAGES[String(error?.message || "")] || fallback
  );

  const executionStatusLabel = (value) => (
    EXECUTION_STATUS_LABELS[value] || String(value || "—")
  );

  const EXECUTION_MODE_LABELS = {
    shadow: "Shadow",
    sandbox: "Sandbox",
    live: "Live canary",
  };

  const executionModeLabel = (value) => (
    EXECUTION_MODE_LABELS[value] || String(value || "—")
  );

  const executionAdvanceLabel = (run) => {
    if (run.mode === "live") {
      return run.status === "created"
        ? "Отправить реальную limit-заявку"
        : "Сверить Live по request ID";
    }
    return run.status === "created"
      ? "Отправить следующую Sandbox limit-заявку"
      : "Сверить Sandbox";
  };

  const executionStartSuccessMessage = (mode) => {
    if (mode === "shadow") {
      return "Shadow-репетиция записана. Broker mutation не выполнялась.";
    }
    if (mode === "sandbox") {
      return "Sandbox state machine запущена. Production-заявка не создавалась.";
    }
    return (
      "Live-canary run создан. Реальная заявка ещё не отправлена: "
      + "проверьте детали и нажмите отдельную кнопку отправки."
    );
  };

  const executionMutationSuccessMessage = (mode, action) => {
    if (mode === "live") {
      return action === "cancel"
        ? "Live cancel/reconciliation записан в immutable журнал."
        : "Live состояние сверено по сохранённому request ID.";
    }
    return action === "cancel"
      ? "Sandbox cancel/reconciliation записан в immutable журнал."
      : "Состояние Sandbox сверено по сохранённому request ID.";
  };

  const terminalExecutionStatus = (value) => (
    ["succeeded", "cancelled", "failed"].includes(value)
  );

  const renderLiveMandate = (payload) => {
    const source = (
      payload !== null
      && typeof payload === "object"
    ) ? payload : {};
    liveOperatorEnabled = source.operator_enabled === true;
    liveOperatorMaxOrder = Number(source.operator_max_order_notional_rub) || 0;
    liveOperatorMaxDaily = Number(source.operator_max_daily_notional_rub) || 0;
    liveMandate = (
      source.mandate !== null
      && typeof source.mandate === "object"
    ) ? source.mandate : null;

    if (
      !(liveMaxOrder instanceof HTMLInputElement)
      || !(liveMaxDaily instanceof HTMLInputElement)
      || !(liveExpiresAt instanceof HTMLInputElement)
      || !(liveProfileId instanceof HTMLInputElement)
      || !(liveConfirm instanceof HTMLInputElement)
    ) {
      throw new TypeError("Live mandate form has invalid controls");
    }

    liveMaxOrder.max = String(liveOperatorMaxOrder || 1);
    liveMaxDaily.max = String(liveOperatorMaxDaily || 1);
    const now = Date.now();
    liveExpiresAt.min = localDateTimeInputValue(new Date(now + 5 * 60 * 1000));
    liveExpiresAt.max = localDateTimeInputValue(new Date(now + 24 * 60 * 60 * 1000));
    liveProfileId.placeholder = currentProfileId || "000000001";

    if (!liveOperatorEnabled) {
      liveMandateForm.classList.add("hidden");
      liveMandateRevoke.classList.add("hidden");
      setStateBadge(liveMandateStatus, "Выключен server-side", "state-next");
      liveMandateSummary.textContent = (
         "Реальное исполнение технически подготовлено, но не активировано: "
        + "опубликованные legal-документы v6 описывают режим без реальных поручений. "
        + "Shadow и Sandbox продолжают работать."
      );
      syncExecutionControls();
      return;
    }

    const connectedProduction = (
      source.connected_environment === "prod"
      && typeof source.connected_account_id === "string"
      && source.connected_account_id !== ""
    );
    liveMandateForm.classList.toggle("hidden", !connectedProduction);
    if (!connectedProduction) {
      setStateBadge(liveMandateStatus, "Нужен production-счёт", "state-next");
      liveMandateSummary.textContent = (
        "Live gate включён, но сначала подключите exact production T-Invest счёт. "
        + "Sandbox-счёт не может получить production authority."
      );
      syncExecutionControls();
      return;
    }

    if (liveMandate) {
      setStateBadge(liveMandateStatus, "Mandate активен", "state-ok");
      liveMandateSummary.textContent = [
        "Разрешение действует до " + formatDateTime(liveMandate.expires_at),
        "лимит одной заявки " + formatRub(liveMandate.max_order_notional_rub),
        "дневной лимит " + formatRub(liveMandate.max_daily_notional_rub),
      ].join(" · ");
      liveMaxOrder.disabled = true;
      liveMaxDaily.disabled = true;
      liveExpiresAt.disabled = true;
      liveProfileId.disabled = true;
      liveConfirm.disabled = true;
      liveMandateSave.classList.add("hidden");
      liveMandateRevoke.classList.remove("hidden");
    } else {
      setStateBadge(liveMandateStatus, "Разрешение не создано", "state-next");
      liveMandateSummary.textContent = (
        "Production live остаётся без authority, пока вы явно не зададите caps, "
        + "срок и ID профиля. Создание mandate само по себе не отправляет заявку."
      );
      liveMaxOrder.disabled = false;
      liveMaxDaily.disabled = false;
      liveExpiresAt.disabled = false;
      liveProfileId.disabled = false;
      liveConfirm.disabled = false;
      liveMandateSave.classList.remove("hidden");
      liveMandateRevoke.classList.add("hidden");
    }
    syncExecutionControls();
  };

  const loadLiveMandate = async () => {
    try {
      const payload = await api("/api/portfolio/live-execution/mandate", {
        method: "GET",
      });
      renderLiveMandate(payload);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      liveOperatorEnabled = false;
      liveMandate = null;
      liveMandateForm.classList.add("hidden");
      setStateBadge(liveMandateStatus, "Не удалось проверить gate", "state-error");
      liveMandateSummary.textContent = (
        "Live authority не считается активной без успешной server-side проверки."
      );
    }
  };

  const saveLiveMandate = async () => {
    if (liveMandateRequestInFlight) {
      return;
    }
    if (!liveOperatorEnabled) {
      showMessage(
        liveMandateMessage,
        "Production live выключен server-side. Разрешение не создано.",
        true,
      );
      return;
    }
    if (!validateFormWithMessage(
      liveMandateForm,
      liveMandateMessage,
      "Проверьте параметры live-разрешения.",
    )) {
      return;
    }
    const connectedAccountId = typeof tbankAccountId === "string" ? tbankAccountId : "";
    const maxOrder = Number(liveMaxOrder.value);
    const maxDaily = Number(liveMaxDaily.value);
    const expires = new Date(liveExpiresAt.value);
    const now = Date.now();
    if (
      !connectedAccountId
      || connectedTbankEnvironment !== "prod"
      || !Number.isFinite(maxOrder)
      || !Number.isFinite(maxDaily)
      || maxOrder <= 0
      || maxDaily < maxOrder
      || maxOrder > liveOperatorMaxOrder
      || maxDaily > liveOperatorMaxDaily
      || Number.isNaN(expires.getTime())
      || expires.getTime() <= now
      || expires.getTime() > now + 24 * 60 * 60 * 1000
      || liveProfileId.value.trim() !== currentProfileId
      || !liveConfirm.checked
    ) {
      showMessage(
        liveMandateMessage,
        "Проверьте exact production-счёт, caps, срок до 24 часов, ID профиля и явное подтверждение.",
        true,
      );
      return;
    }
    if (!window.confirm(
      "Создать краткоживущее разрешение на реальные заявки? Это не отправляет поручение само по себе, но позволит отдельно запустить подтверждённый Live-canary пакет.",
    )) {
      return;
    }

    liveMandateRequestInFlight = true;
    liveMandateSave.disabled = true;
    try {
      await api("/api/portfolio/live-execution/mandate", {
        method: "PUT",
        body: JSON.stringify({
          account_id: connectedAccountId,
          max_order_notional_rub: String(maxOrder),
          max_daily_notional_rub: String(maxDaily),
          expires_at: expires.toISOString(),
          confirm_public_id: liveProfileId.value.trim(),
          confirm_live_execution: true,
        }),
      });
      showMessage(
        liveMandateMessage,
        "Live-разрешение создано. Реальная заявка не отправлялась.",
      );
      await loadLiveMandate();
      await loadProposals();
      await loadExecutions();
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      showMessage(
        liveMandateMessage,
        executionErrorMessage(
          error,
          "Live-разрешение не создано. Production authority не изменилась.",
        ),
        true,
      );
    } finally {
      liveMandateSave.disabled = false;
      liveMandateRequestInFlight = false;
    }
  };

  const revokeLiveMandate = async () => {
    if (liveMandateRequestInFlight || !liveMandate) {
      return;
    }
    if (!window.confirm(
      "Включить kill switch? Новые production-заявки будут запрещены. Уже отправленные заявки останутся в журнале для сверки/отмены.",
    )) {
      return;
    }
    liveMandateRequestInFlight = true;
    liveMandateRevoke.disabled = true;
    try {
      await api("/api/portfolio/live-execution/mandate", {method: "DELETE"});
      showMessage(
        liveMandateMessage,
        "Kill switch включён: новые live-заявки запрещены.",
      );
      await loadLiveMandate();
      await loadProposals();
      await loadExecutions({inspectLatest: true});
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      showMessage(
        liveMandateMessage,
        "Не удалось подтвердить отзыв разрешения. До успешной проверки не считайте kill switch применённым.",
        true,
      );
    } finally {
      liveMandateRevoke.disabled = false;
      liveMandateRequestInFlight = false;
    }
  };

  const syncExecutionControls = () => {
    const connectedAccountId = typeof tbankAccountId === "string" ? tbankAccountId : "";
    const sandboxConnected = tbankIsConnected && connectedTbankEnvironment === "sandbox";
    const liveConnected = tbankIsConnected && connectedTbankEnvironment === "prod";
    const activeMandateId = String(liveMandate?.id || "");
    const activeMandateAccount = String(liveMandate?.account_id || "");

    proposalHistory.querySelectorAll("button[data-execution-start]").forEach((element) => {
      if (!(element instanceof HTMLButtonElement)) {
        return;
      }
      const mode = element.dataset.executionStart || "";
      const proposalAccountId = element.dataset.proposalAccountId || "";
      const scenarioKind = element.dataset.proposalScenarioKind || "";
      if (mode === "sandbox") {
        const accountMatches = (
          sandboxConnected
          && connectedAccountId !== ""
          && proposalAccountId === connectedAccountId
        );
        element.disabled = !accountMatches;
        element.title = accountMatches
          ? "Создать run для exact-пакета этого Sandbox-счёта"
          : "Sandbox требует тот же счёт, для которого создан подтверждённый план.";
        return;
      }
      if (mode !== "live") {
        return;
      }
      element.classList.toggle("hidden", !liveOperatorEnabled);
      const ready = (
        liveOperatorEnabled
        && liveConnected
        && activeMandateId !== ""
        && activeMandateAccount === connectedAccountId
        && proposalAccountId === connectedAccountId
        && scenarioKind === "deploy_cash"
      );
      element.disabled = !ready;
      element.title = ready
        ? "Создать live-run. Реальная заявка появится только после отдельного действия «Отправить»."
        : "Live требует active mandate, exact production account и deploy_cash canary.";
    });

    executionHistory.querySelectorAll("button[data-execution-action]").forEach((element) => {
      if (!(element instanceof HTMLButtonElement)) {
        return;
      }
      const mode = element.dataset.executionMode || "";
      const executionAccountId = element.dataset.executionAccountId || "";
      if (mode === "sandbox") {
        const accountMatches = (
          sandboxConnected
          && connectedAccountId !== ""
          && executionAccountId === connectedAccountId
        );
        element.disabled = !accountMatches;
        element.title = accountMatches
          ? ""
          : "Для управления run подключите тот же exact Sandbox-счёт.";
        return;
      }
      if (mode !== "live") {
        return;
      }

      const accountMatches = (
        liveConnected
        && connectedAccountId !== ""
        && executionAccountId === connectedAccountId
      );
      if (!accountMatches) {
        element.disabled = true;
        element.title = "Для recovery подключите тот же exact production-счёт.";
        return;
      }

      const needsSubmissionAuthority = (
        element.dataset.executionAction === "advance"
        && element.dataset.executionStatus === "created"
      );
      const submissionAuthorityReady = (
        liveOperatorEnabled
        && activeMandateId !== ""
        && element.dataset.executionMandateId === activeMandateId
      );
      element.disabled = needsSubmissionAuthority && !submissionAuthorityReady;
      element.title = element.disabled
        ? "Kill switch/expiry блокирует отправку. Pending run можно безопасно завершить кнопкой «Отменить Live»."
        : "";
    });
  };

  const proposalExecutionControls = (proposal) => {
    const controls = document.createElement("div");
    controls.className = "proposal-decision-actions";

    const shadow = document.createElement("button");
    shadow.type = "button";
    shadow.className = "button button-secondary";
    shadow.textContent = "Shadow-репетиция";
    shadow.dataset.executionStart = "shadow";

    const sandbox = document.createElement("button");
    sandbox.type = "button";
    sandbox.className = "button button-secondary";
    sandbox.textContent = "Создать Sandbox-run";
    sandbox.dataset.executionStart = "sandbox";

    const live = document.createElement("button");
    live.type = "button";
    live.className = "button button-danger-secondary hidden";
    live.textContent = "Создать Live-canary run";
    live.dataset.executionStart = "live";

    const proposalId = String(proposal?.id || "");
    const proposalVersion = String(proposal?.version || "");
    const proposalHash = String(proposal?.hash || "");
    const proposalAccountId = String(proposal?.account_id || "");
    const proposalScenarioKind = String(proposal?.scenario_kind || "");

    for (const button of [shadow, sandbox, live]) {
      button.dataset.proposalId = proposalId;
      button.dataset.proposalVersion = proposalVersion;
      button.dataset.proposalHash = proposalHash;
      button.dataset.proposalAccountId = proposalAccountId;
      button.dataset.proposalScenarioKind = proposalScenarioKind;
      controls.append(button);
    }
    return controls;
  };

  const renderProposals = (items) => {
    proposalHistory.replaceChildren();
    const proposals = Array.isArray(items) ? items : [];
    const pending = proposals.filter((item) => item.status === "pending");

    proposals.slice(0, 12).forEach((proposal) => {
      const row = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = [
        `v${proposal.version}`,
        proposalScenarioLabel(proposal.scenario_kind),
        proposalStatusLabel(proposal.status),
      ].join(" · ");

      const details = document.createElement("small");
      const trades = proposal.payload?.scenario?.trades || [];
      details.textContent = [
        `счёт: ${proposal.account_id || "—"}`,
        `hash: ${String(proposal.hash || "").slice(0, 16)}…`,
        `до: ${formatDateTime(proposal.expires_at)}`,
        proposalBeforeAfterText(proposal),
        ...trades.map(proposalTradeSummary),
        proposal.decision_user_reason
          ? `причина: ${proposal.decision_user_reason}`
          : "",
        proposal.deferred_until
          ? `отложено до: ${formatDateTime(proposal.deferred_until)}`
          : "",
      ].filter(Boolean).join(" · ");
      row.append(title, details);

      if (proposal.status === "pending") {
        row.append(proposalDecisionControls(proposal));
      } else if (proposal.status === "confirmed") {
        row.append(proposalExecutionControls(proposal));
      }
      proposalHistory.append(row);
    });

    if (!proposalHistory.childElementCount) {
      appendEmptyState(
        proposalHistory,
        "Immutable proposals ещё не создавались.",
      );
    }

    if (pending.length) {
      const firstPending = pending[0];
      setHomeAttentionBucket("proposals", [{
        severity: "warning",
        title: pending.length === 1
          ? `План v${firstPending.version} ожидает решения`
          : `Планов ожидает решения: ${pending.length}`,
        detail: `Текущая версия действует до ${formatDateTime(firstPending.expires_at)}.`,
        view: "decisions",
      }]);
      setStateBadge(
        proposalStatus,
        `Ожидает решения: v${pending[0].version}`,
        "state-next",
      );
    } else if (proposals.length) {
      setHomeAttentionBucket("proposals", []);
      setStateBadge(
        proposalStatus,
        proposalStatusLabel(proposals[0].status),
        proposals[0].status === "confirmed" ? "state-ok" : "state-next",
      );
    } else {
      setHomeAttentionBucket("proposals", []);
      setStateBadge(proposalStatus, "Нет активного предложения", "state-next");
    }
    syncExecutionControls();
  };

  const loadProposals = async () => {
    try {
      const result = await api("/api/portfolio/proposals", {method: "GET"});
      renderProposals(result.proposals || []);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      proposalHistory.replaceChildren();
      appendEmptyState(proposalHistory, "Не удалось загрузить версии предложений.");
      setHomeAttentionBucket("proposals", [{
        severity: "warning",
        title: "Статус планов не подтверждён",
        detail: "Не удалось прочитать сохранённые версии предложений. Торговое действие не выполнялось.",
        view: "decisions",
      }]);
      setStateBadge(proposalStatus, "Ошибка чтения proposals", "state-error");
    }
  };

  const createProposal = async (button) => {
    if (proposalRequestInFlight) {
      return;
    }
    proposalRequestInFlight = true;
    showMessage(proposalMessage, "");
    button.disabled = true;
    try {
      const body = {
        scenario_kind: button.dataset.proposalCreate,
        replaced_instrument_uid: button.dataset.replacedInstrumentUid || null,
      };
      const result = await api("/api/portfolio/proposals", {
        method: "POST",
        body: JSON.stringify(body),
      });
      showMessage(
        proposalMessage,
        `Зафиксирована immutable версия v${result.proposal.version}. Подтверждение не отправляет заявки брокеру.`,
      );
      await loadProposals();
      await loadExecutions();
    } catch (error) {
      showMessage(
        proposalMessage,
        error.status === 409
          ? "Сценарий изменился или устарел. Обновите балансировку и зафиксируйте новую версию."
          : "Не удалось зафиксировать предложение. Предыдущие версии не изменены.",
        true,
      );
      if (error.status === 401) {
        location.reload();
      }
    } finally {
      button.disabled = false;
      proposalRequestInFlight = false;
    }
  };

  const decideProposal = async (button) => {
    if (proposalRequestInFlight) {
      return;
    }
    const proposalId = button.dataset.proposalId;
    const action = button.dataset.proposalDecision;
    const reason = proposalHistory.querySelector(
      `[data-proposal-reject-reason="${proposalId}"]`,
    );
    const deferAt = proposalHistory.querySelector(
      `[data-proposal-defer-at="${proposalId}"]`,
    );

    const rejectReason = reason?.value.trim() || "";
    if (action === "reject" && !rejectReason) {
      showMessage(proposalMessage, "Для отклонения укажите причину.", true);
      reason?.focus();
      return;
    }

    let deferredUntil = null;
    if (action === "defer") {
      const deferValue = deferAt?.value || "";
      if (!deferValue) {
        showMessage(proposalMessage, "Для отсрочки выберите дату и время.", true);
        deferAt?.focus();
        return;
      }
      const deferredDate = new Date(deferValue);
      if (
        Number.isNaN(deferredDate.getTime())
        || deferredDate.getTime() <= Date.now()
      ) {
        showMessage(
          proposalMessage,
          "Дата отсрочки должна быть в будущем. Выберите новую дату и время.",
          true,
        );
        deferAt?.focus();
        return;
      }
      deferredUntil = deferredDate.toISOString();
    }

    proposalRequestInFlight = true;
    showMessage(proposalMessage, "");
    button.disabled = true;
    try {
      const body = {
        action,
        proposal_version: Number(button.dataset.proposalVersion),
        proposal_hash: button.dataset.proposalHash,
        reason: action === "reject" ? rejectReason : null,
        deferred_until: deferredUntil,
      };
      const result = await api(
        `/api/portfolio/proposals/${uuidPathSegment(proposalId)}/decision`,
        {method: "POST", body: JSON.stringify(body)},
      );
      showMessage(
        proposalMessage,
        `${proposalStatusLabel(result.proposal.status)}. Broker execution выключен.`,
      );
      await loadProposals();
      await loadExecutions();
    } catch (error) {
      showMessage(
        proposalMessage,
        error.status === 409
          ? "Эта версия уже решена, истекла или её исходные данные изменились."
          : "Не удалось записать решение. Повторная торговая операция не создавалась.",
        true,
      );
      if (error.status === 401) {
        location.reload();
      }
    } finally {
      button.disabled = false;
      proposalRequestInFlight = false;
    }
  };

  const renderExecutionDetails = (payload) => {
    executionDetails.replaceChildren();
    const run = (
      payload !== null
      && typeof payload === "object"
      && payload.execution !== null
      && typeof payload.execution === "object"
    ) ? payload.execution : null;
    if (!run) {
      appendEmptyState(executionDetails, "Выберите запуск из журнала.");
      return;
    }

    const summary = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = [
      executionModeLabel(run.mode),
      executionStatusLabel(run.status),
      `proposal v${run.proposal_version}`,
    ].join(" · ");
    const details = document.createElement("small");
    details.textContent = [
      `run: ${String(run.id || "").slice(0, 8)}…`,
      `account: ••••${String(run.account_id || "").slice(-6)}`,
      run.error_code ? `код: ${run.error_code}` : "",
      `создан: ${formatDateTime(run.created_at)}`,
    ].filter(Boolean).join(" · ");
    summary.append(title, details);
    executionDetails.append(summary);

    const legs = Array.isArray(run.legs) ? run.legs : [];
    legs.forEach((leg) => {
      if (leg === null || typeof leg !== "object") {
        return;
      }
      const row = document.createElement("div");
      const legTitle = document.createElement("strong");
      legTitle.textContent = [
        `#${Number(leg.leg_index) + 1}`,
        leg.action === "buy" ? "BUY" : "SELL",
        executionStatusLabel(leg.status),
      ].join(" · ");
      const legDetails = document.createElement("small");
      legDetails.textContent = [
        `UID: ${String(leg.instrument_uid || "").slice(0, 16)}…`,
        `лоты: ${leg.lots_executed}/${leg.lots_requested}`,
        `limit: ${leg.limit_price} (${leg.limit_price_type})`,
        `request: ${String(leg.request_id || "").slice(0, 8)}…`,
        `сумма: ${formatMoney({currency: "RUB", value: leg.executed_amount_rub})}`,
        `комиссия: ${formatMoney({currency: "RUB", value: leg.executed_commission_rub})}`,
      ].join(" · ");
      row.append(legTitle, legDetails);
      executionDetails.append(row);
    });

    const events = Array.isArray(payload.events) ? payload.events : [];
    events.slice(-12).forEach((event) => {
      if (event === null || typeof event !== "object") {
        return;
      }
      const row = document.createElement("div");
      const eventTitle = document.createElement("strong");
      eventTitle.textContent = `Событие · ${event.event_type || "unknown"}`;
      const eventDetails = document.createElement("small");
      eventDetails.textContent = formatDateTime(event.created_at);
      row.append(eventTitle, eventDetails);
      executionDetails.append(row);
    });
  };

  const loadExecutionDetails = async (runId) => {
    if (typeof runId !== "string" || runId.length === 0) {
      executionDetails.replaceChildren();
      appendEmptyState(executionDetails, "Не удалось определить запуск для просмотра.");
      return;
    }
    try {
      const payload = await api(`/api/portfolio/executions/${uuidPathSegment(runId)}`, {method: "GET"});
      renderExecutionDetails(payload);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      executionDetails.replaceChildren();
      appendEmptyState(executionDetails, "Не удалось загрузить состояние запуска.");
    }
  };

  const renderExecutions = (items) => {
    executionHistory.replaceChildren();
    const runs = Array.isArray(items)
      ? items.filter((item) => item !== null && typeof item === "object")
      : [];

    runs.slice(0, 12).forEach((run) => {
      const row = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = [
        executionModeLabel(run.mode),
        executionStatusLabel(run.status),
        `proposal v${run.proposal_version}`,
      ].join(" · ");
      const details = document.createElement("small");
      details.textContent = [
        `run: ${String(run.id || "").slice(0, 8)}…`,
        `создан: ${formatDateTime(run.created_at)}`,
        run.error_code ? `код: ${run.error_code}` : "",
      ].filter(Boolean).join(" · ");

      const actions = document.createElement("div");
      actions.className = "proposal-decision-actions";

      const inspect = document.createElement("button");
      inspect.type = "button";
      inspect.className = "button button-secondary";
      inspect.textContent = "Детали";
      inspect.dataset.executionInspect = String(run.id || "");
      actions.append(inspect);

      if (
        ["sandbox", "live"].includes(run.mode)
        && !terminalExecutionStatus(run.status)
      ) {
        const advance = document.createElement("button");
        advance.type = "button";
        advance.className = "button button-primary";
        advance.textContent = executionAdvanceLabel(run);
        advance.dataset.executionAction = "advance";
        advance.dataset.executionId = String(run.id || "");
        advance.dataset.executionAccountId = String(run.account_id || "");
        advance.dataset.executionMode = String(run.mode || "");
        advance.dataset.executionStatus = String(run.status || "");
        advance.dataset.executionMandateId = String(run.live_mandate_id || "");

        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "button button-danger-secondary";
        cancel.textContent = run.mode === "live" ? "Отменить Live" : "Отменить Sandbox";
        cancel.dataset.executionAction = "cancel";
        cancel.dataset.executionId = String(run.id || "");
        cancel.dataset.executionAccountId = String(run.account_id || "");
        cancel.dataset.executionMode = String(run.mode || "");
        cancel.dataset.executionStatus = String(run.status || "");
        cancel.dataset.executionMandateId = String(run.live_mandate_id || "");

        actions.append(advance, cancel);
      }

      row.append(title, details, actions);
      executionHistory.append(row);
    });

    if (!executionHistory.childElementCount) {
      appendEmptyState(
        executionHistory,
        "Проверка исполнения ещё не запускалась. Сначала подтвердите план.",
      );
      executionDetails.replaceChildren();
      appendEmptyState(executionDetails, "Состояние запуска появится после shadow/sandbox.");
      setStateBadge(
        executionStatus,
        liveOperatorEnabled ? "Live gate доступен · запусков нет" : "Live выключен · запусков нет",
        "state-next",
      );
      return;
    }

    const active = runs.find((run) => !terminalExecutionStatus(run.status));
    if (active) {
      setStateBadge(
        executionStatus,
        `${executionModeLabel(active.mode)} · ${executionStatusLabel(active.status)}`,
        active.status === "reconciling" ? "state-error" : "state-next",
      );
      return;
    }
    setStateBadge(
      executionStatus,
      liveOperatorEnabled ? "Live gate доступен · журнал готов" : "Live выключен · журнал готов",
      "state-ok",
    );
  };

  const loadExecutions = async ({inspectLatest = false} = {}) => {
    try {
      const result = await api("/api/portfolio/executions", {method: "GET"});
      const runs = (
        result !== null
        && typeof result === "object"
        && Array.isArray(result.executions)
      ) ? result.executions : [];
      renderExecutions(runs);
      const latestRun = runs[0];
      const latestRunId = typeof latestRun?.id === "string" ? latestRun.id : "";
      if (inspectLatest && latestRunId) {
        await loadExecutionDetails(latestRunId);
      }
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      executionHistory.replaceChildren();
      executionDetails.replaceChildren();
      appendEmptyState(executionHistory, "Не удалось загрузить журнал исполнения.");
      setStateBadge(executionStatus, "Ошибка чтения исполнения", "state-error");
    }
  };

  const executionStartBlocker = (mode, proposalAccountId) => {
    const connectedAccountId = typeof tbankAccountId === "string" ? tbankAccountId : "";
    if (
      mode === "sandbox"
      && (
        connectedTbankEnvironment !== "sandbox"
        || !connectedAccountId
        || proposalAccountId !== connectedAccountId
      )
    ) {
      return (
        "Sandbox-run требует тот же exact Sandbox account_id, "
        + "из которого построено подтверждённое предложение."
      );
    }
    if (
      mode === "live"
      && (
        !liveOperatorEnabled
        || connectedTbankEnvironment !== "prod"
        || !connectedAccountId
        || proposalAccountId !== connectedAccountId
        || liveMandate?.account_id !== connectedAccountId
      )
    ) {
      return (
        "Live-run заблокирован: нужен active mandate "
        + "и тот же exact production account_id."
      );
    }
    return "";
  };

  const confirmLiveRunCreation = (mode) => (
    mode !== "live"
    || window.confirm(
      "Создать Live-canary run? Это ещё не отправляет заявку. "
      + "Реальное поручение потребует отдельного нажатия "
      + "«Отправить реальную limit-заявку».",
    )
  );

  const startExecution = async (button) => {
    if (!(button instanceof HTMLButtonElement) || executionRequestInFlight) {
      return;
    }

    const mode = button.dataset.executionStart || "";
    const proposalId = button.dataset.proposalId || "";
    const proposalHash = button.dataset.proposalHash || "";
    const proposalAccountId = button.dataset.proposalAccountId || "";
    const proposalVersion = Number(button.dataset.proposalVersion);
    if (
      !["shadow", "sandbox", "live"].includes(mode)
      || !UUID_PATTERN.test(proposalId)
      || !/^[0-9a-fA-F]{64}$/.test(proposalHash)
      || !Number.isInteger(proposalVersion)
      || proposalVersion < 1
    ) {
      showMessage(
        executionMessage,
        "Параметры запуска повреждены. Обновите страницу и выберите предложение заново.",
        true,
      );
      return;
    }

    const blocker = executionStartBlocker(mode, proposalAccountId);
    if (blocker) {
      showMessage(executionMessage, blocker, true);
      return;
    }
    if (!confirmLiveRunCreation(mode)) {
      return;
    }

    executionRequestInFlight = true;
    showMessage(executionMessage, "");
    button.disabled = true;
    try {
      const result = await api("/api/portfolio/executions", {
        method: "POST",
        body: JSON.stringify({
          proposal_id: proposalId,
          proposal_version: proposalVersion,
          proposal_hash: proposalHash,
          mode,
        }),
      });
      const runId = typeof result?.execution?.id === "string"
        ? result.execution.id
        : "";
      if (!UUID_PATTERN.test(runId)) {
        throw new TypeError("execution response is missing a valid run id");
      }

      showMessage(executionMessage, executionStartSuccessMessage(mode));
      await loadExecutions();
      await loadExecutionDetails(runId);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      showMessage(
        executionMessage,
        executionErrorMessage(
          error,
          error.status === 409
            ? "Запуск заблокирован: предложение устарело или контур счёта изменился."
            : "Проверка исполнения не запущена. Production-заявка не создавалась.",
        ),
        true,
      );
    } finally {
      button.disabled = false;
      executionRequestInFlight = false;
      syncExecutionControls();
    }
  };

  const mutateExecution = async (button) => {
    if (!(button instanceof HTMLButtonElement) || executionRequestInFlight) {
      return;
    }
    const runId = button.dataset.executionId || "";
    const action = button.dataset.executionAction || "";
    const mode = button.dataset.executionMode || "";
    if (
      !UUID_PATTERN.test(runId)
      || !["advance", "cancel"].includes(action)
      || !["sandbox", "live"].includes(mode)
    ) {
      showMessage(
        executionMessage,
        "Действие запуска повреждено. Обновите журнал перед повтором.",
        true,
      );
      return;
    }

    executionRequestInFlight = true;
    showMessage(executionMessage, "");
    button.disabled = true;
    try {
      await api(`/api/portfolio/executions/${uuidPathSegment(runId)}/${executionActionSegment(action)}`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      showMessage(executionMessage, executionMutationSuccessMessage(mode, action));
      await loadExecutions();
      await loadExecutionDetails(runId);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      showMessage(
        executionMessage,
        executionErrorMessage(
          error,
          error.status === 503
            ? "Provider недоступен. Run оставлен в безопасном состоянии для последующей сверки."
            : "Действие исполнения не выполнено. Запуск не продвинут в небезопасное состояние.",
        ),
        true,
      );
    } finally {
      button.disabled = false;
      executionRequestInFlight = false;
      syncExecutionControls();
    }
  };

  const loadBalancing = async () => {
    if (!tbankIsConnected) return;
    const generation = portfolioGeneration;
    try {
      const payload = await api("/api/portfolio/balancing", {method: "GET"});
      if (generation !== portfolioGeneration || !tbankIsConnected) return;
      renderBalancing(payload);
      renderProposalCreateOptions(payload);
    } catch (error) {
      if (generation !== portfolioGeneration) return;
      if (error.status === 401) {
        location.reload();
        return;
      }
      balancingScenarios.replaceChildren();
      balancingScreening.replaceChildren();
      renderProposalCreateOptions(null);
      appendEmptyState(balancingScenarios, "Сценарий балансировки временно недоступен.");
      setStateBadge(balancingStatus, "Ошибка preview", "state-error");
    }
  };

  const loadIntelligence = async () => {
    if (!tbankIsConnected) return;
    const generation = portfolioGeneration;
    try {
      const snapshot = await api("/api/portfolio/intelligence", {method: "GET"});
      if (generation !== portfolioGeneration || !tbankIsConnected) return;
      renderIntelligence(snapshot);
    } catch (error) {
      if (generation !== portfolioGeneration) return;
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
      void loadBalancing();
      return;
    }
    void loadIntelligence();
    void loadBalancing();
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
        if (!matchesConnectedAccount(snapshot)) return;
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
      if (generation === analysisGeneration) {
        analysisInFlight = false;
        analysisRefresh.disabled = false;
      }
    }
  };

  const renderTbankSummary = (status) => {
    invalidatePortfolioRequest();
    resetAnalysis();
    const accountChanged = tbankAccountId !== String(status.account_id || "")
      || connectedTbankEnvironment !== status.environment;
    if (accountChanged) renderDisconnectedPortfolio();
    homeConnectionCard.classList.remove("is-offline", "is-error");
    topConnectionIndicator.classList.remove("is-offline", "is-error");
    tbankIsConnected = Boolean(status.connected);
    connectedTbankEnvironment = status.connected ? status.environment : null;
    tbankAccountId = status.connected ? String(status.account_id || "") : null;
    syncExecutionControls();

    if (!status.connected) {
      setHomeAttentionBucket("connection", [{
        severity: "warning",
        title: "T-Invest не подключён",
        detail: "Подключите собственный счёт, чтобы командный центр показывал подтверждённые данные.",
        view: "connections",
      }]);
      setHomeAttentionBucket("portfolio", []);
      resetHomePortfolioSummary("Подключите T-Invest для данных портфеля.");
      portfolioLoaded = false;
      lastPortfolioSnapshot = null;
      lastPortfolioLoadError = null;
      resetPortfolioVisualization("Подключите T-Invest для сохранённой истории портфеля.");
      portfolioFreeCash.textContent = "—";
      lastPortfolioRefreshAt = 0;
      overviewAccount.textContent = "T-Invest не подключён";
      overviewConnectionText.textContent = "Подключите read-only API-токен в разделе «Подключения».";
      homeConnectionCard.classList.add("is-offline");
      topConnectionIndicator.classList.add("is-offline");
      topConnectionText.textContent = "T-Invest не подключён";
      setStateBadge(homeTbankState, "Не подключено", "state-next");
      setStateBadge(homePortfolioState, "Нет подключения", "state-next");
      setStateBadge(portfolioStateBadge, "Нет подключения", "state-next");
      updateOwlState(null);
      updateGuard(null);
      hunterResults.replaceChildren();
      showMessage(hunterMessage, "Подключите T-Invest, чтобы искать инструменты.");
      showPortfolioMode("disconnected");
      return;
    }

    setHomeAttentionBucket("connection", []);
    setHomeAttentionBucket("portfolio", portfolioLoaded ? homeAttentionBuckets.portfolio : null);
    const environment = status.environment === "sandbox" ? "Песочница" : "Биржа";
    const accountName = status.account_name || "Брокерский счёт";
    overviewAccount.textContent = accountName;
    overviewConnectionText.textContent = `${environment} · соединение подтверждено`;
    topConnectionText.textContent = "T-Invest подключён";
    setStateBadge(homeTbankState, "Работает", "state-ok");
    showMessage(hunterMessage, "");
    if (!portfolioLoaded) {
      setStateBadge(homePortfolioState, "Загружаем", "");
      setStateBadge(portfolioStateBadge, "Загружаем", "");
      updateOwlState(null);
      updateGuard(null);
    } else {
      renderPortfolioDataStatus();
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
    invalidatePortfolioRequest();
    resetAnalysis();
    setHomeAttentionBucket("connection", [{
      severity: "error",
      title: "Не удалось проверить T-Invest",
      detail: "Состояние подключения не подтверждено. Обновите страницу или попробуйте позже.",
      view: "connections",
    }]);
    setHomeAttentionBucket("portfolio", []);
    resetHomePortfolioSummary("Состояние T-Invest не подтверждено.");
    resetPortfolioVisualization("Состояние T-Invest не подтверждено; история не обновлялась.");
    portfolioFreeCash.textContent = "—";
    overviewAccount.textContent = "Не удалось проверить подключение";
    overviewConnectionText.textContent = "Обновите страницу или попробуйте позже.";
    homeConnectionCard.classList.add("is-error");
    topConnectionIndicator.classList.add("is-error");
    topConnectionText.textContent = "Ошибка T-Invest";
    tbankIsConnected = false;
    connectedTbankEnvironment = null;
    tbankAccountId = null;
    syncExecutionControls();
    portfolioLoaded = false;
    lastPortfolioSnapshot = null;
    lastPortfolioLoadError = null;
    lastPortfolioRefreshAt = 0;
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
    const generation = portfolioGeneration;
    showMessage(tbankMessage, "");
    try {
      const status = await api("/api/broker/tbank", {method: "GET"});
      if (generation !== portfolioGeneration) return;
      renderTbankStatus(status);
      if (status.connected) {
        void loadPortfolioData();
      }
    } catch (error) {
      if (generation !== portfolioGeneration) return;
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

  const renderBalancingPolicy = (policy) => {
    showMessage(balancingPolicyMessage, "");
    if (!policy) {
      balancingPolicyVersion.textContent = "Не заполнена";
      balancingPolicyCreated.textContent = "Версия ещё не сохранена";
      return;
    }

    balancingPolicyVersion.textContent = `v${policy.version}`;
    balancingPolicyCreated.textContent = `Сохранено: ${formatDateTime(policy.created_at)}`;
    balanceMaxInstrument.value = String(policy.max_instrument_percent);
    balanceMaxSector.value = String(policy.max_sector_percent);
    balanceMaxIssuer.value = String(policy.max_issuer_percent);
    balanceMaxGroup.value = String(policy.max_group_percent);
    balanceMaxShare.value = String(policy.max_share_percent);
    balanceMaxBond.value = String(policy.max_bond_percent);
    balanceMaxEtf.value = String(policy.max_etf_percent);
    balanceMaxBelowGrade.value = String(policy.max_below_grade_percent);
    balanceMaxUnknown.value = String(policy.max_unknown_percent);
    balanceMaxTerm.value = String(policy.max_term_months);
    balanceTurnoverBudget.value = String(policy.turnover_budget_percent);
    balanceDailyParticipation.value = String(
      policy.max_daily_turnover_participation_percent
    );
    balanceTaxRate.value = String(policy.securities_tax_rate_percent);
    balanceUncertaintyHaircut.value = String(policy.uncertainty_haircut_percent);
    balanceCreditHaircut.value = String(policy.credit_loss_haircut_percent);
    balanceNoTradeBand.value = String(policy.no_trade_band_percent);
    balanceMinReplaceBenefit.value = String(policy.min_replace_benefit_rub);
  };

  // Starter values are editable, unconfirmed examples, never loaded personal facts.
  const STARTER_DRAFTS = Object.freeze({
    "investment-profile": ["100000", "0", "60", "20", "5", false],
    "balancing-policy": ["5", "25", "5", "10", "50", "80", "30", "0", "0", "120",
      "10", "5", "13", "10", "20", "1", "1000"],
  });
  const SETTING_HELP = Object.freeze({
    "profile-reserve-rub": ["Неприкосновенный резерв", "₽", {"summary": "Сколько свободных рублей не использовать для новых покупок в расчёте. Чем больше резерв, тем меньше денег остаётся на такие покупки. На отдельный счёт эта сумма не переводится.", "sections": [["Что означает", "Это часть свободных рублей на брокерском счёте, которую вы хотите оставить деньгами. Расчёт сначала вычитает её из доступной суммы. Резерв задаётся в рублях, а не в процентах и не в количестве бумаг."], ["Что меняется при настройке", "Увеличите резерв — расчёт сможет распределить меньше свободных денег. Уменьшите — больше, если остальные ограничения это допускают. Если резерва и планируемых снятий больше, чем свободных рублей, новые покупки на этот остаток не рассчитываются."], ["Пример на условных суммах", "Свободно 100 000 ₽. Резерв — 30 000 ₽, планируемые снятия — 10 000 ₽. Остаётся 60 000 ₽ до расходов и других ограничений. Если поднять резерв до 50 000 ₽, останется 40 000 ₽."], ["Важно знать", "Это правило для расчёта, а не банковская блокировка денег. Оно не продаёт бумаги, чтобы пополнить резерв. Резерв в процентах в верхнем черновике — отдельная настройка. Не указывайте одну и ту же сумму и здесь, и в снятиях: расчёт вычтет обе. «Не знаю» не означает ноль."]]}, ["10000", "50000", "100000"]],
    "profile-withdrawal-rub": ["Планируемые снятия", "₽", {"summary": "Деньги, которые вы планируете забрать со счёта. Расчёт не предлагает использовать эту сумму для новых покупок. Сам вывод денег не выполняется.", "sections": [["Что означает", "Укажите общую сумму предстоящих снятий, которую нужно оставить свободной сверх резерва. В этой форме нет даты вывода: весь указанный объём исключается из бюджета новых покупок, а не только сумма на ближайшую дату."], ["Что меняется при настройке", "Больше планируемых снятий — меньше денег участвует в расчёте покупок. Меньше снятий — больше денег может участвовать. Ноль означает, что вы сейчас не закладываете снятия; это не то же самое, что неизвестная сумма."], ["Пример на условных суммах", "На счёте свободно 80 000 ₽. Резерв — 20 000 ₽. При снятиях 15 000 ₽ остаётся 45 000 ₽ до расходов. При снятиях 30 000 ₽ остаётся 30 000 ₽."], ["Важно знать", "Сохранение не отправляет перевод, не назначает дату снятия и не продаёт активы для его оплаты. Если деньги уже включены в резерв, не учитывайте их второй раз. Пример не определяет, сколько лично вам нужно вывести."]]}, ["0", "10000", "50000"]],
    "profile-horizon-months": ["Срок планирования", "мес.", {"summary": "На какой срок вы планируете оставлять деньги во вложениях. Сейчас этот срок ограничивает допустимый срок облигаций в расчёте. Он не назначает дату продажи.", "sections": [["Что означает", "Это ваш срок планирования в полных месяцах: 12 — один год, 36 — три года, 60 — пять лет. Он описывает вашу задачу, а не срок работы аккаунта и не обязательство держать каждую бумагу до конца."], ["Что меняется при настройке", "Более короткий срок исключает из расчёта облигации с более поздним погашением. Более длинный может расширить выбор, но только до отдельного ограничения «Срок облигаций». Из этих двух сроков применяется меньший."], ["Пример на условных суммах", "Вы выбрали 36 месяцев, а в лимитах облигаций — 60. В расчёте предел будет 36 месяцев. Облигация со сроком 48 месяцев его не проходит. Если увеличить ваш срок до 84 месяцев, предел всё равно останется 60."], ["Важно знать", "Изменение не включает автоматическую продажу через указанное время и не обещает прибыль к этой дате. Срок до погашения не гарантирует, что деньги вернутся: важны условия бумаги и способность заёмщика платить."]]}, ["12", "36", "60", "120"]],
    "profile-max-drawdown": ["Допустимое снижение", "%", {"summary": "Какое падение стоимости портфеля вы считаете для себя нежелательным. Это записанное предпочтение, а не защита от убытков и не команда продать бумаги при достижении процента.", "sections": [["Что означает", "Процент помогает выразить вашу готовность видеть снижение капитала. Например, 10% — это потеря 10 из каждых условных 100 рублей. Здесь вы выбираете границу для своего профиля, а не прогноз будущего рынка."], ["Что меняется при настройке", "Меньшее значение обозначает меньшую готовность к потерям; большее — большую. В проверенном текущем расчёте перестройки этот процент сохраняется среди условий, но по нему не вычисляется будущая просадка и не ограничивается автоматически состав покупок."], ["Пример на условных суммах", "Для условного портфеля 100 000 ₽ падение на 10% — это 10 000 ₽, до 90 000 ₽. Падение на 20% — это 20 000 ₽, до 80 000 ₽. Это объяснение масштаба, не расчёт вашего портфеля."], ["Важно знать", "Даже при выбранных 5% реальный убыток может быть больше. Здесь не создаётся стоп-приказ, страховка или гарантированный предел потерь. Ноль тоже не делает инвестиции безрисковыми. Не выбирайте число только потому, что оно стоит в примере."]]}, ["5", "10", "20", "30"]],
    "profile-liquidity-days": ["Срок выхода из позиции", "дн.", {"summary": "Сколько дней торгов можно учитывать, оценивая допустимый размер позиции. Более длинный срок может допустить больший объём. Это не обещание продать всё за столько дней.", "sections": [["Что означает", "Расчёт смотрит на подтверждённый средний дневной объём торгов и берёт только выбранную вами часть этого объёма. Затем умножает результат на число дней здесь. Так получается ограничение размера позиции с учётом возможности её продать."], ["Что меняется при настройке", "Увеличите число дней — по этому ограничению можно рассмотреть больше бумаг. Уменьшите — меньше. Параметр работает вместе с «Долей дневного объёма торгов». Ноль не означает мгновенную продажу: он не даёт доступного объёма для новых покупок по этому расчёту."], ["Пример на условных суммах", "Средний объём — 1 000 000 ₽ в день. Вы разрешили учитывать 1%: это 10 000 ₽ в день. За 5 дней расчётный предел — 50 000 ₽, за 10 — 100 000 ₽. Затем учитываются целые торговые лоты и другие лимиты."], ["Важно знать", "Лот — количество бумаг, которое продают или покупают одним минимальным пакетом. Объём прошлых торгов не гарантирует будущих покупателей, прежнюю цену или исполнение. При нехватке данных система не должна считать весь рынок доступным вам."]]}, ["1", "5", "10", "30"]],
    "balance-max-instrument": ["Один инструмент", "%", {"summary": "Верхний предел доли одной конкретной бумаги или одного фонда. Например, 5% — не больше 5 из каждых 100 рублей портфеля. Это потолок, а не цель, которую нужно заполнить.", "sections": [["Что означает", "Один инструмент — например, акции одного вида или один выпуск облигаций. Все имеющиеся бумаги этого инструмента учитываются вместе. Два разных выпуска облигаций одной компании — разные инструменты, но у них общий эмитент."], ["Что меняется при настройке", "Меньший предел оставляет меньше места для одной бумаги. Больший позволяет более крупную долю, но сильнее связывает результат с ней. Для расчёта новой покупки из допустимой доли вычитается уже имеющаяся стоимость этого инструмента."], ["Пример на условных суммах", "Условный портфель — 100 000 ₽, предел — 5%: максимум 5 000 ₽ в одном инструменте. Если он уже занимает 4 000 ₽, остаётся 1 000 ₽ по этому лимиту. Если минимальный лот дороже, новая покупка не помещается."], ["Важно знать", "Также проверяются пределы компании, группы, отрасли и класса: применяется более строгое ограничение. Ноль не оставляет места для покупки, а 100% не отменяет остальные проверки. Снижение лимита не продаёт уже купленные бумаги и не устраняет риск потерь."]]}, ["5", "10", "15", "25"]],
    "balance-max-sector": ["Один сектор", "%", {"summary": "Сколько всего может приходиться на одну отрасль, например банки или нефтегаз. Активы одной отрасли складываются, даже если выпущены разными компаниями.", "sections": [["Что означает", "Сектор — это отрасль бизнеса. У нескольких компаний могут быть разные названия, но похожие причины роста и падения. Лимит помогает не сосредоточивать слишком большую часть расчётного портфеля в одной такой отрасли."], ["Что меняется при настройке", "Уменьшите предел — для новых покупок в уже большой отрасли останется меньше места. Увеличите — больше. Сам параметр не распределяет деньги поровну между всеми отраслями и не заставляет покупать отсутствующие сектора."], ["Пример на условных суммах", "Портфель — 100 000 ₽. При лимите 25% на банки может приходиться до 25 000 ₽. Если два банка уже занимают 12 000 ₽ и 10 000 ₽, остаётся 3 000 ₽ для всей отрасли, а не для каждого банка."], ["Важно знать", "Предел считается от стоимости всего портфеля, а не только акций. Используется доступная классификация; неизвестная отрасль не становится автоматически безопасной. При лимите 0% новые покупки по этому ограничению не помещаются. Сохранение не запускает продажу."]]}, ["10", "20", "25", "40"]],
    "balance-max-issuer": ["Один эмитент", "%", {"summary": "Общий предел для бумаг одной компании или другого заёмщика, который их выпустил. Разные выпуски его облигаций суммируются, а не получают отдельный лимит каждый.", "sections": [["Что означает", "Эмитент — тот, кто выпустил ценную бумагу: компания, государство или другой заёмщик. Несколько облигаций одной компании могут зависеть от её способности вернуть один и тот же долг, поэтому смотреть только на число выпусков недостаточно."], ["Что меняется при настройке", "Меньший предел сокращает допустимую зависимость от одного эмитента. Больший допускает более крупную общую долю. При покупке расчёт учитывает уже имеющиеся бумаги, которые относятся к этому эмитенту по проверенным данным."], ["Пример на условных суммах", "При портфеле 100 000 ₽ и лимите 10% общий потолок — 10 000 ₽. Первый выпуск компании занимает 6 000 ₽, второй — 3 000 ₽. Остаток для её бумаг — 1 000 ₽, а не ещё 10 000 ₽."], ["Важно знать", "Лимит одной бумаги и лимит эмитента действуют вместе. Поиск связи с эмитентом опирается на данные, а не на похожее название. Ноль не оставляет места для новой покупки. Изменение не продаёт активы и не гарантирует возврат денег."]]}, ["5", "10", "15", "25"]],
    "balance-max-group": ["Одна группа компаний", "%", {"summary": "Общий предел для связанных компаний. Он нужен, чтобы несколько разных названий внутри одного бизнеса не выглядели как полностью независимые вложения.", "sections": [["Что означает", "Группа — связанные компании, которые могут зависеть от общего владельца или бизнеса. У каждой может быть свой эмитент, но проблемы одной части группы способны затронуть другие. Для объединения нужны подтверждённые связи."], ["Что меняется при настройке", "Меньший предел уменьшает место для группы в расчёте новых покупок. Больший допускает большую суммарную долю. Предел не заменяет ограничения каждой компании и каждого инструмента."], ["Пример на условных суммах", "Портфель — 100 000 ₽, предел группы — 15%, то есть 15 000 ₽. Компания А занимает 8 000 ₽, связанная с ней Б — 6 000 ₽. По групповому лимиту остаётся 1 000 ₽."], ["Важно знать", "Если связь компаний неизвестна, нельзя считать, что проверка всех пересечений выполнена. Эта настройка сама не изучает владельцев компаний и не раскрывает состав фондов. Ноль запрещает новые покупки по этому лимиту; существующие вложения не продаются автоматически."]]}, ["10", "15", "25", "40"]],
    "balance-max-share": ["Все акции", "%", {"summary": "Максимальная доля всех акций вместе. Этот предел не равен желаемой доле акций в черновике распределения и не означает команду купить акции до указанного процента.", "sections": [["Что означает", "Суммируются позиции, которые данные брокера относят к акциям. Процент считается от общей стоимости портфеля. Акции внутри фонда не становятся здесь отдельными прямыми позициями: фонд учитывается как фонд."], ["Что меняется при настройке", "Меньший предел сокращает место для новых покупок акций. Больший допускает большую долю, но не делает её обязательной. При 0% новые покупки акций по этому ограничению не проходят; уже имеющиеся акции остаются на счёте."], ["Пример на условных суммах", "Портфель — 100 000 ₽, предел акций — 40%: максимум 40 000 ₽. Если акции уже стоят 35 000 ₽, по этому ограничению остаётся 5 000 ₽. Другие лимиты могут уменьшить эту сумму ещё сильнее."], ["Важно знать", "Пределы акций, облигаций и фондов не обязаны складываться в 100%: это независимые потолки. Повышение не обещает рост дохода; стоимость акций может падать. Сохранение не покупает и не продаёт бумаги."]]}, ["0", "20", "50", "100"]],
    "balance-max-bond": ["Все облигации", "%", {"summary": "Максимальная доля всех облигаций вместе. Это ограничение суммы, а не обещание надёжности, дохода или возврата денег.", "sections": [["Что означает", "Облигация — ценная бумага с обязательствами заёмщика по выплатам. Для этого лимита суммируются прямые позиции в облигациях. Их количество и число выпусков не отменяют общие риски одного заёмщика."], ["Что меняется при настройке", "Уменьшите предел — для новых облигаций останется меньше места. Увеличите — больше, если проходят остальные проверки. При 0% новые покупки облигаций не помещаются по этому лимиту."], ["Пример на условных суммах", "Портфель — 100 000 ₽, максимум облигаций — 70 000 ₽. Если они уже стоят 65 000 ₽, остаётся 5 000 ₽ по этому ограничению. Это не обещание, что найдётся подходящий выпуск или лот."], ["Важно знать", "Отдельно важны срок, рейтинг, отрасль, компания и возможность продажи. Облигации тоже могут дешеветь, а заёмщик может не выполнить выплаты. Ползунок не меняет купон уже купленной бумаги и не создаёт сделки."]]}, ["0", "50", "80", "100"]],
    "balance-max-etf": ["Все фонды", "%", {"summary": "Максимальная доля всех фондов вместе. Фонд учитывается целиком; эта настройка сама не раскрывает, какие акции или облигации находятся внутри него.", "sections": [["Что означает", "Покупая пай фонда, инвестор получает долю в общем наборе вложений. В этом разделе лимит относится к стоимости самих паёв. Он не заменяет отдельное изучение состава и правил фонда."], ["Что меняется при настройке", "Меньший предел оставляет меньше места для новых фондов; больший допускает больше. При 0% новые покупки фондов по этому ограничению не проходят. Остальные ограничения продолжают действовать."], ["Пример на условных суммах", "Портфель — 100 000 ₽, предел фондов — 30%, то есть 30 000 ₽. Два фонда занимают 12 000 ₽ и 13 000 ₽. На все новые покупки фондов остаётся 5 000 ₽ по этому лимиту."], ["Важно знать", "Два фонда могут владеть одними и теми же компаниями или быть сосредоточены в одной отрасли. Поэтому наличие фондов само по себе не означает отсутствие риска. Лимит не меняет состав фонда и не означает гарантированный доход."]]}, ["0", "10", "30", "100"]],
    "balance-max-below-grade": ["Ниже инвестиционного уровня", "%", {"summary": "Верхний предел для бумаг, отнесённых к категории с более низким кредитным рейтингом. Он работает только вместе с отдельным разрешением в профиле и остальными проверками.", "sections": [["Что означает", "Кредитный рейтинг — оценка способности заёмщика выполнять долговые обязательства. «Ниже инвестиционного уровня» — категория с более высоким кредитным риском по используемой шкале. Это не обещание высокой доходности."], ["Что меняется при настройке", "Ноль не допускает новые покупки этой категории. Большее значение только оставляет место в пределах лимита. Сначала должно быть включено отдельное разрешение в профиле. Даже вместе они не отменяют проверку состояния бумаги: текущий расчёт допускает только обычное состояние риска."], ["Пример на условных суммах", "Портфель — 100 000 ₽, предел — 5%: теоретический потолок категории 5 000 ₽. Но при выключенном разрешении в профиле фактически действует ноль. Нельзя обойти этот запрет, поставив здесь 50%."], ["Важно знать", "Рейтинг может измениться и не гарантирует выплат. Значение не даёт прав брокеру, не снимает требования к доступности и не продаёт уже имеющиеся бумаги. Более высокий лимит не делает низкорейтинговые бумаги подходящими лично вам."]]}, ["0", "5", "10"]],
    "balance-max-unknown": ["Без подтверждённого рейтинга", "%", {"summary": "Верхний предел для бумаг, у которых система не смогла подтвердить кредитный рейтинг. «Неизвестно» не означает ни хороший, ни плохой рейтинг.", "sections": [["Что означает", "Причиной может быть отсутствие рейтинга, недостаток данных или невозможность подтвердить его актуальность. Это отдельная категория, а не замена низкого рейтинга. Там, где рейтинг к виду актива не применяется, используется отдельное состояние."], ["Что меняется при настройке", "При 0% новая покупка с неизвестным рейтингом не допускается этим правилом. При большем значении появляется только допустимая доля категории. Отсутствующие важные данные или другие запреты всё равно могут исключить бумагу."], ["Пример на условных суммах", "Портфель — 100 000 ₽, лимит — 5%: до 5 000 ₽ по этому ограничению. Если такие позиции уже занимают 4 000 ₽, остаётся 1 000 ₽. Это не подтверждение, что покупка безопасна или вообще доступна."], ["Важно знать", "Настройка не придумывает рейтинг и не заставляет систему считать неизвестный риск нормальным. Если связь или данные неполны, это должно быть видно. Сохранение не меняет рейтинг бумаги, не продаёт её и не гарантирует возврат средств."]]}, ["0", "5", "10"]],
    "balance-max-term": ["Срок облигаций", "мес.", {"summary": "Самый длинный срок до погашения облигации, допустимый для расчёта. Используется меньший из этого значения и вашего срока планирования в профиле.", "sections": [["Что означает", "Погашение — предусмотренное условиями облигации возвращение основной суммы долга. Здесь учитывается оставшийся срок в месяцах, а не возраст бумаги с даты выпуска. Условия и фактические выплаты нужно проверять отдельно."], ["Что меняется при настройке", "Уменьшите предел — выпуски с более далёким погашением не пройдут расчёт. Увеличите — выбор может расшириться, но не за ваш срок планирования. Ноль не означает «без ограничений»: положительный оставшийся срок его не проходит."], ["Пример на условных суммах", "Ваш срок планирования — 60 месяцев, лимит облигаций — 36. В расчёте действует 36. Выпуск с погашением через 48 месяцев исключается. Если поставить 120, всё равно сработает более короткий срок профиля — 60."], ["Важно знать", "Поле не заставляет продать уже купленную облигацию и не гарантирует возврат денег в срок. Оно также не равно сроку, за который можно продать позицию на бирже: для этого есть отдельная настройка ликвидности."]]}, ["12", "36", "60", "120"]],
    "balance-turnover-budget": ["Бюджет перестройки", "%", {"summary": "Какую сумму покупок и продаж можно рассмотреть в одном расчёте перестройки. Процент берётся от стоимости всего портфеля. Продажа и последующая покупка считаются отдельно.", "sections": [["Что означает", "Перестройка — изменение набора вложений. Оборот здесь означает суммарную стоимость рассматриваемых покупок и продаж, а не прибыль, количество сделок или месячный расход на сервис. NAV в старой подписи — стоимость портфеля, которую использует расчёт."], ["Что меняется при настройке", "Меньший бюджет ограничивает размер изменений; больший допускает более крупную перестройку. Ноль не оставляет бюджета на новые покупки в этом расчёте. Лимит не резервирует деньги и не означает обязательство его потратить."], ["Пример на условных суммах", "Портфель — 100 000 ₽, бюджет — 10%: оборот до 10 000 ₽. Условная продажа на 5 000 ₽ и покупка на 5 000 ₽ уже дают 10 000 ₽. Комиссии и другие расходы проверяются дополнительно."], ["Важно знать", "Это лимит одного рассматриваемого варианта, не гарантированный общий лимит всех ваших сделок за день или месяц. Он не отменяет резерв и другие ограничения. Сохранение не отправляет эти сделки брокеру."]]}, ["0", "5", "10", "20"]],
    "balance-daily-participation": ["Доля дневного объёма торгов", "%", {"summary": "Какую часть обычного дневного объёма торгов система может учитывать для вашей позиции. Это доля рынка конкретной бумаги, а не процент вашего портфеля.", "sections": [["Что означает", "Если за день бумагой обычно торгуют на определённую сумму, нельзя считать, что весь этот объём доступен одному инвестору. Настройка задаёт, какую часть подтверждённого среднего объёма разрешено использовать в оценке."], ["Что меняется при настройке", "Меньший процент даёт меньшую дневную расчётную вместимость. Больший — большую. Затем эта сумма умножается на «Срок выхода из позиции». Ноль не даёт доступного объёма для покупки по такому расчёту."], ["Пример на условных суммах", "Средний оборот бумаги — 1 000 000 ₽ в день. При 1% учитывается 10 000 ₽ в день; при 5% — 50 000 ₽. Если срок выхода 5 дней, получаются 50 000 ₽ и 250 000 ₽ до округления по лотам и других ограничений."], ["Важно знать", "Объёмы прошлых торгов не обещают исполнение завтра. Параметр не размещает заявку в очереди и не позволяет продать по любой цене. При недостатке подтверждённой истории повышение процента не заменяет недостающие данные."]]}, ["1", "5", "10"]],
    "balance-tax-rate": ["Налог в сценарии", "%", {"summary": "Процент налога, который вы задаёте как предположение для сценария. Он не определяет ваш настоящий налог. В текущем расчёте новых покупок налог не вычитается из будущих выплат.", "sections": [["Что означает", "Это записываемое допущение, а не ставка, полученная из вашей налоговой истории. Реальный налог зависит от операции и применимых условий. Стоящие в примере 13% не означают, что именно столько должны платить вы."], ["Что меняется при настройке", "Изменение меняет сохранённое предположение. Нельзя обещать, что оно сейчас пересчитает все выплаты, стоимость портфеля или итог после налога: текущий расчёт новых покупок этого не делает. Там, где налог при продаже известен отдельно, используется соответствующая оценка расходов."], ["Пример на условных суммах", "Только для понимания процента: от условной облагаемой прибыли 1 000 ₽ ставка 13% даёт 130 ₽. От суммы продажи 100 000 ₽ тот же налог автоматически считать нельзя. Этот пример не является расчётом вашей обязанности."], ["Важно знать", "Параметр не меняет налог у брокера и ничего не перечисляет в бюджет. Ноль — не доказательство освобождения от налога. Если значение неизвестно, выберите «Не знаю»: форма потребует уточнения перед сохранением всех лимитов."]]}, ["0", "13", "15"]],
    "balance-uncertainty-haircut": ["Поправка на неопределённость", "%", {"summary": "Условный вычет из расчётной выгоды покупки, чтобы не полагаться на слишком оптимистичную оценку. В текущем коде процент берётся от полной расчётной стоимости покупки, а не от ожидаемой прибыли.", "sections": [["Что означает", "Поправка на неопределённость — выбранный вами запас осторожности. Английское haircut здесь означает уменьшение оценки. Это не деньги, которые спишут, не комиссия и не измеренная вероятность убытка."], ["Что меняется при настройке", "Больше процент — больше вычет и меньше расчётная выгода кандидата. Вариант может перестать проходить отбор. Меньше процент — меньше запас осторожности. Ноль убирает только эту поправку, но не устраняет неизвестность."], ["Пример на условных суммах", "Полная расчётная стоимость одного лота — 10 000 ₽. Поправка 10% даёт вычет 1 000 ₽. Если до этой поправки выгода была 1 500 ₽, останется 500 ₽; затем могут учитываться другие вычеты. Это условные числа."], ["Важно знать", "Вычет уменьшает оценку выгоды, а не отображаемый реальный остаток на счёте. Он складывается с отдельной кредитной поправкой. Даже большой процент не заменяет отсутствующие обязательные данные и не гарантирует, что расчёт окажется верным."]]}, ["0", "5", "10", "20"]],
    "balance-credit-haircut": ["Кредитный стресс", "%", {"summary": "Дополнительный условный вычет из расчётной выгоды покупки на случай проблем с выплатами у заёмщика. Это размер выбранного вычета, а не вероятность таких проблем.", "sections": [["Что означает", "Кредитный риск — возможность того, что заёмщик не выполнит обязательства. В текущем расчёте этот процент от полной стоимости покупки вычитается из её ожидаемой выгоды. Он задаётся пользователем, а не вычисляется как вероятность неплатежа."], ["Что меняется при настройке", "Увеличите процент — расчётная выгода станет меньше; больше кандидатов может не пройти отбор. Уменьшите — вычет станет меньше. Ноль не означает, что заёмщик обязательно заплатит."], ["Пример на условных суммах", "При полной расчётной стоимости лота 10 000 ₽ значение 20% даёт вычет 2 000 ₽. Если поправка на неопределённость ещё 10%, отдельно вычитается 1 000 ₽. Вместе — 3 000 ₽ из оценки выгоды, а не со счёта."], ["Важно знать", "Здесь 20% не означает «вероятность дефолта 20%» и не означает гарантированную потерю 20%. Реальный ущерб может быть другим. Настройка не делает бумагу с плохими данными допустимой и не включает автоматическую продажу."]]}, ["0", "10", "20", "50"]],
    "balance-no-trade-band": ["Порог выгоды замены, % позиции", "%", {"summary": "Процентный порог выгоды, выше которого стоит рассматривать замену позиции. Это не отклонение её доли от цели. Процент считается от стоимости заменяемой позиции, а не всего портфеля.", "sections": [["Что означает", "Старая подпись «Зона без перестройки» могла вводить в заблуждение. В текущем коде правило сравнивает пользу замены с сохранением прежней позиции: дополнительная расчётная выгода после учтённых расходов должна быть достаточно большой."], ["Что меняется при настройке", "Больше процент — более заметная выгода требуется для замены, поэтому подходящих вариантов может быть меньше. Меньше — порог ниже. Одновременно действует «Минимальная выгода замены» в рублях: расчёт берёт больший из двух порогов."], ["Пример на условных суммах", "Заменяемая позиция стоит 20 000 ₽. Порог 3% — это 600 ₽. Если рублёвый минимум 1 000 ₽, нужна выгода строго больше 1 000 ₽. Ровно 1 000 ₽ не проходит. При процентном пороге 10% потребуется больше 2 000 ₽."], ["Важно знать", "Это не настройка «продавать при отклонении доли на 3%». Она относится к проверке рассматриваемых замен, а не ко всем изменениям рынка. При нуле остаются рублёвый минимум и другие проверки. Выгода расчётная, не обещанная; сделка не создаётся."]]}, ["0", "1", "3", "5"]],
    "balance-min-replace-benefit": ["Минимальная выгода замены", "₽", {"summary": "Минимальная дополнительная выгода в рублях, ради которой расчёт рассматривает замену одной позиции на другую. Она сравнивается с вариантом оставить прежнюю позицию.", "sections": [["Что означает", "Это не минимальная сумма сделки и не ожидаемый доход всего портфеля. Расчёт сравнивает две оценки: оставить текущую позицию или заменить её, учитывая доступные расходы на продажу и покупку, а также налог при продаже, если он определён."], ["Что меняется при настройке", "Больше минимум — меньше небольших замен проходят проверку. Меньше — могут пройти варианты с меньшим преимуществом. Одновременно применяется процентный порог от стоимости позиции; используется больший из двух."], ["Пример на условных суммах", "Минимум — 1 000 ₽. Процентный порог для данной позиции — 600 ₽. Дополнительная выгода 900 ₽ не проходит, 1 000 ₽ тоже: нужно строго больше. 1 200 ₽ проходит только этот порог, но не заменяет остальные проверки."], ["Важно знать", "Если сравнение или необходимые расходы неизвестны, нельзя объявлять замену выгодной. Ноль не означает «заменять всегда». Сохранение не поручает продажу брокеру. Фактический результат может отличаться от расчётной оценки."]]}, ["100", "500", "1000", "5000"]],
  });
  const settingsUIs = new Map();
  const controlTitles = new Map();
  const uiNode = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const uiButton = (text, action, className = "filter-chip") => {
    const element = uiNode("button", text, className);
    element.type = "button";
    element.addEventListener("click", action);
    return element;
  };
  // Preserve database decimals (including exponent notation) without Number arithmetic.
  const plainDecimal = (value) => {
    const match = /^(\d+)(?:\.(\d*))?(?:e([+-]?\d{1,2}))?$/i.exec(String(value).trim().replace(",", "."));
    if (!match) return null;
    const exponent = Number(match[3] || 0);
    if (Math.abs(exponent) > 24) return null;
    const digits = match[1] + (match[2] || "");
    const point = match[1].length + exponent;
    let expanded = digits.slice(0, point) + "." + digits.slice(point);
    if (point <= 0) expanded = "0." + "0".repeat(-point) + digits;
    if (point >= digits.length) expanded = digits + "0".repeat(point - digits.length);
    return expanded.replace(/^0+(?=\d)/, "");
  };
  const scaledInteger = (value, scale) => {
    const normalized = plainDecimal(value);
    if (normalized === null) return null;
    const [whole, fraction = ""] = normalized.split(".");
    if (fraction.length > scale) return null;
    return BigInt(whole) * (10n ** BigInt(scale)) + BigInt(fraction.padEnd(scale, "0") || "0");
  };
  const trimFractionZeros = (value) => {
    let end = value.length;
    while (end > 0 && value[end - 1] === "0") end -= 1;
    return value.slice(0, end);
  };
  const decimalString = (value, scale) => {
    const factor = 10n ** BigInt(scale);
    const fraction = trimFractionZeros(String(value % factor).padStart(scale, "0"));
    return fraction ? `${value / factor}.${fraction}` : String(value / factor);
  };
  const exactLabel = (value, unit = "") => {
    const normalized = plainDecimal(value);
    if (normalized === null) return "Не задано";
    const [whole, fraction] = normalized.split(".");
    return BigInt(whole).toLocaleString("ru-RU")
      + (fraction ? "," + fraction : "") + (unit ? " " + unit : "");
  };
  const adjustExactInput = (input, direction, increment) => {
    if (input.disabled) return;
    const parts = [input.value || input.min, increment, input.min, input.max].map(plainDecimal);
    if (parts.includes(null)) return;
    const scale = Math.max(...parts.map((part) => (part.split(".")[1] || "").length));
    const [current, step, minimum, maximum] = parts.map((part) => scaledInteger(part, scale));
    const next = current + step * BigInt(direction);
    let bounded = next;
    if (bounded < minimum) bounded = minimum;
    if (bounded > maximum) bounded = maximum;
    input.value = decimalString(bounded, scale);
    input.dispatchEvent(new Event("input", {bubbles: true}));
  };

  const enhanceSettingsForm = (form) => {
    if (settingsUIs.has(form)) return settingsUIs.get(form);
    const controls = [];
    form.querySelectorAll('.field > input[type="number"]').forEach((input) => {
      const spec = SETTING_HELP[input.id];
      if (!spec) return;
      const [title, unit, helpText, choices] = spec;
      const field = input.closest(".field");
      const label = field.querySelector("label");
      const decimal = input.step !== "1";
      const originalStep = input.step;
      if (decimal) input.step = "any"; // Saved precision must not fail a coarse UI step.
      controlTitles.set(input, {title, unit});
      field.classList.add("touch-setting");
      label.textContent = title;
      const heading = uiNode("div", undefined, "setting-label");
      label.before(heading);
      heading.append(label);
      workspace.attachHelp(heading, `Справка: ${title}`, () => ({...helpText,
        current: input.value === "" ? "Не знаю — значение нужно уточнить. Это не ноль."
          : `${exactLabel(input.value, unit)} в открытой форме. Числа в примере ниже условные и не являются данными вашего счёта.`,
      }));
      const hint = field.querySelector(".field-hint") || uiNode("p", undefined, "field-hint");
      hint.id ||= input.id + "-hint";
      hint.textContent = helpText.summary;
      hint.classList.add("setting-hint");
      input.setAttribute("aria-describedby", hint.id);
      input.hidden = true;
      const output = uiNode("output", undefined, "setting-value");
      output.setAttribute("for", input.id);
      output.tabIndex = -1;
      const steps = {
        "₽": ["0.00000001", "0.0001", "0.01", "1", "1000", "10000", "100000", "1000000", "100000000", "1000000000000"],
        "%": ["0.0001", "0.1", "1", "5", "10"],
      }[unit] || ["1", "5", "12", "30", "100"];
      const increment = uiNode("select");
      increment.setAttribute("aria-label", `Шаг изменения: ${title}`);
      steps.forEach((value) => {
        const option = uiNode("option", exactLabel(value, unit));
        option.value = value;
        option.defaultSelected = value === (unit === "₽" ? "1000" : "1");
        increment.append(option);
      });
      increment.value = unit === "₽" ? "1000" : "1";
      const stepLabel = uiNode("label", undefined, "setting-step-label");
      stepLabel.append(uiNode("span", "Шаг ±"), increment);
      const decrease = uiButton("−", () => adjustExactInput(input, -1, increment.value), "step-button");
      const increase = uiButton("+", () => adjustExactInput(input, 1, increment.value), "step-button");
      decrease.dataset.stepDirection = "-1";
      increase.dataset.stepDirection = "1";
      const control = uiNode("div", undefined, "precise-control");
      control.append(decrease, stepLabel, increase);
      input.before(output, control);
      const exact = uiButton("Точный ввод", () => {
        input.hidden = !input.hidden;
        exact.setAttribute("aria-expanded", String(!input.hidden));
        if (!input.hidden) input.focus();
      }, "setting-text-button");
      exact.setAttribute("aria-expanded", "false");
      exact.setAttribute("aria-controls", input.id);
      exact.setAttribute("aria-label", `Точный ввод: ${title}`);
      const unknown = uiButton("Не знаю", () => {
        input.value = "";
        input.dispatchEvent(new Event("input", {bubbles: true}));
      }, "setting-text-button");
      unknown.setAttribute("aria-label", `Не знаю: ${title}`);
      const tools = uiNode("div", undefined, "setting-tools");
      tools.append(exact, unknown);
      const controlsHelp = uiNode("span", "Как менять", "setting-control-help");
      tools.append(controlsHelp);
      workspace.attachHelp(controlsHelp, `Как настроить: ${title}`, () => ({
        summary: "Кнопки −/+ меняют число на выбранный шаг. Быстрое значение заменяет число целиком. Рабочий черновик сохраняется автоматически после загрузки; подтверждённые условия и сделки сами не меняются.",
        current: `Шаг сейчас: ${exactLabel(increment.value, unit)}. Допустимое значение: от ${exactLabel(input.min, unit)} до ${exactLabel(input.max, unit)}.`,
        sections: [
          ["Кнопки − и +", `Одно нажатие вычитает или прибавляет ${exactLabel(increment.value, unit)}. Например, при шаге 1 переход с 20 на 21 — одно нажатие. На границе диапазона число останавливается. Это меняет настройку «${title}», а не деньги на счёте.`],
          ["Выбор шага", "Шаг определяет только величину следующего нажатия −/+. Сам выбор шага не меняет число. Маленький шаг удобен для точной поправки, большой — чтобы не нажимать много раз."],
          ["Ползунок и быстрые значения", "Если есть ползунок, он задаёт число в пределах диапазона. Кнопка с готовым числом подставляет именно это число, а не прибавляет его. Готовые значения — примеры для ввода, не рекомендации."],
          ["Точный ввод", "Открывает обычное поле с клавиатурой как дополнительный способ. Можно не пользоваться им: кнопки и выбор шага остаются доступны. В процентах переход с 10% на 11% — прибавление одного процентного пункта, не одного процента от 10."],
          ["Не знаю", "Убирает число только из открытой формы. Сохранённая версия не удаляется. Пока обязательное значение неизвестно, форма не позволит подтвердить всю группу настроек. Выберите число позже, когда сможете его обосновать."],
          ["Когда будет запись", "Черновик меняется сразу и сохраняется автоматически. Статус над вкладками показывает результат записи. Проверка и отдельное подтверждение нужны для применения профиля или лимитов; отмена не применяет их. В автономном примере копия относится только к этому браузеру."],
        ],
      }));
      const chips = uiNode("div", undefined, "setting-choices");
      chips.setAttribute("role", "group");
      chips.setAttribute("aria-label", `Примеры значений: ${title}`);
      const quick = choices.map((value) => {
        const chip = uiButton(exactLabel(value, unit), () => {
          input.value = value;
          input.dispatchEvent(new Event("input", {bubbles: true}));
        });
        chip.dataset.quickValue = value;
        chips.append(chip);
        return chip;
      });
      let range = null;
      if (Number(input.max) <= 1200) {
        range = uiNode("input", undefined, "setting-range");
        range.type = "range";
        range.min = input.min;
        range.max = input.max;
        range.setAttribute("aria-label", title);
        range.setAttribute("aria-describedby", hint.id);
        range.addEventListener("input", (event) => {
          event.stopPropagation();
          input.value = range.value;
          input.dispatchEvent(new Event("input", {bubbles: true}));
        });
        field.append(range);
      }
      field.append(chips, tools, hint);
      // One description covers the slider, quick choices, step size and exact/unknown buttons.
      for (const element of [output, decrease, increase, increment, exact, unknown, ...quick]) {
        element.setAttribute("aria-describedby", hint.id);
      }
      const sync = () => {
        output.textContent = input.value === "" ? "Не знаю · уточнить" : exactLabel(input.value, unit);
        output.classList.toggle("is-unknown", input.value === "");
        field.classList.toggle("is-disabled", input.disabled);
        [increment, exact, unknown, ...quick].forEach((element) => { element.disabled = input.disabled; });
        decrease.disabled = input.disabled || (input.value !== "" && Number(input.value) <= Number(input.min));
        increase.disabled = input.disabled || (input.value !== "" && Number(input.value) >= Number(input.max));
        decrease.setAttribute("aria-label", `Уменьшить ${title} на ${exactLabel(increment.value, unit)}`);
        increase.setAttribute("aria-label", `Увеличить ${title} на ${exactLabel(increment.value, unit)}`);
        quick.forEach((chip) => chip.setAttribute("aria-pressed", String(input.value !== "" && Number(input.value) === Number(chip.dataset.quickValue))));
        unknown.setAttribute("aria-pressed", String(input.value === ""));
        if (range) {
          const fraction = Math.max((originalStep.split(".")[1] || "").length, (plainDecimal(input.value)?.split(".")[1] || "").length);
          range.step = fraction ? "0." + "0".repeat(fraction - 1) + "1" : "1";
          range.value = input.value || input.min;
          range.disabled = input.disabled;
          range.setAttribute("aria-valuetext", output.textContent);
          range.style.setProperty("--range-progress", `${100 * (Number(range.value) - Number(range.min)) / (Number(range.max) - Number(range.min))}%`);
        }
      };
      input.addEventListener("input", sync);
      increment.addEventListener("change", sync);
      controls.push({input, sync, output, field, exact});
      sync();
    });
    const checkbox = form.querySelector('input[type="checkbox"]');
    if (checkbox) {
      const label = checkbox.closest("label");
      label.classList.add("toggle-row");
      checkbox.setAttribute("role", "switch");
      const span = label.querySelector("span");
      const text = "Разрешить рассмотрение бумаг ниже инвестиционного уровня";
      span.textContent = text;
      controlTitles.set(checkbox, {title: text, unit: ""});
      const helpHolder = uiNode("div", undefined, "setting-toggle-help");
      label.after(helpHolder);
      helpHolder.append(uiNode("span", "Повышенный кредитный риск · по умолчанию выключено"));
      workspace.attachHelp(helpHolder, "Справка: бумаги ниже инвестиционного уровня", () => ({"summary": "Отдельное разрешение рассматривать бумаги с более низкой оценкой способности заёмщика платить. По умолчанию выключено. Одного включения недостаточно, чтобы бумага прошла расчёт.", "sections": [["Что означает", "Ниже инвестиционного уровня — категория более высокого кредитного риска по используемой шкале рейтинга. Переключатель записывает ваше разрешение учитывать такую категорию, а не ваше согласие купить конкретную бумагу."], ["Что меняется при настройке", "Выключено — для этой категории применяется нулевой лимит, даже если в лимитах распределения введён больший процент. Включено — используется выбранный лимит категории, но остаются все проверки данных, доступности и риска."], ["Пример на условных суммах", "В лимитах выбрано 5%, но переключатель выключен: новые покупки этой категории не допускаются. После включения 5% становится только верхним пределом. Текущий расчёт всё равно не допускает кандидата с неподходящим состоянием риска."], ["Важно знать", "Кредитный рейтинг не гарантирует выплаты и может меняться. Эта кнопка не включает торговлю, не снимает ограничения брокера и не продаёт старые позиции. Разрешение — не обещание, что появятся доступные варианты."]], current: checkbox.checked ? "Включено в открытой форме. Сохранение требует отдельного подтверждения." : "Выключено в открытой форме. Разрешение не выдано."}));
    }
    const actionsHelp = uiNode("div", "Загрузка, проверка и сохранение", "setting-toggle-help");
    form.append(actionsHelp);
    workspace.attachHelp(actionsHelp, "Справка: работа с версиями настроек", {
      summary: "Рабочий черновик сохраняется автоматически. Загрузка в этой форме читает подтверждённый профиль или лимиты. Проверка показывает изменения, а отдельное подтверждение применяет их к расчётам. Это разные состояния.",
      sections: [
        ["Загрузить сохранённую версию", "Читает настройки этого аккаунта и заполняет форму. Если вы уже меняли числа, сначала появится вопрос о замене несохранённого черновика. При отказе ваши изменения останутся; при подтверждении успешная загрузка заменит их. Это не отмена сделок."],
        ["Проверить и сохранить", "Открывает окно с точными значениями. Изменённые числа показаны рядом с предыдущими. Нажатие ещё ничего не записывает. Неизвестное обязательное значение нужно сначала уточнить."],
        ["Подтверждение в окне", "Галочка означает, что вы проверили показанные настройки. Затем кнопка «Сохранить новую версию» отправляет именно их. Нажатие на справку или отмену не означает согласия и не отправляет запись."],
        ["Пример", "Вы поменяли резерв с 30 000 ₽ на 40 000 ₽. До подтверждения в расчётах остаётся 30 000 ₽. Отмена окна оставляет 40 000 ₽ в рабочем черновике, который сохраняется отдельно. Загрузка после вашего разрешения вернёт последнюю сохранённую сумму."],
        ["Ошибки и границы", "Дождитесь сообщения об успешном сохранении. При ошибке значения остаются на экране, но запись не подтверждена. Если версия изменилась в другой вкладке, сначала сравните данные заново. В автономном примере реальный аккаунт не меняется. Возможность восстановления демонстрационной копии зависит от хранилища браузера."],
      ],
    });
    const interfaceState = {
      sync: () => controls.forEach((item) => item.sync()),
      reveal: (input) => {
        const item = controls.find((entry) => entry.input === input);
        if (!item) return;
        const group = item.field.closest("details");
        if (group) group.open = true;
        item.field.scrollIntoView({block: "center", behavior: "instant"});
        item.output.focus({preventScroll: true});
      },
      reset: () => controls.forEach(({input, exact}) => {
        input.hidden = true;
        exact.setAttribute("aria-expanded", "false");
      }),
    };
    settingsUIs.set(form, interfaceState);
    return interfaceState;
  };

  const groupSettingsForm = (form, groups) => {
    const grid = form.querySelector(".constraint-form-grid");
    const fields = [...grid.children];
    if (fields.some((field) => field.tagName === "DETAILS")) return;
    grid.replaceChildren();
    groups.forEach(({title, note, indexes, open}) => {
      const panel = uiNode("details", undefined, "settings-disclosure");
      panel.open = open;
      const summary = uiNode("summary");
      const heading = uiNode("span", undefined, "settings-group-heading");
      const count = uiNode("span", undefined, "settings-group-count");
      heading.append(uiNode("strong", title), uiNode("small", note));
      summary.append(heading, count);
      const body = uiNode("div", undefined, "constraint-form-grid settings-group-grid");
      indexes.forEach((index) => body.append(fields[index]));
      panel.append(summary, body);
      grid.append(panel);
      const update = () => {
        const inputs = [...body.querySelectorAll('.touch-setting input[type="number"]')];
        count.textContent = `${inputs.filter((input) => input.value !== "").length}/${inputs.length}`;
        summary.setAttribute("aria-label", `${title}. ${count.textContent} значений задано. ${note}`);
      };
      form.addEventListener("input", update);
      form.addEventListener("settings:sync", update);
      update();
    });
  };

  // Drafts live only in this page. Never put personal settings in shared browser storage.
  const createSettingsEditor = ({form, save, message, prefix, path, key, render, payload}) => {
    const status = requiredElement(`#${prefix}-draft-status`);
    const reload = requiredElement(`#${prefix}-reload`);
    const inputs = Array.from(form.querySelectorAll("input"));
    let version = null;
    let baseline = "";
    let busy = false;
    let saving = false;
    let conflicted = false;
    let generation = 0;
    const values = () => JSON.stringify(inputs.map((input) => (
      input.type === "checkbox" ? input.checked : input.value
    )));
    const dirty = () => version !== null && values() !== baseline;
    let reviewed = null;
    let reviewAction = null;
    const invalidateReview = () => {
      reviewed = null;
      if (reviewAction?.isConnected) workspace.closeDialog();
      reviewAction = null;
    };
    const sync = () => {
      inputs.forEach((input) => { input.disabled = busy || version === null; });
      settingsUIs.get(form)?.sync();
      form.dispatchEvent(new Event("settings:sync"));
      save.disabled = busy || version === null || conflicted;
      save.textContent = saving ? "Сохраняем…" : "Проверить и сохранить";
      reload.disabled = busy;
      form.setAttribute("aria-busy", String(busy));
    };
    const accept = (record) => {
      if (record !== null && (!record || !Number.isSafeInteger(record.version)
          || record.version < 1)) {
        throw new Error("Invalid saved settings version");
      }
      invalidateReview();
      form.reset();
      render(record);
      if (record === null) {
        inputs.forEach((input, index) => {
          const starter = STARTER_DRAFTS[prefix][index];
          if (input.type === "checkbox") input.checked = starter === true;
          else input.value = String(starter);
        });
      }
      version = record?.version ?? 0;
      if (record === null) requiredElement(`#${prefix}-version`).textContent = "Черновик";
      baseline = values();
      settingsUIs.get(form)?.reset();
      conflicted = false;
      status.textContent = record ? "Все изменения сохранены" :
        "Стартовый черновик: проверьте каждое допущение. Он не сохранён и не является персональной рекомендацией.";
      strategyLibrary?.acceptExternal();
    };
    const load = async ({confirmDiscard = false} = {}) => {
      if (busy) return;
      if (dirty() && (!confirmDiscard || !window.confirm(
        "Заменить ваши несохранённые значения последней сохранённой версией?"
      ))) return;
      invalidateReview();
      const requestGeneration = ++generation;
      busy = true;
      sync();
      showMessage(message, "");
      status.textContent = "Загружаем сохранённые параметры…";
      try {
        const result = await api(path, {method: "GET"});
        if (requestGeneration !== generation) return;
        if (!result || !(key in result)) throw new Error("Missing saved settings");
        if (result.public_id !== currentProfileId) {
          conflicted = true;
          throw new Error("settings_owner_conflict");
        }
        accept(result[key]);
      } catch (error) {
        if (requestGeneration !== generation) return;
        status.textContent = "Не удалось проверить сохранённую версию";
        showMessage(message, error.message === "settings_owner_conflict"
          ? "Аккаунт изменился в другой вкладке. Обновите страницу перед редактированием."
          : "Проверьте соединение и нажмите «Загрузить сохранённую версию»."
            + errorReference(error), true);
      } finally {
        if (requestGeneration === generation) { busy = false; saving = false; sync(); }
      }
    };
    const showSaveFailure = (error) => {
      status.textContent = "Изменения на экране не подтверждены";
      if (error.status === 409 && error.message === "settings_version_conflict") {
        conflicted = true;
        showMessage(message, "Параметры уже изменены в другой вкладке или на другом устройстве. "
          + "Ваш черновик остался на экране. Загрузите сохранённую версию перед новой правкой.", true);
      } else if (error.status === 409 && error.message === "settings_owner_conflict") {
        conflicted = true;
        showMessage(message, "Аккаунт изменился в другой вкладке. "
          + "Скопируйте нужные значения и обновите страницу перед редактированием.", true);
      } else if (error.status === 409) {
        showMessage(message, "Для сохранения нужно принять актуальные документы. "
          + "Черновик останется здесь, пока вы не закроете страницу.", true);
      } else if (error.status === 401) {
        showMessage(message, "Сессия завершена. Скопируйте нужные значения перед повторным входом.", true);
      } else if (error.status === 422) {
        showMessage(message, "Проверьте допустимые значения. Сервер отклонил изменения.", true);
      } else {
        showMessage(message, "Сохранение не подтверждено. Ваши значения остались на экране. "
          + "Повторите сохранение или загрузите сохранённую версию." + errorReference(error), true);
      }
    };
    const commitReviewed = async (candidate, serializedValues) => {
      if (busy || !reviewed || reviewed !== JSON.stringify(candidate)
          || values() !== serializedValues || version !== candidate.expected_version
          || currentProfileId !== candidate.expected_public_id || conflicted) {
        invalidateReview();
        return;
      }
      // Capture exactly what was reviewed before closing the shared dialog.
      const body = reviewed;
      invalidateReview();
      const requestGeneration = ++generation;
      busy = true;
      saving = true;
      sync();
      status.textContent = "Сохраняем… Дождитесь подтверждения";
      showMessage(message, "");
      try {
        const result = await api(path, {method: "PUT", body});
        if (requestGeneration !== generation) return;
        if (!result?.[key]) throw new Error("Missing save confirmation");
        if (result.public_id !== currentProfileId) {
          conflicted = true;
          const error = new Error("settings_owner_conflict");
          error.status = 409;
          throw error;
        }
        accept(result[key]);
        showMessage(message, "Сохранение подтверждено. Параметры применены к вашему профилю.");
      } catch (error) {
        if (requestGeneration !== generation) return;
        showSaveFailure(error);
      } finally {
        if (requestGeneration === generation) { busy = false; saving = false; sync(); }
      }
    };
    const saveDraft = (event) => {
      event.preventDefault();
      if (busy || version === null || conflicted) return;
      const invalid = inputs.find((input) => !input.validity.valid);
      if (invalid) {
        settingsUIs.get(form)?.reveal(invalid);
        showMessage(message, `Уточните «${controlTitles.get(invalid)?.title || invalid.id}». `
          + "Выберите значение кнопками или ползунком. Неизвестное значение не равно нулю.", true);
        return;
      }
      const candidate = Object.freeze({...payload(), expected_version: version, expected_public_id: currentProfileId});
      const serializedValues = values();
      reviewed = JSON.stringify(candidate);
      const body = workspace.openDialog(prefix === "investment-profile" ? "Проверить профиль капитала" : "Проверить лимиты распределения");
      body.append(uiNode("p", version === 0
        ? "Стартовый пример ещё не был сохранён. Проверьте, что каждое значение подходит вашей задаче. Это не определённые системой личные данные."
        : `Сохранённая версия v${version} останется в истории. Проверьте изменения перед созданием новой версии.`, "inline-note"));
      const list = uiNode("dl", undefined, "settings-review");
      const before = JSON.parse(baseline);
      inputs.forEach((input, index) => {
        const {title, unit} = controlTitles.get(input) || {title: input.id, unit: ""};
        const display = (value) => {
          if (input.type !== "checkbox") return exactLabel(value, unit);
          return value ? "Разрешено" : "Выключено";
        };
        const current = input.type === "checkbox" ? input.checked : input.value;
        const row = uiNode("div", undefined, "settings-review-row");
        const term = uiNode("dt", title);
        row.append(term);
        const fieldHelp = SETTING_HELP[input.id]?.[2];
        if (fieldHelp) workspace.attachHelp(term, `Справка: ${title}`, {
          ...fieldHelp,
          current: `${display(current)} показано для подтверждения. Пример ниже использует условные суммы, не данные вашего счёта.`,
        });
        const value = uiNode("dd");
        if (version > 0 && current !== before[index]) {
          value.append(uiNode("span", display(before[index]), "settings-review-before"), uiNode("span", " → "));
          row.classList.add("is-changed");
        }
        value.append(uiNode("strong", display(current)));
        row.append(value);
        list.append(row);
      });
      body.append(list, uiNode("p", "Сохранение настроек не создаёт сделок. Налог и стресс-поправки — выбранные допущения, не прогнозы. Целевые доли из черновика распределения этим действием не сохраняются.", "field-hint"));
      const consent = uiNode("label", undefined, "check review-consent");
      const acknowledgement = uiNode("input");
      acknowledgement.type = "checkbox";
      acknowledgement.id = "settings-review-confirmation";
      consent.append(acknowledgement, uiNode("span", "Я проверил(а) значения и подтверждаю именно эти настройки"));
      body.append(consent);
      const actions = uiNode("div", undefined, "settings-review-actions");
      const cancel = uiButton("Вернуться к настройке", () => {
        invalidateReview();
        status.textContent = "Сохранение отменено. Черновик остался на экране.";
      }, "button button-secondary");
      const apply = uiButton("Сохранить новую версию", () => {
        if (acknowledgement.checked) void commitReviewed(candidate, serializedValues);
      }, "button button-primary");
      reviewAction = apply;
      apply.id = "settings-review-save";
      apply.disabled = true;
      acknowledgement.addEventListener("change", () => { apply.disabled = !acknowledgement.checked || reviewed === null; });
      actions.append(cancel, apply);
      body.append(actions);
      const helpHolder = uiNode("div", "Что произойдёт после подтверждения?", "setting-toggle-help");
      body.prepend(helpHolder);
      workspace.attachHelp(helpHolder, "Справка: подтверждение настроек", {"summary": "Вы проверяете точные значения перед записью новой версии настроек. Открытие окна ничего не сохраняет. Подтверждение сохраняет настройки, но не покупает и не продаёт активы.", "sections": [["Что означает", "В таблице показано, что будет записано. Для изменённых сохранённых значений видны старое и новое. При первом сохранении числа являются выбранными примерами, а не фактами, определёнными системой."], ["Что меняется при настройке", "Подтвердите только после проверки всех строк. Изменения относятся к текущей группе: профилю капитала или лимитам. Черновик распределения долей этим действием не записывается в серверные настройки."], ["Пример на условных суммах", "Вы меняете резерв с 30 000 ₽ на 40 000 ₽. После успешного сохранения расчёт будет оставлять на 10 000 ₽ больше вне покупок при прочих равных. Но уже купленные бумаги от этого не продаются."], ["Важно знать", "«Отменить» закрывает проверку без записи. Ошибка связи не означает успешное сохранение. При конфликте версий нужно заново сверить настройки, а не затирать более новую запись. В автономном примере сохранение существует только в памяти страницы."]]});
      requiredElement("#workspace-dialog").addEventListener("close", () => {
        if (reviewAction === apply) { reviewed = null; reviewAction = null; }
      }, {once: true});
    };
    const reset = () => {
      invalidateReview();
      generation += 1;
      busy = false;
      saving = false;
      version = null;
      conflicted = false;
      form.reset();
      settingsUIs.get(form)?.reset();
      render(null);
      requiredElement(`#${prefix}-version`).textContent = "Проверяем";
      requiredElement(`#${prefix}-created`).textContent = "Сохранённая версия ещё не получена";
      baseline = "";
      status.textContent = "Проверяем сохранённые параметры…";
      sync();
    };
    form.addEventListener("input", (event) => {
      if (!inputs.includes(event.target)) return;
      invalidateReview();
      if (busy || conflicted) return;
      if (dirty()) {
        status.textContent = "Рабочие изменения отличаются от подтверждённых параметров. Статус автосохранения — над вкладками стратегии.";
        return;
      }
      status.textContent = version === 0 ? "Стартовый пример · ещё не сохранён. Проверьте допущения." : "Значения соответствуют сохранённой версии";
    });
    form.addEventListener("submit", saveDraft);
    reload.addEventListener("click", () => { void load({confirmDiscard: true}); });
    reset();
    const fieldNames = Object.keys(payload());
    const readDraft = () => Object.fromEntries(inputs.map((input, index) => {
      const value = input.type === "checkbox" ? input.checked : input.value;
      return [fieldNames[index], value === "" ? null : value];
    }));
    const writeDraft = (draft) => {
      if (version === null || busy) return;
      invalidateReview();
      inputs.forEach((input, index) => {
        if (input.type === "checkbox") input.checked = draft[fieldNames[index]] === true;
        else input.value = draft[fieldNames[index]] ?? "";
      });
      settingsUIs.get(form)?.sync();
      form.dispatchEvent(new Event("settings:sync"));
      status.textContent = "Рабочий черновик. Подтверждённые параметры изменятся только после проверки и применения.";
    };
    return {load, reset, readDraft, writeDraft, isReady: () => version !== null && !busy,
      savedVersion: () => version, isDirty: dirty, hasPending: () => saving || (dirty() && !strategyLibrary?.isCurrentSaved())};
  };

  const investmentEditor = createSettingsEditor({
    form: investmentProfileForm, save: investmentProfileSave, message: investmentProfileMessage,
    prefix: "investment-profile", path: "/api/profile/investment", key: "profile",
    render: renderInvestmentProfile,
    payload: () => ({
      reserve_rub: profileReserveRub.value,
      planned_withdrawal_rub: profileWithdrawalRub.value,
      horizon_months: Number(profileHorizonMonths.value),
      max_drawdown_percent: profileMaxDrawdown.value,
      liquidity_horizon_days: Number(profileLiquidityDays.value),
      allow_below_investment_grade: profileAllowBelowGrade.checked,
    }),
  });
  const balancingEditor = createSettingsEditor({
    form: balancingPolicyForm, save: balancingPolicySave, message: balancingPolicyMessage,
    prefix: "balancing-policy", path: "/api/profile/balancing", key: "policy",
    render: renderBalancingPolicy,
    payload: () => ({
      max_instrument_percent: balanceMaxInstrument.value,
      max_sector_percent: balanceMaxSector.value,
      max_issuer_percent: balanceMaxIssuer.value,
      max_group_percent: balanceMaxGroup.value,
      max_share_percent: balanceMaxShare.value,
      max_bond_percent: balanceMaxBond.value,
      max_etf_percent: balanceMaxEtf.value,
      max_below_grade_percent: balanceMaxBelowGrade.value,
      max_unknown_percent: balanceMaxUnknown.value,
      max_term_months: Number(balanceMaxTerm.value),
      turnover_budget_percent: balanceTurnoverBudget.value,
      max_daily_turnover_participation_percent: balanceDailyParticipation.value,
      securities_tax_rate_percent: balanceTaxRate.value,
      uncertainty_haircut_percent: balanceUncertaintyHaircut.value,
      credit_loss_haircut_percent: balanceCreditHaircut.value,
      no_trade_band_percent: balanceNoTradeBand.value,
      min_replace_benefit_rub: balanceMinReplaceBenefit.value,
    }),
  });
  // A durable working copy is separate from the reviewed profile/policy authority.
  const createStrategyLibrary = () => {
    const host = requiredElement('[data-view-panel="strategy"]');
    const sectionNames = ["Подход", "Доли", "Капитал", "Лимиты", "Проверка"];
    const clone = (value) => structuredClone(value);
    const pendingRequests = new Set();
    const request = async (path, options) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      pendingRequests.add(controller);
      try { return await api(path, {...options, signal: controller.signal}); }
      finally { clearTimeout(timeout); pendingRequests.delete(controller); }
    };
    const canonical = (value) => {
      if (Array.isArray(value)) return value.map(canonical);
      if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort((a, b) => a.localeCompare(b)).map((key) => [key, canonical(value[key])]));
      if (typeof value === "string" && /^\d+(?:\.\d*)?$/.test(value)) {
        const [whole, fraction = ""] = value.split(".");
        const trimmed = trimFractionZeros(fraction);
        return whole.replace(/^0+(?=\d)/, "") + (trimmed ? "." + trimmed : "");
      }
      return value;
    };
    const equal = (left, right) => JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
    let catalog = null;
    let documentState = null;
    let customCopy = null;
    let unacknowledged = null;
    let loading = false;
    let loadNotice;
    let loadMessage;
    let loadRetry;
    const initialControls = [...host.querySelectorAll(":scope > .strategy-layout, :scope > .strategy-live-settings, :scope > .strategy-jump")];
    const showInitialLoad = (failed = false) => {
      if (built) return;
      if (!loadNotice) {
        loadNotice = uiNode("div", undefined, "inline-note strategy-load-status");
        loadMessage = uiNode("p"); loadMessage.setAttribute("role", "status");
        loadRetry = uiNode("button", "Повторить загрузку", "button button-secondary");
        loadRetry.type = "button";
        loadRetry.addEventListener("click", () => {
          void Promise.all([investmentEditor.load(), balancingEditor.load()]).then(() => load());
        });
        loadNotice.append(loadMessage, loadRetry);
        host.querySelector(".page-heading").after(loadNotice);
      }
      loadNotice.hidden = false;
      loadRetry.hidden = !failed;
      loadRetry.disabled = loading;
      loadMessage.textContent = failed
        ? "Не удалось загрузить вашу стратегию. Настройки ниже недоступны: их сохранение не подтверждено. Сохранённые значения не заменены."
        : "Загружаем вашу стратегию. Пока загрузка не завершена, изменения и автосохранение недоступны.";
      initialControls.forEach((element) => { element.inert = true; });
    };
    let version = null;
    let generation = 0;
    let revision = 0;
    let dirty = false;
    let busy = false;
    let blocked = false;
    let intent = "edit";
    let timer = null;
    let maximumWait = null;
    let saveStatus;
    let currentTitle;
    let cards;
    let restore;
    let retry;
    let reload;
    let category = "Все";
    let panels = [];
    const ratingInputs = new Map();
    let yieldFloor;
    let yieldMargin;
    let wrapperCap;
    let diagnosticResult;
    let diagnosticRevision = 0;
    const clearDiagnostic = () => {
      diagnosticRevision += 1;
      diagnosticResult?.replaceChildren();
    };
    let built = false;
    const notify = (message) => { if (saveStatus) saveStatus.textContent = message; };
    const setButtonState = () => {
      if (!built) return;
      host.querySelectorAll("[data-choose-strategy]").forEach((button) => { button.disabled = dirty || busy || blocked || version === null; });
      restore.disabled = !customCopy || dirty || busy || blocked;
      retry.hidden = !blocked;
      reload.disabled = busy;
      panels.forEach((panel) => { panel.inert = version === null; });
      host.dataset.strategyCustomized = String(Boolean(documentState?.customized));
      if (!documentState) currentTitle.textContent = "Стратегия: проверяем аккаунт";
      if (documentState) {
        const preset = catalog.presets.find((item) => item.id === documentState.base_preset_id);
        currentTitle.textContent = documentState.customized ? `Пользовательская · на основе «${preset.title}»` : preset.title;
      }
    };
    const clearTimers = () => { clearTimeout(timer); clearTimeout(maximumWait); timer = null; maximumWait = null; };
    const snapshot = () => ({
      ...documentState,
      allocation: workspace.readAllocation().allocation,
      locked: workspace.readAllocation().locked,
      excluded: workspace.readAllocation().excluded,
      profile: investmentEditor.readDraft(), policy: balancingEditor.readDraft(),
      rules: {
        rating_caps: Object.fromEntries([...ratingInputs].map(([key, input]) => [key, input.value])),
        yield_floor: yieldFloor.checked ? "key_rate" : "none",
        yield_margin_pp: yieldMargin.value, fund_wrapper_cap_percent: wrapperCap.value,
      },
    });
    const checkRecord = (payload) => {
      if (payload?.public_id !== currentProfileId) throw new Error("strategy_owner_changed");
      const record = payload.selection;
      if (record !== null && (!record || !Number.isSafeInteger(record.version) || record.version < 1
        || record.document?.catalog_version !== catalog.version
        || !catalog.presets.some((item) => item.id === record.document.base_preset_id))) throw new Error("strategy_record_invalid");
      return record;
    };
    const flush = async () => {
      clearTimers();
      if (!dirty || busy || blocked || version === null || !currentProfileId || workspace.isDemo()) return;
      const epoch = generation;
      const sentRevision = revision;
      const sent = clone(documentState);
      const expected = version;
      const sentIntent = intent;
      unacknowledged = {document: sent, version: expected, revision: sentRevision};
      busy = true;
      notify("Сохраняем черновик в аккаунте…");
      setButtonState();
      try {
        const payload = await request("/api/profile/strategy", {method: "PUT", keepalive: true, body: JSON.stringify({
          expected_public_id: currentProfileId, expected_version: expected, intent: sentIntent, document: sent,
        })});
        if (epoch !== generation) return;
        const record = checkRecord(payload);
        if (!record || !equal(record.document, sent)) throw new Error("strategy_save_mismatch");
        version = record.version;
        unacknowledged = null;
        customCopy = record.custom_document || null;
        if (sentRevision === revision) {
          dirty = false;
          workspace.markAllocationSaved();
          notify("Черновик сохранён в аккаунте · " + new Date(record.updated_at).toLocaleTimeString("ru-RU", {hour: "2-digit", minute: "2-digit"}));
        }
      } catch (error) {
        if (epoch !== generation) return;
        blocked = true;
        notify(error.status === 409 ? "Конфликт версий. Ваши изменения остались на экране; чужая версия не перезаписана."
          : "Сохранение не подтверждено. Изменения остаются на экране. Проверьте статус перед выходом.");
      } finally {
        if (epoch === generation) {
          busy = false;
          setButtonState();
          if (dirty && !blocked) void flush();
        }
      }
    };
    const schedule = (immediate = false) => {
      clearTimeout(timer);
      if (blocked) { setButtonState(); return; }
      timer = setTimeout(() => { void flush(); }, immediate ? 0 : 500);
      if (!maximumWait) maximumWait = setTimeout(() => { void flush(); }, 4000);
      notify("Изменено · ожидает автосохранения");
      setButtonState();
    };
    const edited = () => {
      if (!documentState || version === null || workspace.isDemo()) return;
      const next = snapshot();
      if (equal(next, documentState)) return;
      clearDiagnostic();
      next.customized = true;
      documentState = next;
      intent = "edit";
      dirty = true;
      revision += 1;
      renderCards();
      schedule();
    };
    const selectExact = (input, value) => {
      const text = String(value);
      if (![...input.options].some((option) => option.value === text)) {
        const option = uiNode("option", text + " " + (input.dataset.strategyUnit || "%")); option.value = text; input.append(option);
      }
      input.value = text;
    };
    const renderDocument = () => {
      clearDiagnostic();
      investmentEditor.writeDraft(documentState.profile);
      balancingEditor.writeDraft(documentState.policy);
      workspace.writeAllocation(documentState);
      for (const [key, input] of ratingInputs) selectExact(input, documentState.rules.rating_caps[key]);
      yieldFloor.checked = documentState.rules.yield_floor === "key_rate";
      selectExact(yieldMargin, documentState.rules.yield_margin_pp);
      selectExact(wrapperCap, documentState.rules.fund_wrapper_cap_percent);
      setButtonState();
    };
    const select = (id) => {
      if (busy || dirty || blocked || version === null) return;
      const selected = id === "custom" ? clone(customCopy) : clone(catalog.presets.find((item) => item.id === id).document);
      if (!selected) return;
      if (id !== "custom") {
        for (const [section, key] of [["profile", "reserve_rub"], ["profile", "planned_withdrawal_rub"], ["policy", "securities_tax_rate_percent"]]) {
          selected[section][key] = documentState[section][key];
        }
      }
      if (equal(selected, documentState)) return;
      documentState = selected;
      intent = id === "custom" ? "edit" : "select";
      dirty = true;
      revision += 1;
      renderDocument();
      renderCards();
      schedule(true);
    };
    const tab = (index, focus = false) => {
      workspace.closeDialog();
      panels.forEach((panel, i) => { panel.hidden = i !== index; });
      [...host.querySelectorAll("[data-strategy-tab]")].forEach((button, i) => {
        button.setAttribute("aria-selected", String(i === index)); button.tabIndex = i === index ? 0 : -1;
        if (focus && i === index) button.focus();
      });
    };
    const help = (holder, title, summary, sections = []) => workspace.attachHelp(holder, "Справка: " + title, {summary, sections});
    const renderCards = () => {
      if (!cards) return;
      cards.replaceChildren();
      for (const preset of catalog.presets.filter((item) => category === "Все" || item.category === category)) {
        const card = uiNode("article", undefined, "strategy-preset-card");
        card.dataset.strategyId = preset.id;
        const selected = documentState?.base_preset_id === preset.id && !documentState?.customized;
        card.classList.toggle("is-selected", selected);
        const title = uiNode("h3", preset.title);
        const proportions = Object.values(preset.document.allocation);
        const summary = uiNode("p", `Акции ${proportions[0]}% · облигации ${proportions[1]}% · фонды ${proportions[2]}% · деньги ${proportions[3]}%`, "preset-proportions");
        const actions = uiNode("div", undefined, "preset-actions");
        const choose = uiNode("button", selected ? "Выбрано" : "Выбрать", "button button-primary");
        choose.type = "button"; choose.dataset.chooseStrategy = preset.id; choose.setAttribute("aria-pressed", String(selected));
        choose.addEventListener("click", () => select(preset.id));
        const more = uiNode("button", "Подробнее", "button button-secondary");
        more.type = "button";
        more.addEventListener("click", () => {
          const body = workspace.openDialog(preset.title);
          body.append(uiNode("p", preset.description), uiNode("p", preset.risk, "inline-note"),
            uiNode("p", preset.parameter_basis), uiNode("p", "Историческая проверка на рынке РФ и вероятность прибыли пока не подтверждены. Значения можно использовать как редактируемые условия, не как обещание результата."));
          const sourceTitle = uiNode("h4", "Основания подхода"); body.append(sourceTitle);
          for (const sourceId of preset.source_ids) {
            const source = catalog.sources.find((item) => item.id === sourceId);
            if (!source?.url?.startsWith("https://")) continue;
            const link = uiNode("a", source.title); link.href = source.url; link.target = "_blank"; link.rel = "noopener noreferrer"; body.append(link);
          }
          body.append(uiNode("p", "Именные варианты — адаптации принципов, не оригинальные портфели авторов и не их рекомендации для РФ.", "field-hint"));
        });
        actions.append(choose, more);
        card.append(uiNode("span", preset.category, "card-label"), title, uiNode("p", preset.description), summary, actions);
        cards.append(card);
      }
      setButtonState();
    };
    const percentControl = (parent, label, value, onChange, unit = "%") => {
      const row = uiNode("label", undefined, "strategy-rule-row");
      const name = uiNode("span", label);
      const selectBox = uiNode("select");
      selectBox.setAttribute("aria-label", label);
      selectBox.dataset.strategyUnit = unit;
      // Every integer percent is reachable without typing; saved fractional caps
      // have their exact value added, never rounded into a nearby option.
      for (let n = 0; n <= 100; n += 1) { const option = uiNode("option", n + " " + unit); option.value = String(n); selectBox.append(option); }
      if (![...selectBox.options].some((item) => item.value === value)) { const option = uiNode("option", value + " " + unit); option.value = value; selectBox.append(option); }
      selectBox.value = value;
      selectBox.addEventListener("change", onChange);
      row.append(name, selectBox); parent.append(row);
      return selectBox;
    };
    const build = () => {
      if (built) return;
      built = true;
      if (loadNotice) loadNotice.hidden = true;
      initialControls.forEach((element) => { element.inert = false; });
      host.classList.add("strategy-compact");
      const heading = host.querySelector(".page-heading");
      heading.querySelector("h2").textContent = "Моя стратегия";
      heading.querySelector("p:last-child").textContent = "10 готовых подходов или ваши правила. Изменения автоматически сохраняются как черновик; сделки не создаются.";
      const oldJump = host.querySelector(".strategy-jump");
      if (oldJump.nextElementSibling?.classList.contains("setting-toggle-help")) oldJump.nextElementSibling.remove();
      oldJump.remove();
      const navigation = uiNode("div", undefined, "strategy-tabs"); navigation.setAttribute("role", "tablist"); navigation.setAttribute("aria-label", "Настройки стратегии");
      const toolbar = uiNode("div", undefined, "strategy-savebar");
      currentTitle = uiNode("strong"); saveStatus = uiNode("span", "Проверяем сохранённую версию…"); saveStatus.setAttribute("role", "status");
      retry = uiNode("button", "Проверить сохранение", "button button-secondary"); retry.type = "button"; retry.hidden = true; retry.addEventListener("click", () => { if (version === null) void load(); else void reconcile(); });
      reload = uiNode("button", "Загрузить версию", "button button-secondary"); reload.type = "button"; reload.addEventListener("click", () => {
        if (busy || (dirty && !window.confirm("Заменить изменения на экране последней сохранённой копией?"))) return;
        dirty = false; version = null; void load();
      });
      restore = uiNode("button", "Мой вариант", "button button-secondary"); restore.type = "button"; restore.id = "strategy-restore-custom"; restore.addEventListener("click", () => select("custom"));
      toolbar.append(currentTitle, saveStatus, restore, retry, reload);
      heading.after(toolbar, navigation);
      panels = sectionNames.map((name, index) => {
        const panel = uiNode("div", undefined, "strategy-tab-panel"); panel.id = "strategy-panel-" + index; panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", "strategy-tab-" + index);
        const button = uiNode("button", name, "strategy-tab"); button.type = "button"; button.id = "strategy-tab-" + index; button.dataset.strategyTab = String(index); button.setAttribute("role", "tab"); button.setAttribute("aria-controls", panel.id);
        button.addEventListener("click", () => tab(index));
        button.addEventListener("keydown", (event) => {
          const next = {ArrowRight: (index + 1) % 5, ArrowLeft: (index + 4) % 5, Home: 0, End: 4}[event.key];
          if (next !== undefined) { event.preventDefault(); tab(next, true); }
        });
        navigation.append(button); host.append(panel); return panel;
      });
      const layout = host.querySelector(".strategy-layout"); panels[1].append(layout);
      const live = host.querySelector(".strategy-live-settings");
      panels[2].append(investmentProfileForm.closest("article")); panels[3].append(balancingPolicyForm.closest("article"));
      live.remove();
      host.querySelector(":scope > .section-heading")?.remove();
      const group = layout.querySelector(".strategy-preset-group");
      if (group?.previousElementSibling?.classList.contains("setting-toggle-help")) group.previousElementSibling.remove();
      group?.nextElementSibling?.remove(); group?.remove();
      layout.querySelector(".strategy-summary .inline-note").textContent = "Доли сохраняются в черновике. Подтверждённые профиль и лимиты пока применяются отдельно; черновик не является торговым поручением.";
      const filters = uiNode("div", undefined, "chip-group"); filters.setAttribute("role", "group"); filters.setAttribute("aria-label", "Категории подходов");
      for (const label of ["Все", "Базовые", "По задачам", "Именные"]) {
        const button = uiNode("button", label, "filter-chip"); button.type = "button"; button.setAttribute("aria-pressed", String(label === category));
        button.addEventListener("click", () => { category = label; [...filters.children].forEach((item) => item.setAttribute("aria-pressed", String(item === button))); renderCards(); }); filters.append(button);
      }
      cards = uiNode("div", undefined, "strategy-catalog"); panels[0].append(filters, cards);
      const ratingPanel = uiNode("details", undefined, "settings-disclosure"); const ratingTitle = uiNode("summary", "Рейтинги: отдельные ограничения");
      const ratingBody = uiNode("div", undefined, "strategy-rating-grid"); ratingPanel.append(ratingTitle, uiNode("p", "Пределы считаются от всего капитала. Они не обязаны суммироваться до 100%. Нулевой предел запрещает новые покупки этой категории. Разные шкалы не равны по риску.", "field-hint"), ratingBody);
      help(ratingTitle, "Пределы рейтингов", "Это максимальные доли, а не обязательное количество бумаг и не вероятность возврата денег.", [["Пример", "При капитале 100 000 ₽ предел 5% для BBB разрешает не более 5 000 ₽ в этой категории, если остальные ограничения соблюдены."], ["Что не включается автоматически", "Низкие рейтинги не разрешаются одним положительным лимитом: разрешение повышенного риска остаётся отдельным. Дефолтные бумаги, неизвестные данные и неподдержанные условия не становятся доступными из-за высокого процента."], ["Подключение", "Эти детальные правила сохраняются в рабочей копии. Их применение в серверном подборе требует расширения проверенного финансового контура; текущий экран этого не обещает."]]);
      for (const level of catalog.rating_levels) {
        const input = percentControl(ratingBody, level === "NR" ? "Без рейтинга" : level, documentState.rules.rating_caps[level], edited);
        ratingInputs.set(level, input);
        workspace.attachHelp(input.parentElement, "Справка: предел " + level, () => ({
          summary: "Верхняя доля этой категории от всего капитала. Это не обязательная покупка и не оценка вероятности возврата денег.",
          current: `${input.value}% выбрано в рабочем черновике.`,
          sections: [["Если увеличить", "Вы расширяете допустимое место для категории, но не улучшаете качество компаний. Данные, связанные компании и остальные ограничения всё равно нужны."],
            ["Если уменьшить", "Для новых покупок этой категории остаётся меньше места. Ноль запрещает такие покупки по этому правилу. Уже купленные бумаги не продаются."],
            ["Условный пример", "Предел 5% при капитале 100 000 ₽ соответствует 5 000 ₽. Все выпуски в категории складываются, а не получают по 5 000 ₽ каждый."],
            ["Источник и применение", "Буквы без агентства, шкалы, даты и объекта рейтинга не подтверждают надёжность. Сейчас детальные категории сохраняются в черновике; они ещё не подключены к действующему подбору."]],
        }));
      }
      panels[3].append(ratingPanel);
      const rules = uiNode("div", undefined, "settings-card");
      const floorLabel = uiNode("label", undefined, "check"); yieldFloor = uiNode("input"); yieldFloor.type = "checkbox"; yieldFloor.addEventListener("change", edited); floorLabel.append(yieldFloor, uiNode("span", "Порог: не ниже ключевой ставки")); rules.append(floorLabel);
      help(floorLabel, "Порог доходности", "Фильтр для сопоставимой рублёвой доходности по денежным потокам, а не для купонного процента.", [["При нехватке данных", "Без подтверждённой ставки, цены и условий доходность неизвестна; покупать ради процента нельзя."], ["Без подходящих бумаг", "Деньги остаются нераспределёнными. Кредитные ограничения не ослабляются автоматически."], ["Применение", "Сейчас правило сохраняется в черновике для расширенного подбора. Сам переключатель не изменяет прежний серверный расчёт."]]);
      yieldMargin = percentControl(rules, "Надбавка к порогу, п.п.", "0", edited, "п.п.");
      help(yieldMargin.parentElement, "Надбавка к порогу", "На сколько процентных пунктов выбранный минимум выше подтверждённой ключевой ставки.", [["Пример", "При условной ставке 10% надбавка 2 п.п. означает минимум 12%, а не 10,2%. Это пример, не текущая ставка ЦБ."], ["Влияние", "Более высокий порог обычно оставляет меньше подходящих вариантов. Он не разрешает слабые компании. Правило пока сохраняется для расширенного подбора."]]);
      wrapperCap = percentControl(rules, "Один фонд: внешний предел", "20", edited);
      help(wrapperCap.parentElement, "Один фонд", "Верхняя доля одного фонда отдельно от компаний внутри него. Нужен раскрытый состав, чтобы проверить пересечения с прямыми бумагами.", [["Пример", "Два фонда с одинаковыми акциями не становятся независимыми наборами компаний."], ["Важно", "Без данных о составе подтверждать диверсификацию нельзя. Расширенное правило пока относится к сохраняемому черновику."]]);
      panels[3].append(rules);
      const checkCard = uiNode("article", undefined, "settings-card");
      checkCard.append(uiNode("h3", "Что уже проверено, а что неизвестно"), uiNode("p", "Сумма целевых долей — 100%. Черновик сохраняется отдельно от подтверждённых параметров. Ни один подход не имеет доказанной вероятности прибыли 99,9%.", "inline-note"), uiNode("p", "Предыдущие подтверждённые профиль и лимиты остаются действующими. Чтобы применить их изменения, откройте «Капитал» или «Лимиты» и проверьте точные значения перед подтверждением."));
      help(checkCard.querySelector("h3"), "Границы проверки", "Работоспособность кнопок и сохранения — не подтверждение доходности стратегии.", [["Проверяемые расчёты", "Стоимость лотов, сумма долей, пределы концентрации и результаты явно заданных стрессов можно воспроизвести."], ["Чего пока нет", "Нет проверенной истории всех нужных активов и откалиброванных вероятностей. Именные принципы не становятся оригинальными стратегиями авторов от смены названия."], ["Почему не 99,9%", "Даже много удачных сценариев внутри модели не исключают неизвестные рынку события. Доверительный уровень расчёта — не обещанная вероятность прибыли."]]);
      const diagnostic = uiNode("div", undefined, "strategy-diagnostic");
      diagnostic.append(uiNode("h4", "Проверить на условной сумме"), uiNode("p", "Это проверка лота и заданных изменений цен, а не прогноз по вашему счёту.", "field-hint"));
      const capital = uiNode("select"); capital.setAttribute("aria-label", "Условный капитал, рубли");
      for (const value of [1000, 3000, 10000, 50000, 100000, 1000000]) { const option = uiNode("option", new Intl.NumberFormat("ru-RU").format(value) + " ₽"); option.value = String(value); capital.append(option); }
      capital.value = "100000";
      capital.addEventListener("change", clearDiagnostic);
      const amountLabel = uiNode("label", "Капитал примера", "strategy-rule-row"); amountLabel.append(capital);
      const calculate = uiNode("button", "Проверить пример", "button button-secondary"); calculate.type = "button";
      const result = uiNode("div"); result.setAttribute("role", "status");
      diagnosticResult = result;
      calculate.addEventListener("click", async () => {
        if (!version || busy || dirty || blocked) { result.textContent = "Сначала выберите подход или измените параметр и дождитесь автосохранения черновика."; return; }
        const epoch = generation; const currentRevision = revision; const expected = version;
        const calculationRevision = ++diagnosticRevision;
        calculate.disabled = true; result.textContent = "Считаем условный пример…";
        try {
          const data = await request("/api/profile/strategy/feasibility", {method: "POST", body: JSON.stringify({expected_public_id: currentProfileId, expected_version: expected, nav_rub: capital.value, lot_cost_rub: "1000.01"})});
          if (epoch !== generation || currentRevision !== revision || version !== expected || calculationRevision !== diagnosticRevision) return;
          if (data?.strategy_version !== expected || data?.public_id !== currentProfileId) throw new Error("strategy_diagnostic_mismatch");
          result.replaceChildren(uiNode("p", `Условный лот с расходами: 1 000,01 ₽. Предел одной компании: ${data.issuer_budget_rub ?? "не задан"} ₽. Помещается лотов: ${data.lots_per_issuer ?? "неизвестно"}.`));
          if (data.stress) {
            for (const row of data.stress.scenarios) result.append(uiNode("p", `${row.title}: ${row.portfolio_change_percent}% (${row.change_rub} ₽).`, "field-hint"));
            result.append(uiNode("p", data.stress.scope, "field-hint"));
          }
          result.append(uiNode("p", data.note || "Не хватает заданного предела компании.", "field-hint"));
        } catch { if (epoch === generation && currentRevision === revision && calculationRevision === diagnosticRevision) result.textContent = "Расчёт не подтверждён. Проверьте соединение и версию черновика."; }
        finally { calculate.disabled = false; }
      });
      diagnostic.append(amountLabel, calculate, result);
      checkCard.append(diagnostic);
      panels[4].append(checkCard);
      host.addEventListener("input", (event) => { if (event.target.closest("#investment-profile-form, #balancing-policy-form")) edited(); });
      document.addEventListener("strategy:allocation", edited);
      for (const name of ["change", "pointerup"]) host.addEventListener(name, () => { if (dirty) schedule(true); });
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") void flush(); });
      window.addEventListener("pagehide", () => { void flush(); });
      tab(0);
      renderCards();
    };
    const preserveEditor = (name, editor, initial, record, firstLoad) => {
      const values = editor.readDraft();
      const changed = editor.isDirty() && (firstLoad || !equal(values, initial));
      if ((!record && editor.savedVersion() > 0) || changed) {
        documentState[name] = values;
        documentState.customized = true;
      }
      return changed;
    };
    const load = async () => {
      if (loading || busy || dirty || !currentProfileId || workspace.isDemo() || version !== null) return;
      loading = true;
      showInitialLoad();
      const epoch = ++generation;
      const owner = currentProfileId;
      const firstLoad = documentState === null;
      const initialProfile = investmentEditor.readDraft();
      const initialPolicy = balancingEditor.readDraft();
      const initialAllocation = workspace.readAllocation();
      try {
        const data = await request("/api/strategy/catalog", {method: "GET"});
        if (epoch !== generation || currentProfileId !== owner) return;
        if (!data || data.presets?.length !== 10 || !data.version) throw new Error("strategy_catalog_invalid");
        catalog = data;
        const payload = await request("/api/profile/strategy", {method: "GET"});
        if (epoch !== generation || currentProfileId !== owner) return;
        const record = checkRecord(payload);
        if (!investmentEditor.isReady() || !balancingEditor.isReady()) throw new Error("strategy_unverified_profile");
        documentState = record?.document || clone(catalog.presets.find((item) => item.id === catalog.default_id).document);
        const profileChanged = preserveEditor("profile", investmentEditor, initialProfile, record, firstLoad);
        const policyChanged = preserveEditor("policy", balancingEditor, initialPolicy, record, firstLoad);
        let preserveEdits = profileChanged || policyChanged;
        const allocation = workspace.readAllocation();
        if (!equal(allocation, initialAllocation)) {
          Object.assign(documentState, allocation, {customized: true}); preserveEdits = true;
        }
        customCopy = record?.custom_document || null;
        version = record?.version ?? 0; unacknowledged = null; blocked = false; dirty = preserveEdits;
        build(); renderDocument(); renderCards();
        notify(record ? "Черновик загружен из аккаунта" : "Исходный черновик · ещё не сохранён. Неизвестные личные суммы не подставлены.");
        if (record && !preserveEdits) workspace.markAllocationSaved();
        if (preserveEdits) { intent = "edit"; revision += 1; schedule(); }
      } catch {
        if (epoch !== generation) return;
        blocked = true;
        notify("Не удалось проверить сохранённый черновик. Ранее подтверждённые параметры не заменены.");
        loading = false;
        showInitialLoad(true);
        setButtonState();
      } finally {
        if (epoch === generation) loading = false;
      }
    };
    const reconcile = async () => {
      if (busy || !currentProfileId || !catalog) return;
      const epoch = generation;
      try {
        const payload = await request("/api/profile/strategy", {method: "GET"});
        if (epoch !== generation) return;
        const record = checkRecord(payload);
        const currentMatches = record && equal(record.document, documentState);
        const sentMatches = record && unacknowledged
          && record.version === unacknowledged.version + 1
          && equal(record.document, unacknowledged.document);
        if (currentMatches || sentMatches) {
          version = record.version; customCopy = record.custom_document;
          unacknowledged = null; blocked = false;
          if (currentMatches) {
            dirty = false;
            workspace.markAllocationSaved();
            notify("Сохранение черновика подтверждено сервером");
          } else {
            // The server acknowledged the earlier snapshot. Keep newer edits
            // visible and send them against that version, never discard them.
            dirty = true;
            schedule(true);
          }
        } else if ((record?.version ?? 0) === version) {
          blocked = false; schedule(true);
        } else {
          notify("На сервере другая версия. Загрузите её явно; ваши текущие значения пока остались на экране.");
        }
      } catch { if (epoch === generation) notify("Сервер пока недоступен. Сохранение не подтверждено."); }
      if (epoch === generation) setButtonState();
    };
    return {
      load, acceptExternal: edited,
      prepare: () => { if (version === null) { showInitialLoad(); setButtonState(); } },
      hasPending: () => dirty || busy,
      isCurrentSaved: () => built && version > 0 && !dirty && !busy && !blocked,
      reset: () => {
        clearTimers(); clearDiagnostic(); generation += 1;
        pendingRequests.forEach((controller) => controller.abort()); version = null; dirty = false; busy = false; blocked = false;
        documentState = null; customCopy = null; unacknowledged = null; revision = 0; loading = false;
        if (loadNotice) loadNotice.hidden = true;
        ratingInputs.forEach((input) => { input.value = "0"; });
        if (yieldFloor) yieldFloor.checked = false;
        if (yieldMargin) yieldMargin.value = "0";
        if (wrapperCap) wrapperCap.value = "0";
        notify("Проверяем аккаунт…"); setButtonState();
      },
    };
  };

  const settingsEditors = [investmentEditor, balancingEditor];
  window.addEventListener("beforeunload", (event) => {
    if (settingsEditors.some((editor) => editor.hasPending())) {
      event.preventDefault();
    }
  });

  const showProfile = (profile) => {
    if (profileContextLost || workspace?.isDemo()) return;
    workspace?.setSession();
    if (currentProfileId && currentProfileId !== profile.public_id) {
      pauseProfileContext();
      return;
    }
    if (currentProfileId !== profile.public_id) {
      settingsEditors.forEach((editor) => editor.reset());
    }
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
    startCbrIndicators();
    void loadTbankStatus();
    strategyLibrary?.prepare();
    void Promise.all([investmentEditor.load(), balancingEditor.load()]).then(() => strategyLibrary?.load());
    void loadLiveMandate().then(() => {
      void loadProposals();
      void loadExecutions({inspectLatest: true});
    });
  };

  const showAuth = () => {
    if (profileContextLost || workspace?.isDemo()) return;
    recoveryGeneration += 1;
    clearTimeout(recoveryTimer);
    settingsEditors.forEach((editor) => editor.reset());
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

    if (workspace?.isDemo()) return;
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

  const verifyProfileContext = async () => {
    if (!currentProfileId || profileContextLost || profileCheckInFlight
      || document.visibilityState !== "visible") return;
    profileCheckInFlight = true;
    try {
      await api("/api/me", {method: "GET"});
    } catch {
      // api pauses on identity changes. A network failure grants no new authority.
    } finally {
      profileCheckInFlight = false;
    }
  };

  window.addEventListener("focus", () => { void verifyProfileContext(); });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) void verifyProfileContext();
  });
  requiredElement("#profile-context-reload").addEventListener("click", () => {
    if (settingsEditors.some((editor) => editor.hasPending()) && !window.confirm(
      "Обновить страницу? Несохранённые изменения этой вкладки будут потеряны."
    )) return;
    settingsEditors.forEach((editor) => editor.reset());
    location.reload();
  });

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

  let searchDebounce;
  hunterQuery.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    hunterRequest?.abort();
    hunterGeneration += 1;
    if (hunterQuery.value.trim()) searchDebounce = setTimeout(() => { void searchHunter(); }, 250);
    else { hunterResults.replaceChildren(); workspace?.setCatalog([]); hunterSearch.disabled = false; hunterSearch.textContent = "Найти"; }
  });

  hunterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void searchHunter();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") {
      return;
    }
    void verifyProfileContext();

    if (lastPortfolioSnapshot) renderPortfolioDataStatus();

    const cbrStale = Date.now() - lastCbrIndicatorRefreshAt >= 5 * 60 * 1000;
    if (cbrStale) {
      void loadCbrIndicators();
    }

    const portfolioStale = Date.now() - lastPortfolioRefreshAt >= 5 * 60 * 1000;
    if (tbankIsConnected && portfolioStale && !portfolioRequestInFlight) {
      void loadPortfolioData({force: true});
    }
  });

  portfolioRefresh.addEventListener("click", () => {
    void loadPortfolioData({force: true});
  });
  activityRefresh.addEventListener("click", () => { void loadAccountActivity(); });
  recoveryRefresh.addEventListener("click", () => { void loadRecoveryStatus(); });

  portfolioRetry.addEventListener("click", () => {
    void loadPortfolioData({force: true});
  });

  analysisRefresh.addEventListener("click", () => {
    void loadAnalysis();
  });

  const closestButtonTarget = (event, selector) => {
    const target = event.target;
    if (!(target instanceof Element)) {
      return null;
    }
    const button = target.closest(selector);
    return button instanceof HTMLButtonElement ? button : null;
  };

  portfolioHistoryPeriodButtons.forEach((button) => {
    button.addEventListener("click", () => {
      if (button.classList.contains("hidden") || !lastPortfolioVisualization) {
        return;
      }
      const days = Number(button.dataset.portfolioHistoryDays);
      if (!Number.isFinite(days)) {
        return;
      }
      selectedPortfolioHistoryDays = days;
      renderPortfolioHistory(lastPortfolioVisualization.history || []);
    });
  });

  allocationViewButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const view = button.dataset.allocationView;
      if (!["class", "currency", "sector", "position"].includes(view)) {
        return;
      }
      selectedAllocationView = view;
      renderPortfolioAllocationView();
    });
  });

  positionsList.addEventListener("click", (event) => {
    const button = closestButtonTarget(event, "[data-instrument-detail]");
    if (button?.dataset.instrumentDetail) {
      void openInstrumentDetail(button.dataset.instrumentDetail);
    }
  });

  positionsTableBody.addEventListener("click", (event) => {
    const button = closestButtonTarget(event, "[data-instrument-detail]");
    if (button?.dataset.instrumentDetail) {
      void openInstrumentDetail(button.dataset.instrumentDetail);
    }
  });

  instrumentDetailClose.addEventListener("click", closeInstrumentDetail);

  instrumentMarketModeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.marketMode;
      if (!["line", "candles"].includes(mode)) {
        return;
      }
      instrumentMarketMode = mode;
      syncInstrumentMarketControls();
      if (instrumentMarketPayload) {
        renderInstrumentMarketChart(instrumentMarketPayload);
      }
    });
  });

  instrumentMarketPeriodButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const period = button.dataset.marketPeriod;
      if (!["1d", "1w", "1m", "3m", "1y"].includes(period)) {
        return;
      }
      instrumentMarketPeriod = period;
      syncInstrumentMarketControls();
      if (instrumentMarketUid) {
        void loadInstrumentMarket(instrumentMarketUid, {force: true});
      }
    });
  });

  instrumentMarketRetry.addEventListener("click", () => {
    if (!instrumentMarketUid) {
      return;
    }
    stopInstrumentMarketStream({resetRetry: true});
    void loadInstrumentMarket(instrumentMarketUid, {force: true});
  });

  instrumentMarketScrubber.addEventListener("input", inspectInstrumentMarketChart);
  instrumentMarketScrubber.addEventListener("blur", removeInstrumentMarketCrosshair);

  homeAttentionList.addEventListener("click", (event) => {
    const button = closestButtonTarget(event, "[data-home-attention-view]");
    const view = button?.dataset.homeAttentionView;
    if (view && VIEW_TITLES[view]) {
      navigateToView(view);
    }
  });

  proposalCreateOptions.addEventListener("click", (event) => {
    const button = closestButtonTarget(event, "[data-proposal-create]");
    if (button) {
      void createProposal(button);
    }
  });

  proposalHistory.addEventListener("click", (event) => {
    const decisionButton = closestButtonTarget(event, "[data-proposal-decision]");
    if (decisionButton) {
      void decideProposal(decisionButton);
      return;
    }
    const executionButton = closestButtonTarget(event, "[data-execution-start]");
    if (executionButton) {
      void startExecution(executionButton);
    }
  });

  executionHistory.addEventListener("click", (event) => {
    const inspect = closestButtonTarget(event, "[data-execution-inspect]");
    if (inspect) {
      void loadExecutionDetails(inspect.dataset.executionInspect);
      return;
    }
    const action = closestButtonTarget(event, "[data-execution-action]");
    if (action) {
      void mutateExecution(action);
    }
  });

  executionRefresh.addEventListener("click", () => {
    void loadExecutions({inspectLatest: true});
  });

  liveMandateForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void saveLiveMandate();
  });

  liveMandateRevoke.addEventListener("click", () => {
    void revokeLiveMandate();
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

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") {
      stopInstrumentMarketStream();
      return;
    }
    if (
      currentView === "portfolio"
      && instrumentMarketUid
      && !instrumentDetail.classList.contains("hidden")
    ) {
      startInstrumentMarketStream();
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
      `request ${lastFailedRequestId || "нет ошибок в этой вкладке"}`,
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

  tbankForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage(tbankMessage, "");
    resetTbankPreview();

    const credential = tbankToken.value.trim();
    const environment = tbankEnvironmentSelect.value;

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
      void loadLiveMandate();
      showMessage(tbankMessage, "T-Invest подключён. Токен сохранён в зашифрованном виде.");
    } catch (error) {
      resetTbankPreview();
      tbankForm.classList.remove("hidden");
      if (error.status === 400) {
        showMessage(tbankMessage, "Не удалось подключить выбранный счёт. Проверьте токен.", true);
      } else if (error.status === 409) {
        showMessage(tbankMessage, error.message === "broker_disconnect_required"
          ? "Сначала отключите текущий счёт кнопкой «Отключить T-Invest», затем подключите другой. Текущее подключение сохранено."
          : "Подключение не изменено. Проверьте состояние счёта и незавершённые заявки.", true);
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
      "Отключить T-Invest? Токен, сохранённая история портфеля и связанные расчёты будут удалены из OmniCIO. Настройки стратегии сохранятся. Активы и счёт у брокера останутся без изменений."
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
      void loadLiveMandate();
      showMessage(tbankMessage, "T-Invest отключён.");
    } catch (error) {
      showMessage(
        tbankMessage,
        error.status === 409
          ? "T-Invest нельзя отключить, пока Live-run не завершён: сначала сверите или отмените реальную заявку."
          : "Не удалось удалить подключение.",
        true,
      );
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
    stopCbrIndicators();

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
        error.status === 409
          ? "Аккаунт нельзя удалить, пока Live-run не завершён. Сначала сверите или отмените реальную заявку."
          : "Аккаунт не удалён. Обновите страницу и повторите попытку.",
        true,
      );
    }
  });

  logoutButton.addEventListener("click", async () => {
    if (settingsEditors.some((editor) => editor.hasPending()) && !window.confirm(
      "Выйти из аккаунта? Несохранённые изменения профиля и лимитов будут потеряны."
    )) return;
    settingsEditors.forEach((editor) => editor.reset());
    stopCbrIndicators();
    try {
      await api("/api/auth/logout", {method: "POST"});
    } catch (error) {
      if (!profileContextLost) throw error;
    } finally {
      pendingTbankCredential = null;
      if (!profileContextLost) location.reload();
    }
  });

  const enterDemoWorkspace = (data, historyPoints) => {
    stopCbrIndicators();
    window.clearInterval(owlTimer);
    invalidatePortfolioRequest();
    settingsEditors.forEach((editor) => editor.reset());
    authCard.classList.add("hidden");
    profilePanel.classList.remove("hidden");
    currentProfileId = "";
    tbankIsConnected = false;
    portfolioVisualizationLoaded = true;
    for (const element of [profileId, drawerProfileId, profilePageId, supportProfileId, settingsProfileId]) element.textContent = "Демо";
    initializeNavigation();
    renderPortfolio(data);
    renderPortfolioVisualization({history: historyPoints, latest: null});
    clearPortfolioFreshnessTimer();
    homeHistoryNote.textContent = "Вымышленная история за 90 дней. Демонстрация интерфейса, не результат инвестиций.";
    portfolioHistoryNote.textContent = homeHistoryNote.textContent;
    portfolioRefreshed.textContent = "Демонстрационные данные";
    homeSnapshotTime.textContent = "Вымышленный портфель · без подключения";
    topConnectionText.textContent = "Демонстрация";
    overviewAccount.textContent = "Посмотрите, как устроен OmniCIO";
    overviewConnectionText.textContent = "Для своего портфеля перейдите ко входу и подключите счёт.";
    setStateBadge(homeHistoryState, "Демо", "state-next");
    setStateBadge(portfolioStateBadge, "Демо", "state-next");
    for (const badge of [homePortfolioState, homePortfolioSummaryState, owlState]) setStateBadge(badge, "Демо", "state-next");
    portfolioDataNotice.textContent = "Все значения на этом экране вымышлены. Вход и доступ к брокеру не используются.";
    setHomeAttentionBucket("connection", [{severity: "info", title: "Демонстрационный режим", detail: "Познакомьтесь с интерфейсом без реальных сделок.", view: "assets"}]);
    for (const form of [tbankForm, tbankAccountForm, liveMandateForm, deleteAccountForm]) {
      form.querySelectorAll("input,select,button").forEach((control) => { control.disabled = true; });
    }
    for (const control of [portfolioRefresh, analysisRefresh, tbankDisconnect, logoutButton, deleteAccountStart, executionRefresh]) control.disabled = true;
    showMessage(tbankMessage, "В демо подключение счёта недоступно. Перейдите ко входу для своего аккаунта.");
    showMessage(executionMessage, "Деморежим: заявки брокеру не отправляются.");
    showMessage(analysisStatus, "Деморежим: персональный анализ не запрашивается. Изучите каталог, структуру портфеля и черновик стратегии.");
  };

  workspace = window.OmniWorkspace.init({
    navigate: navigateToView,
    openInstrument: openInstrumentDetail,
    renderAssets: renderHunterResults,
    enterDemo: enterDemoWorkspace,
    theme: (preference) => { saveTheme(preference); applyTheme(preference); },
    hasPending: () => settingsEditors.some((editor) => editor.hasPending()) || executionRequestInFlight || liveMandateRequestInFlight || proposalRequestInFlight,
    refreshAnalysis: () => {
      if (tbankIsConnected) void loadAnalysis();
      else workspace.toast("Подключите свой счёт для подтверждённых событий.");
    },
  });
  enhanceSettingsForm(investmentProfileForm);
  enhanceSettingsForm(balancingPolicyForm);
  groupSettingsForm(investmentProfileForm, [
    {title: "Основное · капитал и время", note: "Резерв, снятия и горизонт", indexes: [0, 1, 2], open: true},
    {title: "Расширенное · риск и ликвидность", note: "Просадка и срок выхода", indexes: [3, 4], open: false},
  ]);
  groupSettingsForm(balancingPolicyForm, [
    {title: "Концентрация", note: "Одна бумага, эмитент, группа и сектор", indexes: [0, 1, 2, 3], open: false},
    {title: "Классы активов", note: "Верхние лимиты, а не целевые доли", indexes: [4, 5, 6], open: false},
    {title: "Расширенное · ликвидность и оборот", note: "Рейтинг, срок и доступный объём", indexes: [7, 8, 9, 10, 11], open: false},
    {title: "Расширенное · сценарные допущения", note: "Налог, поправки и пороги выгоды", indexes: [12, 13, 14, 15, 16], open: false},
  ]);


  strategyLibrary = createStrategyLibrary();
  settingsEditors.push(strategyLibrary);

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Tab" || !document.body.classList.contains("drawer-open")) return;
    const focusable = [...appDrawer.querySelectorAll("button:not(:disabled), a[href]")].filter((item) => item.getClientRects().length);
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  renderReleaseInfo();
  applyTheme(storedTheme());
  refreshInstallState();
  startOwl();
  void loadState();
})();
