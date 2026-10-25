# N00 — catalogue input and search after keyboard reflow

N00 remains open. N01–N11 are not implemented by these repairs. The published
APK is still38. Candidate40 /0.13.2-preview has passed the full laptop build;
its complete Android acceptance and physical-phone check remain unverified.

## Product defect and fix

[Run40237838049](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40237838049)
used candidate39 on measured4096-byte and16384-byte Android37 pages. Both profiles
passed native2D, session context, privacy, goals and the repaired assistant
navigation. Both failed catalogue/ready at font2: the keyboard opened, but the
header occupied the remaining viewport and no native editor remained visible.

The public-window evidence showed a320×640 display, IME bounds[0,357,320,640]
and a focused application window. The downloaded failure screenshot and archive
hashes were verified. Evidence run40239405104 archive SHA-256:
`7729734a2494f4929572516bb2d53a42c817811a1f41297e48ff22ce26c4261d`.

MarketCatalogueScreen now uses the existing WorkspaceDetailPage IME adaptation.
The heading yields vertical space in a short viewport; the back button stays
available at the side and content keeps its composition location. Compact
catalogue content removes vertical outer padding. The two version guards were
updated with version40 /0.13.2. No native-input assertion was weakened.

The exact four files were applied on LAPTOP-NPSGA016 and backed up in
`7df6603279f392d75214316d1a0d8ae3db162fbe`.
Base commit:`d42f70ddf1b46b9c72a7906fb33d5b3047e830ef`.
Build source inventory:`55714d036df727441f2c23a45fdcf8896711c048b6595bea9825fb09ff9533a1`.
Product patch payload:`e303e73aaf2b3092651b660da04ca800554b40f8d084fccebed48d889fd63556`.

## Actual complete laptop build

[Run40239983022](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40239983022)
completed SUCCESS. All work ran on LAPTOP-NPSGA016; WSL provided Linux on that
same laptop. Timeweb stored the archive and did not execute application code.

- Host:1057 tests in43.372s, no failures, the same3 platform skips.
- Tools52 and Node checks passed, as did source/diff/dependency/workspace guards.
- Backend:1684 tests and1515 subtests passed in143.08s; health/OpenAPI passed.
- Android:174 JVM tests across30 suites, no failures/errors/skips; app and test
  driver lint/build passed. Gradle completed successfully in10m24s.
- Signature, manifest, APK/native alignment and unchanged source/key checks passed.
  Certificate SHA-256 remains
  `bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1`.

| Output | Bytes | SHA-256 |
|---|---:|---|
| Preview40 |29754870|a3b7d0ec4e0ac568ed15a0853635e2056898618a911c4114f7576b4c5c315aa0|
| Debug fixture40 |63276145|3e29f33beb3a6ad4dade2f56b8340d8419aeff415ffe78ed35714291ae889acf|
| Separate UI driver |2683172|ded99158cff1dd8bd7dd355d577336e0c1f742933594081af299ac2ec7e62cea|

The build finished at2026-10-25T22:47:15Z and its worker had zero remaining
owned processes. The1031-file archive is68,755,175 bytes, SHA-256
`685ed5adf8bcba7f215fe20f735df4e80e007c5cb778b9501d101a6cd359df75`.
Timeweb9417611 confirmed receipt at22:48:13Z under
`/var/lib/analyst-ai-build/incoming/windows-development-40239983022-1/`.

## Actual keyboard input and subsequent search failure

[Focused run40241897573](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40241897573)
installed the exact candidate40. At font2, the native editor accepted
`new1`, retained focus and exposed the real caret at4/4 while the IME was
visible. The actual screenshot was downloaded and visually inspected.

The case then FAILED with `List target not reachable: Найти`.
It did not complete the purchase flow or replace the full15-stage acceptance.
The17-file private diagnostic archive is316,156 bytes, SHA-256
`e7c5641c3ed62f99711941519bebd0474c8ced9f3b0519b5912ea2d9f4d4d927`.
The separate reviewable screenshot artifact from run40242307120 has SHA-256
`00d86fadab85dbd5facbdd20a263ee586123df74337225412d719d594d383f15`.

[Geometry run40242538843](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40242538843)
preserved that failure and observed the public native tree. Immediately before
the forward search, neither the query field nor Find was visible. Forward
scrolling could not reach either. Two reverse scrolls found the enabled,
clickable Find owner and its query field in the same viewport:

| Element | Actual bounds |
|---|---|
| List viewport |[56,141][320,616]|
| Query field |[76,327][300,440]|
| Find owner and valid tap rectangle |[76,440][300,507]|

After the keyboard closes and the layout widens, the edited form can be above
the current scroll position. The test now returns toward that form before its
ordinary native tap. The48px margin, three settled fresh frames, actual tap,
window identity, price guard and result invalidation remain unchanged.

## Windows test repair and continuation

[Run40243041873](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40243041873)
applied only catalogue_ui_probe.py and test_catalogue_dialog_transition.py on
the laptop. Its base is7df6603279f392d75214316d1a0d8ae3db162fbe.
New test-source inventory:
`d79d8cfc31d74560eda38b8aeae8cf58aa5e389de8366d54b66886b47ad54cbc`.
Two-file payload:
`818a7469edbc7ba23069e64296dde11368827bbe16deef0537bc9653d8373013`.

