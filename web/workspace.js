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
    const description = node("p");
    description.id = "workspace-help-text";
    const dismiss = button("Закрыть справку", () => close(true));
    dismiss.hidden = true;
    dismiss.classList.add("hidden");
    popover.append(description, dismiss);
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
    const close = (restoreFocus = false) => {
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
      if (restoreFocus && trigger?.isConnected) {
        restoringFocus = true;
        trigger.focus({preventScroll: true});
        restoringFocus = false;
      }
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
      pinned = pin;
      description.textContent = text;
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
    const attach = (selector, title, text) => {
      const target = $(selector);
      if (!target) return;
      const trigger = node("button", "?", "help-trigger");
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
      trigger.addEventListener("click", (event) => pinOrClose(event, trigger, text));
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
    return {close};
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
      if (!dialog.open) previousFocus = document.activeElement;
      $("#dialog-title").textContent = title;
      dialogBody.replaceChildren();
      if (!dialog.open) dialog.showModal();
      return dialogBody;
    };
    $("#dialog-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => previousFocus?.focus());
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
        input.value = String(allocation[i]);
        range.disabled = locked.has(i) || excluded.has(i);
        input.disabled = locked.has(i) || excluded.has(i);
        $(`[data-lock="${key}"]`).disabled = excluded.has(i);
        $(`[data-allow="${key}"]`).checked = !excluded.has(i);
        $(`[data-lock="${key}"]`).setAttribute("aria-pressed", String(locked.has(i)));
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
          $("#allocation-status").textContent = "Распределено 100%. Черновик изменён; сделки и сохранённые лимиты не менялись.";
        });
      }
      $(`[data-lock="${key}"]`).addEventListener("click", () => {
        if (locked.has(index)) locked.delete(index); else locked.add(index);
        renderAllocation();
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
      $("#allocation-status").textContent = "Начальные доли восстановлены. Серверные параметры не изменялись.";
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
          if (demo) showDemoInstrument(item);
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
        ["Личный аккаунт", demo ? "Сейчас открыт демонстрационный режим. Для своего портфеля нужен вход через VK ID." : "Вы вошли через VK ID. Подключение брокера и согласие на торговые действия проверяются отдельно.", "profile"],
        ["Выберите, с чего начать", "Изучите демо с вымышленными данными или подключите собственный счёт.", "connections"],
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

    const demoInstruments = [
      {uid: "demo-bond-1", ticker: "СЕВЕР-01", name: "Север Энерго · выпуск 01", instrument_type: "bond", lot: 1, price: "1000", quantity: "650"},
      {uid: "demo-bond-2", ticker: "ГОРОД-02", name: "Город Инфра · выпуск 02", instrument_type: "bond", lot: 1, price: "1000", quantity: "100"},
      {uid: "demo-share-1", ticker: "ВЕКТОР", name: "Вектор Технологии", instrument_type: "share", lot: 10, price: "250", quantity: "1000"},
      {uid: "demo-fund-1", ticker: "БАЛАНС", name: "Фонд «Баланс»", instrument_type: "etf", lot: 1, price: "125", quantity: "1000"},
    ];
    const showDemoInstrument = (item) => {
      const body = showDialog(item.name);
      body.append(node("span", "Вымышленный инструмент · демо", "state-badge state-next"), node("h3", item.ticker));
      const facts = node("dl", undefined, "info-list");
      for (const [label, value] of [["Класс", {bond: "Облигация", share: "Акция", etf: "Фонд"}[item.instrument_type]], ["Цена в примере", money(item.price)], ["Лот", `${item.lot} бумаг`], ["Доступность", "Не проверена — инструмент вымышленный"]]) {
        const row = node("div");
        row.append(node("dt", label), node("dd", value));
        facts.append(row);
      }
      body.append(facts, node("p", "Демонстрация структуры карточки. Доходность, рейтинг и право на покупку здесь не утверждаются.", "inline-note"), button("Открыть стратегию", () => { dialog.close(); adapter.navigate("strategy"); }));
    };
    const startDemo = () => {
      if (sessionStarted) return;
      demo = true;
      document.body.classList.add("is-demo");
      $("#demo-banner").classList.remove("hidden");
      const stamp = new Date().toISOString();
      const m = (value) => ({currency: "RUB", value: String(value)});
      const positions = demoInstruments.map((item) => ({
        instrument_uid: item.uid, figi: item.uid, ticker: item.ticker, name: item.name,
        instrument_type: item.instrument_type, quantity: item.quantity, quantity_lots: String(Number(item.quantity) / item.lot),
        lot: item.lot, current_price: m(item.price), average_position_price: m(Number(item.price) * .97),
        expected_yield_percent: "3.2", average_price: m(Number(item.price) * .97),
        value: m(Number(item.price) * Number(item.quantity)), blocked: false, blocked_lots: "0",
        current_nkd: m(0),
      }));
      const data = {refreshed_at: stamp, environment: "demo", account_name: "Демонстрационный портфель", cash: [m(125000)], blocked_cash: [m(0)], limits_loading_in_progress: false, freshness: {status: "fresh", observed_at: stamp, coverage: "complete"}, portfolio: {total: m(1250000), expected_yield_percent: "3.2", daily_yield: m(2350), daily_yield_percent: ".188", positions, asset_totals: [{kind: "bonds", money: m(750000)}, {kind: "shares", money: m(250000)}, {kind: "funds", money: m(125000)}, {kind: "currencies", money: m(125000)}]}};
      const history = Array.from({length: 90}, (_, i) => ({captured_at: new Date(Date.now() - (89-i) * 86400000).toISOString(), nav_rub: String(1120000 + i * 1400 + Math.round(Math.sin(i / 4) * 7200))}));
      history.at(-1).nav_rub = "1250000";
      snapshot = data;
      catalog = [...demoInstruments];
      events = [{kind: "income", title: "В примере ожидается купон", detail: "1 240 ₽ · Север Энерго. Объявленная выплата ещё не является свободными деньгами.", time: stamp, view: "payouts"}, {kind: "system", title: "Всё начинается с понятной картины", detail: "Изучите структуру, сравните инструменты и настройте пример стратегии. Данные вымышлены.", time: stamp, view: "strategy"}];
      payouts = [{instrument_uid: "СЕВЕР-01", name: "Север Энерго · выпуск 01", event_type: "coupon", expected_at: new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 15, 12).toISOString(), amount: "1240", currency: "RUB", status: "announced"}, {instrument_uid: "ГОРОД-02", name: "Город Инфра · выпуск 02", event_type: "coupon", expected_at: new Date(calendarMonth.getFullYear(), calendarMonth.getMonth(), 27, 12).toISOString(), amount: "850", currency: "RUB", status: "announced"}];
      adapter.enterDemo(data, history);
      renderEvents();
      renderCalendar();
      adapter.renderAssets(catalog);
      markPrivate();
    };
    $("#start-demo").addEventListener("click", startDemo);
    $("#exit-demo").addEventListener("click", () => location.assign("/"));

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
    renderCalendar();
    renderEvents();
    renderGoals();
    refreshNetwork();
    markPrivate();
    void configurePwa();

    return {
      isDemo: () => demo,
      openDemoInstrument: (uid) => {
        const item = demoInstruments.find((entry) => entry.uid === uid);
        if (item) showDemoInstrument(item);
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
      demoSearch: (query) => demoInstruments.filter((item) => `${item.name} ${item.ticker}`.toLocaleLowerCase("ru-RU").includes(query.toLocaleLowerCase("ru-RU"))),
      onView: (view) => {
        help.close();
        if (view === "goals") renderGoals();
        if (view === "events") renderEvents();
        if (view === "payouts") renderCalendar();
        if (view === "assets" && !catalog.length) empty($("#hunter-results"), "Найдите первый инструмент", "Введите название, тикер или ISIN. Для поиска нужен подключённый счёт T-Invest.");
        markPrivate();
      },
    };
  }};
})();
