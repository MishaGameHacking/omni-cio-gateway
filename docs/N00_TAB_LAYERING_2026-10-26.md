# N00 — fixed tabs above scrolling content

N00 remains open. N01–N11 are not implemented. Published APK38 is unchanged.
This change is candidate41 /0.13.3-preview, not a published release.

## Reproduced native failure in candidate40

[Focused40249497543](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40249497543)
proved that the compound target protocol works, then failed in the first
discovery/ready/font1 case at "List target not reachable: Выплаты".
The comparison and common-period assertions passed; no complete portfolio
case or complete UI matrix passed.

[Unmodified traversal observation40251310156](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40251310156)
ran on LAPTOP-NPSGA016, runner omni-cio-ci-2, source
4e4af39281f8cf15c7cc42f3837340384b6928c3, inventory
4aa72786eeb5021e012e97b1d4ad12fabb7336c1d43721d8b477f5736f159025.
It used the same candidate40 APKs and verified driver7fb9ad41….
The16KB profile ran00:51:28Z–00:54:41Z and reproduced the same assertion.

The external hook only recorded original tree reads before the assertion.
Only after that failure did it capture the screen and observe bounded reverse
scrolling. It rethrew the original error. This is diagnostic evidence, not a
changed acceptance path.

Actual first frame at0.536s:
- tab rail: [12,369][308,421];
- payout action owner profile-tabs-item-3: [160,369][247,397];
- payout text: [168,386][239,397];
- keyboard-visible=false; focused app window10.

The rail is52px high but Android reports only28px for that interior tab.
The unchanged48px rule correctly rejects it. A full horizontal scroll then
passes the target. After two reverse actions the payout owner becomes
[214,369][301,421],52px high.

The actual failure/reverse XML explains the overlap: a scrolled position
action position-row-synthetic-account-a:synthetic-share-b has native bounds
[38,397][282,455] although its workspace-content viewport starts at421.
Its24px extension overlaps the bottom of interior tabs. The visible screenshot
shows an intact fixed rail; the overlapping native target trims the
accessibility bounds. The first and last partly uncovered tabs retain larger
bounding rectangles. This is a production layering/accessibility defect,
not a reason to accept a28px action.

The27-file private diagnostic archive is557,988 bytes, SHA256
9e3e46d81f17d2bd9abe7075ffcf03401852c21d35483bb65ff9d9b5ea1cc548.
Timeweb9417611 confirmed receipt at2026-10-26T00:56:10Z. No application
code ran on Timeweb; transport cleanup succeeded.

[Evidence40251710216](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40251710216)
artifact12620967165 is178,417 bytes, SHA256
cfb6347acb51928ec62106d6e02900f6f2a0f7e910c968fb719c2e796a12794a.
The archive and all seven manifest entries were verified. Both original-failure
and reverse-visible PNGs were visually inspected; both XML files were checked.

| Evidence | SHA256 |
|---|---|
|portfolio-tabs-observations.json|b412f77f766c4510f1fc029968b18a727574f51e7a5b3eb5f61088b86d0caa56|
|portfolio-tabs-original-failure.png|f81ce428e244e0952414cede2457f7b60e69caa84fcfe24fd37eca8a0f611c93|
|portfolio-tabs-original-failure.xml|acbc6784214cc3b89adf3c2040157a93744be52241da82061962de309ae18c41|
|portfolio-tabs-reverse-visible.png|32f4041e382eb2e480cf9fa34ef794b436a8f02fb436c82ea98e0bc9ab161923|
|portfolio-tabs-reverse-visible.xml|57fb5631aa6a54227a6fcf69574e4b5c112e5accea54d2d6580875748ec31dc4|
|runtime-16384.log|e93eec12826097e82f4b74fbe4e3d19fe4be59eed5f8236339c57e3dd6255914|

## Production change and verification

SpectrumTabs places its outer layout above scrolling siblings with zIndex1.
This preserves the native tab controls, labels, selected state, hit testing,
fonts and horizontal scrolling. No test traversal,48px threshold, three-frame
stability requirement or source-contract assertion is changed.
The existing version guards advance40/0.13.2 to41/0.13.3.

[Android zIndex reference](https://developer.android.com/reference/kotlin/androidx/compose/ui/zIndex.modifier)
describes sibling drawing order. Actual emulator results, not that API
description alone, determine whether the native overlap is fixed.

[Build40252011635](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40252011635)
applies four files on the existing Windows laptop from base
b9f4ca0dcf38eadfcdb0f4705b2dd783f0b678bc.
Patch SHA256e989f382adf076217e2e5cfa56bd248aac653c1a6dcd9be6164c56a837c80c5d.
Administrative bootstrap SHA256
5de856ff862e586d8fb06e3fcbc4d34cf41ec6c0ee79335a33b696a27c42556b.
Compiled source inventory
8d309ea0b418dcf125957d72806bde5dd6fa65db716d8024e02e2ca406cfbef9.

| Windows-applied file | SHA256 |
|---|---|
|SpectrumTabs.kt|51599f1211c2630451a17b5ea1d2e4efbd3521e0cf8f39b0e23ffac8ca18c145|
|app/build.gradle.kts|38211eae835361b9a0dfefeecddc0bbc8a70095b75a7e8f4cbb7498cc9552c34|
|test_android17_live_spectrum.py|5278e2210efad5cbcde230fad68452d2815406e64f1732795ef3cd04b1988c50|
|test_spectrum_brand_identity.py|b8912a719de1bf54d5d6579d0e85b750945a9ea33cbc918f0fa5960089bb2aac|

All1066 host tests passed in43.999s (the same three platform skips);
all52 tools tests, Node checks, source/dependency audit and diff check passed.
The complete WSL backend suite passed1684 tests plus1515 subtests in130.03s,
with health/OpenAPI passed. The check stage finished01:04:21Z.

All requested Android unit-test, debug/preview lint, debug/release/preview
assemble and driver lint/assemble tasks passed. Gradle finished in10m26s.
Signature, manifest, native/ZIP alignment and APK verification all passed.
The existing certificate/key and source inventories remained unchanged.
Build finished2026-10-26T01:15:01Z; owned processes remaining after cleanup:0.

| Build output | Bytes | SHA256 |
|---|---:|---|
|preview41 /0.13.3-preview|29754870|0cad98a49c15678cc2933610a5165d90f8442ef356e86e8d1d91215374f12fda|
|debug41|63276145|925a7f8a874e70123c380c9ef2ac256c5e9be08f41c7fb53758e77f7e7dd0931|
|test-only driver|2683192|7fb9ad4121c2a1e981cacc611522941122c9fe3178e2eeb3849683200f3c7705|

The private1033-file build archive is68,773,030 bytes, SHA256
34e5fb996f8fec39e0734354fd4d9b37daa7827560a7eb1ee684c28313d37f83.
Collector receipt will be recorded after it completes.
External quality was not run by this bootstrap. Android runtime acceptance
of candidate41 remains pending; build success alone does not prove the tab fix.

## Continue in order

1. Run all14 original portfolio cases at fonts100/200 on measured16KB using
   exact candidate41 bytes; preserve the first actual failure if any.
2. Once focused acceptance passes, run the complete15-stage suite on both
   measured4096/16384 profiles, including genuine38→41 upgrade and clean install.
3. Preserve exact-head Sonar and other gates while moving obsolete hosted
   application tests to the owner's Windows/WSL environment and baseline34→38.
4. Only then close applicable N00 criteria and proceed to N01. No publication41,
   live broker orders, paid AI activation or physical-phone claim is authorized
   by these diagnostic/build results.
