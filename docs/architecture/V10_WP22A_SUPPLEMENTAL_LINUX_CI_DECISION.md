# WP22A — Supplemental Linux CI Decision

Status: **PROVIDER RETIRED / EVIDENCE MIGRATED / LENOVO AUTHORITATIVE GATE PRESERVED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Recovery decision date: **2026-08-23**  
Accepted recovery base `main`: `4dd5cf123726a76a08424f5376db5b6b10ba5a31`

CircleCI provider requirement: **RETIRED**.

## 1. Purpose

The accepted Lenovo `omni-cio-ci` GitHub self-hosted Windows runner remains the authoritative pre-merge compute lane. The earlier CircleCI Free lane supplied useful independent Linux/PostgreSQL evidence, but it was supplemental execution infrastructure rather than repository authority.

On 2026-08-23 the CircleCI Free account became a durable provider-availability failure for the PROJECT OWNER. GitHub webhook deliveries for current repository pushes were observed returning HTTP 200, while CircleCI created no commit contexts and the OWNER could not access CircleCI Services because the provider restricts Free-plan accounts flagged from a sanctioned location. CircleCI's current support policy states that Russia is a sanctioned location and that a restricted Free-plan user is permanently restricted from CircleCI Services.

A provider that the PROJECT OWNER cannot access, inspect or recover cannot remain an applicable mandatory merge dependency. This decision migrates the evidence, not the safety requirement.

Target recovery topology:

`GitHub source -> existing Lenovo authoritative Windows gate -> native ephemeral PostgreSQL 18 Phase-4 rehearsal -> squash merge -> exact-main Regression Shield -> canonical Render native-Linux + Neon PostgreSQL 18 deployment/health acceptance`

## 2. Non-negotiable boundaries

The recovery preserves:

- canonical source only in `MishaGameHacking/omni-cio-gateway`;
- protected `main`, exact-head evidence and squash-only integration;
- `app:app` protected V9 runtime/recovery baseline;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- `PUBLIC_MULTI_USER_ENABLED=false` while WP22A launch gates remain unfinished;
- broker write disabled;
- no real broker, Telegram, VK, provider or recovery secret in ordinary CI;
- no paid CI subscription, credit purchase or GitHub budget mutation;
- WP23+ locked until WP22A Exit Gate;
- post-merge Regression Shield before provider apply;
- Render/Neon Phase-4 apply only through the canonical accepted-main workflow.

CircleCI historical runs remain historical evidence. They are not current acceptance authority after this recovery decision.

## 3. Root cause and blast radius

The immediate symptom was not a repository parser failure. Current `.circleci/config.yml` had already been source-validated against CircleCI 2.1 structure, and GitHub delivered current push events successfully. The provider nevertheless emitted no build/status evidence and the OWNER could not access the CircleCI account.

The engineering defect was architectural: a supplemental external CI provider had become a mandatory exact-head acceptance dependency without an executable zero-cost provider-loss transition.

Blast radius review covered:

- `.circleci/config.yml`;
- this supplemental-CI decision;
- the PostgreSQL 18 Phase-4 rehearsal producer `scripts/rehearse_v10_wp22a_phase4_runtime_role.py`;
- the accepted Windows temporary-PostgreSQL pattern in `infrastructure/windows/rehearse_wp13_persistence.ps1`;
- `tests/test_wp22a_phase4_pg18_rehearsal_security.py`;
- the existing `Self-Hosted Windows CI / V10 authoritative merge gate`;
- the Phase-4 Render/Neon deployment workflow and `/healthz` acceptance contract;
- CI cost-control and exact-head GREEN rules;
- candidate hosted-CI fallbacks.

No product identity, tenant, provider-apply, broker or Real-execution authority is widened.

## 4. Why the recovery does not add another hosted CI provider

Azure Pipelines was the previously documented fallback candidate. It is not activated by this recovery.

Current Microsoft documentation states that the Microsoft-hosted private-project free grant requires the Azure DevOps organization to be linked to a valid Azure subscription. Activating it would therefore introduce a new external provider/account/billing prerequisite and OWNER action merely to replace a supplemental CI service. That is not justified while the already-approved GitHub Pro + Lenovo path can execute the required PostgreSQL 18 semantics at zero additional recurring cost.

Azure Pipelines is not activated.

No other paid or account-only CI service is introduced.

## 5. Pre-merge PostgreSQL 18 evidence migration

The repository already contains a proven Windows pattern that creates an isolated temporary PostgreSQL 18 cluster from the installed PostgreSQL 18 toolchain, binds it only to loopback, waits for readiness with a finite deadline and deletes all temporary state afterward.

Phase 4 now reuses that pattern through:

`infrastructure/windows/rehearse_wp22a_phase4_runtime_role.ps1`

The wrapper must:

1. resolve PostgreSQL 18 tools from `Program Files/PostgreSQL/18/bin` or the controlled runner PATH;
2. initialize an ephemeral cluster with synthetic trust-only local authentication;
3. bind the server only to `127.0.0.1` on a dynamically selected free port;
4. wait for `pg_isready` with a finite 45-second deadline;
5. prove the running server major version is exactly PostgreSQL 18;
6. create isolated synthetic databases;
7. execute the existing Python `creator-edge` rehearsal unchanged;
8. execute the existing Python full `bootstrap` + existing-role retry rehearsal unchanged;
9. use no real provider/database/broker secret or private payload;
10. stop PostgreSQL and remove the temporary cluster fail-closed.

