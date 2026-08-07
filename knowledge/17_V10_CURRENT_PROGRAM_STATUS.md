# 17 — V10 CURRENT PROGRAM STATUS

Updated: 2026-08-07

## Executive state

Omni-CIO V10: **DEVELOPMENT STARTED / WP3 COMPLETE / BLOCK B IN PROGRESS / WP4 NEXT**.

Accepted implementation progress: **5%**.

Accepted completed work:

- Block A / WP0 — **COMPLETE (5%)**;
- Block B / WP1 — **COMPLETE**;
- Block B / WP2 — **COMPLETE**;
- Block B / WP3 — **COMPLETE**;
- GitHub Pro hybrid CI / Lenovo continuity hardening — **COMPLETE infrastructure hardening, no V10 product scope credited**;
- concrete AI/local-first planning amendment — **ACCEPTED planning authority, no runtime implementation credited**;
- GitHub Pro maximum-utilization + migration implementation discipline — **OWNER-APPROVED planning authority in PR #244, no runtime implementation credited**.

Current authorized implementation work package remains:

**WP4 — Release, build provenance and deployment contract.**

PR #244 is planning/governance/contracts only. It must not be interpreted as starting WP4, Block C, Web, broker-report implementation, Telegram, Cortex runtime or any later V10 implementation.

Owner start command: **`START V10`** received 2026-08-05.

Starting or advancing V10 never expands broker/Real-money authority by itself.

## Canonical authority

Base program:

- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;
- `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;
- `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`;
- `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`.

Accepted planning elaborations are discoverable through:

- `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`;
- `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_IMPLEMENTATION_CHECKLIST.md`;
- `docs/architecture/V10_AI_CORTEX_CONTRACT.json`;
- `docs/architecture/V10_GITHUB_PRO_UTILIZATION_CONTRACT.json`;
- `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json`;
- `docs/architecture/V10_COMPONENT_REUSE_MATRIX.json`;
- `docs/architecture/V10_RELEASE_MANIFEST.schema.json`.

Architecture/protection authorities include:

- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/REPOSITORY_STRUCTURE.md`;
- `docs/architecture/V10_V9_BASELINE_FREEZE.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.md` + `.json`;
- `docs/architecture/V10_REGRESSION_SHIELD.md`.

Protected production/recovery baseline remains:

**Omni-CIO v9.0.0 — COMPLETE / owner-accepted / controlled maintenance.**

## Progress

| Block | Planned weight | Accepted state |
|---|---:|---|
| A. Architecture and V9 protection | 5% | COMPLETE — WP0 |
| B. GitHub, dependencies and CI/CD | 9% | WP1 COMPLETE / WP2 COMPLETE / WP3 COMPLETE / WP4 NEXT |
| C. Lenovo Omni-CIO Node / infrastructure | 12% | NOT STARTED as V10 runtime block |
| D. V10 Core and data | 14% | NOT STARTED |
| E. Omni-CIO Web Platform | 14% | NOT STARTED |
| F. Telegram | 8% | NOT STARTED |
| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |
| H. Guardian / Watchtower Loop | 8% | NOT STARTED |
| I. Personal Real Execution | 7% | NOT STARTED |
| J. Integration / hardening / recovery / release | 5% | NOT STARTED |
| **TOTAL** | **100% planned** | **5% ACCEPTED** |

No partial Block B percentage is credited. Its 9% weight becomes accepted only after WP4 and the Block B Exit Gate are accepted.

## Accepted WP0–WP3 evidence

- WP0 PR #228 -> `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 PR #229 -> `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 PR #230 -> `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 PR #236 -> `289ff563e99a64bbf8b5a289e84668dde58ef42a`.

WP3 established the permanent Regression Shield/anti-bypass contracts, fast hosted PR feedback, compatibility gates, capability-aware future contracts and required protection model for private `main`.

## GitHub Pro hybrid CI / Lenovo continuity evidence

Infrastructure PR #242 — `Infra: GitHub Pro hybrid CI + Lenovo continuity` — is **MERGED**.

Post-merge `Regression Shield` run `31128835442` completed **SUCCESS** on that infrastructure main SHA.

The accepted hybrid model is:

- GitHub-hosted runners = fast/clean-room acceleration and modern-toolchain compatibility;
- Lenovo `omni-cio-ci` = authoritative heavy Windows gate and continuity lane;
- private `main` = protected by active `Protect main` ruleset;
- required merge context = `V10 authoritative merge gate` from GitHub Actions;
- merge method = squash only;
- no permanent bypass is part of the accepted protection model.

