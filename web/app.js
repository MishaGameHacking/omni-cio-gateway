(() => {
  "use strict";

  const phoneForm = document.querySelector("#phone-form");
  const codeForm = document.querySelector("#code-form");
  const authCard = document.querySelector("#auth-card");
  const profilePanel = document.querySelector("#profile-panel");
  const message = document.querySelector("#auth-message");
  const profileId = document.querySelector("#profile-id");
  const logoutButton = document.querySelector("#logout");

  const tbankForm = document.querySelector("#tbank-form");
  const tbankAccountForm = document.querySelector("#tbank-account-form");
  const tbankEnvironment = document.querySelector("#tbank-environment");
  const tbankToken = document.querySelector("#tbank-token");
  const tbankAccount = document.querySelector("#tbank-account");
  const tbankCheck = document.querySelector("#tbank-check");
  const tbankConnect = document.querySelector("#tbank-connect");
  const tbankConnected = document.querySelector("#tbank-connected");
  const tbankDisconnect = document.querySelector("#tbank-disconnect");
  const tbankAccountLabel = document.querySelector("#tbank-account-label");
  const tbankMessage = document.querySelector("#tbank-message");

  let challengeId = null;
  let pendingTbankCredential = null;
  let pendingTbankEnvironment = null;

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

  const resetTbankPreview = () => {
    pendingTbankCredential = null;
    pendingTbankEnvironment = null;
    tbankAccount.replaceChildren();
    tbankAccountForm.classList.add("hidden");
  };

  const renderTbankStatus = (status) => {
    resetTbankPreview();
    tbankToken.value = "";

    if (!status.connected) {
      tbankConnected.classList.add("hidden");
      tbankForm.classList.remove("hidden");
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
      showTbankMessage("Не удалось проверить подключение T-Invest.", true);
    }
  };

  const showProfile = (id) => {
    profileId.textContent = id;
    authCard.classList.add("hidden");
    profilePanel.classList.remove("hidden");
    void loadTbankStatus();
  };

  const showAuth = () => {
    profilePanel.classList.add("hidden");
    authCard.classList.remove("hidden");
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
    try {
      const config = await api("/api/auth/config", {method: "GET"});
      if (!config.owner_login_enabled) {
        phoneForm.querySelectorAll("input, button").forEach((element) => {
          element.disabled = true;
        });
        showMessage("Личный вход владельца временно недоступен.");
      }
    } catch {
      showMessage("Сервис авторизации временно недоступен.", true);
    }
  };

  phoneForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage("");

    const phone = document.querySelector("#phone").value.trim();
    const payload = {
      phone,
      accept_privacy: document.querySelector("#accept-privacy").checked,
      accept_personal_data: document.querySelector("#accept-pd").checked,
      accept_terms: document.querySelector("#accept-terms").checked,
      confirm_age_18: document.querySelector("#confirm-age-18").checked,
    };

    try {
      const result = await api("/api/auth/request-code", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      challengeId = result.challenge_id;
      phoneForm.classList.add("hidden");
      codeForm.classList.remove("hidden");
      document.querySelector("#code").focus();
      showMessage("Код отправлен. Введите 6 цифр из SMS.");
    } catch (error) {
      if (error.status === 403) {
        showMessage("Этот номер не имеет доступа к личному аккаунту.", true);
      } else if (error.status === 429) {
        showMessage("Слишком много попыток. Попробуйте позже.", true);
      } else if (error.status === 400) {
        showMessage("Введите номер строго в формате +79XXXXXXXXX.", true);
      } else {
        showMessage("Сейчас отправить код нельзя. Попробуйте позже.", true);
      }
    }
  });

  codeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const code = document.querySelector("#code").value.trim();
    if (!challengeId) {
      showMessage("Запросите новый код.", true);
      return;
    }

    try {
      const result = await api("/api/auth/verify", {
        method: "POST",
        body: JSON.stringify({challenge_id: challengeId, code}),
      });
      showProfile(result.public_id);
      showMessage("");
    } catch {
      showMessage("Код неверный, просрочен или уже использован.", true);
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

    tbankCheck.disabled = true;
    try {
      const result = await api("/api/broker/tbank/accounts", {
        method: "POST",
        body: JSON.stringify({credential, environment}),
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

  void loadState();
})();
