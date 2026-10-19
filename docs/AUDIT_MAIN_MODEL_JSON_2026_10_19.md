# F20 / F22 / F23 — main model JSON hardening, 19 October 2026

Base: `12b5b1fb4f536ae44ddbb01b74e1e9401ccace26`. This narrow maintenance
branch is separate from unfinished 0.11.0 / PR880. It must not be merged or
published merely because the development branch contains more functionality.

## Finding and fix

Main's ai_guarded_client decoded both the provider envelope and the inner
message using only parse_constant. That rejects literal NaN/Infinity, but not
numeric overflow such as 1e999, nonzero underflow to zero, or repeated property
names. The default decoder keeps the last repeated name. No application depth
limit was applied. A malicious or malformed model response could therefore
produce ambiguous usage/decision fields or excessive parser resource use.
This is a parser boundary finding, not evidence of a compromise or financial loss.

The shared iterative UTF-8/depth preflight caps input at 512,000 bytes and 64
open containers before json.loads. The decoder still validates JSON grammar.
Custom hooks reject duplicate names, nonfinite numeric conversion and nonzero
underflow. Guards apply to the HTTP envelope and model content. Network URL,
credentials, budget reservation/settlement and no-paid-replay policy are unchanged.

## Verification

Twelve unittest methods exercise the actual parser and _send with
httpx.MockTransport: exact size/depth boundaries, strings/escapes, malformed
JSON/UTF-8, duplicates, overflow, underflow and accepted values. The same tests
run against the development client. Locally these passed with unused
ledger/queue/config imports stubbed; this is boundary-only verification, not a
full backend or device pass. Test imports in CI use real repository dependencies.

Exact source bytes were checked against the Git blob SHA
`4dd394fdbb525cb7571d3e214f51ceeb882f7ca7` before editing. CI on this maintenance
PR must complete independently. No Android SDK/version, secrets, user data,
server, Timeweb resources or APK channel is changed by this patch.

References:
- https://docs.python.org/3/library/json.html (untrusted input and decoder hooks)
- https://www.rfc-editor.org/rfc/rfc8259#section-9 (application size/depth limits)
