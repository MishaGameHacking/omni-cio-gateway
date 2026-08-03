# Omni-CIO v9 — Portfolio Autopilot & Capital Management Program

Status: **OWNER-APPROVED / PROGRAM LOCKED**  
Approved: 2026-08-03  
Baseline protected: **Omni-CIO v8.6.1**  
Target: **Omni-CIO v9.x**

## 1. Program mandate

This document is the canonical development program for the second major Omni-CIO release.

The program objective is to evolve the existing single Custom GPT + single Gateway product into a substantially more capable portfolio-management system that:

- understands ordinary human language without requiring the user to know Action names or technical command syntax;
- autonomously gathers portfolio, liquidity, market, instrument, operations, credit, fund, issuer and public-evidence data;
- searches the full technically available investment universe through deterministic filtering and staged research;
- diagnoses portfolio gaps, concentration, liquidity, inflation exposure, permanent-loss risk and credit risk;
- builds diversified, evidence-backed portfolio plans;
- explains each proposed action in simple Russian;
- requires explicit owner approval before any real-money execution;
- continuously monitors the portfolio and external risk signals in read-only mode;
- preserves the complete reproducible configuration and recovery procedure in GitHub;
- scales from small portfolios to materially larger capital without replacing hard safety controls with unconstrained autonomous trading.

The primary investment objective remains:

> Preserve purchasing power, protect against permanent capital loss and inflation, and seek long-term real capital growth after costs and risk. No guaranteed return is permitted.

## 2. Program lock

Until this program reaches its Definition of Done:

1. This program is the default roadmap priority.
2. Agents and developers must not start a competing product roadmap, duplicate bot, separate frontend, second gateway or unrelated execution surface.
3. New work must either implement a listed v9 package, repair a blocking defect, maintain security/dependencies, or preserve production v8.6.1.
4. Any proposed scope outside this program must be explicitly approved by the owner and documented as a program amendment.
5. The stable v8.6.1 production contour must remain available throughout development.
6. No future capability described here may be represented as implemented until code, tests, CI and required production acceptance prove it.

## 3. Non-negotiable safety and product boundaries

### 3.1 Preserve the proven v8.6.1 execution lifecycle

The following invariants remain mandatory:

- production read-only, Sandbox and real execution are separate contours;
- real execution uses a dedicated account-scoped trading token without transfer access;
- immutable proposal before submit;
- explicit owner confirmation in a new user turn;
- one broker submit per proposal/idempotency key;
- ambiguous submit is never retried automatically;
- broker `submitted` is not `filled` without broker proof;
- own-funds BUY and own-position SELL only;
- no margin, uncovered short, withdrawal or transfer;
- durable journal failure or tamper fails closed;
- account identifiers and secrets remain redacted;
- `REAL_TRADING_ENABLED=false` remains the master rollback.

### 3.2 Autonomy boundary

Autonomy is allowed for:

- data collection;
- universe discovery;
- screening;
- research;
- portfolio diagnostics;
- strategy selection within the owner policy;
- candidate comparison;
- sizing calculations;
- plan creation;
- read-only monitoring;
- alerts and re-analysis.

Autonomy is not permission for unconfirmed real-money writes.

The preferred user experience is one understandable approval for an immutable, fully disclosed portfolio plan. Server-side execution must still re-check every order and halt on drift, stale data, cap violations or ambiguity.

## 4. Target user experience

The user should be able to write commands such as:

- `Проанализируй портфель`;
- `Управляй портфелем`;
- `Распредели свободные деньги`;
- `Проверь риски`;
- `Что изменилось?`;
- `Есть ли опасность дефолта?`;
- `Подготовь лучший план на текущий капитал`.

The system must translate natural language into the required internal workflow without asking the user to name Gateway Actions.

Default response layers:

1. concise decision in simple Russian;
2. verified facts and numbers;
3. risks and uncertainty;
4. proposed immutable plan;
5. expected portfolio before/after;
6. one clear approval or rejection request when real execution is intended.

## 5. Target architecture

```text
Custom GPT / Natural Language CIO Interface
        │
        ▼
Intent Router + Task Orchestrator
        │
        ├── Portfolio State & Policy
        ├── Market Universe Engine
        ├── Deterministic Screening Pipeline
        ├── Research & Evidence Engine
        ├── Credit & Default Engine
        ├── Fund X-Ray Engine
        ├── Portfolio Risk Engine
        ├── Strategy Selector
        ├── Candidate Ranking Engine
        ├── Portfolio Optimizer
        ├── Immutable Plan Compiler
        ├── Final Decision Review
        ├── Confirmed Plan Execution
        └── Watchtower / Monitoring / Audit
                │
                ▼
Omni-CIO Gateway → T-Invest + official/public evidence sources
                │
                └── Upstash Redis/QStash for durable state and schedules
```

