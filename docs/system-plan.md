# Этап 2 — системная разработка Android OMNICIO

Статус: утверждённый OWNER Android/local-first pivot от 10.10.2026; реализация выпусков ещё не принята.
Этап начинается только после завершения [Android UI-этапа](ui-plan.md) версии 2.5.0.
Ровно двенадцать последовательных выпусков SYS-01–SYS-12.
Процесс разработки/проверки: [AGENTS.md](../AGENTS.md).

## Целевая архитектура

OMNICIO разделяется на два вычислительных контура.

### Android device — персональный контур

На устройстве пользователя:

- read-only T-Invest token;
- реальные счета, позиции, деньги, операции и выплаты;
- цели/резерв и другие локальные параметры;
- локальная история синхронизаций;
- персональные расчёты концентраций и сценариев;
- кэш общих аналитических профилей инструментов;
- локальные уведомления и состояние их обработки.

Базовый local-first режим не требует серверного аккаунта OMNICIO.

### Timeweb — общий контур

На Timeweb:

- разрешённые общие источники;
- отчётность и корпоративные события;
- общая аналитика эмитентов/инструментов;
- GPT/AI Gateway;
- общий каталог и версии аналитических фактов;
- entitlement/payment verification при включении подписок;
- optional push routing без брокерского токена и без сумм портфеля.

Timeweb не является обязательным хранилищем брокерского токена, баланса, позиций, операций или личной стратегии пользователя.

## Инварианты

- T-Invest token не покидает устройство в local-first режиме.
- Использовать только read-only token; write/transfer authority приложению не требуется.
- GPT не получает broker token, email/phone, номер счёта, баланс или полный портфель.
- Денежные числа, комиссии, лоты, концентрации и сценарии считает deterministic code.
- Общий анализ одного эмитента переиспользуется всеми устройствами.
- Unknown != 0.
- Stale data явно маркируются.
- Public/general T-Invest API data не ретранслируются сервером как общий публичный источник.
- Android background execution не считается гарантированным 24/7 scheduler.
- Серверные analytics-first функции не зависят от инвестиционного советника.
- Auto-selected personalized BUY/SELL/HOLD, конкретные лоты и замены остаются за regulated feature gate.
- Никаких искусственных лимитов числа позиций или капитала.
- Никаких hidden production roles/test entitlements.
- Одна production PostgreSQL сохраняется; новые копии/клоны без отдельного решения OWNER не создаются.

## Privacy model

Цель — минимизировать серверную обработку, а не объявить её отсутствующей без проверки.

Базовый local-first поток:

1. приложение получает T-Invest data напрямую на устройство;
2. локальная БД хранит portfolio data;
3. приложение запрашивает с Timeweb только общую аналитику по instrument/issuer IDs;
4. персональный расчёт происходит локально;
5. сервер не получает holdings/balance/token.

Если отдельная функция всё же передаёт серверу device push token, purchase/entitlement id, support data или иные данные, её категории/цели фиксируются отдельно.
Требования 152-ФЗ/уведомления оцениваются по фактической серверной обработке; архитектура не содержит обещания автоматического освобождения только потому, что клиент нативный.

## Legal product gate

Analytics-first production может:

- показывать фактический портфель;
- рассчитывать доли/концентрации/выплаты;
- анализировать общие публичные факты эмитентов;
- показывать существенное ухудшение;
- выполнять stress/scenario calculations;
- сравнивать варианты, выбранные самим пользователем;
- рассчитывать лоты/стоимость выбранного пользователем сценария.

Release production при закрытом regulated gate не должен:

- сам выбирать конкретный инструмент как персонально подходящий;
- давать auto-selected BUY/SELL/HOLD;
- сам определять конкретные количества покупки/продажи как персональную рекомендацию;
- назначать персональную замену проблемному активу.

Research engine для этих задач можно разрабатывать в test/research build variant и на synthetic portfolios.
Release build не должен открывать этот output локальным setting/hidden tap.
Если в будущем подтверждена регулируемая модель, активация проходит отдельный security/legal/release review.

## Последовательность версий

| Выпуск | Version name | Результат |
|---|---|---|
| SYS-01 | 3.0.0 | Локальная защищённая БД и lifecycle данных |
| SYS-02 | 3.1.0 | Прямое read-only подключение T-Invest на устройстве |
| SYS-03 | 3.2.0 | Достоверный portfolio ledger: позиции, деньги, операции и выплаты |
| SYS-04 | 3.3.0 | Общий Timeweb intelligence API и разрешённые источники |
| SYS-05 | 3.4.0 | Локальный portfolio/risk engine |
| SYS-06 | 3.5.0 | Общий issuer-risk engine и ранние сигналы ухудшения |
| SYS-07 | 3.6.0 | Scenario/candidate analytics без персональной auto-trade выдачи |
| SYS-08 | 3.7.0 | Research optimizer и regulated output gate |
| SYS-09 | 3.8.0 | Background/event orchestration и уведомления |
| SYS-10 | 3.9.0 | Timeweb AI Gateway и контролируемый GPT pipeline |
| SYS-11 | 3.10.0 | RuStore subscriptions/entitlements и тарифы |
| SYS-12 | 3.11.0 | Production hardening, observability, load/security и полный release |

