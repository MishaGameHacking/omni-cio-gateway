# Omni-CIO V10 — Security Boundaries

Status: **WP22A boundary update pending acceptance**  
Runtime effect: **WP22A private-remote path remains gated until its Exit Gate**

## 1. Objective

Define authority boundaries before implementation so a Web/Telegram/AI/GitHub compromise cannot automatically become broker-write authority.

Security model: **least privilege + explicit authority + fail closed + evidence before action**.

## 2. Authority zones

### Zone A — GitHub engineering plane

May contain:

- code, tests, schemas, migrations;
- safe configuration defaults;
- AI policies/prompts/tool contracts/evals;
- CI/deployment/bootstrap/recovery logic;
- public/non-secret release metadata.

Must not contain:

- broker/Telegram/runtime secret values;
- full account IDs/private portfolio payloads;
- private encryption keys;
- raw private DB backups.

GitHub collaborator access is engineering authority only, never money authority.

### Zone B — CI / self-hosted runner

The runner executes repository workflows and is therefore treated as potentially dangerous if workflow trust is lost.

Required V10 design:

- private repository only;
- runner identity separate from runtime identity;
- runner cannot read trading secret store/private DB backups;
- reviewed release deployment separated from arbitrary PR code;
- persistent runner workspace is cleaned after jobs;
- critical deployment path validates reviewed Git/release identity.

Until WP3/WP6 implement stronger controls, project process manually requires focused PR + exact-head CI + no direct secret-bearing deployment from unreviewed branches.

### Zone C — V10 runtime

Runtime services use separate least-privilege identities where practical.

Sub-boundaries:

- Core/read-only services;
- Web/API;
- Telegram adapter;
- AI worker;
- Research collector;
- Execution service;
- database/backup service.

The AI/Web/Telegram processes must not inherit direct broker-write credentials merely because they share one machine.

### Zone D — Local secret store

Contains runtime-only secret values:

- T-Invest read credential;
- T-Invest trading credential;
- Telegram bot token;
- local encryption/recovery material where applicable;
- future approved external source credentials.

Requirements planned for Block C:

- OS/DPAPI/credential-protected or owner-approved equivalent;
- ACL by runtime role;
- no command-line/history/log exposure;
- rotation/revocation metadata;
- recovery key stored separately from protected data.

### Zone E — Broker authority

Three independent credentials/contours:

1. **Production READ** — read-only, never fallback to trading credential.
2. **Sandbox** — virtual-only credential and host.
3. **Personal Real** — separate account-scoped trading credential, no transfer authority.

No code may silently promote READ into Real or use Real as a convenience fallback for ordinary reads.

### Zone F — Owner approval

Owner development approval, alert acknowledgement and Real plan approval are different authorities.

`START V10` authorizes engineering work only.

Real approval later requires:

- exact immutable plan identity/hash;
- recent/step-up owner authentication on the approved surface;
- short lifetime;
- repeat preflight before submit;
- plan drift invalidates approval.

### Zone G — AI authority

AI may call only an allowlisted tool registry.

AI is denied:

- direct broker write;
- secret access;
- raw OS command execution by default;
- authority escalation through natural-language instructions;
- treating retrieved text as higher-priority system policy.

Untrusted documents/news are data, never instructions.

### Zone H — External Web/Telegram ingress

Before the WP22A Exit Gate, V10 Web remains local/private and public Internet ingress remains disabled.

The WP22A Personal implementation decision, pending acceptance, selects this private path:

`OWNER tailnet device -> Tailscale HTTPS/Serve -> loopback-only Omni-CIO Web runtime`

The corresponding boundary requires:

- Tailscale Serve only for the Personal baseline; Funnel/public routing is forbidden;
- backend launcher bound to `127.0.0.1` plus an independent application-level loopback-peer check;
- exact `*.ts.net` Host and exact locally fingerprinted Serve OWNER identity;
- local private configuration ACL limited to SYSTEM/Administrators plus read-only runtime access;
- server-side sessions with bounded 120-minute idle / 24-hour absolute lifetime, rotation and revocation;
- `Secure`/`HttpOnly`/`SameSite=Strict` cookie;
- exact Origin, Host and CORS-deny controls plus live-session validation and CSRF for unsafe requests;
- rate limiting/abuse handling without locking ordinary monitoring GETs;
- HSTS/no-store/nosniff/anti-frame/referrer response hardening;
- replay/staleness validation remains mandatory before any future Telegram Mini App identity can become authoritative;
- recent/step-up auth remains mandatory before any future Real plan approval surface can be published.

The selected private transport is not a third Omni-CIO product identity provider and does not enable public multi-user mode, broker-write authority or Real execution.

## 3. Data classifications

### Public/low sensitivity

- application code;
- architecture docs;
- public market/source references;
- non-secret release version/Git SHA.

### Internal engineering

- prompts/policies;
- tests/evals;
- deployment schemas;
- non-secret diagnostics.

### Private financial

- positions;
- balances;
- operations;
- private Decision Journal content;
- portfolio analytics tied to OWNER.

### Secret

- bearer/API tokens;
- broker credentials;
- Telegram bot token;
- private keys/encryption material;
- authorization headers.

Secret data is never committed. Private financial data is not treated as repository configuration.

## 4. Critical negative guarantees

The system must be designed so these implications are false:

```text
GitHub write access      != trading authority
AI output                != plan approval
Telegram alert click     != broker submit
Web session              != secret access
Read token               != trading token
Plan approved once       != approval of a changed plan
Possible broker submit   != safe retry permission
Submitted order          != filled order
AI research text         != canonical evidence
Lenovo possession        != plaintext secret disclosure
Private remote reach     != public Internet exposure
Tailscale identity       != broker/Real approval authority
```

## 5. Kill-switch hierarchy

Existing V9 kill switches remain binding until replaced by reviewed V10 equivalents:

- `REAL_TRADING_ENABLED=false` — master Real rollback;
- `WATCHTOWER_ENABLED=false` — monitoring rollback.

Planned V10 switches include separate AI, Telegram, plan-execution and Watchtower controls. Disabling an optional component must not widen another component's authority.

## 6. Current repository protection observation

At WP0 start, GitHub reports `main` as not protected by a server-side branch protection rule. This does **not** authorize direct pushes.

Until WP3 evaluates and configures the strongest repository protection available for the owner's GitHub plan, V10 manually enforces:

`focused branch -> PR -> exact-head Regression Shield/security -> zero review blockers -> squash merge`.

WP3 must explicitly evaluate required status checks/conversation resolution/restrictions supported for this private repository; inability to enable a paid GitHub protection feature must be documented and compensated with repository/CI process controls rather than silently ignored.

## 7. Security-change rule

Any change that moves a component across one of these boundaries requires:

- explicit current-WP scope;
- threat review;
- deterministic negative tests where possible;
- rollback/kill switch where relevant;
- ADR if the boundary changes architecturally.
