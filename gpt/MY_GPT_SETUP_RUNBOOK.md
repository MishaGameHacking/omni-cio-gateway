# Omni-CIO v8.6 — setup / recovery runbook

Для обычной настройки сначала читать `gpt/SETUP_INDEX.md`. Этот документ — короткий recovery checklist, если GPT Editor пришлось настраивать заново.

## 1. Canonical runtime

- GitHub repo: `Misha2304/omni-cio-gateway`.
- Deploy branch: `main`.
- Render service: `omni-cio-gateway`.
- Entrypoint: `app:app`.
- Base URL: `https://omni-cio-gateway.onrender.com`.
- Health: `https://omni-cio-gateway.onrender.com/health`.
- OpenAPI: `https://omni-cio-gateway.onrender.com/openapi.json`.

Один Gateway service. Не создавать duplicate service для Sandbox или real trading.

## 2. Canonical GPT configuration

- UI name may still show `Omni-CIO API | Управляющий и аналитик v8.4` until owner renames it.
- Canonical Instructions behavior: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- Recommended model: `Thinking 5.6`.
- Timezone: MSK / `Europe/Moscow`.
- Web Search: ON.
- Data Analysis: ON.
- Image generation: OFF for investment workflow.
- Apps: do not combine with Actions.

## 3. Knowledge

Upload exactly the 10 files listed in `gpt/SETUP_INDEX.md` / `gpt/CONFIGURATION.md`, one copy each.

Never upload secrets, source code, full account IDs or private broker reports as configuration.

## 4. Action authentication

Import production OpenAPI URL.

Authentication:

- Type: API Key;
- Mode: Bearer;
- Value: current `GATEWAY_API_KEY` from Render.

Never paste T-Invest tokens into GPT Editor.

## 5. Action surface recovery

Use `gpt/ACTIONS_CATALOG.md` as source of truth.

Default safe state:

- real flag OFF → no Real Trading Actions;
- Sandbox flag OFF → 14 baseline GET Actions;
- Sandbox flag ON → baseline + 8 Sandbox Actions.

After controlled real enable and valid static readiness:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

No real cancel/replace/withdraw/transfer/MARKET/margin Actions belong to first release.

## 6. Render secret recovery

See `gpt/SECRETS_AND_RENDER.md`.

Never change the role separation:

- `TINVEST_TOKEN` = production read-only;
- `TINVEST_SANDBOX_TOKEN` = Sandbox only;
- `TINVEST_TRADING_TOKEN` = real order execution only, account-scoped and non-transfer;
- `GATEWAY_API_KEY` = GPT → Gateway authentication.

Real execution additionally needs persistent disk `/var/data` and small server caps.

## 7. Preview smoke after recovery

Read-only:

1. gatewayHealth only;
2. getConnection;
3. balance;
4. portfolio;
5. 90-day operations;
6. `УПРАВЛЯЙ ПОРТФЕЛЕМ` → portfolio snapshot → cash liquidity → analytics → analysis.

Sandbox if enabled:

- status;
- virtual portfolio;
- two-phase proposal/confirmation;
- wrong/expired confirmation rejection;
- replay protection.

Real if enabled:

- follow `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md` exactly;
- run Phase 3 negative acceptance before any correct real confirmation;
- prove rollback kill switch;
- first real order only under a new explicit owner instruction.

## 8. Publishing

Click GPT Editor `Update` only when:

- Instructions v8.6 copied completely;
- Knowledge count correct;
- Action surface matches current flags/readiness;
- Bearer authentication works;
- read-only smoke passes;
- Sandbox smoke passes if enabled;
- real Phase 3 acceptance passes if real contour is being published.

## 9. GitHub boundary

A GitHub merge/deploy does not automatically modify GPT Editor. Conversely, changing GPT Editor does not update GitHub. Keep GitHub `main` as the canonical reproducible configuration.