## Сквозные production gates

### RuStore

- package/applicationId и release signing identity фиксируются до первой публикации;
- release key не хранится в Git;
- модерации предоставляется demo/test path без production secrets;
- приложение соответствует заявленной функциональности и не является WebView-обёрткой;
- все используемые платёжные SDK и категории собираемых данных декларируются фактически.

### Единственная PostgreSQL

- общий Timeweb analytics store остаётся одной production-БД;
- новый schema-changing release использует additive/backward-compatible миграции;
- recovery-защита не удаляется молча;
- если OWNER запрещает новые recovery copies, destructive schema changes не выполняются без отдельно принятого safety contract;
- личный портфель в local-first режиме не зависит от этой БД и не должен теряться из-за миграции общего backend.

### Права на данные

- пользовательский T-Invest token используется на устройстве в пределах его прав;
- сервер не делает публичную ретрансляцию T-Invest API;
- общий Timeweb intelligence использует только источники, для которых подтверждены нужные права автоматической обработки/показа предусмотренных результатов;
- source license/coverage/freshness хранится вместе с аналитическими фактами.

### AI

- AI Gateway имеет model/day budget;
- token usage измеряется;
- retry bounded;
- prompt injection из документов не даёт authority на денежные расчёты;
- LLM output проходит schema/semantic validation;
- отсутствие LLM не ломает локальный портфель.

### Mobile background

- WorkManager используется для deferrable/persistent work;
- точное время выполнения periodic work не обещается;
- critical general-market monitoring выполняет Timeweb;
- phone выполняет персональную проверку при sync/open/background opportunity;
- optional fast alerts используют push и не включают portfolio amounts в payload.

## SYS-01 — 3.0.0. Локальное защищённое хранилище

**Результат:** устройство может безопасно хранить локальный портфель без серверного аккаунта.

Задачи:

- Room/SQLite repository layer.
- Версионирование локальной схемы и migration tests.
- Sensitive database encryption: implementation выбирается security review; нельзя хранить портфель в открытой Room DB.
- Random database encryption key генерируется на устройстве и защищается Android Keystore.
- T-Invest token не хранится в Room/plain SharedPreferences; secret wrapping/access через Keystore.
- Состояния: new install, existing DB, migration, corrupted DB, key unavailable, user wipe.
- Export по умолчанию не содержит T-Invest token.
- Local wipe удаляет token, portfolio DB, strategy и queued personal work.
- Debug/logging не печатает holdings/token.
- Backup policy Android проверяется явно: sensitive local DB/secret не должен неожиданно попадать в cloud backup без принятого encrypted design.

Приёмка:

- извлечение APK/DB file не раскрывает token/plain portfolio;
- migration old->new не теряет fixture data;
- failed migration не открывает частично обновлённую БД;
- wipe проверен;
- process death/reboot безопасны.

## SYS-02 — 3.1.0. T-Invest read-only on-device

**Результат:** пользователь подключает свой счёт, а broker token остаётся на телефоне.

Задачи:

- ручной secure ввод/вставка token;
- проверка прав token;
- принимать только read-only/account-scoped token для production analytics;
- прямое TLS-соединение приложения с официальным T-Invest API;
- account discovery;
- выбор одного/нескольких своих счетов;
- revoke/disconnect flow;
- sandbox/test mode отдельно от production;
- structured error mapping без печати token.

Не использовать наш Timeweb как credential proxy для базового режима.

Приёмка:

- full/transfer authority отклоняется либо не принимается как analytics credential;
- revoked/expired token корректно переводит connection в disconnected;
- token никогда не появляется в Timeweb logs;
- sandbox не смешивается с production.

## SYS-03 — 3.2.0. Достоверный portfolio ledger

**Результат:** приложение различает позиции, деньги, операции, выплаты и незавершённые состояния.

Задачи:

- accounts;
- current positions;
- blocked/free quantities;
- currencies/cash;
- operations history with pagination/cursor;
- coupons/dividends/amortization/redemptions/top-ups/withdrawals;
- active/order state где доступно и необходимо для недопущения двойного бюджета;
- timestamps/source/tracking id;
- idempotent ingestion;
- correction/replay.

Расчёты:

- пополнение != доход;
- возврат номинала != целиком прибыль;
- ожидаемая выплата != доступные деньги;
- неизвестная цена != 0;
- partial fill не считается полным;
- same operation replay не удваивает деньги.

Приёмка:

- synthetic sequences top-up/buy/partial fill/coupon/redemption корректны;
- restart/replay не меняет итог;
- история может быть неполной — UI показывает это явно;
- нет торговли через API.

## SYS-04 — 3.3.0. Общий Timeweb intelligence

**Результат:** Timeweb анализирует рынок один раз для всех устройств, не зная личные портфели.

Backend хранит:

- instrument/issuer identity;
- source records;
- corporate events;
- reports;
- payouts facts;
- common market/macro facts;
- extracted structured facts;
- confidence/provenance;
- freshness;
- versioned issuer/instrument profile.

API отдаёт по instrument/issuer IDs только общие результаты.

Требования:

- canonical source IDs;
- dedup/revisions;
- source rights registry;
- immutable provenance link;
- bounded public API;
- cache headers/version cursors;
- no user portfolio endpoint in local-first mode.

Приёмка:

- один report processed once;
- duplicate/revision semantics проверены;
- клиент может получить delta после cursor;
- запрещённый источник не попадает в production pipeline.

## SYS-05 — 3.4.0. Локальный portfolio/risk engine

**Результат:** устройство самостоятельно рассчитывает структуру и сценарии.

Расчёты:

- asset class;
- issuer/group concentration;
- sector;
- currency exposure;
- maturity buckets;
- income schedule;
- overlap фонда/прямой позиции если data available;
- stale/unknown coverage;
- stress scenarios;
- local budget/reserve.

Требования:

- deterministic;
- unit-aware;
- Decimal/fixed-point where money requires;
- versioned formulas;
- same inputs -> same outputs;
- no LLM in monetary path.

Приёмка:

- fixtures 100 ₽ / 100 млн ₽;
- missing prices;
- multi-currency;
- duplicate issuer exposure;
- large portfolio;
- formula property tests.

## SYS-06 — 3.5.0. Issuer risk engine

**Результат:** система замечает подтверждённые признаки ухудшения до дефолта, не объявляя недоказанную вероятность фактом.

Общий backend оценивает:

- debt/liquidity trends;
- near-term obligations;
- cash flow;
- interest coverage;
- refinancing events;
- rating changes;
- covenant/material disclosures;
- audit/going-concern statements;
- confirmed legal/restructuring events;
- market liquidity/spread facts where licensed.

Подход отраслевой: банк/промышленность/девелопер и т.п. не используют один набор коэффициентов.

Состояния общего риска:

- normal;
- watch;
- elevated;
- critical-data-event;
- insufficient-data.

Локальный app сопоставляет общий риск с долей пользователя.

Приёмка:

- каждый существенный флаг имеет evidence;
- GPT не генерирует probability of default как факт;
- revision source может снять/изменить флаг;
- backtest включает recovery/false positives.

## SYS-07 — 3.6.0. Scenario и candidate analytics

**Результат:** пользователь может исследовать возможные изменения без auto-selected personal trade advice.

Доступно:

- общие screener/ranking по одинаковым для всех правилам;
- пользователь сам выбирает инструмент;
- приложение показывает, как выбранное изменение повлияет на его портфель;
- локальный calculator количества лотов по выбранной пользователем сумме;
- сравнение нескольких выбранных пользователем вариантов;
- сохранение scenario, но не broker order.

Не доступно при закрытом gate:

- «лучший именно для вас X»;
- «продать Y и купить X»;
- auto-selected quantities.

Приёмка:

- пользовательский выбор явно отделён от system candidate generation;
- generic rankings не используют personal profile;
- portfolio impact вычисляется локально.

## SYS-08 — 3.7.0. Research optimizer и regulated gate

**Результат разработки:** полноценный optimization engine готов к research/backtest, но запрещённый output не попадает в обычный production build.

Engine умеет на synthetic/test data:

- budget allocation;
- reserve;
- whole lots;
- transaction cost;
- concentration constraints;
- liquidity constraints;
- strategy/profile constraints;
- replacement candidates;
- wait/no-action result.

Архитектура:

- `research` build variant/test module содержит полный auto-selection output;
- `release` analytics-first build не имеет пользовательского маршрута к auto-selected BUY/SELL/HOLD;
- regulated capability не открывается local preference/developer menu;
- будущая активация требует отдельного PR, правового evidence, security review и release acceptance.

Приёмка:

- optimizer может корректно вернуть «нет допустимого решения»;
- optimal/feasible/timeout различаются;
- не расходовать деньги дважды между целями;
- research fixtures не содержат production user data.

## SYS-09 — 3.8.0. Background и события

