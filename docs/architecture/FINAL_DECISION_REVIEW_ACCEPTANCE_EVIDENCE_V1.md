# Final decision-review production acceptance evidence v1

## Назначение

PR-64 вводит immutable evidence contract для фактической production-приёмки
`GET /decision/final-review`. Контракт не выполняет deploy, не вызывает Gateway, не
изменяет GPT Editor и не проводит rollback. Он только фиксирует уже полученные
доказательства и не позволяет объявить приёмку завершённой без полного набора.

## Восемь обязательных case

1. `render_source_commit` — Render использует ожидаемый merge commit SHA.
2. `health_contract` — cache-busted `/health` подтверждает версию и read-only режим.
3. `private_auth_negative` — запрос без корректного Gateway key отклонён.
4. `exact_route_positive` — exact authenticated query вернул reviewed compact response.
5. `gpt_schema_import` — актуальная OpenAPI schema импортирована в GPT Editor.
6. `gpt_authenticated_preview` — authenticated Action выполнен в Preview.
7. `gpt_action_list` — после импорта отсутствуют write/order/funds-movement Actions.
8. `rollback_restore` — rollback drill восстановил известный read-only release.

## Статусы evidence

- `not_executed` — наблюдение отсутствует; timestamp, source и proof запрещены;
- `passed` — проверка выполнена и подтверждена датированным доказательством;
- `failed` — проверка выполнена, приложено доказательство и безопасный error code;
- `not_applicable` — допускается только как датированное manual-review решение и не
  засчитывается как завершение acceptance.

## Proof binding

Каждая выполненная строка содержит:

- timezone-aware `observed_at`;
- типизированный source: Render, Gateway, GPT Editor, rollback runbook или manual review;
- bounded safe reference без query/credential material;
- краткое безопасное summary;
- optional safe count metrics;
- canonical SHA-256 по case, status, времени, source, reference, summary, error code и metrics.

Изменение любого proof field делает digest недействительным.

## Collector

`collect_final_decision_review_acceptance_evidence(...)`:

- принимает ожидаемые commit SHA, app version и HTTPS base URL;
- принимает только уже сформированные evidence rows;
- отклоняет дубли, future timestamps, неверный source и mismatch Render commit;
- добавляет отсутствующие case как `not_executed`;
- сортирует case канонически;
- рассчитывает counters и overall status;
- не выполняет network calls и не изменяет внешние системы.

## Dependency order

`passed` допускается только последовательно:

`Render commit → health → auth negative → exact route → GPT import → GPT Preview → Action list`.

Rollback фиксируется отдельным обязательным case. Любой `failed` переводит dossier в
`failed`. Полный статус `passed` возможен только при восьми `passed`.

## Safety boundary

Во всех evidence и dossier зафиксировано:

- `collector_performed_network_calls=false`;
- `collector_changed_deployment=false`;
- `collector_changed_gpt_editor=false`;
- `contains_sensitive_material=false`;
- `contains_account_context=false`;
- `trade_authorized=false`;
- `order_created=false`;
- `execution_ready=false`;
- `trading_methods=false`.

Reference и summary отклоняются при признаках Authorization/Bearer/API key/token,
полного account context, portfolio/order/confirmation material.

## Acceptance boundary

Merge PR-64 создаёт только контракт и collector. Все восемь production case остаются
`not_executed`, пока реальные проверки не проведены и их результаты не записаны отдельным
следующим пакетом. Наличие зелёного CI для PR-64 не является production acceptance.

## Rollback

Revert PR-64. Runtime Gateway, production route, OpenAPI и PR-63 orchestration не
изменяются, поэтому функциональный rollback не требуется.
