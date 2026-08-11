# Omni-CIO V10 WP16 — Web Design System Execution Contract

Status: **WP16 IMPLEMENTATION CONTRACT / EXIT GATE PENDING**  
Block: **E — Omni-CIO Web Platform**  
WP: **16 — Web Design System**

## 1. WP identity

- Authorized by current program status: **YES**.
- Prior accepted `main`: `c557dd1f3441a21619edaae1928965d0bacc51b1`.
- Prior gate: WP15 implementation/code/security accepted; status PR #279 merged; post-status Regression Shield #1462 / run `31421676262` succeeded on exact `main`.
- Block D live broker acceptance remains deferred to WP17 and Block D credit remains withheld.

## 2. Accepted baseline

Protected runtime remains V9 `app:app` with `trading_methods=false` and `REAL_TRADING_ENABLED=false`.

WP16 is governed by:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/architecture/REPOSITORY_STRUCTURE.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.md` and `.json`;
- `docs/architecture/V10_REGRESSION_SHIELD.md`;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`.

## 3. Purpose

Create the single reusable visual/component foundation for the one source-controlled Omni-CIO Web App at `apps/web/`. WP16 owns presentation primitives only and does not implement WP17 application-shell business flows.

## 4. Inputs and prerequisites

- canonical Web root `apps/web/` reserved by WP1;
- accepted WP2 frontend baseline: Node 24.18.0, npm 11.16.0, React/React DOM 19.2.8, Vite 8.1.5, TypeScript 7.0.2 and package-lock v3;
- Lenovo `omni-cio-ci` authoritative Windows runner;
- accepted repository/security/Regression Shield contracts;
- no broker credential or private portfolio input is required.

## 5. Existing implementation to reuse

WP16 uses **REUSE_AS_IS** for the WP2 Node/npm/React/Vite/TypeScript baseline and existing CI/repository boundaries. It creates the first product Web package rather than copying the WP2 smoke fixture. It reuses the canonical operational vocabulary from accepted Core contracts rather than creating Web-specific financial state meanings.

Playwright Test is an exact-pinned **test-only** addition for browser evidence. It does not become product runtime authority or a second browser/application stack.

## 6. Allowed changes

WP16 may change only what is required for the design-system Exit Gate, principally:

- `apps/web/` design-system source, package/lock/build/test configuration and synthetic gallery;
- Web-specific CI/guard integration;
- repository ignore/security/toolchain guards needed to protect the new canonical Web package;
- this WP16 execution contract and associated deterministic tests.

## 7. Explicit non-goals

WP16 does **not** implement:

- WP17 navigation/application shell or route business flows;
- Telegram/VK authentication runtime, sessions or public registration;
- broker credential provisioning or deferred WP15 live evidence;
- WP18 real portfolio dashboard/data integration;
- public Internet ingress;
- Telegram product runtime or Cortex/AI;
- broker write, transfer/withdrawal or Real execution authority.

## 8. Interfaces/contracts

The reusable interface is the source-controlled design system under `apps/web/src/design-system/`:

- semantic tokens: typography, spacing, surfaces, focus, operational state and risk severity;
- reusable component primitives: cards, tables, chart frame, dialogs, drawers, buttons, badges, fields, toasts, skeletons and empty/error/warning states;
- canonical operational vocabulary: `READY | PARTIAL | STALE | DEGRADED | BLOCKED | ERROR | OFFLINE | RECOVERING | OWNER_ACTION_REQUIRED`;
- risk vocabulary: `LOW | MEDIUM | HIGH | CRITICAL`;
- responsive acceptance matrix: 360 / 768 / 1440 px.

WP17+ pages must consume these primitives/tokens instead of creating random local visual patterns.

## 9. Data/persistence effects

- database migration: **NO**;
- private-data migration: **NO**;
- broker/account state: **NO ACCESS**;
- gallery data: synthetic only;
- browser credential storage: forbidden;
- backup/recovery consequence: source and deterministic npm lock remain recoverable from GitHub; generated build/test artifacts are disposable.

## 10. Security/authority effects

WP16 does not change broker, OS, authentication, public-ingress, AI or Real-money authority.

