# V10 WP11 — V9 Core Extraction Contract

Status: **WP11 IMPLEMENTATION CONTRACT / PR EVIDENCE REQUIRED**  
Program authority: `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`  
Protected runtime baseline: Omni-CIO v9.0.0 / `app:app`  
Money locks: `trading_methods=false`, `REAL_TRADING_ENABLED=false`

## 1. Scope

WP11 separates the accepted V9 deterministic financial engines from the mandatory Custom GPT / FastAPI presentation boundary without changing their reviewed financial semantics. The implementation follows the program preference `REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Inspection of accepted `main` shows that the V9 domain engines are already source-separated under `omni_cio/`; moving or rewriting them would add migration risk without improving the WP11 boundary. WP11 therefore **reuses the reviewed engines as-is and adds one narrow Core orchestration adapter** at `omni_cio/core/service_v1.py`.

WP11 does not introduce the future V10 WP12 canonical domain model, PostgreSQL persistence, Web/Telegram/Cortex product surfaces, broker-write authority, or a replacement application entrypoint.

## 2. Accepted V9 WP1–WP14 inventory

The following is the exact source-level inventory used for WP11. `app.py`, `app_v360.py`, `app_v371.py`, `main.py` and `gpt/` remain presentation/integration surfaces and are not moved into Core.

| V9 WP | Capability | Accepted deterministic source | WP11 treatment | Presentation dependency |
|---|---|---|---|---|
| WP1 | Natural-language CIO routing | `omni_cio/router/` + `omni_cio/contracts/v1/intent_router.py` | REUSE_AS_IS; not part of financial planning facade | language/presentation input exists upstream; financial engines do not depend on it |
| WP2 | Investment Policy Statement | `omni_cio/policy/` + `omni_cio/contracts/v1/investment_policy.py` | WRAP_ADAPTER through Core facade | none |
| WP3 | Market Universe | `omni_cio/universe/` + `omni_cio/contracts/v1/universe.py` | REUSE_AS_IS; later callers may supply verified candidates/assets | none |
| WP4 | Candidate Funnel | `omni_cio/candidates/` + `omni_cio/contracts/v1/candidate_funnel.py` | REUSE_AS_IS | none |
| WP5 | Research/Evidence | `omni_cio/research/` + `omni_cio/contracts/v1/research_evidence.py` | REUSE_AS_IS | external research orchestration is upstream; deterministic contracts remain independent |
| WP6 | Credit/Rating/Default | `omni_cio/credit/` + `omni_cio/contracts/v1/credit.py` | REUSE_AS_IS | none |
| WP7 | Fund X-Ray | `omni_cio/funds/` + `omni_cio/contracts/v1/fund_xray.py` | REUSE_AS_IS | none |
| WP8 | Portfolio Risk | `omni_cio/risk/engine_v1.py` + `omni_cio/contracts/v1/portfolio_risk.py` | WRAP_ADAPTER through Core facade | none |
| WP9 | Meta-Strategy Selector | `omni_cio/strategy/selector_v1.py` + `omni_cio/contracts/v1/meta_strategy.py` | WRAP_ADAPTER through Core facade | none |
| WP10 | Portfolio Optimizer | `omni_cio/optimizer/engine_v1.py` + `omni_cio/contracts/v1/portfolio_optimizer.py` | WRAP_ADAPTER through Core facade | none |
| WP11 | Immutable Portfolio Plan | `omni_cio/plans/protocol_v1.py` + `omni_cio/contracts/v1/portfolio_plan.py` | WRAP_ADAPTER through Core facade | none |
| WP12 | Safe Plan Execution | `omni_cio/plan_execution/` + `omni_cio/contracts/v1/plan_execution.py` | protected; intentionally outside WP11 Core planning facade | execution authority boundary; must remain isolated |
| WP13 | Watchtower | `omni_cio/watchtower/engine_v1.py` + `omni_cio/contracts/v1/watchtower.py`; route/runtime/journal adapters remain under `omni_cio/watchtower/` | REUSE_AS_IS; later Block H owns V10 durable monitoring | `omni_cio/watchtower/routes_v1.py` is an adapter layer; deterministic Watchtower engine remains separate |
| WP14 | Decision Journal / evaluation | `omni_cio/decision_journal/journal_v1.py`, `recorder_v1.py`, `evaluation_v1.py`, `replay_v1.py` + `omni_cio/contracts/v1/decision_journal.py` | REUSE_AS_IS; later Core/data WPs own persistence migration | persistence adapters are separate from deterministic journal/evaluation logic |

Historical WP11 note: at WP11 acceptance, the remaining top-level portfolio/accounting modules were still protected migration inputs. Amendment 20 now owns their later convergence. V9C-B relocates those accepted implementations to `omni_cio/portfolio/`, `omni_cio/analytics/`, `omni_cio/pretrade/`, `omni_cio/adapters/` and `omni_cio/reconciliation/` without changing financial semantics; this does not retroactively change what WP11 accepted.

## 3. Stable WP11 Core interface

`CorePlanRequestV1` deliberately composes existing accepted V9 versioned DTOs:

- `InvestmentPolicyStatementV1`;
- `PortfolioRiskInputV1`;
- `OptimizerAssetV1`;
- `StrategyFrictionEvidenceV1`;
- explicit `evaluated_at`;
- optional existing risk/strategy/optimizer/plan settings, stress scenarios and macro assumptions.

`run_core_plan_pipeline()` executes only deterministic reviewed functions:

`policy assessment -> portfolio risk -> meta-strategy -> optimizer -> immutable plan`

The returned `CorePlanResultV1` exposes the exact policy assessment, risk, strategy, optimizer and plan objects. No new financial formula is introduced by the adapter.

The explicit evaluation timestamp is part of the service request so golden parity and future callers can reproduce a decision from the same versioned inputs rather than inheriting time from a UI or chat session.

## 4. Compatibility and authority rules

The following remain mandatory:

- `app:app` is unchanged and remains the V9 production/recovery entrypoint;
- the Custom GPT remains the current V9 user interface until its later parity/decommission gate;
- Core imports neither `app*` nor `gpt` nor OpenAI;
- Core does not import `omni_cio.real_trading` or `omni_cio.plan_execution`;
- plan construction is read-only and grants no submit authority;
- `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged;
- no broker/Telegram/encryption secret or private portfolio payload is added to GitHub, CI logs, or artifacts;
- V10 WP12 remains locked until WP11 is accepted.

