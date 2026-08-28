# FL-058 — Deferred bootstrap debt becomes current when an excluded consumer enters the required acceptance chain

Status: **ADDITIVE FAILURE-LEARNING ENTRY; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-28**  
WP / PR / reference: **Governance PR #402 blocker / issue #406 / accepted bootstrap repair PR #405**

## Symptom / failing gate

PR #405 correctly repaired a deliberately narrow dependency-closed set of six self-hosted workflows after repeated exact-SHA Git/Schannel bootstrap transport failures. Its runbook and FL-057 explicitly retained the remaining single-attempt self-hosted consumers as known adjacent debt rather than pretending that the whole repository had been migrated.

After PR #405 was accepted, fresh PR #402 verification proved that some of those previously deferred consumers were now direct required gates. `V10 Live Gateway Authority Contract` and `V10 WP22 System Admin Audit` reproduced the same pre-code Windows Schannel / `curl 56` / `early EOF` / `invalid index-pack output` failure class. The accepted-main `V10 Phase 4 Free Preview Deploy` lifecycle reproduced the same bootstrap failure before provider mutation, and its downstream Hosted Release Alignment is a direct current consumer with both an initial fetch and a post-probe current-main reconfirmation fetch.

The first repair was therefore valid for its original dependency closure but no longer sufficient for the expanded current acceptance chain.

## Root-cause analysis

The technical defect class did not change: several current self-hosted workflows still treated one HTTPS `git fetch` attempt as authoritative and some cleanup paths still assumed that checkout had created `HEAD`.

The process-level root cause was narrower: the accepted regression guard encoded the exact six-workflow closure needed by PR #405, while the runbook deliberately documented the broader single-attempt domain as deferred. Once PR #402 and the accepted-main deployment lifecycle made additional consumers directly applicable, that deferred debt became an immediate blocker and had to be activated as one coherent current dependency closure rather than patched one failing workflow at a time.

## Blast radius searched

Issue #406 reviewed the current PR and accepted-main lifecycle rather than bulk-rewriting every historical workflow.

The direct current closure is:

- `v10-live-gateway-authority-contract.yml`;
- `v10-wp16-web-design-system-audit.yml`;
- `v10-wp17-application-shell-audit.yml`;
- `v10-wp18-portfolio-dashboard-audit.yml`;
- `v10-wp19-watchtower-incidents-audit.yml`;
- `v10-wp20-research-dossier-audit.yml`;
- `v10-wp21-decision-risk-plan-audit.yml`;
- `v10-wp22-system-admin-audit.yml`;
- `v10-wp22a-clientless-access-audit.yml`;
- `v10-wp22a-phase2-product-auth-audit.yml`;
- `v10-phase4-free-preview-deploy.yml`;
- `v10-hosted-release-alignment.yml`.

Historical one-shot acceptance workflows, unrelated WP15 surfaces and the future #401 verifier/provider migration remain outside this focused correction because no direct current dependency evidence requires them.

## Why preflight missed it

PR #405 did not silently miss the wider domain: `V10_CI_ACTION_DOWNLOAD_RESILIENCE.md` and FL-057 explicitly recorded it. The miss was temporal/applicability-related. At the time of the first blocker repair, expanding to every historical consumer would have increased CI cost and scope without being necessary to prove that repair.

Fresh accepted evidence later changed applicability. The excluded consumers became direct gates in the exact lifecycle being verified. The previous narrow regression tuple therefore remained historically correct but was no longer sufficient as the only retry-coverage guard.

## Corrective change

Issue #406 applies the already accepted transport pattern to the newly direct current closure:

- exactly three bounded attempts for repository fetch transport only;
- `http.lowSpeedLimit=1000` and `http.lowSpeedTime=60`;
- fresh `.git` state for each initial bootstrap attempt;
- job-scoped read-only GitHub token authority;
- non-interactive Git/GCM;
- temporary credential-helper removal after every attempt;
- exact reviewed/event SHA verification after successful fetch;
- explicit non-zero failure after retry exhaustion;
- cleanup safe when bootstrap never produced `HEAD`.

Project tests, lint, type checks, Web builds, security scans, provider mutation and deployment logic are not retried.

Hosted Release Alignment keeps its existing TOCTOU protection. Its post-probe current-main reconfirmation gets a separate bounded read-only retry loop without deleting the already verified checkout. Reconfirmation exhaustion fails non-zero and withholds runtime PASS; a successful fetch still suppresses PASS when a newer `main` has superseded the expected SHA.

## Permanent regression / guard

`tests/test_v10_ci_action_download_resilience.py` now separates three contracts:

1. the historical six-workflow PR #405 retry closure;
2. the current issue #406 critical follow-up retry closure;
3. the Hosted Release Alignment dual-fetch/TOCTOU contract.

The guard requires retry markers, bounded attempt counts, explicit fail-closed exits, pre-`HEAD`-safe cleanup, and the ordering that prevents hosted runtime PASS from being published before successful post-probe main reconfirmation.

## Future prevention rule

A deliberately narrow blocker fix is valid only while excluded analogous consumers are not part of the current required acceptance chain.

When fresh evidence makes a previously deferred analogous consumer directly applicable, do not patch only the first newly failing workflow. Recompute the current dependency closure, activate the complete directly required subset, add deterministic coverage for that new closure, and leave genuinely historical/future surfaces deferred unless their own evidence makes them current.

Conversely, known blast radius alone does not authorize bulk migration. Scope follows current dependency evidence, not fear of every hypothetical future failure.

## Dependency/tooling knowledge change

Self-hosted Git/Schannel transport reliability is a cross-workflow execution property. Regression coverage therefore needs two dimensions: stable security semantics across the whole authority plane and explicit retry coverage for every workflow that is part of the **current** required acceptance/deployment chain.
