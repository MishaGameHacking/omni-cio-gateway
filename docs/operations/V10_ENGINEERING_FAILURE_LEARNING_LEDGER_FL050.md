# FL-050 — Stronger CSRF transport requires cross-layer regression-guard migration

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR WP22A PHASE 5; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-26**  
WP / PR / reference: **WP22A Phase 5 integrated technical closeout / PR #391 / exact head `6074ad92de8b25e4c42ca4fe5d5798a2f01f77ec`**

## Symptom / failing gate

Fresh exact-head DRAFT verification after the Sonar hardening commit failed in `V10 WP22A Clientless Access Audit`, step `Run WP22A static and unit contracts`.

The surrounding evidence was already GREEN on the same exact head:

- Web typecheck, lint, 61 unit tests and production build succeeded;
- Web dependency audit reported zero vulnerabilities;
- focused Ruff check and formatter check succeeded;
- repository-wide mypy succeeded for 340 source files.

The single failing assertion was:

`tests/test_v10_wp22a_external_access.py::test_frontend_remote_mutations_echo_host_bound_csrf_cookie`

It required the literal `__Host-omni_v10_csrf` to remain in `apps/web/src/app-shell/api.ts`.

## Root cause

The accepted historical clientless regression test encoded a transport implementation detail: browser JavaScript had to know the CSRF cookie name because it previously read the double-submit cookie directly.

The Sonar hardening change deliberately strengthened the Phase-5 hosted browser model:

- the session-bound CSRF cookie is now `HttpOnly` and therefore unavailable to JavaScript;
- authenticated `/api/v10/web/session` validates the session and the bound CSRF cookie server-side before returning `csrf_token` in the bootstrap JSON;
- browser code retains the token only in module memory and sends it as `X-Omni-CSRF` for unsafe same-origin requests;
- middleware still requires the session cookie, CSRF cookie, header equality, session-bound HMAC validation, exact Origin and Fetch Metadata policy.

The old test therefore failed because the security boundary became stronger, not because CSRF protection was removed. The workflow's later source-contract guard already checked the correct invariant (`X-Omni-CSRF` present; Web Storage absent), confirming that this was an isolated stale consumer.

## Corrective change

The cross-layer Python regression guard is migrated to the current security invariant. It now requires:

- no `__Host-omni_v10_csrf` cookie identifier in frontend API source;
- no `document.cookie` or `readCookie(` browser-cookie access;
- authenticated session bootstrap path `/api/v10/web/session`;
- explicit `csrf_token` bootstrap extraction;
- transient `csrfHeaderToken` in-memory handling;
- `X-Omni-CSRF` mutation header;
- no `localStorage` or `sessionStorage` credential persistence.

No production security check, workflow threshold, test count, quality profile or CI requirement is weakened.

## Blast radius / preserved authority

Direct consumers reviewed:

- `apps/web/src/app-shell/api.ts`;
- `apps/web/tests/app_shell_contract.test.ts`;
- `tests/test_v10_wp22a_external_access.py`;
- `.github/workflows/v10-wp22a-clientless-access-audit.yml`;
- hosted CSRF validation and cookie issuance added in the preceding hardening commit.

The dormant historical `external_access_v1.py` Phase-A path is intentionally unchanged; its accepted source markers remain required by the clientless audit and do not become Phase-5 product-session authority.

V9, broker and execution locks remain unchanged.

## Permanent prevention rule

When a security transport is strengthened or migrated:

1. inventory not only runtime producers/consumers but also cross-language tests, source-contract scripts and workflow assertions;
2. encode the security property (provenance, confidentiality, binding, no persistence), not a replaceable browser implementation detail;
3. a stronger HttpOnly boundary must never be reverted merely to satisfy an older text-search guard;
4. a new commit invalidates all previous exact-head GREEN evidence and requires a fresh complete gate cycle.
