# Omni-CIO V10 — Program Lock

Status: **OWNER-APPROVED PROGRAM / ACTIVE / SCOPE-SEQUENCE LOCK**  
Baseline: **Omni-CIO v9.0.0 — COMPLETE / PROTECTED / controlled maintenance**  
Searchable canonical plan: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Owner-readable PDF: `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`  
Integrity manifest: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256`  
Amendments index: `docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md`  
Concrete execution amendment: `docs/master-plan/OMNI_CIO_V10_CONCRETE_EXECUTION_PLAN_AMENDMENT.md`  
GitHub Pro / migration implementation amendment: `docs/master-plan/OMNI_CIO_V10_GITHUB_PRO_AND_MIGRATION_IMPLEMENTATION_AMENDMENT.md`  
Autonomous governance/commercial amendment: `docs/master-plan/OMNI_CIO_V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_AND_COMMERCIAL_MODEL_AMENDMENT.md`  
Identity/authentication amendment: `docs/master-plan/OMNI_CIO_V10_IDENTITY_MULTI_TENANT_ACCOUNT_AND_AUTHENTICATION_AMENDMENT.md`  
Phone/headless-node amendment: `docs/master-plan/OMNI_CIO_V10_PHONE_ONLY_ENGINEERING_AND_HEADLESS_NODE_OPERATIONS_AMENDMENT.md`  
Engineering-quality amendment: `docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md`  
Mandatory WP template: `docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md`  
Machine-readable AI contract: `docs/architecture/V10_AI_CORTEX_CONTRACT.json`  
Machine-readable portfolio-governance contract: `docs/architecture/V10_AUTONOMOUS_PORTFOLIO_GOVERNANCE_CONTRACT.json`  
Russian-market/sanctions policy: `docs/architecture/V10_RUSSIAN_MARKET_UNIVERSE_AND_SANCTIONS_POLICY.json`  
Zero-custody/license/update contract: `docs/architecture/V10_ZERO_CUSTODY_LICENSE_UPDATE_CONTRACT.json`  
Russian commercial/legal gates: `docs/legal/V10_RU_COMMERCIAL_LEGAL_GATES.md`  
Machine-readable GitHub Pro contract: `docs/architecture/V10_GITHUB_PRO_UTILIZATION_CONTRACT.json`  
V9->V10 parity ledger: `docs/architecture/V10_V9_TO_V10_PARITY_LEDGER.json`  
Component reuse matrix: `docs/architecture/V10_COMPONENT_REUSE_MATRIX.json`  
Release manifest schema: `docs/architecture/V10_RELEASE_MANIFEST.schema.json`  
Current progress authority: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

**Dynamic current WP/progress is intentionally not duplicated here.** This file locks scope, sequence and precedence. The exact accepted percentage, current/next WP and transition evidence are read only from `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` on accepted `main`.

## 1. Authority

The OWNER approved Omni-CIO V10 as the next and only feature-development program after completed V9 and explicitly issued **`START V10`** on 2026-08-05.

The canonical base program remains one synchronized pair:

- `OMNI_CIO_V10_MASTER_PLAN.md` — searchable engineering source;
- `Omni-CIO_V10_Master_Plan_RU.pdf` — synchronized owner-readable copy;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` — integrity fingerprints.

The synchronized pair is not edited piecemeal. OWNER-approved implementation clarifications are recorded through the amendment mechanism and are discoverable through `OMNI_CIO_V10_AMENDMENTS_INDEX.md`. A later intentional consolidation may fold accepted amendments into a newly synchronized Markdown/PDF pair.

If the synchronized pair, manifest, Program Lock and accepted amendments conflict materially, feature implementation stops until an OWNER-reviewed correction establishes one consistent authority set.

## 2. Program sequence and historical early acceptance evidence

The Master Plan block/WP order remains mandatory. This Program Lock deliberately does not maintain a second moving `NEXT` field.

Historical early evidence establishing the program and control plane includes:

- planning accepted by PR #227;
- WP0 accepted by PR #228 as `7c5de954eed10dd406e743c38f7bdef6b0634108`;
- WP1 accepted by PR #229 as `dbd459b280de84d3f571b458b46f1039880312ca`;
- WP2 accepted by PR #230 as `3e3a89791d7f1594e4e1ba52125f8361708ae29d`;
- WP3 accepted by PR #236 as `289ff563e99a64bbf8b5a289e84668dde58ef42a`;
- GitHub Pro hybrid CI + Lenovo continuity hardening accepted by PR #242;
- concrete AI/local-first planning accepted by PR #243 as `5743608389dd0fc6eba4dc33540a61016dc98914`;
- GitHub Pro/migration planning accepted by PR #244;
- Telegram product planning accepted by PR #245;
- pre-WP4 repository hygiene accepted by PR #246.

