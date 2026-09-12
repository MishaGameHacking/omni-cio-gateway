# V10 Engineering Failure Learning Ledger — FL130

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `CF_D_EPHEMERAL_INVOKE_CREDENTIAL_AMBIGUOUS_CREATE_CUSTODY_GAP`
- Scope: Neon Function `functions:invoke` credential custody introduced by PR #496

## Discovery evidence

During the pre-merge adjacent-failure review of PR #496, the current official Neon credential API contract was checked directly. The provider documents branch credential issuance as a non-idempotent `POST` and explicitly warns that a request may commit even when the client receives no response. The same API exposes a read-only credential metadata list and a credential revoke endpoint that is explicitly documented as idempotent for this resource.

The first PR implementation correctly revoked every credential whose successful issuance returned a usable `token_id`, but an ambiguous transport failure during issuance could leave a successfully created credential unknown to the caller. A second adjacent case exists on revocation: even though this credential-specific DELETE is provider-documented as idempotent, a lost response still leaves the caller unable to prove whether the first revoke reached the provider unless state is reconciled. Either gap would contradict the PR's ephemeral/no-persistence/revoke-after-use contract.

No production secret, credential identifier, Function URL, account identifier or private provider payload is recorded here.

## Root cause

The initial implementation treated credential issuance and revocation like ordinary request/response operations. It did not distinguish a definite provider rejection from an ambiguous create where server commit and client observation can diverge, and it did not explicitly reconcile a lost revoke response.

The defect was in credential custody, not in the Neon Function ingress fallback itself. Retrying the create `POST` would be unsafe because it could create another credential. Credential-specific revoke may be repeated only because that exact Neon endpoint is explicitly idempotent.

## Blast radius and adjacent review

The review covered the complete lifecycle introduced by PR #496:

- project-scoped management authority loading and masking;
- branch-scoped `functions:invoke` credential issuance;
- exact-scope/branch/principal validation;
- Function ingress use;
- normal and exceptional revocation;
- ambiguous create and ambiguous revoke outcomes;
- provider list/revoke semantics;
- current and subsequent workflow attempts.

The issue is bounded to the new ephemeral invocation credential. PostgreSQL credentials, Cloudflare secrets, GitHub OIDC, broker authority and protected V9 are unchanged.

## Permanent correction

The credential helper now owns a deterministic managed-name namespace and reconciles it before every new issuance. Only credentials in that namespace with the exact expected `functions:invoke` scope, `user` principal and target branch are eligible for automatic cleanup. Any namespace collision with broader or mismatched authority fails closed instead of being deleted or accepted.

Issuance is attempted exactly once. Definite 401/403/404 provider rejection is returned directly. For any failure where create may have committed — transport loss, malformed/oversized response, redirect or unclassified create response — a `finally` reconciliation lists the branch metadata and revokes any exact managed credential before propagating the original failure. The create request is never blindly retried.

Normal credential exit revokes the exact returned token. If that revoke does not produce a trusted terminal result, the helper immediately reconciles the managed namespace through the read-only list endpoint and repeats only the credential-specific idempotent revoke for exact managed entries. The release remains failed even when reconciliation succeeds; cleanup is not reinterpreted as release success. If reconciliation itself fails, that failure also remains blocking.

A later release attempt performs the same namespace reconciliation before minting its own credential, so a stale exact managed credential from a prior ambiguous attempt is removed before any new authority is issued.

## Regression guard

Focused tests require:

- exact `functions:invoke` scope and immediate token masking;
- stale exact managed credentials are revoked before a new create;
- managed-name scope drift fails closed without automatic deletion;
- ambiguous create is reconciled by list + credential-specific idempotent revoke and the release still fails rather than treating recovery as success;
- normal-use and exceptional-use credentials are revoked;
- ambiguous revoke is reconciled and remains a failed release;
- reconciliation failure remains blocking and preserves exception context;
- explicit provider authorization failure remains classified and is not converted into a retry loop.

## Prevention law

For every new provider mutation, classify the HTTP operation and the exact endpoint's idempotency contract before publishing the checkpoint. A non-idempotent mutation whose authority object can outlive the process must have deterministic custody reconciliation for the lost-response case; blind retry is forbidden. An operation may be repeated for reconciliation only when that exact provider endpoint is explicitly documented as idempotent.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
