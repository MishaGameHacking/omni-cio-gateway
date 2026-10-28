# F15/F20/F23 — audit of shared liquidity and model JSON

## Exact source slices and limits

Development reviewed: `0c7ef3fbd75f6019aa50ad3ea4c8d9631627c79f` (PR #880).
Main reviewed: `12b5b1fb4f536ae44ddbb01b74e1e9401ccace26`.

This is a focused source audit with reproductions and fixes, not certification of
all 469 changed files, all dependencies, the entire server, or the Android APK.
Existing Sonar results at development 0c7ef3f were already clean (zero new/accepted
issues and annotations); the screenshots describe older commits. This pass does
not take credit for the earlier Sonar fixes and does not suppress any rule.

## Finding: visible liquidity was duplicated across the owner's accounts

`allocation_plan.py` capped each candidate at its own `visible_lots`. Two accounts
could each consume six lots from the same six-lot market observation. This also
applied to sells. Reproduction is synthetic: no live market or order was used.

The v2 allocator first establishes one conservative volume budget per instrument
from the minimum of all fresh candidate observations. Priority allocation consumes
this budget once across accounts. Stale/future quotes remain WAIT and cannot set
the fresh budget. Distinct instruments remain independent. Account-specific
broker limits remain independent. Fees and minimum feasible sale proceeds are
computed after limiting quantity, not corrected by editing the output afterward.

The version and `liquidity_basis` make the changed rule explicit. Without a full
price-level order book this is a conservative draft constraint, not guaranteed
execution or a best-price optimizer. Fresh broker validation, confirmed strategy,
reserved cash, shared risk caps, non-spending of anticipated sale proceeds and
`automatic_order=false` remain. Separate calls are still drafts, not concurrent
executable commitments; their transactional publication remains a separate task.

14 new unittest methods cover buy/sell sharing, partial consumption, distinct
instruments, conflicting/zero/stale depths, fees, blocked capacity, deterministic
priority and repeated calls. One method checks 250 seeded joint plans against an
independent integer oracle. On the original source the new suite produced 252
failed assertions/subcases. After the fix all 14 new and 24 existing allocation
tests pass; the latter include 500 seeded exhaustive sizing checks. The tests load
the actual pure module normally, not a reimplemented sizing formula.

## Main finding: permissive model JSON is not a valid finance boundary

Main rejected literal NaN/Infinity but accepted exponent overflow, nonzero
underflow and duplicate object fields in both content and the response envelope.
The development parser already handles these and now gets the same regression
suite as the focused main backport in PR #883. No new parser is invented here.

The main backport adds the existing 512000-byte / 64-container preflight plus
unique-key and finite-float parsing to both decode sites, preserving the existing
budget/settlement and no-paid-retry semantics. Fifteen regression methods passed
locally using the real HTTP parser and MockTransport. The local loader omitted
unrelated DB/queue imports; this is not full backend integration. Committed tests
import the ordinary backend modules in CI. No critical exploitation or RCE has
been demonstrated; these are data-integrity and parser-budget findings.

## Other inspected boundaries, not exhaustive certification

- owner_access.py / owner_app.py retain configured identity, fail-closed startup,
  transactional guards and explicit rebinding. No first-visitor enrollment added.
- require_clean_sonar.cjs still requires exact SHA, trusted check identity, newest
  result, completed success, zero annotations and unambiguous zero issue counts.
  Its current test file uses node:test; it is not removed or excluded.
- Legacy main CI evidence logging is not equivalent to the newer strict dev gate.
- Main and PR #880 need separate exact-head CI; a draft backport does not change
  main. No merge, deployment, resource purchase, token change or APK publication.

Primary references:
- https://docs.python.org/3.14/library/json.html (parse_float, object_pairs_hook,
  parse_constant and untrusted-input budgets).
- https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
  (deny by default and check authorization for each request).
- https://docs.sonarsource.com/sonarqube-cloud/analyzing-source-code/test-coverage/overview
  (coverage must be measured and imported; a green static gate is not coverage).

Remaining release work includes whole-repository integration, dependency/security
review, the owner-approved Android17 migration, emulator/physical-device checks,
and the end-to-end recommendation pipeline. No historical API35/36 pass can
certify Android17. Source-code commits are not a running Timeweb installation.
