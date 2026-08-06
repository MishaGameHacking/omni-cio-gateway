# Omni-CIO V10 — Concrete Execution Plan Amendment

Status: **OWNER-APPROVED PLANNING AMENDMENT / IMPLEMENTATION BOUNDARY LOCK**  
Date recorded in GitHub: **2026-08-07**  
Applies to: **Omni-CIO V10 Personal Autonomous Investment Platform**  
Base program: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Program Lock: `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`

## 0. Why this amendment exists

The canonical V10 Master Plan intentionally defines the full program at a high level. This amendment makes the OWNER-approved implementation intent concrete enough that future AI/developer sessions do not invent architecture from chat memory or choose a different AI/data/runtime direction ad hoc.

This document **does not renumber the canonical blocks, change their weights or permit out-of-order implementation**. It narrows ambiguous implementation choices and adds mandatory acceptance criteria.

If an older unmerged PR, chat message, screenshot or draft conflicts with this accepted amendment, accepted `main` plus this amendment takes precedence. The synchronized Master Plan Markdown/PDF pair is not edited independently by this focused amendment; it can be reconsolidated intentionally later.

## 1. Current program handoff

Accepted program evidence before this amendment:

- WP0 — architecture/program freeze: complete;
- WP1 — repository architecture/boundaries: complete;
- WP2 — toolchain/dependency baseline: complete;
- WP3 — Regression Shield/repository protection: complete and squash-merged by PR #236;
- GitHub Pro hybrid CI + Lenovo continuity hardening: complete and squash-merged by PR #242;
- private `main` is protected by `Protect main` and requires `V10 authoritative merge gate` from GitHub Actions;
- GitHub-hosted runners are acceleration/clean-room compatibility lanes;
- Lenovo `omni-cio-ci` is the authoritative heavy Windows gate and continuity lane;
- protected V9 runtime remains the current production/recovery baseline while V10 is built.

**Next authorized implementation package after acceptance of this planning amendment remains WP4 — Release, build provenance and deployment contract.** This amendment is planning/governance only and must not silently start WP4 runtime work.

## 2. Final product definition

V10 is not “a website with an AI chat widget”. It is one personal investment operating system with two cooperating layers:

```text
                         OMNI-CIO V10
                              |
             +----------------+----------------+
             |                                 |
     DETERMINISTIC CORE                    AI CORTEX
     financial source of truth             local intelligence
             |                                 |
      parse / normalize                    understand
      reconcile                            research
      calculate                            explain
      validate                             orchestrate
      enforce                              monitor
             |                                 |
             +----------- SAFE TOOLS ---------+
                              |
          broker reports / MOEX / CBR / official sources
          Web / Telegram / System Health / Evidence Store
```

### 2.1 Deterministic Core owns truth

The LLM must not become the calculator, ledger, portfolio database or broker authority. Exact financial values are produced by deterministic code and versioned schemas.

The Core owns at minimum:

- broker-report parsing and validation;
- normalized portfolio/accounting model;
- cash, positions, trades, commissions, taxes, coupons/dividends and accrued-interest representation;
- reconciliation and discrepancy reporting;
- market quote ingestion and freshness;
- portfolio/risk/concentration/cash-flow calculations;
- immutable plans and all money-path safety rules;
- source identity, timestamps and provenance;
- permissions and tool results consumed by AI.

The AI may explain or compare these values but may not silently replace them with its own arithmetic.

### 2.2 AI Cortex owns intelligence, not authority

The AI Cortex is a narrow Omni-CIO operator, not a general-purpose assistant. Its approved domain is:

- the OWNER portfolio and its accepted data;
- V10 capabilities and system health;
- investment/risk/research explanation;
- evidence-backed issuer/instrument research;
- explanation of calculations and data gaps;
- orchestration of allowlisted read/analysis tools;
- event-driven background research and monitoring;
- generation of alerts, summaries, scenarios and publication drafts from verified data.

Out-of-domain requests may be declined or answered only when they are directly necessary to operate/explain Omni-CIO.

## 3. V10 accounting/data source hierarchy

### 3.1 V10 portfolio/accounting source of truth

For the new V10 cabinet, the approved primary accounting input is a **verified broker HTML account report import**. Image/photo/screenshot/OCR portfolio import is not part of the V10 target.

The report import must:

- parse data only; never execute report HTML/JS/CSS;
- detect arbitrary report periods;
- validate MIME/encoding/size/required structures;
- calculate SHA-256 and reject/identify duplicates;
- normalize decimal comma/point, spaces, negative values, row/column spans and empty cells;
- support securities, bonds, nominal price %, accrued interest, cash balances, trades, commissions, taxes and income sections;
- distinguish “recognized”, “partially recognized” and “unsupported” formats;
- never claim electronic-signature authenticity unless a real signature is actually verified;
- show a review/validation screen before analytics is accepted;
- retain a report archive with replace/delete/compare/history semantics;
- reconcile totals and surface discrepancies instead of hiding them.

The current V9 T-Invest-based runtime remains protected during migration. V10 must not silently change V9 production behavior before the responsible V10 Core/data work package passes its Exit Gate.

### 3.2 Live market data

MOEX market data is enrichment for **current market valuation**, not a replacement for broker accounting facts.

The UI/data contracts must explicitly distinguish:

- `broker_period_end_state` — what the broker report says at the end of its period;
- `current_market_estimate` — current valuation using fresh market quotes.

### 3.3 External research source priority

For factual research use the narrowest authoritative source available:

1. imported broker report for account/operations truth;
2. MOEX for supported market/instrument data;
3. CBR/regulator official data;
4. official issuer/company disclosures;
5. other official/primary documents;
6. reputable secondary media;
7. general Web search as discovery/context.

A web result cannot override an authoritative portfolio/accounting record.

## 4. Approved local AI baseline

### 4.1 Default model

The first approved V10 local model baseline is:

- **Qwen3.5-4B**;
- open-weight model under **Apache-2.0** license;
- local inference first;
- quantized deployment targeted initially at **Q4_K_M or equivalent validated 4-bit build**;
- Russian is a first-class product language;
- tool calling is mandatory;
- multimodal/image use is **not required** for V10 and must not reintroduce OCR/photo portfolio ingestion.

The model is a replaceable provider implementation, not a dependency of the deterministic Core.

### 4.2 Inference runtime

Default runtime: **Ollama on the Lenovo Windows node**.

Mandatory runtime rules:

- bind AI API to localhost/private application boundary by default;
- never expose raw Ollama directly to the public Internet;
- record model name, artifact/digest, quantization and license in a versioned model manifest;
- model/runtime upgrades require benchmark + regression/eval + rollback evidence;
- auto-update must not silently change accepted AI behavior.

### 4.3 Context policy

Initial local operating context is intentionally bounded:

- start at **8K context**;
- 16K may be enabled only after measured VRAM/latency/stability acceptance;
- very large advertised model context is not a product requirement on the current node;
- retrieval should pass only relevant evidence rather than dumping the whole project into context.

### 4.4 No mandatory paid AI subscription

V10 Definition of Done must not depend on OpenAI, Anthropic, Google or another paid AI inference API.

A paid provider may only be added later as an explicitly optional provider through a separate OWNER-approved amendment. The local provider must remain capable of running the accepted V10 analytical/operational experience without that subscription.

## 5. AI specialization path

Do not begin with fine-tuning merely because it is possible. Specialization order is mandatory:

### Stage A — System Policy

Create a versioned Omni-CIO System Policy that defines:

- domain scope;
- source hierarchy;
- deterministic truth rule;
- missing-data behavior;
- read-only/tool authority;
- research rules;
- no-fabrication rules;
- execution prohibitions;
- response/evidence format.

### Stage B — Tool Registry

Expose narrow typed tools instead of raw DB/broker/system access.

Examples:

- `get_portfolio_snapshot()`;
- `get_portfolio_risks()`;
- `get_cash_flows()`;
- `get_report_status()`;
- `get_reconciliation_status()`;
- `get_market_data_status()`;
- `get_moex_quote()`;
- `get_system_health()`;
- `get_feature_status()`;
- `search_web()`;
- `fetch_source()`;
- `research_issuer()`.

Every tool has a schema, authority class, timeout, provenance requirements and tests.

### Stage C — Knowledge/RAG

Migrate accepted project/GPT knowledge into versioned, retrievable domain knowledge. Retrieval must be scoped to the current question and treat retrieved/external text as **data**, never as executable instructions.

### Stage D — Evaluation corpus

Build repository-controlled synthetic/sanitized evals covering at least:

- portfolio facts;
- missing/partial data;
- concentration/risk explanations;
- bond/accrued-interest semantics;
- commissions/income/cash flow;
- period comparison;
- report reconciliation;
- source freshness/provenance;
- tool selection;
- prompt-injection-shaped external content;
- system-health questions;
- prohibited broker/system authority attempts.

Critical safety acceptance requires **zero broker-write authority leakage** and **zero invented exact financial facts** in the critical deterministic fixture set.

### Stage E — QLoRA only if measured gap remains

Only after Stages A-D are working may an Omni-CIO QLoRA adapter be considered. Fine-tuning must target observed recurrent failures, not general “make it smarter” goals.