All1060 host tests passed in44.044s with the same3 skips and git diff --check.
The new regression executes the complete existing catalogue traversal after
a simulated IME reflow. It proves the former forward-only search fails, and
that missing/disabled Find still prevents the purchase flow. Simulated frames
are not Android runtime evidence.

## Actual focused results and visual evidence

Run40243041873 completed all four focused catalogue cases: ready and partial
at fonts2 and1 on measured16384-byte Android37. Each checked search outside
current holdings, rejection of a missing price, the typed purchase-check
request, displayed constraints, invalidation after an edited input and absence
of a broker order. These are actual Android observations, separate from host
fixtures. Twelve native-input records and screenshots show query new1,
price95 and edited price950, with the native editor focused and caret preserved.

The workflow deliberately finished FAILURE after those four cases with
`Diagnostic only: full UI suite was deliberately not claimed`.
Its inherited runtime step label says full UI, but the external hook ran only
the focused cases. The report has diagnostic_only=true and release_gate_pass=false.
Neither the four case passes nor the inherited step label is full acceptance.

The49-file private archive is1,883,136 bytes, SHA-256
`b894f93af42b81898f2a266fd6d5f7d309ac434d037445d66f5633f91ba248dd`.
Timeweb9417611 confirmed receipt at2026-10-25T23:11:12Z under
`/var/lib/analyst-ai-build/incoming/windows-development-40243041873-1/`.

[Evidence run40243798073](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40243798073)
provided artifact12617821664,906,266 bytes, SHA-256
`17370b74d46c2424c8d522916ff665a604f9421ad55086b6f10b896664f32a88`.
The downloaded archive and19 manifest file hashes were verified.
Four actual input images were visually inspected: font2 query/price95/price950
and font1 price95. The value and caret remain above the keyboard. The synthetic
debug disclosure rail makes these diagnostic windows narrower than production;
do not describe its45% side rail as normal production geometry.

## Complete matrix: actual 16KB failure, 4KB still running

[Full run40243609014](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40243609014)
checks the exact backed-up source
`2347eb54b7270d947587adb0f3cc09a5e0de1572`
with inventory
`d79d8cfc31d74560eda38b8aeae8cf58aa5e389de8366d54b66886b47ad54cbc`.
It uses the unchanged candidate40/debug/driver bytes listed above from
run40239983022. The compiled application source inventory55714d… differs
from this runtime checkout only by the two tested harness files and documents;
do not claim a second complete application build after that harness-only repair.

This run has no diagnostic hook. All15 UI stages, upgrade from the actual
published APK38 and clean installation are required on16384-byte and4096-byte
profiles. The16KB profile finished FAILED at2026-10-25T23:28:34Z.
Measured page size, published38 clean installation,38→40 upgrade, launch,
candidate40 clean installation and debug fixture installation passed. Native2D,
session context, privacy and goals passed. All30 normal-font business cases
passed; at font2, catalogue ready and empty passed, then partial failed:
`List target not reachable: Покупка не прошла проверку`.

The actual failure image shows the lower part of the purchase-check dialog,
including the saved synthetic-purchase-check record and Close. This proves
a response rendered; it does not establish the expected heading's geometry.
Image SHA-256:
`1e99c8506ad63cddaed2d62f17ddd55157049de5800a82a868ac1e0cfe4e5bf8`.
[Evidence run40245031227](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40245031227)
artifact12618042978 is426,069 bytes, archive SHA-256
`4414f31e484867d25e9ea30b9125df975b9df587a0d8031cdc60d53d5e0135b9`.
The downloaded archive and12 manifest file hashes were verified and the failure
PNG was visually inspected. The runtime log SHA-256 is
`f2c09b9fb68bf3f2a086dea4f974b91dbf2c05d0a5e8ecde1138e3ecda097227`.

The4KB profile continues independently. At this checkpoint it passed native2D,
session context, privacy and goals and reached catalogue at the normal font.

[Diagnostic run40245350516](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40245350516)
is queued behind the same canonical emulator lease. It uses the exact unchanged
source and APKs. An external diagnostic hook observes the original result
traversal; only after a real assertion failure does it inspect reverse scrolling
and rethrow the original failure. It cannot claim a complete UI PASS. The
response-insertion/scroll timing explanation is a hypothesis until these actual
frames establish it. No new repair has been applied at this checkpoint.

No complete Android PASS, physical-phone result or publication40 is claimed.
The full build also explicitly records external_quality_gate as not_run_by_this_bootstrap;
the tested source2347eb5 has no automatic check runs. Before a release/merge,
retain the exact-head external quality gate and adapt the existing PR workflows
to the owner's Windows/WSL execution rule and published38 upgrade baseline;
do not launch their legacy cloud test/runtime paths or remove any quality gate.

Preserve the signature, owner/session/broker bindings, database and read-only
runtime. Do not enable paid AI or real-money execution. Continue N01–N11 in
order after N00 acceptance; the plan remains incomplete.
