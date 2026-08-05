# Omni-CIO V10 — Toolchain and Dependency Baseline

Status: **WP2 IN PROGRESS — compatibility candidates, not final pins**  
Runtime effect: **none until WP2 Exit Gate is accepted**  
Protected production baseline: **V9 `app:app` / Python 3.12.10 compatibility remains unchanged during evaluation**

## 1. Purpose

WP2 selects one reproducible development/toolchain baseline before Lenovo bootstrap and before Web/Telegram/AI product implementation.

The rule is evidence-first:

`official supported release -> clean compatibility build -> deterministic lock -> security/license/SBOM checks -> exact-head V9 regression -> accepted pin`.

Newest is not automatically safest. Existing is not automatically acceptable forever.

## 2. Current proven backend baseline

Accepted V9 currently uses:

- Python `3.12.10` in the Windows CI bootstrap;
- FastAPI `0.141.1`;
- Uvicorn `0.51.0`;
- HTTPX `0.28.1`;
- `t-tech-investments==1.49.3`;
- root `requirements.in` / `requirements-dev.in` plus SHA-256 hash-locked generated requirements files;
- stable production entrypoint `app:app`.

This baseline is proven for compatibility. It is **not yet accepted as the long-term V10 Python baseline**.

## 3. Fresh release review at WP2 start

Review date: `2026-08-05`.

### Python

Official Python release sources show:

- Python `3.12.10` was the final regular 3.12 bugfix release with Windows binary installers;
- later Python 3.12 security releases are source-only and the 3.12 line is security-fixes-only until October 2028;
- Python `3.13.14` and `3.14.6` are current supported maintenance releases.

Sources:

- `https://www.python.org/downloads/release/python-31210/`
- `https://www.python.org/downloads/release/python-31213/`
- `https://www.python.org/downloads/release/python-31314/`
- `https://www.python.org/doc/versions/`

Decision rule: WP2 must test newer Windows-installable Python candidates before deciding whether to retain 3.12.10 for V10.

### FastAPI / current broker SDK

Current FastAPI/Uvicorn metadata supports newer Python versions. `t-tech-investments` declares Python `>=3.8.1,<4.0.0`, but its published classifiers explicitly list through Python 3.12. Therefore a Python 3.13/3.14 move requires actual project compatibility evidence; metadata range alone is insufficient for this broker-critical system.

Sources:

- `https://pypi.org/project/fastapi/`
- `https://pypi.org/project/uvicorn/0.51.0/`
- `https://pypi.org/project/t-tech-investments/`

### Node.js / npm

Node.js `24.18.0` is current LTS (`Krypton`) and bundles npm `11.16.0`.

Sources:

- `https://nodejs.org/en/about/previous-releases`
- `https://nodejs.org/en/blog/release/v24.18.0`

Candidate:

- Node.js `24.18.0`;
- npm `11.16.0`;
- npm `package-lock.json` lockfile v3 unless the compatibility build exposes a blocker.

V10 does not select Node Current v26 for the baseline because Node's own release guidance recommends production applications use Active/Maintenance LTS.

### React / Vite / TypeScript

Fresh official/package release evidence:

- React stable line: `19.2`;
- current React package patch observed at review: `19.2.8`;
- Vite regular-patch stable line: `8.1`;
- current Vite package patch observed at review: `8.1.5`;
- `@vitejs/plugin-react`: `6.0.4`;
- TypeScript `7.0` is a stable new native compiler generation; current package patch observed at review: `7.0.2`.

Sources:

- `https://react.dev/versions`
- `https://www.npmjs.com/package/react`
- `https://vite.dev/releases`
- `https://www.npmjs.com/package/vite`
- `https://www.npmjs.com/package/@vitejs/plugin-react`
- `https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/`

Candidate toolchain for a **non-product smoke project only**:

- React `19.2.8`;
- React DOM `19.2.8`;
- Vite `8.1.5`;
- `@vitejs/plugin-react` `6.0.4`;
- TypeScript `7.0.2`.

The Web product itself is still blocked until its later V10 work package. WP2 may create only the minimum deterministic fixture needed to prove the frontend toolchain and lock format.

### PostgreSQL

PostgreSQL `18.4` is the current supported stable PostgreSQL 18 release at WP2 start. PostgreSQL 19 is still development/beta and is not a V10 Personal baseline candidate.

