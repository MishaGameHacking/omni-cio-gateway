(() => {
  "use strict";

  const phoneForm = document.querySelector("#phone-form");
  const codeForm = document.querySelector("#code-form");
  const authCard = document.querySelector("#auth-card");
  const profilePanel = document.querySelector("#profile-panel");
  const message = document.querySelector("#auth-message");
  const profileId = document.querySelector("#profile-id");
  const logoutButton = document.querySelector("#logout");
  let challengeId = null;

  const showMessage = (text, isError = false) => {
    message.textContent = text;
    message.classList.toggle("error", isError);
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

  const showProfile = (id) => {
    profileId.textContent = id;
    authCard.classList.add("hidden");
    profilePanel.classList.remove("hidden");
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
      if (!config.registration_enabled) {
        phoneForm.querySelectorAll("input, button").forEach((element) => {
          element.disabled = true;
        });
        showMessage("Авторизация временно закрыта до завершения проверки SMS-провайдера.");
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
      if (error.status === 429) {
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

  logoutButton.addEventListener("click", async () => {
    try {
      await api("/api/auth/logout", {method: "POST"});
    } finally {
      location.reload();
    }
  });

  loadState();
})();
