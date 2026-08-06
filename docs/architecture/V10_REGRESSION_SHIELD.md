# Omni-CIO V10 — Regression Shield and Hybrid CI Protection Contract

Status: **PRE-WP4 GITHUB INFRASTRUCTURE HARDENING / NO PRODUCT FEATURE WORK**  
Scope: GitHub Actions, repository protection and CI continuity only  
Protected runtime: current V9 `app:app` remains unchanged until an owning later WP intentionally migrates it

## 1. Purpose

The repository uses a hybrid CI model so GitHub Pro accelerates development without becoming a single point of failure.

The contract is layered:

1. **Fast PR Checks** run in parallel on GitHub-hosted Linux for quick repository/policy/frontend feedback.
2. **V10 Toolchain Compatibility** runs on clean GitHub-hosted Windows and proves the selected Python/Node baseline.
3. **Self-Hosted Windows CI** runs on the OWNER Lenovo. Its `V10 authoritative merge gate` job independently covers the mandatory regression, security, V10 toolchain and frontend compatibility surface required to merge. Its `Windows runner smoke test` job remains the focused runner/bootstrap diagnostic.
4. **Regression Shield** remains a post-merge sentinel on `main` for protected-runtime monitoring.
5. GitHub-hosted lanes are acceleration and independent evidence. The self-hosted authoritative lane is the continuity path if included hosted minutes are exhausted or hosted execution is otherwise unavailable.

A green fast or hosted toolchain lane never substitutes for the authoritative self-hosted merge gate.

## 2. Non-negotiable invariants

- Mandatory jobs may not use `continue-on-error: true`.
- External GitHub Actions are pinned to full commit SHA.
- Workflow permissions remain least-privilege; repository checkout does not persist credentials.
- Self-hosted PR jobs reject fork pull requests and use the dedicated `self-hosted, Windows, X64, omni-cio-ci` runner labels.
- CI must not receive broker/Telegram/AI/private-database secrets merely to run tests.
- Test-only placeholder environment values are allowed only where existing deterministic tests require them.
- A failing mandatory gate is repaired; it is not bypassed by deleting, path-filtering away, renaming or softening the check.
- Current V9 money-path replay/idempotency and execution-safety tests remain protected.
- `app:app` stays part of the protected regression contract until a later accepted WP owns its migration.
- Generated dependency/SBOM evidence may contain package metadata only, never portfolio/account/private runtime state.
- Hosted dependency caches must be keyed from committed lock inputs; caches are acceleration only and never replace deterministic installs.
- Stale PR runs may be cancelled through `concurrency` so included GitHub-hosted minutes are not wasted on obsolete commits.

## 3. CI lanes

### 3.1 GitHub-hosted Fast PR Checks

Purpose: fail quickly before the OWNER runner spends time on the full gate.

Required characteristics:

- `pull_request` + manual dispatch;
- `ubuntu-latest` standard GitHub-hosted runners;
- no repository/environment secrets;
- no self-hosted dependency;
- pinned checkout/setup Actions;
- repository/V10-boundary policy checks;
- CI/security policy self-check;
- selected V10 toolchain policy check;
- Python source compilation and focused policy/unit tests;
- frontend baseline type/lint/unit/build from committed lock;
- npm dependency cache keyed by the committed frontend lock;
- `cancel-in-progress: true` per PR.

These jobs are intentionally fast parallel acceleration. They are not the continuity authority when hosted quota is unavailable.

### 3.2 GitHub-hosted V10 Toolchain Compatibility

This remains the clean hosted Windows compatibility lane for:

- Python **3.14.6**;
- Node.js **24.18.0** / npm **11.16.0**;
- deterministic Windows dependency projection;
- hosted Ruff/format/mypy quality evidence;
- full deterministic backend tests on the selected future V10 interpreter;
- frontend type/lint/unit/build/audit/SBOM evidence;
- pip and npm caches keyed by committed dependency locks;
- `cancel-in-progress: true` per PR.

The lane provides independent clean-machine evidence while GitHub-hosted capacity is available.

### 3.3 Self-Hosted Windows CI / authoritative merge gate

The existing `.github/workflows/self-hosted-windows-smoke.yml` workflow is retained so PR checks are available before this infrastructure package reaches `main`. Its workflow name is now `Self-Hosted Windows CI` and it owns two same-repository jobs:

- `Windows runner smoke test` — focused runner/bootstrap diagnostic and transitional required context during cutover;
- `V10 authoritative merge gate` — the PR continuity and merge-authority job.

The authoritative job runs only on the dedicated OWNER Lenovo self-hosted Windows runner and has no GitHub-hosted dependency.

It must independently cover at minimum:

- runner OS/architecture identity;
- protected current Python **3.12.10** runtime bootstrap;
- hash-lock projection/reproducibility;
- CI/security/repository/V10 authority guards;
- compile;
- Ruff lint and format;
- mypy;
- stable `app:app` and read-only release contracts;
- full pytest + branch coverage threshold;
- runtime dependency audit;
- Bandit SAST;
- detect-secrets scan;
- isolated V10 Python **3.14.6** compatibility environment;
- V10 Node **24.18.0** / npm **11.16.0** compatibility;
- frontend typecheck/lint/unit/build/audit;
- cleanup of both isolated Python environments and the self-hosted workspace after every result.

After cutover, the GitHub `main` ruleset should require this single stable context:

`V10 authoritative merge gate`

Hosted acceleration contexts remain visible and useful, but they must not be the only path that can authorize a merge after hosted-minute exhaustion.

