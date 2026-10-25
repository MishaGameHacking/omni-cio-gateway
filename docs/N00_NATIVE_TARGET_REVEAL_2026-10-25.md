# N00 — precise scrolling of a partially visible native target

The candidate remains 0.13.1-preview/39, unpublished. Published APK38 and the
read-only production backend remain unchanged. N00 is still open; N01–N11
are not implemented by these test-harness repairs.

## Actual Android observations

[Run40235053258](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40235053258)
verified genuine38→39 upgrades and clean installs on Android37 with measured
16384-byte and4096-byte kernel pages. Both passed native-2d-renderer,
session-context, balance-privacy and goal-workflow. Privacy was tested at font
scales1 and2, including reveal, release, cancel, isolation and no currency cycling.
The goal scenario retained actual native editing, rotation, lost-response recovery,
idempotency and deletion.

Both profiles then FAILED at assistant/ready inside the business stage:
`List target not reachable: assistant-impact-position`.
This failure is not a full UI PASS. The113-file private runtime archive has
SHA-256 `7d4991c8bc0abc25be92585751dadd70b717d8c6b6518c99df0f265d3d6fb386`
and was received on Timeweb9417611. No application tests ran on Timeweb.

The fixture contains the exact synthetic instrument and account. The screenshot
showed that the test had reached the end of the assistant history.
[Focused run40236775156](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40236775156)
recorded the real public node geometry:

| Observation | Button bounds | List viewport | Available button height |
|---|---|---|---|
| Forward search | [38,346][282,394] | [0,171][320,393] | 47px |
| Next forward frame | [38,164][282,216] | [0,171][320,393] | 45px |
| Reverse diagnostic | [38,262][282,314] | [0,171][320,393] | 52px |

Both forward fragments were smaller than the existing48px tap requirement.
The button was present, visible, enabled and clickable; full-page semantic
scrolling passed its usable position. The independent reverse diagnostic found
it fully inside the viewport. It deliberately retained the original failing
result and did not replace the full-suite gate.

An earlier diagnostic run40236337864 incorrectly replaced the bound frame-reader
method and was rejected by the owned-session check before forward scrolling.
It is not evidence for the forward-scroll cause; the corrected diagnostic above
preserves the authenticated reader and observes frames through the probe method.

## Repair and retained requirements

The test-only driver now accepts one bounded public ACTION_SHOW_ON_SCREEN
request for an exact visible enabled descendant of an exact whitelisted app list.
It re-reads the active application root, checks the focused app window, rejects
foreign/ambiguous/off-list targets and bounds tree traversal and target-id input.
It never clicks, injects application state or invokes an arbitrary action.

The Python reveal loop uses this minimal native scroll only when a requested
resource intersects its list but does not yet have a valid tap rectangle.
An action acknowledgement is not a ready frame: the unchanged48px clipping rule,
three equal fresh rectangles, actual tap and exact resulting navigation remain
required. A refused action, malformed acknowledgement, deadline or unchanged
partial geometry still fails.

Primary API reference:
https://developer.android.com/reference/android/view/accessibility/AccessibilityNodeInfo.AccessibilityAction#ACTION_SHOW_ON_SCREEN

The handler's actual result is checked even when the action is not enumerated
in node metadata. Compose's public accessibility implementation handles the
standard action independently of that list; acceptance still requires fresh
observed geometry on the emulator.

## Windows provenance and validation

All11 files were applied and read back on LAPTOP-NPSGA016 in
`C:\actions-runner-2\_work\omni-cio-gateway\omni-cio-gateway\windows-development-40237838049-1`.
Base commit: `6746b769e8f0eb8d908c67f6455dcf3667ed9f0b`.
Base code inventory: `b9e41cf2f6c13115be097759b842e1669ee2faffb9c9c7955dca0890bc99e109`.
New code inventory: `4c1d90f9c7afd2b00f5734c525480f049cb2e30c68ccc942394bf552518d7663`.
Patch transport: `eed14df149c91f345ba318bef7efe67ad93b65374bbcafaa0f676012d2048a55`.

[Run40237838049](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40237838049)
passed all1057 host tests in43.987s (the same3 existing platform skips),
git diff --check and the test-only Android driver's lintDebug/assembleDebug.
The check finished at 2026-10-25T21:58:40.130841+00:00.
The driver is2,683,172 bytes, SHA-256
`ded99158cff1dd8bd7dd355d577336e0c1f742933594081af299ac2ec7e62cea`.
Preview and debug-fixture application APKs retain their exact previous hashes;
only the separate test-lab driver was rebuilt.

Run40237554869 also passed host tests and driver compilation/lint, but its
administrative wrapper accidentally reused the driver path when writing the
host status receipt. The APK hash check rejected it before either emulator ran.
That attempt is FAILED and its driver file is unusable. The wrapper now uses
an independent status path; run40237838049 rebuilt and verifies the actual APK.

The host regression reproduces the actual47px/45px fragments and verifies that
neither can become a tap merely from an acknowledgement. It covers missing,
foreign, disabled and ambiguous targets, stale/wrong/truncated responses, bounds,
sequence exhaustion, deadlines and stable geometry.
The real Java driver guard is compiled and executed against observation doubles
for28 positive/negative cases; those doubles do not simulate successful scrolling.
Real Android is the independent acceptance test for native behavior.

The existing oversized-composer test now supplies the minimal-reveal primitive
instead of only its former page-scroll primitive. It still checks that the same
editor is actually tapped inside its own viewport and that chat history is unchanged.
The first repair run40237347692 remains FAILED because that model lacked the new
primitive. No Android acceptance was claimed from that attempt.

## Actual completion and continuation

Run40237838049 completed with FAILURE. Both measured page sizes passed the
four preceding stages and the previously failing assistant navigation, including
font200. Both then failed catalogue/ready at font2 because the native editor
disappeared above the visible keyboard. This is an independently observed product
layout defect. The original native-input assertion remains unchanged.

The244-file private archive is10,273,516 bytes, SHA-256
`7e7119c0a9abdf7b07f9600afacad76895f644e4c6a5e3b36a7893292333730a`.
Timeweb9417611 confirmed receipt at2026-10-25T22:33:10Z.
The rebuilt test driver and all failed evidence are retained.

[Candidate40 catalogue repair and subsequent checks](N00_CATALOGUE_IME_2026-10-25.md)
continue N00. The full15-stage matrix remains required on both page sizes.
Do not claim release acceptance or physical-phone verification from this repair.
