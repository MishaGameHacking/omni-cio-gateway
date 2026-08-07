# Omni-CIO V10 — GitHub Pro Maximum Utilization and Migration Implementation Amendment

**Status:** OWNER-APPROVED PROGRAM AMENDMENT / PLANNING AUTHORITY  
**Date:** 2026-08-07  
**Implementation effect:** planning only; this document does not start WP4 or any later V10 implementation  
**Primary intent:** make V10 implementation deterministic, auditable, subscription-minimal, and recoverable from GitHub without relying on chat memory  
**Feature-expansion intent:** NO

## 1. Executive rule

Omni-CIO V10 is a controlled **productization and migration of the accepted V9 system into the V10 architecture**, not a greenfield rewrite and not a feature-expansion program.

The default engineering path is:

`accepted V9 capability -> identify canonical V10 owner -> REUSE/WRAP/EXTRACT decision -> contract -> implementation -> deterministic parity evidence -> staged cutover -> retirement only after acceptance`.

No future developer/AI session may invent a replacement architecture, add an unrelated service, choose a paid SaaS, rewrite a working engine, or skip an Exit Gate merely because it appears convenient.

GitHub Pro is the engineering Control Plane for V10. The Lenovo node is the primary self-hosted compute/runtime node, but it is replaceable. GitHub-hosted runners provide disposable clean-room acceleration; Lenovo provides authoritative heavy validation and local AI/GPU validation where required.

## 2. Subscription-minimization policy

V10 Definition of Done must be achievable with the subscriptions/resources already approved unless an OWNER-approved amendment explicitly changes this rule.

Baseline:

- GitHub Pro: approved and intentionally maximized;
- Lenovo hardware: approved existing resource;
- open-source/self-hosted software: preferred where practical;
- paid AI API: not required;
- paid search/research API: not required;
- paid CI/security SaaS: not required;
- GitHub Enterprise Cloud: not required;
- GitHub Advanced Security products: not required;
- additional hosted databases/queues/observability services: not required unless a later measured constraint proves necessity and OWNER approves.

A paid service may be proposed only after the developer records:

1. the exact missing capability;
2. why GitHub Pro + Lenovo + open-source/self-hosted alternatives cannot satisfy it safely;
3. expected monthly/annual cost;
4. migration/lock-in consequences;
5. fallback if the subscription is cancelled;
6. whether it changes V10 Definition of Done.

The default decision is **do not add the subscription**.

## 3. GitHub Pro capability policy

GitHub Pro is used as far as it provides real engineering value without weakening privacy or creating false dependencies.

Approved uses include:

- private repository as engineering source of truth;
- protected `main` / repository rulesets;
- pull requests and squash-only reviewed integration;
- CODEOWNERS as responsibility mapping;
- GitHub Actions standard hosted runners within included quota;
- self-hosted Lenovo runner for heavy/free compute;
- Actions cache;
- short-lived workflow artifacts;
- GitHub Releases and immutable release identity controls available on the current plan;
- GitHub Environments for deployment state/branch scoping where supported on private Pro repositories;
- Dependabot alerts/security updates/version updates;
- dependency graph and SBOM export/generation;
- GitHub Issues as WP/defect/decision work records;
- GitHub Projects where useful as a living V10 program board;
- Codespaces for clean-room development/recovery verification where the included quota is useful;
- Repository Insights for engineering visibility;
- email support if a GitHub platform defect blocks the program.

Explicit non-assumptions:

- private-repository artifact attestations are not a V10 prerequisite on GitHub Pro;
- private-repository native GitHub code scanning/CodeQL is not assumed available on GitHub Pro;
- private-repository native GitHub secret scanning/push protection is not assumed available on GitHub Pro;
- private-environment required reviewers/wait timers are not assumed available on GitHub Pro;
- private GitHub Pages is not used as an authority or private documentation host.

When a GitHub feature is plan-gated, V10 must implement a repository-controlled/open-source equivalent only if the underlying safety requirement is material.

## 4. Engineering source-of-truth hierarchy

The following order governs development:

1. accepted `main`;
2. Program Lock;
3. Master Plan;
4. Amendments Index + active OWNER-approved amendments;
5. machine-readable architecture/contracts;
6. current program status;
7. current-WP runbook/acceptance contract;
8. open PR/issues and exact-head CI evidence.

Chat memory, historical PR descriptions, screenshots, developer intuition, and old branches are not program authority.

## 5. V9 -> V10 parity ledger contract

Every material accepted V9 capability must have one row/object in `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json` before its owning V10 work package can claim completion.

Required fields:

- stable capability ID;
- V9 domain/capability name;
- exact V9 source/module/function/API/tool references once inventoried;
- accepted semantic meaning;
- current tests/evidence protecting the meaning;
- V10 canonical owner/domain;
- V10 API/DTO/tool/UI destinations where applicable;
- migration method;
- data migration requirement;
- rollback/fallback;
- parity oracle;
- status;
- owning WP;
- evidence links/commit/run identifiers once implemented.

Allowed statuses:

`BASELINE_IDENTIFIED | CONTRACT_DEFINED | IMPLEMENTED | PARITY_PROVEN | INTENTIONALLY_RETIRED | BLOCKED`.

A V10 release cannot claim migrated parity while a material row remains `BASELINE_IDENTIFIED`, `CONTRACT_DEFINED`, `IMPLEMENTED` or `BLOCKED`, unless the Master Plan explicitly assigns it to a later version.

`INTENTIONALLY_RETIRED` requires OWNER approval and a written reason.

## 6. Component reuse/rewrite decision contract

Before modifying a material V9 component for V10, it must receive one migration decision in `V10_COMPONENT_REUSE_MATRIX.json`:

- `REUSE_AS_IS` — behavior/code remains authoritative;
- `WRAP_ADAPTER` — preserve engine, add V10 boundary/DTO/API adapter;
- `EXTRACT_TO_CORE` — move/isolate reviewed logic without changing financial meaning;
- `REWRITE_REQUIRED` — replacement is necessary and must prove parity;
- `RETIRE` — OWNER-approved removal.

Default preference order:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

`REWRITE_REQUIRED` must name at least one concrete reason:

- security defect;
- incompatible architecture boundary;
- untestable/unrecoverable implementation;
- unsupported dependency/runtime;
- proven correctness defect;
- impossible data contract migration;
- explicit Master Plan replacement requirement.

“Cleaner code”, “newer framework”, “AI prefers another architecture”, or “easier to rewrite” are not sufficient reasons.

## 7. Canonical financial acceptance oracles

Migration correctness is judged by domain truth, not by visual similarity.

### 7.1 Broker-period accounting truth

Verified broker HTML report data is canonical for report-period composition, quantities, cash balances, trades, commissions, taxes, coupons/dividends and report-period accounting facts.

For the same normalized input and schema version, deterministic accounting results must match the accepted expected values using exact Decimal/rounding rules.

### 7.2 Current market truth

MOEX/current-market enrichment is separate from broker-period accounting. Comparison tests must bind quote/source identity and `as_of` time. A price fetched at a different timestamp is not a deterministic regression oracle.

### 7.3 Risk/strategy/optimizer truth

The same canonical portfolio snapshot + policy/version + deterministic inputs must produce reproducible reviewed output. Any intentional formula/semantic change requires a versioned contract and explicit migration evidence.

### 7.4 AI/Cortex truth

AI acceptance does not require identical prose. It requires measurable behavior:

- correct tool selection;
- no invented exact financial facts;
- no broker-write/admin authority;
- valid structured output/schema;
- evidence/source binding where required;
- correct unknown/insufficient-data behavior;
- prompt-injection resistance at the authority boundary;
- deterministic Core remains operational when AI is unavailable.

## 8. Canonical DTO / schema registry rule

Web, Telegram, Cortex and adapters must consume canonical Core contracts rather than reinterpret raw storage or calculate competing financial values.

Expected versioned families include, as required by owning WPs:

- `BrokerReportV1`;
- `PortfolioSnapshotV1`;
- `PositionV1`;
- `CashBalanceV1`;
- `TradeV1`;
- `CashMovementV1`;
- `ReconciliationResultV1`;
- `RiskSnapshotV1`;
- `EvidenceV1`;
- `IncidentV1`;
- `DecisionV1`;
- `ImmutablePlanV1`;
- `ExecutionStateV1`;
- `SystemHealthV1`;
- `CapabilityStateV1`.

Contract conventions:

- money/quantity use Decimal-safe serialized representation;
- currency explicit where ambiguity exists;
- UTC canonical timestamps;
- source identity and `as_of` where material;
- schema version explicit;
- canonical identifiers preferred over display names;
- `0`, `unknown`, `not_available`, `not_applicable`, `stale`, and `partial` are distinct states;
- frontend/AI never reconstruct financial meaning from formatted display strings.

## 9. Unified runtime state/degradation contract

V10 uses a consistent state vocabulary:

`READY | PARTIAL | STALE | DEGRADED | BLOCKED | ERROR | OFFLINE | RECOVERING | OWNER_ACTION_REQUIRED`.

Each owning WP must define:

- trigger condition;
- what data remains trustworthy;
- what actions remain allowed;
- what becomes blocked;
- retry/backoff semantics;
- user-visible state;
- audit/health evidence.

Binding examples:

- MOEX unavailable -> broker-period truth remains valid; current estimate becomes stale/unavailable; no invented price;
- Cortex/Ollama unavailable -> deterministic Core/Web portfolio/system health continue;
- Telegram unavailable -> Core remains operational; notification delivery is degraded, not financial truth;
- DB unavailable/corrupt -> state-mutating and Real paths fail closed;
- broker freshness insufficient -> affected live/current/Real paths block; historical verified report remains separately valid;
- research source unavailable -> evidence gap is explicit; AI cannot fill it from memory as fact.

## 10. Work Package execution standard

Every WP implementation PR must be preceded or accompanied by an explicit WP execution contract containing:

1. accepted baseline;
2. WP purpose;
3. owner/authority domain;
4. exact inputs/prerequisites;
5. existing code/data/contracts to reuse;
6. component reuse/rewrite decisions;
7. files/domains allowed to change;
8. explicit non-goals;
9. interfaces/schemas created or changed;
10. persistence/migration effects;
11. security/authority boundary effects;
12. normal-path acceptance tests;
13. negative/failure tests;
14. observability/diagnostics;
15. rollback/recovery path;
16. exact Exit Gate;
17. evidence required to mark accepted;
18. next WP unlocked by acceptance.

Scope rule: if discovered work is not required to satisfy the current WP Exit Gate, it must not be silently implemented. It becomes either:

- a blocker/defect of the current WP with justification;
- a future-WP issue;
- an amendment proposal if architecture/scope changes.

## 11. Parallel-run and cutover contract

V9 remains the protected fallback until V10 capability-by-capability parity and final acceptance permit retirement.

Migration sequence for each material capability:

`V9 baseline -> V10 implementation -> shadow/parallel verification where meaningful -> parity evidence -> V10 primary -> observation -> V9 freeze -> later retirement`.

Forbidden:

- deleting the old capability immediately after a first successful V10 test;
- changing production authority because the new UI appears complete;
- retiring Custom GPT/V9 before consuming V10 paths have parity evidence;
- treating a successful unit test as full product cutover evidence.

Retirement requires:

- parity proven;
- required data migration/reconciliation complete;
- consuming surfaces on V10;
- rollback/recovery documented and tested at the owning gate;
- no unresolved material blocker.

## 12. Scope firewall — V10 is not feature expansion

Without a new OWNER-approved amendment, V10 work is limited to:

- migration/parity of accepted V9 capabilities;
- already-approved broker-report V10 accounting path;
- already-approved Web productization;
- already-approved Telegram adapter;
- already-approved Cortex/local-first AI/research layer;
- 24/7 Watchtower/Guardian behavior already in the plan;
- optional Real execution already governed by Block I;
- platform/security/reliability/recovery/observability required by existing scope;
- defects discovered while proving the above.

Examples requiring later amendment or future version:

- additional brokers;
- public multi-user SaaS;
- billing/subscriptions;
- new unrelated investment products/features;
- autonomous discretionary Real trading;
- new paid AI/search platforms as a default dependency;
- a second Core/website/AI brain competing with V10.

## 13. GitHub Actions compute-routing contract

V10 uses three complementary compute classes.

### 13.1 Hosted Ubuntu — fast lane

Purpose: fastest low-cost PR feedback.

Typical responsibilities:

- repository/program/security contracts;
- schema validation;
- Python compile/static checks that do not require Windows;
- Ruff/mypy where suitable;
- frontend type/lint/unit/build;
- documentation/link/schema checks;
- lightweight parser/unit tests;
- dependency metadata checks.

### 13.2 Hosted Windows — disposable compatibility lane

Purpose: prove V10 can reproduce on a clean GitHub Windows image and selected toolchain.

Triggered when relevant paths change and before release candidates.

Typical responsibilities:

- selected Python/Node runtime compatibility;
- Windows install/lock reproducibility;
- clean-room full or targeted tests;
- frontend Windows compatibility;
- build/SBOM generation;
- bootstrap compatibility checks once Block C exists.

### 13.3 Lenovo self-hosted Windows — authoritative/heavy lane

Purpose: heavy validation without consuming hosted Actions minutes and validation against the primary Personal Node hardware.

Typical responsibilities as capabilities appear:

- authoritative Regression Shield;
- full deterministic suite;
- broker/parser reconciliation fixtures;
- SAST/dependency/secret scans implemented by repository-controlled tools;
- Web E2E/browser suite;
- recovery/bootstrap integration checks appropriate for the node;
- Ollama/Qwen integration;
- AI evals/tool-use/factuality/prompt-injection tests;
- GPU/VRAM/latency benchmarks;
- QLoRA experiments only after the approved gate.

Lenovo runner jobs must not gain access to trading secrets/private runtime state merely because they run on the same physical device.

## 14. Path-aware CI policy

Hosted CI minutes must be spent according to changed risk/domain rather than blindly running every clean-room matrix on every documentation edit.

The implementation in WP4/owning CI package should classify changes into at least:

- docs/program only;
- backend/Core/contracts;
- broker/parser/data;
- frontend;
- infrastructure/bootstrap;
- AI/Cortex/evals;
- dependency/toolchain;
- release/security authority.

Minimum routing principle:

- fast policy/source checks: every PR;
- authoritative merge gate: every merge candidate;
- hosted Windows compatibility: only when relevant paths/toolchain/release require it;
- GPU AI eval: only when AI model/policy/tool/RAG/eval-relevant paths change or release gate requires it;
- full release/recovery matrix: release candidates and explicit release/recovery workflows.

`concurrency` with `cancel-in-progress` is required where stale runs have no audit value.

## 15. Actions minute budget

GitHub Pro included hosted Actions minutes are treated as a finite acceleration budget, not as the only compute resource.

Planning target allocation per billing cycle:

- 50% fast PR/ordinary hosted validation;
- 25% clean-room compatibility;
- 15% release/recovery validation;
- 10% incident/emergency reserve.

These percentages are operating targets, not hard GitHub limits. WP4 must implement observability/documentation sufficient to review actual consumption and adjust routing without weakening gates.

Rules:

- self-hosted work should absorb heavy repeatable tests when safe;
- no intentional paid overage is required for V10 Definition of Done;
- if included quota nears exhaustion, hosted acceleration may degrade, but authoritative Lenovo gates remain available;
- quota exhaustion must not cause direct pushes or disabled safety checks.

## 16. Cache policy

Actions cache is used for reproducible dependency/build acceleration, not as durable project state.

Approved cache classes when useful:

- pip/download wheels;
- npm;
- Playwright browser downloads;
- safe build tool caches;
- public/static analysis databases where deterministic/freshness policy permits.

Forbidden cache classes:

- broker reports/private portfolio data;
- secrets/tokens;
- durable DB backups;
- Qwen model weights if their size would evict higher-value CI caches;
- authoritative release evidence.

Cache keys must bind relevant lock/toolchain/platform identity and tolerate safe misses.

