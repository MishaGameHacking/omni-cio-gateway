# Final Decision Review Approved Owner Installation V1

## Status

PR-80 internal production installation boundary. Read-only, typed and
fail-closed.

This package supplies the concrete adapter that installs already existing
PR-78 owner ports into one PR-79 acquisition call. It does not create financial
values, authenticate an HTTP request, add an Action or change the final-review
HTTP contract.

## Input boundary

`FinalDecisionReviewApprovedOwnerInstallationV1` accepts only:

- one immutable `FinalDecisionReviewApprovedServerContextV1`;
- one typed `FinalDecisionReviewTrustedPurchaseOwnerPortsV1` or
  `FinalDecisionReviewTrustedSellOwnerPortsV1`;
- optional timezone-aware installation/completion timestamps.

It does not accept:

- raw calculator payloads;
- request bodies;
- credentials or bearer values;
- provider names from a user;
- full brokerage account identifiers;
- order, confirmation or execution parameters.

The context must already be authenticated, server-derived, masked and bound to
one exact purchase or sell operation by the PR-79 contract.

## Concrete loader installation

For one invocation the adapter creates fixed PR-79 loaders for:

1. Decision Engine owner;
2. exact capacity-intent owner;
3. capacity-assessment owner;
4. explicit `ProFormaRiskScenarioV1` owner;
5. the selected directional preview owner.

The opposite directional preview loader contains no owner and is never selected
or called by PR-79. Loader and lease metadata use the fixed internal provider
`omni-cio-existing-calculators`; no dynamic provider lookup is introduced.

Every loader is bound to the exact immutable server context. A different
context causes source loading to fail closed before PR-78 owner materialization.

## One-shot flow

```text
approved server context
        +
existing typed PR-78 owner ports
        |
        v
PR-80 fixed loader installation
        |
        v
PR-79 presence/freshness/account/direction gates
        |
        v
PR-78 one-shot materialization, provider invocation and cleanup
```

The adapter creates a temporary PR-79 acquisition object, invokes it once and
does not retain the supplied owner ports after the call. PR-78 continues to own
materialization, exact intent/scenario binding, provider routing and cleanup.

## Failure behavior

PR-80 does not weaken any PR-79 failure rule:

- stale authenticated context blocks every owner call;
- a missing, failed, stale or mismatched lease blocks PR-78;
- operation mismatch is rejected before source installation;
- account mismatch remains sanitized as source unavailable;
- owner exception text is not exposed;
- no failed path is reported as `ok` or `pending`.

Blocked acquisition continues to map to the existing result:

```text
FINAL_REVIEW_SOURCE_UNAVAILABLE
HTTP 503
```

## Production registration

`FinalDecisionReviewProductionRuntimeV1` now owns one
`FinalDecisionReviewApprovedOwnerInstallationV1` that shares the exact PR-78
composition object with the PR-79 acquisition controller.

Registration remains lazy:

- no installation is performed at startup;
- no owner is called at startup;
- no portfolio, network or broker call is performed at startup;
- owner and final-review registries remain empty after restart.

The default production route therefore remains safely unavailable until a later
reviewed package derives the authenticated server context and chooses the
existing typed owner ports from the actual server request lifecycle.

## Safety and compatibility

- stable entrypoint: `app:app`;
- Gateway version: `3.10.0`;
- production OpenAPI: unchanged 14 authenticated GET operations;
- request bodies: none;
- public source-publication route: none;
- raw financial payloads: none;
- credentials and full account identifiers: none;
- broker order, replacement, cancellation, transfer or withdrawal calls: none;
- trade authorization and execution readiness: false;
- `trading_methods=false`.

## Explicitly not completed

PR-80 closes the concrete typed owner-loader installation gap. It deliberately
does not fabricate the remaining authenticated server lifecycle. Production
still requires a separately reviewed request-context producer that can derive
one exact masked context and select the already-existing owner ports without
accepting raw Action values.

Render, Gateway, GPT Editor and rollback acceptance remain `not_executed` until
real external evidence is collected.

## Rollback

Revert PR-80. PR-79 returns to its fixed missing-loader startup behavior and the
existing final-review route remains fail-closed with HTTP 503. No data, secret,
OpenAPI, dependency or storage migration is required.
