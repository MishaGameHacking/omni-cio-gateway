# F20 / F22 / F23 — bounded HTTP response audit, 19 October 2026

This is a focused, reproduced security/data-integrity repair within the wider audit, not certification of the whole repository, a working server, or an emulator-tested APK.

## Reviewed baseline and branch separation

Development baseline: `d27771cf22c13c5d195653216a33d93d3e5087d2` (PR #880). Main baseline: `12b5b1fb4f536ae44ddbb01b74e1e9401ccace26`. The same vulnerable `iter_bytes()` response loop exists in both. The compatible main repair extends the existing PR #881 (`audit/main-ai-accounting-20261019`, prior head `9bc993b440fa1c26558d02cc81e3f1874177f065`); it does not import the unfinished 0.11.0 redesign or merge anything into main.

At the initial live read, development's Sonar check on d27771c reported success, zero new/accepted issues and zero annotations. The old screenshot warning about `require_clean_sonar.test.cjs` was already repaired: Node's real `test()` runner is present. That earlier repair is not attributed to this change. Backend CI had passed on the baseline; these historical results do not certify the new commit.

## Reproduced findings

1. **Size checking after automatic decompression.** `_send` used HTTPX `iter_bytes()`, then extended a buffer, then checked its length. HTTPX decodes content before yielding it. A small gzip response can therefore allocate much more than the 512,000-byte application limit before rejection. This is a resource-exhaustion exposure to a malicious/corrupt upstream response, not evidence of an attack or credential compromise.
2. **Truncated gzip accepted.** A valid JSON envelope whose gzip trailer was removed was accepted by the old path. The transport must prove stream completion and CRC validation before JSON/usage is trusted.
3. **Later gzip members silently ignored.** Two gzip members containing separate JSON documents were interpreted as just the first document by the old path. A split valid document must be decoded completely; hidden trailing documents must fail JSON parsing.

A controlled Python 3.13.5 / HTTPX 0.28.1 reproduction compressed 32 MiB of repeated bytes into 32,635 bytes. `tracemalloc` observed peaks of 81,144,473 bytes for the old decode-and-check loop versus 1,098,424 bytes for the bounded collector before rejection. These are local Python-allocation measurements with preconstructed input, not server RSS, universal memory bounds or phone benchmarks.

## Repair architecture

`backend/bounded_ai_response.py` owns transport decoding; `GuardedAIClient._send` owns status handling, connection scope and JSON handoff. Both branches retain their existing JSON validation and accounting implementations.

- Negotiate only `Accept-Encoding: gzip, identity`; reject unsolicited/stacked encodings rather than instantiate an unbounded decoder. No automatic retry with different headers.
- Read `iter_raw()` and enforce separate wire and decoded limits, both 512,000 bytes at this call site. Content-Length is not accepted as proof of actual size.
- Call `decompress(..., remaining_budget + 1)` and check before appending. Do not use unbounded `flush()`; its length argument is an initial buffer size, not a cap.
- Require gzip EOF/checksum. Process concatenated members as one document, with an explicit 16-member application limit including empty members. Apply the existing strict JSON parser to the entire decoded document.
- Start the response deadline before dispatch; check at entry, every raw chunk and EOF, including header-only chunks producing no decoded output. The synchronous deadline does not preempt a blocking read: the existing HTTPX connect/read timeouts remain applicable. No hard 60-second wall-clock guarantee is claimed.
- Preserve connection cleanup and non-retryable fixed diagnostic codes. No response bodies, credentials, portfolio data, paid fallback, ledger refunds or order submission are added.
- Pre-read identity responses remain supported for explicit callers/MockTransport; predecoded gzip cannot claim bounded decompression and is rejected. Production HTTPX stream responses follow the raw path.

No `GuardedAIClient` method other than `_send` is changed by this repair. Its import list is extended. Model selection, monetary reservations, unknown-paid-outcome handling, queue claims, cancellation and permissions are preserved.

## Verification and limits

Added 40 unittest methods: 28 collector tests and 12 real `_send` tests using HTTPX MockTransport with SyncByteStream. Cases include exact size boundaries, split input, expansion bombs, truncated trailers, CRC errors, concatenated/empty members, extra JSON, unadvertised encodings, redirects, closure, read failures, raw-chunk deadlines and 64 independent responses across four threads.

Before the change the combined local suite produced five failures and one error; after the change all 40 methods passed for both development and the main-compatible source. Source copies were checked against Git blob hashes. Locally, unrelated application/queue/budget imports were omitted in an AST loader while all tested functions, classes, HTTPX transport and decoder/JSON implementations remained real. The committed tests use ordinary package imports, not that loader. Complete package integration and final-head CI/Sonar must still pass separately.

Normal full-checkout commands:

```sh
python -m unittest backend.tests.test_bounded_ai_response backend.tests.test_ai_response_streaming -v
python -m compileall -q backend/bounded_ai_response.py backend/ai_guarded_client.py
```

The audit also read owner binding, Telegram token/nonce validation, queue ownership, joint allocation, scenario arithmetic and the Sonar gate. That review does not prove absence of every vulnerability. Android runtime failures, the requested Android 17 migration, single-owner rollout and complete recommendation workflow remain separate work. No Timeweb changes, resource purchases, live AI calls, broker operations, APK release or deployment occur in this change.

## Primary contracts

- HTTPX raw streaming and automatic content decoding: https://www.python-httpx.org/quickstart/#streaming-responses
- Python zlib bounded decompression, EOF and unused data: https://docs.python.org/3/library/zlib.html
- Sonar quality gates are conditions, not an exhaustive security proof: https://docs.sonarsource.com/sonarqube-cloud/standards/managing-quality-gates/introduction-to-quality-gates
