# Omni-CIO V10 — Engineering Quality / Pre-CI / Green-Merge Amendment

Status: **OWNER-APPROVED POLICY / EFFECTIVE ONLY AFTER MERGE TO `main`**  
Date: 2026-08-16  
Scope: all remaining V10 implementation, maintenance, recovery, dependency, CI, status, OWNER-handoff and runtime-hosting-selection work.

## 1. Purpose

This amendment turns the OWNER's engineering rules into durable GitHub authority so future AI/developer sessions do not depend on chat memory.

The objective is not to make CI green by repeated small guesses. The objective is to make each branch as close as reasonably possible to correct **before** expensive exact-head CI is started, then use CI as an independent verification gate.

This amendment does not renumber Work Packages, change block weights, unlock WP23, expand broker authority, enable public multi-user mode or modify the protected V9 rollback.

## 2. Core engineering rule

For every material change use this order:

`restore authority -> understand the whole failure/scope -> inspect blast radius -> review current official dependencies/approaches -> implement root-cause fix -> add permanent regression guards -> run cheap/focused preflight -> review full diff -> run exact-head full CI -> all applicable checks SUCCESS -> review/merge -> post-merge verification -> OWNER product acceptance only if required`

CI is a verification system, not the normal interactive debugger.

No engineer/agent may claim 100% certainty that software contains no defects. The required standard is **evidence-backed readiness** before CI and **independent GREEN evidence** before merge.

## 3. Root-cause and blast-radius law

When a defect or RED check is found:

1. identify the actual root cause before changing code;
2. inspect all files/modules/workflows that use the same pattern, dependency, API, configuration or assumption;
3. determine whether the defect is local or systemic;
4. fix the defect class, not only the first failing line;
5. add deterministic regression coverage/guarding so the same defect class is harder to reintroduce;
6. inspect adjacent failure modes that reasonably follow from the root cause;
7. only then start another expensive full CI cycle.

A one-line fix is acceptable only when evidence shows the problem is genuinely one-line in scope. Small patch size is never itself proof of adequate diagnosis.

## 4. Mandatory pre-CI engineering gate

Before starting an expensive full exact-head validation cycle, the developer/agent must perform all applicable preflight work that can be done without OWNER-only actions:

- restore current `main`, current WP, accepted amendments and current contracts;
- inspect the complete branch diff against accepted `main`;
- inspect all changed files plus directly coupled consumers/producers;
- run format/lint/type/compile/static contract checks available locally or on the trusted self-hosted runner;
- run focused unit/integration/negative tests for the changed behavior;
- validate schemas, migrations, Terraform/IaC, PowerShell parsing and configuration where applicable;
- verify dependency manifests and lockfiles are synchronized;
- verify external GitHub Actions remain pinned to immutable full commit SHAs;
- perform secret/private-data checks on changed surfaces;
- verify rollback/recovery consequences;
- verify safety invariants and authority boundaries;
- search for analogous uses of any pattern that just failed;
- review the current official documentation/release/support/security state of materially changed external dependencies or APIs when that information can change over time.

The developer must not deliberately trigger a long full CI run while known preflight failures remain.

## 5. Dependency and technology law

`latest` is not automatically `best`, and `old` is not automatically wrong.

Before introducing or materially upgrading a language, runtime, framework, package, provider, Action or infrastructure component, verify as applicable:

- current official maintenance/support status;
- security advisories and known incompatibilities;
- license suitability;
- Windows/Lenovo compatibility where relevant;
- reproducible install/build and lock integrity;
- rollback/fallback;
- operational burden;
- data/secrets/privacy impact;
- measurable benefit to the owning WP.

Existing accepted components are not rewritten merely to use a newer language/framework.

A new programming language is allowed only when its owning component has a concrete correctness, security, isolation, performance or systems-integration reason and the toolchain/recovery/maintenance cost is accepted. Polyglot sprawl is forbidden.

## 6. Fault-isolation / "spider" law

Omni-CIO must be designed as bounded failure domains rather than one fragile monolith.

Where practical, component boundaries must use explicit contracts and include applicable:

- timeouts/deadlines;
- bounded retries with idempotency rules;
- circuit-breaker/backpressure semantics;
- queues/checkpoints for durable asynchronous work;
- health/readiness/freshness states;
- restart/recovery behavior;
- least-privilege process/service boundaries for high-risk components;
- graceful degradation for optional dependencies.

