# Real-money trading v1 — staged release runbook

Status: **ENGINEERING PHASES 0–2 MERGED; FREE DURABLE STORAGE MIGRATION IN PROGRESS. OWNER PHASE 3 REQUIRED BEFORE ANY REAL ORDER.**

Architecture: `docs/architecture/REAL_TRADING_V1.md`.

Durable storage: `docs/operations/REAL_TRADING_DURABLE_STORAGE_V1.md`.

Tracking issue: #164.

## 0. Absolute safety rules

Existing production credential remains:

`TINVEST_TOKEN = read-only`

Never replace or promote it.

Real trading uses only:

`TINVEST_TRADING_TOKEN = separate account-scoped full-access, non-transfer token`

No withdrawal/transfer, securities transfer, token-management, MARKET/BESTPRICE,
margin/short, futures/options/currency execution, stop order, replace or
async-submit method is allowed in the first release.

`REAL_TRADING_ENABLED=false` is the master rollback/default state.

## 1. Engineering acceptance already completed

### Phase 0 — threat model/design

Merged and green:

- token separation/account binding;
- fixed production broker host/method allowlist;
- LIMIT/CURRENCY/DAY only;
- confirmation binding/TTL;
- hard caps;
- market/data gate;
- UUID idempotency;
- ambiguous-submit no-retry;
- audit/redaction;
- rollback plan;
- staged acceptance.

### Phase 1 — isolated backend

Merged and green:

- dedicated production REST client with no read-only token fallback;
- proposal/state machine;
- HMAC-bound exact confirmation;
- own-funds BUY / own-position SELL;
- order preview;
- price-step validation;
- immutable code ceilings + config limits;
- revalidation immediately before submit;
- `confirmMarginTrade=false` hard-coded;
- request UUID/idempotency;
- broker state reconciliation;
- fake-client security/regression tests.

### Phase 2 — durable state + conditional Actions

PR #168 merged after exact-head Regression Shield/security passed.

The initial implementation used SQLite on a Render persistent disk. The owner
cannot use Render's paid disk, so the final zero-cost deployment replaces the
production journal backend with Upstash Redis Free over HTTPS while retaining
SQLite only as an optional compatibility backend.

Conditional Action surface remains:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- consequential `executeRealTrade`;
- `getRealOrderState`.

With `REAL_TRADING_ENABLED=false`, all real-trading Actions remain absent.

## 2. Free infrastructure — no Render upgrade required

Keep the existing single Render Web Service:

`omni-cio-gateway`

Keep its instance type:

`Free`

**Do not buy Starter and do not add a Render disk.**

The durable journal is an external Upstash Redis database reached over HTTPS.
Upstash currently publishes a Free Redis tier and states that creating a normal
free database does not require a credit card:

- https://upstash.com/redis
- https://upstash.com/pricing/redis

A temporary database created through `https://upstash.com/start-redis` expires
after 72 hours unless claimed, so do not use an unclaimed temporary database for
real-money production state.

## 3. Owner Phase 3 — configuration only, NO REAL SUBMIT

This is the first owner intervention required after the free-storage code is
merged/deployed.

### 3.1 Create permanent free Upstash Redis

1. Create/sign in to an Upstash account.
2. Create one Redis database on the Free plan.
3. Copy only the database **HTTPS REST URL** and **REST Token**.
4. Never paste the token into ChatGPT, GitHub, Knowledge or screenshots.

