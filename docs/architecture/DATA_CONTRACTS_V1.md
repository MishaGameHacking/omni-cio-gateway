# Versioned Data Contracts v1

PR-04 introduces the first stable, read-only domain-contract boundary for
Omni-CIO. The contracts live in `omni_cio/contracts/v1/` and do not change any
existing FastAPI route or GPT Action response.

## Contract guarantees

- schema version is explicit (`1.0`);
- unknown fields are rejected;
- contract objects are immutable after validation;
- money uses `Decimal` and serializes as JSON strings;
- currencies are normalized to uppercase ISO-style three-letter codes;
- timestamps must include a timezone and are normalized to UTC;
- account identifiers must already be masked;
- every instrument requires a stable identity (`position_uid`, `uid`, `figi`,
  or `isin`);
- provenance, quality and completeness are first-class metadata;
- portfolio positions and per-currency totals reject duplicates;
- no broker SDK, order placement, cancellation, withdrawal or transfer method
  is imported or exposed.

## Current scope

The v1 package contains common provenance/quality primitives and a typed
`PortfolioSnapshotV1`. Existing runtime dictionaries remain unchanged during
this PR. Later adapter work may validate and translate existing broker payloads
into these contracts behind the current public API.

## Compatibility policy

- compatible additions use optional fields inside the current `v1` package;
- incompatible changes require a new package such as `v2`;
- public route migration requires a separate PR, migration notes and contract
  tests;
- old versions remain importable while any supported consumer depends on them.

## Security boundary

These models are data-only. They deliberately contain no execution commands,
API tokens, full account identifiers or real portfolio fixtures. The project
remains GET-only with `trading_methods=false` and Render entrypoint `app:app`.
