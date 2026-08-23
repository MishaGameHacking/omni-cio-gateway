# FL-037 — Supplemental PostgreSQL rehearsals require a universal readiness gate

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-23**  
WP / reference: **WP22A Phase 4 / post-merge CircleCI verification of main `4dd5cf123726a76a08424f5376db5b6b10ba5a31`**

## Symptom / failing gate

After PR #376 passed all exact-head DRAFT and READY checks and was squash-merged, the post-merge CircleCI pipeline on exact main `4dd5cf123726a76a08424f5376db5b6b10ba5a31` reported:

- `supplemental_linux_governance` — SUCCESS;
- `supplemental_linux_phase4_pg18_creator_edge` — SUCCESS;
- `supplemental_linux_postgres18` — SUCCESS;
- `supplemental_linux_phase4_pg18_bootstrap` — FAILURE (build 808).

The merged main tree is `f9d16da82d68c2f3574bae004ddccd1010679dcd`, exactly the same tree as PR head `91648018b27b837c2d08e58a35e7420717a1d377`, where the Phase-4 PostgreSQL bootstrap rehearsal had succeeded. The available GitHub status and CircleCI email identify the failed job but do not expose the private build-step log, so the literal build-808 failing statement is not fabricated here.

## Root cause class

The current parameterized `supplemental_linux_postgres18` job has three rehearsal modes: `wp13`, `phase4-creator-edge`, and `phase4-bootstrap`.

The accepted supplemental-Linux CI contract requires this PostgreSQL lane to **wait with a finite deadline for PostgreSQL readiness** before rehearsal work. The implementation, however, kept the finite psycopg retry loop inside the `wp13` conditional only. Both Phase-4 modes reached `psycopg.connect()` without an unconditional readiness barrier.

This is a deterministic repository contract defect even though the exact build-808 exception text is unavailable. CircleCI documents that secondary database containers can race job steps and recommends an explicit readiness wait because a PostgreSQL service may be running before it is ready to accept connections. Independent service containers explain why one same-tree PostgreSQL job can fail while sibling PostgreSQL jobs succeed.

The correction therefore fixes the proven readiness-contract violation and the directly matching nondeterministic failure class without claiming unsupported certainty about the unavailable build-808 log.

## Blast radius searched

The review covered:

- exact PR head `91648018b27b837c2d08e58a35e7420717a1d377` versus squash-main `4dd5cf123726a76a08424f5376db5b6b10ba5a31` and confirmed identical Git tree `f9d16da82d68c2f3574bae004ddccd1010679dcd`;
- all four CircleCI post-merge contexts and the failed build-808 notification;
- `.circleci/config.yml` parameter routing for all three PostgreSQL rehearsal modes;
- `scripts/rehearse_v10_wp22a_phase4_runtime_role.py` initial admin connection, creator-edge and full bootstrap paths;
- `scripts/provision_v10_render_neon_preview.py::_converge_runtime_role` and PostgreSQL-18 role semantics;
- `docs/architecture/V10_WP22A_SUPPLEMENTAL_LINUX_CI_DECISION.md`, which already requires a finite PostgreSQL readiness wait;
- CircleCI first-party guidance on secondary-service startup races and database readiness waits.

No provider mutation, database privilege widening, broker authority change, public multi-user activation, Real execution change or WP23+ work is part of this correction.

## Why preflight missed it

The original supplemental PostgreSQL lane implemented its readiness retry before WP13 rehearsal work. Later Phase-4 creator-edge and bootstrap modes reused the same parameterized job but were added below that mode-specific `when` block. The readiness requirement was therefore inherited conceptually but not structurally.

Exact-head PR checks frequently passed because dependency installation usually gave the PostgreSQL service enough time to become ready. That timing made the missing universal barrier latent rather than deterministic on every run.

## Corrective change

- move PostgreSQL readiness/version verification to one unconditional step after hash-locked dependencies are installed and before any rehearsal-mode branch;
- implement the wait in a small repository-controlled Python module using psycopg, a 45-second finite deadline and bounded connection attempts;
- retry only `psycopg.OperationalError` startup/connectivity failures;
- fail closed on timeout with a sanitized `POSTGRES_READY_TIMEOUT` code and never echo the DSN/password;
- verify `SHOW server_version_num` reports PostgreSQL major 18 and execute `SELECT 1` before the rehearsal begins;
- remove the duplicated WP13-only inline readiness one-liner so all three modes share exactly one boundary.

## Permanent regression / guard

Focused tests prove:

1. transient psycopg operational failures are retried and eventually produce a PostgreSQL-18 PASS;
2. timeout fails closed without reproducing a DSN or password in the exception;
3. a wrong PostgreSQL major fails immediately rather than being retried as readiness noise;
4. `.circleci/config.yml` contains exactly one readiness step and it appears before the first rehearsal-mode `when` block, making it unconditional for WP13 and both Phase-4 modes.

## Future prevention rule

When a CI job is parameterized into multiple modes, prerequisites such as checkout integrity, dependency installation, service readiness, runtime identity, secret masking and safety guards must live **above** the mode split unless the contract explicitly makes them mode-specific.

A database service being declared in a Docker executor does not prove it is ready for SQL. Every independently started service container that is required by the test must have a bounded readiness check before first use.

## Dependency/tooling knowledge change

CircleCI first-party database guidance explicitly treats secondary-container startup as a race condition and demonstrates a finite wait before PostgreSQL-dependent work. This behavior is execution-environment semantics, not an application/database permission issue, and should be handled in CI orchestration rather than by weakening PostgreSQL or product safety boundaries.