Render Environment variables:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<HTTPS endpoint>
UPSTASH_REDIS_REST_TOKEN=<secret REST token>
```

No Render Persistent Disk is needed.

### 3.2 Create dedicated T-Invest trading token

Create a **new** token for the intended single account:

- account-scoped;
- full-access trading rights needed for orders;
- **without transfer access**.

Do not modify/revoke/replace existing read-only `TINVEST_TOKEN`.

Store the new value only in Render as:

`TINVEST_TRADING_TOKEN`

Never paste the value into chat, GitHub, GPT Instructions, Knowledge or Action
Authentication.

### 3.3 Initial free-deployment variables

Use deliberately small caps:

```text
REAL_TRADING_ENABLED=false
REAL_TRADING_JOURNAL_BACKEND=upstash
REAL_TRADING_MAX_ORDER_RUB=1000
REAL_TRADING_MAX_DAILY_RUB=2000
REAL_TRADING_CONFIRMATION_TTL_SECONDS=120
REAL_TRADING_MARKET_MAX_AGE_SECONDS=15
```

Keep existing:

```text
TINVEST_TOKEN=<unchanged read-only token>
GATEWAY_API_KEY=<unchanged gateway secret>
SSL_TBANK_VERIFY=True
```

Keep Sandbox configuration unchanged unless intentionally testing Sandbox.

### 3.4 Deploy with real flag still false

Redeploy/restart.

Expected:

- `/health` healthy;
- read-only Actions work;
- Sandbox remains independent if enabled;
- real-trading Actions absent from OpenAPI because the kill switch is false;
- no disk requirement and no paid Render upgrade.

## 4. Controlled real enable — still NO REAL SUBMIT

Only after the free-storage release is merged and default-off deployment is
healthy, set:

`REAL_TRADING_ENABLED=true`

Redeploy/restart.

If token, limits or Upstash journal cannot initialize, Gateway must fail closed:
mutation routes must not become usable. Do not work around the error.

### 4.1 Refresh Custom GPT

In GPT Editor:

1. replace Instructions completely with `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
2. keep exactly the canonical 10 Knowledge files;
3. re-import `https://omni-cio-gateway.onrender.com/openapi.json`;
4. keep Authentication = API Key → Bearer using existing `GATEWAY_API_KEY`;
5. compare operations with `gpt/ACTIONS_CATALOG.md`;
6. click `Update` only after Preview acceptance below.

## 5. Phase 3 Preview negative acceptance — zero real submit

Use a fresh Preview chat. During this section, do **not** send the correct phrase
for a prepared real proposal.

### Test A — readiness

Prompt:

`Проверь готовность реальных сделок. Вызови только getRealTradingStatus. Другие Actions не вызывай.`

PASS requires:

- `status=ready`;
- `execution_ready=true`;
- `real_money=true`;
- `real_trading_methods=true`;
- `journal_backend=upstash`;
- masked account only;
- durable journal true / integrity ok;
- caps = 1000 / 2000 RUB;
- no order submitted.

### Test B — read-only regression

Run:

1. `Проверь подключение к брокеру.`
2. `Сколько у меня сейчас денег?`
3. `Что у меня сейчас в портфеле?`
4. `УПРАВЛЯЙ ПОРТФЕЛЕМ — обнови данные и скажи, что делать.`

Expected portfolio chain:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

No real proposal should be created merely because portfolio management was
requested.

### Test C — wrong real confirmation

Prepare a **small technical LIMIT proposal only** for a supported owned/buyable
instrument below the 1000 RUB cap. Do not execute correctly.

When Gateway returns the exact phrase, send a deliberately wrong phrase.

PASS:

- `REAL_CONFIRMATION_MISMATCH` or equivalent exact-confirmation rejection;
- zero broker submit;
- no portfolio change.

### Test D — expiry

Prepare a new proposal, wait beyond TTL, then send the old exact phrase.

PASS:

- expired confirmation rejected;
- no broker submit;
- new proposal required.

### Test E — hard cap

Attempt to prepare a proposal with preliminary total above 1000 RUB.

PASS:

- blocked before `PostOrder`;
- hard-limit error;
- no real broker mutation.

### Test F — stale/incomplete market

When fresh trusted order book is unavailable, attempt a real proposal.

PASS:

- proposal fails closed;
- stale last price is not treated as executable market evidence;
- no submit.

### Test G — SELL beyond own position

Prepare SELL for more lots than owned.

PASS:

- own-position limit rejection before submit;
- margin/short is not used.

### Test H — Upstash restart persistence

1. Prepare a real proposal but do not confirm it.
2. Restart/redeploy the Render Free service.
3. Re-check readiness and journal integrity.
4. The proposal row count must survive the restart.

Do not submit the order during this test.

