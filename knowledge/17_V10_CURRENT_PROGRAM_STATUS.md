# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-14

## Executive state

Omni-CIO V10: **DEVELOPMENT ACTIVE / BLOCK D COMPLETE / WP16 COMPLETE / WP17 COMPLETE / WP18 COMPLETE / WP19 COMPLETE / WP20 COMPLETE / WP21 COMPLETE / WP22 COMPLETE / WP22A AUTHORIZED NEXT**.

Accepted implementation progress is **40%**.

Block A (5%), Block B (9%), Block C (12%) and Block D (14%) have passed their owning Exit Gates. Block E is still in progress: WP16, WP17, WP18, WP19, WP20, WP21 and WP22 are complete; WP22A — External Web Access / OWNER Authentication Security Gate — is the next authorized implementation package. Block E receives no percentage credit until its own Block Exit Gate, which includes WP22A.

WP22 was implemented on final reviewed head `cbe521c2cafad1a7d8df81119344ffca35098e12` and squash-merged through PR #314 to exact `main` `872976cd2bb34d304c8666a332e466fc6cd9b0d4`.

On the final reviewed WP22 head, the fresh `ready_for_review` cycle completed **SUCCESS** for the dedicated WP22 System Admin Audit, inherited WP15 Live Web Support, WP16 Web Design System, WP17 Application Shell, WP18 Portfolio Dashboard, WP19 Watchtower Incident, WP20 Research Dossier, WP21 Decision/Risk/Plan and authoritative Self-Hosted Windows CI. The authoritative gate included Regression Shield coverage, dependency audit, SAST, tracked-content secret scan, stable `app:app` and read-only GPT Actions checks. Hosted Fast PR Checks / Toolchain Compatibility did not start substantive GitHub-hosted jobs because of the account billing/spending-limit condition; they remain infrastructure failures, not PASS and not code failures.

After squash merge, post-merge Regression Shield #1494 / run `31796896704` completed **SUCCESS** on exact `main` `872976cd2bb34d304c8666a332e466fc6cd9b0d4`. Both independent jobs passed: quality/contracts/coverage and dependency/code/secret security. The post-merge WP22 System Admin Audit #15 / run `31796896578` also completed **SUCCESS** on the same exact main.

The post-merge WP15 Live Web OWNER Audit #21 / run `31796896713` remains **FAILURE**, not PASS. Its accepted immutable OWNER evidence is bound to the accepted WP15 implementation rather than the later WP22 main, so the audit reports `implementation_bound=false` and `WP15_LIVE_RUNNER_ISOLATION_NOT_PROVEN`. The auditor intentionally performs the live secret/evidence ACL probes only after implementation/evidence/hash binding succeeds; because that precondition is false on later Web main SHAs, the emitted runner-access booleans remain fail-closed defaults and are not evidence that a new runner secret-access regression occurred. The same sanitized audit still records real broker READ observation present, locally used READ credential evidence present, no secret value recorded, no private portfolio values recorded, no broker-write authority added, `trading_methods=false` and gateway `app:app`. No new OWNER evidence is synthesized merely to rebind historical WP15 acceptance to a later Web commit.

The accepted WP22 product surface remains local/private, OWNER/session-scoped and READ-only. `/system` now projects sanitized service health, release/deploy identity, PostgreSQL/migration state, accepted backup RPO/RTO plus durable backup observation, T-Invest READ/Watchtower state, explicit future-locked Telegram/AI state, bounded resource telemetry, required safety invariants and bounded recent jobs/errors. Unknown/degraded telemetry remains explicit instead of being fabricated as READY. No browser mutation control, public ingress, broker-write route, Telegram/AI activation or Real execution authority was introduced.

The deferred/accepted WP15 real T-Invest READ path remains unchanged. Broker provisioning remains connection-scoped through the authenticated local/private Web flow; raw broker credentials, full provider account IDs and private portfolio payloads remain outside GitHub/CI evidence.

