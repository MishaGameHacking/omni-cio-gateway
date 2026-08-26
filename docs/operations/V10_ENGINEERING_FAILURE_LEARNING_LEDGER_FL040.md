# FL-040 — Untrusted request metadata must not grant authenticated or proxy authority

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-25**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / DRAFT head `8ee86fd4` / independent Gitar review**

## Symptom / review finding

Independent review on PR #391 identified two trust-classification problems in the hosted request-security middleware:

1. any session cookie that merely matched the opaque-token character/length pattern was passed to `HostedRequestAbuseControlV1` as an authenticated session key before the server-side session registry resolved it;
2. the application read `X-Forwarded-Proto` directly from the request and allowed the value `https` to satisfy its HTTPS gate based on a deployment comment rather than a source-enforced proxy trust decision.

The first defect allowed an unauthenticated caller to rotate shape-valid fake session cookies, receive separate higher-capacity session buckets and consume the shared global API capacity. The second made a client-supplied forwarded header an authority signal if the middleware were reused outside the exact reviewed Render edge boundary.

Both findings are blockers even if deterministic CI is otherwise GREEN. Review-thread resolution without source changes would not satisfy the Phase-5 trust-boundary contract.

## Root cause

The two defects share one design mistake: **syntax or transport metadata was treated as authority before the authoritative boundary had verified it**.

For session classification, token shape is useful only to reject malformed attacker input cheaply. A syntactically plausible token says nothing about whether the server issued it, whether it still exists, or whether it was revoked or expired. Only the server-side session registry can establish a live authenticated session.

For TLS classification, `X-Forwarded-Proto` is an ordinary request header unless a trusted proxy layer has already authenticated the connecting intermediary and rewritten/validated the forwarded metadata. A code comment describing Render's topology did not turn the header into a trusted value.

## Blast radius searched

The review covered:

- `HostedPreviewSecurityMiddlewareV1` request ordering;
- `HostedRequestAbuseControlV1` global, anonymous and per-session limiter keys;
- process-local and PostgreSQL session `resolve()` semantics;
- malformed, shape-valid fake, revoked/expired and live-session behavior;
- the provider start/callback path and its independent provider abuse limits;
- `/healthz` capacity isolation;
- hosted entrypoint composition and the accepted Render `.onrender.com` boundary;
- current Render documentation stating that its load balancer terminates inbound TLS and forwards to an application port that is not directly reachable from the public Internet;
- current Uvicorn proxy guidance warning that forwarded headers are safe only when the connecting proxy is explicitly trusted;
- directly coupled hosted rate-limit, entrypoint and browser-security tests.

No change is required to broker authority, tenant identity, provider authentication protocols, protected V9 `app:app`, dependency versions or public-production activation locks.

## Why earlier preflight missed it

An earlier source review correctly noticed that obviously malformed session cookies should not create attacker-controlled limiter keys, but the corrective rule stopped at token-shape validation. It did not challenge the deeper authority question: whether a shape-valid token had been resolved as a live server session before receiving authenticated capacity.

Likewise, the Render edge comment correctly described the accepted deployment topology, but the implementation still consumed a client-controlled forwarded header. The review did not separate "the provider terminates TLS" from "this particular header value is trusted by the application."

Independent review therefore exposed two adjacent failure modes that deterministic unit/format/type gates alone were not designed to infer.

## Corrective change

### Session/rate classification

The product API limiter is split into ordered stages:

1. consume the bounded global API allowance **before** any session-store lookup;
2. reject malformed session-cookie candidates without querying durable state;
3. resolve a plausible token against the server-side session registry;
4. grant the per-session limiter key only when that lookup returns a live `SessionScopeV1`;
5. collapse missing, fake, revoked or expired tokens into the shared anonymous bucket;
6. reuse the resolved scope for endpoint authorization so the same request does not perform a second session lookup.

This preserves bounded PostgreSQL work under fake-token rotation and prevents syntax from becoming authentication authority.

### Render TLS/proxy classification

The application no longer reads `X-Forwarded-Proto` as an HTTPS authority signal.

The generic hosted app defaults to requiring an actual HTTPS ASGI scheme. The reviewed Render entrypoint explicitly sets a source-level `trusted_edge_tls_terminated=True` composition assertion only for the accepted `.onrender.com` host, relying on the provider-documented fact that Render terminates public TLS and the forwarded application port is not directly public.

A client-supplied `X-Forwarded-Proto: https` therefore cannot make an otherwise direct HTTP request pass the generic gate. A future hosting topology must establish a new reviewed proxy-trust boundary rather than inheriting Render's assertion.

## Permanent regression / guard

Deterministic tests now prove that:

- a live server-resolved session receives the bounded session bucket;
- a shape-valid but unresolved token remains anonymous;
- malformed tokens do not reach the session store;
- the global cap rejects additional fake-token work before another durable lookup;
- a client-supplied `X-Forwarded-Proto: https` cannot bypass the default direct-HTTP rejection;
- the source-declared trusted Render edge accepts the provider's internal HTTP hop without consuming client forwarded headers;
- the deployed `create_app()` composition explicitly selects that Render edge boundary.

The existing exact-head formatter, mypy, tests, security audits and independent review remain unchanged and must all succeed on the new head.

## Future prevention rule

For request metadata used to select a more privileged security class:

1. identify the authoritative verifier first;
2. use syntax/shape checks only as bounded pre-validation, never as proof of identity;
3. enforce a global work cap before attacker-controlled lookups where feasible;
4. classify authenticated capacity only after durable/session authority confirms a live session;
5. never trust forwarded headers merely because the current deployment happens to sit behind a proxy;
6. encode provider-specific trust in reviewed composition/configuration and keep the reusable middleware fail-closed by default;
7. test both the intended trusted path and the spoofed metadata path.

## Dependency/tooling knowledge change

No dependency update is required. The finding changes request-authority ordering and hosted composition only. Current Render and Uvicorn documentation was rechecked to distinguish provider TLS termination from application-level forwarded-header trust.