A failure in an optional component should not unnecessarily take down deterministic Core truth. Examples of intended behavior:

- AI unavailable -> deterministic Core remains usable and AI state is explicit DEGRADED/OFFLINE;
- Research unavailable -> portfolio/Core remain usable and research freshness becomes explicit;
- Telegram unavailable -> Web/Core remain usable;
- external Web ingress unavailable -> local Personal Node/recovery remain usable;
- broker READ unavailable -> last verified snapshot may be shown only with explicit STALE/OFFLINE semantics; no fabricated freshness.

Money/security authority remains fail-closed. Graceful degradation must never mean weakening broker, identity, secret or Real-execution controls.

## 7. Exact-head GREEN merge law

A V10 implementation/maintenance PR may be merged only when the **current exact head SHA** satisfies all of the following:

- every applicable V10 check has actually run and concluded `success`;
- no applicable check is `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` or `skipped`;
- zero unresolved blocking review threads;
- complete diff review against the accepted base;
- no known unresolved P0/P1 defect in scope;
- required security/recovery/evidence gates are present.

Project policy is intentionally stricter than GitHub's generic status semantics: `skipped` and `neutral` are **not** accepted as GREEN evidence for an applicable Omni-CIO V10 gate.

If a workflow is genuinely irrelevant to a branch/WP, the correct fix is to make its trigger/routing non-applicable so it does not appear as a misleading check. Do not call a skipped/cancelled check PASS.

Infrastructure/billing/provider startup failures are not code failures, but while the check is red they still block merge under this OWNER policy. The engineering task is to restore the check, route to an accepted fallback, or correct the workflow applicability — never to merge around red evidence.

Any code/config/document commit after a GREEN cycle creates a new exact head and invalidates the previous final merge evidence. Run the required cycle again.

## 8. No premature PR close / merge

Do not close a feature/implementation PR merely because the code exists or because an alternative branch was started.

Normal successful closure is:

`all applicable exact-head checks GREEN -> final diff/review -> squash merge -> PR closed by merge`.

An unmerged PR may be closed only when explicitly superseded/abandoned for a documented reason. It must never be represented as accepted implementation.

## 9. OWNER participation boundary

Before the implementation PR is merged and its required post-merge verification is GREEN, do **not** ask the OWNER to perform product acceptance such as:

- phone/browser walkthroughs;
- login/logout acceptance;
- visual/UX acceptance;
- portfolio/data comparison;
- ordinary runtime rehearsal that CI/engineering can perform;
- manual tests whose only purpose is to compensate for unfinished branch code.

Pre-merge OWNER participation is permitted only for a genuinely non-delegable **prerequisite** needed to make the engineering branch verifiable, for example:

- external account/consent bootstrap;
- domain purchase/ownership decision;
- creation/storage of a narrowly scoped credential that cannot be created safely by automation;
- UAC/admin/firmware/BitLocker/physical action;
- explicit OWNER decision reserved by the Master Plan;
- payment approval for an OWNER-approved necessary dependency.

When such a prerequisite is needed, ask for exactly that prerequisite and stop OWNER involvement there. Do not combine it with premature product acceptance.

OWNER product acceptance happens only after:

`implementation PR merged -> exact new main verified -> required post-merge Regression Shield GREEN`.

If post-merge OWNER acceptance finds a defect, create a new focused fix branch/PR. Do not patch `main` directly.

### 9.1 Direct-link-first OWNER handoff law

Whenever OWNER participation is genuinely required, engineering must make the handoff deterministic. The canonical handoff standard is `docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md`.

Before asking the OWNER to click or change anything in GitHub, Cloudflare, a broker/provider, billing, domain/account, consent or another browser surface:

- verify current official provider UI/docs when navigation can change;
- provide a direct official HTTPS link to the exact stable page when such a stable link exists;
- do not make the OWNER discover the target page from vague instructions such as “open Settings” or “find Billing”;
- if an exact deep link cannot be verified, state that fact and provide the closest verified official start URL plus the exact click path;
- identify the exact account/repository/workspace/service/device scope;
- give one bounded action at a time;
- state the expected result, explicit STOP conditions, adjacent actions that must not be taken and the minimum safe non-secret result to return;
- state cost/authority consequences before any payment, paid plan, public exposure, credential scope or irreversible change is confirmed.

