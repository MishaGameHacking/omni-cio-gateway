# Omni-CIO V10 — Toolchain and Dependency Baseline

Status: **WP2 SELECTED BASELINE / FINAL EXIT GATE PENDING**  
Runtime effect: **none until later runtime migration packages**  
Protected production baseline: **V9 `app:app` remains unchanged on its accepted runtime while V10 tooling is prepared**  
Machine-readable authority: `docs/architecture/V10_TOOLCHAIN_BASELINE.json`

## 1. Purpose

WP2 freezes one reproducible development/toolchain baseline before Lenovo bootstrap and before Web/Telegram/AI product implementation.

Selection rule:

`official supported release -> clean compatibility build -> deterministic lock -> security/license/SBOM checks -> exact-head V9 regression -> accepted pin`.

Newest was not accepted merely because it was newest. The selected versions below passed project-specific compatibility evidence.

## 2. Selected V10 baseline

### Backend

- Python: **3.14.6**;
- FastAPI: **0.141.1**;
- Uvicorn: **0.51.0**;
- HTTPX: **0.28.1**;
- T-Tech Investments SDK: **1.49.3**;
- Python direct dependency sources: root `requirements.in` / `requirements-dev.in`;
- generated Python locks: root `requirements.txt` / `requirements-dev.txt`, exact and SHA-256 hash locked.

### Frontend toolchain

- Node.js: **24.18.0 LTS**;
- npm: **11.16.0**;
- npm lock format: **package-lock v3**;
- React: **19.2.8**;
- React DOM: **19.2.8**;
- Vite: **8.1.5**;
- `@vitejs/plugin-react`: **6.0.4**;
- TypeScript: **7.0.2**;
- `@types/node`: **24.13.3**;
- `@types/react`: **19.2.17**;
- `@types/react-dom`: **19.2.3**.

The accepted WP2 frontend fixture lives under `tests/toolchain/frontend/`. It proves the toolchain only; it is **not** the Omni-CIO Web product and contains no portfolio/business/execution implementation.

### Database compatibility target

- PostgreSQL major: **18**;
- reviewed/tested patch baseline: **18.4**.

WP2 freezes the supported version policy only. PostgreSQL runtime installation/configuration remains Block C and schemas/data services remain later V10 work packages.

## 3. Why Python 3.14.6 was selected

The accepted V9 Windows CI bootstrap uses Python `3.12.10`. Official Python release guidance states that 3.12.10 was the final regular 3.12 bugfix release with binary installers; later 3.12 security releases are source-only. Therefore WP2 evaluated newer Windows-installable Python lines rather than freezing the future V10 platform to the old compatibility interpreter.

Official review sources:

- `https://www.python.org/downloads/release/python-31210/`;
- `https://www.python.org/doc/versions/`;
- `https://www.python.org/downloads/release/python-3146/`.

WP2 clean Windows compatibility run `31050239756` tested:

- Python `3.12.10` — **SUCCESS**;
- Python `3.13.14` — **SUCCESS**;
- Python `3.14.6` — **SUCCESS**.

For each candidate the workflow proved:

- exact interpreter identity;
- strict Windows projection of the existing hash-locked dependency set;
- dependency installation including the broker SDK;
- repository structure guard;
- V10 repository-boundary guard;
- source compilation;
- stable `app:app` import and `/health` contract;
- the full deterministic pytest suite.

Because `3.14.6` passed the same protected project gates and is the newer supported maintenance line, WP2 selects **Python 3.14.6 for future V10 development/toolchain work**.

This does **not** upgrade the current Render/V9 production runtime in WP2. Runtime migration happens only in the work package that owns that deployment boundary.

## 4. Concurrency portability defect found during evaluation

The initial 3.13/3.14 matrix exposed two tests whose concurrency assertions accidentally depended on thread scheduling order. The production evaluators correctly reject chronologically out-of-order events, but the tests submitted increasing microsecond timestamps concurrently and assumed workers would acquire the lock in submission order.

WP2 corrected only the concurrency tests:

- ACRA rating-actions alert policy;
- MOEX ISS quote alert policy.

The concurrency tests now use equal timestamps, proving serialization/fire-once behavior without assuming scheduler ordering. Separate explicit out-of-order tests remain unchanged and continue to prove fail-closed temporal ordering.

No production alerting logic, broker authority or execution behavior was weakened.

## 5. Node/npm/frontend selection evidence

Node.js release policy recommends Active/Maintenance LTS for production applications. WP2 therefore selected Node 24 LTS rather than a Current line.

Official sources:

- `https://nodejs.org/en/about/previous-releases`;
- `https://nodejs.org/en/blog/release/v24.18.0`.

The clean Windows frontend job in run `31050239756` proved:

- exact Node `24.18.0`;
- exact npm `11.16.0`;
- deterministic generated package-lock v3;
- `npm ci` reproduction;
- strict TypeScript typecheck;
- Vite production build of the non-product smoke fixture;
- `npm audit --audit-level=high`;
- CycloneDX SBOM generation.

The successful candidate lock was reviewed and committed as:

