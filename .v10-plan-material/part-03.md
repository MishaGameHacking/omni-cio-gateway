ает portfolio->risk->optimizer->plan.

**Exit Gate**

- Core может работать без Custom GPT и без OpenAI.

- V9 rollback остаётся рабочим.

**Зависимости:** Blocks A-C

## WP12 - Canonical Domain Model и tenant-ready IDs

**Цель:** Создать единую внутреннюю модель данных, пригодную для OWNER сейчас и возможного multi-tenant будущего без включения public режима.

**Результаты / deliverables**

- Определить Tenant/User/BrokerAccount/PortfolioSnapshot/Position/Instrument/Policy/Evidence/Incident/Decision/Plan/Execution/Journal models.

- Каждый private record связывается с tenant_id/portfolio_id/policy_id.

- В V10 runtime разрешён только OWNER tenant; попытка создать public tenant fail closed.

- Identity instruments связывать по broker UID/ISIN/FIGI/class code, а ticker/name использовать только как secondary labels.

**Обязательная проверка**

- Schema validation, uniqueness/identity collision tests, cross-tenant access negative tests.

**Exit Gate**

- Нет неявных глобальных singleton-данных, которые сделали бы будущую изоляцию невозможной.

**Зависимости:** WP11

## WP13 - PostgreSQL persistence и migrations

**Цель:** Перевести durable state из ad-hoc storage в версионированную локальную базу с auditability.

**Результаты / deliverables**

- Создать migration framework и схемы portfolio snapshots, positions, evidence, research, incidents, decisions, plans, execution, journal, jobs, health.

- Все деньги/цены/количества - Decimal/numeric с явной scale policy, не float.

- Append-only/audit-sensitive записи защищать от тихого overwrite.

- Indexes/retention для временных market/research caches.

**Обязательная проверка**

- Migration up/down или forward-recovery tests.

- Concurrent writes/idempotency tests.

- Backup/restore интеграция.

**Exit Gate**

- DB можно поднять из нуля миграциями и восстановить из backup; state hashes/revisions согласованы.

**Зависимости:** WP12

## WP14 - Durable Job System

**Цель:** Сделать фоновые задачи наблюдаемыми, idempotent и восстанавливаемыми после перезапуска.

**Результаты / deliverables**

- Job model: id, type, idempotency key, state, lease, attempts, next_run, error class, correlation id.

- Задачи: portfolio refresh, market refresh, research, Watchtower, AI research, reconciliation, backups, health.

- Bounded retries; permanent/validation errors не повторять бесконечно.

- Job journal позволяет объяснить, что реально запускалось на сервере.

**Обязательная проверка**

- Crash mid-job recovery.

- Duplicate scheduling/idempotency.

- Lease expiry/concurrency.

**Exit Gate**

- После reboot незавершённые задачи либо корректно продолжаются, либо безопасно помечаются для reconciliation.

**Зависимости:** WP13

## WP15 - T-Invest read-only data layer и freshness

**Цель:** Обеспечить канонические реальные данные портфеля для всех последующих решений.

**Результаты / deliverables**

- Адаптер account-specific read-only token.

- Portfolio/positions/market/operations streams или bounded polling по официальным возможностям API.

- Единые timestamps, freshness policy и data completeness markers.

- Кэш instrument identities; rate-limit aware backoff.

- Никаких торговых методов в read-only adapter.

**Обязательная проверка**

- Offline fixtures + controlled live read-only smoke.

- Stale/partial/stream reconnect tests.

- Wrong account/identity binding tests.

**Exit Gate**

- Core получает точный PortfolioSnapshot с completeness/freshness и masked account identity; real write невозможен из read adapter.

**Зависимости:** WP14

**Участие владельца:** Локально предоставить read-only T-Invest token, когда read layer будет готов.

# BLOCK E - Omni-CIO Web Platform (15%)

## WP16 - Web Design System

**Цель:** Создать один переиспользуемый UI-фундамент вместо десятков несогласованных страниц.

**Результаты / deliverables**

- Tokens: typography, spacing, semantic status, risk severity, light/dark.

- Components: cards, tables, charts wrappers, dialogs, drawers, buttons, badges, toasts, skeletons, empty/error states.

- Mobile-first от 360px; keyboard navigation; accessibility labels; reduced-motion support.

- Финансовые warning/error стили отделены от декоративных цветов.

**Обязательная проверка**

- Visual regression/screenshots ключевых components.

- Accessibility smoke.

- 360/768/1440 layout matrix.

**Exit Gate**

- Все последующие страницы используют единый design system; нет локальных случайных UI паттернов.

**Зависимости:** Block D core API contracts

## WP17 - Application Shell и navigation

**Цель:** Сделать стабильный каркас единого сайта.

**Результаты / deliverables**

- Навигация: Обзор, Портфель, Активы, Watchtower, Research, Риски, Решения, Планы, Исполнение, Журнал, Система, Настройки.

- OWNER authentication/session; route guards; API error boundary.

- Global health/freshness indicator.

- Web build version/git SHA visible in system page, не в каждом экране.

**Обязательная проверка**

- Route/E2E tests, unauthorized access tests, offline API behaviour.

**Exit Gate**

- Сайт стабильно открывается локально и показывает системный shell даже при degraded downstream services.

**Зависимости:** WP16

## WP18 - Portfolio Dashboard и Assets

**Цель:** Дать владельцу прозрачное текущее состояние капитала без обращения к GPT.

**Результаты / deliverables**

- Portfolio value, cash, positions, weights, currencies, issuers, sectors/classes, data timestamp.

- Concentration/top positions, stale data warnings, broker connection state.

- Position detail с instrument identity и linked incidents/research.

- Объяснимые расчёты и distinction broker/current market where applicable.

**Обязательная проверка**

- Golden portfolio UI fixtures, decimal/currency tests, empty portfolio, partial data, stale data.

**Exit Gate**

- Все показанные числа имеют источник/timestamp; UI не маскирует неполноту данных.

**Зависимости:** WP17, WP15

## WP19 - Watchtower / Incident UI

**Цель:** Сделать каждую тревогу проверяемым объектом, а не transient сообщением.

**Результаты / deliverables**

- Incident timeline, severity, subject, evidence refs, current state, risk impact, dedup/reopen status.

- Переходы lifecycle и связь с Decision/Plan.

- Фильтры active/resolved/critical.

**Обязательная проверка**

- Incident state E2E; duplicate/reopened scenario; missing evidence display.

**Exit Gate**

- По каждому alert мо