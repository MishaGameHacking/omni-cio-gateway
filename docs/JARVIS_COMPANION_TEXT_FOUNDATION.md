# Local companion: text foundation, separate authority

Development candidate only. Feature COMPANION_CHAT_ENABLED is off by default.
No deployment, real account operation, microphone activation or paid API call.

The existing portfolio client intentionally requires a broker connection. Do not
remove that guard just to enable general conversation. The companion instead
uses the existing authenticated/Android-gated current_user dependency plus its
initiating session, and can run with a real user whose broker token is NULL.

Routes: POST /assistant/chat with request_id/text, GET/DELETE
/assistant/chat/history, POST /assistant/chat/turns/{id}/cancel. Routes preserve
no-store responses. The initial POST is synchronous in FastAPI's worker pool;
it is NOT realtime audio, streaming, a durable background agent or a voice UI.
Retrying the same request ID returns its saved state and never replays inference.
A running duplicate returns202; callers may poll the bounded history. A new
request when the single persisted companion slot is busy receives429.

The same installed local model/Unix transport is reused. No second model or daemon,
cloud fallback, tool executor, broker read, shell or web retrieval is added. Model
identity, JSON, finish status, bounded answer and usage are validated. Returned
model tools are rejected. The separate portfolio/risk/mandate path is unchanged.

Input and answers are encrypted with the existing application cipher, bound to
owner/turn/conversation epoch and field kind. Up to200 turns are retained until
explicit clear; latest6 completed pairs form bounded context. This is contextual
conversation memory, not a permanent factual profile. At capacity, reject new
work rather than silently dropping idempotency receipts. Clearing rotates the
epoch and deletes active rows so late output cannot recreate cleared history.
SQLite/backups may retain deleted bytes; this is not guaranteed physical erasure.

Before dispatch and atomically before saving, verify feature flags, initiating
session, user, epoch, status, slot and expiry. Logout/expired session, cancellation,
clear or disabling the feature suppresses late output. Cancel does not yet stop
CPU generation; keep the slot until the caller exits or the lease expires. A
process interruption eventually marks the attempt interrupted, never retries it.

Testing uses synthetic users/sessions/SQLite and fixture model replies, never real
broker tokens or personal conversations. Test separately: offline feature gate,
no-broker success, idempotency/conflict/concurrency, per-user privacy, encrypted
storage, conversation history, cancellation/session revocation/clear races,
wrong model/malformed JSON/tool responses, interrupted requests and HTTP auth.
Real Gemma validation and live service rollout remain separate acceptance gates.
