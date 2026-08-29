# AGENTS.md — Omni-CIO project rules

Этот файл обязателен для любого AI-агента, разработчика или нового чата, который меняет `MishaGameHacking/omni-cio-gateway`.

## 1. Product boundary

Поддерживается **один Omni-CIO product line**.

Защищённый owner-accepted V9 production/recovery baseline остаётся:

`Existing Omni-CIO Custom GPT v9.0.0 -> Omni-CIO Gateway (app:app) -> protected broker contours`.

V10 последовательно productize/migrate этот продукт. Не создавать второй Gateway, duplicate Web, competing AI stack, competing scheduler, parallel broker/execution stack или второй user-facing staging product вне явно принятого execution unit/amendment.

For public V10, broker credentials are tenant-scoped `BrokerConnection` credentials, never global application credentials. GitHub/Cloudflare engineering access never means broker/trading authority.

## 2. Current program state

V10 is the exclusive active feature program. Exact current progress/current execution authority is always read from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`; this file is guidance, not a competing progress ledger.

Current synchronized snapshot for this authority transition:

- V10 WP0–WP22A are accepted COMPLETE;
- accepted V10 progress is **54%**;
- Block E has passed the complete `WP22A — External Web Access / Product Authentication Security Gate` technical Exit Gate;
- **CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION — Repository-Side Portable Verification Integration** is the current next package after Amendment 14 acceptance;
- **PRODUCT IMPLEMENTATION PAUSED** during the provider/security authority sequence;
- `WEB-VISUAL-INTEGRATED` remains the prepared product System Update and still requires `START V10 WEB VISUAL SYSTEM UPDATE` before its source implementation;
- WP23+ remains LOCKED;
- `PUBLIC_MULTI_USER_ENABLED=false` remains the current fail-closed runtime state, not a permanent V10-wide release lock;
- Telegram Login, VK ID, public multi-user tenant access and public T-Invest READ remain `BLOCKED_EXTERNAL` until their own real gates pass;
- broker write remains OFF, `trading_methods=false`, `REAL_TRADING_ENABLED=false`;
- protected V9 `app:app` and rollback remain intact.

The PROJECT OWNER is not a special Omni-CIO product role. When using Omni-CIO, the PROJECT OWNER is an ordinary USER on the same `OmniCIOUserAccount -> Tenant -> Session` path as supported users. GitHub/Cloudflare/Windows/CI authority stays outside product identity.

## 3. Mandatory authority restore order

Before any material development, restore current authority from GitHub `main`, not chat memory. Minimum reading order:

1. `README.md`;
2. `AGENTS.md`;
3. `CONTRIBUTING.md`;
4. `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
5. `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
6. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
7. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
8. `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
9. every applicable active amendment, especially Amendments 8–14;
10. `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
11. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
12. architecture/contracts/runbooks/ledgers for the current execution unit;
13. exact current `main`, recent commits, open PR/issues and GitHub Actions.

Key current amendments/contracts include:

- `docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_WP22A_TECHNICAL_CLOSEOUT_AND_PUBLIC_ACTIVATION_SEPARATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_LIVE_USER_OPERABILITY_AND_PROGRESSIVE_CAPABILITY_ACTIVATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_CLOUDFLARE_PLATFORM_AND_CONTINUOUS_RELEASE_AUTHORITY_AMENDMENT.md`;
- `docs/architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json`;
- `docs/architecture/V10_PROGRESSIVE_CAPABILITY_ACTIVATION_CONTRACT.json`;
- `docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json`.

Old chat, screenshots, stale PR text, Cloudflare dashboard state or historical package-local headings never override accepted `main` plus this authority chain.

## 4. GitHub #1 / Cloudflare #2 authority

Amendment 14 establishes, when accepted on protected `main`:

1. **GitHub authority rank 1** — source, PR/review, exact SHA, provenance, accepted status and release-source truth.
2. **Cloudflare Workers Paid platform rank 2** — primary managed application/edge/build target for new V10 work after each owning gate.

Cloudflare must never override accepted GitHub engineering authority.

For new V10 work:

- Cloud.ru Evolution is no longer the selected deployment target;
- Render is retired from active new-V10 deployment, zero-charge attestation, hosted-release-alignment and recovery authority;
- accepted WP22A Render/Neon evidence remains historical technical evidence and must not be rewritten;
- protected V9 Render `app:app` production/recovery remains protected until an explicit V9 decommission/recovery change;
- Amendment 14 acceptance itself performs no provider mutation, DNS/domain mutation, API-token/secret creation, public-user activation or production cutover.

The final V10 public product requires a **managed-cloud production runtime** independent of OWNER home IP/Wi-Fi/router/LAN/Lenovo. The selected new-V10 platform is Cloudflare Workers Paid only after the owning compatibility/candidate/cutover gates.

Cloudflare services may be used when an owning package justifies them:

- Workers / Static Assets for the canonical Web/API boundary;
- Workers Builds for portable verification after repository integration;
- Custom Domains, DNS, TLS, WAF, DDoS/rate controls and Turnstile at the owning security/cutover gate;
- Access for private/admin/engineering surfaces, never as Omni-CIO product identity;
- Hyperdrive only after PostgreSQL 18 compatibility proof;
- KV/R2/Durable Objects/Queues/Workflows only for concrete approved roles, never as accidental financial/tenant truth;
- Workers AI/Vectorize only when AI/Cortex scope is authorized.

Do not click Cloudflare dashboard `Deploy`, create tokens/secrets, mutate DNS/domain or create paid-overage resources during a governance/build-planning package unless that exact provider mutation is the authorized execution unit.

## 5. Continuous exact-main public release law

V10 is an engineering program; the public product releases progressively. A capability need not wait for V10 100% if its own gates pass.

Every accepted new protected `main` SHA is a product revision **candidate**, not an automatic production deployment.

Required release flow:

`PR exact-head GREEN/review -> squash merge -> exact-main post-merge GREEN -> immutable Cloudflare candidate -> candidate acceptance -> production promotion`.

Rules:

- re-check current `main` immediately before promotion;
- a superseded candidate must not be promoted;
- if the latest `main` is not promotable, production stays last-known-good and exposes `UPDATE_PENDING`, `DEPLOYMENT_BLOCKED` or `OUT_OF_SYNC`;
- public release identity uses event-derived CalVer `YYYY.MM.DD.N` plus exact source SHA, Cloudflare version ID, UTC release time and status;
- do not create a source version-bump commit solely to change the public release number;
- rollback to a Worker version does not rewrite GitHub authority;
- KV/R2/D1/Durable Object external state is not rolled back by Worker-code rollback, so schema/storage compatibility and recovery are separate evidence.

## 6. Execution-unit discipline

Every material change is exactly one:

- `FOCUSED_CHANGE` — isolated defect, governance/documentation correction, maintenance, independent migration or mandatory split boundary;
- `INTEGRATED_SYSTEM_UPDATE` — one coherent OWNER-authorized subsystem outcome with ordered internal milestones.

Mandatory split triggers are evidence-based:

1. migration/DB ordering;
2. security/authority transition;
3. dependency/toolchain boundary;
4. genuinely non-delegable OWNER/provider action;
5. live/temporal evidence;
6. production cutover;
7. Real-money authority;
8. reviewability limit.

Amendment 14 therefore requires this sequence rather than one unsafe mega-cutover branch:

1. `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` — repository-side portable build/check integration, no production deploy;
2. `CLOUDFLARE-RUNTIME-COMPATIBILITY` — React/Vite/backend/native dependency/PostgreSQL/Hyperdrive evidence, no assumed compatibility;
3. `CLOUDFLARE-CANDIDATE-DEPLOYMENT` — provider mutation for immutable candidate only after prior gates;
4. `CLOUDFLARE-PUBLIC-CUTOVER` — canonical domain/security/promotion/rollback and capability-specific live-user acceptance.

Do not start the next stage before the prior stage Exit Gate is accepted.

## 7. Pre-CI / root-cause discipline

CI is an independent verifier, not the normal interactive debugger.

Before fixing a material defect:

- find root cause;
- determine blast radius;
- search analogous repository patterns;
- inspect directly coupled producers/consumers/config/workflows;
- inspect adjacent failure modes;
- add deterministic regression guards for reusable defect classes;
- run cheap/focused preflight before expensive full CI;
- review the complete diff before publishing verification head.

Do not patch symptoms one at a time when the defect is systemic. A one-line fix is acceptable only when evidence proves the defect class is truly local.

After publishing a verification SHA, **HEAD FREEZE** applies while the safe independent batch reaches terminal state. Collect findings, group by root cause and publish one coherent correction batch after focused preflight.

An unexpected material RED after declared readiness requires a confidence postmortem in `docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`.

Prefer bounded failure domains rather than one fragile monolith. Timeouts, bounded retries, idempotency, backpressure/circuit-breaking, durable checkpoints, readiness/freshness, restart recovery and least-privilege process boundaries should be considered where applicable. Money/security authority always fails closed.

## 8. Git / PR lifecycle

Never develop directly in `main`.

For each execution unit:

1. get exact current accepted `main`;
2. create a focused/integrated branch from that SHA;
3. implement only the authorized unit;
4. add deterministic tests/guards;
5. run cheap/focused preflight;
6. inspect complete diff and coupled surfaces;
7. open a DRAFT PR;
8. run all applicable exact-head DRAFT checks;
9. perform complete Files changed review plus independent review outputs;
10. resolve all blocking review threads;
11. move unchanged head to READY;
12. require fresh applicable READY checks;
13. squash merge;
14. verify exact new `main` through Regression Shield and owning post-merge gates;
15. only then mark the change accepted.

Every **applicable** exact-head V10 check must actually execute and conclude `success`. `failure`, `cancelled`, `queued`, `pending`, `in_progress`, `timed_out`, `action_required`, `stale`, `neutral` and `skipped` are not V10 GREEN evidence for an applicable gate.

New commit = old exact-head GREEN/review evidence is no longer final.

### Changed-files + independent code-review merge gate

Before merge:

- inspect **all** Files changed, not only the latest fix;
- inspect inline review threads, check annotations and applicable Sonar/Gitar/SAST/security/code-review outputs;
- classify every material finding technically;
- bot approval is supporting evidence only, never a substitute for engineering review;
- unresolved blocking review threads must equal zero;
- after a correction commit, repeat Files changed + independent review on the new exact head;
- do not call a PR GREEN while any applicable exact-head check is non-success.

Normal closure is squash merge after GREEN; closing an unmerged PR never makes its implementation accepted.

## 9. Testing baseline

Do not weaken checks to obtain GREEN. Where applicable, baseline includes:

```text
python scripts/check_ci_security_baseline.py
python scripts/check_repository_layout.py
python scripts/check_v10_repository_boundaries.py
python scripts/check_v10_engineering_governance.py
python scripts/check_v10_cloudflare_platform_authority.py
python scripts/check_v10_documentation_consistency.py
python scripts/check_gpt_recovery_consistency.py
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q --cov --cov-branch --cov-fail-under=60
```

Also run current-WP/provider-specific checks, dependency/security scans, frontend typecheck/lint/test/build/audit and browser/recovery evidence when applicable.

Current GitHub/Lenovo routing remains authoritative until `CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION` is accepted. Do not fake Windows/PowerShell/ACL/PostgreSQL-18 semantics in a portable Cloudflare lane. Quota/provider outage is not `success`.

## 10. Dependencies / toolchain

Do not update dependencies to `latest` by initiative alone. Use accepted versions/locks.

Canonical Python sources:

- `requirements.in`;
- `requirements-dev.in`.

Reviewed generated locks:

- `requirements.txt`;
- `requirements-dev.txt`.

V10 toolchain authority:

- `docs/architecture/V10_TOOLCHAIN_BASELINE.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.json`.

For Cloudflare runtime work, compatibility evidence is mandatory. Current FastAPI source does not imply all CPython/native dependencies work in Python Workers/Pyodide. PostgreSQL 18 + Hyperdrive is not assumed compatible. Preserve the migration preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

## 11. Product / tenant / activation law

One canonical Omni-CIO Web is the normal user-facing product.

Human product authentication remains exactly Telegram Login and VK ID unless a later amendment changes that. Infrastructure/edge identity must never mint/select an Omni-CIO tenant session.

Product path:

`Telegram Login | VK ID -> verified identity -> OmniCIOUserAccount -> Tenant -> server-side Session`.

Tenant scope must be server-derived; PostgreSQL RLS/FORCE-RLS and cross-tenant negatives remain mandatory. Cloudflare WAF/Access/Turnstile is additive outer security, not tenant authorization.

For implemented capability tracking use exactly:

`IMPLEMENTED | LIVE_OPERABLE | BLOCKED_EXTERNAL | REAL_MONEY_AUTHORIZED`.

`V10 is unfinished` is not itself a valid blocker. A capability becomes `LIVE_OPERABLE` only after all owning technical/security/external gates pass.

## 12. Security / secrets

Never put real secrets in GitHub, chat, commits, PR comments, CI logs, screenshots or artifacts.

Never request a real token/key/password when the task can be done without receiving it.

`.env` is local-only from `.env.example`.

Never disclose:

- broker tokens;
- Telegram/VK secrets;
- provider API secrets;
- DB passwords;
- encryption/recovery keys;
- full account IDs;
- private portfolio payloads.

Cloudflare API tokens/secrets must be provisioned through approved secret custody at the owning provider-action gate, not pasted into repository config or chat.

## 13. Broker / Real-money boundary

Current protected invariants:

- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- transfer/withdrawal authority false;
- margin/leverage/uncovered-short authority false.

READ and optional TRADE credentials are tenant-scoped and role-separated. `TRADE credential connected/verified != broker submit authorized`.

Real submit requires `REAL_MONEY_AUTHORIZED` after representative Sandbox/Shadow evidence, immutable plan, authenticated USER approval, drift/preflight, ambiguous-submit reconciliation, kill switches and actual broker permission.

A GitHub merge, Cloudflare deployment, release, AI output, START command or public-user registration is never broker-submit authorization.

## 14. V9 / V10 boundary

Protected V9 remains production/recovery baseline until an explicit decommission/parity gate safely replaces it.

Stable V9 Gateway entrypoint remains `app:app`.

Do not modify the protected V9 Render service merely because Render is retired from **new V10** authority. V9 rollback must remain available.

V10 is migration/productization, not greenfield rewrite.

## 15. OWNER participation / handoff law

Do not ask OWNER to do work that repository/code/docs/GitHub/provider tooling can safely do automatically.

OWNER is required only for genuinely non-delegable actions such as external consent/account/provider UI, UAC/physical steps, secrets kept outside chat, domain/payment decisions or explicit Master Plan authority.

When OWNER action is required:

- give a direct official HTTPS link when stable;
- otherwise give a verified official start URL plus exact click path;
- state exact scope and expected result;
- state stop conditions and what **not** to do;
- request only the minimum safe return evidence;
- do one bounded action at a time;
- never ask OWNER to discover the target page independently;
- state cost/authority consequences before confirmation.

OWNER product acceptance is post-merge/post-Regression-Shield unless a genuinely non-delegable prerequisite must happen earlier.

## 16. Continuity / handoff

After a substantial stage, leave GitHub-visible handoff in the active PR/issue or canonical status when appropriate. Include:

- exact base/main/head SHA;
- current execution unit;
- completed changes;
- checks run and conclusions;
- review/blocker state;
- remaining blockers;
- next authorized step.

Do not create a competing current-status document.
