# Local companion: encoding, deadline and cancellation hardening

Base: 0ef27f65a034b4758470ea584c33b3453075a71d. Candidate only; feature remains
off by default and the protected installed service/owner DB are not modified.

## Previous exact revision acceptance

Full Lenovo Linux run 41245233293, job124667169785, succeeded at
2026-10-31T21:54 UTC: 2892 passed, 1636 subtests, 1 dependency warning.
All eight Linux steps and health/OpenAPI passed, changed_sources=[].
Artifact13058634263; 495 Python sources passed compilation audit. This evidence
belongs to0ef27f65, not automatically to the hardening changes below.

## Fixed cases

- Invalid Unicode scalars (unpaired UTF-16 surrogates decoded from JSON), NUL and
  other C0 controls except tab/CR/LF are rejected with a fixed422 before inserting
  a turn or invoking a model. Valid Russian/combining/emoji/ZWJ text is preserved,
  not normalized/repaired. Model output and decrypted history are validated too.
  Bad stored text can be cleared rather than poisoning the next model context.
- Session tokens must be ASCII; invalid identifiers cannot raise Unicode/SQLite
  encoding errors. Cancellation identifiers are bounded32-character hex IDs.
- Context pruning measures the EXACT serialized transport request including the
  system message and double JSON escaping, capped at40000bytes. Newest complete
  pairs are kept, current question is never silently truncated. This byte budget
  does not replace the worker's independent actual-token/context checks.
- Cancellation, logout, expiry, history clear or feature disable during readiness
  is rechecked just before sending. Post-answer atomic checks remain. There is
  still a possible cancellation after dispatch: no false claim of instantaneous
  native-generation interruption or voice barge-in is made.
- Local HTTP uses one monotonic240-second deadline across connect/send, headers
  and response-body reads, including byte-trickling peers. Python SocketIO
  makefile reads use the deadline socket's recv_into. No background timeout thread,
  replay, global socket settings or provider fallback is introduced.
- Both HTTPResponse and HTTPConnection close on all exit paths, including rejected
  hashes and oversized bodies after HTTP/1.0 socket detachment. Tokens and request
  encoding are checked before opening a socket.
- A timed-out companion attempt becomes failed with a fixed504; it is not retried.
  Its persisted companion slot is retained until the original300-second deadline,
  including after a new API instance or history clear, to avoid immediately piling
  work onto possibly still-running native inference. The server's existing
  SIGALRM native watchdog is unchanged; socket timeout is not proof of GPU/CPU stop.
  This slot controls companion calls, not all portfolio/research callers.

## Verification to perform on the existing Lenovo runner

Run old+new companion tests, existing agent/accounting/queue regressions, local
transport unit tests, and real private Unix HTTP peers in the complete Linux gate.
Real-socket tests use only a short-lived owned /tmp directory and one peer thread;
no model weights, protected installation, owner records or external API is used.
Windows intentionally skips the three Unix-peer cases; they must execute in WSL.
The complete suite is required because local_ai_transport is shared by other lanes.

Production integration and actual installed-model acceptance are still pending the
existing protected-runtime permission boundary. No ACL/password/service changes,
paid inference, broker orders, microphone capture or APK release accompany this
change. Realtime voice, Android companion UI and persistent owner knowledge remain
separate later work. Record actual test results and exact SHA in issue898.

## Technical references

Python socket timeout/makefile and sendall behavior:
https://docs.python.org/3/library/socket.html
Monotonic clock unaffected by system clock updates:
https://docs.python.org/3/library/time.html#time.monotonic
