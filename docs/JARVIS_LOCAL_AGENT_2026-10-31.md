# Analyst AI / Jarvis: confirmed direction and staged implementation

Owner approval: 2026-10-31, conversation at 17:07 UTC.
Baseline: dfdef4a38bf3c05f5ec4e94683b9841f2cfaf94c (includes the Lenovo-only
Android candidate and the subsequently tested local JSON inference changes).
This document records the new agreed direction; older requirements prohibiting
all external inference do not describe the target hybrid architecture.
It does NOT activate paid providers, real trading, microphone capture or deployment.

## Confirmed requirements

- One owner, one persistent personal assistant. Main application backend, memory,
  database, scheduler and installed model run on the existing Lenovo Legion Y540.
  Use CPU, RAM and RTX 2060 as appropriate; 100% constant utilization is not a goal.
- Preserve the existing AnalystAIHomeHost / AnalystAI-Service installation.
  The local model already has a LiteRT integration. Do not install a duplicate
  Ollama/model stack just because the Windows ollama command is absent.
- Local inference and local speech are the default. Optional stronger models are
  accessed through Timeweb AI Gateway, with exact approved model identifiers,
  current pricing, data approval and the existing money-reservation ledger.
- Timeweb is optional inference, not a replacement main host. Existing production
  data remain protected until a verified migration; do not delete the old host.
- 24/7 means a supervised, event-driven service independent of Android Studio,
  Codex, the open Android screen or an ongoing ChatGPT conversation. Sleep/power
  loss on the only host interrupts local work. Do not promise high availability.
- Voice target: greet on app entry, continuous explicitly enabled conversation,
  interruption of speech playback, context memory, microphone status and stop.
  A local CPU citation-selection benchmark is NOT acceptance of voice latency.
- Public internet access is for authenticated data connectors and source retrieval.
  Documents/web pages/model answers are untrusted data, never executable orders.
  Stronger models do not replace actual retrieval of up-to-date evidence.
- Explain decisions with sources, calculations, alternatives and uncertainty.
  Do not invent completed actions or present internal model text as an audit trail.
- Owner target: execute an already permitted investment strategy without confirming
  each routine trade, then report broker-confirmed results. A separate deterministic
  risk/execution layer is mandatory; an LLM never holds the trading key or changes
  its own mandate. Implementation/testing here remain read-only, shadow or sandbox.
  Real-account activation is not part of this development step.
- Retain existing qualification, rating, issuer, instrument and turnover constraints.
  Resolve any historical mandate conflicts from the actual saved mandate; never
  silently widen risk limits or enable leverage. Preserve unknown-order states and
  reconciliation. Only one live executor may ever own an account.
- No new manual diagnostic commands or Codex tasks for the owner in this stage.
  Use the existing authorized repository/Lenovo test runner. Never export private
  runtime scripts, credentials, conversations or account data into public CI logs.

## Budget (planning, not a supplier quotation)

The agreed economical illustration totals 3,000 RUB/month:
2,000 external AI + 400 electricity + 200 backup + 100 domain + 300 reserve.
Electricity and external connectivity are estimates, not measured bills.
A paid gateway/tunnel, hardware service, home internet, broker commissions and
hired engineering support are separate where applicable. Do not order a server,
GPU, paid data source or subscription as part of this step.

Do not silently rewrite current service limits (previous checkpoint: AI 95/day,
2900/month). The new policy's proposed cloud envelope is at most 95/day and
2000/month, intersected with ALL stricter existing user/project money limits.
Missing daily limits keep paid calls off. Reaching the envelope must not stop
local monitoring; cloud-required work waits rather than silently downgrading a
financial review. The actual MoneyLedger remains authoritative and must reserve
atomically immediately before dispatch; a preflight decision is not a reservation.
No cloud token cost applies to local inference, but hardware/energy still cost money.

## Stages and acceptance criteria

| Stage | Scope | Acceptance / current state |
|---|---|---|
| 1 | Record requirements and build local-first admission policy | Initial implementation in agent_runtime_policy.py; synthetic tests must pass on Lenovo; no runtime switch |
| 2 | Connect policy to existing jobs, local adapter and guarded Timeweb client | One per-job route, atomic budget reservation, no global AI_TRANSPORT mutation, no paid retry, redacted context; integration tests |
| 3 | Persistent agent tasks and inspectable memory | Recover jobs after restart; deduplication; cancellation; sources and owner edits; no duplicate scheduler or broker executor |
| 4 | Local speech and Android live conversation | Real Russian recognition/synthesis, interruption, latency/resource measurements on Lenovo; microphone explicitly enabled |
| 5 | Public data retrieval and portfolio read-only reasoning | Source freshness/provenance, exact calculations, no internet text interpreted as a tool instruction |
| 6 | Trading executor simulation/sandbox | Mandate checks, commissions/lots, idempotency, partial fills, unknown outcomes, recovery and kill switch; no live activation through this work |
| 7 | Supervision, encrypted backups and recovery | Real reboot test, restore test, bounded logs/queues, power/network failure and resource contention tests |
| 8 | Owner app and migration acceptance | Signed client, login over mobile network, actual owner DB/key migration, one active runtime, verified rollback and explicit release report |

Stages 2-8 are NOT complete. A passing stage-1 unit suite does not establish
working voice, current GPU inference, full portfolio autonomy or a released APK.

## Stage-1 boundaries and next integration

`agent_runtime_policy.plan_task` is a side-effect-free admission planner.
It uses `ai_budget.configured_limits` rather than introducing another money ledger.
It can describe local model, local service, paid Timeweb preflight or deferral.
No HTTP client, model invocation, shell, microphone, database migration or broker
call is implemented in this module. It is intentionally not attached to the live
controller yet, and never authorizes a trade.

Caller-supplied availability, privacy and freshness signals must originate from
trusted application checks, NOT model-authored tool arguments. Budget snapshots
include existing settled/reserved/uncertain charges and must be current. Recheck
and reserve using the existing guarded client at execution to handle concurrency.
Retain all existing URL, model catalogue, region, token and context restrictions.

For the next step, read this document plus AGENTS.md, ai_jobs.py, ai_budget.py,
ai_guarded_client.py and the current local adapter. Integrate per-job routing
without overwriting owner settings or installing a second model. Persist code
and test evidence before changing any running service.
