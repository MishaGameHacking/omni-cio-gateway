/* Product workspace: local previews never acquire session or broker authority. */
(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const all = (selector) => [...document.querySelectorAll(selector)];
  const node = (tag, text, className = "") => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const icon = (name) => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("ui-icon");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS(svg.namespaceURI, "use");
    use.setAttribute("href", `#icon-${name}`);
    svg.append(use);
    return svg;
  };
  const money = (value, maximumFractionDigits = 0) => {
    const numeric = typeof value === "bigint" ? value : Number(value);
    if (value === null || (typeof numeric !== "bigint" && !Number.isFinite(numeric))) return "Не подтверждено";
    return new Intl.NumberFormat("ru-RU", {style: "currency", currency: "RUB", maximumFractionDigits}).format(numeric);
  };
  const decimalToKopecks = (value) => {
    const text = String(value).trim();
    if (!/^\d{1,12}(?:\.\d{1,2})?$/.test(text)) return null;
    const [units, fraction = ""] = text.split(".");
    return BigInt(units) * 100n + BigInt(fraction.padEnd(2, "0"));
  };
  const button = (label, action, primary = false) => {
    const element = node("button", label, `button button-${primary ? "primary" : "secondary"}`);
    element.type = "button";
    element.addEventListener("click", action);
    return element;
  };
  const empty = (container, title, detail) => {
    container.replaceChildren();
    const card = node("div", undefined, "empty-card");
    const mark = node("span", undefined, "empty-symbol");
    mark.append(icon("events"));
    card.append(mark, node("h3", title), node("p", detail));
    container.append(card);
    return card;
  };
  const download = (filename, data, type = "application/json") => {
    const url = URL.createObjectURL(new Blob([data], {type}));
    const link = node("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  // Integer percentages, largest remainder, with locked values preserved.
  const redistribute = (values, locked, index, requested) => {
    const result = [...values];
    if (locked.has(index)) return result;
    const others = values.map((_, i) => i).filter((i) => i !== index && !locked.has(i));
    const fixed = values.reduce((sum, value, i) => sum + (locked.has(i) ? value : 0), 0);
    result[index] = others.length ? Math.min(100 - fixed, Math.max(0, Math.round(requested))) : 100 - fixed;
    if (!others.length) return result;
    const remaining = 100 - fixed - result[index];
    const weight = others.reduce((sum, i) => sum + values[i], 0);
    const shares = others.map((i) => ({i, exact: weight ? remaining * values[i] / weight : remaining / others.length}));
    shares.forEach(({i, exact}) => { result[i] = Math.floor(exact); });
    const rest = 100 - result.reduce((sum, value) => sum + value, 0);
    shares.sort((a, b) => (b.exact % 1) - (a.exact % 1) || a.i - b.i);
    shares.slice(0, rest).forEach(({i}) => { result[i] += 1; });
    return result;
  };

  const initHelp = () => {
    const popover = node("div", undefined, "help-popover");
    popover.id = "workspace-help";
    popover.hidden = true;
    popover.style.maxHeight = "calc(100dvh - 32px)";
    popover.style.overflowY = "auto";
    const heading = node("h3", undefined, "help-title");
    heading.id = "workspace-help-title";
    const header = node("div", undefined, "help-header");
    const description = node("p", undefined, "help-summary");
    description.id = "workspace-help-text";
    const details = node("div", undefined, "help-details");
    details.tabIndex = 0;
    details.setAttribute("aria-label", "Подробное объяснение. Можно прокручивать.");
    const pinHint = node("p", "Нажмите значок i, чтобы закрепить справку и прочитать пример.", "help-pin-hint");
    const dismiss = button("Закрыть справку", () => close(true));
    dismiss.hidden = true;
    dismiss.classList.add("hidden");
    header.append(heading, dismiss);
    popover.append(header, description, pinHint, details);
    document.body.append(popover);
    let active = null;
    let pinned = false;
    let restoringFocus = false;
    let hovering = null;
    let gesture = null;
    let suppressedClick = null;
    let hoverTimer;
    let leaveTimer;
    let holdTimer;

    const clearTimers = () => {
      clearTimeout(hoverTimer);
      clearTimeout(leaveTimer);
      clearTimeout(holdTimer);
    };
    const unbind = () => {
      active?.removeAttribute("aria-describedby");
      active?.removeAttribute("aria-controls");
      active?.removeAttribute("aria-expanded");
    };
    const canRestoreFocus = (trigger, view) => trigger?.isConnected && !trigger.disabled
      && !trigger.closest("[hidden], .hidden, [inert]") && trigger.getClientRects().length > 0
      && getComputedStyle(trigger).visibility === "visible"
      && (view === null || trigger.closest("[data-view-panel]")?.dataset.viewPanel === view);
    const close = (restoreFocus = false, view = null) => {
      const focused = document.activeElement;
      const focusInside = popover.contains(focused);
      clearTimers();
      hovering = null;
      if (gesture) suppressedClick = {trigger: gesture.trigger, id: gesture.id};
      gesture = null;
      const trigger = active;
      unbind();
      active = null;
      pinned = false;
      popover.hidden = true;
      dismiss.hidden = true;
      dismiss.classList.add("hidden");
      // Capture focus before hiding: the browser may already have moved it to body.
      if ((restoreFocus || focusInside) && canRestoreFocus(trigger, view)) {
        restoringFocus = true;
        trigger.focus({preventScroll: true});
        restoringFocus = false;
      } else if (focusInside) focused.blur();
    };
    const position = () => {
      const rect = active.getBoundingClientRect();
      const above = rect.top - popover.offsetHeight - 8;
      const top = above >= 16 ? above : rect.bottom + 8;
      popover.style.left = `${Math.max(16, Math.min(innerWidth - popover.offsetWidth - 16, rect.left))}px`;
      popover.style.top = `${Math.max(16, Math.min(innerHeight - popover.offsetHeight - 16, top))}px`;
    };
    const show = (trigger, text, pin = false) => {
      clearTimeout(hoverTimer);
      clearTimeout(leaveTimer);
      unbind();
      active = trigger;
      // A native modal makes body siblings inert. Keep this one help engine in its top layer.
      const host = trigger.closest("dialog[open]") || document.body;
      if (popover.parentElement !== host) host.append(popover);
      pinned = pin;
      // Rich copy is resolved at opening, so the value and state cannot go stale between visits.
      const content = typeof text === "function" ? text() : text;
      const rich = typeof content === "object" && content !== null;
      const sections = rich && Array.isArray(content.sections) ? content.sections : [];
      heading.textContent = trigger.getAttribute("aria-label").replace(/^Справка: /, "");
      description.textContent = rich ? content.summary : content;
      details.replaceChildren();
      const addSection = (title, body) => {
        const section = node("section", undefined, "help-section");
        section.append(node("h4", title), node("p", body));
        details.append(section);
      };
      if (pin && rich) {
        if (content.current) addSection("Выбрано сейчас", content.current);
        sections.forEach(([title, body]) => addSection(title, body));
      }
      details.hidden = !pin || !rich;
      pinHint.hidden = pin || !rich;
      popover.classList.toggle("help-expanded", pin && rich);
      popover.scrollTop = 0;
      popover.setAttribute("aria-labelledby", heading.id);
      trigger.setAttribute("aria-describedby", description.id);
      popover.setAttribute("role", pin ? "dialog" : "tooltip");
      popover.setAttribute("aria-label", trigger.getAttribute("aria-label"));
      dismiss.hidden = !pin;
      dismiss.classList.toggle("hidden", !pin);
      if (pin) {
        trigger.setAttribute("aria-controls", popover.id);
        trigger.setAttribute("aria-expanded", "true");
      }
      popover.hidden = false;
      position();
    };
    const scheduleClose = () => {
      clearTimeout(leaveTimer);
      leaveTimer = setTimeout(() => {
        if (!pinned && active !== document.activeElement && hovering !== active && !popover.matches(":hover")) close();
      }, 150);
    };
    const beginGesture = (event, trigger, text) => {
      if (!event.isPrimary || event.button !== 0) return;
      clearTimers();
      suppressedClick = null;
      gesture = {trigger, id: event.pointerId, x: event.clientX, y: event.clientY, held: false};
      if (event.pointerType === "mouse" || (active === trigger && pinned)) return;
      holdTimer = setTimeout(() => {
        if (!gesture || document.hidden) return;
        gesture.held = true;
        show(trigger, text);
      }, 300);
    };
    const finishGesture = (event) => {
      if (gesture?.id !== event.pointerId) return;
      clearTimeout(holdTimer);
      const held = gesture.held;
      const trigger = gesture.trigger;
      if (held || event.type === "pointercancel") suppressedClick = {trigger, id: gesture.id};
      gesture = null;
      if (!pinned && active === trigger && (held || event.type === "pointercancel")) close();
    };
    const pinOrClose = (event, trigger, text) => {
      const suppressed = suppressedClick;
      suppressedClick = null;
      if (event.detail !== 0 && suppressed?.trigger === trigger
        && (event.pointerId === undefined || event.pointerId === suppressed.id)) return;
      clearTimers();
      gesture = null;
      if (active === trigger && pinned) close();
      else {
        show(trigger, text, true);
        if (event.detail === 0) dismiss.focus({preventScroll: true});
      }
    };
    const attach = (targetOrSelector, title, text) => {
      const target = typeof targetOrSelector === "string" ? $(targetOrSelector) : targetOrSelector;
      if (!target) return;
      if (target.querySelector(":scope > .help-trigger")) return;
      const trigger = node("button", undefined, "help-trigger");
      trigger.append(icon("info"));
      trigger.type = "button";
      trigger.setAttribute("aria-label", title);
      target.append(trigger);
      trigger.addEventListener("focus", () => {
        if (!restoringFocus && gesture?.trigger !== trigger && suppressedClick?.trigger !== trigger
          && !(active === trigger && pinned)) show(trigger, text);
      });
      trigger.addEventListener("blur", scheduleClose);
      trigger.addEventListener("pointerenter", (event) => {
        if (event.pointerType !== "mouse") return;
        hovering = trigger;
        clearTimeout(leaveTimer);
        clearTimeout(hoverTimer);
        if (pinned || active === trigger) return;
        hoverTimer = setTimeout(() => { if (!document.hidden) show(trigger, text); }, 350);
      });
      trigger.addEventListener("pointerleave", (event) => {
        if (event.pointerType !== "mouse") return;
        hovering = null;
        clearTimeout(hoverTimer);
        scheduleClose();
      });
      trigger.addEventListener("pointerdown", (event) => beginGesture(event, trigger, text));
      trigger.addEventListener("click", (event) => {
        event.stopPropagation();
        pinOrClose(event, trigger, text);
      });
      trigger.addEventListener("contextmenu", (event) => {
        if ((gesture?.trigger === trigger && gesture.held) || suppressedClick?.trigger === trigger) event.preventDefault();
      });
    };
    attach(".command-kpi-primary > span", "Как рассчитана стоимость портфеля", "Сумма активов и денег по последнему снимку брокера. Это оценка: при продаже итог зависит от цены исполнения и издержек.");
    attach(".command-kpi:nth-child(2) > span", "Что означает изменение за день", "Изменение стоимости за день по данным брокера. Пополнения и выплаты могут влиять на капитал; это не обещание доходности.");
    attach(".command-kpi:nth-child(3) > span", "Какие рубли считаются свободными", "Незаблокированные рубли на счёте. Перед расчётом торгового бюджета отдельно учитываются резерв, заявки, комиссии и НКД.");
    popover.addEventListener("pointerenter", () => clearTimeout(leaveTimer));
    popover.addEventListener("pointerleave", scheduleClose);
    document.addEventListener("pointerdown", (event) => {
      suppressedClick = null;
      if (!active?.contains(event.target) && !popover.contains(event.target)) close();
    }, true);
    document.addEventListener("pointermove", (event) => {
      if (gesture?.id === event.pointerId && Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) > 10) close();
    }, {passive: true});
    for (const name of ["pointerup", "pointercancel"]) document.addEventListener(name, finishGesture);
    document.addEventListener("keydown", (event) => {
      suppressedClick = null;
      if (event.key !== "Escape") return;
      const visible = !popover.hidden;
      close(visible && popover.contains(document.activeElement));
      if (visible) { event.preventDefault(); event.stopPropagation(); }
    }, true);
    document.addEventListener("scroll", (event) => {
      if (popover.contains(event.target)) return;
      // Browser focus scrolling must not dismiss a keyboard user's explanation.
      if (active && !pinned && !gesture && active === document.activeElement) position();
      else close();
    }, true);
    document.addEventListener("visibilitychange", () => { if (document.hidden) close(); });
    window.addEventListener("pagehide", () => close());
    window.addEventListener("resize", () => close());
    return {close, attach};
  };

  window.OmniWorkspace = {init(adapter) {
    let demo = false;
    let sessionStarted = false;
    let snapshot = null;
    let catalog = [];
    let assetFilter = "all";
    let eventFilter = "all";
    let events = [];
    let payouts = [];
    let calendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
    const favorites = new Set();
    const comparison = new Map();
    const goals = [];
    const labels = ["Акции", "Облигации", "Фонды", "Денежный резерв"];
    const keys = ["shares", "bonds", "funds", "cash"];
    const colors = ["#245eea", "#259c87", "#a487d0", "#c5cfdf"];
    const initialAllocation = [20, 60, 10, 10];
    let allocation = [...initialAllocation];
    const locked = new Set();
    const excluded = new Set();
    const dialog = $("#workspace-dialog");
    const dialogBody = $("#dialog-content");
    let previousFocus = null;
    let toastTimer;
    let waitingWorker = null;
    let updateRequested = false;
    let allocationExported = JSON.stringify(initialAllocation);
    let goalsExported = "[]";
    let notificationsDirty = false;

    const toast = (text) => {
      const target = $("#workspace-toast");
      target.textContent = text;
      target.classList.remove("hidden");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => target.classList.add("hidden"), 5000);
    };
    const showDialog = (title) => {
      help.close(false);
      if (!dialog.open) previousFocus = document.activeElement;
      $("#dialog-title").textContent = title;
      dialogBody.replaceChildren();
      if (!dialog.open) dialog.showModal();
      return dialogBody;
    };
    $("#dialog-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
      help.close(false);
      if (previousFocus?.isConnected && !previousFocus.closest(".hidden, [hidden], [inert]")
          && previousFocus.getClientRects().length) previousFocus.focus({preventScroll: true});
    });
    dialog.addEventListener("click", (event) => {
      if (event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
    });

    const markPrivate = () => {
      const selectors = [
        ".command-kpi > strong", ".portfolio-metric > strong", ".portfolio-metric > small",
        ".allocation-list", ".cash-list", ".portfolio-chart-facts", ".positions-table",
        ".positions-mobile", ".position-card", ".analysis-sources", ".analysis-observation",
        ".metric-strip strong", ".goal-value", ".event-card p", ".event-card h3",
        ".attention-list", ".goal-card p", ".instrument-detail", ".market-price-row",
        ".chart-inspector[data-private]", "#home-portfolio-history-chart", "#portfolio-history-chart", "#portfolio-drawdown-chart",
      ];
      all(selectors.join(",")).forEach((element) => { element.dataset.private = ""; });
    };
    $("#privacy-toggle").addEventListener("click", () => {
      const hidden = document.body.classList.toggle("privacy-mode");
      $("#privacy-toggle").setAttribute("aria-pressed", String(hidden));
      $("#privacy-toggle").setAttribute("aria-label", hidden ? "Показать суммы" : "Скрыть суммы");
      try { localStorage.setItem("omnicio_hide_amounts", String(hidden)); } catch { /* Optional visual preference. */ }
    });
    try {
      if (localStorage.getItem("omnicio_hide_amounts") === "true") $("#privacy-toggle").click();
    } catch { /* Private browsing can disable storage. */ }
    $("#quick-theme").addEventListener("click", () => adapter.theme(document.body.dataset.theme === "dark" ? "light" : "dark"));
    document.addEventListener("keydown", (event) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "k") return;
      if (event.target.closest("input, textarea, select, [contenteditable=true]") || dialog.open || $("#profile-panel").classList.contains("hidden")) return;
      event.preventDefault();
      adapter.navigate("assets");
      $("#hunter-query").focus();
    });

    all("[data-auth-mode]").forEach((tab) => tab.addEventListener("click", () => {
      const register = tab.dataset.authMode === "register";
      all("[data-auth-mode]").forEach((item) => item.setAttribute("aria-pressed", String(item === tab)));
      $("#login-title").textContent = register ? "Создать личный кабинет" : "С возвращением";
      $("#vkid-login").textContent = register ? "Зарегистрироваться через VK ID" : "Войти через VK ID";
      $("#auth-message").textContent = register
        ? "Регистрация проходит через VK ID. Доступность нового аккаунта проверит сервер; при заполненном лимите аккаунт не создаётся."
        : "";
    }));

    const renderEvents = () => {
      const feed = $("#events-feed");
      feed.replaceChildren();
      const visible = events.filter((item) => eventFilter === "all" || item.kind === eventFilter);
      if (!visible.length) {
        empty(feed, eventFilter === "all" ? "Пока нет подтверждённых событий" : "Нет событий этого типа", "После обновления источников здесь появятся важные изменения. Отсутствие событий не подтверждает отсутствие риска.");
        return;
      }
      visible.forEach((item) => {
        const card = node("article", undefined, "event-card");
        card.dataset.kind = item.kind;
        const mark = node("span", undefined, "event-icon");
        mark.append(icon(item.kind === "income" ? "calendar" : "events"));
        const body = node("div");
        const category = {risk: "Требует внимания", income: "Выплаты", system: "Сервис"}[item.kind] || "Сервис";
        body.append(node("span", category, "card-label"), node("h3", item.title), node("p", item.detail));
        if (item.time) {
          const time = node("time", new Date(item.time).toLocaleString("ru-RU"));
          time.dateTime = item.time;
          body.append(time);
        }
        if (item.view) body.append(button("Открыть разбор", () => adapter.navigate(item.view)));
        card.append(mark, body);
        feed.append(card);
      });
      markPrivate();
    };
    all("[data-event-filter]").forEach((chip) => chip.addEventListener("click", () => {
      eventFilter = chip.dataset.eventFilter;
      all("[data-event-filter]").forEach((item) => item.setAttribute("aria-pressed", String(item === chip)));
      renderEvents();
    }));
    $("#events-refresh").addEventListener("click", () => {
      if (demo) toast("Показаны демонстрационные события. Источники не запрашиваются.");
      else adapter.refreshAnalysis();
    });

    const renderAllocation = () => {
      let accumulated = 0;
      const stops = allocation.map((value, index) => {
        const start = accumulated;
        accumulated += value;
        return `${colors[index]} ${start}% ${accumulated}%`;
      });
      $("#strategy-donut").style.background = `conic-gradient(${stops.join(",")})`;
      $("#strategy-donut").setAttribute("aria-label", allocation.map((value, i) => `${labels[i]} ${value}%`).join(", "));
      $("#allocation-legend").replaceChildren();
      keys.forEach((key, i) => {
        const range = $(`[data-target-range="${key}"]`);
        const input = $(`[data-target-number="${key}"]`);
        range.value = String(allocation[i]);
        range.style.setProperty("--range-progress", `${allocation[i]}%`);
        input.value = String(allocation[i]);
        range.disabled = locked.has(i) || excluded.has(i);
        input.disabled = locked.has(i) || excluded.has(i);
        $(`[data-lock="${key}"]`).disabled = excluded.has(i);
        $(`[data-allow="${key}"]`).checked = !excluded.has(i);
        const lock = $(`[data-lock="${key}"]`);
        lock.setAttribute("aria-pressed", String(locked.has(i)));
        lock.setAttribute("aria-label", `${locked.has(i) ? "Разблокировать" : "Закрепить"} долю: ${labels[i]}`);
        const lockText = lock.querySelector(".allocation-lock-text");
        if (lockText) lockText.textContent = locked.has(i) ? "Закреплено" : "Свободно";
        let explanation = "Остаток распределяется автоматически";
        if (locked.has(i)) explanation = "Доля закреплена";
        if (excluded.has(i)) explanation = "Класс выключен";
        range.setAttribute("aria-valuetext", `${allocation[i]} процентов. ${explanation}`);
        all(`[data-allocation-step="${key}"]`).forEach((step) => {
          step.disabled = input.disabled || (step.dataset.direction === "-1" ? allocation[i] === 0 : allocation[i] === 100);
        });
        const row = node("div", undefined, "legend-row");
        const dot = node("i");
        dot.style.backgroundColor = colors[i];
        row.append(dot, node("span", labels[i]), node("strong", `${allocation[i]}%`));
        $("#allocation-legend").append(row);
      });
    };
    keys.forEach((key, index) => {
      for (const selector of [`[data-target-range="${key}"]`, `[data-target-number="${key}"]`]) {
        $(selector).addEventListener("input", (event) => {
          if (event.target.value === "") return;
          const value = Number(event.target.value);
          if (!Number.isFinite(value)) return;
          allocation = redistribute(allocation, new Set([...locked, ...excluded]), index, value);
          renderAllocation();
          document.dispatchEvent(new Event("strategy:allocation"));
          $("#allocation-status").textContent = "Распределено 100%. Черновик изменён; сделки и сохранённые лимиты не менялись.";
        });
      }
      $(`[data-lock="${key}"]`).addEventListener("click", () => {
        if (locked.has(index)) locked.delete(index); else locked.add(index);
        renderAllocation();
        document.dispatchEvent(new Event("strategy:allocation"));
      });
      $(`[data-allow="${key}"]`).addEventListener("change", (event) => {
        if (event.target.checked) excluded.delete(index);
        else {
          const available = keys.some((_, i) => i !== index && !excluded.has(i) && !locked.has(i));
          if (!available) { event.target.checked = true; toast("Оставьте хотя бы один доступный класс без замка для перераспределения."); return; }
          locked.delete(index);
          allocation = redistribute(allocation, new Set([...locked, ...excluded]), index, 0);
          excluded.add(index);
        }
        renderAllocation();
        document.dispatchEvent(new Event("strategy:allocation"));
        $("#allocation-status").textContent = "Разрешённые классы изменены только в черновике. Сумма долей — 100%.";
      });
    });
    all("[data-preset]").forEach((item) => item.addEventListener("click", () => {
      if (locked.size || excluded.size) { toast("Разрешите все классы и снимите замки, чтобы применить пример целиком."); return; }
      allocation = [...{income: [10, 70, 10, 10], growth: [55, 25, 10, 10], balanced: [30, 50, 10, 10]}[item.dataset.preset]];
      renderAllocation();
      $("#allocation-status").textContent = "Пример добавлен в черновик. Проверьте каждую долю; это не персональная рекомендация.";
    }));
    $("#reset-allocation").addEventListener("click", () => {
      allocation = [...initialAllocation];
      locked.clear();
      excluded.clear();
      renderAllocation();
      document.dispatchEvent(new Event("strategy:allocation"));
      $("#allocation-status").textContent = "Начальные доли восстановлены в черновике. Подтверждённые параметры не изменялись.";
    });
    $("#review-allocation").addEventListener("click", () => {
      const body = showDialog("Изменения в черновике");
      body.append(node("p", "Сравнение с начальным примером. Верхние лимиты профиля, торговые планы и поручения брокеру не меняются.", "muted"));
      const table = node("table", undefined, "diff-table");
      table.innerHTML = "<thead><tr><th>Класс</th><th>Начальный пример</th><th>Черновик</th></tr></thead><tbody></tbody>";
      labels.forEach((label, i) => {
        const row = node("tr");
        row.append(node("td", label), node("td", `${initialAllocation[i]}%`), node("td", `${allocation[i]}%`));
        table.tBodies[0].append(row);
      });
      const actions = node("div", undefined, "dialog-actions");
      actions.append(button("Продолжить редактирование", () => dialog.close()), button("Скачать черновик", () => {
        download("omnicio-strategy-draft.json", JSON.stringify({kind: "allocation_draft", version: 1, created_at: new Date().toISOString(), targets: Object.fromEntries(keys.map((key, i) => [key, allocation[i]])), allowed_classes: keys.filter((_, i) => !excluded.has(i)), applied: false}, null, 2));
        allocationExported = JSON.stringify(allocation);
        toast("Черновик скачан. Серверная стратегия не менялась.");
      }, true));
      body.append(table, actions);
    });

    const renderComparisonTray = () => {
      $("#comparison-tray").classList.toggle("hidden", comparison.size === 0);
      $("#comparison-count").textContent = `Для сравнения: ${comparison.size} из 3`;
      $("#compare-assets").disabled = comparison.size < 2;
    };
    const filterAssets = (items) => items.filter((item) => assetFilter === "all"
      || (assetFilter === "favorites" ? favorites.has(item.uid) : item.instrument_type === assetFilter));
    const decorateAssets = (items) => {
      all("#hunter-results .hunter-result").forEach((card, index) => {
        const item = items[index];
        if (!item?.uid) return;
        const flags = card.querySelector(".hunter-result-flags");
        const state = node("span", "Доступность покупки не проверена", "state-badge state-next");
        flags.replaceChildren(state);
        const actions = node("div", undefined, "asset-actions");
        actions.append(button("Подробнее", () => {
          if (demo) toast("Для данных инструмента нужен вход и подключение собственного счёта.");
          else { adapter.navigate("portfolio"); adapter.openInstrument(item.uid); }
        }));
        const favorite = button(favorites.has(item.uid) ? "★ В избранном" : "☆ В избранное", () => {
          if (favorites.has(item.uid)) favorites.delete(item.uid); else favorites.add(item.uid);
          adapter.renderAssets(catalog);
        });
        favorite.setAttribute("aria-pressed", String(favorites.has(item.uid)));
        const compare = button(comparison.has(item.uid) ? "Убрать из сравнения" : "Сравнить", () => {
          if (comparison.has(item.uid)) comparison.delete(item.uid);
          else if (comparison.size < 3) comparison.set(item.uid, item);
          else { toast("Сравнивайте до трёх инструментов одновременно."); return; }
          adapter.renderAssets(catalog);
          renderComparisonTray();
        });
        actions.append(favorite, compare);
        card.append(actions);
      });
    };
    all("[data-asset-filter]").forEach((chip) => chip.addEventListener("click", () => {
      assetFilter = chip.dataset.assetFilter;
      all("[data-asset-filter]").forEach((item) => item.setAttribute("aria-pressed", String(item === chip)));
      adapter.renderAssets(catalog);
    }));
    $("#clear-comparison").addEventListener("click", () => {
      comparison.clear();
      renderComparisonTray();
      adapter.renderAssets(catalog);
    });
    $("#compare-assets").addEventListener("click", () => {
      const body = showDialog("Сравнение инструментов");
      const table = node("table", undefined, "diff-table");
      for (const [label, key] of [["Инструмент", "name"], ["Тикер", "ticker"], ["Класс", "instrument_type"], ["Лот, бумаг", "lot"]]) {
        const row = node("tr");
        row.append(node("th", label));
        comparison.forEach((item) => {
          const value = key === "instrument_type"
            ? ({share: "Акция", bond: "Облигация", etf: "Фонд"}[item[key]] || item[key])
            : String(item[key] ?? "Не подтверждено");
          row.append(node("td", value));
        });
        table.append(row);
      }
      body.append(table, node("p", "Цена, доходность и право покупки требуют отдельного подтверждения брокером. Отсутствующие данные не заменяются оценкой.", "inline-note"));
    });

    const eventDate = (item) => item.actual_at || item.expected_at;
    const monthPayouts = () => payouts.filter((item) => {
      const date = new Date(eventDate(item));
      return date.getFullYear() === calendarMonth.getFullYear() && date.getMonth() === calendarMonth.getMonth();
    });
    const payoutTotal = (items) => {
      if (!items.length) return "Не подтверждено";
      // Provider amounts can be per security; never label their sum as account income.
      if (!demo) return "Не подтверждено";
      const amounts = items.map((item) => item.currency?.toUpperCase() === "RUB" ? decimalToKopecks(item.amount) : null);
      if (amounts.includes(null)) return "Не подтверждено";
      return money(Number(amounts.reduce((sum, value) => sum + value, 0n)) / 100);
    };
    const renderCalendar = () => {
      $("#payout-month").textContent = calendarMonth.toLocaleDateString("ru-RU", {month: "long", year: "numeric"});
      const selected = monthPayouts();
      const income = selected.filter((item) => ["coupon", "dividend"].includes(item.event_type));
      $("#payout-announced").textContent = payoutTotal(income.filter((item) => ["announced", "confirmed", "paid", "broker_confirmed"].includes(item.status)));
      $("#payout-estimated").textContent = payoutTotal(income.filter((item) => !["announced", "confirmed", "paid", "broker_confirmed"].includes(item.status)));
      $("#payout-principal").textContent = payoutTotal(selected.filter((item) => ["redemption", "amortization"].includes(item.event_type)));
      const calendar = $("#payout-calendar");
      calendar.replaceChildren();
      const offset = (calendarMonth.getDay() + 6) % 7;
      const last = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + 1, 0).getDate();
      for (let cell = 0; cell < Math.ceil((offset + last) / 7) * 7; cell += 1) {
        const day = cell - offset + 1;
        const control = node("button", day > 0 && day <= last ? String(day) : "", "calendar-day");
        control.type = "button";
        control.disabled = day < 1 || day > last;
        if (!control.disabled) {
          const date = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), day);
          const items = selected.filter((item) => new Date(eventDate(item)).getDate() === day);
          control.classList.toggle("is-today", date.toDateString() === new Date().toDateString());
          control.classList.toggle("has-payout", items.length > 0);
          const countLabel = items.length ? String(items.length) + " выплат" : "нет подтверждённых выплат";
          control.setAttribute("aria-label", `${date.toLocaleDateString("ru-RU")}: ${countLabel}`);
          if (items.length) control.append(node("small", `${items.length} выплат`));
          control.addEventListener("click", () => {
            const body = showDialog(date.toLocaleDateString("ru-RU", {day: "numeric", month: "long", year: "numeric"}));
            if (!items.length) body.append(node("p", "На эту дату в полученных данных нет выплат. Это не подтверждает отсутствие будущих начислений.", "muted"));
            items.forEach((item) => {
              const row = node("div", undefined, "settings-card");
              row.append(node("h3", item.name || item.instrument_uid), node("p", ({coupon: "Купон", dividend: "Дивиденд", redemption: "Возврат номинала", amortization: "Амортизация"}[item.event_type] || "Событие облигации")));
              const amount = node("strong", item.currency?.toUpperCase() === "RUB" ? money(item.amount, 2) : `${item.amount ?? "—"} ${item.currency || ""}`);
              amount.dataset.private = "";
              const state = {announced: "объявлено", scheduled: "запланировано", cancelled: "отменено", paid: "выплачено по данным источника", defaulted: "не исполнено", observed: "наблюдается"}[item.status] || "требует подтверждения";
              row.append(amount, node("p", `Статус: ${state}. Дата выплаты не подтверждает зачисление денег.`, "field-hint"));
              if (!demo) row.append(node("p", "Сумма события из источника может относиться к одной бумаге. Выплата именно по вашему счёту и право на неё отдельно не подтверждены.", "inline-note"));
              body.append(row);
            });
          });
        }
        calendar.append(control);
      }
      markPrivate();
    };
    for (const [id, offset] of [["payout-prev", -1], ["payout-next", 1]]) $("#" + id).addEventListener("click", () => {
      calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + offset, 1);
      renderCalendar();
    });
    $("#payout-today").addEventListener("click", () => {
      calendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
      renderCalendar();
    });

    const deleteGoal = (index) => {
      const body = showDialog("Удалить сценарий?");
      body.append(node("p", goals[index].name), button("Удалить сценарий", () => {
        goals.splice(index, 1);
        renderGoals();
        dialog.close();
      }, true));
    };
    const renderGoals = () => {
      const list = $("#goals-list");
      list.replaceChildren();
      if (!goals.length) {
        const card = empty(list, "Для чего растёт ваш капитал?", "Создайте сценарий цели: сумма, дата и регулярные пополнения. Без выдуманного процента доходности.");
        card.append(button("Создать первую цель", () => editGoal(), true));
      }
      goals.forEach((goal, index) => {
        const card = node("article", undefined, "goal-card");
        const initial = decimalToKopecks(goal.initial);
        const target = decimalToKopecks(goal.target);
        const monthly = decimalToKopecks(goal.monthly);
        const months = Math.max(0, Math.ceil((new Date(goal.date) - Date.now()) / (30.4375 * 86400000)));
        const projected = initial + monthly * BigInt(months);
        const remaining = target > projected ? target - projected : 0n;
        const percent = target > 0n ? Math.min(100, Number(initial * 100n / target)) : 0;
        const progress = node("div", undefined, "goal-progress");
        const bar = node("span");
        bar.style.width = `${percent}%`;
        progress.setAttribute("role", "progressbar");
        progress.setAttribute("aria-label", goal.name);
        progress.setAttribute("aria-valuenow", String(percent));
        progress.setAttribute("aria-valuemin", "0");
        progress.setAttribute("aria-valuemax", "100");
        progress.append(bar);
        card.append(node("span", "СЦЕНАРИЙ · В ТЕКУЩЕЙ ВКЛАДКЕ", "card-label"), node("h3", goal.name), node("strong", money(goal.target), "goal-value"), progress, node("p", `${percent}% · начальная сумма ${money(goal.initial)}`), node("p", `К ${new Date(goal.date + "T12:00:00").toLocaleDateString("ru-RU")}: ${money(projected / 100n)} при пополнении ${money(goal.monthly)} в месяц. Доходность и инфляция не включены.`));
        card.append(node("p", remaining > 0n ? `До цели не хватает ${money(remaining / 100n)}. Измените срок или пополнения.` : "Плановые пополнения покрывают номинальную цель. Это сценарий, не гарантия.", "inline-note"));
        const actions = node("div", undefined, "goal-actions");
        actions.append(button("Изменить", () => editGoal(index)), button("Скачать все цели", () => {
          download("omnicio-goals.json", JSON.stringify({kind: "goal_scenarios", goals, linked_to_portfolio: false}, null, 2));
          goalsExported = JSON.stringify(goals);
        }), button("Удалить", () => deleteGoal(index)));
        card.append(actions);
        list.append(card);
      });
      markPrivate();
    };
    const editGoal = (index = null) => {
      const body = showDialog(index === null ? "Новая цель капитала" : "Изменить цель");
      const form = node("form", undefined, "form-stack");
      form.innerHTML = '<label class="field">Название<input name="name" maxlength="80" placeholder="Например, финансовая подушка" required></label><div class="constraint-form-grid"><label class="field">Целевая сумма, ₽<input name="target" type="number" min="1" max="999999999999.99" step="0.01" inputmode="decimal" required></label><label class="field">Желаемая дата<input name="date" type="date" required></label><label class="field">Начальная сумма, ₽<input name="initial" type="number" min="0" max="999999999999.99" step="0.01" value="0" required></label><label class="field">Пополнение в месяц, ₽<input name="monthly" type="number" min="0" max="999999999999.99" step="0.01" value="0" required></label></div><p class="inline-note">Номинальная цель в рублях. Средства не резервируются и не связываются с портфелем. Сценарий останется в этой вкладке; скачайте его для сохранения.</p><button class="button button-primary" type="submit">Сохранить сценарий в этой вкладке</button><output class="message" aria-live="polite"></output>';
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      form.elements.date.min = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2,"0")}-${String(tomorrow.getDate()).padStart(2,"0")}`;
      if (index !== null) Object.entries(goals[index]).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].value = value; });
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const goal = Object.fromEntries(new FormData(form));
        goal.name = goal.name.trim();
        if (!goal.name || ["target", "initial", "monthly"].some((key) => decimalToKopecks(goal[key]) === null)) {
          form.querySelector("output").textContent = "Введите название и суммы с точностью до копеек.";
          return;
        }
        if (index === null) goals.push(goal); else goals[index] = goal;
        renderGoals();
        dialog.close();
      });
      body.append(form);
      form.elements.name.focus();
    };
    $("#create-goal").addEventListener("click", () => editGoal());

    all("[data-prompt]").forEach((item) => item.addEventListener("click", () => {
      $("#assistant-input").value = item.dataset.prompt;
      $("#assistant-input").focus();
    }));
    $("#assistant-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const text = $("#assistant-input").value.trim();
      $("#assistant-message").textContent = text
        ? "Черновик оставлен в этой вкладке. Qwen пока не подключён: сообщение не отправлено, ответ не сгенерирован."
        : "Напишите вопрос, чтобы оставить черновик.";
    });
    $("#assistant-context").addEventListener("change", () => {
      $("#assistant-context-label").textContent = $("#assistant-context").value === "portfolio"
        ? "Контекст портфеля выбран, но не отправлен" : "Без данных портфеля";
    });
    $("#new-chat").addEventListener("click", () => {
      if ($("#assistant-input").value.trim()) {
        const body = showDialog("Очистить черновик разговора?");
        body.append(node("p", "Этот черновик ещё не отправлен ассистенту."), button("Очистить", () => {
          $("#assistant-input").value = "";
          $("#assistant-message").textContent = "";
          dialog.close();
        }, true));
      } else $("#assistant-input").focus();
    });
    $("#assistant-memory").addEventListener("click", () => {
      showDialog("Память ассистента").append(node("p", "Сохранённых воспоминаний нет. После подключения ассистента вы сможете просмотреть точный текст перед сохранением и удалить отдельную запись.", "inline-note"));
    });
    $("#notifications-form").addEventListener("input", () => { notificationsDirty = true; });
    $("#notifications-form").addEventListener("submit", (event) => {
      event.preventDefault();
      download("omnicio-notifications-draft.json", JSON.stringify({kind: "notification_draft", active: false, digest_time: $("#digest-time").value, time_zone: $("#digest-zone").value, quiet_hours: [$("#quiet-start").value, $("#quiet-end").value], max_daily_push: 3, security: $("#notify-security").checked, income: $("#notify-income").checked, critical_at_night: $("#notify-night").checked, lock_screen_amounts: $("#notify-amounts").checked}, null, 2));
      $("#notifications-message").textContent = "Настройки скачаны. Доставка уведомлений ещё не включена.";
      notificationsDirty = false;
    });

    const onboarding = (step = 1) => {
      const body = showDialog("Настроим ваш кабинет");
      body.append(node("p", `Шаг ${step} из 5`, "card-label"));
      const progress = node("div", undefined, "step-progress");
      for (let i = 1; i <= 5; i += 1) progress.append(node("span", "", i <= step ? "active" : ""));
      body.append(progress);
      const steps = [
        ["Личный аккаунт", demo ? "Сейчас открыт обзор без аккаунта. Для своего портфеля нужен вход через VK ID." : "Вы вошли через VK ID. Подключение брокера и согласие на торговые действия проверяются отдельно.", "profile"],
        ["Выберите, с чего начать", "Посмотрите официальные справочные данные без входа или подключите собственный счёт после авторизации.", "connections"],
        ["Подключите T-Invest", "Создайте токен только для чтения и введите его в разделе подключений. Сервер проверит токен и покажет ваши счета.", "connections"],
        ["Расскажите о предпочтениях", "Укажите резерв, срок и допустимые колебания. Если пока не знаете, пропустите: доступ к аналитике сохранится.", "strategy"],
        ["Ваш первый обзор", "Откройте портфель: проверьте стоимость, состав и время данных. Уведомления можно настроить позже.", "portfolio"],
      ];
      const [title, text, view] = steps[step - 1];
      body.append(node("h3", title), node("p", text, "muted"));
      const options = node("div", undefined, "onboarding-options");
      options.append(button(({profile: "Открыть профиль", connections: "Подключить свой счёт", strategy: "Настроить предпочтения", portfolio: "Открыть портфель"})[view], () => { dialog.close(); adapter.navigate(view); }, true));
      if (step === 2 && !sessionStarted) options.append(button("Посмотреть демо", () => { dialog.close(); startDemo(); }));
      body.append(options);
      const actions = node("div", undefined, "dialog-actions");
      if (step > 1) actions.append(button("Назад", () => onboarding(step - 1)));
      actions.append(button(step < 5 ? "Продолжить знакомство" : "Готово", () => step < 5 ? onboarding(step + 1) : dialog.close()));
      body.append(actions);
    };
    $("#open-onboarding").addEventListener("click", () => onboarding());

    const startDemo = () => {
      if (sessionStarted) return;
      demo = true;
      document.body.classList.add("is-demo");
      $("#demo-banner").classList.remove("hidden");
      snapshot = null; catalog = []; events = []; payouts = [];
      adapter.enterDemo();
      renderEvents(); renderCalendar(); adapter.renderAssets([]); markPrivate();
    };
    $("#start-demo").addEventListener("click", startDemo);
    $("#exit-demo").addEventListener("click", () => location.assign("/?login"));

    const exportPortfolio = () => {
      if (!snapshot) { toast("Для экспорта сначала нужен снимок портфеля."); return; }
      const safe = (value) => {
        const text = String(value ?? "");
        const escaped = /^[=+@\-\t\r\n]/.test(text) ? "'" + text : text;
        return '"' + escaped.replaceAll('"', '""') + '"';
      };
      const rows = [["Дата снимка", "Инструмент", "Тикер", "Количество", "Цена", "Валюта"]];
      for (const item of snapshot.portfolio.positions || []) rows.push([snapshot.refreshed_at, item.name, item.ticker, item.quantity, item.current_price?.value, item.current_price?.currency]);
      download("omnicio-portfolio.csv", "\uFEFF" + rows.map((row) => row.map(safe).join(";")).join("\r\n"), "text/csv;charset=utf-8");
    };
    const exportButton = button("Скачать состав CSV", exportPortfolio);
    $("#portfolio-refresh").after(exportButton);

    const refreshNetwork = () => {
      $("#network-banner").classList.toggle("hidden", navigator.onLine);
    };
    window.addEventListener("online", refreshNetwork);
    window.addEventListener("offline", refreshNetwork);
    const configurePwa = async () => {
      if (!("serviceWorker" in navigator)) return;
      try {
        const build = document.body.dataset.build;
        const registration = await navigator.serviceWorker.register(`/sw.js?build=${encodeURIComponent(build)}`);
        const offer = (worker) => {
          if (!worker) return;
          waitingWorker = worker;
          $("#update-banner").classList.remove("hidden");
        };
        offer(registration.waiting);
        registration.addEventListener("updatefound", () => {
          const worker = registration.installing;
          worker?.addEventListener("statechange", () => {
            if (worker.state === "installed" && navigator.serviceWorker.controller) offer(registration.waiting);
          });
        });
        let checkedAt = Date.now();
        const checkForUpdate = () => {
          if (!navigator.onLine || document.hidden || Date.now() - checkedAt < 60000) return;
          checkedAt = Date.now();
          void registration.update().catch(() => { /* Retry on a later online/visible check. */ });
        };
        window.addEventListener("online", checkForUpdate);
        document.addEventListener("visibilitychange", checkForUpdate);
        window.setInterval(checkForUpdate, 60 * 60 * 1000);
      } catch { /* Online operation remains available without installation. */ }
    };
    $("#apply-update").addEventListener("click", () => {
      if (adapter.hasPending() || dialog.open || notificationsDirty || $("#assistant-input").value.trim()
        || JSON.stringify(allocation) !== allocationExported || JSON.stringify(goals) !== goalsExported) {
        toast("Завершите или сохраните открытый черновик перед обновлением.");
        return;
      }
      if (!waitingWorker) return;
      updateRequested = true;
      if (waitingWorker.state === "activated") location.reload();
      else waitingWorker.postMessage({type: "ACTIVATE_UPDATE"});
    });
    let reloading = false;
    navigator.serviceWorker?.addEventListener("controllerchange", () => {
      if (updateRequested && !reloading) { reloading = true; location.reload(); }
    });

    renderAllocation();
    const help = initHelp();
    help.attach("#public-reference-title", "Официальные данные Банка России", {
      summary: "Показывает опубликованные ЦБ курсы и ключевую ставку. Курс ЦБ — не цена покупки валюты на бирже или у брокера.",
      sections: [
        ["Что меняет выбор", "Валюта и период меняют только отображаемый график. Они не меняют настройки счёта и не создают сделок."],
        ["Откуда значения", "Каждая точка — значение, опубликованное Банком России, с датой действия. Промежутки без наблюдений не заполняются выдуманными ценами."],
        ["Как читать", "Нажмите точку или передвиньте ползунок под графиком: рядом появятся точное значение и дата. Таблица раскрывает все полученные наблюдения."],
        ["Когда источник недоступен", "Показана ошибка или предыдущий ответ с исходными датами. Повторное открытие не превращает старый курс в новый. Личные деньги без входа не загружаются."],
      ],
    });
    const allocationExplanations = {"shares": ["Желаемая часть черновика, отведённая акциям. Это не фактическая доля на счёте. Изменение не покупает акции. В каталоге подходов оно сохраняет рабочий черновик отдельно от подтверждённых условий.", "Акция — доля участия в компании. Её рыночная цена может расти или падать; выплаты владельцам зависят от решений и результатов компании. Эта строка показывает, какую долю вы хотите отвести прямым вложениям в акции в примере.", "При большей доле акций в черновике уменьшаются другие свободные доли. Если когда-либо действительно собрать такой портфель, большая его часть будет зависеть от цен акций. Сам ползунок не рассчитывает будущий доход и не обещает его рост."], "bonds": ["Желаемая часть черновика, отведённая облигациям. Это не сумма уже купленных облигаций и не обещание фиксированного результата. Реальные бумаги на счёте не меняются.", "Облигация — бумага с обязательствами заёмщика по выплатам. Условия отличаются: важны срок, цена и способность заёмщика платить. Эта строка задаёт желаемую долю облигаций только в верхнем черновике.", "Большая доля оставляет меньше места другим свободным классам. Если реализовать такой состав отдельными действиями, больше капитала будет связано с облигациями и их рисками. Это не гарантирует стабильные выплаты или отсутствие падения цены."], "funds": ["Желаемая часть черновика, отведённая фондам. Фонд — общий набор вложений, в котором вы можете купить долю. Этот процент не раскрывает состав фондов и ничего не покупает.", "Фонд может держать акции, облигации или другие активы по своим правилам. Здесь вы задаёте желаемую долю паёв фондов как отдельного класса, а не отдельные доли всех компаний внутри них.", "Больше фондов в черновике — меньше места другим свободным классам. Реальный результат зависел бы от состава выбранных фондов. Разные фонды могут пересекаться по одним компаниям; само наличие нескольких фондов не означает независимые риски."], "cash": ["Желаемая часть капитала, которую в этом черновике вы оставляете деньгами. Это процент, а не рублёвый резерв ниже. Деньги не переводятся и не блокируются.", "Эта доля показывает незанятую ценными бумагами часть примерного распределения. Например, 10% — десятая часть капитала. Она не является вкладом или обещанием дохода на свободный остаток.", "Увеличите денежную долю — уменьшатся другие свободные доли. Уменьшите — в черновике можно отвести больше ценным бумагам. Это только схема распределения: ваш действительный денежный остаток от неё не меняется."]};
    keys.forEach((key, index) => {
      const control = $(`[data-allocation-key="${key}"]`);
      const heading = control.querySelector(".allocation-control-head");
      const number = $(`[data-target-number="${key}"]`);
      number.readOnly = true;
      number.inputMode = "none";
      number.setAttribute("aria-label", `Доля ${labels[index]}, изменяется ползунком и кнопками`);
      const allowance = $(`[data-allow="${key}"]`);
      allowance.setAttribute("role", "switch");
      allowance.closest("label").classList.add("toggle-row");
      const lock = $(`[data-lock="${key}"]`);
      lock.append(node("span", "Свободно", "allocation-lock-text"));
      const range = $(`[data-target-range="${key}"]`);
      const row = node("div", undefined, "allocation-adjustment");
      range.before(row);
      const step = (direction) => {
        const item = button(direction < 0 ? "−" : "+", () => {
          if (number.disabled) return;
          number.value = String(Math.max(0, Math.min(100, allocation[index] + direction)));
          number.dispatchEvent(new Event("input", {bubbles: true}));
        });
        item.className = "step-button";
        item.dataset.allocationStep = key;
        item.dataset.direction = String(direction);
        item.setAttribute("aria-label", `${direction < 0 ? "Уменьшить" : "Увеличить"} долю ${labels[index]} на 1 процентный пункт`);
        return item;
      };
      row.append(step(-1), range, step(1));
      help.attach(heading, `Справка: доля ${labels[index]}`, () => ({
        summary: allocationExplanations[key][0],
        current: `${allocation[index]}% в черновике. Из условных 100 000 ₽ это ${money(allocation[index] * 1000)}. Это пример, не сумма вашего портфеля.`,
        sections: [
          ["Что означает", allocationExplanations[key][1]],
          ["Если увеличить или уменьшить", allocationExplanations[key][2]],
          ["Как работают доли", "Всего всегда 100%. Когда вы меняете одну долю, остаток распределяется между разрешёнными долями без замка, пропорционально прежним значениям. Например, увеличение с 20% до 30% забирает 10 процентных пунктов из других свободных долей."],
          ["Как изменить", "Кнопки −/+ меняют на один процентный пункт. Ползунок задаёт долю напрямую. Если доля выключена или закреплена замком, сначала измените соответствующий переключатель. Если все остальные доли закреплены, свободного остатка для изменения нет."],
          ["Что не изменится", "Реальные активы, рублёвый резерв и сохранённые верхние лимиты не меняются. Этот блок пока не передаёт целевые доли серверному расчёту. Доступны просмотр различий и скачивание черновика, но не его применение к реальному счёту."],
        ],
      }));
      const tools = node("div", undefined, "allocation-tools");
      const allowedHelp = node("span", "Разрешение класса");
      const lockHelp = node("span", "Как работает замок");
      help.attach(allowedHelp, `Справка: разрешение ${labels[index]}`, () => ({
        summary: "Разрешает использовать этот класс в верхнем черновике долей. Выключение ставит его долю в ноль; имеющиеся бумаги на брокерском счёте не продаются.",
        current: excluded.has(index) ? `${labels[index]} выключены в черновике, доля 0%.` : `${labels[index]} разрешены в черновике, доля ${allocation[index]}%.`,
        sections: [
          ["Что делает включение", "Позволяет снова менять долю этого класса. Ранее убранный процент не восстанавливается сам: задайте нужную долю ползунком или кнопками. Это не включает серверный подбор и не разрешает брокеру покупки."],
          ["Что делает выключение", "Убирает долю из черновика и распределяет освободившееся между остальными разрешёнными долями без замка. Если доля была закреплена, при её выключении этот замок снимается."],
          ["Пример", "В черновике акции занимают 20%. Выключите их — станет 0%, а эти 20 процентных пунктов перейдут в другие доступные доли. Акции, которые уже куплены у брокера, останутся на счёте."],
          ["Когда действие не получится", "Нужно оставить хотя бы один другой разрешённый класс без замка. Иначе некуда распределить остаток до 100%. Сначала освободите нужную долю. Выключение в этом блоке не заменяет нулевой верхний лимит в сохранённых настройках."],
        ],
      }));
      help.attach(lockHelp, `Справка: замок ${labels[index]}`, () => ({
        summary: "Закрепляет выбранный процент в черновике, чтобы он не менялся при настройке других долей. Это замок числа, а не денег или бумаг на счёте.",
        current: locked.has(index) ? `Доля ${allocation[index]}% закреплена.` : `Доля ${allocation[index]}% не закреплена и может участвовать в перераспределении.`,
        sections: [
          ["Когда замок закрыт", "Эта доля не участвует в распределении остатка и её ползунок недоступен. Остальные разрешённые доли без замка делят оставшийся процент."],
          ["Когда замок открыт", "Доля снова может изменяться: и напрямую, и при настройке соседних долей. Снятие замка само по себе не меняет текущий процент."],
          ["Пример", "Закрепили денежный резерв 10%. На остальные классы остаётся 90%. При изменении доли акций эти 10% не затрагиваются. Если закрепить все доли, перераспределять будет нечего."],
          ["Границы действия", "Замок действует только в открытом черновике. Выключение класса убирает его долю и снимает её замок. Кнопка возврата начальных долей сбрасывает все замки. Денежный резерв у брокера и торговые поручения это не меняет."],
        ],
      }));
      tools.append(allowedHelp, lockHelp);
      control.append(tools);
    });
    const presetDescriptions = {
      income: "Больше облигаций в примере; выплаты не гарантированы.",
      growth: "Больше акций в примере; стоимость может сильнее колебаться.",
      balanced: "Сочетание классов в примере, а не оценка вашего риск-профиля.",
    };
    all("[data-preset]").forEach((item) => {
      const description = node("small", presetDescriptions[item.dataset.preset]);
      item.append(description);
      const presetContainer = node("div", undefined, "preset-with-help");
      item.before(presetContainer);
      presetContainer.append(item);
      const presetValues = {income: [10, 70, 10, 10], growth: [55, 25, 10, 10], balanced: [30, 50, 10, 10]}[item.dataset.preset];
      const presetTitle = {income: "Доход", growth: "Накопление", balanced: "Сочетание"}[item.dataset.preset];
      help.attach(presetContainer, `Справка: пример «${presetTitle}»`, {
        summary: `Подставляет пример долей: акции ${presetValues[0]}%, облигации ${presetValues[1]}%, фонды ${presetValues[2]}%, деньги ${presetValues[3]}%. Это начальная схема для редактирования, не готовая рекомендация.`,
        sections: [
          ["Что изменится", "Заменятся только четыре доли в верхнем черновике. Название описывает идею примера, но не определяет вашу цель, подходящие бумаги, доходность или риск. Каждую долю можно изменить."],
          ["На условном капитале 100 000 ₽", `Акции — ${money(presetValues[0] * 1000)}, облигации — ${money(presetValues[1] * 1000)}, фонды — ${money(presetValues[2] * 1000)}, деньги — ${money(presetValues[3] * 1000)}. Это иллюстрация процентов, а не поручение распределить ваши деньги.`],
          ["Когда пример не применится", "Если какие-либо классы выключены или закреплены, кнопка не снимает эти ограничения за вас. Сначала осознанно разрешите классы и снимите замки, либо изменяйте доли по одной."],
          ["Чего название не обещает", "«Доход» не гарантирует выплаты, «Накопление» — рост капитала, «Сочетание» — защиту от убытков. Рублёвый резерв, верхние лимиты, сохранённый профиль и реальные активы этой кнопкой не меняются."],
        ],
      });
      item.setAttribute("aria-pressed", "false");
      item.addEventListener("click", () => {
        if (locked.size || excluded.size) return;
        all("[data-preset]").forEach((preset) => preset.setAttribute("aria-pressed", String(preset === item)));
      });
    });
    all("[data-target-range], [data-target-number], [data-allow]").forEach((item) => {
      item.addEventListener("input", () => all("[data-preset]").forEach((preset) => preset.setAttribute("aria-pressed", "false")));
    });
    $("#reset-allocation").addEventListener("click", () => all("[data-preset]").forEach((preset) => preset.setAttribute("aria-pressed", "false")));
    const presetHelp = node("div", "Примеры для старта", "setting-toggle-help");
    $(".strategy-preset-group").before(presetHelp);
    help.attach(presetHelp, "Справка: примеры распределения", {"summary": "Три кнопки дают разные начальные схемы распределения. Они меняют только черновик четырёх долей. Название подхода не обещает доход и не выбирает финансовые условия за вас.", "sections": [["Доход", "Пример: 10% акции, 70% облигации, 10% фонды, 10% деньги. Большая доля облигаций в примере не гарантирует выплаты или сохранность средств."], ["Накопление", "Пример: 55% акции, 25% облигации, 10% фонды, 10% деньги. Большая доля акций не означает, что капитал обязательно вырастет."], ["Сочетание", "Пример: 30% акции, 50% облигации, 10% фонды, 10% деньги. Это ещё одна схема, а не вычисленный для вас баланс риска и дохода."], ["Как применяются", "Нужно разрешить все классы и снять замки; иначе пример не заменяет ваши ограничения. Кнопки не записывают серверный профиль. Для каждого примера рядом есть отдельная справка с точным составом."]]});
    // Time selectors reuse the existing, device-local notification draft contract.
    for (const {id, title, text} of [
      {"id": "digest-time", "title": "Время обзора", "text": {"summary": "Время, в которое вы хотели бы получать обзор. Пока оно только входит в скачиваемый черновик расписания: эта настройка не запускает отправку уведомлений.", "sections": [["Как читать", "Часы и минуты выбираются отдельно. 20:30 означает половину девятого вечера в выбранном часовом поясе, а не обязательно в текущем поясе телефона."], ["Что меняет выбор", "Меняется записанное пожелание о времени обзора. Ни число активов, ни доли, ни расчёт дохода от этого не меняются. Смена времени не создаёт ещё один обзор."], ["Пример", "Было 20:30, выбрали 19 часов и 00 минут — в черновике станет 19:00. Это не подтверждение, что сообщение уже запланировано сервером."], ["Ограничение текущей версии", "Серверная доставка по этому расписанию пока не подключена. Разрешения браузера, сеть и тихий режим устройства нельзя обойти выбором времени."]]}},
      {"id": "quiet-start", "title": "Начало тихих часов", "text": {"summary": "Начало интервала, когда вы не хотите получать обычные уведомления. Сейчас это пожелание в черновике, а не включённый на сервере запрет доставки.", "sections": [["Как работает интервал", "Начало 22:00 и конец 09:00 означают ночь через полночь. Используется выбранный часовой пояс. Выбирайте разные времена начала и конца: одинаковое время в текущем интерфейсе не объясняет однозначно длительность."], ["Если изменить", "Более раннее начало при том же конце означает более длинный ночной интервал в таком примере. Более позднее — более короткий. Это не меняет настройки звука телефона."], ["Пример", "22:00–09:00 — пожелание не беспокоить ночью. 21:00–09:00 начинает этот интервал на час раньше."], ["Что не произойдёт", "Торги, позиции, выплаты и наблюдение за портфелем этой настройкой не останавливаются. Фактическая серверная доставка по черновику сейчас не включена."]]}},
      {"id": "quiet-end", "title": "Окончание тихих часов", "text": {"summary": "Время окончания желаемого тихого интервала. Оно не включает звук телефона, не назначает утреннюю сделку и пока не управляет реальной доставкой сообщений.", "sections": [["Что означает", "В паре с началом задаёт интервал без обычных уведомлений в вашем черновике. Время относится к выбранному часовому поясу."], ["Если изменить", "При начале 22:00 конец в 10:00 делает ночной интервал на час длиннее, чем конец в 09:00. Конец в 08:00 — на час короче."], ["Пример", "22:00–09:00 — одна настройка; 22:00–10:00 — другая. Выбор не означает гарантированную отправку всех сообщений ровно в 10:00."], ["Ограничение текущей версии", "Расписание только редактируется и скачивается. Будущая доставка потребует отдельного подключения; настройки устройства и разрешения браузера сохраняют силу."]]}},
    ]) {
      const input = $("#" + id);
      const row = node("span", undefined, "time-choice");
      const hours = node("select");
      const minutes = node("select");
      for (const [select, size, label] of [[hours, 24, "часы"], [minutes, 60, "минуты"]]) {
        select.setAttribute("aria-label", `${title}: ${label}`);
        for (let value = 0; value < size; value += 1) {
          const option = node("option", String(value).padStart(2, "0"));
          option.value = String(value).padStart(2, "0");
          select.append(option);
        }
        select.addEventListener("change", () => {
          input.value = `${hours.value}:${minutes.value}`;
          input.dispatchEvent(new Event("input", {bubbles: true}));
        });
      }
      const sync = () => {
        [hours.value, minutes.value] = input.value.split(":");
        hours.disabled = input.disabled;
        minutes.disabled = input.disabled;
      };
      input.hidden = true;
      input.after(row);
      row.append(hours, node("span", ":"), minutes);
      const holder = node("span", undefined, "time-choice-help");
      row.after(holder);
      help.attach(holder, `Справка: ${title}`, () => ({...text, current: `${input.value}, часовой пояс ${$("#digest-zone").selectedOptions[0].textContent}. Только черновик расписания.`}));
      input.addEventListener("input", sync);
      sync();
    }
    for (const {selector, title, text} of [
      {"selector": "#notify-security", "title": "События безопасности", "text": {"summary": "Включает пожелание получать сообщения о безопасности в черновик настроек. Выключение не отключает защиту аккаунта и не разрешает опасные действия.", "sections": [["Включено и выключено", "Включено — вы отмечаете этот тип сообщений как нужный. Выключено — убираете его из черновика. Это не отключатель серверных проверок и не разрешение входа другим людям."], ["Пример", "Сообщение о проблеме доступа относится к безопасности. Это не совет покупать или продавать активы."], ["На что влияет сейчас", "Меняется только скачиваемое пожелание о сообщениях. Серверная доставка по нему ещё не подключена. Сами активы и деньги не меняются."]]}},
      {"selector": "#notify-income", "title": "Выплаты", "text": {"summary": "Добавляет в черновик желание получать сообщения о выплатах по активам. Сообщение об ожидаемой выплате не означает, что деньги уже появились на счёте.", "sections": [["Что различать", "Дата в календаре и объявленная сумма — не то же самое, что подтверждённое зачисление брокером. Расходовать ожидаемую выплату как свободные деньги нельзя только на основании сообщения."], ["Включено и выключено", "Включение отмечает категорию в черновике, выключение убирает её. Право на купон или дивиденд и график выплат от переключателя не зависят."], ["Пример", "В календаре указан купон на завтра. Это будущая ожидаемая выплата, а не уже доступная сумма."], ["На что влияет сейчас", "Меняется только локальный черновик уведомлений. Доставку сообщений на телефон эта версия не включает; финансовых действий нет."]]}},
      {"selector": "#notify-night", "title": "Важные события ночью", "text": {"summary": "Отдельное пожелание получать важные сообщения даже в выбранные тихие часы. Это не разрешение обходить режим «Не беспокоить» телефона.", "sections": [["Включено и выключено", "Включено — в черновике отмечено исключение для важных событий. Выключено — такого исключения нет. Значок не гарантирует, что приложение сможет издать звук или показать сообщение ночью."], ["Пример", "Тихие часы 22:00–09:00. Вы можете отметить пожелание получать важное ночью, но система телефона всё равно может заблокировать звук или показ."], ["На что влияет сейчас", "Только на черновик расписания. Серверной доставки по нему пока нет. Торги, защита и состав портфеля не меняются."]]}},
      {"selector": "#notify-amounts", "title": "Суммы в уведомлениях", "text": {"summary": "Пожелание показывать финансовые суммы в сообщениях. Это может сделать их видимыми постороннему на экране телефона. По умолчанию выключено.", "sections": [["Когда выключено", "Предпочтение — получать сообщение без финансовых сумм. Сами данные портфеля в аккаунте не удаляются."], ["Когда включено", "В черновике вы разрешаете показывать суммы в будущих уведомлениях. Человек рядом может увидеть их на экране блокировки, если устройство показывает содержимое сообщений."], ["Пример", "Нейтральный текст «Есть обновление по портфелю» не раскрывает размер выплаты. Текст с суммой выплаты раскрывает больше личной информации."], ["На что влияет сейчас", "Только на скачиваемые настройки. Доставка ещё не подключена. Это не меняет доступ к аккаунту, не публикует портфель и не даёт брокеру торговые права."]]}},
    ]) {
      const input = $(selector);
      input.setAttribute("role", "switch");
      const holder = node("div", undefined, "setting-toggle-help");
      input.closest("label").after(holder);
      holder.append(node("span", title));
      help.attach(holder, `Справка: ${title}`, () => ({...text, current: input.checked ? "Включено в черновике. Это не подтверждение включённой доставки." : "Выключено в черновике."}));
    }

    const actionHelp = (selector, title, content) => {
      const element = $(selector);
      if (!element) return;
      const holder = node("div", title, "setting-toggle-help");
      element.after(holder);
      help.attach(holder, `Справка: ${title}`, content);
    };
    actionHelp("#review-allocation", "Просмотр и скачивание долей", {"summary": "Кнопка открывает сравнение начального примера с вашим черновиком. Сам просмотр ничего не сохраняет и не пересобирает реальный портфель.", "sections": [["Что показывает таблица", "Для каждого класса видны начальный процент и выбранный вами процент. Это сравнение двух черновых схем, а не состава вашего счёта до и после сделки."], ["Продолжить редактирование", "Закрывает окно и оставляет выбранные доли на странице. Ничего не отправляется брокеру."], ["Скачать черновик", "Создаёт файл с выбранными долями и разрешёнными классами. Он нужен для переноса или проверки. Скачивание не применяет стратегию в аккаунте и не меняет серверные лимиты."], ["Пример", "В начале акции 20%, теперь 30%. В окне будет 20% → 30%. Это не означает, что на счёте куплено ещё 10% акций."]]});
    actionHelp("#reset-allocation", "Возврат начальных долей", {"summary": "Возвращает верхний черновик к начальному примеру и снимает его замки и исключения. Сохранённый профиль капитала и лимиты ниже не сбрасываются.", "sections": [["Что восстановится", "Акции 20%, облигации 60%, фонды 10%, деньги 10%. Все классы снова разрешены в черновике, все замки открыты."], ["Что будет потеряно", "Ваше текущее распределение в этом блоке заменится начальным. Это не загрузка последней версии из аккаунта и не отмена реальных сделок."], ["Пример", "Были акции 40% и закреплённый резерв 15%. После возврата станет 20% акций и 10% денег, замок будет снят."], ["На что не влияет", "Бумаги и деньги у брокера, рублёвый резерв, планируемые снятия и сохранённые лимиты не меняются."]]});
    actionHelp("#digest-zone", "Часовой пояс расписания", {"summary": "Уточняет, к какому местному времени относятся часы обзора и тихий интервал. Пока это часть черновика; часовой пояс телефона или брокера не меняется.", "sections": [["Как выбрать", "Выберите из списка понятный вам город или регион. Europe/Moscow — московское время, Asia/Yekaterinburg — время Екатеринбурга."], ["Что меняет выбор", "Цифры часов остаются теми же, но интерпретируются в другом поясе. Это не меняет даты сделок или выплат на стороне брокера."], ["Пример", "20:30 в Москве и 20:30 в Екатеринбурге относятся к разным моментам. Поэтому проверяйте пояс вместе со временем."], ["Граница функции", "Скачивание расписания не создаёт серверное напоминание. Реальная доставка пока не подключена."]]});
    actionHelp("#notifications-form button[type=\"submit\"]", "Скачивание настроек сообщений", {"summary": "Скачивает файл с выбранными категориями, временем и тихими часами. Это экспорт черновика, а не включение уведомлений на сервере.", "sections": [["Что попадёт в файл", "Время обзора, выбранный часовой пояс, начало и конец тихих часов, состояния переключателей сообщений."], ["Чего не происходит", "Кнопка не запрашивает разрешение браузера на уведомления и не проверяет доставку на телефон. Текущая версия не применяет скачанное расписание сервером."], ["Что значит результат", "Файл на устройстве — подтверждение экспорта, а не обещание получить обзор в выбранное время. Портфель и торговые настройки не меняются."]]});
    const strategyGuide = node("div", "Как связаны три блока", "setting-toggle-help");
    $(".strategy-jump").after(strategyGuide);
    help.attach(strategyGuide, "Справка: три блока стратегии", {"summary": "Доли показывают желаемую схему. Профиль задаёт денежные и временные условия. Лимиты ограничивают расчёт. Это разные настройки, они не подменяют друг друга.", "sections": [["1 · Распределение", "Проценты акций, облигаций, фондов и денег должны дать 100%. В каталоге подходов доли входят в сохраняемый рабочий черновик. В деморежиме они остаются примером. Можно посмотреть различия и скачать копию."], ["2 · Капитал и риск", "Отдельные настройки: рублёвый резерв, снятия, срок планирования, отношение к падению, срок выхода и разрешение более высокого кредитного риска. Фактическое применение каждого поля описано в его справке."], ["3 · Лимиты", "Максимальные доли, срок облигаций, объём перестройки и допущения. Например, цель акций 20% и предел акций 40% — не противоречие: одно означает желание, другое — потолок. Верхние пределы не нужно складывать до 100%."], ["Заполнение не означает проверку", "Счётчик 3/3 сообщает лишь, что три поля имеют значения. Он не подтверждает их разумность, сохранение или безопасность портфеля. Числа в стартовом примере не являются вашими личными данными."], ["Когда меняется счёт", "Изменение настроек само по себе не совершает сделок. В автономном примере нет доступа к реальному аккаунту: даже подтверждённое сохранение существует только до перезагрузки страницы."], ["Как читать помощь", "Наведите мышь или удержите i для короткой справки. Обычное нажатие закрепляет подробный текст с примером. Его можно прокручивать; «Закрыть справку» или Escape возвращают к настройке."]]});
    all("[data-strategy-section]").forEach((item) => item.addEventListener("click", () => {
      const target = $("#" + item.dataset.strategySection);
      target.scrollIntoView({block: "start", behavior: "instant"});
      target.focus({preventScroll: true});
    }));
    renderAllocation();
    renderCalendar();
    renderEvents();
    renderGoals();
    refreshNetwork();
    markPrivate();
    void configurePwa();

    return {
      isDemo: () => demo,
      openDemoInstrument: () => toast("Для данных инструмента нужен вход и подключение собственного счёта."),
      markAllocationSaved: () => { allocationExported = JSON.stringify(allocation); },
      readAllocation: () => ({allocation: Object.fromEntries(keys.map((key, i) => [key, allocation[i]])),
        locked: [...locked].map((i) => keys[i]).sort((a, b) => a.localeCompare(b)), excluded: [...excluded].map((i) => keys[i]).sort((a, b) => a.localeCompare(b))}),
      writeAllocation: (draft) => {
        const next = keys.map((key) => draft.allocation[key]);
        if (next.some((value) => !Number.isInteger(value) || value < 0 || value > 100)
          || next.reduce((sum, value) => sum + value, 0) !== 100) throw new Error("Invalid allocation draft");
        allocation = next; locked.clear(); excluded.clear();
        for (const key of draft.locked) locked.add(keys.indexOf(key));
        for (const key of draft.excluded) excluded.add(keys.indexOf(key));
        renderAllocation();
        $("#allocation-status").textContent = "Распределено 100%. Целевые доли входят в сохраняемый черновик; сделки не создаются.";
      },
      setSession: () => { sessionStarted = true; $("#start-demo").disabled = true; },
      setSnapshot: (data) => { snapshot = data; markPrivate(); },
      setAnalysis: (data) => {
        events = (data?.analysis?.observations || []).map((item) => ({kind: item.priority <= 2 ? "risk" : "system", title: item.title, detail: item.detail, time: data.refreshed_at, view: "decisions"}));
        renderEvents();
      },
      setPayouts: (items) => { payouts = items || []; renderCalendar(); },
      setCatalog: (items) => { catalog = items; },
      filterAssets, decorateAssets, toast,
      attachHelp: help.attach,
      openDialog: showDialog,
      closeDialog: () => dialog.close(),
      demoSearch: () => [],
      onView: (view) => {
        help.close(false, view);
        if (dialog.open) dialog.close();
        if (view === "goals") renderGoals();
        if (view === "events") renderEvents();
        if (view === "payouts") renderCalendar();
        if (view === "assets" && !catalog.length) empty($("#hunter-results"), "Найдите первый инструмент", "Введите название, тикер или ISIN. Для поиска нужен подключённый счёт T-Invest.");
        markPrivate();
      },
    };
  }};
})();
