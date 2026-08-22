# FL-030 — Direct script invocation must not lose repository import root

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-22**  
WP / PR / reference: **WP22A Phase 4 Render + Neon synthetic preview / accepted-main deploy run `32521783571` / diagnostic PR #363**

## Symptom / failing gate

The accepted-main Phase 4 deploy verified exact-main Regression Shield evidence, passed all 52 focused Phase 4 source tests, passed the zero-charge provider boundary, verified the Neon Free organization and created the Frankfurt-scoped Neon preview project. Provider apply then stopped before Render provisioning with `DATABASE_BOOTSTRAP_IMPORT_FAILED`.

The public Render root and `/healthz` consequently remained `404`: the accepted-main run never reached the Render service creation/deploy boundary.

## Root cause

The deployment workflow invoked the provisioner as a direct file:

`python scripts/provision_v10_render_neon_preview.py`

The provisioner intentionally delays importing `omni_cio.persistence.*` until database bootstrap. Under Python direct-file execution, the script directory becomes the initial import location rather than the repository root. The workflow therefore entered `_bootstrap_database()` with `scripts/` as the script import root and could not resolve the repository package imports required there.

A read-only reproduction on the exact accepted main, exact Python 3.12.10 runtime and exact Phase 4 dependency projection proved that `psycopg`, `psycopg.sql`, `omni_cio.persistence`, `omni_cio.persistence.hosted_postgres_runtime_v1` and `omni_cio.persistence.migration` all import successfully when the repository root is on `sys.path`. This isolated module resolution, not dependency installation or provider state, as the defect.

## Blast radius searched

The defect class was traced through the Phase 4 workflow launch command, the provisioner bootstrap import closure, repository executable-script patterns and the coupled Neon-to-Render deployment sequence.

The correction does not change:

- exact-main Regression Shield authority;
- Render or Neon credentials, API permissions or zero-cost constraints;
- Neon Free plan, PostgreSQL 18 or Frankfurt region requirements;
- database migration, least-privilege runtime-role or FORCE-RLS semantics;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- protected V9 `app:app`;
- broker write, `trading_methods=false` or `REAL_TRADING_ENABLED=false`;
- the WP23+ lock.

## Why preflight missed it

The Phase 4 tests loaded the provisioner under pytest/importlib, where the repository root was already available for imports. They verified provider and bootstrap logic but did not reproduce the exact production launch form used by the accepted-main workflow.

The branch therefore entered the protected provider cycle with a launch-mode portability gap even though the internal modules and dependencies were valid.

## Corrective change

Execute the accepted provisioner from the exact checked-out repository root as a Python module:

`python -m scripts.provision_v10_render_neon_preview`

This preserves the reviewed provisioner and provider boundary while giving Python the repository root as the module-search base. No global `PYTHONPATH` mutation, package rewrite, dependency change or authority widening is introduced.

## Permanent regression / guard

`tests/test_wp22a_phase4_provisioner_import_path.py` is part of the pre-provider Phase 4 source gate and verifies:

- the workflow uses the reviewed `python -m scripts.provision_v10_render_neon_preview` launch form;
- the previous direct-file launch form is absent from the workflow;
- module invocation resolves from the repository root with `PYTHONPATH` removed;
- the deferred database-bootstrap import closure resolves from the repository root.

Any future change to the provider launch mode must pass the same focused guard before provider mutation.

## Future prevention rule

Executable deployment, recovery and evidence scripts that import repository packages must be tested under the exact interpreter launch mechanism used by production/CI. Direct-file execution, `python -m`, installed-package execution and arbitrary-CWD execution have different module-search semantics and must not be treated as interchangeable.

Where repository source identity is authoritative, bind or preserve the exact reviewed repository root explicitly and add a regression that removes ambient `PYTHONPATH` assumptions.

## Dependency/tooling knowledge change

Python interpreter launch mode is part of the deployment toolchain contract. A successful import under pytest or `python -c` does not prove the same package is resolvable under `python path/to/script.py`; exact launch-mode reproduction is required before a provider apply is declared preflight-ready.
