# FL-173 — Sequential read-only probes must agree on valid pre-target provider state

Date: 2026-09-27  
WP / reference: TIMEWEB-PLATFORM-CONSOLIDATION / V10 RU-PG-B Timeweb Read-Only Proof #24 / accepted main `2bfa6c2b55caab0d474f890792f4e44c745a7744`

## Symptom / failing gate

The protected-main environment-policy proof completed successfully. The provider job then emitted:

`TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY ... cluster_name_available=true existing_target=false`

and immediately failed in the next GET-only observer with:

`TIMEWEB_RU_PG_IPV4_INVENTORY=STOPPED code=TIMEWEB_IPV4_TARGET_NOT_FOUND`.

## Root cause

Two sequential read-only consumers encoded contradictory state semantics. The control-plane probe correctly defines an absent exact synthetic database target as a valid pre-create observation state. The later IPv4 custody probe required that same target to exist before it would even inspect the account-level floating-IP inventory.

The defect is therefore not missing credentials, PostgreSQL authentication, Telegram, Timeweb API availability or malformed provider state. It is repository producer/consumer contract skew: a valid state emitted by the first probe was treated as impossible by the second.

Timeweb documents public IPv4 as an account-level resource that can exist unattached and later be assigned to a database in the same availability zone. A database needs a public IPv4 for external access, but the account-level IP resource is not itself evidence that a specific database target exists or owns it.

## Blast radius searched

- the automatic protected-main read-only workflow and environment gate;
- the control-plane target-selection and success path;
- the GET-only IPv4 observer;
- floating-IP inventory truncation/shape validation;
- target-bound custody marker and binding logic;
- synthetic-create / allocation / Public IPv4+TLS mutation prerequisites;
- P3 production network-scope proof, which is separate and must continue to reject synthetic targets;
- durable README/AGENTS/CONTRIBUTING guidance that had independently frozen stale current-main/focused-branch text.

## Corrective change

When the exact synthetic target is absent, the IPv4 observer still reads and validates the complete account-level `/api/v1/floating-ips` inventory. It emits aggregate-only `target=absent` observation evidence and an explicit fail-closed recovery disposition:

`TIMEWEB_RU_PG_IPV4_RECOVERY=BLOCKED code=TIMEWEB_IPV4_TARGET_ABSENT`.

The observer returns success because the read-only observation itself is valid. It does not fabricate a cluster id, target-bound marker, custody, binding, network readiness or mutation authority. Malformed or truncated inventory remains terminal. Once the target exists, all existing target-bound provenance checks remain unchanged.

Durable contributor/agent front-door documents no longer duplicate mutable exact-main or temporary focused-branch state; they delegate that state to fresh GitHub plus the canonical V10 current-status ledger.

## Permanent regression/guard

Focused tests reproduce the exact target-absent provider state, prove the observer performs only the expected GETs, prove output contains no provider identifiers/secrets/READY/PASS claims, and prove truncated inventory still fails closed. The machine guard requires the pre-target observation path and explicitly forbids reintroducing `TIMEWEB_IPV4_TARGET_NOT_FOUND` as the observer contract.

## Future prevention rule

Every multi-step provider proof must enumerate valid states once and verify that all sequential consumers agree on them. Observation helpers must distinguish **state absent**, **state malformed**, **state unauthorized** and **state not yet ready**. A later observer may narrow authority, but it must not convert an earlier valid precondition state into a generic failure unless the contract explicitly says that state is impossible.

## Dependency/tooling knowledge change

None.
