# Omni-CIO V10 — Program Lock

Status: **OWNER-APPROVED PROGRAM / DEVELOPMENT STARTED / WP3 COMPLETE / WP4 NEXT**  
Baseline: **Omni-CIO v9.0.0 — COMPLETE / PROTECTED / controlled maintenance**  
Searchable canonical plan: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Owner-readable PDF: `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`  
Integrity manifest: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`  
Amendments index: `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`  
Concrete execution amendment: `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`  
Machine-readable AI contract: `docs/architecture/V10_AI_CORTEX_CONTRACT.json`  
Current progress authority: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

## 1. Authority

The OWNER approved Omni-CIO V10 as the next and only feature-development program after completed V9 and explicitly issued **`START V10`** on 2026-08-05.

The canonical base program remains one synchronized pair:

- `OMNI_CIO_V10_MASTER_PLAN.md` — searchable engineering source;
- `Omni-CIO_V10_Master_Plan_RU.pdf` — synchronized owner-readable copy;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` — integrity fingerprints.

The synchronized pair is not edited piecemeal. OWNER-approved implementation clarifications are recorded through the amendment mechanism and are discoverable through `OMNI_CIO_V10_AMENDMENTS_INDEX.md`. A later intentional consolidation may fold accepted amendments into a newly synchronized Markdown/PDF pair.

If the synchronized pair, manifest, Program Lock and accepted amendments conflict materially, feature implementation stops until an OWNER-reviewed correction establishes one consistent authority set.

## 2. Accepted program state and sequence

Accepted evidence:

- planning accepted by PR #227;
- WP0 accepted by PR #228 as `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 accepted by PR #229 as `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 accepted by PR #230 as `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 accepted by PR #236 as `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- GitHub Pro hybrid CI + Lenovo continuity hardening accepted by PR #242; current accepted `main` after that infrastructure merge is `4b034e52c94619f1a7b2cf5dcae5248185a5f45b`.

Post-merge Regression Shield run `31128835442` succeeded on that accepted `main` SHA.

**WP4 — Release, build provenance and deployment contract is the next authorized implementation package.**

Block B is still **IN PROGRESS** and its 9% weight is not credited until WP4 and its Block Exit Gate are accepted. Overall accepted V10 progress remains **5%**.

The full V10 Lenovo runtime remains Block C after WP4. The already-operational GitHub self-hosted runner does not count as implementation of the V10 application/AI/database node.

## 3. Frozen architecture and repository authority

Architecture sources established by accepted work include:

- `docs/architecture/V10_SYSTEM_ARCHITECTURE.md`;
- `docs/architecture/V10_SECURITY_BOUNDARIES.md`;
- `docs/architecture/V10_DATA_FLOW.md`;
- `docs/architecture/V10_THREAT_MODEL.md`;
- `docs/architecture/V10_RECOVERY_CONTRACT.md`;
- `docs/architecture/V10_ADR_PROCESS.md`;
- `docs/architecture/V10_V9_BASELINE_FREEZE.md`;
- `docs/architecture/REPOSITORY_STRUCTURE.md`;
- `docs/architecture/V10_TOOLCHAIN_BASELINE.md` + `.json`;
- `docs/architecture/V10_REGRESSION_SHIELD.md`;
- `.github/CODEOWNERS` and permanent repository/CI guards.

The accepted Concrete Execution Plan additionally freezes ambiguous implementation choices without changing the canonical block order/weights.

## 4. Concrete V10 implementation lock

The following OWNER-approved rules are binding for later owning work packages:

### 4.1 One product, two cooperating layers

V10 uses one **Deterministic Core** and one **Omni-CIO Cortex**.

- Deterministic Core owns financial/accounting truth, normalization, reconciliation, exact calculations, source identity, permissions and money-path enforcement.
- AI Cortex owns interpretation, explanation, bounded research, tool orchestration, monitoring and non-authoritative scenarios/drafts.
- AI must never silently replace deterministic numbers with its own arithmetic.

### 4.2 V10 portfolio/accounting target

The new V10 cabinet uses **verified broker HTML report import** as the primary accounting/portfolio input. Photo/screenshot/OCR portfolio import is outside the accepted V10 target.

The report path must be safe, period-agnostic, deduplicated, reviewable, reconcilable and historical. Current V9 runtime behavior remains protected until the responsible V10 Core/data package passes its Exit Gate.

MOEX current quotes are market enrichment and must remain explicitly separate from broker period-end facts.

### 4.3 Local-first AI baseline

The approved initial AI baseline is **Qwen3.5-4B via Ollama**, behind a replaceable provider boundary.

V10 Definition of Done must not require a paid OpenAI/Anthropic/Google/other AI inference subscription, paid search API or hosted agent SaaS. GitHub Pro remains the accepted engineering subscription.

Initial context target is 8K; 16K requires measured hardware acceptance. Model/digest/quantization/license/policy/adapter provenance and rollback are mandatory.

### 4.4 Specialization sequence

Do not jump directly to fine-tuning. The sequence is:

`System Policy -> typed Tool Registry -> Knowledge/RAG -> sanitized eval corpus -> measured local benchmark -> QLoRA only if persistent measured gaps remain`.

### 4.5 24/7 autonomy

Autonomy is **event-driven**, checkpointed and bounded. Endless untriggered LLM thinking is forbidden.