### 3.4 Post-merge Regression Shield

`Regression Shield` runs on pushes to `main` and by manual dispatch. It is a post-merge sentinel for the protected current runtime and security surface.

It remains self-hosted and retains the established quality/security/coverage checks. It does not replace the PR authoritative gate and does not need to consume GitHub-hosted minutes.

## 4. GitHub Pro resource policy

For the private repository, standard GitHub-hosted runners are used deliberately as acceleration while included plan capacity is available.

Policy:

- prefer Linux hosted runners for platform-neutral fast feedback;
- retain clean hosted Windows where Windows compatibility itself is the evidence;
- use dependency caching to avoid repeated downloads;
- cancel obsolete PR runs when a newer commit supersedes them;
- retain artifacts only for short diagnostic windows;
- keep self-hosted Lenovo execution independent of the hosted-minute quota;
- do not move broker/private runtime secrets into hosted CI;
- do not weaken required safety checks merely to reduce minute consumption.

Repository/account billing budgets, included-usage alerts, default `GITHUB_TOKEN` permissions and repository artifact/log retention are account/repository controls configured outside version-controlled workflow files. The safe owner-side repository settings and ruleset cutover are scripted in `scripts/configure_github_pro_hybrid_ci.ps1`.

## 5. Frontend quality contract before the product Web package exists

The accepted WP2 fixture under `tests/toolchain/frontend/` remains the only current frontend executable surface.

When the future canonical Web package is introduced by its owning V10 work package, CI must require all of:

- deterministic install from committed lock;
- TypeScript typecheck;
- lint;
- unit/component tests;
- production build;
- Playwright smoke/E2E for critical OWNER workflows;
- dependency audit;
- no secret/private data in browser test fixtures.

A Web package without required scripts/config/tests is a CI failure, not a reason to skip the lane.

## 6. Capability-aware mandatory test contracts

When later V10 work introduces a capability, the matching tests become mandatory in the same PR.

| Capability introduced later | Mandatory test evidence once present |
|---|---|
| PostgreSQL migrations/schema | forward migration, clean bootstrap, rollback/recovery policy where supported, migration version contract |
| Web/API schema | OpenAPI/schema validation, request/response contract tests, auth/authority boundary tests |
| Backup/restore implementation | deterministic backup metadata + restore rehearsal/verification tests |
| Telegram webhook/bot ingress | signature/secret validation, replay/freshness/identity tests, no broker authority expansion |
| AI schemas/providers/tools | structured schema validation, unknown/abstain behavior, tool allowlist/authority-firewall tests |
| Web critical workflows | Playwright smoke/E2E using non-secret deterministic fixtures |

The CI policy guard detects a newly introduced capability root/configuration without its required test evidence.

## 7. Money-path protection

This infrastructure package does not change execution authority.

The authoritative gate must continue to protect semantics relevant to Real/Sandbox/plan execution, including:

- immutable proposal/plan context;
- exact confirmation lifecycle;
- UUID/idempotency binding;
- one possible broker submit per request identity;
- ambiguous possible-submit => unknown/reconcile, never blind retry;
- `submitted` != `filled` without broker evidence;
- fail-closed stale/missing/contradictory inputs where required.

Future execution WPs may add tests, but this CI architecture may not weaken these invariants.

## 8. Anti-bypass policy

The repository CI guard fails if it detects any of the following on mandatory V10 workflows:

- `continue-on-error: true`;
- floating external Action refs;
- unsafe self-hosted execution for fork PRs;
- persisted checkout credentials;
- removal of required authoritative regression/security/toolchain commands;
- removal of selected-toolchain policy checks;
- a capability root without its mandatory test contract;
- future Web package without type/lint/unit/build/E2E contract;
- a required PR workflow whose check can disappear solely because of a path filter.

## 9. GitHub server-side protection expectation

The private `main` branch remains protected by the active repository ruleset `Protect main`.

Required invariants:

- target: `main` only;
- enforcement: active;
- bypass list: empty;
- deletion blocked;
- force-push blocked;
- PR required before merge;
- unresolved review conversations block merge;
- allowed merge method: squash only;
- required status policy is strict/up-to-date;
- the stable required context after hybrid-CI cutover is `V10 authoritative merge gate`.

Hosted Fast PR and Toolchain Compatibility checks remain enabled even when they are not server-side merge blockers, because they provide parallel clean-runner evidence and faster failure discovery.

## 10. Cutover sequence

This infrastructure package is complete only after:

1. GitHub-hosted fast checks are green on the exact PR head;
2. GitHub-hosted clean Windows toolchain checks are green on the same head;
3. `Windows runner smoke test` and `V10 authoritative merge gate` are green on the same head;
4. zero unresolved review threads remain;
5. repository Actions defaults are set to read-only `GITHUB_TOKEN`, PR approval by Actions is disabled, full-SHA Action pinning is required, and short artifact/log retention is configured;
6. while PR #242 is still open and its authoritative exact-head check is green, `Protect main` is cut over from the transitional seven-check list to the single stable `V10 authoritative merge gate` context, preserving strict/up-to-date policy, squash-only merge, empty bypass list, deletion block and force-push block;
7. server-side `Protect main` is re-read and verified after the cutover;
8. PR #242 is squash-merged with expected-head protection and no bypass;
9. post-merge `Regression Shield` on `main` is green;
10. included-usage alerts/budget controls are enabled at the owner account level.

This is infrastructure hardening only. It does **not** start WP4 or any later V10 product work.
