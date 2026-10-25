# N00 — catalogue editor remains visible above the keyboard

N00 remains open. N01–N11 are not implemented by this repair. The active
publication is still APK38; candidate39 was not published. The next candidate
is 0.13.2-preview/40 and must pass its own complete checks.

## Observed defect

[Run40237838049](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40237838049) used the exact candidate39 and the separately rebuilt native
test driver. On Android37 with measured16384-byte and4096-byte pages it passed native2D,
session context, privacy, goals, all30 ordinary-font business cases and the
large-font assistant navigation that had previously failed.

Both profiles failed the catalogue/ready case at font scale2:
`Native editor or keyboard is not ready for input`.
The keyboard really opened, but the catalogue header and subtitle filled the
remaining application viewport. The native editor was absent from the visible
accessibility tree. This is a product layout defect, not an absent keyboard.

The actual public-window evidence reported a320×640 display, IME bounds
[0,357,320,640], a focused application window and no visible editor. The actual
failure screenshot was downloaded, its archive and file hashes verified, and
visually inspected. Evidence run40239405104 completed successfully; its archive
SHA-256 is7729734a2494f4929572516bb2d53a42c817811a1f41297e48ff22ce26c4261d.
No synthetic success frame or weakened native-input assertion was used.

## Product change

MarketCatalogueScreen now opts into the existing WorkspaceDetailPage IME
adaptation already used by LiveStrategyScreen. When the safe viewport becomes
too short for the selected font size, the heading yields its vertical space
and the back button remains available at the side. The content keeps its
composition location. Compact catalogue content also removes vertical outer
padding, while the scrollable controls and native text field remain intact.

The version advances39→40 /0.13.1→0.13.2, with the two existing version guards
updated consistently. Native editor, keyboard,48px tap geometry, stable-frame,
navigation, purchase invalidation and full-suite assertions are unchanged.

## Required verification

The exact four files are applied only on LAPTOP-NPSGA016 from base
d42f70ddf1b46b9c72a7906fb33d5b3047e830ef and expected source inventory
4c1d90f9c7afd2b00f5734c525480f049cb2e30c68ccc942394bf552518d7663.
[Build run40239983022](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40239983022) uses patch payload
e303e73aaf2b3092651b660da04ca800554b40f8d084fccebed48d889fd63556.

Before any new publication, record actual full host/backend/health/OpenAPI,
JVM/lint/build/signature/alignment results, then the complete15-stage Android
matrix on measured4096 and16384-byte pages. The upgrade baseline remains the
published APK38, not unpublished39. A focused catalogue diagnostic is separate
from full acceptance. Preserve all failed attempts and the existing signature,
owner/session/broker bindings and read-only runtime.

Build results, exact APK/source hashes, source backup commit, Android results
and archive receipts must be appended from observed reports before claiming
their respective checks passed. The physical-phone check remains separate.

## Actual Windows source application

Run40239983022 applied and read back all four exact files on the laptop.
The resulting source inventory is
`55714d036df727441f2c23a45fdcf8896711c048b6595bea9825fb09ff9533a1`.
The host suite ran1057 tests in43.372s with no failures and the same three
platform skips; tools52 and Node checks passed. The complete backend suite then passed1684 tests and1515 subtests in143.08s,
with health/OpenAPI verified and no changed Linux source files. All host/backend
checks finished at2026-10-25T22:36:37Z. Android JVM/lint/build and emulator results
are still pending and are not inferred from these checks.

The preceding complete candidate39 attempt40237838049 failed the same catalogue
case on both page sizes; its244-file private archive is10,273,516 bytes,
SHA-256`7e7119c0a9abdf7b07f9600afacad76895f644e4c6a5e3b36a7893292333730a`.
Timeweb9417611 confirmed receipt at2026-10-25T22:33:10Z; it stored the evidence
and did not execute application code.