Later accepted implementation is indexed by `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` and its evidence section. Historical wording in early package records does not roll the program back to an earlier WP.

The physical presence of later V10 code, infrastructure or a provider configuration never authorizes a Work Package on its own. Authorization and completion come only from the canonical sequence plus the current-status/Exit-Gate evidence chain.

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

Accepted planning amendments additionally freeze ambiguous implementation choices without changing the canonical block order/weights.

Documentation authority/lifecycle is defined by `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`; dated WP records remain evidence, not competing current-state ledgers.

## 4. Concrete V10 implementation lock

The following OWNER-approved rules are binding for later owning work packages.

### 4.1 One product, two cooperating layers

V10 uses one **Deterministic Core** and one **Omni-CIO Cortex**.

- Deterministic Core owns financial/accounting truth, normalization, reconciliation, exact calculations, source identity, permissions and money-path enforcement.
- AI Cortex owns interpretation, explanation, bounded research, tool orchestration, OWNER clarification/negotiation and non-authoritative scenarios/drafts.
- The **Guardian/Watchtower/Decision system**, not the LLM, is the primary 24/7 autonomous actor.
- AI must never silently replace deterministic numbers with its own arithmetic or become the canonical portfolio Decision Engine.

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

The autonomous system continuously runs deterministic/scheduled/event-driven monitoring, asset-health, Watchtower, risk, sanctions/custody, universe-screening, proposal and reconciliation workflows. Cortex is invoked only when language/research/interpretation or OWNER dialogue adds value.

Approved research baseline is a provider abstraction with self-hosted SearXNG first, normal bounded HTTP retrieval first and Playwright only as a browser fallback. Material research must use evidence/provenance/freshness/identity binding.

LangGraph OSS is the initial orchestration candidate for durable workflows/checkpoint/resume/HITL; the deterministic Core must not depend on LangGraph internals.

### 4.6 Authority firewall

AI may autonomously use allowlisted read/analytical/research tools and persist bounded cache/evidence/task state.

AI never receives directly:

- raw broker trading secret;
- arbitrary broker execute/PostOrder tool;
- transfer/withdrawal authority;
- margin/short/sanctions hard-gate override;
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

### 4.8 V10 is migration/productization, not a rewrite

Every material accepted V9 capability in V10 scope must be tracked through the parity ledger and receive a component reuse decision before material replacement work starts.

Default engineering preference:

`REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

No component is rewritten merely because a newer framework or cleaner design is available. `REWRITE_REQUIRED` needs a concrete security/correctness/runtime/architecture reason and parity evidence.

Material V9 capability retirement is blocked until parity/recovery/cutover gates pass or the OWNER explicitly approves `INTENTIONALLY_RETIRED`.

### 4.9 GitHub Pro maximum-utilization lock

GitHub Pro is the default engineering subscription and must be used before proposing another recurring paid engineering service.

Approved V10 compute model:

- GitHub-hosted Ubuntu = fast PR lane when capacity is available;
- GitHub-hosted Windows = disposable path-aware clean-room compatibility lane when capacity is available;
- Lenovo `omni-cio-ci` = authoritative heavy/self-hosted lane and later local AI/GPU eval lane.

The project must use hosted minutes as a finite acceleration budget, preserve heavy validation on Lenovo where safe, use caches/artifacts deliberately, and keep release provenance/recovery source-controlled.

V10 Definition of Done must not depend on GitHub Enterprise-only/private-repository features, GitHub Advanced Security products, paid AI/search APIs or another paid CI/security SaaS.

Plan-gated capabilities are replaced only where necessary by repository-controlled/open-source checks; lack of a premium feature is never a reason to weaken the safety requirement.

Current mutable hosted-capacity/cost state is governed by `docs/operations/V10_CI_COST_CONTROL_STANDARD.md` and must not be treated as permanent architecture.

### 4.10 Unified WP execution discipline

Every implementation WP must follow `OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md` and define accepted baseline, reuse/parity decisions, allowed changes, non-goals, interfaces, data/security effects, positive/negative tests, CI routing, rollback, Exit Gate and evidence.

Work discovered outside the current Exit Gate is not silently implemented. It becomes a current blocker/defect, future-WP item or OWNER-approved amendment.

Exact details are authoritative in the active amendments and machine-readable contracts, not chat memory.

### 4.11 Product mission — Autonomous Portfolio Governance

The central product is continuous evidence-backed portfolio governance, not a dashboard/chatbot/trading robot.

The system must monitor all held assets, maintain explicit health/freshness/trend state, detect material deterioration/opportunity, screen the allowed investment universe, evaluate portfolio impact and produce one ranked primary restructuring proposal or `NO_CHANGE`.

The normal proposal may replace one asset with one, split exposure across multiple assets, rebalance multiple positions or deliberately make no change. The system must include anti-churn/material-improvement discipline so small score differences do not cause needless turnover.

### 4.12 Russian-market-only / sanctions-custody policy

Commercial V10 candidate selection is Russian-market-only under a documented instrument-classification policy. Broker availability alone is insufficient.

Sanctions/custody risk is a hard first-class policy. `BLOCKED` instruments are excluded from new BUY proposals. Naive display-name-only sanctions matching is insufficient; evidence freshness and applicable ownership/control relationships must be handled by the owning implementation.

The product must not claim that a Russian issuer/instrument guarantees immunity from blocking/freeze. Custody, settlement, payment currency/index and external infrastructure dependencies remain analyzed risks.

### 4.13 OWNER proposal negotiation and cash-only execution

The system selects a concrete proposal and explains before/after portfolio effects. OWNER may approve, reject or request revision.

Rejection/revision triggers a concise Cortex dialogue and versioned soft PreferenceProfile/constraint change. Hard policy cannot be overridden by conversation.

Real execution supports only confirmed BUY/SELL within own cash/owned free quantity. Margin, leverage, uncovered short positions, transfers and withdrawals remain prohibited. Only an exact valid immutable proposal after fresh preflight may reach the isolated execution service.

### 4.14 Zero-custody / fixed-term paid access

Private investment state is Personal Node authority by default. Central Omni-CIO infrastructure must not become a portfolio/broker-secret/private-Cortex-history database.

The narrow central commercial plane may hold only payment/license/update/security records required for paid access and lawful operations, subject to an explicit field-level data inventory.

Commercial access model is:

`7-day full trial -> manual prepaid 1/3/6/12 month access -> EXPIRED -> explicit new payment to renew`.

Auto-renewal and recurring charges are not part of V10.

### 4.15 Automatic supported-version convergence and Russian-law launch gates

Active supported Personal Nodes automatically converge to the approved `STABLE` release. The normal product flow must not require users to manually download installers or permanently pin obsolete versions.

Updates must be signed/verified, rollback-safe, staged/atomic, health-checked and isolated from broker secrets/private state. Real execution pauses during unsafe update windows.

Commercial/public activation is fail-closed until the legal gates in `docs/legal/V10_RU_COMMERCIAL_LEGAL_GATES.md` are accepted for the actual business/data/deployment model. Engineering does not self-certify compliance with 152-FZ, consumer law, 39-FZ, broker API commercial terms, KKT/payment rules or Bank of Russia investment-advisory/software requirements.

## 5. Program exclusivity

Until V10 reaches full Definition of Done and OWNER acceptance:

- do not start V11 or another competing version program;
- do not create a parallel frontend, Telegram architecture, AI stack, Gateway, broker/execution stack or competing roadmap;
- do not merge an older unaccepted planning PR if it conflicts with an accepted amendment;
- do not skip directly to central public/multi-user SaaS, billing runtime or Real execution outside the responsible later work package and legal/security gates;
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

`restore authority -> identify exactly one current WP/defect -> focused branch -> root-cause/blast-radius review -> implementation + tests -> cheap/focused preflight -> full-diff review -> all applicable exact-head gates SUCCESS -> zero blocking review threads -> squash merge -> exact-main post-merge verification -> OWNER acceptance only if required -> update current status -> next WP`.

A WP is not complete because files/UI exist. Completion requires its Exit Gate and required integration/recovery evidence.

## 8. GitHub protection rule

Private `main` is protected by the accepted `Protect main` ruleset. The accepted merge model requires:

- pull request workflow;
- squash as the only merge method;
- conversation resolution;
- strict required check `V10 authoritative merge gate` from GitHub Actions;
- no routine bypass actor;
- no direct weakening of CI/ruleset to make a PR green.

GitHub-hosted lanes provide fast/clean-room acceleration when current capacity exists. Lenovo `omni-cio-ci` remains the authoritative heavy Windows/continuity lane. Infrastructure outages are handled by documented incident procedures and accepted routing contracts, not permanent weakening of protection or fabricated PASS evidence.

Release/tag/deployment protections added by accepted WPs use the strongest safe controls available on the current GitHub Pro plan without pretending Enterprise-only controls exist.

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
6. machine-readable contracts;
7. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` for current WP/progress;
8. accepted current V10 architecture/ADR/runbook/contracts;
9. current PR/CI/runtime acceptance evidence;
10. historical WP records/PRs/issues only as trace evidence.

When canonical authorities conflict materially, feature work stops until an OWNER-reviewed correction resolves the conflict.

## 11. Completion rule

V10 is not complete until the canonical 100% program, accepted amendments, final capability/evidence matrix, V9->V10 parity ledger, autonomous portfolio-governance gates, Russian-market/sanctions/custody gates, AI/local-first/degraded-mode gates, zero-custody/commercial/update gates, clean-room recovery/portability, final security/reliability/legal production gates and OWNER acceptance all pass.

Until then no successor version is authorized.
