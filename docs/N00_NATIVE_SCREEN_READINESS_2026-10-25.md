# N00 — native text screens and candidate39 runtime

Status at 2026-10-25 21:23 UTC: N00 remains in progress; N01–N11 are not implemented.
Published APK38 and production remain unchanged. Candidate39 is built, not released.

## Completed build and system-policy verification

Windows run [40232404397](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40232404397)
passed the full backend suite in the laptop-owned Ubuntu WSL distribution,
health/OpenAPI, host/tools/Node checks, JVM tests, lint, debug/preview/release builds,
native alignment, APK manifest and cryptographic signature verification.
The complete build finished at 2026-10-25T21:02:46.224792Z.

Candidate: 0.13.1-preview /39, package ru.omnicio.app.debug, 29,754,866 bytes.
APK SHA-256:
`6bb6735f83620962a3170f7f749d60b6b7515e4c213f504d7d2d97b444e6df03`.
Certificate SHA-256:
`bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1`.
Debug fixture APK:
`42b90f2ab4b5ba2fbb0aeb612b0e3380aae632567bf75e0ba473c8ec2c763c7d`.
The private build/source archive has SHA-256
`def2be58fc394d64e87894cc105b982d62af21861f8772dbb0ab529fcc8a0d61`;
its verified receipt is on current Timeweb9417611. No builds/tests ran there.

[Runtime run40233680433](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40233680433)
measured both actual page sizes (16384 and4096), installed the genuine published
APK38, upgraded38→39 and performed clean candidate/debug-fixture installation.
Both runs passed native artwork/system animation recovery and session-context
stages, then FAILED at balance-privacy readiness. This is not full UI acceptance.
The runtime archive (72 files) has SHA-256
`d29d952c59ed4f9b03d3e718dca79ca86373f7057ead212983ea41e1b895f8f0`
and was returned to Timeweb storage successfully.

## Proven test-harness mismatch and correction

The privacy fixture contains two native text amounts and ordinary Compose layout;
it has no decorative Canvas. The actual captured failure screen shows both masked
amounts and the native instructions. The existing readiness helper required a
positive decorative draw counter, so it rejected this correctly rendered plain
screen. Force-stopped launch and the actual fixture marker had already passed.

A separate native-screen readiness helper now requires the exact visible fixture,
visible app content, actual portrait display geometry, actual requested font scale,
the native renderer and zero retained 3D resources. It does not require a decorative
draw operation. Privacy and goal native-screen checks use that helper.
The artwork helper still requires positive draw evidence and remains unchanged.
Hold, release, cancellation, isolation of the other amount, currency taps, goal
editing, rotation and recovery assertions remain in the full Android suite.

Ten adversarial host tests cover missing/wrong/hidden screen identity, wrong
geometry/font/orientation, errors, retained 3D resources, conflicting observations
and invalid inputs. A plain frame is explicitly still rejected as artwork evidence.
The focused goal-window race tests now mock the new readiness boundary; their
real window-transition assertions and negative reproduction are preserved.

## Windows source provenance

All five files were actually applied on LAPTOP-NPSGA016, not on Timeweb:
`C:\actions-runner-2\_work\omni-cio-gateway\omni-cio-gateway\windows-development-40235053258-1`.

Base Git commit: `7270d4095880e4cac8545b3e6064f85860250050`.
Base code inventory:
`259a45f022c53cdf1ef7cca4e8631bdfa2b3f9a1ddf04d8800b5f1426905b03e`.
Final code inventory:
`b9e41cf2f6c13115be097759b842e1669ee2faffb9c9c7955dca0890bc99e109`.
Reviewed patch transport:
`50ce4ce0280aafe950ae9685667d31b2f42896969f10353606b20dbe821b2809`.

[Run40235053258](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40235053258)
passed all1040 host tests (existing3 skips) and git diff --check, finishing
2026-10-25T21:22:47.528807Z. The earlier run40234849690 failed six subcases
because the focused goal-window simulation still mocked the old helper; that
attempt remains failed and is not a runtime receipt.
Only Python test-harness files changed; the verified preview/debug/driver APK
bytes were copied with exact size/hash checks and were not rebuilt or relabelled.

## Next gate

Run40235053258 is executing the entire Android37 installation/upgrade/UI matrix,
16KB followed by4KB, including all15 stages. Inspect actual receipts before
marking N00 complete or publishing39. Do not skip later stages after a failure.
Physical-phone installation remains a separate unverified owner-side check.
Continue N01 only after the N00 implementation/check gate is closed.
The remainder of N01–N11, including the required shadow observation interval,
cannot be marked implemented by this repair.
