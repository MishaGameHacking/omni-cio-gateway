жно понять что произошло, почему, когда и что система сделала после обнаружения.

**Зависимости:** WP18

## WP20 - Research Dossier UI

**Цель:** Сделать provenance и неопределённость видимыми владельцу.

**Результаты / deliverables**

- Facts, source links/labels, published/retrieved time, freshness, contradictions, unknowns, confidence.

- Event timeline; issuer/security identity; Credit/Fund links.

- AI generated summary явно отделяется от canonical structured facts.

**Обязательная проверка**

- Long text/source list rendering; stale/contradictory states; malicious markup sanitization.

**Exit Gate**

- Нельзя визуально спутать факт из источника с AI/inference.

**Зависимости:** WP19, Block G contracts

## WP21 - Decision, Risk и Plan UI

**Цель:** Показать одно основное решение и точную математику до/после.

**Результаты / deliverables**

- MAIN_DECISION: NO_ACTION/HOLD/REDUCE/EXIT/REALLOCATE.

- Risk before/after, target weights, lots, costs, cash, constraints, blockers, evidence.

- Immutable plan hash/version/expiry.

- Альтернативы доступны как explanation, но не заставляют владельца угадывать правильную долю.

**Обязательная проверка**

- Deterministic rendering from Plan DTO; altered plan invalidates approval UI.

**Exit Gate**

- Владелец видит точный предмет будущего подтверждения до любого real execution.

**Зависимости:** WP20

## WP22 - System/Admin UI

**Цель:** Дать владельцу единое место эксплуатации без командной строки.

**Результаты / deliverables**

- Service health, Git SHA/release, last deploy, DB/migrations, last backup, T-Invest, Telegram, Watchtower, AI, resource/temperature/free disk.

- Kill-switch state отображается read-only/controlled admin flow.

- Recent errors/jobs без secret leakage.

**Обязательная проверка**

- Degraded service scenarios; masked error output.

**Exit Gate**

- Владелец может понять состояние всей системы без GitHub/PowerShell для обычной диагностики.

**Зависимости:** WP21

# BLOCK F - Telegram и связь с Web (8%)

## WP23 - Telegram Bot Foundation

**Цель:** Создать отдельный лёгкий adapter к Core для уведомлений и быстрых owner-команд.

**Результаты / deliverables**

- OWNER-only bot; команды status, portfolio summary, active alerts, open app.

- Long polling на Personal Node на первом этапе; публичный webhook не требуется.

- Bot не содержит финансовой бизнес-логики - только Core API calls и presentation.

**Обязательная проверка**

- Unauthorized Telegram user denied; token masking; reconnect/backoff tests.

**Exit Gate**

- OWNER получает проверенный status/alerts, а чужой user ID не получает private data.

**Участие владельца:** Создать BotFather bot и один раз локально сохранить token.

## WP24 - Telegram Identity и Mini App authentication

**Цель:** Криптографически связывать Web/Mini App session с OWNER.

**Результаты / deliverables**

- Validate Telegram `initData` server-side; не доверять `initDataUnsafe`.

- Проверять auth_date/expiry; OWNER whitelist; session rotation.

- Подготовить возможность future OIDC/third-party validation без изменения Core identity.

**Обязательная проверка**

- Tampered hash, replayed stale auth_date, wrong user ID tests.

**Exit Gate**

- Ни один Mini App request не получает OWNER scope только из client-provided fields.

**Зависимости:** WP23

## WP25 - Alert Delivery Policy

**Цель:** Присылать только полезные material alerts и не превращать Watchtower в шум.

**Результаты / deliverables**

- Critical/Important/Info/Silent policy.

- Semantic dedup, reopen after resolution, quiet hours policy только для non-critical.

- Message содержит минимум private data, incident id и safe summary.

**Обязательная проверка**

- Duplicate delivery, persistent condition, resolved/reappeared condition.

**Exit Gate**

- Чистый Watchtower run молчит; новый material incident доставляется один раз.

**Зависимости:** WP24

## WP26 - Telegram -> Web / Mini App integration

**Цель:** Использовать Telegram как точку входа в единый сайт, а не писать второй сложный UI.

**Результаты / deliverables**

- Кнопка открывает конкретный incident/decision route.

- Deep-link/start parameter validation.

- Поддержать ordinary browser и Telegram Mini App одним frontend codebase.

- External HTTPS ingress активируется только после отдельного security gate.

**Обязательная проверка**

- Deep-link wrong/expired incident; Telegram/mobile themes; safe-area/responsive.

**Exit Gate**

- Alert -> click -> правильный incident на Web без повторного ручного поиска.

**Зависимости:** WP25, Block E

# BLOCK G - Research + Local AI (12%)

## WP27 - Trusted Source Registry

**Цель:** Сначала создать данные и provenance; только потом добавлять AI.

**Результаты / deliverables**

- Иерархия: broker/exchange/regulator/issuer/official disclosure/rating agency/audited report; reliable media только secondary context.

- Для source: authority, allowed uses, legal/technical notes, parser type, freshness SLA.

- Запрет неизвестного источника формировать strong decision без explicit review.

**Обязательная проверка**

- Source allow/deny tests; timestamp/timezone normalization.

**Exit Gate**

- Каждый material claim может сослаться на canonical evidence record.

## WP28 - Research Collector и normalization

**Цель:** Автоматизировать сбор и дедупликацию внешних материалов без LLM-зависимости.

**Результаты / deliverables**

- Fetchers/parsers для утверждённых источников; caching/rate limits; content hash.

- Instrument/issuer identity resolution.

- Document normalization с безопасным удалением active content/HTML execution.

- Не хранить больше private/public raw data, чем нужно для evidence/replay policy.

**Обязательная проверка**

- Duplicate article, changed article, broken HTML/PDF, rate limit, timeout tests.

**Exit Gate**

- Один документ не порождает множество ложных событий; raw source provenance сохранён.

**Зависимости:** WP27

## WP29 - Evidence/Claims Engine

**Цель:** Преобразовать документы в структурированный слой, который можно валидировать до использования в Risk.

**Результаты / deliverables**

- Claim types, supporting/contradicting evidence, materiality metadata, freshness, identity binding.

- Critical contradiction блокирует strong recommendation до разрешения/explicit uncertainty.

- LLM output никогда не становится evidence без source reference.

**Обязательная проверка**

-