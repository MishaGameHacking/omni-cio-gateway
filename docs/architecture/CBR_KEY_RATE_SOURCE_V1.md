# Official CBR key-rate source v1

## Purpose

PR-84 adds the first production-grade official macro-data source for Omni-CIO:
key-rate history from the Bank of Russia `DailyInfo.KeyRateXML` operation.

The package is an internal read-only source and versioned contract. It does not
add a FastAPI route, GPT Action or frontend widget and does not change the
compact final-review response.

## Official source

- provider: Bank of Russia;
- service: `DailyInfo`;
- operation: `KeyRateXML`;
- fixed endpoint: `https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx`;
- fixed SOAPAction: `http://web.cbr.ru/KeyRateXML`;
- authority: `official`.

The endpoint and operation are constants. They cannot be supplied through an
Action, query parameter, environment variable or document payload.

## Contract

`CbrKeyRateSnapshotV1` contains:

- requested date range;
- timezone-aware retrieval timestamp;
- `available` or `unavailable` status;
- official source identity when data is available;
- unique observations sorted by effective date;
- the latest observation in the requested range;
- one bounded safe error code when unavailable;
- immutable privacy and read-only safety flags.

Rates use `Decimal` and are validated in the inclusive range `0..100` percent.
An available snapshot requires at least one observation and `current` must equal
the latest row. An unavailable snapshot cannot retain source data or rows.

## Transport safety

`fetch_cbr_key_rate` performs one HTTPS POST to the fixed endpoint:

- TLS verification is enabled for the owned client;
- redirects are disabled, including for an injected test/runtime client;
- timeout is bounded to `0.1..30` seconds;
- date ranges are bounded to 3660 days and cannot end in the future;
- response `Content-Type` must be XML/SOAP;
- `Content-Length` is checked before reading;
- decoded response bytes are read as a stream and capped at the configured
  maximum before XML parsing;
- no Authorization, token, account or broker header is sent.

HTTP, transport, content-type and size failures return an immutable unavailable
snapshot. Upstream response bodies and exception text are not returned.

## XML safety

Raw XML is treated only as data and is never retained in the contract.

The parser:

- rejects `DOCTYPE` and `ENTITY` declarations before parsing;
- uses a bounded `pyexpat` tree builder with parameter entities disabled;
- rejects external entity callbacks;
- accepts both nested `XmlDocument` and XML escaped inside
  `KeyRateXMLResult`;
- recognizes official date/rate field variants without executing source text;
- supports ISO and `dd.mm.yyyy` dates plus decimal comma/point;
- rejects malformed XML, SOAP Fault, empty data, out-of-range rows and
  conflicting duplicate dates;
- never stores raw XML or fault text.

The initial ElementTree parser was rejected by Bandit B314 during draft CI and
was replaced rather than suppressed.

## Failure codes

Publicly safe internal codes include:

- `CBR_KEY_RATE_NETWORK_ERROR`;
- `CBR_KEY_RATE_HTTP_ERROR`;
- `CBR_KEY_RATE_CONTENT_TYPE_INVALID`;
- `CBR_KEY_RATE_RESPONSE_TOO_LARGE`;
- `CBR_KEY_RATE_XML_INVALID`;
- `CBR_KEY_RATE_SOAP_FAULT`;
- `CBR_KEY_RATE_EMPTY`;
- `CBR_KEY_RATE_RANGE_MISMATCH`;
- `CBR_KEY_RATE_DUPLICATE_CONFLICT`.

No code contains an upstream message, URL query, credential or account value.

## Compatibility and safety

- `app:app` is unchanged;
- production OpenAPI remains exactly 14 authenticated GET Actions;
- no request body or new operation ID is added;
- no T-Invest call is performed;
- no broker order, cancellation, transfer or withdrawal method is added;
- no credential or full account identifier is accepted or retained;
- `trading_methods=false`.

## Remaining integration boundary

PR-84 creates the trusted source but does not silently insert it into an
existing response. A later reviewed package must:

1. select the exact internal dashboard/analysis owner that needs the key rate;
2. define freshness/cache and unavailable-display semantics;
3. wire the typed snapshot without changing broker-account facts;
4. preserve current Action compatibility or version the public contract
   explicitly if a public field is intentionally added;
5. test the real Render/GPT path separately from local CI.

## Tests

Focused tests cover contract invariants, request construction, nested and
escaped XML, decimal normalization, sorting, duplicate conflicts, range
mismatch, DTD/entity rejection, SOAP Fault redaction, fixed endpoint and
headers, network/HTTP/content-type/size/redirect failures, invalid input before
network access and absence of route/write surfaces.

## Rollback

Revert the PR-84 squash commit. No database, secret, dependency, OpenAPI or
Render migration is required.