Secret-bearing, shortened, third-party redirect or private-runtime links are forbidden in OWNER handoffs.

### 9.2 Personal-Node runtime / Render boundary law

For V10, the approved Lenovo/replacement Personal Node remains the primary Web/API/application runtime host. Source-controlled V10 Web assets are built/rendered/served there according to the owning deployment contract.

A separate paid general-purpose cloud application host is not required for normal V10 operation. In particular:

- Render.com is **not** the V10 runtime target;
- an empty/new Render.com workspace is not Omni-CIO authority;
- do not create a new Render.com V10 Web Service, worker, database, deployment target or paid plan without a later explicit OWNER-approved amendment;
- the existing Render.com `app:app` service remains the protected V9 production/recovery baseline until the responsible V10 parity/decommission gate;
- an external-access provider selected by WP22A is access/security transport to the Personal-Node origin, not a second application/private-state host.

The local V10 rendering/serving model must not be confused with the commercial Render.com service.

## 10. Failure-learning law

A material RED result that occurs after the branch was considered preflight-ready requires a short engineering confidence postmortem before the next expensive retry.

Record non-secret learning in `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md` when the failure class is reusable. Each entry must contain:

- symptom/failing gate;
- root cause;
- blast radius searched;
- why preflight did not catch it;
- corrective change;
- permanent regression/guard;
- prevention rule for future WPs;
- whether dependency/tooling knowledge changed.

The ledger is not a blame log. It is an engineering memory designed to prevent repeated failures across chats, agents and developers.

Do not record secrets, private portfolio payloads, raw OWNER identities or sensitive machine identifiers in the ledger.

## 11. Evidence before confidence

Before stating that a branch is ready for final CI, the developer/agent should be able to point to concrete evidence such as:

- clean focused tests;
- static/type/format checks;
- dependency/lock validation;
- relevant official documentation review;
- negative/failure tests;
- full-diff review;
- regression guard for the defect just fixed.

Statements such as "probably fixed", "only one line changed", "it passed on the previous SHA" or "the red job is probably infrastructure" are not merge evidence.

## 12. CI efficiency law

The preferred validation funnel is:

`cheap deterministic checks -> focused changed-surface tests -> broader local/self-hosted preflight -> full exact-head PR gates -> post-merge Regression Shield`.

Do not intentionally consume a long CI cycle to discover errors that deterministic preflight could have found cheaply.

Do not reduce test coverage, disable security checks, suppress real failures, weaken timeouts, remove negative tests or mark jobs `continue-on-error` merely to save CI time.

## 13. GitHub enforcement surfaces

This policy must be reflected in GitHub through multiple independent surfaces rather than one prose file:

- Amendments Index;
- `AGENTS.md`/agent instructions;
- `.github/copilot-instructions.md` plus repository modular instructions;
- PR template;
- mandatory WP execution template;
- machine-readable quality contract;
- OWNER Action Handoff & Local Runtime Standard;
- failure-learning ledger;
- repository/CI governance guard;
- deterministic regression tests;
- exact-head CI and post-merge Regression Shield.

Repository automation may enforce only facts it can actually observe. Human/agent review remains required for root-cause quality, full-diff reasoning, current provider UI verification and whether an OWNER action is truly non-delegable.

## 14. Protected invariants

This policy never permits weakening:

- `app:app` protected V9 compatibility;
- `trading_methods=false` for current V10 non-execution surfaces;
- `REAL_TRADING_ENABLED=false` until the owning later WP explicitly changes the accepted state;
- READ/Sandbox/TRADE credential separation;
- no transfer/withdrawal authority;
- private durable state / GitHub source / runtime secret separation;
- protected V9 rollback;
- current Master Plan WP ordering.

## 15. Acceptance

This amendment becomes active authority only after its focused governance PR itself obeys the rule it introduces: exact-head applicable checks must be GREEN, review must be clean, it must be squash-merged to `main`, and required post-merge verification must succeed.

Until then, existing accepted `main` remains authority and the current WP22A implementation PR remains unaccepted.