**Результат:** приложение обновляется экономно и честно относительно ограничений Android.

Timeweb:

- два плановых общих обзора по торговому календарю;
- обработка существенных событий по поступлению;
- общий delta feed.

Android:

- WorkManager sync с network/battery constraints;
- sync при открытии;
- sync после broker connection change;
- local reevaluation после новых общих facts;
- local notifications;
- retry/backoff;
- cursor checkpoints.

Optional fast alerts:

- отдельный opt-in;
- сервер может хранить push endpoint и минимальный topic/instrument subscription;
- не хранить quantity/balance/token;
- push payload: generic event id, без суммы портфеля;
- приложение локально решает релевантность и показывает детали.

Приёмка:

- система не обещает exact periodic execution Android;
- missed background window догоняется cursor sync;
- duplicate push/sync idempotent;
- battery/data saver учитываются.

## SYS-10 — 3.9.0. AI Gateway

**Результат:** GPT усиливает общий анализ, не получает персональный портфель.

Pipeline:

1. source normalization;
2. deterministic extraction where possible;
3. dedup/chunking;
4. Luna-class model для массовой структуризации;
5. stronger model для сложных material events;
6. strict schema validation;
7. evidence linking;
8. stored common result.

Правила:

- no T-Invest token;
- no holdings/balance;
- no user identity;
- bounded context;
- max retries;
- daily/model spend caps;
- cached result reuse;
- prompt injection treated as untrusted text;
- AI failure -> common analysis marked unavailable/stale, portfolio remains usable.

Приёмка:

- one source event does not trigger per-user LLM call;
- token/cost telemetry;
- deterministic financial math never delegated to GPT;
- synthetic secret canary never leaves allowed boundary.

## SYS-11 — 3.10.0. RuStore subscriptions и entitlements

**Результат:** платные аналитические функции подключаются только после измеренного спроса.

Исходный запуск может оставаться бесплатным.

При включении оплаты:

- использовать актуальный RuStore Pay SDK, не deprecated BillingClient;
- products/subscriptions настроены в RuStore Console;
- purchase verification;
- restore purchase;
- refund/cancel/grace handling;
- server хранит минимальный opaque entitlement/purchase state, не portfolio;
- цены/период/автопродление/отмена отображаются до оплаты;
- налоговое/чековое оформление подтверждено для фактической схемы владельца;
- платёжный провайдер/SDK декларируется RuStore.

Уровни:

- Наблюдение;
- Аналитика;
- Персональный план — не продаётся при закрытом regulated gate;
- Цели и доход — только реально доступные analytics функции;
- Капитал — только реально доступные analytics функции.

Приёмка:

- duplicate callbacks не удваивают entitlement;
- refund/revoke снимает доступ корректно;
- offline entitlement имеет bounded grace;
- отсутствие покупки не блокирует базовый portfolio local-first режим.

## SYS-12 — 3.11.0. Production hardening и полный release

Проверить:

- release signing/rotation policy;
- reproducible CI build;
- dependency/SBOM scan;
- local DB migration matrix;
- Keystore loss/reinstall behavior;
- T-Invest rate/error behavior;
- backend API auth/rate limit for paid/general endpoints;
- load test general intelligence API;
- AI cost load;
- background/reboot/offline;
- RuStore push availability/no-distributor fallback;
- crash reporting с минимальными данными;
- privacy declaration;
- user data wipe;
- moderation demo flow;
- Android 8.0+ and representative current devices;
- screen sizes/font scale/accessibility;
- release rollback/halt;
- backend compatibility with previous app version.

Финальная приёмка:

- реальный read-only T-Invest работает на устройстве;
- Timeweb не получает broker token/portfolio в local-first режиме;
- общий GPT-analysis переиспользуется;
- analytics-first release не выдаёт auto-selected personal trades;
- приложение остаётся полезным без GPT и без background window;
- опубликованная RuStore версия совпадает с проверенной release build;
- ни один обязательный secret не находится в APK/Git/logs.

## Что остаётся на старом web/backend

Старый web UI не является новым пользовательским продуктом.
Минимальный web-контур может обслуживать:

- API;
- privacy/terms;
- status;
- release metadata;
- техническую документацию.

Старые email-auth/workspace endpoints удаляются или переводятся в legacy только отдельными проверенными изменениями после появления Android replacement; пользовательские данные не удаляются молча.

## Что не входит в новый scope

- iOS до отдельного решения OWNER;
- Telegram Mini App;
- web/PWA как основной клиент;
- торговые поручения/автоследование;
- transfer-access T-Invest;
- пользовательский AI chat;
- серверное хранение личного портфеля по умолчанию;
- собственная GPU-модель;
- новая production-БД/клон только ради Android;
- regulated personal trade output без отдельного подтверждённого режима.
