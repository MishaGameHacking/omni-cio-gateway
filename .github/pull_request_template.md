## Что изменено

Опишите одну логическую цель и затронутые файлы.

## Причина / source of truth

Какую проблему Omni-CIO решает изменение, почему оно нужно сейчас и каким current source of truth подтверждён defect/scope?

## Scope

- [ ] Изменение относится непосредственно к существующему Omni-CIO GPT/Gateway, данным, безопасности, тестам, эксплуатации или документации.
- [ ] Не создаётся duplicate bot/Gateway/frontend/scheduler/broker stack или parallel setup/configuration source.
- [ ] Учтено, что WP0–WP15 завершены; feature work вне maintenance требует отдельной owner-approved программы.

## Authority / безопасность

- [ ] Stable Render entrypoint `app:app` сохранён либо приложен отдельный approved migration plan.
- [ ] Production read-only credential не используется как fallback для Sandbox/Real execution.
- [ ] Sandbox остаётся virtual/isolated.
- [ ] Если затронут Real contour, сохранены reviewed prepare → new-turn exact owner confirmation → execute → broker reconciliation, one-submit idempotency и fail-closed semantics.
- [ ] Не добавлены transfer/withdrawal, margin/short, MARKET/BESTPRICE, stop/replace/async, token-management или autonomous recurring real-money authority без отдельной approved program/threat model.
- [ ] Internal engine не объявляется GPT Action без operationId в effective production OpenAPI.
- [ ] Account IDs остаются masked.
- [ ] В diff нет token/key values, Authorization headers, full account IDs или private broker payloads.
- [ ] Валюты не агрегируются без verified FX + timestamp.
- [ ] Partial/stale/truncated/contradictory data не выдаются за complete/current.

## OpenAPI / GPT

- [ ] OpenAPI/operationId не изменены, **или** изменение явно описано и reviewed.
- [ ] Если меняется applied GPT configuration/Knowledge/Action contract, указано, что после merge требуется owner Preview + `Update` на **том же** GPT.
- [ ] Если GPT-visible state не меняется, это явно отмечено как backend/doc-only maintenance.

## Тесты / guards

- [ ] `python scripts/check_repository_layout.py`
- [ ] `python scripts/check_ci_security_baseline.py`
- [ ] `python scripts/check_gpt_recovery_consistency.py` (если применимо/входит в текущий gate)
- [ ] Ruff / formatting / mypy
- [ ] compileall
- [ ] pytest + required branch coverage
- [ ] dependency audit / SAST / secret scan
- [ ] exact-head Regression Shield
- [ ] unresolved review threads = 0

Результаты:

```text
вставьте краткий результат / ссылки на exact-head runs
```

## Контракты и документация

- [ ] Обновлены только затронутые canonical docs; не создан competing source of truth.
- [ ] `knowledge/16_CURRENT_PROGRAM_STATUS.md` обновлён, если изменился accepted/applied status.
- [ ] `gpt/` обновлён только если менялись Custom GPT configuration/behavior/Actions/recovery.
- [ ] `CHANGELOG.md` обновлён, если это release/program/maintenance milestone.
- [ ] Если менялись dependencies, `.in` constraints и generated hash locks согласованы.
- [ ] External GitHub Actions pinned full SHA.
- [ ] Historical issue/PR statements не используются как current state вместо accepted `main`.

## После merge

- [ ] Для backend change проверен deployed Render commit и соответствующий safe smoke (`/health`, `/openapi.json` или профильный runbook).
- [ ] Для OpenAPI/GPT-visible change выполнена отдельная owner Preview/`Update` acceptance на existing GPT.
- [ ] Для doc-only change подтверждено, что external GPT update не требуется.
- [ ] Известен rollback path (`REAL_TRADING_ENABLED=false`, `WATCHTOWER_ENABLED=false`, protected v8.6.1 GPT rollback или профильный rollback — по scope).