OWNER action required now: **NO**. Engineering may proceed autonomously to the WP22A dependency/contract check only after this status-only transition itself passes exact-head required gates, is squash-merged, and the resulting exact `main` passes the required post-status Regression Shield. This transition does not itself open public ingress or enable public multi-user activation.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Accepted / current WP state

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE**;
- Block B / WP2 — **COMPLETE**;
- Block B / WP3 — **COMPLETE**;
- Block B / WP4 — **COMPLETE (Block B accepted at 9%)**;
- Block C / WP5 — **COMPLETE**;
- Block C / WP6 — **COMPLETE**;
- Block C / WP7 — **COMPLETE**;
- Block C / WP8 — **COMPLETE**;
- Block C / WP9 — **COMPLETE**;
- Block C / WP9A — **COMPLETE**;
- Block C / WP10 — **COMPLETE (Block C accepted at 12%)**;
- Block D / WP11 — **COMPLETE**;
- Block D / WP12 — **COMPLETE**;
- Block D / WP13 — **COMPLETE**;
- Block D / WP14 — **COMPLETE**;
- Block D / WP15 — **COMPLETE (Block D accepted at 14%)**;
- Block E / WP16 — **COMPLETE**;
- Block E / WP17 — **COMPLETE**;
- Block E / WP18 — **COMPLETE**;
- Block E / WP19 — **COMPLETE**;
- Block E / WP20 — **COMPLETE**;
- Block E / WP21 — **COMPLETE**;
- Block E / WP22 — **COMPLETE**;
- Block E / WP22A — **AUTHORIZED NEXT / NOT STARTED**;
- Block F / WP23+ — **LOCKED behind WP22A and Master Plan sequence**;
- public multi-user activation — **OFF / LOCKED**;
- public Internet ingress — **OFF / LOCKED until WP22A Exit Gate**;
- broker write / Real execution — **UNCHANGED / NOT AUTHORIZED**.

## Current next package — WP22A External Web Access / OWNER Authentication Security Gate

Master Plan objective: prevent the local Personal cabinet from becoming a public attack surface before external-access security design and evidence are complete.

Required WP22A deliverables:

- decide whether public ingress is needed at all; safe private remote access is evaluated first;
- if external ingress is needed, define reviewed TLS termination, certificate issuance/renewal, HSTS/host allowlist and trusted reverse-proxy chain;
- preserve a separate ordinary-browser authentication path; Telegram/Mini App identity is not the only login authority;
- server-side sessions with defined lifetime, rotation, explicit revoke/logout and secure/HttpOnly/SameSite cookies or equivalent reviewed controls;
- CSRF protection plus Origin/Referer/Host validation where applicable and CORS deny-by-default;
- login/API rate limiting and abuse policy without self-DoS of critical monitoring;
- any future Real-plan approval endpoint requires step-up/recent OWNER authentication and never trusts only a deep-link URL;
- external ingress configuration remains repository-controlled while secret keys/certificate private material remain runtime-only.

Required WP22A checks include relevant ASVS 5.0.0 controls, invalid/stolen/expired sessions, CSRF, host-header/origin abuse, brute-force/rate-limit behavior, direct API calls without UI and Telegram `initData` replay/staleness where applicable.

WP22A Exit Gate: **until this gate is GREEN, Web remains local/private and the Real approval surface is not published externally**.

WP22A must reuse the accepted single Web App, server-side session/identity model, tenant isolation and operational diagnostics. It must not create a second website/control plane, grant broker-write authority, enable Real execution, or treat external reachability as equivalent to public multi-user activation.

## Canonical authority

Base program:

- `AGENTS.md`;
- `README.md`;
- `knowledge/00_PROJECT_MASTER_CONTEXT.md`;
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` for protected V9 runtime state;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`.

Identity, broker provisioning and Web work are additionally governed by:

- `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`;
- `docs/architecture/ADR-0010-identity-multitenant-authentication.md`;
- `docs/architecture/V10_IDENTITY_AUTHENTICATION_CONTRACT.json`;
- `docs/operations/V10_IDENTITY_AND_BROKER_CONNECTION_SECURITY_NOTES.md`;
- `docs/architecture/V10_WP15_TINVEST_READONLY_CONTRACT.md`;
- `docs/architecture/V10_WP15_LIVE_ACCEPTANCE_STATE.json`;
- `docs/architecture/V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json`;
- `docs/operations/V10_WP15_OWNER_LIVE_READ_RUNBOOK.md`;
- `docs/architecture/V10_WP16_WEB_DESIGN_SYSTEM_CONTRACT.md`;
- `docs/architecture/ADR-0011-web-read-credential-provisioning.md`;
- `docs/architecture/V10_WP17_APPLICATION_SHELL_CONTRACT.json`;
- `docs/operations/V10_WP17_APPLICATION_SHELL_RUNBOOK.md`;
- `docs/architecture/V10_WP18_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP18_PORTFOLIO_DASHBOARD_CONTRACT.md`;
- `docs/architecture/V10_WP19_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP19_WATCHTOWER_INCIDENT_UI_CONTRACT.md`;
- `docs/architecture/V10_WP20_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP20_RESEARCH_DOSSIER_UI_CONTRACT.md`;
- `docs/architecture/V10_WP21_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP21_DECISION_RISK_PLAN_UI_CONTRACT.md`;
- `docs/architecture/V10_WP22_EXECUTION_CONTRACT.md`;
- `docs/architecture/V10_WP22_SYSTEM_ADMIN_UI_CONTRACT.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_THREAT_MODEL.md`.

GitHub remains engineering source of truth. Protected production/recovery baseline remains **Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance** until the responsible later V10 parity/decommission gate.

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | COMPLETE — WP1 / WP2 / WP3 / WP4 |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | COMPLETE — WP5 / WP6 / WP7 / WP8 / WP9 / WP9A / WP10 |
| D. V10 Core and data | 14% | COMPLETE — WP11 / WP12 / WP13 / WP14 / WP15 incl. real READ evidence |
| E. Omni-CIO Web Platform | 14% | IN PROGRESS — WP16 / WP17 / WP18 / WP19 / WP20 / WP21 / WP22 COMPLETE; WP22A NEXT |
| F. Telegram | 8% | NOT STARTED — product/interaction contract pre-approved only |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **40% ACCEPTED** |

The 40% total is intentional: Block E is not credited piecemeal and WP22A has not passed its Exit Gate.

## Accepted implementation evidence index

- WP0 PR #228 -> `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 PR #229 -> `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 PR #230 -> `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 PR #236 -> `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- WP4 PR #248 / hardening #249 -> accepted Block B;
- WP5 PR #251; WP6 #253; WP7 #255; WP8 #257; WP9 #259; WP9A #261; WP10 rebuild #267 -> accepted Block C;
- WP11 clean rebuild #269; WP12 #271; WP13 #273; WP14 #275;
- WP15 primary PR #277 -> `f8862d1af88400189d3c0780d2029a87cb5427ca`;
- Identity / Multi-Tenant / Authentication amendment PR #278 -> `cbf6a7adba78fa56d23e90ce2cfe2952d21a5e5b`;
- WP16 PR #280 -> `03f3ff2f389b1b683e60e1ccc706cd7f62a9ba35`;
- WP17 PR #282 -> `5b6b12f144c9bfa71307dcb28548a97527456b5b`;
- deferred WP15 live support PR #284 and acceptance hardening PRs #285/#286/#287/#290/#292/#293/#294/#295/#296/#297/#298/#299;
- V10 status/runbook sync PR #300 -> `0825e6c4625944d7b8e7dd796150fb1ae6707e6d`;
- WP15 live responsiveness/deadline correction PR #301 -> exact accepted implementation `a7ecad5f7e84e756d19fca2969a71c62fca744a2`;
- WP15 live acceptance/status transition PR #302 -> accepted pre-WP18 `main` `8b6780dc2d0c6cb3f70577e6f24a5e8ca11def07`;
- WP18 PR #303 -> squash merge `90c8b52c864db034d31d6184346b2ff62707c121`;
- WP19 PR #308 -> squash merge `058e53a76e6f6aeabe32eb6711cb5168417d5093`;
- WP20 PR #310 -> squash merge `b83e2bcc729ed0863f861a258dc951a57ec6b65e`;
- WP21 PR #312 -> squash merge `933e05ead311f0016372cab1d38eb9746bc62a19`;
- WP21 status transition PR #313 -> `4bb18b7cddc33b8d79d168103c747852b8624b23`;
- WP22 final reviewed head `cbe521c2cafad1a7d8df81119344ffca35098e12`: dedicated WP22 audit, inherited Web regressions and authoritative Self-Hosted Windows CI — **SUCCESS**;
- WP22 PR #314 squash merge -> exact `main` `872976cd2bb34d304c8666a332e466fc6cd9b0d4`;
- post-WP22 Regression Shield #1494 / run `31796896704` on exact `main` `872976cd2bb34d304c8666a332e466fc6cd9b0d4` — **SUCCESS**, including quality/contracts/coverage, dependency audit, SAST and tracked-secret scan;
- post-WP22 System Admin Audit #15 / run `31796896578` — **SUCCESS** on the same exact main;
- post-WP22 WP15 Live Web OWNER Audit #21 / run `31796896713` — **FAILURE** because immutable accepted WP15 evidence is not bound to the later WP22 main; the audit short-circuits before live ACL probes when binding is false and therefore is not treated as PASS or as proof of a new isolation regression.

