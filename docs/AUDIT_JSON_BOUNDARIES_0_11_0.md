# F20 / F22 / F23 — bounded model JSON audit, 19 October 2026

## Verified baseline and finding

Development baseline: `7fb2196ee41c64b09bcc4b7223d97a01fd16ef29`.
Main baseline: `12b5b1fb4f536ae44ddbb01b74e1e9401ccace26`.
Backend job 118115902200 recorded 1318 passed, 2 skipped, 966 successful
subtests and two failing subtests in `ModelJsonAuditTests`. Both envelope and
content accepted the 10,000-array input instead of producing a controlled error.
The existing defence relied on the decoder throwing RecursionError. That is not
an application depth limit and varies with the interpreter/decoder. Exact-head
Sonar reported zero annotations; that did not establish runtime correctness.

## Change

Before json.loads, both model boundaries now enforce a shared 512,000-byte UTF-8
budget and maximum 64 simultaneously open containers. Strings and escaped quotes
are scanned separately; braces inside strings do not count. The iterative scan
is bounded by input size and uses at most 65 stack entries. JSON grammar remains
json.loads' responsibility. The existing duplicate-key, nonfinite and nonzero
underflow checks, response accounting, route binding and paid-retry prohibitions
are unchanged. A rejected reply is never an authorization to repeat a paid call.

These are application limits, not a claim that JSON itself forbids deeper data.
The public contracts permit parser size/depth limits:
- https://www.rfc-editor.org/rfc/rfc8259#section-9
- https://docs.python.org/3/library/json.html

## Verification and limitations

Twelve new unittest methods cover exact depth/byte boundaries, arrays/objects,
UTF-8 byte size, strings with escaped structural characters, malformed input,
duplicate names, nonfinite/underflow numbers, and the real httpx transport method
with MockTransport. A decoder spy verifies rejection occurs before json.loads;
it does not rely on Python's recursion limit. No sys.setrecursionlimit changes,
quality exclusions, skipped assertions or paid model requests were introduced.

Local run: 12 methods passed on a boundary-only harness. The exact client source
blob was checked against GitHub SHA f0e270023e87472741c339bfbbd2ad8d9c9fe7bd before
editing. Unused ledger/queue/config imports were placeholders locally; no database
or full backend integration pass is claimed. CI runs the tests with the actual
repository dependencies. Final-head Backend, Android and Sonar still must run.

Main additionally lacks duplicate-name, overflow and underflow checks. A narrow
backport is required rather than merging the entire unfinished 0.11.0 branch.
This pass is not a complete review of every repository file, Android 17 migration,
portfolio strategy validation or proof of absence of all security issues.
No main merge, Timeweb deployment or APK publication is authorized by this audit.
