# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-07-29  
Фактическая вершина программы после merge этого пакета: **PR-56**  
Точная версия определяется текущей вершиной ветки `main`.

## Назначение документа

Этот файл является краткой оперативной картой текущего состояния программы.
Он имеет приоритет для определения активного этапа, если
`knowledge/00_PROJECT_MASTER_CONTEXT.md` содержит более ранний номер PR.
Стратегические правила, безопасность, цели и Definition of Done продолжают
определяться master-context и `AGENTS.md`.

Код в `main` остаётся окончательным источником истины.

## Текущий режим

Сохраняются без исключений:

- `trading_methods=false`;
- GET-only пользовательские Gateway Actions;
- Render entrypoint `app:app`;
- отсутствие создания, отправки, замены и отмены заявок;
- отсутствие переводов и вывода денег;
- отсутствие margin, short и derivatives execution;
- работа только через отдельную ветку и Pull Request;
- squash merge только после полного Regression Shield.

## Завершённые базовые контуры

### P0 — безопасность и воспроизводимость

Завершены и находятся в `main`:

- Telegram runtime retirement;
- broker SDK read-only allowlist;
- запрет mutating Actions и торговых SDK-вызовов;
- hash-locked dependencies;
- Ruff, formatting, mypy и coverage gates;
- dependency audit, SAST и secret scan;
- стабильный `app:app` и GET-only release contract;
- маскирование счёта и запрет секретов в GitHub.

### P1 — аналитический backend

Реализованы versioned read-only слои для:

- portfolio, cash, operations и broker-report reconciliation;
- provenance, timestamps, completeness и quality gates;
- portfolio analytics, concentration, stress и conservative risk policy;
- market reference, quotes, liquidity, ratings и corporate events;
- safe news sanitation, deduplication и citation-backed retrieval;
- equity, bond и fund evidence assessments;
- OHLCV technical-indicator evidence;
- Decision Engine с обязательным no-action/abstain;
- threshold rebalancing;
- purchase и sell pre-trade previews;
- shadow и paper workflows;
- authenticated/encrypted paper ledger, backup, restore и DR readiness;
- purged walk-forward planning, OOS performance и statistical stability;
- market-capacity assessment и capacity-aware decision gating;
- unified homogeneous buy/sell pre-trade review envelope;
- account-aware portfolio-risk/pre-trade explanation envelope;
- tamper-evident pro-forma risk/intention binding;
- compact user-safe final review response и shadow parity validation;
- auditable final-response release-eligibility assessment для будущего
  GET/read-only contract review;
- fixed final-review GET Action candidate и OpenAPI shadow validation через
  существующий read-only release guard;
- exact final-review read-only query/input binding без request body и без
  credential/execution/mutation/transfer/withdrawal surface.

## Последняя завершённая цепочка PR

### PR-44

Market-capacity assessment: ADV, top-of-book depth, execution window,
spread/impact proxy и whole-lot safe capacity.

### PR-45

Capacity-aware decision gate: полное покрытие затронутых инструментов,
freshness и fail-closed no-action.

### PR-46

Exact capacity-intent binding: сторона, валюта, лоты, размер лота, цена,
execution window, units и notional должны совпадать без подстановок.

### PR-47

Purchase-side composition с `PreTradePreviewV1`: affordability,
commission integrity и точная привязка брокерского preview без создания
заявки.

### PR-48

Sell-side composition с `SellPreTradePreviewV1`: position availability,
open-order checks, tax basis, commission integrity и exact intent binding.
Брокерские gross/net proceeds не пересчитываются gate, чтобы не нарушать
правила номинальной цены облигаций и НКД.

### PR-49

Канонический оперативный status-файл добавлен в обязательный порядок чтения,
чтобы устаревший номер этапа в стратегическом master-context не направлял
новых агентов к уже завершённому PR-03.

### PR-50

Unified directional pre-trade review принимает ровно один однородный buy- или
sell-source gate, блокирует смешивание направлений и сохраняет полный исходный
gate без пересчёта брокерских значений и без исполнения.

### PR-51

