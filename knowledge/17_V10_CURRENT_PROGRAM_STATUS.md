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
- GitHub Pro hybrid CI / Lenovo continuity hardening — **COMPLETE infrastructure hardening, no V10 product scope credited**.

Current authorized implementation work package after acceptance of the current planning amendment:

**WP4 — Release, build provenance and deployment contract.**

This planning amendment itself is governance/documentation only and does **not** start WP4 runtime implementation.

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
- `docs/architecture/V10_AI_CORTEX_CONTRACT.json`.

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

## Accepted WP0 evidence

WP0 PR #228 was squash-merged as:

`7c5de954eed10dd406e743c38f7bdef6b0634108`

It established the V10 architecture freeze without widening runtime or money authority.

## Accepted WP1 evidence

WP1 PR #229 was squash-merged as:

`dbd459b280de84d3f571b458b46f1039880312ca`

It established canonical repository ownership, one deterministic `omni_cio/` Core, repository-boundary guards and protected V9 compatibility.

## Accepted WP2 evidence

WP2 PR #230 was squash-merged as:

`3e3a89791d7f1594e4e1ba52125f8361708ae29d`

It froze the V10 toolchain/dependency baseline and its compatibility gates without starting Web/Telegram/AI/runtime migration.

## Accepted WP3 evidence

WP3 PR #236 — `V10 WP3: harden Regression Shield and PR gates` — is **MERGED**.

Squash merge commit:

`289ff563e99a64bbf8b5a289e84668dde58ef42a`

WP3 established the permanent Regression Shield/anti-bypass contracts, fast hosted PR feedback, compatibility gates, capability-aware future contracts and required protection model for private `main`.

## GitHub Pro hybrid CI / Lenovo continuity evidence

Infrastructure PR #242 — `Infra: GitHub Pro hybrid CI + Lenovo continuity` — is **MERGED**.

Current accepted `main` after that merge:

`4b034e52c94619f1a7b2cf5dcae5248185a5f45b`

Post-merge `Regression Shield` run `31128835442` completed **SUCCESS** on that exact `main` SHA.

The accepted hybrid model is:

- GitHub-hosted runners = fast/clean-room acceleration and modern-toolchain compatibility;
- Lenovo `omni-cio-ci` = authoritative heavy Windows gate and continuity lane;
- private `main` = protected by active `Protect main` ruleset;
- required merge context = `V10 authoritative merge gate` from GitHub Actions;
- merge method = squash only;
- no permanent bypass is part of the accepted protection model.

The Lenovo already being a GitHub self-hosted runner does **not** mean Block C V10 runtime is implemented. Ollama/Cortex/DB/Web/Telegram/research/node bootstrap remain future Block C+ work after WP4.

## Owner-approved concrete V10 implementation lock

The current planning amendment makes the previously broad V10 direction concrete without changing block weights or order:

- deterministic Core is the financial/accounting source of truth;
- V10 portfolio/accounting target uses verified broker HTML reports; no photo/screenshot/OCR portfolio workflow;
- MOEX is current-market enrichment and must remain distinct from broker period-end accounting facts;
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

Exact details and machine-readable invariants live in the amendment and `V10_AI_CORTEX_CONTRACT.json` rather than chat memory.

## Current authorized next step — WP4

WP4 remains the next implementation package. It must finish release/build provenance and deployment contracts before the full V10 Lenovo runtime is configured.

In addition to the base Master Plan, WP4 must make future AI/model provenance representable in release metadata, including provider/model identity, digest, quantization, license, policy revision and optional adapter revision. WP4 does **not** itself implement the AI runtime.

After WP4 and the Block B Exit Gate are accepted, Block C may begin the reproducible Lenovo V10 node/bootstrap work.

## Lenovo sequencing

The GitHub runner is already operational and is part of accepted CI infrastructure. Full V10 node provisioning remains deliberately sequenced after WP4 and includes future runtime/database/health/watchdog/Ollama/resource-arbitration work under Block C.

Do not install or expose the full V10 local AI/runtime stack merely because the hardware is available.

## Money/safety rule

GitHub access, AI output, research result, Watchtower alert, Telegram message, `START V10`, development approval or model output is never broker-submit authorization.

Current V9 money-path invariants and kill switches remain binding until an explicitly responsible later V10 work package replaces a boundary and passes its Exit Gate.
