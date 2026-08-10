# Omni-CIO V10 — WP15 OWNER Live Read-Only Acceptance Runbook

Status: **WP15 OWNER-local gate / no broker-write authority**

This runbook is used only after the WP15 implementation head has passed deterministic offline review/CI and the PR explicitly names the exact reviewed SHA. It never asks the OWNER to paste a broker token, full account ID, account fingerprint, portfolio payload or screenshot into GitHub/ChatGPT.

## 1. Safety invariants

- Use only a T-Invest **production READ_ONLY** token for the intended OWNER account.
- Prefer a token restricted by T-Invest to the single intended account.
- Never use a trading/full-access token as a fallback for WP15.
- The WP15 production credential boundary independently verifies token-derived account `access_level`; any accessible account that is not reported as `ACCOUNT_ACCESS_LEVEL_READ_ONLY` fails closed before portfolio/market/operations acceptance.
- The production client proxy exposes only the approved Users/Operations/Instruments/MarketData read methods and does not expose orders, stop orders, Users write methods or an underlying service delegate.
- Never paste the token into a command line, environment variable, GitHub issue/PR, ChatGPT message, screenshot or log.
- The token is entered only through the accepted WP8 local secure prompt and stored as the `broker_read` DPAPI blob.
- `C:\ProgramData\OmniCIO\wp15\private` is private durable local state and must not be uploaded.
- Only `C:\ProgramData\OmniCIO\wp15\evidence\wp15-owner-live-evidence.json` is designed for sanitized CI validation.
- The local comparison block intentionally contains private portfolio values. Do not copy or photograph that block for GitHub/chat.
- `trading_methods=false`, `REAL_TRADING_ENABLED=false` and `app:app` remain unchanged.

## 2. Preconditions

The WP15 PR must provide the exact reviewed implementation SHA. On the Lenovo OWNER checkout:

```powershell
git rev-parse HEAD
```

The output must exactly equal the SHA named by the PR instructions. If it differs, stop and report only the SHA; do not run the live gate.

Then verify the checkout is clean:

```powershell
git status --porcelain
```

No output is expected. The focused and OWNER evidence workflows validate against this exact PR-head SHA, not a GitHub synthetic merge ref.

## 3. Provision or verify the read-only token locally

First inspect the sanitized lifecycle state:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\manage_wp8_secret.ps1 -Operation Status -SecretClass broker_read
```

If `broker_read` is `UNPROVISIONED` or `REVOKED`, use an elevated OWNER PowerShell and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\manage_wp8_secret.ps1 -Operation Set -SecretClass broker_read -AcknowledgeContourReady
```

If it is already `ACTIVE` but the credential must be replaced, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\windows\manage_wp8_secret.ps1 -Operation Rotate -SecretClass broker_read -AcknowledgeContourReady
```

PowerShell prompts with `Read-Host -AsSecureString`. Type the credential only into that local masked prompt. Do not send it back to the developer/chat.

If the external credential was ever exposed, revoke it at T-Invest first; local `Revoke`/`Rotate` does not replace issuer-side revocation.

Important: a manually asserted read-only label is not enough. During the live gate, T-Invest `GetAccounts` must report the accessible OWNER account at `ACCOUNT_ACCESS_LEVEL_READ_ONLY`; broader or unknown access fails closed.

## 4. Run the reviewed OWNER gate

From an elevated OWNER PowerShell in the exact clean checkout, run this as one line:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\infrastructure\windows\run_wp15_owner_gate.ps1"
```

The wrapper:

- refuses GitHub Actions execution;
- requires OWNER-admin elevation and a clean checkout;
- uses the protected Python 3.12.10 toolchain and hash-locked dependencies;
- protects the private WP15 account-binding directory from the CI runner;
- reads the broker credential only through the WP8 DPAPI/ACL boundary;
- creates only the structurally allowlisted read-only production client surface;
- verifies token-derived READ_ONLY account authority and rejects broader/unknown authority;
- discovers the single accessible open account and shows only its masked label before confirmation;
- reads portfolio/positions, instrument metadata, last market prices and bounded cursor operations;
- refuses a strict live snapshot if broker position limits are still loading, if required identity is unresolved, or if unsupported virtual positions would otherwise be silently omitted;
- interprets broker `blocked_lots` as numeric blocked quantity and the separate `blocked` boolean conservatively;
- asks the OWNER to compare the locally displayed portfolio summary and one sample position against the broker view;
- asks the OWNER to accept or reject displayed data ages;
- writes only sanitized implementation-bound evidence for CI.

## 5. OWNER confirmations

Every prompt is fail-closed. Type exactly `YES` only when true.

You will confirm:

1. the locally provisioned T-Invest credential is intended to be read-only;
2. the masked account is the intended OWNER account;
3. the portfolio summary matches the same broker account;
4. the sample position quantity and displayed current price/value match the broker view on the same basis;
5. the displayed snapshot/market data ages are acceptable.

The first confirmation is not a substitute for technical enforcement: the gate also verifies the broker-reported token access level.

A `NO`, broader/unknown token authority, wrong account, missing instrument identity, partial/loading snapshot, unsupported virtual positions, stale snapshot, missing market price, read failure or implementation mismatch fails the gate.

## 6. What is safe to send back

Send only the final safe summary lines, for example:

```text
WP15 OWNER live gate: PASS
Reason: WP15_OWNER_LIVE_READ_ONLY_ACCEPTED
Read-only token confirmation: True
Expected account binding: True
Portfolio confirmation: True
Sample position confirmation: True
Freshness confirmation: True
Implementation binding: True
```

On failure, send the same final safe block with `FAIL` and its reason code.

Do **not** send:

- the token;
- full account ID or account fingerprint;
- the private comparison block;
- portfolio total;
- position names/quantities/prices;
- `owner-account-binding.json`;
- screenshots containing private broker data.

## 7. CI evidence hand-off

After an OWNER PASS, the `V10 WP15 OWNER Live Audit` runs as the non-admin self-hosted CI identity against the exact PR head. It must prove that:

- the broker-read ciphertext is unreadable/not visible to CI;
- the private account-binding file is unreadable/not visible to CI;
- the sanitized evidence is readable;
- the evidence exact Git SHA and implementation SHA-256 match the reviewed head;
- every required OWNER confirmation is true;
- no private value/fingerprint/raw payload is recorded;
- broker-write/trading/Real flags remain false.

CI never decrypts or uses the real token.

## 8. After PASS

OWNER PASS is necessary but not sufficient for WP15 completion. The development flow still requires:

- final exact-head deterministic and authoritative CI GREEN;
- zero unresolved blocking review threads;
- full diff review;
- squash merge;
- post-merge Regression Shield on the exact new `main` SHA;
- separate status synchronization that marks WP15/Block D accepted.

Only after those gates may WP16 — Web Design System — be unlocked.
