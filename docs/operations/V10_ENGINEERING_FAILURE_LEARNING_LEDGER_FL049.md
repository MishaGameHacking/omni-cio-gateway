# FL-049 — Sonar annotations must be resolved as one evidence-backed defect class

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-26**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / exact head `f8bdde940f7e9cf4b5f55112f9c4779f14a09680`**

## Symptom / failing gate

The integrated Phase-5 DRAFT head had repository CI success but SonarQube Cloud remained RED with **Security Rating on New Code = B** where **A** is required. The GitHub check summary reported 17 annotations, while the available automation surface did not expose their issue payload.

A later GitHub UI evidence capture exposed all 17 annotations. They were not one isolated security sink; they were a mixed hardening set across production and deterministic tests:

- four cognitive-complexity findings in hosted middleware/app composition, provider routes and Telegram JWKS refresh;
- two provider runtime override-signature findings;
- two duplicated-literal findings;
- seven exception-test single-invocation findings;
- one React component readonly-props finding;
- one CSRF cookie `HttpOnly` security review finding.

## Root cause

The Phase-5 implementation had accumulated correct security behavior behind several analyzer-hostile structural boundaries:

1. provider-specific subclasses widened a base `start()` signature instead of making the shared runtime contract authoritative at the base implementation;
2. large composition functions combined independent admission, mutation, routing and recovery concerns;
3. the browser-readable CSRF double-submit cookie was intentionally non-`HttpOnly`, even though the server could deliver the already session-bound CSRF value through the authenticated bootstrap response and keep the cookie script-inaccessible;
4. deterministic exception tests performed timestamp/string/setup calls inside `pytest.raises` blocks, obscuring the single operation expected to throw;
5. repeated literals represented shared protocol constants but were encoded independently.

The earlier response-header and CSPRNG hypotheses were useful falsification steps but were not the complete defect class. Exact annotation evidence changed the repair strategy from sink speculation to complete static-analysis closure.

## Corrective change

The repair is intentionally systemic:

- Telegram and VK base runtimes now implement the common optional route-owned `browser_proof` start contract directly; deployed adapter classes no longer override the method signature;
- provider route orchestration is split into start, callback parsing, provider completion and authenticated-session establishment helpers;
- hosted request security is split into transport, admission/session-resolution and mutation/CSRF guards;
- hosted FastAPI routes are registered through small bound route methods instead of one large nested route factory;
- Telegram JWKS single-flight refresh is split into cache lookup, refresh claim/wait, failure publication and successful publication stages while keeping provider I/O outside the shared lock;
- the session-bound CSRF cookie is `Secure` + `HttpOnly`; authenticated session bootstrap returns the already verified CSRF value and browser code keeps it only in module memory for `X-Omni-CSRF`, never in Web Storage;
- shared protocol/media literals are represented once;
- exception-test setup values are computed before `pytest.raises`, leaving one target invocation in each exception context;
- React login props use an explicit readonly contract.

No `NOSONAR`, rule exclusion, quality-profile change, skipped gate or reduced security assertion is introduced.

## Blast radius / preserved authority

The review covers provider transaction storage, provider start/callback routing, session fixation protection, CSRF transport, hosted request admission, Telegram JWKS refresh, frontend credential handling and directly coupled tests.

The following authority remains unchanged:

- protected V9 entrypoint `app:app`;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no preview/private/OWNER human session issuer;
- no WP23+, AI/Cortex or Real-execution expansion.

## Permanent prevention rule

When an independent analyzer gate exposes multiple annotations on one exact head:

1. recover the complete annotation set before further speculative source changes whenever evidence is available;
2. group findings by shared root cause and repair the underlying contract rather than adding analyzer-specific wrappers;
3. keep security-cookie changes behaviorally equivalent or stronger and add deterministic transport guards;
4. structure exception tests so setup is outside the exception context and exactly one target operation is allowed to raise;
5. refactor cognitive complexity by extracting responsibilities and early-return guards, never by suppressing or raising thresholds;
6. treat every new commit as a new exact-head candidate requiring fresh independent analyzer evidence.

A fresh SonarQube Cloud result on the new exact head remains the authority for whether this repair closes the gate.
