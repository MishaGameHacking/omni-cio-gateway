# FL-045 — Provider-start credential and redirect authority must be structural at browser sinks

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-25**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / SonarQube Cloud Security Rating follow-up**

## Symptom / failing gate

After the Telegram/VK backend network destinations were made structurally fixed and the repository formatter defect was corrected, SonarQube Cloud posted another PR Quality Gate failure while `a6266fabc48d53195b1bfa769ed681228610ef34` was the unchanged current head: **Security Rating on New Code = B**, while the accepted project gate requires A.

The available GitHub integration does not expose the private Sonar vulnerability annotation or a Sonar check/status object carrying the analyzed Git SHA. This entry therefore does not claim an exact private rule or issue text. It records the next material trust-boundary weakness found by source/blast-radius review after the fresh RED and delegates final proof to a new exact-head Sonar analysis.

## Root-cause analysis

The provider-start route still consumed a compound result from the abstract provider runtime and used two returned values directly at browser security sinks:

- `authorization.browser_proof` was written into the initiating-browser proof cookie;
- `authorization.authorization_url` was passed directly to `RedirectResponse`.

Concrete Telegram and VK implementations were safe in runtime intent: the proof originated from `secrets.token_urlsafe`, and both provider authorization origins were protocol constants. However, those facts were hidden behind the abstract `runtime.start(...)` boundary. The route itself could not structurally demonstrate that the cookie credential was locally minted or that an alternate runtime could not select another redirect authority.

This is the same broader failure class established by FL-042 and FL-044: security-sensitive provenance that exists only inside a concrete implementation is weaker than provenance made explicit at or immediately adjacent to the sink.

## Blast radius searched

The follow-up review covered:

- every Phase-5 provider-start producer and consumer;
- Telegram and VK authorization-start URL construction;
- browser-proof minting, storage, callback consumption and expiry;
- both in-process and PostgreSQL authorization transaction stores;
- provider-route `Set-Cookie` and `RedirectResponse` sinks;
- provider callback session rotation and CSRF binding;
- directly coupled provider-route, rate-limit and hosted-acceptance test doubles;
- already-fixed backend token/JWKS destinations;
- protected V9, tenant authority, broker-write and Real-trading boundaries.

The review also found two stale test authentication doubles still implementing the pre-refactor `authenticate_verified_identity(...)` contract. They are synchronized to the current `resolve_verified_identity -> revoke_session -> bind_session` boundary as an adjacent deterministic failure prevention, without changing production authority.

## Corrective change

Provider-start authority is now split structurally at the browser boundary:

1. `new_authorization_browser_proof_v1()` is an input-free CSPRNG mint called by the route immediately before the proof cookie is created;
2. the route passes that proof into the deployed provider runtime only so the server-side authorization transaction binds its digest;
3. the route writes the locally minted value to the cookie and rejects a runtime result that reports a different proof;
4. deployed Telegram and VK runtimes use `BrowserBound*` adapter subclasses, preserving the existing provider verification/completion stack while accepting the route-owned proof during `start`;
5. provider runtimes return an encoded authorization query separately for deployed start authority;
6. the browser redirect sink selects the Telegram or VK authorization endpoint from source-owned protocol constants and appends only a tightly bounded URL-encoded query; the runtime-returned full URL is retained only for compatibility and is not redirect authority;
7. `Secure=True` is literal at provider/session cookie sinks, consistent with the existing `__Host-` policy that already rejects non-secure configuration.

The existing native Telegram/VK runtime `start()` behavior remains available for deterministic direct tests and compatibility; deployed composition uses the browser-bound subclasses. This is a `WRAP_ADAPTER` migration, not a second authentication stack.

## Permanent regression / guard

Deterministic tests prove that:

- a route-minted browser proof is the exact proof bound into Telegram and VK authorization transactions;
- invalid externally supplied proof material is rejected before transaction storage;
- an abstract runtime cannot override the redirect origin by returning an attacker-controlled `authorization_url`;
- the cookie value is the route-local CSPRNG proof, not a runtime-selected value;
- a runtime proof mismatch fails closed and clears the proof cookie;
- provider start remains POST-only and provider callback remains browser-bound;
- session issuance still follows `resolve -> revoke -> local CSPRNG mint -> bind -> Set-Cookie`;
- existing rate-limit and hosted-acceptance paths use the current authentication contract.

A fresh exact-head Sonar Security Rating A result remains mandatory. No suppression, `NOSONAR`, quality-profile change, rule exclusion or reduced CI gate is introduced.

## Future prevention rule

For provider-auth browser boundaries:

1. mint browser credentials locally at or immediately adjacent to the cookie sink;
2. pass credentials inward for server-side binding rather than returning them outward from an abstract provider runtime;
3. select redirect scheme/host/path from source-owned provider constants at the response sink;
4. treat runtime/provider output as query/content data, never redirect authority;
5. fail closed if an adapter cannot prove the browser proof it bound is the exact route-owned proof;
6. keep direct compatibility APIs behind the same primitives, but use a reviewed `WRAP_ADAPTER` for deployed migration when changing a mature provider stack;
7. after every security-source commit, require a new exact-head independent analysis before claiming GREEN.

## Dependency/tooling knowledge change

No dependency update is required. The change uses the existing Python `secrets`, `hmac`, `urllib.parse.urlencode`, FastAPI/Starlette response surface and accepted provider constants. SonarQube Cloud Security Rating A remains unchanged as the independent acceptance gate.
