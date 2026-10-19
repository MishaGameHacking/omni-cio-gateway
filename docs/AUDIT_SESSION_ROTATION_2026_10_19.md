# F01 / F22 / F23 — session rotation readiness and audit integration

19 October 2026. Continuing audit, not a completed 0.11.0 release.

## Owner authorization and main

The owner explicitly authorized merging ready branches at 18:48 UTC. PR #881
was merged by the repository's permitted squash method as
`97149a309361aa0db0da3c07d2e7342f23d3cc8b`. Its checked head was
`cb4f9e453c037fb71c430977e76b055a1d529ca3`, against main `12b5b1f`.
Backend CI #423 (39301508090), Android CI #657 (39301508025), and the exact-head
Sonar check 118227928136 all completed successfully. Android included its
existing API35/API36 installation/upgrade/profile matrix. This validates the
main-compatible changes, NOT the larger development UI in PR #880.

The merge has no APK publication marker. APK release publication requires that
explicit marker or manual dispatch; backend deployment is manual. No deployment,
release dispatch, Timeweb mutation or update-channel change was performed.
Post-merge checks and the new development/base combination still need their own
results. The original PR description has been updated to reflect permission,
its added connection migration, final checks and previously corrected diagnosis.

## Reproduced code defect

Baseline: `8ee4d2078680b2a00f55aba8085fc502201315be`.
The historical failed check `Signed-out Activity did not change to landscape`
was investigated in `.github/scripts/session_context_probe.py`.
`_rotate_signed_out` first waited for `_signed_out_landscape`, which required
both landscape geometry and an already-visible signed-out label. Only AFTER
that wait did it call `probe.reveal` to scroll the label into view. When the
label was below the visible fold, the action needed to satisfy the wait could
never run. A larger font or shorter viewport exposes this dependency.

This is a reproduced test-driver ordering defect, not proof of a native renderer
crash, not an authentication bypass, and not proof that it explains every failed
emulator run. The development Android #656 (39301400192) remains a failed run;
passing compilation/lint and retained partial evidence do not change its result.

## Repair and invariants

Separate readiness from the final assertion:

1. Wait for landscape geometry AND the visible workspace of the exact debug app.
2. Use the existing native accessibility scroll to reveal the signed-out label.
3. Require the exact app's visible signed-out label and matching landscape
   geometry before AND after the unmodified console PNG in `landscape_frame`.
4. Restore physical pose/logical settings and confirm original geometry through
   the existing context manager, including failure paths.

A foreign app's matching text cannot satisfy readiness or final state. A hidden
workspace, portrait frame, missing/hidden signed-out label, label lost during
capture, stale frame or resized PNG still fails. Neither renderer, layout,
production session logic, screenshot bytes, polling budgets, quality gates nor
font cases were removed or weakened.

This follows the Android testing contract of acting and waiting for observable
state, including scrolling until a target is found, rather than predicting a
transition duration. Existing native-input implementation remains in place;
this patch does not introduce legacy Android APIs or a new test framework.

## Local regression evidence

Original source bytes were checked against Git blob identities:

- session_context_probe.py: `34a70ce01da5c25aaaf8bd201c440ce96ef0ee45`
- tests/test_session_context_rotation.py: `9a4b145ed7be675e415f8f727895427e630b1f67`
- emulator_rotation.py: `a8d6a4fcb6c81550e85946e1b5d34269a9db0ab6`
- native_input_evidence.py: `806d9e826cf0a6994f51b977f9c81c071dc76921`

Added 9 unittest methods to the existing 14, preserving old scenarios. New cases
reproduce the pre-scroll deadlock, check app/visibility boundaries and verify
that the large-font path still rejects incorrect PNG dimensions. On the old
source the expanded suite fails; with the repair all **23 methods pass**.
`compileall` also passes for the local checked source set.

These are unit simulations executing the real rotation/readiness helpers with
synthetic UI trees and mocked device/PNG boundaries, not a local emulator or
full private checkout. Only complete final-head CI can establish the actual
API35/API36 result. No physical phone, live Telegram/broker/model or API37
validation is claimed. All open 0.11.0 acceptance criteria remain open.

Full-checkout reproduction:

```sh
python -m unittest discover -s .github/scripts/tests -p 'test_session_context_rotation.py' -v
python -m compileall -q .github/scripts
```

Primary reference:
https://developer.android.com/training/testing/other-components/ui-automator-legacy#handling-transitions
