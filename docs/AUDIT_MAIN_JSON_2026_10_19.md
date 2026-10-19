# F15/F20/F23 — bounded model JSON backport for main

Audited main: `12b5b1fb4f536ae44ddbb01b74e1e9401ccace26`.
Reference development implementation: `0c7ef3fbd75f6019aa50ad3ea4c8d9631627c79f`.

The main branch rejected literal NaN/Infinity but still accepted exponent overflow,
nonzero underflow and duplicate object keys. The same problem existed in the
response envelope (including usage) and the model's content string. Container
depth also lacked an application budget. This is a data-integrity/parser-budget
finding, not evidence of exploitation, remote code execution or a live trade.

Backport only the existing development parser guards and its unchanged pure
`model_json_limits.py`. No routing, billing, auth, Android or deployment redesign.
Both decoding sites use one helper. Numeric errors are non-retryable; current
settlement and uncertain-reservation behavior remains unchanged.

15 new regression methods exercise content and HTTP-envelope decoding through
MockTransport, without paid requests. The source was checked against its Git blob
SHA. Locally the original code failed 15 assertions/subcases; all 15 methods passed
after the patch in an isolated module runner omitting unrelated DB/queue imports.
This local isolation is not full backend integration or an emulator pass. The
committed tests import the normal backend package in CI. Exact-commit CI and Sonar
must still pass before merging. main, Timeweb and the APK channel are not deployed
by this change.

No claim is made that this focused backport completes the entire 0.11.0 audit or
that the historical status of main certifies the new commit.

Primary reference: https://docs.python.org/3.14/library/json.html — parse_constant
only handles NaN/Infinity literals; parse_float and object_pairs_hook are required
for the additional numeric and duplicate-field checks.