Sources:

- `https://www.postgresql.org/docs/release/18.4/`
- `https://www.postgresql.org/docs/current/`

Candidate baseline: PostgreSQL major `18`, tested patch baseline `18.4`. Runtime installation occurs later in Block C; WP2 freezes compatibility/version policy only.

## 4. Version-selection principles

### Backend Python

A V10 Python pin must satisfy all of:

1. official supported Windows distribution or a separately reviewed reproducible runtime artifact;
2. current hash-locked dependencies install cleanly;
3. `app:app` imports and health contract remain unchanged;
4. full regression suite passes;
5. broker SDK import/client compatibility passes;
6. dependency audit/SAST/secret scan remain green;
7. no hidden reliance on an original developer machine.

Python candidates to evaluate in WP2:

- `3.13.14` — primary migration candidate;
- `3.14.6` — forward candidate;
- `3.12.10` — compatibility control only.

WP2 will select the highest supported candidate that satisfies broker/runtime compatibility without weakening gates. If neither newer candidate passes, retaining 3.12.10 requires a documented security/update mitigation because later 3.12 security releases are source-only.

### Frontend

The frontend toolchain baseline must:

- use Node LTS, not Current;
- use exact package versions in source control;
- commit a deterministic npm lockfile before WP2 acceptance;
- run `npm ci`, not floating `npm install`, in accepted CI;
- run typecheck/build/audit against the lock;
- contain no product portfolio logic during WP2.

### PostgreSQL

WP2 freezes the major/stable patch policy. It does not install the DB on Lenovo and does not create production schemas before the later data/Core work packages.

## 5. Lock/source-of-truth policy

### Python

Canonical human-edited sources remain:

- `requirements.in`;
- `requirements-dev.in`.

Canonical generated locks remain:

- `requirements.txt`;
- `requirements-dev.txt`.

Locks must remain exact and SHA-256 hashed. Generated Windows projection files remain ephemeral CI artifacts.

### JavaScript

Canonical WP2 source will be exact-version `package.json` plus committed `package-lock.json` generated by the accepted npm version. The package manager version is part of the toolchain identity.

No `latest`, caret (`^`) or tilde (`~`) range is accepted for V10 direct critical frontend/toolchain dependencies.

## 6. Dependency provenance / license / SBOM policy

Before WP2 acceptance, CI must produce/check a non-secret dependency manifest containing at minimum:

- ecosystem;
- normalized package name;
- exact resolved version;
- direct/transitive classification where available;
- license expression/declared license where available;
- lock/source identity.

Minimum deny policy:

- missing exact version for a critical direct dependency;
- known high/critical vulnerability not explicitly blocked/mitigated by an accepted exception;
- package with a denied/non-redistributable license for the intended use;
- dependency sourced from an unreviewed registry/path;
- generated lock mismatch.

The manifest/SBOM contains no secret values, account identifiers or private portfolio data.

## 7. CI design during WP2

WP2 introduces a GitHub-hosted Windows compatibility gate before Lenovo setup. It is intentionally separate from the existing protected self-hosted V9 Regression Shield.

Evaluation stages:

1. Python compatibility matrix on clean GitHub-hosted Windows;
2. exact selected Python baseline;
3. exact Node/npm bootstrap;
4. deterministic non-product frontend fixture `npm ci` + typecheck + build;
5. dependency manifest/license/audit checks;
6. existing self-hosted Regression Shield/security on the same PR head.

The compatibility matrix may be temporary during WP2. Accepted `main` keeps only the final selected baseline gate, not exploratory CI noise.

## 8. Non-goals

WP2 does not:

- deploy or configure Lenovo;
- install production PostgreSQL;
- implement Omni-CIO Web screens;
- add Telegram runtime;
- add an AI provider/model;
- change current Render production;
- expand broker-write/Real authority;
- retire the current Custom GPT.

## 9. Exit Gate

WP2 is complete only when:

- one exact backend/frontend/database toolchain baseline is selected from passing evidence;
- exact locks are committed and reproducible;
- clean GitHub-hosted Windows compatibility/build is green;
- dependency/SBOM/license policy is machine-checkable;
- current V9 `app:app` regression/security remains green;
- zero unresolved review blockers remain;
- focused WP2 PR is squash-merged to `main`.
