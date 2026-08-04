# 16 — CURRENT PROGRAM STATUS

Дата актуализации: 2026-08-04

## Executive state

Omni-CIO remains one supported Custom GPT + one production Render Gateway.

Current production release remains **v8.6.1**:

- UI/config: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- canonical Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- read-only analytics: accepted;
- isolated T-Invest Sandbox: accepted;
- real BUY/SELL v1: owner-accepted and release-complete;
- durable journal: Upstash Redis over HTTPS;
- Render: Free;
- stable entrypoint: `app:app`;
- idempotent replay verified with no second submit;
- applied GPT remains v8.6.1 until WP15.

Protected v8.6.1 release commit:

`baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e`

## Active v9 program

Canonical owner-approved/program-locked roadmap:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Tracking epic: #176.

Development follows the earliest dependency-ready incomplete package. Stable v8.6.1 remains recoverable and its real-execution safety contract cannot be weakened by v9 feature work.

## Work-package progress

### WP0 — Baseline freeze and recovery correctness: COMPLETE

- issue #178 / PR #181;
- merged to `main` as `4fd3993bdb56162bb730dca25e3ada7046e560cc`;
- exact-head Regression Shield #989 green.

### WP1 — Natural Language CIO Router: COMPLETE

- issue #182 / PR #184;
- merged to `main` as `7f6772889837ba632dc40c893d080a35b5f902ff`;
- exact-head Regression Shield #1002 fully green;
- deterministic Russian routing, exact-action isolation and fail-closed execution ambiguity accepted;
- router remains internal/read-only and hard-codes `execution_authorized=false`.

Architecture: `docs/architecture/V9_NATURAL_LANGUAGE_CIO_ROUTER.md`.

### WP2 — Investment Policy Statement Engine: COMPLETE

- issue #186 / PR #187;
- merged to `main` as `75c9ae078309f32d1519b76cbedd89a221b62bf0`;
- exact-head Regression Shield #1014 fully green;
- quality/contracts/coverage and dependency/SAST/secret security = success;
- unresolved review threads = 0.

Accepted behavior:

- versioned owner IPS is separate from non-personalized `ConservativeRiskPolicyV1`;
- objective, horizon, explicit liquidity reserve, risk willingness/capacity and maximum drawdown are explicit;
- position/group/sector/currency concentration limits are deterministic;
- allowed/prohibited markets and instrument classes cannot conflict;
- material deny constraints require owner provenance/confirmation;
- system safe defaults cannot impersonate owner policy;
- bond permission requires both rating floor and named rating scale;
- annual review/effective/superseded states fail closed;
- deterministic SHA-256 policy reference binds future immutable plans;
- incomplete/invalid/unconfirmed policy blocks personal sizing;
- margin, short, withdrawal, transfer and autonomous real execution remain `Literal[False]`.

Architecture: `docs/architecture/V9_INVESTMENT_POLICY_STATEMENT.md`.

### WP3 — Market Universe Engine: COMPLETE

- issue #188 / PR #189;
- merged to `main` as `5ae81aa921999a6d4b1bb15aa0c506f7dea92a3f`;
- exact-head Regression Shield #1019 fully green;
- quality/contracts/coverage and dependency/SAST/secret security = success;
- unresolved review threads = 0.

Accepted behavior:

- broker universe uses T-Invest `Shares`, `Bonds`, `Etfs` with `INSTRUMENT_STATUS_BASE`;
- UID / position UID / FIGI / ISIN / ticker+class_code identity evidence is preserved;
- exact duplicate rows are removed and stable-alias conflicts fail closed;
- API/account/IIS/qualification/required-test/TCA eligibility is deterministic;
- account eligibility refresh does not retain `user_id` or full account ID;
- incomplete sources, invalid rows, identity conflicts and unknown eligibility never become `decision_ready`;
- content SHA-256 is source-order invariant and mutation-sensitive;
- only a complete validated BASE catalog is cached; account eligibility remains fresh;
- `FindInstrument` brute-force and broker mutation surfaces are forbidden by repository guard.

Architecture: `docs/architecture/V9_MARKET_UNIVERSE_ENGINE.md`.

### WP4 — Deterministic Candidate Funnel: COMPLETE

- issue #190 / PR #191;
- merged to `main` as `3946fc9af995338504dee8002c82c630ab8629b7`;
- exact-head Regression Shield #1035 fully green;
- quality/contracts/coverage and dependency/SAST/secret security = success;
- unresolved review threads = 0.

Accepted behavior:

- portfolio gap binds to exact portfolio/IPS/universe fingerprints;
- hard policy, evidence, affordability and concentration blockers run before scoring;
- incomplete comparable evidence for the policy+role-eligible universe forbids partial ranking;
- fixed ordinal scoring is contract-validated and cannot be replaced by subjective LLM scoring;
- `NO_ACTION/CASH` is always present and can rank first;
- minimum-lot feasibility and one-lot position/group/sector/currency headroom are checked before shortlist publication;
- T-Invest bond point pricing and per-lot accrued-interest arithmetic are handled without share-style errors;
- ranking, tie-breaks and funnel SHA-256 are deterministic and source-order invariant;
- rejected candidates keep machine-readable reasons;
- candidate runtime remains pure/read-only with `trading_methods=false`.