Critical financial calculations, constraints, policy checks, candidate filtering and plan validation must be deterministic Gateway code. The language model is responsible for intent interpretation, research synthesis and understandable explanations, not for bypassing server rules.

## 6. Canonical work packages

### WP0 — Baseline freeze and recovery correctness

Deliverables:

- tag/document the v8.6.1 stable baseline;
- eliminate documentation drift in GPT recovery files;
- add CI consistency checks for canonical version, instructions, file manifest, Actions and setup index;
- preserve reproducible Render/GPT/Upstash configuration references without secrets;
- add a migration/rollback contract for every v9 release.

Exit gate:

- clean recovery rehearsal from GitHub documentation;
- no conflicting canonical files;
- v8.6.1 regression shield remains green.

### WP1 — Natural Language CIO Router

Deliverables:

- intent taxonomy: analysis, portfolio management, risk, research, cash allocation, plan review, execution, monitoring, exact-action diagnostics;
- deterministic routing rules and ambiguity handling;
- short human commands mapped to internal workflows;
- clarification only when a required owner policy or ambiguous real-money intent cannot be inferred safely;
- compact user-facing responses by default.

Exit gate:

- acceptance suite of natural Russian requests;
- no Action-name knowledge required from the user;
- exact-action isolation remains intact.

### WP2 — Investment Policy Statement (IPS) Engine

Deliverables:

- versioned owner policy containing objective, horizon, liquidity reserve, maximum drawdown tolerance, maximum position/group/sector/currency exposure, minimum credit quality, allowed markets and instrument classes, tax/account constraints and rebalancing bands;
- one-time guided setup and annual review;
- policy provenance and change history;
- safe defaults that do not invent risk tolerance;
- policy-aware sizing and blockers.

Exit gate:

- no confirmed personal sizing without sufficient policy inputs;
- every plan references the exact IPS version used.

### WP3 — Market Universe Engine

Deliverables:

- complete broker-available universe ingestion for supported shares, bonds, ETFs/funds and later explicitly approved classes;
- stable identity graph using UID/ISIN/FIGI/ticker/class code;
- API-trade availability, account eligibility, lot, currency and status filters;
- incremental refresh, caching and data quality metadata;
- no LLM-based brute-force enumeration.

Exit gate:

- reproducible universe snapshot;
- duplicate/conflicting identity detection;
- all candidates traceable to verified broker identifiers.

### WP4 — Deterministic Candidate Funnel

Deliverables:

- portfolio gap → role definition → universe filters → quantitative shortlist → deep research shortlist;
- hard blockers before scoring;
- `NO_ACTION/CASH` always included;
- comparable scorecards without false precision;
- evidence, freshness, liquidity, concentration, costs, permanent-loss and strategy fit.

Exit gate:

- no first-found-ticker behavior;
- deterministic reproduction from the same snapshot and policy;
- reasons recorded for accepted and rejected candidates.

### WP5 — Research & Evidence Engine

Deliverables:

- source hierarchy: broker/exchange/issuer/official disclosure/regulator/rating agency/reliable media context;
- citations, timestamps, freshness, contradictions and confidence;
- issuer fundamentals, reports, corporate actions, dividends, coupons, sanctions, litigation, auditor warnings and material events where relevant;
- bounded web research with rate limits, caching and source-quality controls;
- no unsupported claims or guaranteed forecasts.

Exit gate:

- every material decision claim has evidence provenance;
- unresolved critical contradiction blocks a strong recommendation.

### WP6 — Credit, Rating & Default Engine 2.0

Deliverables:

- distinguish issuer, issue, guarantor and seniority;
- ingest official Bank of Russia rating repositories/registers and official CRA publications where legally and technically available;
- store agency, scale, rating, outlook, action date, history and watch status;
- map rating scales without averaging incompatible ratings;
- analyze maturity schedule, coupons, offers, subordination, collateral, leverage, coverage, refinancing and default/restructuring events;
- produce a Credit Passport for each debt candidate;
- configurable minimum credit quality from IPS.

Exit gate:

- rating changes and default flags trigger re-analysis;
- debt recommendations fail closed on unresolved identity/rating conflicts.

### WP7 — Fund X-Ray Engine

Deliverables:

- fund identity, management company, mandate, benchmark, fees and liquidity;
- holdings/top holdings, asset-class, issuer, sector, currency, duration and credit-quality look-through when sources support it;
- overlap with direct holdings and other funds;
- hidden concentration and duplicated exposure detection;
- tracking and structure quality checks where data is available.

Exit gate:

- funds are not selected from name/category alone;
- portfolio diversification is measured look-through where feasible.

### WP8 — Portfolio Risk Engine 2.0

Deliverables:

- permanent-loss, market, concentration, liquidity, credit, currency, inflation/opportunity and data-quality risk vectors;
- Top-1/3/5, issuer/group/sector/class/currency limits;
- liquidity reserve and exit-capacity checks;
- scenario/stress tests and drawdown-aware policy checks;
- capital-scale-aware sizing from small portfolios to materially larger portfolios;
- risk after proposed trades, not only current risk.

Exit gate:

- every plan shows risk before/after;
- hard policy breaches cannot be averaged away by expected return.

### WP9 — Meta-Strategy Selector

Deliverables:

- select a portfolio regime from the owner IPS and current evidence rather than requiring the user to choose strategy labels;
- combine diversified core, liquidity, quality debt and bounded active ideas where justified;
- avoid regime chasing and unsupported return maximization;
- compare strategies after costs, taxes, liquidity and risk;
- record cancellation/review conditions.

Exit gate:

- selected strategy is explainable and reproducible;
- strategy cannot exceed owner risk policy.

### WP10 — Portfolio Optimizer & Capital Scaling

Deliverables:

- target weights and rebalancing bands;
- constraints for reserve, concentration, credit, liquidity, account eligibility, lot size, commission and taxes;
- small-capital rules that avoid meaningless micropositions;
- large-capital rules for market depth, spread, participation, staged execution and partial fills;
- scenario comparison against current portfolio and NO_ACTION;
- deterministic decimal arithmetic.

Exit gate:

- same policy scales from tens of thousands to millions without merely increasing one hard cap;
- plan remains executable in lots and cash after fees.

### WP11 — Immutable Portfolio Plan Protocol

Deliverables:

- versioned immutable `PORTFOLIO_PLAN` object;
- exact portfolio/evidence/market/policy snapshots used;
- ordered BUY/SELL/NO_ACTION legs;
- expected cost, fees, cash after, target weights and risk before/after;
- validity window, drift tolerances and cancellation conditions;
- final read-only review before preparation;
- one simple owner approval phrase for the disclosed plan.

Exit gate:

- any plan mutation invalidates prior approval;
- plan replay cannot create duplicate orders.

### WP12 — Safe Plan Execution Engine

Deliverables:

- preserve current single-order v8.6.1 protocol as fallback;
- execute only an owner-approved immutable plan;
- per-leg fresh market, spread, liquidity, price-step, own-funds/own-position and risk re-check;
- halt remaining legs on drift or ambiguity;
- staged LIMIT execution for large orders;
- partial-fill state machine and deterministic reconciliation;
- no autonomous recurring real-money execution;
- no transfer/withdraw/margin/short unless a future separately approved threat model and release exists.

Exit gate:

- fake-client/regression proof for replay, ambiguity, partial fill, halt, rollback and reconciliation;
- minimal-real-cap owner acceptance before any cap increase.

### WP13 — Portfolio Watchtower

Deliverables:

- scheduled read-only portfolio and risk checks;
- rating, default, corporate-event, liquidity, concentration and policy-drift alerts;
- event deduplication and severity levels;
- no notification when nothing material changed;
- QStash/Upstash schedules with authenticated endpoints, retry limits, deduplication, callbacks and redacted secrets;
- monitoring can create a recommendation or proposed plan, never an unconfirmed real trade.

Exit gate:

- schedule state is observable and recoverable;
- duplicate deliveries do not duplicate alerts or plans;
- write operations remain owner-confirmed.

### WP14 — Decision Journal, Evaluation & Learning Loop

Deliverables:

- decision/evidence/policy/plan/execution/outcome journal;
- compare expected and realized outcomes without hindsight rewriting;
- benchmark against NO_ACTION and policy objective;
- quality metrics for data completeness, research coverage, concentration reduction and execution quality;
- offline replay/evaluation datasets with sanitized synthetic or fake-broker data;
- no self-modifying production rules without reviewed code changes.

