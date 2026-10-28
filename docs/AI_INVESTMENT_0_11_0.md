# Investment AI integration — 0.11.0 candidate

Updated: 2026-10-18. Working PR: #880 (`codex/spectrum-3d-100`).
This is an implementation/status specification, not a release, investment-return
promise, measured prediction-accuracy report, or approval to place orders.

## Implemented in this increment

- `investment_chat_policy.py`: bounded, deterministic investment-only admission,
  clarification for unknown topics, contextual short follow-ups using owned user
  history, and automatic fast/standard/premium task depth. Definitions can use
  fast; comparative portfolio work uses standard; solvency/default review uses
  premium. Manual underpowered depth is rejected, not silently upgraded.
- `ai_route_catalog.py`: optional evaluated-route catalog supporting eight or
  more candidates (maximum 32). Exact model binding, allowed tasks, context and
  output capacity, structured-JSON attestation and expiring evaluation references.
  Nested/non-string tier values fail with a controlled admission error.
- `ai_guarded_client.py`: lowest estimated TOTAL input-plus-output cost among
  eligible configured routes; strict rejection of non-finite/duplicate JSON;
  pre-reservation route/cost guard. Existing regional approval, price binding,
  budget ledger, uncertain-charge reconciliation and no-paid-retry rules remain.
- `volume_chat.py`: admission before paid work, auto quotes and cost ceilings,
  explicit confirmation for premium selected from auto, immutable queued route
  metadata, worker-side revalidation and history limited before the actual queued
  question. Later messages cannot leak into earlier jobs; repeated questions are
  not removed by text equality. Legacy explicit-tier requests keep receipt hashes.
- Native chat: Auto is the default; server-selected depth and price are visible;
  premium auto-routing requires a second click; changed inputs invalidate quotes;
  route/cost ceilings accompany sending. Existing durable request recovery remains.
- `portfolio_scenarios.py`: Decimal-based joint-scenario arithmetic for expected
  net/real return, loss probability, weighted VaR and exact fractional-tail ES.
  Timestamp, horizon, probability, completeness and numeric validation fail closed.

The lexical scope policy is a conservative baseline, NOT a trained semantic
classifier or a guarantee that every paraphrase/mixed request is correctly
classified. The model is separately instructed to refuse unrelated work. Existing
citation validation checks allowed references, not whether prose truly follows
from them (`claim_meaning_verified` remains false).

## Hierarchical target architecture

One existing job/lease/budget system owns execution. Do not create a second
competing autonomous loop. Proposed dependency order:

`read-only market/portfolio sources -> point-in-time fact validation -> numerical
risk engine -> deterministic portfolio policy -> qualified LLM interpretation ->
validated recommendation -> user decision`

Data-quality gates and risk limits outrank language-model opinions. A model cannot
relax an issuer/sector/liquidity limit, manufacture a probability, turn missing data
into zero risk, replace a broker observation, authorize a strategy, or submit an
order. Context selection must disclose omitted positions and stale/missing facts.

Scheduling design: run common issuer/market analysis once per material snapshot,
reuse its non-personal result across affected portfolios, and apply user-specific
constraints separately. Start/end-of-session jobs use exchange calendars; urgent
confirmed credit events bypass ordinary cooldown but not data, budget or access
checks. Deduplicate events, keep bounded queue ownership, cap retries before
uncertain dispatch, and record skip/wait reasons. This increment reuses existing
workers; it does not claim to implement all scheduling and caching extensions.

Decision states to add to the recommendation policy: observe, wait, reduce,
exit-review, reinvest-preview, and insufficient-data. A missing report is not an
exit signal by itself; a positive expected return is not sufficient when tail loss,
concentration, liquidity, taxation or a user's risk budget make the trade unsuitable.
Reinvesting may first replenish a cash reserve rather than force another purchase.

## Numerical contract and further portfolio work

All scenario returns, costs and inflation use the SAME explicit horizon and are
fractions, not percentages. For scenario s, weights w, costs c and inflation pi:

`net_s = sum(w_i * return_s_i) - c`

`expected_net = sum(probability_s * net_s)`

`expected_real = sum(probability_s * ((1 + net_s) / (1 + pi) - 1))`

ES averages exactly the worst `1-confidence` probability mass, including fractional
boundary mass. Joint rows preserve supplied co-movement; independent resampling of
asset marginals is not used. Near-unit probabilities/weights are normalized only
within a disclosed 1e-18 tolerance. Negative VaR/ES is retained for an all-gain tail.

The module consumes SUPPLIED scenarios. It is not yet connected to a calibrated
live forecast, default-probability estimator, allocation optimizer or automatic
security replacement service. Model-generated probability numbers are not approved
inputs. The current backend does not obtain predictive reliability just by adding
more LLMs or increasing response length.

Next credit model: point-in-time cash/debt maturity schedule, interest coverage,
operating/free cash flow, covenants, refinancing dependence, ratings/outlook and
confirmed payment events. Missingness remains explicit. Train/calibrate a survival
or classification baseline on documented default labels; compare out-of-time,
sector-specific performance and uncertainty. A heuristic warning is not calibrated
probability of default. Separate issuer default risk from market/FX/liquidity risk.

