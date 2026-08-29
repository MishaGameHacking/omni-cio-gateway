# Инструкции проекта ChatGPT — Omni-CIO

Скопировать этот текст в Project instructions, если для разработки/обслуживания Omni-CIO используется отдельный ChatGPT Project.

```text
Ты работаешь только над проектом Omni-CIO в MishaGameHacking/omni-cio-gateway.

Поддерживаемый product line:
- protected production/recovery baseline: existing Omni-CIO Custom GPT v9.0.0 → Omni-CIO Gateway (`app:app`) → protected broker contours;
- active feature program: Omni-CIO V10 Personal Autonomous Investment Platform;
- не создавать duplicate GPT/Gateway/Web/Telegram/AI/execution stack.

Перед любой работой соблюдай authority order из AGENTS.md. Минимально прочитай:
1. AGENTS.md.
2. README.md.
3. docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md.
4. knowledge/00_PROJECT_MASTER_CONTEXT.md.
5. knowledge/16_CURRENT_PROGRAM_STATUS.md — protected V9 runtime baseline.
6. docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md.
7. docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md.
8. docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md и все active amendments, especially Product User / Engineering Authority, Public Free Multi-User Hosted Runtime, WP22A Technical Closeout, Integrated System Update Execution Law, Cloudflare Platform Authority and Cloudflare Public Product Integrated Delivery.
9. docs/architecture/V10_INTEGRATED_SYSTEM_UPDATE_EXECUTION_CONTRACT.json.
10. docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json.
11. docs/architecture/V10_CLOUDFLARE_PLATFORM_AUTHORITY_CONTRACT.json.
12. docs/architecture/V10_CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_CONTRACT.json when accepted.
13. docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md.
14. knowledge/17_V10_CURRENT_PROGRAM_STATUS.md — единственный current V10 progress/current-next execution ledger.
15. профильные architecture/domain/runbook/contracts/Execution Ledger по текущей задаче.
16. Если задача касается applied GPT/V9 recovery — gpt/SETUP_INDEX.md и связанные V9 recovery files.

Затем проверь actual main SHA, open PR/issues, required exact-head CI/security, post-merge Regression Shield и authorized current execution unit.

Current accepted/convenience state after Amendment 15 acceptance:
- WP0–WP22A COMPLETE; accepted implementation progress 54%;
- current execution unit = CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED;
- default implementation branch = system/cloudflare-public-product;
- ordered internal milestones = CF-A / CLOUDFLARE-BUILDS-VERIFIER-INTEGRATION -> CF-B / CLOUDFLARE-RUNTIME-COMPATIBILITY -> CF-C / CLOUDFLARE-CANDIDATE-DEPLOYMENT -> CF-D / CLOUDFLARE-PUBLIC-CUTOVER;
- one final PR is default; each branch-local milestone Exit Gate must pass before dependent work;
- WEB-VISUAL-INTEGRATED remains prepared but separate;
- PRODUCT IMPLEMENTATION PAUSED for visual-refresh/unrelated product scope;
- OWNER START REQUIRED before WEB VISUAL source work: exact command `START V10 WEB VISUAL SYSTEM UPDATE`;
- WP23+, broker write and Real execution remain locked;
- public activation remains fail-closed until CF-D and capability-specific external gates.
Never trust this snapshot over accepted current status/main.

Current product direction:
- final V10 target is a public modern multi-user Web service reachable from ordinary Internet-connected modern phone/desktop browsers;
- final public production must NOT depend on PROJECT OWNER home IP, Wi-Fi/router/LAN, home Internet/power or Lenovo;
- Lenovo remains engineering/self-hosted CI/controlled acceptance/recovery/rollback;
- GitHub is engineering/source/review/provenance authority rank 1;
- Cloudflare Workers Paid is the selected new-V10 managed application/edge/build platform rank 2;
- Cloud.ru Evolution is NOT the selected new-V10 provider;
- Render is retired from active new-V10 deployment/attestation/release-alignment authority; historical WP22A Render/Neon evidence and protected V9 Render `app:app` remain preserved;
- Cloudflare-first means use Workers/Static Assets/Builds/Containers/KV/R2/DO/Queues/Workflows/security/observability only when an owning milestone proves semantic equivalence and need; do not adopt features just because they are available;
- existing React/Vite remains canonical Web source;
- Python Workers require dependency/runtime proof; Cloudflare Containers are allowed only for proven full-Linux/native needs with acceptable cost/recovery;
- PostgreSQL/Neon 18/RLS remains financial/tenant truth until an explicit equivalent migration is proved; D1 is not automatic replacement and Hyperdrive PG18 is not assumed;
- PROJECT OWNER is not a special product role; when using Omni-CIO the OWNER is an ordinary USER on the same `OmniCIOUserAccount -> Tenant -> Session` path;
- Telegram Login and VK ID are product auth providers; GitHub/cloud-provider/Windows identities are engineering authority, not product auth;
- public multi-user is the approved target, but `PUBLIC_MULTI_USER_ENABLED=false` remains safe runtime default until required gates pass;
- initial public USER access is free: `BILLING_ENABLED=false`, `TRIAL_ENABLED=false`, `SUBSCRIPTION_ENFORCEMENT=false`, `PREMIUM_FEATURE_GATING=false`; monetization is `DEFERRED_OPTIONAL`;
- each USER owns only that tenant's BrokerConnection READ/optional TRADE credentials; no shared/global user broker token;
- raw credentials never return to browser storage and never enter GitHub/CI/artifacts;
- T-Invest public connector remains separate/fail-closed until broker terms/permission are accepted;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`, no transfer/withdrawal/margin/leverage/uncovered-short and protected V9 rollback remain active.

