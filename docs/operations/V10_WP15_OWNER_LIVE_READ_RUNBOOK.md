# Omni-CIO V10 — WP15 OWNER Live Read-Only Acceptance Runbook

Status: **WP15 OWNER-local gate / no broker-write authority**

This runbook is used only after the WP15 implementation head has passed deterministic offline review/CI and the PR explicitly names the exact reviewed SHA. It never asks the OWNER to paste a broker token, full account ID, portfolio payload or screenshot into GitHub/ChatGPT.

## 1. Safety invariants

- Use only a T-Invest **read-only** production token for the intended OWNER account.
- Prefer a token restricted by T-Invest to the single intended account.
- Never use a trading token as a fallback for WP15.
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

No output is expected.

## 3. Provision the read-only token locally

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

PowerShell will prompt with `Read-Host -AsSecureString`. Type the token only into that local masked prompt.

If the external token was ever exposed, revoke it at T-Invest first; local `Revoke`/`Rotate` does not replace issuer-side revocation.

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
- discovers the single accessible open account and shows only its masked label before confirmation;
- reads portfolio/positions, instrument metadata, last market prices and bounded cursor operations through the WP15 read-only allowlist;
- asks the OWNER to compare the locally displayed portfolio summary and one sample position against the broker view;
- asks the OWNER to accept or reject displayed data ages;
- writes only sanitized implementation-bound evidence for CI.

## 5. OWNER confirmations

Every prompt is fail-closed. Type exactly `YES` only when true.

You will confirm:

1. the locally provisioned T-Invest credential is read-only;
2. the masked account is the intended OWNER account;
3. the portfolio summary matches the same broker account;
4. the sample position quantity and displayed current price/value are plausible/equal to the broker view on the same basis;
5. the displayed snapshot/market data ages are acceptable.

A `NO`, wrong account, missing instrument identity, partial snapshot, stale snapshot, missing market price, read failure or implementation mismatch fails the gate.

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
- position names/quantities/prices unless a later OWNER-approved diagnostic procedure explicitly requires it;
- `owner-account-binding.json`;
- screenshots containing private broker data.

## 7. CI evidence hand-off

After an OWNER PASS, the focused `V10 WP15 OWNER Live Audit` runs as the non-admin self-hosted CI identity. It must prove that:

- the broker-read ciphertext is unreadable by CI;
- the private account-binding file is unreadable by CI;
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
- separate status synchronization that marks Block D COMPLETE.

Only after those gates may WP16 — Web Design System — be unlocked.
