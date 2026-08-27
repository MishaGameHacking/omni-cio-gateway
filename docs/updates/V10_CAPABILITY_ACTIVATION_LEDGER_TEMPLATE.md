# Omni-CIO V10 — Capability Activation Ledger Template

`WORKING CAPABILITY ACTIVATION STATE — NOT ACCEPTED MAIN AUTHORITY`

This ledger is a working record for one material capability activation transition under Amendment 13. It never replaces `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Identity

- Capability ID:
- User-facing name:
- Owning WP/System Update:
- Accepted base `main` SHA:
- Branch/PR:
- Canonical Web/runtime target:
- Current accepted capability state:
- Proposed capability state:

Allowed states for implemented/activation-tracked capabilities only:

- `IMPLEMENTED`
- `LIVE_OPERABLE`
- `BLOCKED_EXTERNAL`
- `REAL_MONEY_AUTHORIZED`

If the capability is not implemented, STOP. Do not assign an activation state to imply progress that does not exist.

## Implementation / technical evidence

- [ ] Owning implementation is accepted on protected `main`.
- [ ] Required automated positive/negative tests pass.
- [ ] Security/authority review for the capability is accepted.
- [ ] Recovery/rollback semantics are defined.
- [ ] No unrelated future V10 block is being used as an artificial blocker.

Evidence:

```text
accepted implementation SHA/PR/gates:
```

## External blocker inventory

Record only blockers that are real and specific.

- [ ] Provider application/Allowed URL/callback registration, if applicable.
- [ ] Runtime-only provider credentials, if applicable.
- [ ] Managed runtime/hostname/DNS/edge acceptance, if applicable.
- [ ] Privacy/personal-data/legal acceptance, if applicable.
- [ ] Capacity/monitoring/incident-operations acceptance, if applicable.
- [ ] Broker terms/permission, if applicable.
- [ ] Tenant secret-custody/security acceptance, if applicable.
- [ ] Other genuinely non-delegable OWNER/provider action, if applicable.

```text
BLOCKERS:
- blocker:
  evidence:
  owner/action required:
  safe non-secret completion evidence:
```

`V10 is not finished yet` is not a valid blocker.

## Real-user operability evidence

For a proposed `LIVE_OPERABLE` transition:

- [ ] Canonical deployed Web/runtime is the reviewed target.
- [ ] Real supported USER can exercise the capability end-to-end.
- [ ] Login/session/logout/revocation behavior is proven where applicable.
- [ ] USER-facing error/degraded/blocked states are truthful.
- [ ] No demo/OWNER/admin/product-auth bypass was used.
- [ ] Evidence is sanitized and contains no secrets/private portfolio payloads/full broker account IDs.

```text
real-user evidence summary:
```

## Multi-user / tenant isolation

Where tenant-scoped:

- [ ] USER A cannot read USER B data.
- [ ] USER A cannot mutate USER B data.
- [ ] Guessed object IDs do not authorize cross-tenant access.
- [ ] Session/logout/revoke remains user-scoped.
- [ ] Cache/job/notification scope is tenant-safe where applicable.
- [ ] Broker/provider credentials are not cross-tenant accessible.

```text
isolation evidence:
```

## T-Invest READ / TRADE boundary

If broker-related:

- [ ] READ capability is evaluated independently from Real execution.
- [ ] READ never falls back to a TRADE/full-access credential.
- [ ] Public T-Invest terms/permission evidence is real and accepted before public live use.
- [ ] Broker credentials are tenant-scoped and protected by the accepted secret-custody design.
- [ ] TRADE credential connection/verification, if present, does not itself authorize submit.
- [ ] Execution eligibility uses exactly `VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`.
- [ ] Account mismatch fails closed.
- [ ] Transfer/withdrawal/margin/uncovered-short authority is not introduced.

## Real-money authorization gate

Only for a proposed `REAL_MONEY_AUTHORIZED` transition:

- [ ] Representative Sandbox/Shadow evidence accepted.
- [ ] Immutable exact plan contract accepted.
- [ ] Authenticated short-lived USER approval/step-up accepted.
- [ ] Immediate preflight and drift stop/re-plan accepted.
- [ ] Idempotency / one-possible-submit semantics accepted.
- [ ] Ambiguous submit never blindly retries and reconciles first.
- [ ] `submitted != filled` without broker evidence.
- [ ] Kill switches tested.
- [ ] Broker terms/permission and credential authority accepted.
- [ ] `REAL_TRADING_ENABLED` activation is explicitly owned by this accepted gate.

If any item above is not proven, `REAL_MONEY_AUTHORIZED` is forbidden.

## Kill switch / runtime availability

- Accepted capability state:
- Current runtime availability:
- Kill switch / temporary suspension active: YES/NO
- Reason:
- Recovery criteria:

A temporary safety suspension does not silently rewrite accepted capability state. The UI/status must explain the bounded reason.

## Monitoring / recovery

- [ ] Health/readiness/availability is observable.
- [ ] User-impacting failure is diagnosable without secrets.
- [ ] Revoke/disable path exists where applicable.
- [ ] Rollback/recovery path is documented/tested.
- [ ] Incident path preserves tenant and money boundaries.

## State transition decision

```text
FROM:
TO:
DECISION: PASS / BLOCKED / FAIL
EXTERNAL GATES CLOSED:
REMAINING BLOCKERS:
EXACT EVIDENCE:
```

## GitHub acceptance lifecycle

- [ ] Exact-head DRAFT applicable checks all `success`.
- [ ] Independent review complete.
- [ ] Unresolved blocking review threads = 0.
- [ ] Fresh READY exact-head applicable checks all `success`.
- [ ] Squash merge complete.
- [ ] Exact-new-main Regression Shield `success`.
- [ ] Exact-new-main V10 Engineering Governance `success`.
- [ ] `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` updated only from accepted evidence.

Until the final accepted-main transition exists, this ledger remains working-state evidence only.
