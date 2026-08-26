# FL-046 — Cookie-rotation tests must preserve browser cookie scope

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-26**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / exact head `40918d45` / authoritative Windows Regression Shield run `32902327033`**

## Symptom / failing gate

The exact-head DRAFT cycle for PR #391 reached the authoritative `Self-Hosted Windows CI` Regression Shield after the same head had already passed the applicable Ruff, formatter, mypy and focused V10 gates.

The full protected test suite reported:

`1 failed, 2521 passed`

The failing regression was:

`tests/test_v10_wp22a_provider_auth_routes.py::test_callback_requires_initiating_browser_and_rotates_session`

The provider callback itself completed its intended security flow: provider identity resolution, old-session revocation, fresh CSPRNG token minting and server-side binding all ran successfully and the response returned the expected redirect. The failure occurred only when the test performed a name-only HTTPX cookie lookup after rotation. HTTPX raised `CookieConflict` because two cookies with the name `__Host-omni_v10_session` existed in different cookie-jar scopes.

The head remains RED until a new exact-head Regression Shield succeeds. This fixture correction does not satisfy or override the separate SonarQube Cloud Security Rating B blocker observed on the same historical head.

## Root cause

The regression manually seeded the old session with:

`client.cookies.set(BROWSER_SESSION_COOKIE, OLD_SESSION_TOKEN)`

That synthetic cookie had no explicit host/domain scope. The callback response correctly emitted the production `__Host-omni_v10_session` cookie with `Path=/`, `Secure` and no `Domain` attribute. HTTPX therefore retained the manually seeded test cookie and the response cookie as distinct cookie-jar entries with the same name but different scopes.

A real browser does not create the pre-existing `__Host-` session through an unscoped test helper. The cookie is host-bound by a prior server `Set-Cookie` response. The regression fixture therefore did not faithfully model the browser scope that the production replacement operation expects.

HTTPX 0.28.1 intentionally supports domain/path-scoped cookies. Its `Cookies.get()` raises `CookieConflict` when a name-only lookup matches multiple scoped cookies. The failure was consequently a deterministic test-fixture portability defect, not evidence that the production rotation emitted two session cookies.

## Blast radius searched

The review covered:

- every Phase-5 `TestClient.cookies.set(...)` use in the PR diff;
- manual session-cookie fixtures in hosted rate-limit tests;
- provider browser-proof cookie fixtures in provider rate-limit tests;
- hosted technical-boundary session/CSRF fixtures;
- existing accepted WP15/WP22A tests that manually seed cookies;
- every path that expects a same-name server response to replace or delete a manually seeded cookie;
- the provider callback session-rotation assertions;
- the exact accepted dependency pin `httpx==0.28.1`;
- Linux-style focused gates versus the authoritative Windows full Regression Shield.

The analogous manual fixtures do not currently combine an unscoped seed with a same-name server replacement assertion. The material failure is therefore isolated to the session-rotation regression. Production cookie attributes, provider authority, tenant scope, broker authority and public-production locks do not require modification.

## Corrective change

The rotation regression now seeds the synthetic old session into the same host/path cookie-jar slot used by the `https://omni.example` TestClient:

`domain="omni.example", path="/"`

After the callback, session, CSRF and deleted provider-proof assertions use the same explicit host/path scope.

This lets the callback's real `Set-Cookie` replace the synthetic old session in the cookie jar, which matches the browser behavior the test is intended to model. The production route remains unchanged: the `__Host-` session cookie still has `Secure=True`, `Path=/` and no `Domain` attribute.

No cookie-security weakening, dependency update, HTTPX workaround, platform-specific skip, test exclusion or CI relaxation is introduced.

## Permanent regression / guard

The existing provider-route rotation test remains the permanent functional guard and now proves the intended behavior with browser-faithful scope:

- the callback receives and revokes the old session token;
- the authenticated product scope is server-resolved;
- the fresh token is independently minted and differs from old/browser/provider material;
- the exact fresh token is present in the expected host/path session-cookie slot;
- the CSRF cookie in the same scope validates against the fresh token;
- the provider proof cookie is removed from that scope after successful callback.

The authoritative Windows Regression Shield remains mandatory after the correction. Success on a narrower Linux/focused lane does not substitute for that exact-head proof.

## Future prevention rule

For TestClient/HTTPX cookie tests that exercise replacement, rotation or deletion:

1. model the cookie's browser host/path scope when manually seeding pre-existing state;
2. do not use a name-only cookie lookup when the test can legitimately contain more than one scope;
3. use explicit `domain` and `path` in assertions that are about one browser origin;
4. preserve production `__Host-` requirements instead of weakening cookie attributes to make a test jar convenient;
5. search adjacent manual cookie fixtures whenever a cookie-scope failure appears;
6. require the authoritative cross-platform Regression Shield after a fixture correction because narrower lanes can miss cookie-jar/platform interaction differences.

## Dependency/tooling knowledge change

No dependency update is required. The repository remains pinned to `httpx==0.28.1`. The relevant HTTPX behavior is part of its supported cookie API: cookies are scoped by domain/path and a name-only lookup is ambiguous when multiple scoped cookies share the same name.
