# N00: recovery of system animation and full Linux checks

Status: N00 is in progress. N01–N11 are not implemented by this checkpoint.
Candidate 0.13.1-preview / 39 was built and statically verified; published APK38 remains unchanged.

## Observed failures

The complete Linux suite in run40227746918 collected the POSIX installer tests.
It reported 1683 passed, 1515 subtests passed and one failed documentation
contract. The failed assertion still required a five-user installation after
the owner had changed the requirement to one confirmed owner.

Both API37 profiles in run40227132451 installed and launched the exact APK38
but failed while checking motion recovery after Android's animator scale changed
from 0 back to 1. This is a failed UI gate, not successful Android acceptance.

## Windows-applied corrections

The Compose scene now registers ValueAnimator.DurationScaleChangeListener and
uses the scale delivered by that callback. A Settings ContentObserver could
read ValueAnimator's old cached value before the animation subsystem applied
the notification. The listener is removed when the composition is disposed;
lifecycle, user choice, power saving and thermal constraints remain in place.
The Android runtime test additionally requires draw operations to resume after
animations are re-enabled and records the last observed policy on a failure.
Official API reference:
https://developer.android.com/reference/android/animation/ValueAnimator#registerDurationScaleChangeListener(android.animation.ValueAnimator.DurationScaleChangeListener)

The documentation test checks the current single-owner section, exact confirmed
identity, rejection of first-visitor ownership, preservation of owner binding,
multiple accounts/sessions for that owner, and absence of payments. Runtime
admission tests were not removed or relaxed.

Candidate identity is 0.13.1 / 39. Version and listener lifecycle source guards
were updated to this candidate; package IDs, SDK37 and signing identity remain.

## Provenance and checks

All six changed files were applied on LAPTOP-NPSGA016 in
`C:\actions-runner\_work\omni-cio-gateway\omni-cio-gateway\windows-development-40232404397-1`.

Base commit: `dba38f9d9b8d9e0b97360d889f4c59ff5c30f781`.
Base code inventory SHA-256:
`c909e7860e2da29ab82b247115e3b765d87d6a43b91d49eeed913f4ee2b7eee5`.
Applied code inventory SHA-256:
`259a45f022c53cdf1ef7cca4e8631bdfa2b3f9a1ddf04d8800b5f1426905b03e`.
Reviewed transport SHA-256:
`5a4520471bab122f524f9189d9bfddc553e5459708fa25d328dd761c5c8a5bff`.

[Windows run40232404397](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40232404397)
passed dependency checks, Python source audit, workspace guards, all host,
tools and Node tests. The complete backend suite ran as analyst-ci in the
project-owned Ubuntu-24.04 on that laptop, followed by health/OpenAPI checks.
Linux report status is passed with no changed source files; the complete
check stage finished at 2026-10-25T20:51:40.630010Z.

[Live provenance report](https://github.com/MishaGameHacking/omni-cio-gateway/commit/9ca73e8849559e0b8875298788f4fc7968ce05eb/checks)
records exact applied file hashes and separate check/build states.
An earlier attempt, run40232092366, failed three stale source guards after
the version/listener change. Those guards were corrected and the full host
suite rerun; that failed attempt is not a release receipt.

Gradle/JVM/lint/APK verification subsequently passed in the same Windows run.
Both Android page-size profiles then passed animation recovery and session context,
but stopped at a false Canvas-readiness requirement on the plain privacy screen.
See [the current native-screen repair and complete rerun](N00_NATIVE_SCREEN_READINESS_2026-10-25.md).
This is not a full runtime pass or a new publication; N00 remains in progress.