Permanent Web source guards forbid raw HTML injection helpers, `eval`, browser Web Storage for credentials, suppression directives and direct Real-authority references. External GitHub Actions remain full-SHA pinned. Raw broker/Telegram/VK secrets, private investment payloads and full account IDs are forbidden from source, logs and artifacts.

## 11. Normal-path acceptance tests

Exact reviewed head must prove:

- exact Node/npm identity and npm lock reproducibility;
- strict TypeScript typecheck;
- Web source lint contract;
- deterministic Node unit contracts;
- Vite production build;
- Playwright browser smoke against the production-build preview;
- responsive structural assertions and screenshot evidence at 360/768/1440;
- keyboard focus and accessible label/status smoke;
- reduced-motion behavior;
- dependency audit and approved registry/license policy.

## 12. Negative/failure tests

Applicable fail-closed checks include:

- unknown operational state rejected by the type/contract guard;
- missing or drifting package lock rejected;
- direct/floating/unreviewed dependency source rejected;
- Web Storage, unsafe HTML/eval and direct Real-authority references rejected;
- browser test failure or missing supported browser fails the focused gate;
- layout mismatch at any required viewport fails browser evidence;
- repository/security/Regression Shield regression blocks acceptance.

No skipped stage is counted as PASS.

## 13. Observability and evidence

CI output may contain only non-secret dependency/build/test metadata. Short-lived WP16 evidence contains the reviewed lock candidate and synthetic visual test results/screenshots. No portfolio/account/broker-secret evidence belongs in WP16 artifacts.

## 14. CI routing

- Fast hosted lane: Web typecheck/lint/unit/build when GitHub-hosted Actions can start.
- Hosted Windows clean-room: required for frontend compatibility when available.
- Lenovo authoritative lane: required for repository/regression/security and the focused WP16 browser gate.
- GPU AI evaluation: **NO**.
- release/recovery matrix: no release deployment; protected V9 Regression Shield remains mandatory.

GitHub billing/spending-limit startup failures are infrastructure failures, not PASS and not code failures. They do not permit weakening the required Lenovo gate.

## 15. Rollback/recovery

Before merge, rollback is branch-only deletion/reversion. After merge, the source-controlled design system and lock can be reverted by normal reviewed Git history without changing V9 production runtime, PostgreSQL/private data, broker secrets or Real authority. Generated `dist/`, `node_modules/`, Playwright output and screenshots are disposable and must not be authoritative runtime state.

## 16. Exit Gate

WP16 is COMPLETE only when the exact final reviewed head proves all of the following:

1. committed package-lock v3 is reproducible under exact npm 11.16.0;
2. registry/license/dependency policy is GREEN;
3. typecheck, lint, unit and production build are GREEN;
4. Playwright accessibility/keyboard/reduced-motion and 360/768/1440 responsive/screenshot evidence is GREEN on Lenovo;
5. canonical repository/security/Regression Shield remains GREEN;
6. no WP17+ business/auth/broker/Real scope was introduced;
7. full diff is reviewed with zero unresolved blocking threads;
8. PR is squash-merged with exact-head guard;
9. post-merge Regression Shield succeeds on the exact new `main` SHA.

## 17. Required acceptance evidence

Record exact final PR head, authoritative Self-Hosted run, focused WP16 browser run, dependency/security evidence, changed-file scope, review-thread state, squash merge SHA and exact-main post-merge Regression Shield. Visual evidence is synthetic and retained only as short-lived CI evidence.

## 18. Documentation/status updates

This contract changes with implementation when its acceptance assumptions change. Formal program status is updated only after the implementation merge and post-merge Regression Shield are GREEN, using the established status-only PR discipline.

## 19. Next WP unlock

**WP17 — Application Shell and navigation** remains LOCKED until the WP16 Exit Gate above is fully accepted and the resulting status transition is itself merged and regression-verified. Starting WP17 does not by itself credit Block D or unlock WP18 real-data acceptance.

## 20. Scope-discovery rule

Any work discovered outside this Exit Gate is classified as a current WP16 blocker/defect, future-WP work or OWNER-approved amendment. It is not silently implemented in WP16.
