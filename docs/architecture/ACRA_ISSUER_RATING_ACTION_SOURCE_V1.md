# ACRA issuer rating action source v1

## Purpose

PR-94 adds one fixed internal source for issuer-level national-scale credit-rating
actions published by ACRA. It is a read-only source boundary, not a route,
recommendation engine, trading permission or universal rating scraper.

The source is used only after typed contract validation. Raw HTML is treated as
untrusted external data and is not retained.

## Fixed source identity

- endpoint: `https://www.acra-ratings.ru/press-releases/?count=30&lang=en`;
- provider: `ACRA`;
- source id: `ACRA.press_releases.issuer_rating_actions`;
- release URLs: only `https://www.acra-ratings.ru/press-releases/{numeric_id}/?lang=en`;
- caller cannot choose host, path, language, count, agency or generic URL.

The contract records that ACRA is a credit-rating agency recognized by the Bank
of Russia. This flag identifies the source; it does not make ratings from
separate agencies interchangeable.

## Supported records

V1 accepts simple issuer-level Russian national-scale actions only:

- assigned;
- affirmed;
- upgraded;
- downgraded;
- withdrawn.

One record contains:

- normalized issuer/subject name;
- fixed issuer scope;
- agency and rating scale;
- current rating when the action is not withdrawal;
- normalized outlook when explicitly published;
- publication date;
- canonical official release URL;
- immutable source provenance and safety flags.

Ratings are strings such as `AAA(RU)`, `AA-(RU)`, `BBB+(RU)` or `eA(RU)`.
Values are never converted to another agency's scale and no numeric score is
invented.

## Unsupported scope versus malformed supported scope

The list may contain documents outside this V1 boundary. The parser safely skips:

- issue/bond/note/tranche/RMBS/series/class/security actions;
- international-scale actions without `(RU)`;
- multi-target or multi-rating titles;
- non-rating press releases.

A title that clearly presents one national-RU issuer action but does not match
the allowlisted grammar fails closed with a schema error. This distinction
prevents an unsupported action from taking down the source while still detecting
schema drift inside the supported boundary.

Issue-level extraction requires a separate reviewed contract with exact issue
identity. PR-94 does not infer an issue from free text.

## HTML and transport boundary

- HTTPS/TLS verification for the owned client;
- redirects disabled and `trust_env=false`;
- no Authorization or Cookie header;
- bounded timeout, declared `Content-Length` and streamed byte total;
- only HTML/XHTML content types accepted;
- built-in `HTMLParser` with script/style/noscript content ignored;
- visible text and links are treated strictly as data;
- numeric release URL identity and publication-date validation;
- duplicate release conflicts fail closed;
- maximum 30 accepted records;
- future publication dates fail closed.

Network, HTTP, content-type, size, HTML, schema, identity, date, URL and duplicate
failures produce one typed unavailable snapshot with a fixed error code. Upstream
body, raw HTML, exception type, exception text and traceback are not returned or
stored.

## Contract invariants

An available snapshot requires:

- one official ACRA source identity;
- at least one typed record;
- every record sharing the same source;
- no error code.

An unavailable snapshot contains no source and no records and requires one fixed
error code.

A withdrawn action cannot claim a current rating or outlook. Non-withdrawn
actions require a rating. All records remain issuer-only and
`trading_methods=false`.

## Startup and API behavior

Importing the module or constructing contracts performs no network call. The
source is invoked only by an explicit internal caller.

PR-94 adds no:

- FastAPI route or operationId;
- GPT Action, request body or response field;
- frontend/dashboard binding;
- startup/background refresh;
- database, secret or Render migration;
- T-Invest call or broker write method;
- order, cancellation, transfer or withdrawal capability.

`app:app`, exactly 14 authenticated GET Actions and `trading_methods=false`
remain unchanged.

## Tests

Focused tests cover:

- contract consistency and withdrawal semantics;
- assignment, affirmation, upgrade, downgrade and withdrawal parsing;
- publication ordering and outlook normalization;
- issue-level, international-scale, multi-target and non-rating skips;
- malformed supported-action rejection;
- fixed URL scope and release identity;
- missing/future dates and duplicate conflicts;
- empty/non-UTF-8 input;
- fixed endpoint and absent credential headers;
- HTTP/content-type/size/network failure mapping;
- versioned exports and absence of route/startup/write surface.

## Explicit next steps

A later reviewed package may add bounded exact-record cache/freshness and safe
observability. Production owner/UI binding remains blocked until the exact
existing caller is identified. Issue-level ratings, other agencies and agency
scale comparison require separate contracts and source-specific validation.