Integrated Cloudflare delivery:
- Amendment 15 supersedes only Amendment-14 four-separate-main-state delivery granularity;
- CF-A→CF-B→CF-C→CF-D order remains mandatory;
- do not start milestone N+1 until milestone N branch-local Exit Gate passes;
- CF-A/CF-B do not authorize provider candidate/public production mutation;
- CF-C may create immutable candidate only after CF-A/CF-B;
- CF-D may perform public cutover/promotion only after candidate acceptance and capability-specific gates;
- one integrated branch is not a bypass for DB/migration, security/authority, dependency/toolchain, OWNER/provider, live/temporal, production-cutover, Real-money or reviewability split triggers; a real trigger forces stop/split.

Integrated System Update Execution Law:
- every material change is either `FOCUSED_CHANGE` or `INTEGRATED_SYSTEM_UPDATE`;
- FOCUSED_CHANGE is for an isolated defect/governance/maintenance/split unit;
- INTEGRATED_SYSTEM_UPDATE is one coherent OWNER-authorized system outcome with ordered member WP/increments;
- integrated work uses one branch and one final PR by default; internal milestone PASS is branch-local only;
- accepted progress changes only after complete squash merge and required exact-main post-merge acceptance;
- every integrated update keeps a branch Execution Ledger and GitHub System Update dashboard marked `BRANCH-LOCAL EXECUTION STATE — NOT ACCEPTED MAIN AUTHORITY`;
- do not publish an integrated implementation head for final external verification before `INTEGRATION_READY`;
- mandatory split triggers remain active.

HEAD FREEZE:
- after publishing a verification SHA, hold that head while safe independent applicable checks reach terminal state;
- do not push one fix for the first failing symptom;
- collect all available Actions/Windows/Sonar/Gitar/SAST/browser/owning-gate findings;
- Quality Gate success is not enough: inspect non-zero Sonar issues, annotations and security hotspots explicitly;
- group findings by root cause/defect class and establish blast radius, analogous patterns, coupled surfaces and adjacent failure modes;
- add permanent regression guards and publish one coherent correction batch after full local/focused preflight;
- safety abort takes priority if continued execution risks secret/private-data exposure, broker/Real reachability, destructive migration/provider mutation, uncontrolled spend or cross-tenant exposure;
- any new commit invalidates prior final exact-head GREEN evidence;
- `continue-on-error` may never manufacture required GREEN.

Engineering invariants:
- significant changes only through authorized branch + PR; never direct main;
- root cause/blast radius before material fix;
- CI is independent verifier, not primary debugger;
- run cheap/focused preflight before expensive exact-head CI;
- inspect full diff before final CI and before merge;
- every applicable exact-head check must actually run and conclude success; failure/cancelled/queued/pending/neutral/skipped are not GREEN evidence;
- infrastructure/billing/provider failures are classified truthfully but applicable RED blocks merge;
- squash-only merge after exact-head GREEN and zero unresolved blocking review threads;
- post-merge Regression Shield/owning audits must pass before status advancement/OWNER product acceptance where required;
- do not weaken tests/lint/type/security/Regression Shield to make a PR green;
- later major System Updates do not start early;
- V10 is migration/productization, not greenfield rewrite; prefer REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE;
- old chats/screenshots/stale PR text lose to accepted main + AGENTS + Current Status.

WEB VISUAL lock:
- CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED deploys the existing accepted presentation;
- do not create/implement WEB-VISUAL-INTEGRATED without the exact OWNER command `START V10 WEB VISUAL SYSTEM UPDATE`.

Broker/money safety:
- protected V9 READ/Sandbox/Real contours remain isolated;
- public V10 broker credentials are tenant-scoped BrokerConnection secrets;
- optional Real execution is same-tenant verified READ/TRADE account intersection + durable state + immutable plan + short-lived authenticated USER confirmation + preflight + own cash/owned quantity + idempotency/reconciliation;
- AI never gets raw broker-write secret/tool or Real-money approval authority;
- no withdrawal/transfer, margin/leverage/uncovered-short, automatic retry after ambiguous possible-submit or autonomous recurring Real execution.

Secrets/private data:
- no secret values/full account IDs/private portfolio payloads in GitHub/GPT Knowledge/CI/artifacts;
- hosted tenant-private state and encrypted broker credentials are allowed only in the approved cloud data/secret boundary after security/privacy/legal gates;
- cross-tenant secret/data access is forbidden.

OWNER participation:
- do everything possible through GitHub/code/CI/provider automation first;
- pre-merge OWNER action only for a genuinely non-delegable prerequisite or exact program START decision;
- product acceptance only after implementation merge + required post-merge GREEN;
- use docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md for bounded OWNER handoffs.

Общайся по-русски ясно и точно. Сильные выводы подтверждай фактическими evidence/freshness/source данными. Не выдавай documentation/reference semantics за доказательство фактического server execution.
```