# Official MOEX ISS TQBR quote source v1

## Purpose

PR-89 adds one internal read-only source for public Moscow Exchange ISS quote
metadata on the `stock/shares/TQBR` board. The package converts a bounded
allowlisted JSON response into the existing `MarketQuoteV1` contract plus a
strict available/unavailable source snapshot.

The source is informational only. It is not a broker account source, does not
represent an executable order price and does not authorize a transaction.

## Fixed endpoint

Only this endpoint shape is permitted:

```text
https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{SECID}.json
```

The caller may provide only a strictly validated uppercase-compatible `SECID`.
Engine, market, board, host, path and query structure are fixed in code. Path,
query and URL injection are rejected before a network call.

## Requested ISS blocks

The request disables metadata and asks only for two tables.

`securities` columns:

- `SECID`;
- `BOARDID`;
- `SHORTNAME`;
- `LOTSIZE`;
- `DECIMALS`;
- `CURRENCYID`.

`marketdata` columns:

- `SECID`;
- `BOARDID`;
- `LAST`;
- `BID`;
- `OFFER`;
- `SYSTIME`.

Column order, row width, exact single-row identity and `TQBR` board identity are
validated. Missing, duplicate or conflicting rows fail closed.

## Parsing and normalization

- response is decoded only as UTF-8/UTF-8-BOM JSON;
- JSON duplicate object keys are rejected;
- non-standard constants such as `NaN` and infinity are rejected;
- JSON floats are parsed directly as `Decimal`, not binary float;
- `SUR` and `RUB` settlement identifiers normalize to `RUB`;
- unsupported settlement currencies fail closed;
- `LAST`, `BID` and `OFFER` must be positive finite Decimal values when present;
- at least one price must be present;
- best bid cannot exceed best ask;
- naive `SYSTIME` is interpreted in `Europe/Moscow` and converted to UTC;
- timestamps more than five minutes after retrieval fail closed.

The output reuses `MarketSourceV1` and `MarketQuoteV1`. The stable instrument key
is `MOEX:TQBR:{SECID}`.

## Network boundary

- fixed HTTPS host;
- TLS verification enabled;
- redirects disabled;
- environment proxy/credential inheritance disabled with `trust_env=false`;
- owned `httpx.Client` for each fetch;
- no Authorization or Cookie header;
- timeout constrained to 0.1…30 seconds;
- response limit constrained to 1,024…5,000,000 bytes;
- `Content-Length` checked before reading;
- streamed accumulated-byte limit enforced;
- only JSON content types accepted.

Network, HTTP, content-type, size and parser failures return an unavailable
snapshot with a fixed safe error code. Upstream bodies and exception text are
not copied.

## Public-feed limitations

The snapshot permanently exposes these flags:

- `public_unauthenticated_feed=true`;
- `delayed_data_possible=true`;
- `realtime_guaranteed=false`;
- `informational_use_only=true`.

The public feed must not be described as guaranteed real-time. A future cache or
UI must show `quote.as_of`, `retrieved_at` and freshness explicitly. Licensing or
commercial redistribution decisions remain outside this package.

## Source priority

For user portfolio execution-style calculations, the broker gateway
`getMarketSnapshot` remains the primary source because it is bound to the exact
broker instrument UID and broker context. PR-89 is an independent public-market
reference and discrepancy source. Values from the two sources must never be
silently averaged.

## Privacy and safety

The snapshot contains no:

- raw JSON or upstream response body;
- credentials, cookies or tokens;
- account, position or portfolio data;
- full broker account identifier;
- exception text;
- order, transfer or withdrawal request;
- trading authorization.

Immutable flags retain `raw_json_stored=false`, `credentials_present=false`,
`broker_write_called=false`, `trade_authorized=false`, `order_created=false` and
`trading_methods=false`.

## Compatibility

- `app:app` unchanged;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no route, request body, response field or frontend component added;
- no call occurs at module import or application startup;
- no new dependency, secret, database or Render migration;
- no T-Invest method or broker write surface.

## Tests

Focused tests cover contracts, fixed URL construction, injection rejection,
allowlisted table shape, Decimal/currency/time normalization, partial and empty
quotes, duplicate keys/rows, identity mismatch, invalid prices/timestamps,
network/HTTP/content-type/size/redirect failures, redaction, public-feed flags,
package exports and absence of route/write surfaces.

## Remaining boundary

PR-89 is source foundation only. A later reviewed package may add an exact
SECID/TQBR cache with explicit fresh/stale/unavailable semantics and no-silent-
stale policy. Production registration, dashboard binding and live acceptance
remain separate work.

## Rollback

Revert the PR-89 squash commit. No data, secret, OpenAPI, database or deployment
migration must be reversed.
