# FL-020 — Lifecycle transitions must not be encoded as permanent guard truth

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #331; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-18**  
WP / PR / reference: **WP22A planning-acceptance status synchronization / PR #331**

## Symptom / failing gates

After PR #329 had already completed its merge and exact-main post-merge Regression Shield, the status-synchronization branch advanced live guidance from the temporary planning hold to accepted/current WP22A authority. Three exact-head failures then exposed inherited checks that still encoded transitional wording as permanent truth:

- Engineering Governance required the old current-status sentence forbidding functional WP22A work until the planning PR was merged;
- the inherited WP17 Web/security guard recognized the reviewed WP22A source gate only when the execution contract contained the transient `PLANNING HOLD` lifecycle label;
- the focused WP22A provisioning contract test asserted an exact explanatory comment sentence inside the WP17 guard rather than the executable security properties of that guard.

The third failure occurred after frontend type/lint/tests/build, npm audit, Ruff, formatting and mypy had all passed; focused pytest reported one failure caused solely by the exact prose assertion. Downstream steps were skipped and were not treated as PASS.

## Root cause

Permanent executable guards and tests were coupled to **transient lifecycle labels or prose** instead of durable security/program properties. A planning hold is expected to become current implementation authority after its acceptance lifecycle. A source-code comment can be line-wrapped or clarified without changing behavior. Neither is suitable as a permanent acceptance invariant.

This is distinct from removing safety. The durable properties are unchanged: corrected public-hosted WP22A ownership, WP23 lock, `PUBLIC_MULTI_USER_ENABLED=false` until Exit Gates, no OWNER-home production dependency, source presence not implying live activation, and no broker/Real authority expansion.

## Blast radius searched

The review covered:

- public-product planning guard requirements and forbidden stale markers;
- current-status/live-guidance lifecycle language;
- WP17 reviewed-WP22A source-gate recognition;
- WP22A provisioning/source-contract tests that inspect the WP17 guard;
- analogous whole-text assertions where status labels or explanatory comments can be confused with executable policy.

The existing FL-019 authority-consumer lesson remains applicable; this entry narrows the reusable failure class to lifecycle/prose coupling during an accepted authority transition.

## Why preflight missed it

The branch preflight reviewed the intended status transition and the direct guards, but did not initially challenge every inherited assertion with the question: **is this marker a durable property, or only the previous lifecycle representation/explanatory prose?** The first correction therefore exposed the next stale consumer only when the exact focused audit executed.

## Corrective change

- `check_v10_public_product_plan.py` treats superseded planning-freeze phrases as forbidden live-authority regressions rather than required current truth;
- `check_v10_wp17_web_security.py` recognizes the reviewed corrected WP22A source contract through durable public-hosted/source-gate markers and no longer requires the exact `PLANNING HOLD` status string;
- the WP22A provisioning regression test now asserts the durable marker set and executable denial structure instead of an exact source-code comment sentence;
- no source marker is accepted as evidence that provider mutation, ingress or public production is live.

## Permanent regression / guard

The accepted transition is protected by independent checks:

- current public-product guard rejects restoration of obsolete planning-freeze/product-OWNER wording;
- inherited WP17 source-gate validation requires `CORRECTED PUBLIC-HOSTED TARGET`, the Product Authentication WP22A owner, `WP23+: LOCKED`, `PUBLIC_MULTI_USER_ENABLED=false` and the no-home-production marker;
- WP22A regression coverage explicitly rejects making the old `Status: **PLANNING HOLD / ...` string a required source-gate marker;
- existing direct-ingress/bind-all/Tailscale Funnel denial checks remain intact;
- exact-head CI remains required after every correction.

## Future prevention rule

For every accepted lifecycle transition (`DRAFT -> CURRENT`, `PLANNING HOLD -> IMPLEMENTATION`, `CURRENT -> COMPLETE`, provider `UNSELECTED -> SELECTED`, dormant source -> live activation), classify every asserted marker as one of:

1. **durable invariant** — safe to require permanently;
2. **transition evidence** — belongs in status/evidence and changes when the lifecycle advances;
3. **explanatory prose/comment** — must never be the sole executable safety oracle.

Tests should assert parsed state, durable data/markers and executable behavior. Do not use exact comments or obsolete lifecycle sentences as permanent security truth.

## Dependency/tooling knowledge change

No external dependency changed. The engineering-model change is that **lifecycle state and security property are separate dimensions**. A guard must remain valid when the lifecycle advances normally without weakening the property it protects.