`tests/toolchain/frontend/package-lock.json`.

Accepted CI no longer generates a lock as its source of truth; it installs from the committed lock and verifies that the selected npm version would not change it.

## 6. Frontend dependency and license policy

Direct frontend/toolchain dependencies use exact versions. `latest`, caret/tilde ranges, git URLs, file references and arbitrary HTTP sources are forbidden for direct V10 toolchain dependencies.

The committed lock is restricted to the reviewed npm registry:

`https://registry.npmjs.org/`

Allowed licenses observed in the locked frontend dependency tree and accepted for this Personal V10 toolchain are:

- `0BSD`;
- `Apache-2.0`;
- `BSD-3-Clause`;
- `ISC`;
- `MIT`;
- `MPL-2.0`.

The permanent guard is:

`scripts/check_v10_toolchain_baseline.py`

It fails if:

- required direct Python dependencies stop matching the selected baseline;
- `requirements.in` introduces a non-exact direct pin;
- frontend direct versions become floating;
- Node/npm/package-manager identity drifts;
- package-lock root metadata diverges from `package.json`;
- package-lock version changes unexpectedly;
- an npm package resolves outside the approved registry;
- a locked npm dependency lacks license metadata;
- a locked npm dependency uses a license outside the reviewed allowlist;
- the PostgreSQL baseline drifts silently.

## 7. SBOM / vulnerability policy

WP2 CI produces non-secret CycloneDX SBOM evidence for both ecosystems:

### Python

`pip-audit` runs against the strict Windows projection of the hash-locked development dependency set and:

- fails on known audited dependency vulnerabilities according to the existing strict policy;
- generates `python-sbom.cdx.json` in CycloneDX JSON format.

### Frontend

The selected npm lock is audited with:

`npm audit --audit-level=high`

and generates:

`frontend-sbom.cdx.json`

through npm's lock-based CycloneDX SBOM command.

SBOM artifacts are CI evidence only. They contain package/dependency metadata, not broker tokens, account IDs, portfolio data or other runtime secrets.

## 8. Source-of-truth policy

### Python

Human-edited direct sources:

- `requirements.in`;
- `requirements-dev.in`.

Generated/verified locks:

- `requirements.txt`;
- `requirements-dev.txt`.

Generated Windows projections remain ephemeral CI artifacts and are not committed.

### JavaScript

Human-edited direct source:

`tests/toolchain/frontend/package.json`

Committed deterministic lock:

`tests/toolchain/frontend/package-lock.json`

Package manager identity:

`npm@11.16.0`

Accepted CI uses `npm ci` from the committed lock and checks lock reproducibility.

### Machine-readable V10 baseline

`docs/architecture/V10_TOOLCHAIN_BASELINE.json`

This JSON is intentionally paired with this explanatory document so CI can validate exact pins without parsing prose.

## 9. PostgreSQL policy

Official reviewed source:

`https://www.postgresql.org/docs/release/18.4/`

V10 selects PostgreSQL 18 as its stable major baseline with patch `18.4` as the reviewed WP2 reference. Future security/maintenance patch updates remain controlled dependency/runtime changes and require compatibility/recovery evidence; PostgreSQL 19 development/beta is not the Personal V10 baseline.

## 10. Dependency maintenance

Dependabot remains proposal-only:

- Python ecosystem at repository root;
- npm ecosystem at `/tests/toolchain/frontend` for the selected V10 frontend toolchain;
- GitHub Actions at repository root.

No Dependabot proposal is automatic merge authorization. Current-main exact-head compatibility/security evidence remains required.

## 11. CI design after candidate selection

Exploratory Python matrix evidence is retained in the WP2 PR/run history, but accepted workflow configuration keeps only the selected baseline:

- clean GitHub-hosted Windows + Python `3.14.6`;
- clean GitHub-hosted Windows + Node `24.18.0` / npm `11.16.0`;
- machine-readable toolchain/dependency policy check;
- committed-lock `npm ci` / lock reproducibility;
- frontend typecheck/build/audit/SBOM;
- Python full test/audit/SBOM;
- existing self-hosted Regression Shield/security on the same PR head.

The GitHub-hosted toolchain gate supplements the protected V9 Regression Shield; it does not replace or weaken it.

## 12. Non-goals

WP2 does not:

- deploy or configure Lenovo;
- install production PostgreSQL;
- implement Omni-CIO Web screens;
- add Telegram runtime;
- add an AI provider/model;
- change current Render production;
- expand broker-write/Real authority;
- retire the current Custom GPT.

## 13. Exit Gate

WP2 becomes COMPLETE only after the final PR head proves:

- selected baseline JSON and explanatory document agree;
- exact Python and npm locks are reproducible;
- clean GitHub-hosted Windows selected-baseline jobs are green;
- dependency/audit/SBOM/license policy is green;
- current V9 `app:app` Regression Shield/security remains green;
- zero unresolved review blockers remain;
- focused WP2 PR is squash-merged to `main`.

After acceptance, WP3 becomes the next authorized work package. Accepted V10 progress remains 5% until all of Block B is complete.