## 17. Artifact/storage policy

Artifacts are short-lived CI evidence, not the durable source of truth.

PR artifact defaults:

- retention 1–3 days unless a specific debugging/review need justifies longer;
- prefer GitHub Job Summary/logs for human-readable diagnostics when artifact storage is unnecessary.

Suitable artifacts:

- SBOM;
- coverage/test reports;
- sanitized E2E screenshots/videos for failing runs;
- release manifest candidates;
- sanitized AI eval reports;
- small build bundles when needed for a downstream job.

Do not store:

- model weights;
- raw broker reports containing private financial data;
- DB backups;
- secret-bearing logs;
- large indefinite datasets.

Accepted release provenance is committed/tagged/released through the release contract, not dependent on a disposable PR artifact surviving.

## 18. Codespaces clean-room contract

GitHub Codespaces is optional acceleration/recovery proof, not production and not a secret-bearing Personal Node.

A future `.devcontainer` may be added in its owning WP to prove that an authorized developer/AI session can obtain a clean development environment from GitHub-controlled configuration.

Allowed uses:

- clean clone/development shell;
- Core/frontend unit/contract work;
- documentation/schema work;
- migration/bootstrap dry-run components that do not require private state;
- emergency development if Lenovo is unavailable;
- clean-room handoff evidence.

Forbidden uses:

- production portfolio runtime;
- broker/Telegram secrets by default;
- Real execution;
- private DB restore unless a later explicit secure recovery test governs it;
- Qwen GPU production assumptions.

Codespaces usage must remain optional: V10 remains recoverable on an approved replacement node without Codespaces.

## 19. GitHub Releases / tag identity contract

WP4 must establish the V10 release identity and provenance mechanism.

Each accepted release/pre-release must bind at minimum:

- semantic version;
- immutable Git SHA;
- build timestamp/identity;
- Python version;
- Node/npm version where applicable;
- dependency lock digests;
- frontend lock digest;
- DB migration/schema head when applicable;
- API/schema versions;
- broker parser version;
- policy/security contract version;
- AI model identity/digest/quantization when applicable;
- AI adapter digest when applicable;
- SBOM digest(s);
- CI workflow/run evidence;
- compatible bootstrap/recovery version;
- rollback target/instructions.

The machine-readable schema is `V10_RELEASE_MANIFEST.schema.json`.

Release tags use the `v10.*` namespace and must be protected from silent deletion/rewriting using the strongest rules available on the current plan without breaking the reviewed release workflow.

Native private-repository GitHub artifact attestations are an optional future enhancement if the account plan later supports them; they are not a V10 prerequisite.

## 20. GitHub Environments contract

Environments are used for deployment identity/state and supported branch/tag restrictions, not as the primary broker secret store.

Planned logical environments:

- `v9-recovery`;
- `v10-staging`;
- `v10-production`.

Existing legacy environments must be inventoried and either mapped, renamed through a safe migration, or retired in the owning deployment WP. They must not remain unexplained duplicates.

Environment use may include:

- deployment record/history;
- non-secret variables;
- narrowly scoped deployment credentials if unavoidable and approved;
- allowed branch/tag policy supported by GitHub Pro private repositories.

Do not design V10 around private-environment required reviewers/wait timers that are not available on the current Pro plan.

Broker READ/TRADING tokens, Telegram token and V10 encryption keys belong to the local runtime secret boundary, not ordinary GitHub environment secrets.

## 21. Dependabot / supply-chain policy

Dependabot remains enabled for every repository-controlled dependency ecosystem that materially exists.

Required baseline as ecosystems appear:

- Python/pip;
- frontend npm;
- GitHub Actions;
- additional supported ecosystem only when the project actually uses it.

Preferred PR-noise policy:

- group compatible minor/patch version updates by ecosystem where safe;
- keep security remediation visible and prioritized;
- respect lock/hash reproducibility;
- no auto-merge solely because Dependabot opened the PR;
- dependency PR must pass the same relevant V10 gates.

Repository-controlled security substitutes remain mandatory where GitHub Pro private-repository native premium controls are unavailable:

- dependency audit;
- SAST/lint security checks;
- secret-pattern/history/worktree scanning appropriate to the repo;
- SBOM generation;
- pinned GitHub Action commits;
- least-privilege `GITHUB_TOKEN` permissions;
- `persist-credentials: false` unless explicitly required;
- hash-locked dependencies where the selected ecosystem supports the project policy.

## 22. GitHub Project / Issues program-control contract

GitHub Issues are the durable unit of work for WPs, blockers, defects and explicitly deferred items when the relevant project-management surface is adopted.

Recommended Project fields:

- Block;
- WP;
- Status;
- Risk;
- Exit Gate;
- V9 Parity;
- Owner Action Required;
- PR;
- CI/Regression State;
- Release Target.

Recommended views:

- Next WP;
- Active;
- Blocked;
- Owner Action Required;
- V9 Parity Gaps;
- Security;
- AI Cortex;
- Web;
- Release Candidate.

Project automation must not replace repository authority: the Master Plan/status files remain canonical for program meaning; Project is the operational view.

## 23. CODEOWNERS/review policy

CODEOWNERS maps responsibility, but normal V10 development must not require the OWNER to manually approve every routine implementation PR if authoritative automated gates can safely decide it.

Owner review should be reserved for changes that materially alter:

- Master Plan/program scope;
- security/authority boundaries;
- broker-write/Real execution authority;
- secret custody model;
- required merge/deployment security policy;
- irreversible migration/retirement decision;
- subscription/cost baseline;
- OWNER acceptance gates explicitly requiring human decision.

Routine implementation remains governed by focused PR + exact-head automated gates + review-thread resolution + plan compliance.

## 24. WP4 concrete planning target

WP4 remains the next implementation package, but this amendment does **not** start it.

When implementation is later authorized, WP4 must produce/verify at minimum:

1. canonical `V10_RELEASE_MANIFEST.schema.json` integration;
2. release manifest generator/validator;
3. Git SHA/version/toolchain/lock/SBOM provenance capture;
4. release/pre-release naming/tag contract;
5. strongest safe release-tag protection available on the current plan;
6. path-aware hosted CI routing policy;
7. documented Actions-minute/cache/artifact budget and monitoring procedure;
8. release evidence linking exact CI run(s);
9. rollback target/instructions;
10. plan-aware handling for future AI model/policy/adapter provenance fields without requiring AI to be installed during WP4;
11. no Enterprise-only/private-attestation dependency;
12. tests proving malformed/incomplete release provenance fails closed.

WP4 must not install Ollama/Qwen, build the V10 Web product, change broker accounting behavior, or start Block C.

## 25. Plan-aware implementation algorithm for future AI/developer sessions

Before changing code, the developer must execute this mental/repository procedure:

1. read the authority chain;
2. identify exactly one current authorized WP;
3. inspect accepted V9 implementation for owned capability;
4. update/verify parity + reuse decisions;
5. state the WP execution contract;
6. create focused branch;
7. implement the smallest change satisfying the Exit Gate;
8. add deterministic normal/negative tests;
9. run the cheapest relevant local/hosted checks first;
10. run authoritative exact-head gate;
11. inspect all review/CI findings;
12. fix without broadening scope;
13. update parity/status/provenance docs in the same PR when required;
14. merge only after exact-head acceptance;
15. run required post-merge sentinel;
16. advance status to the next WP only when the current Exit Gate evidence is complete.

If a required decision is absent from repository authority and would materially affect architecture/security/data/authority/cost, stop and ask the OWNER instead of inventing it.

## 26. Definition of Done for this planning amendment

This planning amendment is complete when it is accepted into `main` through the existing protected PR process and the repository contains:

- this textual authority;
- GitHub Pro machine-readable utilization contract;
- V9->V10 parity ledger seed;
- component reuse matrix seed;
- release manifest schema;
- Amendments Index entry;
- no implementation of WP4 or later V10 runtime behavior as part of this planning-only PR.

Acceptance of this document authorizes future implementation **only through the existing WP sequence and OWNER start decisions already defined by the Program Lock**. It does not authorize skipping directly to later blocks.