The existing `Self-Hosted Windows CI / V10 authoritative merge gate` invokes this wrapper after installing the exact hash-locked project dependencies. This is not a second queue, second workflow or new CI stack.

## 6. Evidence mapping from the retired CircleCI lane

The former CircleCI responsibilities are mapped as follows:

| Former supplemental evidence | Current mandatory evidence |
| --- | --- |
| Exact source identity | GitHub exact-head checkout in the authoritative merge gate |
| Portable governance/documentation/cost guards | Existing authoritative merge gate + normal exact-head GitHub workflows |
| PostgreSQL 18 readiness | Native temporary cluster + bounded `pg_isready` wait |
| PostgreSQL major 18 | Native client/server version assertion before rehearsal |
| WP13 persistence semantics | Existing accepted Windows WP13 PostgreSQL 18 rehearsal remains authoritative for WP13 |
| Phase-4 creator-admin edge | Native PostgreSQL 18 `creator-edge` execution in authoritative gate |
| Phase-4 hosted bootstrap | Native PostgreSQL 18 `bootstrap` execution in authoritative gate |
| Phase-4 existing-role retry | The same `bootstrap` mode executes both initial convergence and password-rotation retry |
| No real secrets/private data | Synthetic loopback cluster + tracked-content secret guard |
| Linux-hosted runtime compatibility | Canonical accepted-main Render native-Linux build/start + Neon PostgreSQL 18 deployment and health gate |

No former safety assertion is converted to a paper-only PASS.

## 7. Linux evidence boundary

The Windows authoritative gate proves the database and role semantics before merge, but it does not claim to be Linux.

Linux-specific hosted evidence remains mandatory after merge for WP22A Phase 4 through the already-authorized canonical deployment path:

- Render native Python Web Service build/start on the exact accepted-main SHA;
- Neon PostgreSQL 18 in the accepted Frankfurt preview region;
- exact least-privilege runtime role and FORCE RLS checks;
- exact release identity;
- provider-returned HTTPS URL;
- `/healthz` HTTP 200 with `status=ok`, exact `release_sha`, `database=READY` and `synthetic_preview=true`;
- required cache/security headers;
- zero recurring authorized cost and no real user/broker/private payload.

A failed or unavailable post-merge hosted deployment remains RED. This migration does not pre-declare Linux compatibility before that real evidence exists.

## 8. GitHub Actions service-container boundary

The current authoritative runner is Windows. GitHub's current documentation requires a Linux runner with Docker for Actions job/service containers. Therefore this recovery does not add a fake `services: postgres` declaration to the Windows workflow.

The native installed PostgreSQL 18 temporary-cluster pattern is the repository-supported Windows implementation.

## 9. Retired CircleCI configuration

`.circleci/config.yml` is removed by this recovery change so future sessions cannot infer that CircleCI remains an active mandatory gate merely because dormant provider configuration exists.

Historical CircleCI results and prior failure-learning records are not rewritten. They remain provenance for the work that occurred while the provider was usable.

Repository tests permanently guard that:

- the retired CircleCI config is absent;
- the authoritative Windows workflow invokes the Phase-4 PostgreSQL 18 wrapper;
- the wrapper executes both `creator-edge` and `bootstrap` modes;
- readiness, exact major version, loopback isolation, cleanup and no-real-secret markers remain present.

## 10. Cost and provider discipline

This recovery adds no subscription and no payment method.

- GitHub self-hosted runner execution remains free from GitHub-hosted minute consumption;
- the existing Lenovo PostgreSQL 18 installation is reused;
- Azure Pipelines is not activated;
- CircleCI is not upgraded or appealed through a paid plan;
- Render/Neon remain subject to the separate zero-charge provider boundary and fresh OWNER no-payment-method attestation before mutation.

Provider loss is never permission to weaken source/security checks. The correct recovery is to migrate the evidence onto an already-authorized controllable execution boundary.

## 11. Acceptance boundary for the recovery PR

Before merge:

1. the recovery branch starts from exact accepted main;
2. `.circleci/config.yml` is absent;
3. deterministic source tests prove the migrated CI routing contract;
4. the native Windows PostgreSQL 18 Phase-4 rehearsal runs successfully inside the exact-head authoritative merge gate;
5. all other applicable exact-head GitHub checks conclude `success`;
6. Gitar/current review finds no unresolved blocking defect;
7. zero unresolved blocking review threads;
8. fresh unchanged-head READY cycle concludes all applicable checks `success`;
9. squash merge only.

After merge:

1. capture exact new main SHA;
2. exact-main Regression Shield must complete `success` with both required jobs successful;
3. the canonical Phase-4 Render+Neon workflow must re-verify that exact Regression Shield;
4. the zero-charge boundary must pass;
5. provider apply must complete and the exact public HTTPS health contract must pass.

Only after those post-merge steps is the V10 synthetic preview described as working.

## 12. External references reviewed for this recovery

- CircleCI sanctions policy: `https://support.circleci.com/hc/en-us/articles/360043679453-CircleCI-Terms-of-Service-Violation-Sanctioned-Country`
- GitHub self-hosted/service-container requirement: `https://docs.github.com/en/actions/reference/runners/self-hosted-runners`
- Azure Pipelines private-project hosted free tier: `https://learn.microsoft.com/en-us/azure/devops/pipelines/get-started/what-is-azure-pipelines`

These provider facts are operational context, not permanent product authority. If provider policies change later, a new focused engineering decision may reassess optional supplemental CI without weakening this recovery evidence.