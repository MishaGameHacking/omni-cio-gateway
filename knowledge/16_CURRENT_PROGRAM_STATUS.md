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

### WP6 — Credit, Rating & Default Engine 2.0: COMPLETE

- issue #195 / PR #196;
- merged to `main` as `643160085520f1a2a333385aa7431d1b595b2eef`;
- exact-head Regression Shield #1057 fully green on `3375faf6ceef3e48f0be565c37738280280a3b8b`;
- quality/contracts/coverage and dependency/SAST/secret security = success;
- unresolved review threads = 0.

Accepted behavior:

- Credit Passport binds exact WP5 dossier evidence and the WP2 policy reference;
- issue, issuer, guarantor, guarantee terms and seniority remain distinct identities;
- ACRA, Expert RA, NKR and NRA Russian national scales are explicit and agency/scale compatibility is contract-enforced;
- incompatible rating scales are not averaged or silently crosswalked;
- issue rating is preferred, while issuer proxy and eligible-guarantor basis remain explicitly labeled;
- minimum-credit-quality assessment is deterministic and fail-closed;
- maturity, offer, coupon, amortization, collateral and guarantee terms are structured;
- optional leverage, coverage, liquidity and 12-month refinancing metrics remain provenance-bound and are never fabricated when missing;
- default, technical default, restructuring and payment-delay events are preserved; active events fail closed;
- conflicting latest rating observations fail closed and current state is based on latest effective time;
- dossier/policy/rating/outlook/watch/default/terms/financial changes create deterministic re-analysis triggers;
- Credit Passport SHA-256 is canonical and source-order invariant;
- research and credit runtime boundaries are repository-guarded;
- `trading_methods=false`; no broker mutation, public route, OpenAPI Action or GPT Editor change.

Architecture: `docs/architecture/V9_CREDIT_RATING_DEFAULT_ENGINE.md`.

### WP7 — Fund X-Ray Engine: COMPLETE

- issue #197 / PR #198;
- merged to `main` as `15505272872681cb7c3ad1e845affaa79f6ebdc1`;
- exact-head Regression Shield #1064 fully green on `c5086a7f86840a320cecd8b10c3c4878091b5e88`;
- blocking dependency hardening #202 was carried and closed by WP8 PR #201;
- unresolved review threads = 0.

Accepted behavior:

- exact binding to WP5 research target and full WP3 `InstrumentIdentity`/universe fingerprint;
- fund wrapper identity remains separate from underlying holdings;
- composition modes distinguish full holdings, partial holdings, documented buckets and unavailable composition;
- partial holdings are never rescaled to 100%; undisclosed residual remains `UNKNOWN`;
- asset-class/sector/currency/issuer/geography exposures are derived without inventing classifications;
- schema v1.1 adds credit-quality look-through with `UNKNOWN` preservation plus weighted duration with explicit measured coverage; partial duration/credit evidence is never extrapolated to the whole fund;
- credit-quality labels remain evidence only and are not silently crosswalked into WP2 credit-floor compliance;
- top-1/top-5 and HHI expose hidden concentration for holdings-based composition;
- direct-holding overlap and fund-to-fund overlap are deterministic;
- fund manager/benchmark/strategy/AUM/turnover/tracking-error/expense metadata is optional and provenance-bound;
- stale/missing composition fails closed while preserving evidence;
- source hashes must exist as decision-grade records in the exact WP5 dossier;
- impossible weights/coverage states and stale/mismatched liquidity are rejected;
- Fund X-Ray SHA-256 is canonical and source-order invariant;
- acceptance/integrity/duration-credit suites are repository-guarded;
- fund runtime is pure/internal and repository guard forbids broker SDK/tokens/mutation services.

Architecture: `docs/architecture/V9_FUND_XRAY_ENGINE.md`.

### WP8 — Portfolio Risk Engine 2.0: COMPLETE

- issue #199 / PR #201;
- dependency hardening issue #202 closed with the same PR;
- squash-merged to `main` as `24e027f1e576451571d18af88f758a69828f6aed`;
- exact-head Regression Shield #1078 fully green on `039a28f1c7a6dafcf424777fe976ac1dd89cecff`;
- unresolved review threads = 0.

