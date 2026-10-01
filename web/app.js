(() => {
  "use strict";

  const vkidForm = document.querySelector("#vkid-form");
  const vkidLogin = document.querySelector("#vkid-login");
  const authCard = document.querySelector("#auth-card");
  const profilePanel = document.querySelector("#profile-panel");
  const message = document.querySelector("#auth-message");
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

  const viewTitle = document.querySelector("#view-title");
  const navItems = [...document.querySelectorAll("[data-view]")];
  const viewPanels = [...document.querySelectorAll("[data-view-panel]")];
  const viewLinks = [...document.querySelectorAll("[data-go-view]")];
  const appearanceQuick = document.querySelector("#appearance-quick");
  const themeButtons = [...document.querySelectorAll("[data-theme-option]")];
  const motionToggle = document.querySelector("#motion-toggle");

  const overviewAccount = document.querySelector("#overview-account");
  const overviewConnectionText = document.querySelector("#overview-connection-text");
  const overviewConnectionPill = document.querySelector("#overview-connection-pill");

  const VIEW_TITLES = {
    overview: "Обзор",
    portfolio: "Портфель",
    intelligence: "Система",
    activity: "События",
    settings: "Настройки",
  };

  const THEME_KEY = "omnicio_theme";
  const MOTION_KEY = "omnicio_motion";
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");
  const systemReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let pendingTbankCredential = null;
  let pendingTbankEnvironment = null;
  let currentView = "overview";

  const showMessage = (text, isError = false) => {
    message.textContent = text;
    message.classList.toggle("error", isError);
  };

  const showTbankMessage = (text, isError = false) => {
    tbankMessage.textContent = text;
    tbankMessage.classList.toggle("error", isError);
  };

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

  const storedValue = (key, fallback) => {
    try {
      return window.localStorage.getItem(key) || fallback;
    } catch {
      return fallback;
    }
  };

  const storeValue = (key, value) => {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      // Appearance preferences are non-critical and may be blocked by the browser.
    }
  };

  const resolveTheme = (preference) => {
    if (preference === "auto") {
      return systemDark.matches ? "dark" : "light";
    }
    return preference === "light" ? "light" : "dark";
  };

  const applyTheme = (preference) => {
    const resolved = resolveTheme(preference);
    document.body.dataset.theme = resolved;
    themeButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeOption === preference));
    });
  };

  const motionPreference = () => storedValue(MOTION_KEY, "full");

  const applyMotion = () => {
    const requested = motionPreference();
    const reduced = systemReducedMotion.matches || requested === "reduced";
    document.body.dataset.motion = reduced ? "reduced" : "full";
    if (motionToggle) {
      motionToggle.checked = requested !== "reduced";
      const label = motionToggle.closest(".switch-control")?.querySelector("em");
      if (label) {
        label.textContent = reduced ? "Отключены" : "Включены";
      }
    }
  };

  const setView = (view, {focus = false} = {}) => {
    if (!VIEW_TITLES[view]) {
      return;
    }
    currentView = view;
    navItems.forEach((item) => {
      const active = item.dataset.view === view;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-selected", String(active));
    });
    viewPanels.forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.viewPanel !== view);
    });
    viewTitle.textContent = VIEW_TITLES[view];

    if (focus) {
      document.querySelector(`[data-view-panel="${view}"]`)?.scrollIntoView({
        block: "start",
        behavior: document.body.dataset.motion === "reduced" ? "auto" : "smooth",
      });
    }
  };

  const resetTbankPreview = () => {
    pendingTbankCredential = null;
    pendingTbankEnvironment = null;
    tbankAccount.replaceChildren();
    tbankAccountForm.classList.add("hidden");
  };

  const renderOverviewTbank = (status) => {
    if (!overviewAccount || !overviewConnectionText || !overviewConnectionPill) {
      return;
    }

    if (!status.connected) {
      overviewAccount.textContent = "Не подключён";
      overviewConnectionText.textContent = "T-Invest не подключён";
      overviewConnectionPill.classList.add("is-offline");
      return;
    }

    const environment = status.environment === "sandbox" ? "Песочница" : "Биржа";
    const accountName = status.account_name || "Брокерский счёт";
    overviewAccount.textContent = accountName;
    overviewConnectionText.textContent = `${environment} · подключено`;
    overviewConnectionPill.classList.remove("is-offline");
  };

  const renderTbankStatus = (status) => {
    resetTbankPreview();
    tbankToken.value = "";
    renderOverviewTbank(status);

    if (!status.connected) {
      tbankConnected.classList.add("hidden");
      tbankForm.classList.remove("hidden");
      if (tbankStatusBadge) {
        tbankStatusBadge.textContent = "Не подключён";
      }
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
    if (tbankStatusBadge) {
      tbankStatusBadge.textContent = "Подключено";
    }
  };

  const loadTbankStatus = async () => {
    showTbankMessage("");
    try {
      const status = await api("/api/broker/tbank", {method: "GET"});
      renderTbankStatus(status);
    } catch (error) {
      if (error.status === 401) {
        location.reload();
        return;
      }
      if (overviewAccount) {
        overviewAccount.textContent = "Недоступно";
      }
      if (overviewConnectionText) {
        overviewConnectionText.textContent = "Не удалось проверить T-Invest";
      }
      if (tbankStatusBadge) {
        tbankStatusBadge.textContent = "Ошибка";
      }
      showTbankMessage("Не удалось проверить подключение T-Invest.", true);
    }
  };

  const showProfile = (id) => {
    profileId.textContent = id;
    settingsProfileId.textContent = id;
    authCard.classList.add("hidden");
    profilePanel.classList.remove("hidden");
    setView(currentView);
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
      showMessage("Этот VK ID не имеет доступа к личному аккаунту OmniCIO.", true);
    } else if (authError === "provider") {
      showMessage("VK ID временно недоступен. Попробуйте позже.", true);
    } else if (authError === "account") {
      showMessage("Личный аккаунт OmniCIO заблокирован.", true);
    } else if (authError) {
      showMessage("Авторизация VK ID не завершена. Попробуйте ещё раз.", true);
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
        showMessage("Не удалось проверить сессию. Попробуйте обновить страницу.", true);
      }
    }

    showAuth();
    showCallbackResult();
    try {
      const config = await api("/api/auth/config", {method: "GET"});
      if (config.auth_provider !== "vkid" || !config.owner_login_enabled) {
        vkidLogin.disabled = true;
        showMessage(
          "VK ID ещё не настроен для этого личного аккаунта.",
          true,
        );
      }
    } catch {
      vkidLogin.disabled = true;
      showMessage("Сервис авторизации временно недоступен.", true);
    }
  };

  const enableDepthEffects = () => {
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
      return;
    }

    document.querySelectorAll(".interactive-depth").forEach((element) => {
      element.addEventListener("pointermove", (event) => {
        if (document.body.dataset.motion === "reduced") {
          return;
        }
        const rect = element.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;
        element.style.transform =
          `perspective(1100px) rotateX(${(-y * 3).toFixed(2)}deg) ` +
          `rotateY(${(x * 4).toFixed(2)}deg) translateY(-2px)`;
      });

      element.addEventListener("pointerleave", () => {
        element.style.transform = "";
      });
    });
  };

  navItems.forEach((item) => {
    item.addEventListener("click", () => setView(item.dataset.view));
  });

  viewLinks.forEach((item) => {
    item.addEventListener("click", () => setView(item.dataset.goView, {focus: true}));
  });

  appearanceQuick?.addEventListener("click", () => {
    setView("settings", {focus: true});
  });

  themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const preference = button.dataset.themeOption;
      storeValue(THEME_KEY, preference);
      applyTheme(preference);
    });
  });

  motionToggle?.addEventListener("change", () => {
    storeValue(MOTION_KEY, motionToggle.checked ? "full" : "reduced");
    applyMotion();
  });

  systemDark.addEventListener("change", () => {
    if (storedValue(THEME_KEY, "dark") === "auto") {
      applyTheme("auto");
    }
  });
  systemReducedMotion.addEventListener("change", applyMotion);

  vkidForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage("");

    const payload = {
      accept_privacy: document.querySelector("#accept-privacy").checked,
      accept_personal_data: document.querySelector("#accept-pd").checked,
      accept_terms: document.querySelector("#accept-terms").checked,
      confirm_age_18: document.querySelector("#confirm-age-18").checked,
    };
    if (!Object.values(payload).every(Boolean)) {
      showMessage("Подтвердите все пункты перед входом через VK ID.", true);
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
        showMessage("VK ID ещё не настроен или временно недоступен.", true);
      } else {
        showMessage("Не удалось начать авторизацию через VK ID.", true);
      }
    }
  });

  tbankForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showTbankMessage("");
    resetTbankPreview();

    const credential = tbankToken.value.trim();
    const environment = tbankEnvironment.value;
    if (credential.length < 20) {
      showTbankMessage("Вставьте полный API-токен T-Invest.", true);
      return;
    }
    if (!tbankTermsAck.checked) {
      showTbankMessage("Подтвердите правила и риски подключения T-Invest.", true);
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
        showTbankMessage("У токена нет доступных открытых счетов.", true);
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
      showTbankMessage("Токен проверен. Выберите счёт для подключения.");
    } catch (error) {
      resetTbankPreview();
      if (error.status === 400) {
        showTbankMessage("T-Invest отклонил токен. Проверьте его и попробуйте снова.", true);
      } else if (error.status === 503) {
        showTbankMessage("T-Invest API временно недоступен.", true);
      } else {
        showTbankMessage("Не удалось проверить токен.", true);
      }
    } finally {
      tbankCheck.disabled = false;
    }
  });

  tbankAccountForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showTbankMessage("");

    if (!pendingTbankCredential || !pendingTbankEnvironment || !tbankAccount.value) {
      showTbankMessage("Сначала заново проверьте API-токен.", true);
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
      showTbankMessage("T-Invest подключён. Токен сохранён в зашифрованном виде.");
    } catch (error) {
      resetTbankPreview();
      tbankForm.classList.remove("hidden");
      if (error.status === 400) {
        showTbankMessage("Не удалось подключить выбранный счёт. Проверьте токен.", true);
      } else if (error.status === 503) {
        showTbankMessage("T-Invest API временно недоступен.", true);
      } else {
        showTbankMessage("Подключение не сохранено.", true);
      }
    } finally {
      tbankConnect.disabled = false;
    }
  });

  tbankDisconnect.addEventListener("click", async () => {
    const confirmed = window.confirm(
      "Удалить сохранённый T-Invest токен из OmniCIO?"
    );
    if (!confirmed) {
      return;
    }

    tbankDisconnect.disabled = true;
    try {
      await api("/api/broker/tbank", {method: "DELETE"});
      renderTbankStatus({connected: false});
      tbankTermsAck.checked = false;
      showTbankMessage("Подключение удалено.");
    } catch {
      showTbankMessage("Не удалось удалить подключение.", true);
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

  const savedTheme = storedValue(THEME_KEY, "dark");
  applyTheme(["dark", "light", "auto"].includes(savedTheme) ? savedTheme : "dark");
  applyMotion();
  enableDepthEffects();
  void loadState();
})();