The base model, adapter, dataset revision and evaluation results are separately versioned and independently rollbackable.

## 6. 24/7 autonomous operation

### 6.1 Event-driven, not endless thinking

The AI must not run an uncontrolled `while true: think()` loop. It wakes for explicit events or scheduled bounded jobs.

Approved triggers include:

- user question;
- new accepted broker report;
- report discrepancy;
- stale market/source data;
- material change detected by deterministic Watchtower;
- failed connector/source;
- scheduled research refresh;
- system-health degradation;
- pending evidence gap for an active analysis;
- an OWNER-approved background research policy.

Idle periods should not burn GPU cycles without purpose.

### 6.2 Agent orchestration baseline

Approved initial orchestration candidate: **LangGraph OSS**, because V10 needs durable state/checkpoints, restart/resume, bounded long-running research and human-in-the-loop on sensitive actions.

The architecture must remain modular: if LangGraph becomes unsuitable, replacing it must not require rewriting Core financial logic.

### 6.3 Persistence

Autonomous tasks have persistent IDs and checkpointed state. A Windows/process restart must not cause an already completed research step or side effect to be blindly repeated.

At prototype stage a local simple persistence backend may be used; production V10 persistence must follow the canonical DB/recovery contract and survive service restart.

## 7. Autonomous Web Research

### 7.1 Search layer

Approved no-subscription-first baseline: **self-hosted SearXNG** behind an internal adapter.

The application depends on a `SearchProvider` interface, not directly on one public SearXNG instance.

### 7.2 Fetch layer

Default:

- normal HTTP retrieval and parser for static HTML/documents;
- Playwright/Chromium only as a bounded fallback for JavaScript-rendered sources;
- strict request timeout/size/content-type limits;
- no execution of downloaded scripts as trusted application code;
- robots/terms/licensing/retention review for sources where applicable.

### 7.3 Evidence Store

Every material research fact must be bound to evidence metadata such as:

- source URL/identity;
- source class/authority;
- retrieved_at;
- published_at when available;
- document/content hash where practical;
- instrument/issuer identity binding;
- extracted fact/claim;
- contradiction/freshness state;
- confidence is derived from evidence quality, not model self-confidence alone.

The user-facing answer should be able to show “data as of” and source provenance for material conclusions.

## 8. Tool authority firewall

Tool permissions are explicit and fail closed.

### AUTO — allowed without OWNER confirmation

- read portfolio/analytics/reconciliation/system health;
- read approved local knowledge;
- retrieve public/official market/research data;
- perform bounded Web search/fetch;
- write research cache/evidence/checkpoints/log-safe diagnostics;
- create non-money alerts and analytical drafts.

### BOUNDED LOCAL WRITE — allowed only through deterministic service contracts

- update research cache;
- persist agent checkpoint/task status;
- store sanitized evidence metadata;
- update derived analytical state that can be regenerated from source data.

The LLM itself receives no arbitrary SQL/filesystem shell.

### HUMAN/ENGINEERING APPROVAL REQUIRED

- destructive private-data deletion;
- security/firewall/service policy changes;
- Windows administrator actions;
- secret changes;
- GitHub protection/ruleset changes;
- production deployment with changed authority boundary;
- code merge to `main`;
- any Real-money plan approval/submit.

### NEVER DIRECTLY EXPOSED TO AI

- raw broker trading token;
- arbitrary `PostOrder`/execute tool;
- transfer/withdrawal authority;
- unrestricted shell/PowerShell administrator execution;
- unrestricted filesystem/network scanner;
- bypass of GitHub/Regression Shield or OWNER approval.

## 9. User-facing AI behavior

The Web user must be able to ask questions in Russian about both the portfolio and V10 itself, for example:

- what changed in the portfolio/report period;
- why risk/concentration is high;
- why current valuation differs from broker period-end value;
- which data is stale/missing;
- how a metric was calculated;
- why an import/reconciliation failed;
- when MOEX/research data last updated;
- which V10 capability is currently available/degraded;
- how report import, research or monitoring works;
- what evidence supports a conclusion.

The AI must explicitly say when the necessary data is unavailable. “Недостаточно данных” is a valid and preferred result over fabricated precision.

## 10. Windows/Lenovo deployment philosophy

The Lenovo node is the first Personal runtime node, but not the architectural owner of V10.

Current hardware is treated as an acceptance target, not a permanent hard dependency. Infrastructure work must benchmark actual CPU/RAM/VRAM/storage before choosing operational limits.

When an action can be completed through GitHub/code/CI, the engineering agent should do it without OWNER involvement. When local Windows access is genuinely required, OWNER participation should be minimized to:

`open PowerShell (Administrator only when needed) -> paste one reviewed idempotent block -> return output/evidence`.

The bootstrap must detect existing state and avoid destructive reinstall/reconfiguration unless explicitly requested.

AI runtime services must run with least privilege. Administrator rights are for installation/service registration/system configuration, not the permanent AI process identity.

## 11. Lenovo resource arbitration

The same Lenovo currently serves GitHub CI and will later host local AI/runtime workloads. These roles must not fight for resources unpredictably.

Required design:

- identify when the authoritative GitHub runner is busy;
- pause/deprioritize heavy AI background research/training while critical CI runs;
- interactive user AI may remain available with bounded resources where feasible;
- QLoRA/training jobs never overlap an authoritative merge gate by default;
- GPU/CPU/RAM pressure and temperature/availability are observable;
- a failed AI service must not take down deterministic Core or the GitHub runner.

## 12. Concrete instructions by V10 block

The canonical block order/weights remain unchanged. The following requirements are mandatory elaborations.

### Block A — Architecture / V9 protection

Already accepted. Preserve V9 recovery, one-Core boundary and authority separation. Do not rewrite accepted financial engines merely to suit the LLM.

### Block B — GitHub / dependencies / CI/CD

WP1-WP3 are accepted. WP4 must finish release/build provenance and deployment contract before the full Lenovo V10 runtime is configured.

WP4 must additionally define future AI artifact provenance fields (provider, model ID, model digest, quantization, license, policy version, adapter revision) even though AI implementation itself belongs later.

### Block C — Lenovo Omni-CIO Node / infrastructure

Implement reproducible PowerShell-first bootstrap and node contracts:

- hardware/Windows/NVIDIA/time/disk/port prerequisite audit;
- least-privilege service identities;
- local secret-store contract;
- database/runtime backup paths;
- health/watchdog/autostart;
- GitHub runner coexistence;
- Ollama runtime installation/smoke/provenance only as infrastructure capability;
- resource arbitration;
- service recovery/restart testing;
- no public raw Ollama endpoint;
- no autonomous AI authority merely because the runtime is installed.

### Block D — V10 Core and data

Make broker HTML report import and normalized accounting model production-grade before AI depends on it. Implement report archive, comparison, reconciliation, portfolio/cash/trade/income/commission contracts, MOEX current valuation and explicit historical-vs-current state separation.

AI cannot compensate for missing deterministic data contracts.

### Block E — Web Platform

The Web is the primary OWNER cabinet. It must expose truthful states and source/freshness, not static/demo values.

Required product areas remain: Overview, Reports, Portfolio, Operations, Analytics, Rebalancing, AI Strategist/Publications, Sources/Settings plus System Health/AI status where appropriate.

Before import: honest empty state. After import: report validation and OWNER confirmation precede analytics. Mobile >=360 px, Light default + usable Dark, accessibility and critical E2E are mandatory.

### Block F — Telegram

Telegram is an alert/deep-link/light conversation adapter over the same Core/Cortex. It must not become a second portfolio database, second AI brain or alternate money authority.

### Block G — AI Copilot / Research / GPT Migration

This block implements the **Omni-CIO Cortex** using the approved sequence:

1. migrate GPT knowledge/policy into repository-controlled System Policy/RAG assets;
2. implement typed Tool Registry and authority firewall;
3. integrate Qwen3.5-4B via Ollama provider adapter;
4. implement conversational portfolio/system assistance;
5. implement SearXNG-based research provider + bounded fetch/browser fallback;
6. implement Evidence Store and citation/provenance output;
7. implement LangGraph-style durable research workflows/checkpoints;
8. implement deterministic/sanitized AI eval suite;
9. benchmark local latency/VRAM/context and lock accepted runtime limits;
10. consider QLoRA only after measured eval gaps;
11. keep Custom GPT as recovery/parity reference until explicit parity/decommission acceptance.

### Block H — Guardian / Watchtower Loop

Turn AI/Core cooperation into event-driven 24/7 operation:

- deterministic events trigger AI/research tasks;
- deduplicate/coalesce repeated triggers;
- use cooldowns/budgets/timeouts;
- preserve task checkpoints;
- escalate missing evidence/system degradation;
- notify without creating money authority;
- continue deterministic monitoring when AI is unavailable.

### Block I — Personal Real Execution

No change to the absolute authority boundary. AI may explain or prepare analytical context but never owns broker write credentials or an execute tool.

Real execution, if enabled in the accepted V10 program, remains:

`verified facts -> deterministic Decision/Plan -> exact OWNER approval -> preflight -> bounded submit -> reconciliation -> Journal`.

### Block J — Integration / hardening / recovery / release

Final acceptance must test:

- AI unavailable/degraded mode;
- Internet/research unavailable mode;
- broker report corrupt/partial mode;
- stale MOEX mode;
- Windows/AI service restart and checkpoint recovery;
- model rollback;
- GitHub runner + AI resource contention;
- clean-room restoration to another approved node;
- no-subscription local AI operation;
- Web/Telegram same-Core consistency;
- Custom GPT parity/decommission decision;
- final capability/evidence matrix.

## 13. AI evaluation and CI requirements

When `ai/` capabilities begin to appear, Regression Shield must fail closed unless the AI contract/eval suite exists.

At minimum CI must verify:

- policy/schema files parse and are versioned;
- tool schemas are deterministic and authority-classified;
- AI never receives broker-write tool definitions;
- critical fixtures cannot produce an accepted answer with invented exact financial values;
- prompt-injection-like evidence is treated as untrusted data;
- evidence citations point to supplied evidence IDs/records;
- model/provider failure returns controlled degraded state;
- AI output is never the only input to a money-path submit decision;
- local-model upgrade requires explicit eval delta and rollback manifest.

Do not weaken tests because a local model is nondeterministic. Put nondeterminism behind bounded contracts and test deterministic acceptance properties.

## 14. Cost/subscription rule

Design target: **minimum recurring subscriptions**.

- GitHub Pro: already accepted engineering subscription/control plane;
- local Qwen/Ollama: no inference subscription;
- LangGraph OSS: no required hosted subscription;
- SearXNG/self-hosted research layer: no required search API subscription;
- Playwright: local open-source browser automation;
- paid AI/search/agent SaaS: not required for V10 Definition of Done.

If a later requirement cannot be met safely without a paid service, stop and present the OWNER with the exact benefit/cost/alternative before adding the dependency.

## 15. No-fake-product rules

V10 acceptance rejects:

- decorative AI that does not call real tools;
- hard-coded/demo portfolio values presented as live;
- fake refresh/research/export buttons;
- “AI confidence” with no evidence basis;
- hidden fallbacks to stale/unknown data presented as current;
- silently using Web search where an official structured source exists;
- autonomous task success without durable outcome/evidence;
- background AI loops without explicit trigger/budget;
- enabled UI actions whose backend authority is absent.

## 16. Engineering autonomy / OWNER participation

Future engineering sessions should restore state from GitHub and work autonomously through focused branches/PRs.

OWNER participation is requested only for non-delegable actions such as:

- local Windows/UAC/physical machine operations;
- account/billing UI that available tools cannot change;
- secret entry/rotation;
- security/recovery-key acceptance;
- final external product acceptance;
- exact Real-money confirmation.

For local machine work, the preferred interaction is a reviewed PowerShell block with built-in checks and clear PASS/FAIL output, not a long sequence of GUI clicks.

## 17. Definition of Done added by this amendment

The AI/autonomy part of V10 is not complete until all of the following are evidenced:

- local open-weight provider is the accepted default and works without paid AI API;
- Qwen3.5-4B baseline or an explicitly owner-approved replacement passes Omni-CIO evals;
- AI can answer portfolio/system questions only from typed Core/evidence inputs;
- AI can autonomously run bounded research and resume after restart;
- research has source/freshness/provenance and external content cannot acquire tool authority;
- deterministic Core remains fully usable when AI is stopped;
- no broker-write credential/tool is reachable by AI;
- GitHub CI protects model/policy/tool/eval changes;
- Lenovo CI and AI workloads coexist under tested resource arbitration;
- no OCR/photo portfolio workflow exists in the accepted V10 target;
- final recovery drill proves the platform can be rebuilt from GitHub + documented bootstrap + separately restored authorized private state/secrets.

## 18. External technical references reviewed for this amendment

The implementation must re-check current official documentation in the owning work package before pinning versions. Current planning basis:

- Qwen3.5-4B official model card / Apache-2.0 license / tool-use capable model family: `https://huggingface.co/Qwen/Qwen3.5-4B`;
- Ollama tool calling: `https://docs.ollama.com/capabilities/tool-calling`;
- LangGraph durable execution/persistence/HITL: `https://docs.langchain.com/oss/python/langgraph/overview` and related persistence/HITL docs;
- SearXNG HTTP Search API: `https://docs.searxng.org/dev/search_api.html`;
- Playwright browser automation: `https://playwright.dev/docs/intro`.

These links justify candidate technology selection; accepted GitHub code, version locks, tests and measured compatibility remain the implementation authority.
