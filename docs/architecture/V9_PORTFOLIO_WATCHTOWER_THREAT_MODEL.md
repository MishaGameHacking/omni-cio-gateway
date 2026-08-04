# V9 Portfolio Watchtower — Threat Model

## Protected assets

- owner policy identity and portfolio/risk state;
- alert correctness and deduplication state;
- schedule identity/configuration;
- QStash token/signing keys;
- Upstash credentials and HMAC state key;
- protected WP11/WP12 owner-confirmed real-money boundary.

## Trust boundaries

1. Canonical read-only portfolio/risk/credit/market providers → Watchtower reducer.
2. QStash → internal Gateway schedule endpoint.
3. Gateway → durable Watchtower Upstash namespace.
4. Watchtower output → notification/recommendation/proposed-plan consumers.

None of these boundaries grants broker-write authority.

## Threats and controls

### Forged scheduler requests

Threat: an attacker calls the public scheduler endpoint directly.

Controls:

- verify the exact raw request body and destination URL against QStash signature evidence;
- accept current/next signing keys to support controlled rotation;
- reject missing, malformed, expired or invalid signatures before reducer execution;
- exclude scheduler/callback endpoints from GPT OpenAPI.

### Duplicate/retried delivery

Threat: network or QStash retry causes the same logical run to arrive repeatedly.

Controls:

- persist bounded delivery IDs;
- semantic signal fingerprints suppress repeated unchanged alerts even if delivery IDs differ;
- compare-and-swap durable state prevents concurrent double-commit;
- callback/retry handling is itself idempotent.

### Alert spam from changing observation hashes

Threat: identical economic condition receives a new source/assessment SHA each polling cycle.

Control: alert fingerprint is based on semantic condition identity, while source hashes remain evidence only.

### Missed recurrence after recovery

Threat: a condition disappears then later reappears but a permanent historical dedup set suppresses it.

Control: durable state tracks current active signal fingerprints, not an unbounded permanent suppression set. Disappearance clears the active fingerprint so later recurrence can alert again.

### Policy or portfolio binding drift

Threat: Watchtower combines risk/credit evidence from a different policy or portfolio.

Controls:

- exact `PolicyReferenceV1` equality across input risk and credit passports;
- exact portfolio snapshot SHA binding to WP8 risk;
- policy identity change becomes a material error alert;
- invalid binding fails contract validation before state mutation.

### Stale or degraded upstream evidence

Threat: monitoring treats stale/unknown evidence as a clean state.

Controls:

- consume canonical WP8/WP6 readiness and data-quality state;
- stale/unknown liquidity and data-quality degradation are explicit signals;
- scheduler never invents missing values.

### Secret leakage

Threat: logs/state/alerts expose QStash token, signing keys, Upstash credentials, broker tokens or full account data.

Controls:

- secret values exist only in environment configuration;
- safe message codes replace free-form source payloads;
- journal persists hashes/identifiers only;
- repository boundary guard rejects broker tokens/clients and forbidden mutation surfaces;
- scheduler logs must use existing safe observability metadata.

### Scheduler misconfiguration / runaway retries

Threat: duplicate schedules or excessive retries create load/noise.

Controls:

- one canonical schedule identity per Watchtower job;
- bounded retries;
- deduplication IDs;
- signed callback/failure-callback endpoints;
- schedule state can be listed/read and reconciled against expected configuration.

### Privilege escalation to real trading

Threat: recurring monitor becomes an autonomous real-money executor.

Controls:

- Watchtower contracts hard-code `execution_authorized=false` and `trading_methods=false`;
- no import of real-trading/Sandbox mutation services in Watchtower runtime;
- no transfer, withdrawal, margin, short, MARKET/BESTPRICE or submit methods;
- recommendations/plans flow into existing WP11/WP12 owner-confirmed protocol only.

## Fail-closed conditions

Watchtower must reject or safely stop on:

- invalid contract/hash/binding;
- invalid scheduler signature;
- unavailable/corrupt durable state;
- CAS conflict;
- unsupported scheduler target/redirect;
- unbounded or invalid retry configuration;
- attempts to introduce broker-write authority.