## 5. Golden parity oracle

`tests/v9_plan_fixture.py` is the existing deterministic V9 planning fixture. WP11 must run the new Core facade from the fixture's same policy, portfolio, friction evidence, asset universe and timestamp, then compare exact typed objects for:

1. policy assessment;
2. current portfolio risk;
3. meta-strategy selection;
4. optimizer result;
5. immutable portfolio plan.

Any unequal typed result is a WP11 blocker unless a separate versioned semantic-change contract is explicitly approved. Re-running the same Core request must produce the same result.

## 6. No-GPT integration proof

The WP11 test suite statically checks the direct deterministic path:

- `omni_cio/core/service_v1.py`;
- `omni_cio/policy/ips_v1.py`;
- `omni_cio/risk/engine_v1.py`;
- `omni_cio/strategy/selector_v1.py`;
- `omni_cio/optimizer/engine_v1.py`;
- `omni_cio/plans/protocol_v1.py`.

Imports from `app*`, `gpt`, OpenAI, `omni_cio.real_trading`, or `omni_cio.plan_execution` are forbidden on this path. The integration test then executes the full deterministic planning chain without a GPT/OpenAI client.

## 7. Exit Gate

WP11 is not COMPLETE merely because the facade exists. Acceptance requires all of the following on the exact reviewed PR head:

- WP1–WP14 inventory is reviewed and no presentation dependency is hidden inside the extracted planning path;
- golden V9 parity test passes exactly;
- no-GPT Core integration test passes;
- `omni_cio/core` is included in static type checking;
- authoritative Self-Hosted Windows CI / Regression Shield is GREEN for the exact head;
- dependency audit, SAST and tracked-content secret scan are GREEN where scheduled by the authoritative gate;
- zero unresolved blocking review threads;
- full PR diff reviewed;
- protected V9 `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and rollback remain intact;
- post-merge Regression Shield succeeds on the exact resulting `main` SHA before program status is advanced.

Only after that acceptance may V10 WP12 begin.