### Test I — Sandbox independence

If Sandbox is enabled, run `getSandboxTradingStatus` and
`getSandboxPortfolio`.

PASS:

- Sandbox remains `real_money=false`;
- real token/account/journal state is not mixed into Sandbox.

## 6. Kill-switch rollback drill

Before first real order:

1. set `REAL_TRADING_ENABLED=false`;
2. redeploy/restart;
3. verify Real Trading Actions disappear from `/openapi.json`;
4. verify 14 baseline read-only Actions remain;
5. verify Sandbox remains independent if enabled;
6. Upstash data remains intact;
7. re-import OpenAPI in GPT Editor if surface changed.

PASS this drill before Phase 4.

After PASS, the owner may re-enable the real contour for the controlled first
order and re-import OpenAPI again.

## 7. Phase 4 — first controlled real order

Requires a **new explicit owner instruction at that time**. Previous development
autonomy is not authorization to send the first real broker order.

Candidate:

- highly liquid supported cash share/ETF;
- normally 1 lot;
- preliminary total < 1000 RUB;
- LIMIT only;
- fresh order book/trading status;
- exact identity;
- complete own-funds/own-position preflight;
- no margin;
- clear rationale and NO_ACTION alternative.

### Proposal turn

GPT must:

1. label `REAL MONEY` clearly;
2. show masked account;
3. show instrument/ticker;
4. show BUY/SELL;
5. show lots/units;
6. show exact LIMIT price;
7. show preliminary total/commission;
8. show own-funds/own-position limit;
9. show server cap result;
10. show market freshness;
11. show rationale/expiry;
12. show exact `confirmation_phrase`;
13. state **«Реальная заявка ещё не отправлена»**;
14. stop without calling `executeRealTrade`.

### Confirmation turn

Only a new owner message containing the exact phrase may call:

`executeRealTrade(proposal_id, exact phrase)`

No typo correction/substitution.

### Immediately after submit

1. call `getRealOrderState` for the same proposal;
2. do not call a submitted order filled unless broker status proves fill;
3. after fill/partial fill, read back real portfolio/cash/operations as needed;
4. reconcile amount/commission/position;
5. safely replay the same confirmation once only as the release idempotency test;
   it must not create a second broker submit;
6. if any state is ambiguous, **never resubmit** — reconcile only.

## 8. First-release cancellation policy

Real cancellation is **not part of the first real-submit milestone**.

`cancelRealOrder` is not published. `ReplaceOrder` is forbidden.

For the first controlled order choose parameters intended to execute promptly
and avoid leaving an unwanted open order.

A future cancellation sub-release requires its own immutable cancel proposal,
confirmation and reconciliation.

## 9. Rollback after release

At any anomaly:

1. set `REAL_TRADING_ENABLED=false`;
2. redeploy/restart;
3. real routes disappear;
4. keep read-only `TINVEST_TOKEN` unchanged;
5. revoke `TINVEST_TRADING_TOKEN` if necessary;
6. preserve the Upstash database while unresolved `submitting`/`unknown` orders
   exist;
7. reconcile broker state before deleting operational evidence.

## 10. Definition of Done

The real BUY/SELL feature is complete only after all are true:

- [x] threat model/design merged;
- [x] isolated backend merged;
- [x] durable execution-journal contract implemented/tested;
- [x] conditional OpenAPI surface implemented/tested;
- [x] exact-head Regression Shield/security green for prior code release;
- [x] no transfer/withdraw/margin/replace/market execution surface;
- [x] wrong/expired confirmation/replay/ambiguous-submit protections covered by automated tests;
- [x] GPT v8.6 configuration package merged;
- [ ] free Upstash journal migration merged and deployed;
- [ ] permanent Upstash Free database configured in Render;
- [ ] owner Phase 3 negative Preview acceptance complete;
- [ ] kill-switch rollback drill complete;
- [ ] first minimal real order explicitly authorized;
- [ ] broker state reconciled;
- [ ] real portfolio/operations reconciled;
- [ ] idempotent replay verified with no second submit.

Only after every unchecked item becomes complete can the release be called fully
finished.
