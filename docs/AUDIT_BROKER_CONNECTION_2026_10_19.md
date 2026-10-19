# F01 / F02 / F20 / F22 / F23 — broker connection concurrency audit

19 October 2026. Focused security/integrity repair within the continuing audit,
not certification of the whole repository, dependencies or a released APK.

## Baselines and reproduced effects

Development: `f4b3dc9667a50cef64abfa1f8e47e080d503f1d0`, PR #880.
Main: `12b5b1fb4f536ae44ddbb01b74e1e9401ccace26`; its isolated repair
continues PR #881 from `f7e873f38a8e1cec65b75c16b0c807d0b304e7df`.
Neither PR is merged; no Timeweb, broker trade, model call or release is involved.

In both app.py variants, `save_tinvest_token` authenticated once, waited for the
read-only GetAccounts response, and then unconditionally updated the user's
stored broker credential. A successful delayed response could:

- resurrect a connection after DELETE /tinvest/token had returned disconnected,
  including a first connection where DELETE changed NULL to NULL;
- overwrite a newer successfully saved replacement;
- save after its own authorizing session had been revoked or expired, even when
  a different session for that user remained valid;
- return connected=true after deletion of the user, despite updating no row.

These are reproduced ordering defects, not evidence that anybody exploited
production or obtained somebody else's broker token. An attacker would still
need the already accepted Analyst session; no authentication bypass is alleged.
Disconnection is local credential removal, not revocation at the broker itself.
A broker request already dispatched before disconnection cannot be recalled.

The old token endpoint also lacked a bounded printable-ASCII preflight before
building a broker Authorization header. Invalid values now receive a fixed 400
without creating the upstream client. The 4096-character cap is an application
limit, not a claim about the broker's token specification or a whole HTTP ingress
body/memory limit. Existing outer-whitespace trimming is retained.

## Architecture

`backend/broker_connections.py` owns the credential mutation boundary. app.py
retains HTTP parsing, pinned TLS, the existing read-only upstream call/status
mapping and Fernet encryption. No network operation runs under a write lock.

1. Capture a ticket bound to user, Telegram subject, exact live session hash and
   connection version immediately before validation.
2. After the external wait, acquire BEGIN IMMEDIATE, re-read the same session and
   version, and publish the encrypted credential only if both survived. Read the
   clock after acquiring the write reservation, not before a possible lock wait.
3. Disconnect rechecks its own live session in the transaction and invalidates
   every older ticket even when the credential was already NULL.

A sidecar `broker_connection_versions` table is initialized transactionally.
Persisted INSERT / UPDATE OF tinvest_token_encrypted / DELETE triggers version
all existing credential-write paths, including identical-value updates. A random
256-bit marker is internal version identity, NOT an authentication secret; an
independently valid session is required. This avoids ciphertext-only and
second-resolution updated_at ABA checks without changing existing users columns
or storing plaintext tokens. Rollback also restores the version. Profile/name
updates and another user's changes do not invalidate an unrelated ticket.

Missing versions fail closed (503), revoked/expired/missing authorizing sessions
return 401, and stale connection tickets return 409. Diagnostics do not include
credentials or upstream bodies. There is no automatic retry or reconnect.
Existing Android handling treats 409 as a non-retryable failure, not success;
its generic token message is retained in this backend-only change.

The owner-only entry point reuses legacy initialization and discovers owned
tables by user_id, so the new sidecar is included in its ownership checks.
Full owner-factory integration still needs the full CI checkout. No existing
owner binding, five-user legacy policy, scheduler, release gate or encryption key
is changed by this patch.

## Tests and evidence scope

Added **39 unittest methods**:

- 25 real file-SQLite unit methods: rollback, idempotent/concurrent migration,
  NULL/identical-ciphertext ABA, per-user isolation, ticket replay, missing user,
  session revocation/expiry, user recreation, validation and safe diagnostics;
  four simultaneous saves have exactly one winner. A synchronized writer test
  proves expiry is checked after waiting for the SQLite write reservation.
- 14 HTTP regression methods: actual FastAPI handlers, persistent sessions,
  real SQLite and Fernet, with deterministic callbacks at the upstream wait.
  Compatibility includes normal save/disconnect, profile edits, authentication,
  broker rejection, timeout/no retry and absence of a network-time write lock.
  TLS setup is fixture-only; this suite does not attest a production connection.

Local app source bytes were verified against Git blob hashes:
`d10bdd1ad620e634f08ab6d360f475aee15a240d` (development) and
`db3eebfdd487f492bc52d562cf642f39bec55937` (main-compatible).
The local environment cannot obtain a full private checkout. Consequently,
HTTP testing used an AST source-slice loader: selected route/auth/schema functions
and their decorators execute unchanged; unrelated release-gate, device-schema
and scheduler/route imports are fixtures. Unit service tests use normal imports.
The committed HTTP tests use normal backend.app imports, not that local loader.

Before the repair, seven HTTP race scenarios returned 200 where rejection was
required. The invalid-header preflight scenario also failed. After the repair,
all 14 HTTP methods and all 25 SQLite methods pass locally for both app variants;
compileall passes. This does not replace full package integration on CI's pinned
Python/dependency versions. Exact new-head CI and Sonar results must be read after
publication; results from the baseline must not be relabelled as new-head success.

Full-checkout commands:

```sh
python -m unittest backend.tests.test_broker_connection_versions backend.tests.test_tinvest_connection_races -v
python -m pytest backend/tests -q
python -m compileall -q backend
```

## Independent Android blocker and remaining work

Android CI run `39290152464`, attempt 2, job `118197223039` built/linted all
variants successfully. Its API35/16KB installation/UI validation subsequently
failed after the BUDGET sheet. Crash buffer reports SIGSEGV/SEGV_ACCERR in
FEngine::loop and libfilament-jni.so, beginning 17:27:01; subsequent uiautomator
calls abort. This is a real native crash, not the earlier setup-java download
failure. The exact native ownership/lifetime cause is NOT established by this
broker repair; do not weaken the pixel/runtime gates to hide it.

Retained evidence commit: `bd5b7e0f24fd64e99e79010dcfbe4c0d2635a60dc`;
branch path `ui-evidence/actions/run-39290152464-attempt-2` (78 files, 48 PNGs
reported by the retention step). API36 was not reached; API37 migration and the
physical Xiaomi remain unverified. No verified test APK was retained by this run.

The old screenshot's node-test warning was already repaired before this baseline.
The broader auth handoff, all dependencies, all authorization boundaries and
complete investment recommendation pipeline remain separate audit work. These
39 tests do not close the complete F01/F02/F20/F22/F23 acceptance criteria.

## Primary technical contracts

- SQLite transactions and BEGIN IMMEDIATE: https://sqlite.org/lang_transaction.html
- SQLite triggers: https://sqlite.org/lang_createtrigger.html
- SQLite version marker source: https://sqlite.org/lang_corefunc.html#randomblob
- Authorization checks and regression tests: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
