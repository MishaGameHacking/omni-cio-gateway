# Omni-CIO v9 — Credit, Rating & Default Engine 2.0

Status: **WP6 implementation contract**  
Parent program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`  
Protected production baseline: **Omni-CIO v8.6.1**

## 1. Purpose

WP6 converts a WP5 decision-grade research dossier for a bond into a deterministic Credit Passport. It does not predict returns, issue investment advice by itself, or authorize execution.

Canonical sequence:

`WP5 dossier + WP2 credit floor + debt identity graph → current rating state → default/event gates → credit-floor assessment → immutable Credit Passport`

## 2. Identity is not fungible

The engine keeps these identities separate:

- issue / exact T-Invest instrument UID;
- issuer;
- guarantor(s);
- guarantee terms;
- seniority / subordination.

An issuer rating is never relabeled as an issue rating. If it is used as a policy proxy, the passport records `issuer_proxy`. A guarantor can supply an explicit credit basis only when evidence states that the guarantee is full, irrevocable, unconditional and credit-substitution eligible.

Unknown seniority is fail-closed because recovery/default risk differs materially by capital-structure position.

## 3. Source and provenance boundary

Every entity, issue term, rating and adverse-credit event references SHA-256 hashes of WP5 evidence records. WP6 accepts those references only when:

- the hash exists in the exact bound WP5 dossier;
- the source record is `decision_grade`;
- the dossier itself is decision-ready;
- the WP5 target and dossier fingerprint exactly match the WP6 input.

Missing or context-only/media-only provenance blocks credit readiness.

External text remains data. WP6 contains no prompt interpreter and no external text can alter control flow, policy, ranking or execution permissions.

## 4. Rating agencies and scales

Version 1 explicitly models the four Russian credit rating agencies in the Bank of Russia register:

- ACRA / АКРА;
- Expert RA / Эксперт РА;
- NKR / НКР;
- NRA / НРА.

Supported scale ids are agency-specific Russian national scales. Agency/scale identity is part of each observation.

The engine deliberately does **not** average ratings and does **not** silently convert one agency scale into another. The Bank of Russia publishes regulatory thresholds separately for each agency scale and also publishes a dedicated scale-comparison table; therefore any future cross-scale mapping must be a separately versioned policy/data artifact, not an implicit heuristic.

Current floor comparison requires the IPS `credit_rating_scale` to resolve to the same explicit scale as the selected observation.

## 5. Conservative rating selection

The current state is derived by `(subject, subject_id, agency, scale)`.

- latest effective observation wins;
- a latest `withdrawn` action removes that rating from current state;
- two conflicting observations at the same latest timestamp are an unresolved rating contradiction and fail closed;
- issue rating is preferred for issue policy assessment;
- if no issue rating exists, an issuer rating can be used only as the explicitly labeled `issuer_proxy` basis;
- a guarantor rating is considered only for an explicitly eligible guarantee.

No incompatible scale is averaged or substituted.

## 6. Rating-floor arithmetic

For a supported agency scale, the symbol is normalized to the canonical grade ladder:

`AAA > AA+ > AA > AA- > A+ > A > A- > BBB+ > BBB > BBB- > BB+ > BB > BB- > B+ > B > B- > CCC > CC > C > RD/SD/D`

The parser preserves agency-specific syntax:

- ACRA: `A-(RU)`;
- Expert RA: `ruA-`;
- NKR: `A-.ru`;
- NRA: `A-|ru|`.

A symbol outside the supported syntax fails closed. The resulting rank is used only for deterministic minimum-quality comparison. It is not a probability of default, expected loss, expected return or cross-agency average.

## 7. Default and distress events

WP6 explicitly represents:

- default;
- technical default;
- restructuring;
- payment delay.

An unresolved event is an active adverse-credit event and blocks credit readiness / strong recommendation. Resolved events remain in the passport history and fingerprint.

## 8. Re-analysis triggers

When a previous Credit Passport is supplied, the engine deterministically records re-analysis triggers for:

- WP5 dossier fingerprint change;
- IPS policy fingerprint change;
- rating/action change;
- outlook change;
- watch change;
- default-event set change;
- issue-term change.

The trigger is data-state only. It does not autonomously trade or publish a new plan.

## 9. Determinism

Input ordering is canonicalized before publication:

- guarantors by stable entity id;
- rating observations by stable observation id;
- default events by stable event id;
- blockers and re-analysis codes deduplicated and sorted.

`passport_sha256` binds the full canonical passport, including the exact dossier fingerprint and IPS policy reference.

## 10. Safety boundary

WP6 is internal and pure. It adds no:

- OrdersService / StopOrdersService call;
- Sandbox mutation;
- real-money proposal or submit call;
- withdrawal / transfer capability;
- public FastAPI route;
- OpenAPI Action;
- GPT Editor change.

`CreditPassportV1.trading_methods` is `Literal[False]`.

## 11. Exit gate

WP6 is complete only when:

1. versioned credit entity, issue-term, rating, event, floor and passport contracts exist;
2. WP5 dossier binding and source provenance are fail-closed;
3. issuer / issue / guarantor / seniority remain distinct;
4. incompatible agency scales are not averaged or silently mapped;
5. rating-floor assessment is deterministic;
6. unresolved rating contradictions fail closed;
7. active default / technical default / restructuring / payment delay fails closed;
8. rating/default/policy/terms changes produce deterministic re-analysis triggers;
9. passport fingerprint is source-order invariant;
10. repository guard and mypy cover the package;
11. tests, Ruff, mypy and full Regression Shield pass on the exact final head;
12. unresolved review threads are zero;
13. PR is squash-merged and epic #176 marks WP6 complete.
