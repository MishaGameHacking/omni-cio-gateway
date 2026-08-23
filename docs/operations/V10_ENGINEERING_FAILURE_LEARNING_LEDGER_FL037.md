# FL-037 — Supplemental CI provider availability must not become an unrecoverable gate

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 4; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-23**  
WP / reference: **WP22A Phase 4 / closed-unmerged PR #377 / accepted base main `4dd5cf123726a76a08424f5376db5b6b10ba5a31`**

## Symptom / failing gate

After PR #376 merged, the supplemental CircleCI Phase-4 PostgreSQL bootstrap job produced a RED result while the other supplemental jobs were GREEN. A focused PR #377 corrected a real readiness-contract defect in the CircleCI job and later completed all applicable GitHub/Lenovo exact-head checks successfully.

However, CircleCI stopped creating any commit status/context for multiple substantive #377 heads. GitHub repository webhook delivery for the current push was observed as HTTP 200 with an empty response body, so ordinary GitHub-to-provider webhook transport failure was ruled out. The PROJECT OWNER was also unable to access CircleCI Services because the CircleCI Free account had been restricted under the provider's sanctioned-location policy.

The result was an impossible acceptance state: source-side checks were healthy, but a mandatory supplemental provider could no longer emit the evidence required by project policy.

## Root cause

Two separate causes had to be distinguished:

1. the original CircleCI PostgreSQL service path had a repository defect: the finite PostgreSQL readiness wait was scoped only to the WP13 mode rather than all parameterized Phase-4 modes;
2. after that defect was fixed on #377, CircleCI itself became unavailable as an engineering provider for this Free account.

The systemic engineering defect was allowing a **supplemental external CI provider** to become a mandatory acceptance dependency without a repository-owned, executable provider-loss transition.

CircleCI is not GitHub authority, product authority or production runtime authority. Once the provider could no longer be accessed or trusted to emit current exact-head status, keeping it mandatory would have turned an external account restriction into an indefinite project deadlock.

## Blast radius searched

The review covered:

- current and historical #377 exact-head GitHub checks/statuses;
- OWNER-observed GitHub webhook delivery status;
- `.circleci/config.yml` and its parameterized PostgreSQL 18 jobs;
- `docs/architecture/V10_WP22A_SUPPLEMENTAL_LINUX_CI_DECISION.md`;
- `scripts/rehearse_v10_wp22a_phase4_runtime_role.py`;
- `tests/test_wp22a_phase4_pg18_rehearsal_security.py`;
- the established native PostgreSQL 18 temporary-cluster pattern in `infrastructure/windows/rehearse_wp13_persistence.ps1`;
- the existing `Self-Hosted Windows CI / V10 authoritative merge gate`;
- GitHub's current Linux requirement for Actions service containers;
- Azure Pipelines as the documented fallback candidate;
- the canonical accepted-main Render native-Linux + Neon PostgreSQL 18 Phase-4 deploy/health gate;
- cost-control, protected V9, broker-write and Real-execution boundaries.

No evidence justified a product/runtime rewrite or a new paid CI service.

## Why preflight did not catch it

The original supplemental-CI decision correctly treated CircleCI as execution infrastructure and not authority, but its merge acceptance section still made fresh CircleCI success mandatory. The decision documented Azure Pipelines only as a candidate fallback; it did not define a provider-loss state transition that could be executed without another account, billing relationship or OWNER bootstrap.

The repository therefore had strong job-level failure handling but insufficient **provider-level fault isolation**.

## Corrective change

The recovery keeps the evidence requirement and replaces only the unavailable execution boundary:

- CircleCI is retired as an applicable current acceptance dependency;
- dormant `.circleci/config.yml` is removed so future sessions cannot infer that the provider remains required;
- the existing installed PostgreSQL 18 toolchain on the authoritative Lenovo runner is reused;
- a source-controlled PowerShell wrapper creates a fresh loopback-only temporary PostgreSQL 18 cluster, waits for readiness with a finite deadline, verifies server major version 18, and runs both Phase-4 `creator-edge` and full `bootstrap`/retry modes unchanged;
- the wrapper is invoked inside the existing `V10 authoritative merge gate`, avoiding a second workflow or queue;
- temporary PostgreSQL state is stopped and deleted fail-closed;
- no real secrets/private payloads are used;
- Linux-specific hosted evidence is still mandatory after merge through the canonical Render native-Linux + Neon PostgreSQL 18 exact-main deployment and `/healthz` acceptance gate.

Azure Pipelines was not activated. Current Microsoft documentation requires linking a valid Azure subscription to enable the private-project Microsoft-hosted free grant, which would add a new provider/account/billing prerequisite solely to replace a supplemental CI service.

## Permanent regression / guard

`tests/test_wp22a_phase4_pg18_rehearsal_security.py` now requires:

- the retired CircleCI config to be absent;
- the authoritative GitHub Actions workflow to invoke exactly one Phase-4 native PostgreSQL 18 wrapper;
- the wrapper to target PostgreSQL 18, loopback-only startup, finite readiness, both Phase-4 modes, fail-closed cleanup and no-real-secret markers;
- the CI decision to preserve mandatory post-merge Linux-hosted evidence rather than claiming Windows is Linux.

The runtime-role Python rehearsal remains the same implementation used by provider/bootstrap semantics, so the recovery does not create a competing database acceptance model.

## Future prevention rule

A supplemental SaaS CI lane may become mandatory only if its provider-loss behavior is explicitly defined before acceptance. The fallback must preserve the underlying evidence without requiring an unapproved paid subscription, a hidden account-only configuration or a second product/runtime stack.

When an external CI provider becomes unavailable:

1. prove whether the failure is repository, webhook/transport, provider/project or account/billing state;
2. do not call missing provider evidence GREEN;
3. do not weaken the test;
4. migrate the same semantic evidence onto an already-authorized controllable execution boundary when one exists;
5. preserve platform-specific evidence separately rather than falsely claiming cross-platform equivalence;
6. remove or clearly retire dead provider configuration so it cannot remain an implicit future gate.

## Dependency/tooling knowledge change

Current GitHub Actions documentation requires a Linux runner with Docker for job/service containers, so the Windows `omni-cio-ci` runner must use native PostgreSQL rather than a GitHub `services:` PostgreSQL container.

Current CircleCI support policy lists Russia among sanctioned locations and states that a restricted Free-plan user is permanently restricted from CircleCI Services. Provider account availability therefore cannot be assumed to recover through a VPN or ordinary re-login.

Current Azure Pipelines documentation offers private-project hosted free minutes only after the organization is linked to a valid Azure subscription. It is not a zero-friction substitute for the already-authorized self-hosted gate.