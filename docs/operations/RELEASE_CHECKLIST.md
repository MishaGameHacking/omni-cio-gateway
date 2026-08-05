# Omni-CIO release / maintenance checklist

Current applied GPT: **v9.0.0**. Protected rollback: **v8.6.1**. WP0–WP15 is complete; use this checklist for maintenance/security/dependency releases or a future owner-approved program.

## 1. Scope

- [ ] `main` актуален.
- [ ] Open PR/Issues проверены.
- [ ] Branch создана от current `main`.
- [ ] Прочитаны `AGENTS.md`, `knowledge/16_CURRENT_PROGRAM_STATUS.md` и профильный source of truth.
- [ ] Изменение относится непосредственно к Omni-CIO product/runtime/security/maintenance.
- [ ] Один логический scope на PR.
- [ ] Нет competing roadmap/duplicate GPT/Gateway/scheduler.

## 2. Runtime / authority contract

- [ ] Gateway entrypoint остаётся `app:app`.
- [ ] Production read-only broker credential остаётся read-only и не используется как Real fallback.
- [ ] Legacy `trading_methods=false` marker сохраняется.
- [ ] Effective OpenAPI содержит только reviewed operationIds/methods/paths.
- [ ] Baseline 14 GET Actions сохранены, если contract явно не меняется reviewed change.
- [ ] Sandbox surface либо отсутствует, либо является полным reviewed virtual set.
- [ ] Real surface либо отсутствует/status-only fail-closed, либо является полным reviewed set.
- [ ] Consequential mutation Actions сохраняют `x-openai-isConsequential: true`.
- [ ] Нет unreviewed withdrawal/transfer, margin/short, MARKET/BESTPRICE, stop/replace/async surface.
- [ ] Watchtower scheduler/callback routes остаются hidden from GPT OpenAPI.
- [ ] Account ID маскирован.
- [ ] Secrets/private broker payloads отсутствуют в diff.
- [ ] OpenAPI schemas совместимы с GPT Actions.
- [ ] Internal v9 module не публикуется/не заявляется как Action без explicit reviewed operationId.

## 3. Real execution safety if touched

- [ ] Separate `TINVEST_TRADING_TOKEN` boundary preserved.
- [ ] `REAL_TRADING_ENABLED=false` remains safe master rollback.
- [ ] Prepare and execute remain separate owner turns.
- [ ] Exact confirmation binds immutable proposal/plan context.
- [ ] Fresh market/account/funds/position/hard-cap preflight repeated before submit.
- [ ] One-submit idempotency preserved.
- [ ] Ambiguous possible-submit never auto-retries.
- [ ] Submitted is not treated as filled without broker proof.
- [ ] No new Real order is executed merely for CI/configuration acceptance.

## 4. Runtime/dependencies

- [ ] Current `app.py` dependencies not removed without separate compatibility proof.
- [ ] Dependency `.in` source is changed intentionally.
- [ ] Generated locks are regenerated, not hand-edited.
- [ ] Runtime/dev locks remain pinned + hashed.
- [ ] Generated Windows projections are not committed.
- [ ] External GitHub Actions are pinned to full SHA.
- [ ] Dependabot proposal is rebased/tested against current `main`.
- [ ] Major runtime/SDK update receives compatibility review.
- [ ] Known-incompatible toolchain update is held/documented rather than weakening CI.

## 5. Tests / Regression Shield

- [ ] `python scripts/check_repository_layout.py`.
- [ ] `python scripts/check_ci_security_baseline.py`.
- [ ] `python scripts/check_gpt_recovery_consistency.py` when GPT/recovery sources are touched.
- [ ] Ruff lint.
- [ ] Ruff formatting baseline.
- [ ] mypy.
- [ ] compileall.
- [ ] pytest + required branch coverage.
- [ ] dependency audit.
- [ ] SAST/Bandit policy.
- [ ] secret scan.
- [ ] relevant happy/partial/error paths.
- [ ] relevant broker-boundary/idempotency/recovery tests.
- [ ] exact-head Regression Shield fully green.
- [ ] no unresolved review threads.

