# GPT-6 analysis protocol and decision diagnostics

Baseline runtime: `af95e8de8cfd50970d712483b8c17e866f7239c9` on the existing
Timeweb server 9417611. APK57 and broker credentials are unchanged.

## Observed cause of absent orders

The installed decision cycle explicitly returns `read_only`, `no_op=true` and
`real_orders_enabled=false`. The order lifecycle coordinator is a simulation
component, not an enabled live executor. Full token access cannot change that.

Read-only production broker audit 41066050874, 2026-10-30 13:47 UTC:
one open account with FULL_ACCESS; GetPortfolio, GetPositions and GetOrders
all returned successfully from the existing Timeweb host. Zero orders sent.
Balances, account identifiers and broker responses stay in a mode-0600 file on
that host; they are not published in this repository. Execution eligibility and
real-order handling were not tested.

All mandate field names were present. This does not prove the separate
construction confirmations or the field values valid. The patch explains loss
confirmation, income stability, invalid capacity and explicit zero capacity
separately. It does not fill unknown user facts or relax the risk checks.

## Model support

The current runtime uses `dashscope/qwen3.5-flash` for all three analysis tiers.
The patch adds exact Gateway protocol profiles for these catalogue identifiers:

| Identifier | Reasoning | Output |
| --- | --- | --- |
| openai/gpt-6-luna | none | JSON object |
| openai/gpt-6.1-terra | none | JSON object |
| openai/gpt-6.1-sol | low | JSON object |
| openai/gpt-6-astra | low | JSON object |

`max_completion_tokens` bounds reasoning and visible output together. An
incompatible token parameter is rejected before reserving money or dispatching.
No model alias, tool permission, sampling override, paid retry or model fallback
is introduced. Protocol changes invalidate queued route identities. Qwen and
the agent transport keep their current behavior.

Timeweb's catalogue listed these four models as active at 13:46 UTC. This proves
catalogue availability only, not access for the configured inference key or a
successful generation. Luna's context/output sizes were absent in that response;
the other three reported 1,050,000 / 128,000 tokens. No limits are invented.

Before changing live model routing, verify the exact key's model access, bounded
synthetic outputs and cost accounting, and update the currently Qwen-specific
price-renewal path. No model configuration is changed by this code commit.
Existing application caps remain 95 RUB/day and 2,900 RUB/month.

Sources checked on 2026-10-30:
- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/guides/latest-model
- https://github.com/timeweb-cloud/sdk-python/blob/main/docs/AiGatewayChatCompletionRequest.md
- https://developer.tbank.ru/invest/services/accounts/users

## Verification

All executable checks run on LAPTOP-NPSGA016 / Ubuntu-24.04 WSL. The new suite
tests the actual guarded client with a synthetic HTTP transport and SQLite
ledger, including token-cap rejection before spending and exact response
accounting. Decision tests cover individual missing facts, malformed numeric
capacity, zero capacity, unchanged owner configuration and disabled execution.
Full-suite and deployment receipts must be recorded separately after completion.
