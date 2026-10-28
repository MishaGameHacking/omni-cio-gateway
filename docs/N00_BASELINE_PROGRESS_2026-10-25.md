# N00: Windows/Linux baseline and session-context regression

Status: in progress; this is not a release or completion of N00–N11.

## Verified Windows source change

The two files in this change were applied on LAPTOP-NPSGA016 at
2026-10-25T19:41:03.141546Z in the isolated checkout:

`C:\actions-runner-2\_work\omni-cio-gateway\omni-cio-gateway\windows-n00-40227132451-1`

Base commit: `d83349eb43cde10bd009c86705748f9f2e330f06`.
Base code inventory SHA-256: `a31fe06270f7d878422725a1f654824cc911c1ae55ad1925e45bfd07b4dbe89c`.
Patched code inventory SHA-256: `c909e7860e2da29ab82b247115e3b765d87d6a43b91d49eeed913f4ee2b7eee5`.
Reviewed transport SHA-256: `2da0d28d55cf50db89fa06f04b566f94f17cf41b53262c5cfd7640d64c2ddac9`.

| Windows-applied file | SHA-256 |
|---|---|
| .github/scripts/session_context_probe.py | 6e2aab12056b1cc826a3e90cf7d857b58c6652341a8c93681554b3338b208884 |
| .github/scripts/tests/test_session_context_rendering.py | aa3e2a07feaae0525b6b3ad6047b553322092c07929621fc0122090c9f0693ca |

GitHub stores the exact Windows-applied bytes as a backup. No application source
was built or tested in the cloud runner or the assistant's scratch environment.

## Confirmed failure and scoped correction

In [baseline run 40225294651](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40225294651),
API37/16384 boot, real APK37→38 upgrade, clean APK38 install and both launches
passed. The native 2D renderer stage also passed, including 120 scroll steps,
97 distinct rows and measured HWUI p95 of 29.14692 ms.

The next stage stopped at `Session context did not render`.
The actual unmodified PNG showed user A, account-2 and month after session
restoration. Its SHA-256 was
`a4ec6accc54584156fa0f2ec270124dc8fa9d67aef4a2ca51fecd11ef1d20c97`.
The fixture contains ordinary Compose text and buttons, without decorative
Canvas components. Requiring a positive decorative draw counter was incorrect.

The correction is confined to this fixture: require its visible screen marker,
portrait workspace, observed requested font scale, zero retained 3D resources,
and a fresh decoded PNG whose dimensions match the native frame before and
after capture. Decorative draw counters remain distinct from actual HWUI frames.
The renderer-specific readiness requirement remains unchanged.

Same-user restoration, different-user isolation, previous-user eviction, explicit
logout clearing, signed-out rotation and both font-scale cases remain mandatory.
Fifteen new regression tests reject wrong/hidden/foreign screens, invalid or
conflicting metrics, retained 3D resources, incorrect font scale, mismatched PNG
dimensions and state loss during capture.

## Checks and current limits

[Windows verification run 40227132451](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40227132451):
`git diff --check` passed; the full script unittest suite ran 1030 tests in
47.168 seconds, `OK (skipped=3)`. These pre-existing platform/availability skips
are not Android runtime evidence. Full API37/4096 and /16384 reruns are in progress.

The original /4096 attempt was interrupted when the owner rebooted Windows.
Its connection-reset/install failure is not a passed test and must be rerun.

The owner installed WSL and rebooted. [Post-reboot probe 40226860291](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40226860291)
confirmed WSL3.0.3.0, all four automatic runner services running, and usable
WHPX10.0.26300. [Setup run 40227132529](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40227132529)
installed the project-only Ubuntu-24.04 distribution under the existing
NetworkService runner account at
`C:\actions-runner-2\_work\_tool\AnalystLinux\Ubuntu2404`.
Linux6.18.54.1-microsoft-standard-WSL2 and Python3.12.3 actually launched.
No disk partitioning, Windows replacement or personal distribution changes
were performed. Full Linux backend tests, including the three formerly
uncollectable POSIX modules, remain to be completed.

APK38 bytes are unchanged:
`058e307855cad135a30bccc8a4a5bafc96638fd8400ba31fda0af07f255d0bef`.
No new APK, production deployment, paid AI activation or real orders are part
of this checkpoint. Phone verification remains separate. N01–N11 are not
implemented by this test-harness correction.