Exit gate:

- every production decision is auditable;
- model/prompt changes require regression evaluation.

### WP15 — Custom GPT v9 Configuration & Recovery

Deliverables:

- compact GPT Instructions within editor limits;
- canonical Knowledge manifest;
- human-language conversation starters;
- production Actions catalog and OpenAPI;
- recovery procedure from name through tokens/secrets boundaries;
- version consistency CI check;
- owner Preview acceptance.

Exit gate:

- the current bot is upgraded, not duplicated;
- complete restoration from GitHub documentation is demonstrated.

## 7. Delivery sequence

The canonical dependency order is:

```text
WP0
 └─ WP1 + WP2
      └─ WP3
           └─ WP4
                ├─ WP5
                ├─ WP6
                └─ WP7
                     └─ WP8 + WP9
                          └─ WP10
                               └─ WP11
                                    └─ WP12
                     └─ WP13
                          └─ WP14
                               └─ WP15
```

Parallel work is allowed only when dependencies and a single source of truth remain clear. Each PR should implement one reviewable logical slice.

## 8. Development and release method

For each work package:

1. architecture contract;
2. threat/data-quality model;
3. deterministic domain implementation;
4. fake-client and unit tests;
5. integration tests without live broker access;
6. security and secret checks;
7. documentation/source-of-truth update;
8. exact-head Regression Shield;
9. squash merge;
10. deployment behind feature flag;
11. shadow-mode acceptance;
12. Sandbox acceptance where applicable;
13. minimal real-money acceptance only when explicitly authorized.

No promise of “first attempt without tests” is acceptable for financial software. The correct objective is to design for fewer defects through contracts, typed models, deterministic logic, test fixtures, staged deployment and fail-closed behavior.

## 9. Research and implementation principles

- Prefer official APIs and structured sources before general web search.
- Use the model for synthesis and ambiguity resolution, not as the sole source of numeric financial truth.
- Cache and timestamp external evidence.
- Bound concurrency, retries, rate limits and research budgets.
- Use idempotency and deduplication for every background job and plan.
- Use decimal arithmetic for money.
- Separate observed facts, calculations, assumptions and recommendations.
- Never optimize only expected return; optimize within owner policy and hard permanent-loss constraints.
- Do not equate more assets with better diversification.
- Do not equate ratings with certainty or fund labels with actual holdings.
- Do not weaken safety to make the interface simpler.

## 10. Program-level Definition of Done

Omni-CIO v9 is complete only when all of the following are true:

- [ ] v8.6.1 remains recoverable and regression-safe;
- [ ] user can operate the system through ordinary Russian language;
- [ ] IPS is versioned and applied to every recommendation/plan;
- [ ] full supported broker universe can be ingested and identified;
- [ ] deterministic candidate funnel and NO_ACTION comparison are implemented;
- [ ] research evidence has source/date/freshness/conflict provenance;
- [ ] credit/rating/default engine is production-ready;
- [ ] fund look-through and overlap analysis are production-ready;
- [ ] portfolio risk and optimizer support small and materially larger capital;
- [ ] immutable multi-leg portfolio plans are implemented;
- [ ] owner-approved plan execution is idempotent, fail-closed and reconciled;
- [ ] Watchtower performs scheduled read-only monitoring and material alerts;
- [ ] decision journal and offline evaluation are implemented;
- [ ] Custom GPT v9 config and recovery are canonical in GitHub;
- [ ] CI/security/regression evidence is green on exact release head;
- [ ] owner Preview/Sandbox/minimal-real acceptance is complete where required;
- [ ] no unresolved critical security, secret, broker-write or data-integrity defect remains.

## 11. Scope-change rule

A change to this program requires:

1. explicit owner approval;
2. documented rationale;
3. impact on safety, architecture, schedule and Definition of Done;
4. update to this file through a reviewed PR.

Until then, this file is the binding program roadmap for Omni-CIO v9.

## 12. External technical references used for program design

- T-Invest structured instrument/order/portfolio APIs are the primary broker-data and execution surface.
- Bank of Russia official registers and rating repositories are the primary Russian CRA/reference layer.
- Upstash Redis remains the durable state backend; QStash schedules/workflows are the planned zero-cost/low-cost background orchestration option.
- Public web research supplements official structured sources and must preserve citations, freshness and conflicts.