Approved research baseline is a provider abstraction with self-hosted SearXNG first, normal bounded HTTP retrieval first and Playwright only as a browser fallback. Material research must use evidence/provenance/freshness/identity binding.

LangGraph OSS is the initial orchestration candidate for durable workflows/checkpoint/resume/HITL; the deterministic Core must not depend on LangGraph internals.

### 4.6 Authority firewall

AI may autonomously use allowlisted read/analytical/research tools and persist bounded cache/evidence/task state.

AI never receives directly:

- raw broker trading secret;
- arbitrary broker execute/PostOrder tool;
- transfer/withdrawal authority;
- unrestricted administrator shell/PowerShell;
- arbitrary filesystem/SQL/network authority;
- GitHub protection/CI/OWNER bypass;
- Real-money approval authority.

Sensitive/destructive/security/admin/secret/merge/Real-money actions remain explicit human/engineering boundaries.

### 4.7 OWNER local participation

Engineering sessions perform GitHub/code/CI work directly whenever available. Local machine participation is requested only when it is genuinely non-delegable.

Preferred local interaction:

`open PowerShell -> Administrator only if required -> paste one reviewed idempotent block -> return PASS/FAIL evidence`.

The permanent AI process must run least-privilege rather than as Administrator.

Exact details are authoritative in `OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md` and `V10_AI_CORTEX_CONTRACT.json`.

## 5. Program exclusivity

Until V10 reaches full Definition of Done and OWNER acceptance:

- do not start V11 or another competing version program;
- do not create a parallel frontend, Telegram architecture, AI stack, Gateway, broker/execution stack or competing roadmap;
- do not merge an older unaccepted planning PR if it conflicts with an accepted amendment;
- do not skip directly to public/multi-user, billing or Real execution;
- brainstormed chat ideas are not approved scope until incorporated through an OWNER-approved amendment;
- the current Custom GPT remains migration/recovery evidence until explicit parity/decommission acceptance;
- Account Independence / Deployment Portability remains binding.

## 6. Account Independence / Deployment Portability

- GitHub is the engineering Control Plane/source of truth, not one ChatGPT account, IDE, website builder, hosting dashboard or laptop;
- Web/API/AI/Telegram sources, schemas, migrations, policies, tests, deployment/bootstrap/recovery contracts stay repository-controlled where technically possible;
- Lenovo is the first Personal runtime node, not architectural ownership of V10;
- broker/Telegram/encryption secrets and private portfolio/runtime payloads remain outside GitHub;
- GitHub engineering access never implies broker trading authority;
- final V10 acceptance requires clean-room recovery/portability using GitHub + documented bootstrap + authorized backup + separately restored secrets/private state.

## 7. Sequential delivery rule

Mandatory default process:

`restore context -> identify exactly one current WP -> focused branch -> implementation + tests -> security/boundary review -> exact-head required gates -> resolve review threads -> squash merge -> post-merge verification where required -> update V10 status -> next WP`.

A WP is not complete because files/UI exist. Completion requires its Exit Gate and required integration/recovery evidence.

## 8. GitHub protection rule

Private `main` is now protected by the accepted `Protect main` ruleset. The accepted merge model requires:

- pull request workflow;
- squash as the only merge method;
- conversation resolution;
- strict required check `V10 authoritative merge gate` from GitHub Actions;
- no routine bypass actor;
- no direct weakening of CI/ruleset to make a PR green.

GitHub-hosted lanes provide fast/clean-room acceleration. Lenovo `omni-cio-ci` remains the authoritative heavy Windows/continuity lane. Infrastructure outages are handled by documented incident procedures, not permanent weakening of protection.

## 9. Money and safety boundary

The completed V9 money/safety invariants remain binding unless a later responsible V10 WP explicitly replaces a boundary and passes all acceptance gates:

- READ, Sandbox and Real credentials remain isolated;
- no autonomous unconfirmed Real execution;
- immutable plan before submit;
- short-lived exact OWNER confirmation bound to the plan;
- one possible broker submit per idempotent identity;
- ambiguous possible-submit is never automatically retried;
- `submitted` is not `filled` without broker evidence;
- no transfer/withdrawal, margin/short or hidden authority expansion;
- AI has no direct broker-write authority;
- developer/GitHub access is never trading authorization.

Master Real rollback remains `REAL_TRADING_ENABLED=false`.

## 10. Source-of-truth order during V10

1. accepted `main`;
2. `AGENTS.md` for mandatory engineering/safety rules;
3. this Program Lock;
4. synchronized V10 Master Plan Markdown/PDF + integrity manifest;
5. `OMNI_CIO_V10_AMENDMENTS_INDEX.md` and accepted active amendments;
6. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` for current WP/progress;
7. accepted current V10 architecture/ADR/runbook/machine-readable contracts;
8. current PR/CI/runtime acceptance evidence;
9. historical PR/issues/amendments only as trace evidence.

When canonical authorities conflict materially, feature work stops until an OWNER-reviewed correction resolves the conflict.

## 11. Completion rule

V10 is not complete until the canonical 100% program, accepted amendments, final capability/evidence matrix, AI/local-first/degraded-mode gates, clean-room recovery/portability, final security/reliability gates and OWNER acceptance all pass.

Until then no successor version is authorized.
