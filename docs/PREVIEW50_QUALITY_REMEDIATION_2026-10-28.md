# Preview50: product-code quality remediation, not publication

## Fresh starting point

PR889 HEAD3a0c5117ce363d6d4b2ec4cdd2d34dc1067f983c and main
f54912165127bfab42673743cd141d635e20881f were re-read on28.10.2026.
Android40617947106 and Backend40617947271 completed with FAILURE:
the laptop build/project-test steps passed, but the mandatory Sonar step failed.
Android installation/upgrade, exact-APK handoff and publication were skipped.
No in-progress run was reported before staging this product-source correction.
Recent PR comments, AGENTS, README and the candidate checkpoint were read.

The owner's requested outcome remains a verified APK on Timeweb9417611.
A source commit, a successful build step or a backend-only deployment is not
that outcome. Version50 remains an unpublished candidate; preserve applicationId,
certificate, existing server data and channel policy. Full N00–N11 is unfinished.

## Changes in this batch

- Separate broker calendar schema, per-section/day evaluation and combined state.
  Keep exact venue identities, duplicate conflicts, UTC windows, exclusions,
  overnight sessions and conservative failure results. Required venues still
  return a sorted tuple; missing metadata never defaults an instrument to MOEX.
- Separate cash balance validation, settlement coverage and movement identity.
  Keep all scope/currency checks, exact Decimal arithmetic and settlement bounds.
  Preserve conflicting versions even outside the arithmetic window, cancelled/
  unresolved behavior, deduplication and evidence IDs. No real-account calculation
  or broker execution is enabled.
- Separate exact-flow TWR validation and bounded XIRR root selection while keeping
  precision50, the same sign/uniqueness conditions, supported rate bounds and
  bisection termination. A zero rate is not confused with an unavailable root.
- Separate provenance/reference validation and clocks; retain traversal limits,
  conflicting-ID exclusion, unknown publication dates, freshness precedence and
  the explicit statement that provenance is not financial truth verification.
- Make server connection-state selection explicit. Extract the Android summary's
  nullable read-only-mode predicate without changing payload/display semantics.
- Centralize the offline inspector's three fixed evidence filenames. Its input
  restrictions, filesystem checks and exclusive output remain unchanged.

New synthetic public-contract regressions cover exact dictionaries, duplicate
and settlement boundaries, scope validation, XIRR bounds/zero, exact venues,
partial calendar failures, provenance conflicts/clocks and traversal limits.
Existing assertions/tests were not removed, skipped, accepted or weakened.

## Verification boundary

The five prepared Python texts were syntax-parsed without importing/executing
project code; their uploaded Git blob identities matched the intended text.
That is not project test execution. All current-head tests/builds must execute
through the existing Android/Backend CI on LAPTOP-NPSGA016 and its existing WSL.
New tests and the Kotlin change are UNVERIFIED until those runs finish.
Previous failure reports remain unchanged. No Sonar success is claimed here.

The previously denied Windows-controller change is not retried, re-encoded,
moved to another helper, or delegated. `.github/scripts/windows_android_ci.py`,
workflows, remote transports, permissions, signing, release gates and production
configuration are untouched. Its remaining findings and the publisher advisory
remain open; this batch cannot authorize publication over those failures.
The unsuccessful Codex implementation response is not treated as execution.

The public Timeweb policy could not be read from this environment due to DNS;
this is not evidence of a server outage or a fresh observation of version49.
No APK delivery, physical-phone installation, trade, paid application AI call,
new resource, production database change or main merge was performed here.
