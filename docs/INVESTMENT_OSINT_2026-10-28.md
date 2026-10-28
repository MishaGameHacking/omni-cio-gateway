# Investment OSINT: public evidence on the existing Timeweb runtime

Implementation branch: codex/investment-osint-2026-10-28, based on the deployed
2d3e08614f15cfb1d9e9428a0d3613672394a92b. Verification/deployment receipts are
recorded after the owner-laptop and exact-source quality gates complete.
No Android changes, paid model calls, trading actions or new servers.

## Source policy and free tools

* MOEX publishes RSS headlines and annotations: https://www.moex.com/a40 .
  Collect all news, listing and risk feeds; do not infer permission to redistribute
  exchange price data from the separate ISS product.
* Bank of Russia public press RSS: https://cbr.ru/development/RSS/ .
* Approved issuer financial-report indexes: MOEX, Nornickel and Gazprom. Crawl
  only the listed hosts and report paths, respecting robots.txt, source failures
  and request delays. This initial registry is not coverage of all listed issuers.
* GDELT DOC 2.0 provides public discovery metadata:
  https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ .
  Retain title/link/discovery time; do not automatically fetch arbitrary publishers
  or interpret seendate as publication time. Start with one day, advance durable
  time windows, split saturated windows down to 15 minutes and expose remaining
  gaps. The provider does not guarantee exhaustive coverage.
* pypdf 6.21.3: https://pypi.org/project/pypdf/6.21.3/ and
  https://pypdf.readthedocs.io/en/stable/user/extract-text.html .
  A pinned pure-Python wheel is verified on the laptop and deployed as an isolated
  PDF dependency. Original license/metadata are retained. No OCR, scripts, macros
  or document-supplied commands are executed.
* Scrapy AutoThrottle and Trafilatura were evaluated. Their scheduling/downloading
  layers are not needed alongside the existing queue and the narrow RSS/PDF scope.
  Arelle is a possible future connector for explicitly selected XBRL taxonomies,
  not an installed or validated financial-data provider in this release.
* Interfax e-disclosure offers a commercial API:
  https://e-disclosure.ru/poluchenie-informacii/shlyuz-api .
  It is not included in the free collection pipeline; no CAPTCHA, account or
  paywall bypass is implemented.

Public reporting about cyber incidents is eligible investment evidence. Stolen
databases, personal-data dumps, private channels and credentials are excluded.
Sensitive content is rejected; public contact strings are redacted. External
text remains evidence and cannot change configuration, execute code or authorize
a model call or order.

## Runtime and storage

The existing autonomous scheduler enqueues kind=osint in workspace_jobs.
Public collection works without a broker token, but respects the server's
automation pause, account deletion, cancellation and worker leases. Concurrent
enqueue attempts coalesce. Four targets or approximately 90 seconds per batch
keep existing interactive and financial work eligible. Individual bounded
requests can finish beyond the batch budget.

The same SQLite database holds a durable crawl frontier, conditional HTTP
validators, per-host throttles, source health, content-addressed text, publication
revisions and FTS5 search (bounded title-only fallback if unavailable).
Writes validate the job and target leases inside their transaction. Restarts
recover expired leases. 429/503 and Retry-After cause durable backoff.
HTTPS verifies the original hostname while connecting to the checked public IP;
redirects must stay within the approved source hosts. No ambient proxy, cookies,
broker secrets or HTTP authorization is sent.

RSS/Atom rejects entity declarations and enforces body/node/entry limits.
Issuer indexes expose unsupported/empty pages honestly. PDFs are parsed in a
credential-free child process with 384 MiB address space, 15 seconds CPU,
25 seconds wall time, 80 pages and 240,000 extracted characters. Encrypted,
oversized, scanned and truncated files have explicit status.

News expires after 30 days; report records after up to five years. Unknown dates
are labelled unknown and expire relative to first observation, never last fetch.
Index links explicitly dated before the rolling five-calendar-year window are
skipped. Cleanup is bounded and does not delete portfolio data or reviewed
research facts. Old unreferenced bodies and revision history are removed after
30/365 days. Minimal hash tombstones prevent unchanged undated publications from
reappearing after expiry (one year since last observation, capped at 200,000 hashes).
Completed OSINT jobs expire after seven days. The extracted-text
budget is 256 MiB, with 100,000 publications and 5,000 frontier targets; this is
not a total SQLite file-size promise. Capacity failures are visible and do not
silently drop accepted evidence. Backups retain their existing policy.

## Analysis and API

Versioned deterministic rules provide multi-label classification, source quotes,
risk-review conclusions and explicit unknowns. Exact content shares stored text.
SimHash suggests similar text; it does not identify an original author, prove
an event or establish independent corroboration.

PDF financial numbers are candidates with page, raw values and unit hints.
Period, column meaning, issuer identity and accounting scope require validation
before they can enter research_store as reviewed statements. No heuristic
candidate becomes a rating, ratio, trading instruction or investment fact.

Authenticated endpoints under /workspace/osint:
status, sources, documents (q, source_id, before_id, limit), documents/{id},
and POST refresh with the existing request_id contract. GET never starts work.
Existing /workspace/live invalidates on corpus/status revision and automation
status includes persisted OSINT health. The APK remains unchanged; these are
backend APIs, not a claim that an OSINT screen has been added to the phone.

## Acceptance evidence

Pending: full backend regression suite on LAPTOP-NPSGA016 / Ubuntu-24.04,
exact-head Sonar, rollback installer tests, existing-host deployment receipt,
and measured source availability. A short smoke observation cannot prove a
long-running 24/7 soak; failures, freshness and coverage must remain observable.
