# WP22A Phase 3 — Cloud.ru Evolution dormant hosted boundary

This directory is the source-only hosted runtime, data, recovery and readiness
boundary authorized by WP22A Phase 3.

It intentionally **does not** create, modify, discover or destroy Cloud.ru
resources. It carries no provider credentials, project IDs, tenant data, broker
credentials, DNS names, public IPs, TLS material, recovery keys or Terraform
state.

## Current authority

- accepted provider boundary: Cloud.ru Evolution;
- `provider_apply_authorized = false`;
- public ingress remains off;
- `authorized_recurring_rub = 0`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- protected V9 `app:app` remains unchanged;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- WP23+ remains locked.

Any later provider apply requires a separately reviewed Phase-4 privileged path
from accepted `main`, the required OWNER/provider authorization, current
pricing/capacity validation and explicit secret injection outside GitHub source
and CI artifacts.

## Source-controlled boundaries

The Phase-3 directory now contains focused machine-readable contracts for:

- dormant Cloud.ru Terraform safety and provider-family pinning;
- hosted runtime roles, tenant-private state and encrypted secret custody;
- provider-managed PostgreSQL runtime-user privileges and FORCE RLS;
- portable logical backup, integrity, atomic publication and replacement restore;
- hosted edge trust, health-domain classification, sanitized evidence,
  capacity/cost controls and release rollback readiness.

The corresponding Python validators and deterministic tests fail closed on drift
without requiring provider credentials or privileged mutation.

## Dormant IaC

The Terraform root remains deliberately dormant. It pins the official Cloud.ru
Evolution provider family in source and exposes only fail-closed safety
variables/checks. There are no resource or data blocks and no provider block
requiring credentials in Phase 3.

The deterministic contract tests verify that:

1. the official provider source is declared;
2. mutation, public-ingress and cost gates default fail closed;
3. hard product locks remain recorded;
4. no Terraform resources, data sources or credential-shaped values are present;
5. local Terraform state and tfvars remain globally ignored.

These declarations are Phase-3 source evidence, not hosted activation. Public
preview or production deployment begins only through a later accepted-main
protected apply boundary.
