# FL-045 — Provider-start credential and redirect authority must be structural at browser sinks

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-25**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / SonarQube Cloud Security Rating follow-up**

## Symptom / failing gate

After the Telegram/VK backend network destinations were made structurally fixed and the repository formatter defect was corrected, SonarQube Cloud posted another PR Quality Gate failure while `a6266fabc48d53195b1bfa769ed681228610ef34` was the unchanged current head: **Security Rating on New Code = B**, while the accepted project gate requires A.

The available GitHub integration does not expose the private Sonar vulnerability annotation or a Sonar check/status object carrying the analyzed Git SHA. This entry therefore does not claim an exact private rule or issue text. It records the next material trust-boundary weakness found by source/blast-radius review after the fresh RED and delegates final proof to a new exact-head Sonar analysis.

The first provider-start correction was reviewed on exact head `119829e9de198ae665d8cb83b85e3c024cfbedbc`. Gitar then identified two adjacent implementation defects before acceptance:

- Telegram/VK authorization-query construction was duplicated between native runtimes and the deployed browser-bound adapters, creating silent protocol-drift risk;
- the route performed proof/expiry validation after `runtime.start()` had already persisted a pending transaction, so a rejected post-begin result could consume bounded transaction capacity until expiry.

Both findings belong to the same not-yet-accepted provider-start refactor and are folded into this entry rather than creating competing failure-learning documents.

## Root-cause analysis

The provider-start route originally consumed a compound result from the abstract provider runtime and used two returned values directly at browser security sinks:

- `authorization.browser_proof` was written into the initiating-browser proof cookie;
- `authorization.authorization_url` was passed directly to `RedirectResponse`.

Concrete Telegram and VK implementations were safe in runtime intent: the proof originated from `secrets.token_urlsafe`, and both provider authorization origins were protocol constants. However, those facts were hidden behind the abstract `runtime.start(...)` boundary. The route itself could not structurally demonstrate that the cookie credential was locally minted or that an alternate runtime could not select another redirect authority.

The initial adapter implementation corrected provenance but duplicated native query construction and added post-begin rejection checks. Those checks were unnecessary for browser security authority: the route already owns the cookie proof, and the provider endpoint can be fixed independently of runtime output. Treating runtime-returned proof/expiry as browser authority therefore reintroduced avoidable coupling and a bounded-capacity failure path.

This is the same broader failure class established by FL-042 and FL-044: security-sensitive provenance that exists only inside a concrete implementation is weaker than provenance made explicit at or immediately adjacent to the sink.

## Blast radius searched

The follow-up review covered:

- every Phase-5 provider-start producer and consumer;
- Telegram and VK native authorization-query construction;
- browser-proof minting, storage, callback consumption and expiry;
- both in-process and PostgreSQL authorization transaction stores;
- provider-route `Set-Cookie` and `RedirectResponse` sinks;
- bounded pending-transaction capacity and failure paths after `begin()`;
- provider callback session rotation and CSRF binding;
- directly coupled provider-route, rate-limit and hosted-acceptance test doubles;
- already-fixed backend token/JWKS destinations;
- protected V9, tenant authority, broker-write and Real-trading boundaries.

The review also found two stale test authentication doubles still implementing the pre-refactor `authenticate_verified_identity(...)` contract. They were synchronized to the current `resolve_verified_identity -> revoke_session -> bind_session` boundary as an adjacent deterministic failure prevention, without changing production authority.

## Corrective change

Provider-start authority is now split structurally at the browser boundary:

1. `new_authorization_browser_proof_v1()` is an input-free CSPRNG mint called by the route immediately before the proof cookie is created;
2. the route passes that proof into the deployed provider runtime only so the server-side authorization transaction binds its digest;
3. the route writes the locally minted value to the cookie and does not use a runtime-returned proof as browser credential authority;
4. `BrowserBoundTelegramOidcRuntimeV1` and `BrowserBoundVkIdOauthRuntimeV1` bind the route-owned proof through a narrow transaction-store wrapper and then delegate authorization URL/query construction to the existing native Telegram/VK `start()` implementations, so provider parameters are defined once;
5. the adapter extracts only the already-encoded query from the native fixed-origin URL for the browser route;
6. the browser redirect sink selects the Telegram or VK authorization endpoint from source-owned protocol constants and percent-encodes any unsafe query characters before appending the query; runtime output cannot select scheme, host or path;
7. the route no longer rejects runtime-returned proof/expiry after transaction persistence. Its proof cookie uses the fixed accepted browser-proof maximum age, while the server-side transaction remains the actual one-time expiry authority;
8. `Secure=True` remains literal at provider/session cookie sinks, consistent with the existing `__Host-` policy that already rejects non-secure configuration.

The existing native Telegram/VK runtime `start()` behavior remains unchanged for deterministic direct tests and compatibility. Deployed composition uses the browser-bound wrappers, so this remains a `WRAP_ADAPTER` migration rather than a second authentication stack or a provider rewrite.

## Permanent regression / guard

Deterministic tests prove that:

- a route-minted browser proof is the exact proof bound into Telegram and VK authorization transactions;
- invalid externally supplied proof material is rejected before transaction storage;
- an abstract runtime cannot override the redirect origin by returning an attacker-controlled `authorization_url`;
- CR/LF, fragment-like and URL-like query material is percent-encoded while the redirect scheme/host/path remain source-owned provider constants;
- the proof-cookie value is the route-local CSPRNG proof even when a runtime reports a different proof value;
- PostgreSQL retains only the browser-proof digest and consumes the bound transaction with the original proof;
- provider start remains POST-only and provider callback remains browser-bound;
- session issuance still follows `resolve -> revoke -> local CSPRNG mint -> bind -> Set-Cookie`;
- existing rate-limit and hosted-acceptance paths use the current authentication contract.

A fresh exact-head Sonar Security Rating A result remains mandatory. No suppression, `NOSONAR`, quality-profile change, rule exclusion or reduced CI gate is introduced.

## Future prevention rule

For provider-auth browser boundaries:

1. mint browser credentials locally at or immediately adjacent to the cookie sink;
2. pass credentials inward for server-side binding rather than returning them outward from an abstract provider runtime;
3. select redirect scheme/host/path from source-owned provider constants at the response sink;
4. reuse native protocol query construction instead of copying provider parameters into wrappers;
5. do not add fallible post-`begin()` validation when the returned value is not needed as browser authority; keep transaction capacity clean by construction;
6. treat runtime/provider query output as encoded query data only, never redirect authority, and percent-encode unsafe characters before the `Location` sink;
7. keep direct compatibility APIs behind the same primitives, but use a reviewed `WRAP_ADAPTER` for deployed migration when changing a mature provider stack;
8. after every security-source commit, require a new exact-head independent analysis before claiming GREEN.

## Dependency/tooling knowledge change

No dependency update is required. The change uses the existing Python `secrets`, `urllib.parse`, FastAPI/Starlette response surface and accepted provider constants. SonarQube Cloud Security Rating A remains unchanged as the independent acceptance gate.
