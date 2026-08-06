# Omni-CIO V10 — Regression Shield and CI Protection Contract

Status: **WP3 IMPLEMENTATION COMPLETE CANDIDATE / ACCEPTANCE BLOCKED BY GITHUB SERVER-SIDE PROTECTION**  
Scope: CI/repository protection only  
Protected runtime: current V9 `app:app` remains unchanged until an owning later WP intentionally migrates it

## 1. Purpose

WP3 makes CI the primary engineering barrier against hidden regressions before any runtime or release reaches the OWNER node.

The contract is intentionally layered:

1. **Fast PR checks** provide low-cost deterministic feedback without using private runtime secrets or the self-hosted OWNER runner.
2. **Toolchain compatibility** proves the selected WP2 Python/Node baseline on clean GitHub-hosted Windows.
3. **Full exact-head Regression Shield** runs the protected V9 quality/security/contracts/coverage surface on the dedicated self-hosted Windows runner.
4. **Acceptance** is allowed only from the same unchanged PR head that passed every mandatory lane and has zero unresolved review blockers.

A green fast lane never substitutes for the full acceptance gate.

## 2. Non-negotiable invariants

- Mandatory jobs may not use `continue-on-error: true`.
- External GitHub Actions are pinned to full commit SHA.
- Workflow permissions remain least-privilege; repository checkout does not persist credentials.
- Self-hosted jobs reject fork pull requests and use isolated temporary environments outside the checkout.
- CI must not receive broker/Telegram/AI/private-database secrets merely to run tests.
- A failing mandatory gate is repaired; it is not bypassed by deleting, path-filtering away, renaming, or softening the check.
- Current V9 money-path replay/idempotency and execution-safety tests remain protected.
- `app:app` stays part of the protected regression contract until a later accepted WP owns its migration.
- Generated dependency/SBOM evidence may contain package metadata only, never portfolio/account/private runtime state.

## 3. CI lanes

### 3.1 Fast PR Checks

Purpose: detect deterministic repository/policy/source regressions quickly on GitHub-hosted infrastructure.

Required characteristics:

- `pull_request` only;
- no repository or environment secrets;
- no self-hosted runner;
- pinned checkout/setup Actions;
- repository/V10-boundary policy checks;
- CI/security policy self-check;
- selected V10 toolchain policy check;
- Python source compilation and focused policy/unit tests that do not require private runtime state;
- frontend baseline type/lint/unit checks from committed lock when the frontend fixture/product package is present.

Fast checks are advisory for speed but mandatory as a named lane for V10 PR acceptance once WP3 is accepted.

### 3.2 V10 Toolchain Compatibility

The accepted WP2 workflow remains the clean GitHub-hosted Windows compatibility lane for:

- Python 3.14.6;
- Node 24.18.0 / npm 11.16.0;
- deterministic lock reproduction;
- hosted Ruff/format/mypy quality evidence;
- full deterministic backend tests on the selected future V10 interpreter;
- frontend type/lint/unit/build/audit/SBOM evidence.

WP3 must not weaken this lane.

### 3.3 Full Regression Shield

The existing `Regression Shield` remains the authoritative exact-head acceptance gate for the protected runtime and financial Core.

It retains at minimum:

- hash-lock reproducibility;
- repository and V10 authority/boundary checks;
- compile;
- Ruff lint and format;
- mypy baseline;
- stable `app:app` and GPT Action/recovery contracts while applicable;
- pytest with coverage threshold;
- runtime dependency audit;
- SAST;
- secret scan;
- critical execution/replay/idempotency contracts already represented in the deterministic test suite.

The full gate uses the dedicated self-hosted Windows runner only for same-repository PRs.

## 4. Frontend quality contract before the product Web package exists

WP3 must not create the Omni-CIO Web product out of sequence. The accepted WP2 fixture under `tests/toolchain/frontend/` is therefore the only current frontend executable surface.

WP3 may add non-product deterministic lint/unit fixtures around that baseline. When the future canonical Web package is introduced by Block E, CI must require all of:

- deterministic install from committed lock;
- TypeScript typecheck;
- lint;
- unit/component tests;
- production build;
- Playwright smoke/E2E for critical OWNER workflows;
- dependency audit;
- no secret/private data in browser test fixtures.

A Web package without the required scripts/config/tests is a CI failure, not a reason to skip the lane.

## 5. Capability-aware mandatory test contracts

