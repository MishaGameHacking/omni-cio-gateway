# Omni-CIO v9 — Natural Language CIO Router v1

Status: **WP1 implementation contract**.  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.  
Protected production baseline: Omni-CIO v8.6.1.

## 1. Goal

A normal user should be able to write short Russian requests such as:

- `Проанализируй портфель`;
- `Управляй портфелем`;
- `Куда вложить свободные деньги?`;
- `Проверь риски`;
- `Найди лучшие облигации`;
- `Следи за новостями`;
- `Купи SBER`.

The user should not need to know operationIds. The router converts language into a deterministic workflow descriptor; downstream work packages execute the actual analysis/research/plan logic.

## 2. Boundary

WP1 does **not** change the live GPT Editor, OpenAPI or broker runtime.

It adds a deterministic library:

`omni_cio/orchestration/intent_router_v1.py`

The module is intentionally pure and side-effect free:

`text → normalized text → intent/signals → workflow descriptor`.

No external service, LLM, broker call or secret is used by the router itself.

## 3. Intent taxonomy

Version `intent-route.v1` recognizes:

- `exact_action` — owner/developer diagnostics that explicitly say `вызови только ...`;
- `portfolio_analysis` — explain current portfolio state;
- `portfolio_management` — full CIO analysis and plan-building goal;
- `risk_review` — portfolio/default/concentration/risk review;
- `research` — broad market/company/bond/fund/news/rating research;
- `cash_allocation` — allocate new/free capital;
- `plan_review` — explain/review an existing plan;
- `execution_request` — natural-language request to buy/sell/execute;
- `monitoring` — recurring/read-only watch request;
- `asset_analysis` — analyze one instrument/company/fund;
- `unknown` — insufficient intent evidence.

## 4. Exact-action invariant

Exact-action diagnostics have absolute routing priority.

If the user writes `Вызови только getPortfolioSnapshot`, the descriptor contains exactly one Action step and never appends portfolio-management/research steps.

If more than one Action is requested after `только`, or the named Action is not in the currently supplied deployed Action set, the router returns clarification and **zero** Action steps.

Consequential exact Actions remain consequential. Classification never bypasses their existing server confirmation/auth/preflight requirements.

## 5. Natural-language workflow descriptors

Workflow steps have one of three kinds:

- `action` — existing operationId that can be called now;
- `internal` — deterministic v9 engine step, optionally tied to a future work package;
- `owner_gate` — explicit human approval boundary.

WP1 never invents a future operationId. Future capability references are internal steps such as `portfolio_optimizer` with `required_work_package=WP10`.

Non-exact WP1 workflows reference only v8.6.1 baseline **read-only** Actions. No non-exact route includes `prepareRealTrade` or `executeRealTrade`.

## 6. Real-money safety

A phrase such as `Купи SBER` is interpreted as an execution **goal**, not permission to call a broker mutation immediately.

The route is:

`resolve/build safe plan → refresh preflight → owner gate → execute confirmed plan only → broker reconciliation`.

Those later steps are internal/dependency-marked until WP11/WP12 exist.

If a write phrase appears inside a broader request such as:

`Управляй портфелем и если нужно купи активы`,

the router keeps the broader portfolio-management/cash-allocation workflow and marks the route as containing write intent. Analysis and plan construction happen first; the owner gate remains mandatory.

This preserves the proven v8.6.1 rule: broad language is not a real-order confirmation.

## 7. Ambiguity policy

The router is designed for minimum user interruption.

Clarification is required only when:

- the request is empty;
- no intent can be resolved with any deterministic signal;
- an exact-action diagnostic names no valid Action;
- an exact-action request names multiple Actions while saying `только`.

Mixed read-only goals do not automatically trigger clarification. The deterministic priority favors the broader safe workflow.

## 8. Russian normalization

Normalization includes:

- Unicode case-folding;
- `ё → е`;
- punctuation/whitespace normalization;
- a narrow allowlist of common project-specific typos such as `партфель` and `деверсификация`.

The router deliberately avoids a generic fuzzy matcher that could turn an unrelated phrase into a write intent.

## 9. Capability awareness

`route_user_intent(..., available_actions=...)` accepts the actual deployed Action set for exact-action diagnostics.

This prevents a disabled conditional Action such as `getRealTradingStatus` from being represented as callable when only baseline read-only Actions are available.

Future WP integration should supply the Action surface from Gateway readiness/OpenAPI rather than assume optional contours are enabled.

## 10. Threat model

| Threat | WP1 control |
|---|---|
| Natural phrase accidentally becomes broker submit | non-exact routes contain no broker-write operationId |
| `вызови только X` silently expands into other Actions | exact-action absolute priority + one-step invariant |
| Disabled conditional Action is treated as available | caller-supplied `available_actions` validation |
| Typo causes dangerous interpretation | narrow typo map; no generic fuzzy write matching |
| Ambiguous phrase produces fabricated workflow | unknown → clarification, zero steps |
| Future capability appears to be live Action | future engines are `internal` with explicit WP dependency |
| User says `купи/продай` before research | plan/preflight/owner-gate workflow, no submit Action |
| Model changes wording over time | deterministic router acceptance corpus in pytest |

## 11. Acceptance suite

`tests/test_intent_router_v1.py` covers:

- canonical and typo-tolerant Russian portfolio commands;
- analysis/management/risk/research/cash/plan/monitoring/asset/execution intents;
- exact-action isolation;
- disabled/unknown/multiple exact Actions;
- embedded buy intent inside portfolio management;
- no write operationId in natural-language workflows;
- required future WP dependencies;
- one-time news research vs recurring monitoring;
- empty/unknown clarification paths.

## 12. Migration / activation

WP1 is merged as dormant deterministic infrastructure.

It must not alter v8.6.1 behavior merely by existing in the repository. Later orchestration/API/GPT integration must be separately reviewed and gated by the relevant v9 work package.

Rollback is code-only: reverting the WP1 module/tests/docs leaves the production v8.6.1 Action surface unchanged.

## 13. Exit condition

WP1 is complete when:

- natural Russian acceptance tests pass;
- exact-action isolation passes;
- natural execution wording cannot produce a live write Action;
- current production behavior/OpenAPI remains unchanged;
- exact-head Regression Shield/security is green;
- the package is squash-merged and #176 marks WP1 complete.
