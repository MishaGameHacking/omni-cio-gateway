менно так, не доверяя "магии AI".

**Зависимости:** WP37

# BLOCK I - Personal Real Execution (7%)

## WP39 - Mandatory Shadow Mode

**Цель:** Проверить Guardian на реальном портфеле без права менять деньги.

**Результаты / deliverables**

- Все incidents/decisions/plans формируются как если бы execution существовал, но broker writes hard disabled.

- Journal сравнивает decision с NO_ACTION и фактическим последующим рынком, не выдавая hindsight как исходную истину.

- Собрать достаточное число реальных/синтетических событий и failure cases.

**Обязательная проверка**

- Несколько недель стабильной работы; zero unauthorized writes; alert quality review.

**Exit Gate**

- Owner принимает отдельное решение, что Shadow quality достаточна для открытия Real acceptance.

**Зависимости:** Blocks A-H

**Участие владельца:** Наблюдать реальные рекомендации и сообщать о явно неверных/неудобных результатах; никаких торговых подтверждений на этом этапе.

## WP40 - Immutable Plan Approval

**Цель:** Одно подтверждение владельца разрешает только заранее полностью раскрытый plan.

**Результаты / deliverables**

- Plan hash связывает exact legs/assets/lots/price limits/costs/expiry/constraints.

- Approval short-lived, one-time, owner-bound; изменение plan invalidates approval.

- Web является основным экраном подтверждения; Telegram может только открыть plan/показать status.

**Обязательная проверка**

- Altered plan/replayed approval/expired approval/wrong owner tests.

**Exit Gate**

- Сервер не может выполнить другое действие под старым approval.

**Зависимости:** WP39

## WP41 - Execution State Machine

**Цель:** Автоматически выполнить подтверждённый plan строго внутри его границ.

**Результаты / deliverables**

- PRE-FLIGHT -> SUBMIT LEG -> RECONCILE -> VERIFY -> NEXT LEG -> FINAL RECONCILIATION.

- Повторный market/portfolio check перед каждой ногой.

- Idempotency key per request/leg; one possible submit.

- Partial fill policy и cash recalculation.

**Обязательная проверка**

- Broker fake/integration cases: fill/partial/reject/timeout/possible-submit.

**Exit Gate**

- Никаких hidden extra legs; state machine воспроизводима по Journal.

**Зависимости:** WP40

## WP42 - Drift Stop и re-plan

**Цель:** Не продолжать старое решение, если рынок/портфель ушёл за подтверждённые границы.

**Результаты / deliverables**

- Price/spread/liquidity/portfolio/policy drift thresholds.

- При breach - STOP, safe cash/position state, новый analysis/plan, новое approval.

- Запрет автоматического "догоняющего" расширения лимита.

**Обязательная проверка**

- Artificial price gap/spread widening/position change mid-plan.

**Exit Gate**

- Подтверждение означает permission to execute exact plan, а не бессрочную автономию.

**Зависимости:** WP41

## WP43 - Broker reconciliation и ambiguous-submit safety

**Цель:** Сохранить ключевой safety invariant V9 в новой платформе.

**Результаты / deliverables**

- Broker state - единственное доказательство fill.

- Network timeout после possible submit -> UNKNOWN/RECONCILE, no automatic second submit.

- Order/portfolio streams reconcile execution journal.

**Обязательная проверка**

- Idempotent replay verified with no second submit.

- Submitted vs filled distinction.

**Exit Gate**

- Canonical V9 invariant сохраняется в V10 и покрыт permanent regression test.

**Зависимости:** WP42

## WP44 - Kill switches и OWNER authority

**Цель:** Обеспечить быстрый отказ от опасного функционала независимо по контурам.

**Результаты / deliverables**

- REAL_TRADING_ENABLED, PLAN_EXECUTION_ENABLED, WATCHTOWER_ENABLED, AI_ENABLED, TELEGRAM_ENABLED.

- Kill switch state доступен System UI и service config; изменение требует owner/admin authority.

- AI/Telegram kill не должен ломать read-only portfolio monitoring.

**Обязательная проверка**

- Каждый switch on/off runtime tests.

**Exit Gate**

- Одним действием можно запретить реальные деньги без остановки аналитической системы.

**Зависимости:** WP43

# BLOCK J - Системная интеграция, Hardening, Recovery и Release (5%)

## WP45 - Full System Integration

**Цель:** Собрать уже завершённые блоки последовательно и доказать end-to-end workflow.

**Результаты / deliverables**

- GitHub -> reviewed release -> Lenovo -> DB -> T-Invest -> Watchtower -> Research/AI -> Risk -> Decision -> Telegram -> Web -> Plan -> Execution -> Journal.

- Все boundaries проверяются contract tests; не переписывать внутренние компоненты на этапе сборки без отдельного bug PR.

**Обязательная проверка**

- E2E shadow и controlled execution simulations.

**Exit Gate**

- Каждый переход имеет evidence; нет ручных скрытых шагов между сервисами.

**Зависимости:** Blocks A-I

## WP46 - Fault Injection / Chaos для Personal Node

**Цель:** Искусственно сломать систему до эксплуатации и проверить, что отказ не приводит к неконтролируемой сделке.

**Результаты / deliverables**

- Отключение интернета, Telegram, AI, T-Invest, DB, disk-full simulation, stale market, duplicate messages, Windows reboot.

- Crash в разных execution states.

- Clock/time skew checks для TTL/approval.

**Обязательная проверка**

- Automated/controlled fault suite с expected safe state.

**Exit Gate**

- При каждом tested failure money boundary остаётся fail-closed/reconciled.

**Зависимости:** WP45

## WP47 - Security Acceptance

**Цель:** Проверить Web/API/AI/local-node security как отдельный release gate.

**Результаты / deliverables**

- OWASP ASVS 5.0.0 как web/API security checklist; OWASP AISVS 1.0 для AI-enabled components.

- Auth/session/authorization, CSRF/XSS/injection, SSRF, file handling, secret exposure, local privilege, Telegram auth, backup encryption.

- SAST/dependency/secret scans и manual threat-model review.

**Обязательная проверка**

- Attack-path negative tests на owner data/trading authority.

**Exit Gate**

- Нет открытого P0/P1 security finding перед release.

**Зависимости:** WP46

## WP48 - Performance/Thermal/24x7 Acceptance

**Цель:** Доказать, что выбранный Lenovo способен стабильно держать Personal V10.

**Результаты / deliverables**

- CPU/RAM/GPU/VRAM/disk/network baseline под обычной нагрузкой.

- AI heavy task не должен делать Web/Watchtower недоступными надолго; resource quotas/concurrency limits.

- Temperature monitoring и graceful AI throttling.

**Обязательная проверка**

- 24-72h soak test, r