Some WP3 test categories target capabilities that intentionally do not exist yet. WP3 therefore establishes fail-closed repository contracts instead of creating fake product implementations.

When the owning future WP introduces the capability, the matching tests become mandatory in the same PR.

| Capability introduced later | Mandatory test evidence once present |
|---|---|
| PostgreSQL migrations/schema | forward migration, clean bootstrap, rollback/recovery policy where supported, migration version contract |
| Web/API schema | OpenAPI/schema validation, request/response contract tests, auth/authority boundary tests |
| Backup/restore implementation | deterministic backup metadata + restore rehearsal/verification tests |
| Telegram webhook/bot ingress | signature/secret validation, replay/freshness/identity tests, no broker authority expansion |
| AI schemas/providers/tools | structured schema validation, unknown/abstain behavior, tool allowlist/authority-firewall tests |
| Web critical workflows | Playwright smoke/E2E using non-secret deterministic fixtures |

The CI policy guard must detect a newly introduced capability root/configuration without its required test evidence.

## 6. Money-path protection

WP3 does not change execution authority. It protects the existing safety evidence by requiring the full deterministic suite and explicit repository guard checks for critical execution contracts.

At minimum the protected suite must continue to cover the established semantics relevant to Real/Sandbox/plan execution:

- immutable proposal/plan context;
- exact confirmation lifecycle;
- UUID/idempotency binding;
- one possible broker submit per request identity;
- ambiguous possible-submit => unknown/reconcile, never blind retry;
- submitted != filled without broker evidence;
- fail-closed stale/missing/contradictory inputs where required.

Future execution WPs may add tests, but WP3 may not weaken these existing invariants.

## 7. Anti-bypass policy

The repository CI guard fails if it detects any of the following on mandatory V10 workflows:

- `continue-on-error: true`;
- floating external Action refs;
- unsafe self-hosted execution for fork PRs;
- persisted checkout credentials on mandatory jobs;
- removal of required Regression Shield commands;
- removal of selected-toolchain policy checks;
- a capability root that appears without its mandatory test contract;
- future Web package without type/lint/unit/build/E2E contract;
- a workflow design where required checks can remain absent solely because a changed path did not match a path filter.

## 8. Branch-protection expectation

Repository-side branch/ruleset administration is an account-level control and may not be writable through every GitHub integration. WP3 therefore separates two obligations:

1. **repository-enforced evidence:** workflows and guards are version-controlled, deterministic and cannot silently soften themselves;
2. **GitHub settings evidence:** before WP3 acceptance, verify that the repository's merge policy actually blocks significant PR merge while mandatory checks are red or missing, or document the exact owner-admin setting required if the connected integration cannot read/change it.

No claim of branch protection is made without evidence from GitHub itself.

### 8.1 Verified account-level blocker — 2026-08-06

The canonical repository is private. GitHub's repository rulesets endpoint reports that rulesets for this private repository are unavailable on the current account plan and requires an eligible paid plan. The branch-protection endpoint is also not readable through the installed integration, so there is no evidence that `main` currently has an equivalent server-side required-check rule.

This is an **acceptance blocker**, not a reason to weaken WP3:

- the repository must remain private;
- making it public is not an acceptable workaround;
- the OWNER account must use a GitHub plan that supports protected branches/rulesets for private repositories (GitHub Pro or another eligible private-repository plan);
- after eligibility is available, `main` must require the mandatory V10 checks and disallow bypass for the acceptance contract;
- only then may the final unchanged-head acceptance evidence be used for squash merge.

Until server-side protection is proven, PR #236 remains unmerged and WP4 remains blocked even if every repository-controlled CI job is green.

## 9. WP3 Exit Gate

WP3 is complete only when:

- fast PR and full acceptance lanes are distinct and documented;
- V9 quality/security gates remain mandatory;
- selected WP2 toolchain lane remains mandatory;
- frontend baseline has deterministic type/lint/unit coverage and future Playwright/E2E is fail-closed when Web appears;
- DB/API/authority/backup/Telegram/AI capability contracts are machine-checked when their roots appear;
- critical money-path safety tests remain protected;
- anti-bypass guard tests are green;
- final exact-head Fast PR Checks + V10 Toolchain Compatibility + Regression Shield/security are green;
- GitHub server-side protection for private `main` requires the mandatory checks and prevents bypass;
- zero unresolved review blockers remain;
- focused WP3 PR is squash-merged to `main`.

After acceptance, WP4 — Release, build provenance and deployment contract — becomes next.
