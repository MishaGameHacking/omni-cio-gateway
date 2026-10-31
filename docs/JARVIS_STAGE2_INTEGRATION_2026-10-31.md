# Jarvis stage 2: per-job guarded inference integration

Continuation of issue #898 and JARVIS_LOCAL_AGENT_2026-10-31.md.
Baseline: 16f25843c82a88f26409e9af51221d72add822a0.

## Implemented boundary

`AgentTaskClient` composes the existing `GuardedAIClient`, `AnalysisQueue` claim
context, local Unix-socket adapter and `MoneyLedger`. It is opt-in: no live
controller imports it yet, no Windows/WSL services or owner database are changed.

- Require an active queue lease bound to the same user for both local and cloud.
- Choose local/gateway per call using a private configuration copy, never
  mutate global AI_TRANSPORT, credentials or current production budget settings.
- Preserve source freshness/privacy, broker binding, catalogue, region, prices,
  URL, bounded response, model identity, cancellation and accounting checks.
- Intersect existing user/project limits with the stage-1 envelope; recompute
  budget from the existing ledger under its atomic reservation transaction.
- Reject changed relevant settings or trusted task context before dispatch and
  before returning the result. Sent calls remain charged even when cancelled.
- Snapshot input messages before dispatch to avoid post-approval mutation.
- No automatic paid replay, no cloud-on-local-error, no downgrade of a required
  cloud review. Audio/system tasks need their own local handler, not this client.
- No new scheduler, ledger or trading executor. No actual broker order methods.

## Trusted input contract

Context/config providers are in-process, trusted, synchronous and memory-only.
They MUST NOT perform network work or open DB transactions: some checks run
under MoneyLedger's existing SQLite write transaction. Build freshness/privacy
facts in the collecting layer, never from model tool arguments or web-page text.
The adapter only enforces those facts; it is NOT a secret detector or redactor.
It does not create end-to-end voice, persistent memory or a data-fetching agent.

The current guarded client still requires an existing broker connection even
for local inference. This patch preserves that restriction; broker-independent
companion chat must be explicitly designed later, not bypassed through a fake
binding. Test fixtures use only a synthetic temporary database.

## Verification and remaining work

Tests use temporary SQLite, the real queue/ledger and synthetic local/HTTP
transports. No paid provider, real model, private files or real account is used.
Run the targeted suite on the existing Lenovo runner. A green unit/integration
suite does not prove runtime deployment or live model availability.

Next: connect this opt-in seam to the actual job producer with persisted trusted
routing context, perform the full backend regression suite, then accept the
isolated deployed integration before touching the working service. Stage 2 must
not be marked fully complete just because its adapter tests pass.