Accepted behavior:

- exact WP2 IPS fingerprint binding plus exact portfolio snapshot fingerprint reference;
- eight independent vectors: permanent-loss, market, concentration, liquidity, credit, currency, inflation/opportunity and data quality;
- no composite risk score that can average away a hard breach;
- explicit FX-to-base provenance, exact native→base reconciliation and FX freshness for every cross-currency position; no implicit FX conversion;
- Top-1/Top-3/Top-5 plus position/issuer/group/sector/asset-class/currency concentration;
- ETF positions require WP7 Fund X-Ray look-through and caller-supplied `POSITION` exposure is forbidden to prevent wrapper/underlying double counting;
- exact-X-Ray-bound Fund Credit Summary records credit-applicable, assessed, unknown, floor-breach and active-default weights; ETF wrappers cannot silently appear credit-safe;
- direct bond positions require WP6 credit evidence; active default and IPS credit-floor failures are hard breaches;
- owner IPS liquidity reserve is hard; stale/missing liquidity is explicit; exit-days scale with actual position size and daily exit capacity;
- deterministic stress scenarios enforce owner max-drawdown;
- hypothetical proposed trades rebuild a full after-state and record new/resolved blockers;
- proposal effects and assessment SHA are canonical and invariant to equivalent input order;
- changed policy payload with the same id/version fails exact fingerprint binding;
- system guardrails cannot impersonate owner-confirmed hard policy;
- missing Fund Credit, unknown fund-credit weight, stale FX and other incomplete evidence remain explicit readiness blockers;
- acceptance/hardening suites and repository guard protect these invariants;
- `omni_cio/risk` is pure/read-only and repository-guarded against broker SDK/tokens/mutation methods.

Architecture: `docs/architecture/V9_PORTFOLIO_RISK_ENGINE.md`.

### WP9 — Meta-Strategy Selector: IN PROGRESS

Tracking: issue #203 / draft PR #204.  
Branch: `v9/wp9-meta-strategy-selector`.  
Architecture: `docs/architecture/V9_META_STRATEGY_SELECTOR.md`.

Current implementation builds a deterministic policy-bound regime selection:

- exact portfolio snapshot + recomputed WP2 IPS fingerprint/reference + exact current WP8 assessment binding;
- hypothetical WP8 trade assessments cannot impersonate the current portfolio state;
- exactly five bounded regimes are compared: `NO_ACTION`, `CAPITAL_PRESERVATION`, `DEFENSIVE_BALANCED`, `BALANCED_CORE`, `GROWTH_CORE`;
- owner risk willingness/capacity, horizon and WP8 current risk cap the feasible regime set before ranking;
- hard policy/risk breaches cannot be averaged away by objective fit, liquidity fit or lower friction;
- current hard breach makes `NO_ACTION` infeasible while still permitting a sufficiently defensive remediation regime when evidence is decision-ready;
- liquidity reserve, quality debt, diversified core and bounded active ideas are explicit directives;
- bounded active ideas are never required and are allowed only for high willingness + high capacity + compliant current risk in `GROWTH_CORE`;
- structurally feasible actionable regimes require fresh explicit transition-cost + tax evidence;
- friction amount, timestamp and source SHA-256 provenance are bound into the immutable selection fingerprint;
- unsupported expected-return, alpha and macro-regime forecast inputs are absent;
- deterministic tie-breaks prefer safety, objective/liquidity fit, lower explicit friction and then stable identifiers;
- policy/portfolio/risk/friction/tax changes carry explicit review or cancellation conditions;
- selection SHA-256 is canonical and source-order invariant while source mutation changes the fingerprint;
- `omni_cio/strategy` is pure/internal/read-only and protected by both dedicated and canonical repository guards;
- mypy scope includes the strategy package;
- applied GPT remains v8.6.1 and no public route/OpenAPI/GPT Editor change is part of WP9.

WP9 is not complete until Ruff/mypy/full exact-head Regression Shield are green, unresolved review threads are zero and PR #204 is squash-merged. Only the final exact-head CI run after all code/documentation fixes counts as merge evidence.

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

WP1–WP9 add no withdrawal/transfer, margin/short, MARKET/BESTPRICE, autonomous recurring execution or token management.

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