Hosted Fast PR Checks / Toolchain Compatibility runs that GitHub did not start because of the account billing/spending-limit condition remain infrastructure failures, not PASS and not code failures.

## WP22 closeout evidence

WP22 satisfies its Master Plan Exit Gate:

- the `/system` route is authenticated, session/tenant-scoped and strictly READ-only;
- service health, release/deploy identity, PostgreSQL/migration status, backup RPO/RTO, T-Invest READ, Watchtower, resource/disk/temperature availability, safety state and bounded recent jobs/errors are visible from one ordinary operating surface;
- unavailable, degraded and future-locked states are explicit and never fabricated as READY;
- Telegram and AI remain explicitly future-locked rather than being reported as current runtime failures;
- safety/kill-switch information is diagnostic only; contradictory required safety state fails closed;
- diagnostics omit raw exceptions, secret references, credentials, backup/recovery material, full broker account identifiers and private portfolio payloads;
- no POST/PUT/PATCH/DELETE companion route or browser mutation control was added;
- no public ingress, broker-write authority, Telegram/AI activation or Real execution was introduced;
- deterministic Web/Python/browser evidence covers degraded-service, migration mismatch, low disk, masked errors, missing telemetry and authenticated/unauthenticated behavior;
- review state before merge had zero blocking threads/comments and the complete 12-file WP22 diff was reviewed;
- squash merge, exact-main Regression Shield and exact-main focused WP22 audit all completed successfully.

This acceptance authorizes only the separate WP22A external-access security package after this status transition itself is accepted. It does not authorize opening the cabinet to the public Internet before WP22A passes its own Exit Gate.

## Permanent safety / rollback invariants

- deployment entrypoint remains `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- broker write authority is not expanded by Web/read work;
- no real broker/Telegram/VK tokens, encryption/recovery keys, private portfolio payload or full account IDs in GitHub, CI logs or artifacts;
- protected V9 rollback remains preserved;
- red CI is red; skipped is not PASS; billing/infrastructure failure is distinct from code failure;
- feature work uses focused branch/PR, mandatory exact-head CI, zero blocking threads, squash merge and required post-merge Regression Shield;
- OWNER physical/secret evidence is never synthesized.

## Current next action

Start **WP22A — External Web Access / OWNER Authentication Security Gate** only after this status-only transition itself passes exact-head required gates, is squash-merged, and the resulting exact `main` passes the required post-status Regression Shield. Before writing WP22A feature/configuration code, re-read the accepted `main`, WP execution template, Master Plan WP22A section, identity/session contracts, `V10_SECURITY_BOUNDARIES.md`, `V10_THREAT_MODEL.md` and relevant Windows/Web deployment authorities. The first design decision is whether public ingress is needed at all; a secure private remote-access option must be evaluated first. Until WP22A is GREEN, the Web remains local/private and broker-write / Real execution authority remains unchanged.