Risk/pre-trade explanation envelope объединяет консервативную risk evaluation
и directional review, сверяет маскированный account context, freshness и пять
канонических слоёв, показывает первый блокирующий слой и всегда сохраняет
`risk_change_approval_confirmed=false` до отдельной pro-forma привязки.

### PR-52

Pro-forma risk/intention binding связывает отдельную post-change risk evaluation
с точным option, маскированным счётом, однородным направлением и полным набором
`CapacityOrderRequestV1` через детерминированный SHA-256 fingerprint. Даже
подтверждённая risk-привязка остаётся review-only: `trade_authorized=false`,
`execution_ready=false`, `trading_methods=false`.

### PR-53

Final decision-review response формирует компактный user-safe payload с
маскированным счётом, exact intent lines, current/pro-forma risk, blockers,
warnings и очищенной provenance без `source_id`. Internal shadow validation
проверяет паритет status, readiness, option/action, direction, account,
fingerprint, risk approval и safety flags. Публичный route не добавляется.

### PR-54

Final-response release eligibility строит canonical JSON и SHA-256, требует
совпадающий shadow result, проверяет schema `1.0`, account masking, payload и
count bounds, provenance, sensitive-data, execution/mutation surface и точный
HTTP method `GET`. Eligibility не является route approval: route, OpenAPI и
торговые флаги остаются выключены.

### PR-55

Final-review GET Action candidate фиксирует `/decision/final-review`,
`getFinalDecisionReview`, private API-key auth и response contract `1.0`.
OpenAPI shadow добавляет candidate только в deep-copy текущей схемы, повторно
запускает существующий read-only release validator, требует ровно один новый
GET Action и доказывает неизменность всех существующих Actions. Production
route и OpenAPI не меняются.

### PR-56

Final-review read-only input binding формирует минимальный query-only context,
связывает его с точным masked account, requested/final option, intent
fingerprint, ordered instrument set, PR-53 response SHA-256 и PR-55 candidate
SHA-256. Отдельные gates проверяют freshness, размер, instrument count, отсутствие
request body, credentials, execution, mutation, transfer и withdrawal fields.
Production route и OpenAPI не меняются.

## Что остаётся до полного релиза по мастер-плану

### Backend и orchestration

- единый production-route readiness dossier до добавления final-review route;
- production-grade live ingestion для market, ratings, news и corporate events;
- внешний versioned RAG index с freshness и citation controls;
- более полная observability, alerting и operational runbooks.

### Web cabinet

- найти и зарегистрировать исходный frontend существующего сайта;
- не создавать дубликат frontend;
- реализовать безопасный HTML-импорт СберИнвестиций без OCR;
- архив, сравнение периодов, расхождения, мобильный UI и обе темы;
- проверить существующий production site и все интерактивные элементы.

### Release acceptance

- синхронизировать master-context, README, inventory и file index;
- провести финальную сверку GPT Editor, Render и Gateway production health;
- выполнить end-to-end read-only acceptance на реальных, но не сохраняемых
  данных пользователя;
- подтвердить rollback и incident procedures.

### Торговые этапы

Shadow, paper и preview инфраструктура не являются разрешением на реальную
торговлю. Confirm-before-trade, idempotency, TTL confirmation, kill switch,
partial-fill и timeout reconciliation требуют отдельной программы допуска и
отдельного решения владельца.

Полностью автономная торговля без подтверждения не планируется.

## Следующий рекомендуемый пакет

**PR-57 — final-review production-route readiness dossier v1**:

- объединяет PR-53 response, PR-54 eligibility, PR-55 OpenAPI shadow и PR-56
  input binding в один auditable dossier;
- повторно проверяет schema/digest/account/option/fingerprint parity;
- требует документированные rollback, observability и authentication controls;
- выдаёт только `ready_for_route_review`, а не автоматическое route approval;
- не добавляет route, не меняет OpenAPI и не разрешает торговлю.

## Запрет ложного завершения

Проект не считается полностью завершённым только потому, что отдельный PR
слит или CI зелёный. Финальная фраза завершения разрешена только после
закрытия всех согласованных пакетов, production acceptance и отдельной
проверки полного Definition of Done.
