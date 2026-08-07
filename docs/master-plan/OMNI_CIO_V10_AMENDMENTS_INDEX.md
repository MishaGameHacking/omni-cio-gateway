# Omni-CIO V10 — Amendments Index

Status: **ACTIVE PROGRAM INDEX**

This index exists so future engineering/AI sessions can restore OWNER-approved V10 clarifications from GitHub instead of depending on chat memory.

## Authority rule

The synchronized V10 Master Plan remains the canonical base program:

- `OMNI_CIO_V10_MASTER_PLAN.md`;
- `Omni-CIO_V10_Master_Plan_RU.pdf`;
- `OMNI_CIO_V10_MASTER_PLAN.sha256`.

Accepted amendments supplement/narrow the base plan without silently renumbering blocks or changing block weights. When an accepted amendment intentionally resolves an ambiguity, the amendment governs that implementation choice until a later OWNER-approved consolidation or superseding amendment.

Unmerged/closed draft PR text is not an accepted amendment.

## Active amendments

### 1. Account Independence / Deployment Portability

`OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`

Historical owner-approved amendment already consolidated into the canonical Master Plan. Retained for audit/provenance.

### 2. Concrete Execution Plan / AI Cortex / local-first autonomy

`OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`

Machine-readable companion:

`../architecture/V10_AI_CORTEX_CONTRACT.json`

Locks the concrete 2026-08-07 OWNER decisions:

- deterministic Core is the source of financial truth;
- V10 accounting/portfolio target is verified broker HTML report import; no photo/OCR workflow;
- MOEX is current-market enrichment and must not overwrite broker-period accounting facts;
- local-first AI baseline is Qwen3.5-4B + Ollama;
- no paid AI/search/agent SaaS is required for V10 Definition of Done;
- AI is specialized as Omni-CIO Cortex rather than a general-purpose assistant;
- tool authority is typed/allowlisted/fail-closed;
- Web research is evidence-based, SearXNG-first and browser-fallback bounded;
- 24/7 autonomy is event-driven with durable checkpoints, not an endless LLM loop;
- LangGraph OSS is the initial orchestration candidate;
- QLoRA is considered only after System Policy + tools + RAG + evals demonstrate a persistent gap;
- AI never receives direct broker-write/admin/bypass authority;
- OWNER local participation is minimized to reviewed PowerShell operations only when GitHub/code/CI cannot perform the action remotely.

### 3. GitHub Pro Maximum Utilization / V10 Migration Implementation Contract

`OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`

Machine-readable companions:

- `../architecture/V10_GITHUB_PRO_UTILIZATION_CONTRACT.json`;
- `../architecture/V10_V9_TO_V10_PARITY_LEDGER.json`;
- `../architecture/V10_COMPONENT_REUSE_MATRIX.json`;
- `../architecture/V10_RELEASE_MANIFEST.schema.json`.

Locks the OWNER-approved rule that GitHub Pro is the V10 engineering Control Plane and that V10 is a controlled productization/migration of the accepted V9 system, not a greenfield rewrite or feature-expansion program. It defines CI compute routing across GitHub-hosted runners and the Lenovo self-hosted runner, Actions-minute/cache/artifact budgets, Codespaces clean-room use, Releases/tag provenance, environment usage, dependency automation, parity/reuse rules, canonical acceptance oracles, WP execution format, cutover discipline, scope firewall, and a subscription-minimization policy.

## Draft/superseded planning material

Open or historical PR descriptions must not be treated as active plan authority merely because they contain V10 ideas. In particular, any older unmerged planning PR that conflicts with the accepted Concrete Execution Plan must be closed/superseded rather than merged as a competing roadmap.

## Required reading order for new V10 engineering sessions

1. `../../AGENTS.md`;
2. `../../knowledge/00_PROJECT_MASTER_CONTEXT.md`;
3. `OMNI_CIO_V10_PROGRAM_LOCK.md`;
4. `OMNI_CIO_V10_MASTER_PLAN.md`;
5. this Amendments Index;
6. all active amendments listed here;
7. `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
8. current-WP architecture/runbook;
9. current `main`, open PR/issues and GitHub Actions.
