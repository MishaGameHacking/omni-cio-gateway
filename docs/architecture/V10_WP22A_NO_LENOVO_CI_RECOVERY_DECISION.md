# WP22A — No-Lenovo CI Recovery Decision

Status: **DRAFT IMPLEMENTATION / OWNER REPORTED LENOVO UNAVAILABLE / NO CI VENDOR ACCEPTED YET**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Accepted base `main`: `67223469e0031b94d0ada7c5c0d92e3e4efb8d22`

## 1. Trigger

On 2026-08-19 the PROJECT OWNER reported that the Lenovo node is not accessible and cannot be used for runner diagnostics, CI execution or project continuation.

This changes an engineering availability assumption, not product authority. Work must continue without requiring physical access to OWNER home infrastructure.

## 2. Non-negotiable boundaries

The recovery must preserve:

- canonical source only in `MishaGameHacking/omni-cio-gateway`;
- Pull Request development and exact-head acceptance;
- `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- `PUBLIC_MULTI_USER_ENABLED=false` until its owning gate;
- no broker write expansion;
- no real broker/Telegram/VK/recovery secrets in CI;
- protected V9 rollback;
- WP23+ locked until WP22A Exit Gate;
- no hidden paid overage or billing mutation.

A replacement CI service is execution infrastructure only. It does not become source authority, product identity authority, tenant authority or production secret authority.

## 3. GitHub-hosted recovery probe result

A bounded `windows-2025` GitHub-hosted probe was added on recovery PR #337.

Run `32246884046` concluded `failure` before any workflow step was allocated. GitHub returned an empty job-step list and no downloadable job log. Therefore:

- this is **not** evidence of a product/test failure;
- no hosted VM execution evidence exists from that run;
- the exact provider-side pre-execution reason is not asserted without an annotation/log;
- the result is consistent with the accepted zero-budget/hard-stop capacity state and is treated as hosted-capacity unavailable until proven otherwise;
- no billing setting was changed to bypass it.

The GitHub-hosted probe is failure-learning evidence only and must not be represented as PASS.

## 4. Candidate comparison

### CircleCI Cloud — preferred recovery candidate for proof

Current official provider material reports:

- Free plan: 30,000 credits/month;
- no credit card required for the Free plan;
- hosted Docker/Linux and Windows execution are included;
- `windows.medium`: 4 vCPU / 16 GB RAM / 200 GB disk;
- `windows.medium` compute rate: 40 credits/minute;
- GitHub App integration is recommended and uses fine-grained permissions plus short-lived tokens for repository access;
- workflow status can be reported back to GitHub Checks.

The first source-controlled CircleCI probe deliberately uses a small Linux Docker executor, not Windows, so connection/capacity is proven at minimal credit burn before any expensive migration validation.

### Azure Pipelines — fallback candidate

Microsoft-hosted private-project free tier currently provides one hosted job, up to 60 minutes per job and 1,800 minutes/month. Enabling that free hosted tier requires Azure DevOps billing/subscription linkage, so it is not preferred while a no-card Free candidate remains viable.

### GitLab.com CI — secondary fallback

GitLab.com Free currently has a materially smaller shared-runner compute-minute allowance and would introduce another VCS-facing integration while GitHub must remain canonical source. It is not selected for the first recovery attempt.

## 5. Selected recovery experiment

**Candidate for bounded proof: CircleCI Cloud Free + GitHub App, repository access restricted to the canonical Omni-CIO repository.**

This is not yet an accepted CI authority. Acceptance requires actual source-backed execution evidence after the OWNER performs the unavoidable external GitHub App authorization.

The first probe must prove only:

1. the private canonical repository can be checked out;
2. the exact commit SHA is preserved;
3. the source safety markers remain intact;
4. no deployment, provider mutation, billing mutation or secret use occurs.

Only after that probe is GREEN may this PR add the authoritative hosted CI gates.

## 6. Target CI architecture after successful proof

Target direction:

`GitHub canonical PR -> CircleCI hosted Linux primary gates -> bounded CircleCI Windows compatibility/security gate only where Windows semantics are actually required -> GitHub status/check evidence`

Linux becomes the primary hosted validation environment because the accepted final Cloud.ru runtime is Linux `amd64`. Windows remains a compatibility/recovery validation surface, not a dependency on a particular physical Lenovo node.

The migration must preserve test semantics rather than mechanically multiplying historical per-WP workflows. Expensive Windows compute is used only where PowerShell/Windows/PostgreSQL-on-Windows behavior is materially under test. General Python/Web/security/static checks should use lower-cost hosted Linux execution where equivalent.

## 7. Production runtime remains separate

This CI recovery does **not** change the accepted WP22A production provider boundary.

Cloud.ru Evolution remains the selected Stage-2 production security boundary: one managed-cloud VM + private VPC + private Managed PostgreSQL + managed secrets/KMS/recovery controls after the required cost/security/legal gates.

Cloud.ru Container Apps free tier may be used only for synthetic/non-private Stage-1 proof as already documented. It is not silently promoted to real-user durable production because current first-party documentation does not provide a safe Container Apps -> Managed PostgreSQL private path.

## 8. Acceptance gates for CI recovery

Before this recovery can replace Lenovo as required CI authority:

- CircleCI GitHub App access is limited to the canonical repository;
- initial no-secret/no-deploy capacity probe is GREEN;
- immutable image/toolchain inputs are pinned or hash-verified where needed;
- Python 3.12.10 remains exact;
- Node/Web toolchain remains lock-reproduced;
- PostgreSQL 18 remains exact for database/recovery rehearsals;
- mandatory repository/security/Web/PostgreSQL/WP22A checks execute rather than skip;
- CI cost-control guard is updated from the obsolete Lenovo-only assumption without weakening zero-spend discipline;
- GitHub self-hosted jobs cease to be mandatory/applicable while the physical node is unavailable;
- exact-head DRAFT cycle is GREEN;
- zero unresolved blockers;
- fresh READY exact-head cycle is GREEN;
- squash merge;
- post-merge hosted Regression Shield is GREEN on the exact new `main`.

Until those gates pass, PR #336 remains DRAFT and WP22A Phase 2 is not accepted.
