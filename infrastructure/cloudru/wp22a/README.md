# WP22A Phase 3 — Cloud.ru Evolution dormant IaC boundary

This directory is the source-only hosted-runtime/IaC boundary authorized by WP22A Phase 3.

It intentionally **does not** create, modify, discover, or destroy Cloud.ru resources. It carries no provider credentials, project IDs, tenant data, broker credentials, DNS names, public IPs, TLS material, recovery keys, or Terraform state.

## Current authority

- accepted provider boundary: Cloud.ru Evolution;
- `provider_apply_authorized = false`;
- `public_ingress_enabled = false`;
- `authorized_recurring_rub = 0`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- protected V9 `app:app` remains unchanged;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- WP23+ remains locked.

Any later provider apply requires a separately reviewed Phase-4 privileged path from accepted `main`, the required OWNER/provider authorization, current pricing/capacity validation, and explicit secret injection outside GitHub source/CI artifacts.

## What this increment proves

The Terraform root is deliberately dormant. It pins the official Cloud.ru Evolution provider family in source and exposes only fail-closed safety variables/checks. There are no `resource` or `data` blocks and no `provider` block requiring credentials in this increment.

The deterministic Python contract test verifies that:

1. the official provider source is declared;
2. all mutation/public/cost gates default fail-closed;
3. the hard Phase-3 product locks remain recorded;
4. no Terraform resources/data sources or obvious credential/value fields are present;
5. local Terraform state and tfvars remain globally ignored.

This is the first focused Phase-3 source increment, not Phase-3 acceptance by itself. Hosted runtime, private PostgreSQL, encrypted tenant-secret custody, backup/restore, replacement-runtime recovery, rollback, edge trust and observability are added as later focused source increments under the same Phase-3 authority before any provider apply.
