# FL-021 — Inherited acceptance tests must move with an authorized product-boundary correction

Status: **ADDITIVE FAILURE-LEARNING ENTRY FOR PR #336; PRIMARY LEDGER REMAINS `V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md`**  
Date: **2026-08-19**  
WP / PR / reference: **WP22A Phase 2 Product-auth / tenant-security correction / PR #336**

## Symptom / failing gate

On exact PR head `34cdb82`, inherited **V10 WP19 Watchtower Incident Audit #688** reached the shared Web unit suite after repository bootstrap, locked dependency installation, exact-head verification, Web dependency reproduction, TypeScript typecheck and Web lint had all succeeded. The Web test suite reported 56 passing tests and one failure:

`WP22A private access is status-gated and not presented as a public provider`

That historical WP17/WP22A contract still required the visible string `OWNER private access` in `app-shell.tsx`. Phase 2 intentionally removes that historical Cloudflare/edge OWNER login from the normal product shell because accepted authority now requires the PROJECT OWNER to use the same ordinary USER product-auth path as supported users. The failing assertion therefore enforced superseded product-role behavior rather than a still-valid safety property. Downstream browser/audit/Python steps were skipped and are not acceptance evidence.

## Root cause

The Phase-2 change correctly updated the product shell and added a new fail-closed source regression, but preflight did not include the older shared Web contract suite as an explicit **authority consumer**. The inherited test mixed two different properties:

1. keep the already-accepted historical private-edge API source dormant and status-gated for provenance/rollback safety;
2. render that private-edge OWNER path as a normal product-login option.

Property 1 remains valid. Property 2 is explicitly superseded by the accepted Product USER / Engineering Authority boundary.

## Blast radius searched

The correction review covered:

- `apps/web/tests/app_shell_contract.test.ts`;
- `apps/web/src/app-shell/app-shell.tsx`;
- the dormant `private-external-login` client API surface;
- inherited Web test execution used by WP17-WP22 audits;
- Phase-2 permanent source-contract checks rejecting `OWNER private access`, `privateRemoteLogin` and `readPrivateRemoteStatus` in the normal shell;
- repository search for other executable consumers of the historical `private-external-login` / OWNER-private-login wording.

The accepted historical external-access middleware/API source remains untouched where it is still useful as dormant engineering provenance. No provider mutation, public activation or broker-authority change is part of this correction.

## Why preflight missed it

Preflight checked the new Phase-2 Python tests, migration/RLS rehearsal, dedicated source assertions and directly changed shell source, but did not execute or semantically inspect every inherited Web unit contract before opening the expensive exact-head cycle. The existing test name sounded security-positive, so its internal requirement for visible OWNER-product UX was not identified as stale until the shared suite ran.

## Corrective change

The inherited Web contract now verifies the current durable boundary:

- the historical `private-external-login` API/status source may remain present and dormant;
- the normal product shell must **not** contain `OWNER private access`;
- the shell must not call `privateRemoteLogin` or `readPrivateRemoteStatus`;
- loopback-only local OWNER acceptance remains clearly identified as test/acceptance behavior, not a third ordinary login provider;
- ordinary product login remains Telegram/VK.

No test or security gate was disabled. The stale expectation was replaced by assertions for the accepted current product boundary.

## Permanent regression / guard

Phase 2 now has two independent protections:

- the shared Web contract verifies that dormant historical private-edge source is not surfaced as product login;
- `tests/test_v10_wp22a_phase2_source_contract.py` and the focused Phase-2 workflow reject restoration of `OWNER private access` / edge-identity coupling in the product shell.

Any new commit invalidates the failed head's evidence and requires a new exact-head cycle.

## Future prevention rule

When a current WP intentionally supersedes an accepted historical UI/auth behavior, preflight must build an **executable consumer map** that includes inherited component tests, not only new focused tests. For each old assertion ask:

`historical source/provenance that remains safe` **or** `active product behavior that the new authority explicitly replaces`?

Preserve the former; update the latter to the new durable property. A test that was security-positive under an older product model can become a security regression if it forces obsolete privileged UX back into the current product.

## Dependency/tooling knowledge change

No external dependency changed. The reusable engineering lesson is that inherited cross-WP Web suites are architecture consumers: test intent must be revalidated when product identity/authority changes, even if the test file itself is outside the initially changed source set.
