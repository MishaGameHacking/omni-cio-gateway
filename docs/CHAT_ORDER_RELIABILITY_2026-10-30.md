# Chat completion and order lifecycle reliability

The owner reports a RUB-only portfolio and an incomplete answer to a short
greeting. Runtime cc22 explicitly disables order execution. It cannot manage
real capital merely because the API token has trading permission.

This change addresses chat completion and exercises the existing durable order
journal through a simulation coordinator. It does not activate real orders,
margin borrowing, or liquidation. APK57 and the investment mandate remain unchanged.

## Chat

The existing FAST/STANDARD/PREMIUM output ceilings and RUB accounting remain in
force. Prompts must fit those ceilings, including the JSON response envelope,
claims, evidence references and optional analysis fields. A short greeting must
not request a portfolio analysis or inherit earlier portfolio discussion.
Unfinished output must not be published as a complete model answer. A potentially
charged request must not be replayed silently. Failure diagnostics must not retain
provider text, personal identifiers or credentials in public logs.

## Order lifecycle

`order_lifecycle.py` coordinates the existing `paper_execution.PaperJournal`.
It has no network transport, credentials, scheduler or application integration.
An explicit simulation double is required. The journal commits before submission;
an unknown submission outcome requires lookup using the same saved identifier.
Partial execution and cancellation retain reservations until a terminal report
and a fresh complete account snapshot reconcile the result. Exact amounts use
integer nanoroubles, with no float conversion or implicit rounding.

Official T-Invest references checked on 2026-10-30:

- https://developer.tbank.ru/invest/services/orders/faq_orders
- https://developer.tbank.ru/invest/services/orders/head-orders
- https://developer.tbank.ru/invest/api/orders-service-get-order-state
- https://developer.tbank.ru/invest/services/orders/async

The documentation describes account-scoped request identifiers, limited retention,
and request-ID lookup. Pages differ on the response to repeat submission. The
coordinator therefore never infers that a missing response or missing lookup
means a new submission is safe.

## Nested cache reliability

Nested dossier loads could acquire cache stripes in opposite order and deadlock.
Nested cache access now avoids taking a second stripe while preserving outer
single-flight loading, identity isolation, TTL, defensive copies and the 256-entry
bound. A concurrent late completion does not overwrite a value published during
its load. Six bounded concurrency and cache checks cover these properties.
This source defect is confirmed; attribution of the observed runtime stall to
this specific defect remains unproven without thread stacks.

## Remaining boundary

A production broker adapter, executable investment eligibility, exact charges,
tax/settlement effects, broker collateral checks and verified account reconciliation
are still required for live portfolio management. This release does not provide
or activate that complete system. Financial return is not guaranteed.

## Verification

All executable checks run on LAPTOP-NPSGA016 in Ubuntu-24.04 WSL through GitHub
Actions. The existing Timeweb9417611 is the runtime. No new server is created.
The delivery record will identify exact source, test runs and deployment evidence;
code preparation alone is not evidence of a successful test or production repair.
