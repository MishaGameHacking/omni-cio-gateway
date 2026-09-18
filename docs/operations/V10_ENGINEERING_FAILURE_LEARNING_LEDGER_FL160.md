# V10 Engineering Failure Learning — FL160

Failure class: `CF_D_HOSTED_RECOVERY_INCOMPLETE_IMPORT_CLOSURE`

Date: 2026-09-18

Scope: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D / hosted missing-secret recovery`

## Observed failure

Production Release #74 on exact accepted main `dac2b30ecee4918b33990f8310a9e0b474e647e6` correctly reached required hosted production database recovery. The hosted dependency install succeeded, then the bootstrap step stopped before provider mutation with:

`ModuleNotFoundError: No module named 'pydantic'`

The terminal release DAG gate failed and production promotion was skipped, preserving fail-closed release semantics.

The sanitized Neon authority diagnostic after the failure reported `EXACT_PROJECT_BRANCH_READABLE`. The failure was therefore not caused by Neon project/branch authority or credential scope.

## Root cause

The hosted recovery projection contained only `psycopg`, `psycopg-binary`, and `typing-extensions`. That was narrower than the actual Python import graph.

The bootstrap imports the CF-D failure classifier through `omni_cio.contracts.v1`. Importing a regular-package submodule executes the parent package initializers, and the accepted `contracts` initializer reaches Pydantic-backed contracts. Adjacent review also proved that the same bootstrap later imports `omni_cio.persistence.migration`; `omni_cio.persistence.__init__` eagerly imports repository/domain surfaces that also require Pydantic.

A one-file import relocation would therefore have fixed only the first symptom and exposed the same missing dependency class later in the same recovery transaction.

## Permanent correction

Preserve the intentionally bounded hosted recovery environment and canonical dependency authority:

- derive every hosted package version and hash only from accepted `requirements.txt`;
- keep `--require-hashes --no-deps --force-reinstall`;
- expand the explicit hosted allowlist only to the proven Pydantic runtime closure:
  - `annotated-types==0.8.0`;
  - `pydantic==2.13.4`;
  - `pydantic-core==2.46.4`;
  - `psycopg==3.3.4`;
  - `psycopg-binary==3.3.4`;
  - `typing-extensions==4.16.0`;
  - `typing-inspection==0.4.2`;
- keep FastAPI, HTTPX, Starlette, tzdata, Uvicorn and the rest of the application lock outside hosted recovery;
- verify installed hosted package versions from the same source-controlled allowlist instead of duplicating a second version map in workflow YAML;
- freeze the exact allowlist, canonical-lock projection, version-drift failure and workflow verifier with deterministic tests.

## Adjacent failure modes reviewed

- staging recovery uses the same hosted dependency projection and therefore receives the same repair;
- production recovery uses the same generator and verifier;
- existing secrets still skip hosted recovery;
- DSNs and raw branch/project identifiers remain forbidden across job boundaries;
- no Neon Function/OIDC transport is reactivated;
- no provider authority, PostgreSQL 18, RLS/FORCE-RLS, cancellation-safe DAG or production-promotion guard is weakened;
- broker-write and Real-money authority remain unchanged.

## Acceptance requirement

This learning is not closed by source change alone. The replacement exact head must pass all applicable DRAFT/READY checks and Sonar, squash-merge, then exact-new-main post-merge verification. A fresh Cloudflare Production Release must prove required hosted production recovery `success`, followed by production promotion `success` and terminal release DAG `success`.