Architecture: `docs/architecture/V9_DETERMINISTIC_CANDIDATE_FUNNEL.md`.

### WP5 — Research & Evidence Engine: COMPLETE

- issue #193 / PR #194;
- merged to `main` as `f8f0bb95fc9692d68ce89c820a6ccbd1ff9868aa`;
- exact-head Regression Shield #1043 fully green on `ca376e364bf3cd94f792edc69fb091bca87025ef`;
- quality/contracts/coverage and dependency/SAST/secret security = success;
- unresolved review threads = 0.

Accepted behavior:

- bounded WP4 shortlist becomes source-backed WP5 dossiers bound to exact candidate/funnel identity;
- source hierarchy prioritizes broker/exchange/issuer/official disclosure/regulator/rating agency; media remains context-only;
- every material record carries source provenance, timestamps, deterministic freshness and a canonical record SHA-256;
- T-Invest structured research surfaces include asset fundamentals, report schedules, dividends and bond events;
- official-source retrieval is bounded by deterministic budgets, cache keys, TTLs and rate limits;
- external/prompt-injection-shaped text remains inert data and cannot alter control flow or execution authority;
- coverage gaps and contradictions are explicit; unresolved critical contradictions block strong recommendation;
- dossier SHA-256 is deterministic and source-order invariant;
- raw external content is not persisted in the dossier contract;
- research runtime adds no broker mutation, public execution route, OpenAPI Action or GPT Editor change.

Architecture: `docs/architecture/V9_RESEARCH_EVIDENCE_ENGINE.md`.

### WP6 — Credit, Rating & Default Engine 2.0: IN PROGRESS

Tracking: issue #195 / draft PR #196.  
Branch: `v9/wp6-credit-rating-default-engine`.  
Architecture: `docs/architecture/V9_CREDIT_RATING_DEFAULT_ENGINE.md`.

Current implementation builds a deterministic Credit Passport for bond candidates:

- exact binding to the WP5 dossier fingerprint and WP2 policy reference;
- issuer, issue, guarantor, guarantee terms and seniority remain separate identities;
- every material credit input references decision-grade WP5 evidence hashes;
- ACRA, Expert RA, NKR and NRA Russian national scales are explicit and agency-specific;
- incompatible rating scales are not averaged or silently crosswalked;
- policy minimum-credit-quality comparison is deterministic and fail-closed;
- issue rating is preferred; issuer proxy and eligible guarantor basis remain explicitly labeled;
- default, technical default, restructuring and payment-delay events are preserved and active events block readiness;
- conflicting latest rating observations fail closed;
- dossier/policy/rating/outlook/watch/default/terms changes create deterministic re-analysis triggers;
- Credit Passport SHA-256 is canonical and source-order invariant;
- repository guard now protects both inherited WP5 research boundaries and WP6 credit boundaries;
- credit runtime adds no broker SDK, mutation, public route, OpenAPI Action or GPT Editor change.

WP6 is not complete until exact-head Regression Shield is fully green, unresolved review threads are zero and PR #196 is squash-merged.

## Canonical production configuration

- UI: `Omni-CIO API | Управляющий и аналитик v8.6.1`;
- Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
- Gateway: `https://omni-cio-gateway.onrender.com`;
- Render plan: Free;
- entrypoint: `app:app`;
- production Knowledge: exactly 10 files from `gpt/CONFIGURATION.md`.

GitHub remains canonical for code/config reference but does not automatically synchronize GPT Editor, Render secrets or Upstash.

## Broker/execution safety remains unchanged

Production read-only uses only `TINVEST_TOKEN`.

Sandbox uses only `TINVEST_SANDBOX_TOKEN` and remains `real_money=false`.

Real v1 uses only dedicated `TINVEST_TRADING_TOKEN` and remains limited to the accepted narrow flow:

`fresh facts → immutable proposal → exact owner confirmation in a new user turn → one submit/idempotency → broker reconciliation`.

WP1–WP6 add no withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring execution or token management.

`REAL_TRADING_ENABLED=false` remains the master rollback state.

## v8.6.1 owner acceptance evidence

Phase 4 completed 2026-08-03 with one explicitly authorized controlled real SBER LIMIT BUY:

- exactly one submit;
- broker reconciled `EXECUTION_REPORT_STATUS_FILL`;
- 1/1 lot executed at 280.55 RUB;
- commission 0.84 RUB;
- portfolio and operations reconciled;
- idempotent replay verified with no second submit.

**Production release state: Omni-CIO v8.6.1 real BUY/SELL v1 — 100% complete.**
