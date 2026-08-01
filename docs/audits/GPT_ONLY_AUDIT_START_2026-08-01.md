# GPT-only audit start — 2026-08-01

Status: **Stage 0 started; no runtime or trading change**  
Exact base `main`: `fd6c10392ade19a7ada63148cb479802c47ac4f8`  
Working branch: `agent/adopt-final-step-by-step-master-plan`

## 1. Scope declaration

The supported user product is the existing Custom GPT **Omni-CIO API | Управляющий и аналитик** inside ChatGPT.

Included:

- existing Custom GPT configuration;
- canonical Instructions and Knowledge;
- Web Search / Data Analysis as enabled capabilities;
- GPT Actions;
- minimal protected Gateway;
- T-Invest and approved official public sources;
- GitHub code, tests, documentation and history.

Excluded from the current product scope:

- separate website or web cabinet;
- mobile application;
- separate chat UI;
- duplicate Custom GPT;
- self-hosted reasoning model;
- Telegram bot as a second interface.

Current mode remains strict read-only with `trading_methods=false`, GET-only user Actions and stable `app:app`.

## 2. Owner PDF verification

Source: `OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU(1).pdf`.

Verified locally:

- SHA-256: `c4a2f940ecd3dff730f6a29c5f5389363d53b6f6463a8370896c1d606bc84355`;
- PDF 1.7;
- 19 A4 pages;
- not encrypted;
- text-based, OCR not required;
- 62 outline items;
- embedded fonts;
- no form fields or attachments;
- visual render of all pages completed without missing pages.

The document requires context restoration and factual audit before new functions. Its preferred sequence is:

1. close the current compatibility/CI tail;
2. synchronize status and documentation;
3. audit the existing Custom GPT configuration;
4. normalize Knowledge and Actions;
5. prove Gateway end-to-end use;
6. implement portfolio, market and decision workflows only after the audit gates.

## 3. Fresh GitHub evidence

### Current main

Verified current `main`:

`fd6c10392ade19a7ada63148cb479802c47ac4f8`

Latest merge message records the pytest `9.1.1` compatibility package and preservation of:

- 1241 tests;
- 61.97% branch-inclusive coverage;
- exactly 14 GET Actions;
- `trading_methods=false`.

This commit identity matches the starting snapshot in the owner PDF.

### PR #31

Verified PR #31 `CI: bump fastapi from 0.140.9 to 0.141.1`:

- state: open;
- mergeable: true;
- base: `main` at `fd6c10392ade19a7ada63148cb479802c47ac4f8`;
- head branch: `dependabot/pip/fastapi-0.140.13`;
- exact head: `31c87f21ded3ef112c0668605a5c78558b9a62f5`;
- changed files: 3;
- Regression Shield run #828: success;
- workflow run ID: `30701020160`;
- diagnostics artifact ID: `8818900784`;
- artifact digest: `sha256:a9f268b955e881078230ea20e93930728283b2869b6377008bcb17c0794bba31`;
- artifact unexpired at verification time;
- unresolved review threads: none returned.

This proves the historical compatibility head is green against the recorded base. Merge decision still requires review of the actual dependency/lock delta, warning classification and confirmation that the head/base have not moved.

### Roadmap issue

Issue #27 correctly records current `main` and the active PR #31 compatibility gate. It also contains roadmap items inherited from the earlier architecture that conflict with the new GPT-only scope and therefore require migration review before further work.

## 4. Official platform verification

Fresh official OpenAI documentation was checked on 2026-08-01.

Confirmed:

- Instructions define GPT behavior and multi-step workflows should be explicit;
- Knowledge is reference material rather than the critical behavior workflow;
- Actions use authentication and OpenAPI JSON/YAML;
- a GPT can use Apps or Actions, but not both simultaneously;
- Actions must be tested in Preview;
- custom Actions are unavailable in Pro mode;
- the Editor exposes compatible non-Pro models when Actions are configured;
- improving Instructions and examples should precede adding tools when configuration can solve the issue.

These facts remain time-sensitive and must be checked again at GPT Editor acceptance.

## 5. Confirmed documentation drift

The following drift exists on exact base `main`:

1. `README.md` reports current main as `52a818daa64f4290fd6f551fbbc7f77bea3a94b2`, while actual `main` is `fd6c10392ade19a7ada63148cb479802c47ac4f8`.
2. `knowledge/16_CURRENT_PROGRAM_STATUS.md` also reports the stale commit `52a818...` and stale dependency pins/queue state after later merged upgrades.
3. `knowledge/00_PROJECT_MASTER_CONTEXT.md` describes Omni-CIO as an analytical cabinet, records a separate production site, requires locating a frontend repository, and keeps SberInvestments HTML cabinet and external RAG as Definition-of-Done work.
4. Issue #27 still lists frontend discovery, SberInvestments HTML import and external RAG as remaining mandatory blocks.
5. The previous `AGENTS.md` mandatory reading sequence referenced only master prompt v9 and did not require the final GPT-only execution plan.
6. Repository README and current status describe a backend-first next package (`NCR rating-action cache v1`) before completing the new plan's Custom GPT audit and end-to-end map.

Items 1–6 must be reconciled. They are not evidence that the underlying backend code is wrong; they show that roadmap and product-scope documentation no longer represent the owner's final order.

## 6. Preliminary component classification rule

During Stage 1 every component must be assigned one status:

- **active end-to-end** — used by a current GPT intent through an Action and tested response;
- **compatibility** — retained to preserve stable contracts;
- **reusable internal capability** — valid service but not yet exposed to a current GPT scenario;
- **optional future package** — outside read-only v1;
- **deprecated** — migration/rollback history only;
- **orphaned** — no importer, caller, Action, test or documented consumer;
- **conflicting** — violates the final GPT-only product scope.

No component is considered working for the user merely because it exists in Python or has unit tests.

## 7. Changes in this package

This documentation/governance package:

- adds the final GPT-only execution plan as canonical repository Markdown;
- records the exact source PDF checksum and inspection result;
- updates the master-plan index and conflict/migration rule;
- updates `AGENTS.md` so future agents must read the final plan before code changes;
- records the initial Stage 0 evidence and confirmed drift.

It does not change:

- runtime code;
- routes;
- OpenAPI;
- dependencies or locks;
- Render configuration;
- broker adapters;
- Action count;
- `app:app`;
- `trading_methods=false`;
- Telegram runtime state.

## 8. Remaining Stage 0/1 work

- inspect all mandatory repository architecture/GPT files on current `main`;
- inspect PR #31 patch, official FastAPI release notes and transitive lock delta;
- verify PR #31 job details and warning classes from diagnostics;
- audit current `gpt/INSTRUCTIONS.md`, Action catalog, OpenAPI and Knowledge manifest;
- obtain factual existing GPT Editor configuration and Preview evidence where GitHub cannot supply it;
- build the complete intent-to-output map;
- build repository manifest and orphan/compatibility classification;
- reconcile current status, README, issue #27 and master context in a separate logical package after PR #31 decision.

## 9. Next safe package

The next package is the existing PR #31 compatibility decision because it is the first gate named by the final plan and already has exact-head CI evidence.

Required result:

- merge only if the actual dependency/lock/warning review remains acceptable against current `main`;
- otherwise update or close PR #31 with explicit evidence;
- after the decision, create a separate status/documentation synchronization package;
- only then continue the factual Custom GPT configuration audit.