Next allocation policy: rolling short-horizon constrained optimization of expected
net return minus tail-risk and turnover penalties, with per-issuer/sector/currency
caps, tradability, minimum lots, liquidity, cash reserve and actual user loss budget.
New capital should fill constrained underweights gradually; an improvement must
exceed costs and uncertainty before proposing turnover. Parameters need user risk
preferences and validation, not arbitrary universally 'optimal' fixed thresholds.

## Model choice and economics

Do not hardcode panel display names as API identifiers, automatically choose the
newest/largest model, or run eight models for every question. First qualify routes
on held-out Russian financial extraction, numerical/source fidelity, scope attacks,
latency, actual token cost and structured-JSON behavior. Compare the economic
cost per accepted answer, including rejected answers and retries. Expensive review
is useful for selected complex cases, not as an eight-model majority vote.

GPT-oss-120b is a candidate for economical text workloads, not a proven winner on
this application's financial dataset. Other available providers are challengers
under the same task rubric. Scanned-report extraction requires separately verified
vision/table handling; text-only models cannot directly read report images.

The screenshot-only illustration (2,000 input + 600 output tokens) is 0.0892 RUB
at 20/82 RUB per million, 0.2248 RUB at 59/178, and 2.025 RUB at 405/2025. These are
arithmetic examples from user-supplied prices, NOT independently verified current
Timeweb tariffs, complete per-conversation invoices or quality comparisons. Hidden
reasoning, history, added context and provider limits must be verified separately.

Timeweb has two distinct transports. Gateway accepts a model ID. Agent-compatible
API uses the model configured on that agent and may ignore the request model;
separate configured agent routes are therefore required. Provider-side fallbacks
must be disabled for a strict quoted route unless separately validated. An unexpected
returned model triggers existing reconciliation instead of silently accepting it.

## Operator configuration and rollout

Keep secrets in server configuration, never the APK or repository. Existing
`TIMEWEB_AI_TOKEN`, `AI_EXTERNAL_PROCESSING_APPROVED`, permitted processing regions,
`AI_USER_DAILY_RUB` and `AI_PROJECT_DAILY_RUB` remain required. Country configuration
is an operator attestation, not proof of residency or automatic legal compliance.

Optional `AI_ROUTE_CATALOG_JSON` is a JSON array. Each object has exactly:
`label`, `model`, `tiers`, `evaluation_id`, `valid_until`, `context_tokens`,
`max_output_tokens`, `structured_json_verified`. Labels use uppercase letters,
digits and underscores. Tiers are nonempty unique strings fast/standard/premium.
An evaluation expiry must be timezone-aware and within the next 31 days. The model
must exactly equal `AI_MODEL_<LABEL>`. No evaluation result is invented by this file.

For each label configure the existing route fields:
`AI_<LABEL>_TRANSPORT`, `AI_<LABEL>_PROCESSING_REGION`,
`AI_<LABEL>_PRICING_MODEL`, `AI_<LABEL>_PRICING_VALID_UNTIL`,
`AI_<LABEL>_INPUT_RUB_PER_MILLION`, `AI_<LABEL>_OUTPUT_RUB_PER_MILLION`,
`AI_<LABEL>_INPUT_TOKEN_ALLOWANCE`, `AI_<LABEL>_TOKEN_PARAMETER`.
Price expiry is at most seven days; token parameter must be tested for that route.
For agents also use `TIMEWEB_AI_<LABEL>_BASE_URL` and `TIMEWEB_AI_<LABEL>_TOKEN`.
Without the catalog, the existing FAST/STANDARD/PREMIUM slots remain supported.

Deploy backend first after green CI and a staged configured-route smoke test. New
native clients fail closed when an old backend lacks quote metadata. Rollback
must keep the compatible backend or roll back the native client too. No paid
provider call, credentials change, production deployment or APK release is part
of the local verification reported below.

## Verification scope

Local selected-file checkout, not a complete repository checkout:

- 91 policy/catalog tests (including 12 malformed-type regressions).
- 51 helper/scenario tests; helper tests execute selected real AST definitions
  with controlled dependencies and SQLite, not the entire HTTP application.
- Python compilation and `git diff --check` passed.
- 16 plain JVM checks executed against the real `ChatRouteQuote` class. JUnit
  cases are included, but full Android/Compose/Gradle verification requires CI.

The foundation commit message incorrectly said 84 tests: its actual initial
policy/catalog count was 79; after 12 additional cases it is 91. The combined
local Python count for this increment is 142, not a full-backend CI count.

Remaining acceptance gates: complete backend/Android/Sonar checks on the final
commit, device chat/estimate/recovery testing, rate/cost/provider smoke testing,
financial model evaluation and calibration, point-in-time walk-forward validation
including costs/delistings/defaults, and appropriate product/legal review before
publishing individualized recommendations. No claim that all 100 broader v0.11.0
items, all Sonar issues, autonomous allocation or predictive accuracy are complete.

## Primary references checked 2026-10-18

- Timeweb gateway connection and exact model IDs:
  https://timeweb.cloud/docs/ai-agents/agent-environments/cline
- Timeweb agent API limitations:
  https://timeweb.cloud/docs/ai-agents/api-usage/openai-compatible-api
- OpenAI gpt-oss model card (text-only, configurable reasoning, structured output):
  https://openai.com/index/gpt-oss-model-card/
- Boyd et al., Multi-Period Trading via Convex Optimization (optimization combines
  forecasts, risk and costs; it does not supply the missing forecast itself):
  https://web.stanford.edu/~boyd/papers/cvx_portfolio.html