## 6. Documentation/configuration

Update only affected sources of truth:

- [ ] `README.md` if usage/architecture/applied state changes.
- [ ] `AGENTS.md` if development/maintenance boundary changes.
- [ ] `SECURITY.md` if security/authority boundary changes.
- [ ] `knowledge/00_PROJECT_MASTER_CONTEXT.md` for long-lived architecture/boundary changes.
- [ ] `knowledge/16_CURRENT_PROGRAM_STATUS.md` for applied/accepted status.
- [ ] relevant `docs/architecture/` contract/ADR.
- [ ] relevant `docs/operations/` runbook.
- [ ] `gpt/` only when GPT configuration/behavior/recovery/Action contract changes.

Do not create duplicate setup/inventory/audit sources when an existing canonical file should be updated.

## 7. Pull Request / merge

- [ ] PR explains purpose, changes, safety, tests and post-merge acceptance.
- [ ] Head SHA fixed before final decision.
- [ ] No unresolved review threads.
- [ ] No merge conflicts.
- [ ] Required exact-head checks belong to the same head SHA.
- [ ] Squash merge used for maintenance/release package.
- [ ] Remaining open dependency PRs are rebased after `main` changes before their own merge.

## 8. Production Gateway acceptance

After runtime/deployment/Action-authority change:

- [ ] Render deploy uses expected accepted `main` commit.
- [ ] `https://omni-cio-gateway.onrender.com/health` is healthy.
- [ ] Deployed app/OpenAPI version is expected.
- [ ] `app:app` remains stable.
- [ ] `trading_methods=false` marker remains.
- [ ] auth-negative request is rejected where applicable.
- [ ] required auth-positive read endpoint works where applicable.
- [ ] Live Gateway Authority Acceptance passes public `/health` + `/openapi.json` checks.
- [ ] No live protected broker Action is called solely to prove deployment health.

## 9. GPT acceptance

Required only if Instructions/Knowledge/Actions/model/capabilities or their applied contract changes.

- [ ] Edit the **existing** GPT; do not Create a duplicate.
- [ ] Name/config from `gpt/CONFIGURATION.md`.
- [ ] Instructions from `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt` unless a newly reviewed canonical version explicitly replaces it.
- [ ] Knowledge equals exact `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md` set without duplicates unless a new reviewed manifest replaces it.
- [ ] Actions ON / Apps OFF.
- [ ] Supported non-Pro Action-capable model selected.
- [ ] Production OpenAPI refreshed if contract changed.
- [ ] Action list checked against `gpt/ACTIONS_CATALOG.md` and effective OpenAPI.
- [ ] Bearer authentication configured without recording the value.
- [ ] `gatewayHealth` exact-action isolation.
- [ ] portfolio/cash/analytics tool-first smoke.
- [ ] advisory prompt does not become Real proposal/submit.
- [ ] internal Watchtower/journal/optimizer explanation does not fabricate server execution.
- [ ] Real readiness request calls status only and does not prepare/execute.
- [ ] account ID masked and MSK visible time preserved.
- [ ] Preview accepted before `Update`.
- [ ] non-secret owner evidence recorded after `Update`.

Current v9.0.0 acceptance already completed these checks; maintenance changes that do not alter GPT-visible state do **not** require repeating editor Update.

## 10. Rollback

- [ ] Previous accepted GitHub commit is known.
- [ ] Render rollback path is known.
- [ ] `REAL_TRADING_ENABLED=false` is available before/while investigating Real safety anomalies.
- [ ] `WATCHTOWER_ENABLED=false` is available for Watchtower rollback.
- [ ] Protected GPT v8.6.1 recovery assets remain present.
- [ ] Current v9 recovery assets remain present.
- [ ] Secrets are not rotated casually or stored in recovery docs.

Green CI does not replace real external acceptance when a change actually modifies deployed/GPT state. Conversely, dependency/documentation maintenance that preserves the applied GPT contract does not require a new GPT Editor update.