The Lenovo already being a GitHub self-hosted runner does **not** mean Block C V10 runtime is implemented. Ollama/Cortex/DB/Web/Telegram/research/node bootstrap remain future Block C+ work after WP4.

## Accepted concrete V10 planning lock

The current active planning authorities make the V10 direction concrete without changing block weights/order:

- deterministic Core is the financial/accounting source of truth;
- V10 portfolio/accounting target uses verified broker HTML reports; no photo/screenshot/OCR portfolio workflow;
- MOEX is current-market enrichment and remains distinct from broker period-end accounting facts;
- AI is a local-first **Omni-CIO Cortex**, not a general-purpose chatbot;
- initial AI baseline is **Qwen3.5-4B via Ollama**, replaceable behind an AI-provider boundary;
- paid AI/search/agent SaaS is not required for V10 Definition of Done;
- 24/7 autonomy is event-driven and checkpointed, not an endless LLM loop;
- initial agent orchestration candidate is LangGraph OSS;
- self-hosted SearXNG is the initial search-provider baseline with bounded HTTP/Playwright retrieval;
- all material research uses Evidence Store provenance/freshness/identity binding;
- System Policy + typed tools + RAG + evals precede any QLoRA decision;
- AI has no direct broker-write token/tool, unrestricted administrator shell, GitHub protection bypass or Real-money authority;
- OWNER local participation is requested only for genuinely non-delegable actions, preferably as one reviewed PowerShell block.

## GitHub Pro maximum-utilization / migration-development lock

PR #244 adds planning authority only. Future implementation must obey:

- V10 is migration/productization of the accepted system, not a greenfield rewrite;
- every material V9 capability in scope is tracked in the parity ledger;
- material components receive `REUSE_AS_IS | WRAP_ADAPTER | EXTRACT_TO_CORE | REWRITE_REQUIRED | RETIRE` decisions before replacement work;
- default preference is reuse/wrap/extract; rewrite requires a concrete reason and parity evidence;
- every WP uses `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`;
- GitHub Pro is maximized before another recurring paid engineering subscription is proposed;
- GitHub-hosted Ubuntu is the fast lane, hosted Windows is the path-aware clean-room compatibility lane, Lenovo is the authoritative/heavy and later GPU AI-eval lane;
- hosted Actions minutes are a finite acceleration budget; quota exhaustion must not disable authoritative safety gates;
- Actions cache/artifacts are used for build acceleration/short-lived evidence, never private portfolio state, secrets, DB backups or model weights;
- Codespaces is optional clean-room development/handoff, never production/Real/broker-secret storage;
- GitHub Releases + protected `v10.*` tag identity + release manifest become WP4 provenance goals;
- GitHub Environments are deployment identity/history/scoping, not broker-secret custody;
- Dependabot and repository-controlled SAST/dependency/secret/SBOM checks remain the no-extra-subscription supply-chain baseline;
- Enterprise/GHAS-only private-repository features are not V10 prerequisites;
- new recurring paid service requires explicit OWNER-approved amendment after documenting why GitHub Pro + Lenovo + open-source/self-hosted alternatives are insufficient.

## Current authorized next step — WP4

WP4 remains the next implementation package. It must finish release/build provenance and deployment contracts before the full V10 Lenovo runtime is configured.

WP4 is now pre-specified to include:

- release manifest generation/validation against `V10_RELEASE_MANIFEST.schema.json`;
- exact Git SHA/version/toolchain/dependency-lock/SBOM provenance;
- `v10.*` release/tag identity and strongest safe current-plan tag protection;
- path-aware hosted CI routing;
- documented hosted-minute/cache/artifact budget and review procedure;
- exact CI evidence linkage and rollback target;
- future AI model/policy/adapter provenance fields without installing AI during WP4;
- fail-closed tests for malformed/incomplete provenance;
- no dependence on Enterprise-only private artifact attestations.

WP4 must **not** install Ollama/Qwen, build the V10 Web product, change broker accounting behavior, configure the full V10 Lenovo application node or start Block C.

After WP4 and the Block B Exit Gate are accepted, Block C may begin the reproducible Lenovo V10 node/bootstrap work.

## Money/safety rule

GitHub access, AI output, research result, Watchtower alert, Telegram message, `START V10`, development approval or model output is never broker-submit authorization.

Current V9 money-path invariants and kill switches remain binding until an explicitly responsible later V10 work package replaces a boundary and passes its Exit Gate.
