# Stage 2B: opt-in connection to the existing portfolio-analysis worker

This change targets `run_user_analysis` (called by the existing AnalysisQueue
worker and scheduler). It is not a second scheduler or a trading executor.
The implementation is feature-gated; no operating service/configuration or owner
DB is changed by a source commit or its CI run.

## Integration

The portfolio worker builds its normal verified context and deterministic
AnalysisDecision, then calls `build_analysis_client`. With
`AGENT_ROUTING_ENABLED` absent or `false`, an unbound legacy job retains the
existing guarded-client path. Invalid flags fail closed. With `true`, an already
claimed job is required. The trusted server setting `AGENT_PORTFOLIO_ROUTE`
selects `local` (default) or `timeweb`. It is never read from a news item, prompt,
model response or user-supplied JSON. This first integration does not yet expose
route settings in Android or perform a model-authored autonomous escalation.

Before inference, an admission receipt is inserted into existing
`workspace_records`, kind `agent_analysis_admission_v1`, keyed by owner/job.
It binds the route, source deadline, context digest, complete-request digest,
broker-connection version, analysis reason, tier and output limit. The complete
request digest also binds notification intent. No prompt, holding, token, account
label or model output is stored in this receipt. Existing receipts must match
exactly; they are not updated when settings or input change. A previously bound
job cannot escape its route by restarting with the feature disabled.

The admitted messages are kept as an immutable canonical string. Inspection
returns a copy, not a mutable reference. All input messages must match that
canonical request. The persisted broker-connection version is compared again
before readiness/dispatch, so reconnecting cannot analyze old context under the
new connection even before the downstream guarded client binds its own attempt.

Receipt, job lease, cancellation, monitoring permission, automation permission
and broker binding are rechecked before dispatch; the receipt is checked inside
the existing budget reservation transaction and after the response. Expired
evidence or a changed receipt rejects publication, without pretending an incurred
cloud charge was refunded. Network/model work stays outside SQLite transactions.

## Source freshness and privacy

The T-Invest observation must be timezone-aware, no more than 300 seconds old,
and at most 5 seconds in the future. Explicit third-party expiries further narrow
the deadline. Missing/false freshness fails closed. A source without an expiry
uses the same conservative short interval. This does not transform fresh data
into verified correctness or allow a trade.

The adapter copies the structured context, removes direct account IDs/names and
known personal-ID fields, and substitutes ordinal account labels. Secret-shaped
field names cause rejection. Holdings remain sensitive: this is not anonymity or
a universal secret detector. Timeweb still requires AGENT_CLOUD_ENABLED and the
existing explicit external-data/region/catalogue/price/budget approvals. No new
keys are read from files, no AI provider is enabled by this change.

## Scope and acceptance

The factory reuses AgentTaskClient, GuardedAIClient, MoneyLedger and AnalysisQueue.
Existing call-count limits, cost limits, unknown-outcome accounting and report
validation are retained. No paid retry, paid fallback, broker order, microphone
capture, model installation or Android release is included. Legacy status UI
still describes its previous routing path; per-job route UI and companion chat
without broker presence are separate work, not claimed complete here.

Acceptance requires controller-path tests through the actual worker, temporary
SQLite receipt tests, data/permission-change and expiry tests, existing regression
tests, and the full backend suite on the owner's Lenovo/WSL. Successful synthetic
checks do not establish live GPU inference, voice latency, owner-data migration
or successful deployment. Record actual CI results in issue #898 before claiming
this stage complete. Feature enablement and protected-runtime rollout remain
separate from source integration.
