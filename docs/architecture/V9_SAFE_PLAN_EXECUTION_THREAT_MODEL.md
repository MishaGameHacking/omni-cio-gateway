# WP12 Safe Plan Execution — Threat Model

## Trust boundary

WP12 sits between a valid, immutable WP11 plan and the already accepted v8.6.1 real-order primitive. It may orchestrate real BUY/SELL stages only after exact owner approval of the same plan. It must never create a parallel broker execution path.

Trusted inputs are limited to validated internal contracts, trusted read-only portfolio/risk providers, trusted instrument/market evidence, the durable execution journal and the existing `RealTradingServiceV1` adapter.

## Protected assets

- exact WP11 `plan_sha256` and owner approval challenge;
- exact ordered plan legs, lots and direction;
- the WP10-declared execution horizon encoded into WP11 expiry;
- current portfolio/cash/risk state;
- current instrument identity and lot size;
- fresh market/spread/liquidity/price-step evidence;
- v8.6.1 per-order/daily hard caps and own-funds/own-position rules;
- v8.6.1 proposal/request UUID idempotency;
- durable plan/session/attempt journal state;
- broker reconciliation evidence;
- trading token, gateway secret and account identifier confidentiality.

## Threats and controls

| Threat | Control |
| --- | --- |
| Mutated plan is supplied under an old SHA | Full Pydantic re-validation plus canonical `portfolio_plan_sha256` recomputation before use |
| Approval phrase is reused for another plan | Session is bound to exact plan SHA and approval evidence hash; mismatch halts |
| Same approval request is replayed | Already-approved session returns replay; approval itself never submits |
| Caller substitutes ticker, direction, quantity or price | Stage derives all order fields from exact immutable leg plus trusted instrument binding/quote; returned legacy proposal is checked field-for-field |
| Portfolio changes after plan review | Current lots/cash and plan-progress reconciliation run before preparation and submit |
| Policy/risk/strategy/optimizer/target-risk identity drifts | Current SHA bindings and fresh WP11 review fail closed before stage action |
| Instrument identity or lot size changes | Current binding is compared to stored stable key, UID, ticker, ISIN/type/lot contract |
| Quote is stale/future or price step is invalid | Fresh quote timestamp and exact increment checks fail closed |
| Spread/depth/turnover deteriorate | Execution market guard compares current evidence to immutable WP11 baseline and bounded tolerances |
| Own funds or own position no longer support a leg | Existing v8.6.1 `GetMaxLots` preflight runs during prepare and again immediately before submit |
| Per-order/daily cap would be exceeded | Existing v8.6.1 hard caps remain authoritative; daily cap reservation remains atomic |
| A tighter current cap would silently stretch the approved plan into extra days | Preparation computes the actual cap-constrained stage count and rejects the session if the last slice would fall outside immutable plan expiry; no cap increase or plan extension occurs |
| A delayed leg catches up by submitting several staged slices on one day | Any prior submission for the same immutable instrument on the Moscow date blocks another slice until the next date |
| A multi-leg plan is serialized by whole instrument and drifts away from portfolio-level staging | Scheduler orders pending work by `stage_index` and then exact `leg_sequence`, preserving leg order inside each tranche/day |
| Prepared price changes before submit | Stage is reset for fresh preparation; old proposal is not silently modified |
| Network result is ambiguous after possible `PostOrder` | Attempt becomes unknown, entire session halts and only original request-id reconciliation is allowed |
| Replay attempts to submit an already submitted proposal | Existing proposal state is detected and recorded as replay; no second submit |
| Partial fill is treated as complete | Broker status/lots are explicit; active/partial state never advances to next stage |
| Partial terminal fill is replaced on the same day | Remainder returns to pending with earliest next Moscow date = following day; same-instrument daily guard remains active |
| Broker terminal fill is not reflected in portfolio yet | Read-only portfolio/cash reconciliation must pass before stage progression; bounded wait then fail closed |
| Plan expires after submit but before broker evidence is visible | New submits stop, but original request-id broker/portfolio reconciliation remains permitted so ambiguity is never hidden by expiry |
| Concurrent callers advance same execution | Durable journal compare-and-swap revision must advance by exactly one |
| Journal outage, corruption or tamper | Production requires durable journal; integrity/storage/conflict failures fail closed |
| Staged execution becomes hidden recurring trading | One slice per immutable instrument per Moscow day is enforced, every later advance still belongs to the same explicitly approved immutable plan, and no scheduler is introduced in WP12 |
| GPT or other caller bypasses server rules | No free-form direct broker submit is added; WP12 delegates every order to accepted v8.6.1 server primitive |
| Real account/token leaks to logs/state | Contracts store no token and no full account id; existing real-trading sanitization/masking remains authoritative |

## Ambiguous submit invariant

The highest-risk failure is a transport error after the broker may have accepted `PostOrder`. WP12 therefore treats ambiguity as a possible submit, not as a failed submit. Remaining plan legs halt. The same proposal/request id may only be reconciled; it may never be automatically re-prepared or resubmitted. Plan expiry cannot turn this condition into a fresh order opportunity.

## Horizon invariant

WP10 determines whether a portfolio leg needs multiple execution days. WP11 encodes the maximum required execution-day count into plan expiry while retaining the short owner-validity tail on the final day. WP12 may respect a tighter current real-order cap only if the resulting stage count still fits inside that exact expiry. If it does not fit, preparation fails before owner approval and before any broker proposal exists.

This prevents both unsafe directions: WP12 cannot silently extend authorization to new days, and it cannot silently increase the real-money cap to force the trade through faster.

## Owner authorization boundary

Development autonomy, portfolio-management intent and WP11 plan generation are not trading authorization. A WP12 session records approval only after an exact match to the owner challenge embedded in the still-valid immutable plan. This is the authorization for that exact plan, not a general trading mandate.

## Non-goals / prohibited authority

- no withdrawal or transfer;
- no margin or uncovered short;
- no MARKET/BESTPRICE;
- no stop/replace/async order methods;
- no autonomous recurring real-money scheduler;
- no automatic cap increase;
- no automatic plan extension/reissue;
- no token management;
- no second real-trading service;
- no GPT v9 activation before WP15.

## Release boundary

Code/test/CI completion proves the software contract only. Any minimal-real WP12 acceptance must be separately and explicitly owner authorized. Existing v8.6.1 real execution remains the protected fallback until WP12 passes its complete exit gate.
