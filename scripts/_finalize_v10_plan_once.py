from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md"
PDF = ROOT / "docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf"
SHA = ROOT / "docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.sha256"
LOCK = ROOT / "docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md"
AMEND = ROOT / "docs/master-plan/OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md"
AUDIT = ROOT / "docs/master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
AGENTS = ROOT / "AGENTS.md"
MP_README = ROOT / "docs/master-plan/README.md"

WEIGHTS = {"A": 5, "B": 9, "C": 12, "D": 14, "E": 14, "F": 8, "G": 18, "H": 8, "I": 7, "J": 5}


def replace_once(text: str, old: str, new: str, *, required: bool = True) -> str:
    if old not in text:
        if required:
            raise RuntimeError(f"Required anchor not found: {old[:100]!r}")
        return text
    return text.replace(old, new, 1)


def insert_before(text: str, anchor: str, block: str) -> str:
    if block.strip() in text:
        return text
    idx = text.find(anchor)
    if idx < 0:
        raise RuntimeError(f"Insert anchor not found: {anchor!r}")
    return text[:idx] + block.rstrip() + "\n\n" + text[idx:]


def consolidate_master() -> str:
    text = MASTER.read_text(encoding="utf-8")

    # Status / canonical paths / weights.
    text = text.replace("**Статус: DRAFT / разработка не начата**", "**Статус: OWNER-APPROVED / PROGRAM LOCKED / DEVELOPMENT NOT STARTED**")
    text = text.replace("knowledge/V10_CURRENT_PROGRAM_STATUS.md", "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md")
    text = text.replace("`V10_CURRENT_PROGRAM_STATUS.md`", "`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`")
    text = text.replace("# BLOCK B - GitHub, зависимости и CI/CD (10%)", "# BLOCK B - GitHub, зависимости и CI/CD (9%)")
    text = text.replace("# BLOCK C - Lenovo Omni-CIO Node (15%)", "# BLOCK C - Lenovo Omni-CIO Node (12%)")
    text = text.replace("# BLOCK D - V10 Core и данные (15%)", "# BLOCK D - V10 Core и данные (14%)")
    text = text.replace("# BLOCK E - Omni-CIO Web Platform (15%)", "# BLOCK E - Omni-CIO Web Platform (14%)")
    text = re.sub(r"B GitHub/CI\s+\.\.\.\.+\s+0/10", "B GitHub/CI ........... 0/9", text)
    text = re.sub(r"C Lenovo Node\s+\.\.\.\.+\s+0/15", "C Lenovo Node ......... 0/12", text)
    text = re.sub(r"D Core/Data\s+\.\.\.\.+\s+0/15", "D Core/Data ........... 0/14", text)
    text = re.sub(r"E Web\s+\.\.\.\.+\s+0/15", "E Web ................. 0/14", text)
    text = re.sub(r"G Research/AI\s+\.\.\.\.+\s+0/12", "G Research/AI ......... 0/18", text)
    text = text.replace("До этого этап остаётся DRAFT.", "До отдельной команды владельца `START V10` функциональная разработка остаётся запрещена, а прогресс остаётся 0%.")

    # Account-independence consolidation into the canonical architecture, not merely a side amendment.
    account_block = r'''## 1.1 Account Independence / Deployment Portability — обязательный архитектурный инвариант

V10 не принадлежит конкретному ChatGPT-аккаунту, разработчику, IDE, website-builder, хостингу или одному физическому компьютеру. Инженерный источник истины — private GitHub repository; runtime является заменяемым Data Plane.

```text
PRIVATE GITHUB REPOSITORY
  = engineering Control Plane / source of truth

  code / Web / API / Telegram / AI policy
  configuration schemas and safe defaults
  database migrations
  tests / CI / release manifests
  bootstrap / deployment / recovery runbooks
             |
             | reviewed release
             v
APPROVED V10 RUNTIME NODE
  = replaceable Data Plane

  local secret store
  broker credentials
  private portfolio/database state
  Decision Journal private payloads
  runtime cache / machine-specific state
```

Обязательные правила:

- Web является обычным source-controlled приложением и не может иметь authoritative state только в UI-builder/hosting dashboard;
- другой авторизованный разработчик должен восстановить engineering context из GitHub и продолжить branch -> tests -> PR -> review -> deploy без доступа к исходному ChatGPT-аккаунту;
- Lenovo — первый Personal V10 node, но не архитектурный владелец системы; перенос на другой approved node не должен требовать переписывания Web/Core;
- GitHub хранит код, схемы, policies и способы provisioning, но не реальные broker/Telegram tokens, encryption keys, полные account IDs или приватные portfolio payloads;
- GitHub engineering access никогда не означает broker trading authority;
- production release обязан идентифицироваться V10 version + Git SHA;
- до V10=100% обязателен clean-room portability/recovery rehearsal: GitHub + documented bootstrap + authorized backup + отдельно восстановленные secrets -> рабочий новый node;
- существующий `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` после этой консолидации сохраняется как audit trail исходного owner-approved amendment, но не как отдельный конкурирующий source of truth.
'''
    text = insert_before(text, "# 2. Неизменяемые инженерные правила", account_block)

    # Strengthen immutable engineering rules.
    rules_add = r'''
12. GitHub является единственным инженерным source of truth для Web/API/AI/Telegram/configuration contracts/migrations/deployment/recovery; account-only hidden configuration запрещена.

13. Доступ разработчика к GitHub не выдаёт broker/Telegram/encryption secrets и не расширяет real-money authority.

14. External Web ingress запрещён до отдельного TLS + OWNER authentication + session + CSRF/origin/host + rate-limit security gate. Real approval surface не публикуется наружу раньше этого gate.

15. Private local data и secret store должны учитывать угрозу физической потери Lenovo/SSD: full-disk или эквивалентная at-rest защита, отдельное хранение recovery key и проверяемое восстановление.

16. Системное время является security/data dependency: Windows/NTP clock sync контролируется; canonical timestamps хранятся в UTC; опасный clock drift блокирует short-lived confirmations, Telegram freshness checks и Real execution.

17. Logging/privacy policy задаётся до production: allowlist диагностических полей, обязательное masking/omission private data, log rotation/retention, crash-dump policy и audit-log integrity.

18. Runtime/OS/model updates выполняются как контролируемые изменения: Windows, GitHub Runner, NVIDIA driver, PostgreSQL, Ollama и AI model artifacts проходят compatibility/security/eval gate и имеют rollback; auto-update не может тихо изменить real-money behavior.
'''
    text = insert_before(text, "# 3. Модель прогресса и Definition of Done", rules_add)

    # WP0 canonical plan readiness requirements.
    wp0_add = r'''
### WP0 pre-development plan-acceptance gate

До первого feature-кода WP0 обязан подтвердить, что:

- этот Markdown и owner-readable PDF содержательно синхронизированы и имеют новый SHA-256 manifest;
- веса A-J везде одинаковы и суммируются ровно в 100%;
- canonical status path — только `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;
- AI/GPT migration и Account Independence уже находятся внутри канонического Master Plan;
- `OMNI_CIO_V10_PLAN_READINESS_AUDIT.md` не имеет открытых planning blockers;
- accepted `main` содержит V10 Program Lock;
- exact-head Regression Shield/security зелёный;
- V10 всё ещё 0% и не получает новых runtime/trading прав от самого факта утверждения плана.
'''
    text = insert_before(text, "# BLOCK B - GitHub", wp0_add)

    # WP1 account-controlled repository details.
    wp1_add = r'''
### WP1 mandatory portability additions

- Зафиксировать repository ownership Web/API/AI/Telegram/infrastructure/configuration artifacts.
- Запретить authoritative application settings, существующие только в личном account dashboard.
- Development/test environment должен воспроизводиться из repository documentation + dependency locks + safe local config examples.
- Hosting/domain replacement считается deployment/configuration change, а не созданием нового сайта.
'''
    text = insert_before(text, "## WP2 -", wp1_add)

    # WP4 release portability/supply chain additions.
    wp4_add = r'''
### WP4 mandatory release portability additions

- Accepted deploy выполняется только из reviewed Git commit/release evidence, не из untracked working tree.
- Release manifest фиксирует backend/frontend build hash, dependency/SBOM identity, migration version и Git SHA.
- Runtime `/system`/Admin UI показывает только non-secret installed version/Git SHA/build timestamp.
- Provider-specific deployment state минимизируется и документируется, чтобы перенос Lenovo -> другой approved node не создавал новый проект.
'''
    text = insert_before(text, "# BLOCK C - Lenovo", wp4_add)

    # WP5 hardware/OS hardening incl. physical loss and time sync.
    wp5_add = r'''
### WP5 mandatory 24/7 node hardening additions

Hardware/OS audit дополнительно обязан проверить и записать:

- фактическое состояние full-disk encryption (BitLocker where supported или owner-approved equivalent) и отдельный recovery-key custody plan;
- Windows Time/NTP health, UTC canonical time policy и допустимый clock-drift threshold;
- battery/AC behavior, restart after power loss, thermals under sustained AI load и safe shutdown behavior;
- SSD free-space threshold и low-disk fail-safe;
- network interface/firewall baseline и запрет случайного public listener;
- какая часть данных считается private-at-rest и какие процессы имеют к ней ACL.

Exit Gate WP5 дополнительно: сценарий физической потери выключенного диска не должен автоматически раскрывать broker secrets/private DB; clock drift выше принятого threshold детектируется и блокирует чувствительные операции.
'''
    text = insert_before(text, "## WP6 -", wp5_add)

    # WP6 privilege separation improvements.
    wp6_add = r'''
### WP6 mandatory privilege additions

- `omni-ci-runner` не получает право читать `TINVEST_TRADING_TOKEN`/Telegram secret/private DB dumps.
- `omni-cio-runtime` запускается с минимальными локальными ACL и не является Windows administrator без доказанной необходимости.
- Deployment controller принимает только reviewed release identity и не исполняет произвольный PR payload в контексте trading secrets.
- GitHub collaborator role и runtime-secret provisioning являются двумя независимыми процедурами.
'''
    text = insert_before(text, "## WP7 -", wp6_add)

    wp8_add = r'''
### WP8 mandatory secret lifecycle additions

- Для каждого секрета определить owner, purpose, scope, rotation/revocation procedure и признак компрометации.
- Recovery keys/private encryption material хранятся отдельно от GitHub и отдельно от зашифрованного backup, который они защищают.
- Никакой diagnostic bundle/crash dump не может включать raw secrets.
'''
    text = insert_before(text, "## WP9 -", wp8_add)

    # WP9 operational patching/logging/time.
    wp9_add = r'''
### WP9A - Runtime patching, time, observability и controlled restart policy

До 24/7 эксплуатации создать единый operations contract для:

- Windows security updates и predictable maintenance/reboot window;
- GitHub Runner update health;
- NVIDIA driver updates;
- PostgreSQL minor/security updates;
- Ollama runtime/model updates;
- service restart backoff, crash-loop detection и owner alert;
- NTP/time-drift monitoring;
- CPU/RAM/GPU/VRAM/temperature/disk thresholds;
- structured logging с private-data allowlist, rotation/retention и crash-dump policy.

Любой update, способный изменить calculations, AI behavior, DB compatibility или broker execution path, сначала проходит staging/regression/eval и имеет documented rollback.
'''
    text = insert_before(text, "## WP10 -", wp9_add)

    # WP10 RPO/RTO.
    wp10_add = r'''
### WP10 mandatory recovery objectives

WP10 обязан определить измеримые значения:

- **RPO (Recovery Point Objective)** — максимально допустимую потерю private durable state;
- **RTO (Recovery Time Objective)** — максимально допустимое время восстановления Personal V10 node;
- backup frequency/retention/off-device policy, выведенные из этих целей;
- отдельные recovery paths для GitHub-controlled source, encrypted DB/private state и runtime secrets.

Точные числа выбираются после WP5 hardware/storage audit, но отсутствие определённых и протестированных RPO/RTO является blocker для Exit Gate WP10.
'''
    text = insert_before(text, "# BLOCK D - V10 Core", wp10_add)

    # Domain data time semantics.
    wp12_add = r'''
### WP12 mandatory temporal/data identity additions

- Все persisted timestamps имеют явную timezone semantics; canonical storage — UTC, display timezone — presentation concern.
- Market/evidence timestamps различают `published_at`, `retrieved_at`, broker/server time и local receive time.
- Instrument/account/portfolio identities versioned; никакая AI/news строка не связывается с позицией только по похожему имени.
'''
    text = insert_before(text, "## WP13 -", wp12_add)

    # Web external auth gate before Telegram block.
    web_gate = r'''
## WP22A - External Web Access / OWNER Authentication Security Gate

**Цель:** Не превращать локальный Personal кабинет в публично доступную поверхность до завершения security design.

**Обязательные deliverables**

- Решить, нужен ли вообще public ingress; безопасный private remote-access вариант рассматривается первым.
- Если внешний ingress нужен: TLS termination, certificate issuance/renewal, HSTS/host allowlist, trusted reverse-proxy chain.
- Отдельная OWNER authentication для ordinary browser; Telegram Mini App identity не является единственным способом входа.
- Server-side sessions: short/defined lifetime, rotation, explicit revoke/logout, secure/HttpOnly/SameSite cookies или эквивалентный reviewed механизм.
- CSRF protection, Origin/Referer/Host checks где применимо, CORS deny-by-default.
- Login/API rate limiting и lockout/abuse policy без возможности self-DoS критического monitoring path.
- Real-plan approval endpoint требует step-up/recent OWNER authentication и никогда не доверяет только deep-link URL.
- External ingress configuration repository-controlled; secret keys/cert private material остаются runtime-only.

**Обязательная проверка**

- ASVS 5.0.0 relevant controls; invalid/stolen/expired session; CSRF; host-header; origin; brute-force/rate-limit; direct API call without UI; Telegram initData replay/staleness.

**Exit Gate**

- До green gate Web остаётся local/private; Real approval surface не публикуется наружу.
'''
    text = insert_before(text, "# BLOCK F - Telegram", web_gate)

    # Telegram security freshness and direct browser relation.
    tg_add = r'''
### Telegram authentication invariant

- Backend принимает Telegram identity только из валидированного `Telegram.WebApp.initData`; `initDataUnsafe` не является trusted authority.
- `auth_date` freshness проверяется server-side; replay/expired Mini App sessions отвергаются.
- Telegram OWNER ID whitelist не заменяет Web session security и не выдаёт broker secret.
'''
    text = insert_before(text, "## WP25 -", tg_add)

    # Research source rights / raw content handling.
    wp27_add = r'''
### WP27 source-governance additions

Для каждого внешнего source registry хранит не только authority/freshness, но и:

- supported retrieval method/API/public page;
- terms/license/redistribution constraints, если применимы;
- parser version;
- expected update cadence;
- allowed retention of raw content vs normalized evidence.

Недоступный или юридически/технически запрещённый способ получения данных не обходится scraping-hack'ом без отдельного review.
'''
    text = insert_before(text, "## WP28 -", wp27_add)

    # AI model provenance and update policy.
    wp31_add = r'''
### WP31 mandatory model provenance / capacity additions

Каждый AI candidate фиксирует:

- exact model name/version/digest/quantization;
- license and source repository;
- expected RAM/VRAM/context limits;
- measured latency/throughput/thermal profile on Lenovo;
- eval-suite result and accepted threshold;
- rollback artifact/previous accepted model.

Model/runtime auto-update запрещён. Новая модель становится accepted только после повторного Omni-CIO eval и security/tool-authority checks.
'''
    text = insert_before(text, "## WP32 -", wp31_add)

    # AI injection/data exfil safety.
    ai_security = r'''
### AI/RAG security invariant

- External documents/news are untrusted data, never System Policy or tool authorization.
- Prompt-injection-shaped content cannot expand Tool Registry authority, reveal secrets or disable deterministic safety gates.
- Retrieved chunks carry provenance and are filtered/escaped before model use; model output remains untrusted until schema/evidence validation.
- AI context/logging avoids raw broker secrets/private identifiers; tool results expose least data required.
'''
    text = insert_before(text, "## WP33 -", ai_security)

    # Shadow mode duration is evidence based, not arbitrary, and fallback behavior.
    shadow_add = r'''
### WP39 Shadow Mode acceptance criteria

Shadow duration is not a calendar checkbox. Exit requires enough representative incidents to exercise normal, stale-data, contradictory-research, AI-unavailable, broker-unavailable and no-action cases. If natural incidents are insufficient, deterministic replay/synthetic scenarios supplement, but do not falsify live evidence.
'''
    text = insert_before(text, "## WP40 -", shadow_add)

    # Real execution clock/auth/degraded constraints.
    real_add = r'''
### Real execution additional preconditions

Real submit is additionally blocked when any of the following is true:

- system clock/time sync unhealthy beyond accepted threshold;
- OWNER session/confirmation expired or cannot be cryptographically bound to exact plan hash;
- durable state/DB is read-only, degraded or reconciliation state unknown;
- audit log cannot persist required immutable execution evidence;
- external ingress/auth gate is not green for the surface from which approval arrives.
'''
    text = insert_before(text, "## WP42 -", real_add)

    # WP47 security acceptance expanded.
    wp47_add = r'''
### WP47 mandatory expanded security acceptance

Security acceptance must explicitly cover:

- at-rest protection / physical disk-loss threat;
- OWNER browser auth, Telegram initData validation, session revocation and step-up approval;
- TLS/certificate/reverse-proxy configuration if external ingress enabled;
- CSRF/CORS/Origin/Host and external rate limits;
- GitHub runner -> deploy controller -> runtime privilege boundary;
- secret rotation/revocation and diagnostic/crash-dump leakage;
- logging allowlist, masking, retention and audit integrity;
- AI prompt injection, poisoned RAG, tool escalation/excessive agency and data exfiltration checks using OWASP AISVS as a verification baseline;
- dependency/SBOM/license findings and exact exceptions with owner-approved rationale.
'''
    text = insert_before(text, "## WP48 -", wp47_add)

    # WP48 soak specifics incl hardware and clock.
    wp48_add = r'''
### WP48 24/7 soak specifics

Soak test records CPU/RAM/GPU/VRAM, GPU/CPU temperatures, disk growth/free-space, DB size, queue depth, restart count, clock drift, Telegram/Web latency, AI latency and Watchtower cycle timing. Threshold breach must create a bounded alert rather than silently degrading into unsafe Real behavior.
'''
    text = insert_before(text, "## WP49 -", wp48_add)

    # WP49 portability + RPO/RTO proof.
    wp49_add = r'''
### WP49 mandatory clean-room portability and RPO/RTO proof

Disaster Recovery rehearsal is simultaneously the Account Independence acceptance test:

1. Start from a fresh approved machine/environment with no original developer working tree.
2. Restore source/release only from accepted GitHub evidence.
3. Run documented bootstrap/deployment.
4. Restore authorized encrypted private backup.
5. Restore runtime secrets through the separate documented secret procedure.
6. Prove installed V10 version/Git SHA.
7. Prove measured recovery meets accepted RPO/RTO.
8. Prove another authorized developer can modify/test Web without receiving OWNER trading credentials.
9. Prove no hidden ChatGPT/website-builder/hosting-dashboard setting is required.

Failure of any point blocks WP50.
'''
    text = insert_before(text, "## WP50 -", wp49_add)

    # Final DoD additions.
    final_add = r'''
## 19.1 Final pre-release evidence matrix

Перед `V10 = 100% COMPLETE` должна существовать evidence matrix, связывающая каждую заявленную capability с:

`requirement -> implementation commit -> deterministic tests -> security control -> runtime/shadow evidence -> rollback/recovery evidence -> owner acceptance where required`.

Ни сайт, ни презентация, ни AI-текст не являются доказательством capability без этой цепочки. Любая функция, не имеющая evidence chain, считается незавершённой или явно исключённой из release scope.
'''
    text = insert_before(text, "# 20. Реестр внешних технических ориентиров", final_add)

    # Refresh planning references with current audit baseline but still require implementation-time recheck.
    reference_add = r'''
### Technical baseline re-check — 05.08.2026

На этапе финальной проверки плана официальные источники подтверждали следующие ориентиры (версии всё равно перепроверяются перед WP2/WP31 implementation):

- React docs: latest documented line 19.2;
- Vite: 8.1 current supported minor line;
- PostgreSQL: 18.4 current stable release line (PostgreSQL 19 на дату аудита был beta, поэтому не является production baseline V10);
- OWASP ASVS: latest stable 5.0.0;
- OWASP AISVS: version 1.0 live since 24.06.2026;
- Telegram Mini Apps: server-side validation of `initData` + freshness check via `auth_date`;
- Ollama: tool calling + JSON-schema structured outputs supported;
- T-Invest: read-only token cannot place orders; account-specific token scoping available;
- GitHub: self-hosted runner uses outbound HTTPS and private-repository use remains the recommended safety posture.
'''
    text = insert_before(text, "# Приложение A.", reference_add)

    # Appendix status template normalization.
    text = text.replace("B GitHub/CI ........... 0/10", "B GitHub/CI ........... 0/9")
    text = text.replace("C Lenovo Node ......... 0/15", "C Lenovo Node ......... 0/12")
    text = text.replace("D Core/Data ........... 0/15", "D Core/Data ........... 0/14")
    text = text.replace("E Web ................. 0/15", "E Web ................. 0/14")
    text = text.replace("G Research/AI ......... 0/12", "G Research/AI ......... 0/18")

    MASTER.write_text(text, encoding="utf-8")
    return text


def update_supporting_docs() -> None:
    # Program lock: amendment is now incorporated; retained as audit trail.
    text = LOCK.read_text(encoding="utf-8")
    text = text.replace(
        "Mandatory portability amendment: `docs/master-plan/OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`",
        "Account-independence audit trail: `docs/master-plan/OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` (requirements consolidated into canonical Master Plan)",
    )
    text = text.replace(
        "These hashes identify the current paired base-plan revision. The mandatory amendment is separately version-controlled and does not silently mutate the hashed base artifacts. **Before V10 feature implementation begins, all owner-approved mandatory amendments must be reconciled/consolidated into the next paired Master Plan Markdown/PDF revision and the integrity manifest must be regenerated.** No feature code may start while the canonical plan artifacts and the mandatory-amendment set disagree.",
        "The current canonical Master Plan revision consolidates all owner-approved 0%-phase amendments, including AI/GPT migration and Account Independence / Deployment Portability. The standalone amendment remains only as an audit trail. Markdown/PDF integrity is tracked by the regenerated manifest; feature work must stop if substantive divergence is later introduced.",
    )
    text = text.replace(
        "Before the first feature-development WP starts, the owner-approved mandatory amendments recorded during the 0% planning phase must be consolidated into the canonical paired Master Plan artifacts and their hashes regenerated.",
        "Before the first feature-development WP starts, accepted `main` must contain this consolidated canonical paired Master Plan, its regenerated integrity manifest, a green plan-readiness audit and exact-head CI.",
    )
    text = text.replace(
        "4. owner-approved mandatory V10 amendments referenced by this Program Lock, currently including `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`;\n5. the paired canonical V10 program: `OMNI_CIO_V10_MASTER_PLAN.md` + `Omni-CIO_V10_Master_Plan_RU.pdf` after mandatory-amendment consolidation;\n6. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;\n7. relevant V10 architecture/runbook files created by the current work package;\n8. current PR/CI evidence.",
        "4. the paired canonical V10 program: `OMNI_CIO_V10_MASTER_PLAN.md` + `Omni-CIO_V10_Master_Plan_RU.pdf`;\n5. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;\n6. historical amendment/audit records, including `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`;\n7. relevant V10 architecture/runbook files created by the current work package;\n8. current PR/CI evidence.",
    )
    text = text.replace(
        "If the Markdown and PDF ever differ in substantive program content, or a mandatory amendment has not yet been consolidated before feature implementation, V10 feature development must stop until the discrepancy is resolved through an owner-reviewed documentation PR.",
        "If the Markdown and PDF ever differ in substantive program content, V10 feature development must stop until the discrepancy is resolved through an owner-reviewed documentation PR and regenerated integrity manifest.",
    )
    if "## 8. Final planning-readiness invariant" not in text:
        text += r'''

## 8. Final planning-readiness invariant

Before `START V10`, accepted `main` must prove:

- canonical Markdown/PDF are synchronized and SHA-256 tracked;
- weights A-J are 5/9/12/14/14/8/18/8/7/5 = 100%;
- Account Independence and AI/GPT migration are inside the canonical plan;
- disk-at-rest, RPO/RTO, Web TLS/auth, runtime update, time-sync and logging/privacy requirements are explicit;
- `OMNI_CIO_V10_PLAN_READINESS_AUDIT.md` has no open planning blocker;
- exact-head Regression Shield/security are green;
- plan is merged to `main` while V10 implementation progress remains 0%.
'''
    LOCK.write_text(text, encoding="utf-8")

    # Status: consolidation complete, wait for explicit START only after merge.
    text = STATUS.read_text(encoding="utf-8")
    text = text.replace(
        "Omni-CIO V10 is **OWNER-APPROVED / PROGRAM LOCKED / DEVELOPMENT NOT STARTED**.",
        "Omni-CIO V10 is **OWNER-APPROVED / PROGRAM LOCKED / PLAN CONSOLIDATED / DEVELOPMENT NOT STARTED**.",
    )
    text = text.replace(
        "Mandatory planning amendments recorded before implementation:\n\n- `docs/master-plan/OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md`",
        "Consolidated planning scope:\n\n- AI/GPT migration requirements are embedded in the canonical Master Plan;\n- Account Independence / Deployment Portability requirements are embedded in the canonical Master Plan;\n- `docs/master-plan/OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` is retained as the audit trail of the original amendment;\n- `docs/master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md` records final pre-development acceptance checks.",
    )
    old = "Before the owner authorizes the first V10 feature implementation, all mandatory 0%-phase amendments must be reconciled/consolidated into the next paired Master Plan Markdown/PDF revision and its SHA-256 manifest must be regenerated. No feature code may begin from a split or contradictory plan set.\n\nNext implementation WP after explicit owner start instruction and canonical-plan consolidation: **WP0 — V10 Program Lock / Architecture Freeze verification**, followed by the canonical sequence."
    new = "Canonical-plan consolidation is complete on the planning branch: Markdown/PDF are regenerated together and the manifest is regenerated. Remaining acceptance gates are exact-head green CI, zero unresolved review blockers and squash merge of PR #227 to `main`.\n\nAfter those gates, the plan state becomes **READY — WAITING FOR EXPLICIT OWNER `START V10` COMMAND** while implementation progress remains 0%. The first implementation WP is **WP0 — V10 Program Lock / Architecture Freeze verification**, followed by the canonical sequence."
    text = text.replace(old, new)
    if "## Planning acceptance additions" not in text:
        text += r'''

## Planning acceptance additions

The final canonical plan explicitly includes: full-disk/private-state at-rest protection; measured RPO/RTO; external TLS/direct-browser OWNER-auth/session/rate-limit gate; runtime/OS/driver/DB/Ollama/model controlled-update policy; time synchronization/UTC semantics; logging/privacy/retention/crash-dump policy; and clean-room deployment portability.
'''
    STATUS.write_text(text, encoding="utf-8")

    # Readiness audit: close substantive blockers, leave procedural PR/CI gates.
    text = AUDIT.read_text(encoding="utf-8")
    text = text.replace(
        "Readiness verdict at this audit: **NOT READY TO START FEATURE IMPLEMENTATION YET**",
        "Readiness verdict after consolidation: **SUBSTANTIVE PLAN READY; PROCEDURAL PR/CI ACCEPTANCE PENDING**",
    )
    if "## 8. Consolidation closure record" not in text:
        text += r'''

## 8. Consolidation closure record

The canonical-plan finalization closes the substantive findings as follows:

- **B1 CLOSED** — Account Independence requirements are incorporated into canonical Markdown/PDF; amendment retained only as audit trail.
- **B2 CLOSED** — all canonical progress weights normalized to A/B/C/D/E/F/G/H/I/J = 5/9/12/14/14/8/18/8/7/5 = 100%.
- **B3 CLOSED** — canonical status path normalized to `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.
- **B4 CLOSED** — canonical plan status normalized to OWNER-APPROVED / PROGRAM LOCKED / DEVELOPMENT NOT STARTED.
- **S1 INCORPORATED** — at-rest/full-disk/private-state physical-loss requirements added.
- **S2 INCORPORATED** — RPO/RTO definition and measured recovery evidence required.
- **S3 INCORPORATED** — external Web TLS/direct-browser OWNER auth/session/CSRF/origin/host/rate-limit gate added.
- **S4 INCORPORATED** — Windows/runner/driver/PostgreSQL/Ollama/model controlled-update and rollback policy added.
- **S5 INCORPORATED** — logging/privacy/retention/crash-dump/audit integrity policy added.
- Additional prevention controls added for clock/NTP drift, UTC timestamp semantics, AI model provenance, source-governance/retention and clean-room portability.

The only remaining gates are procedural:

- **B5** closes when PR #227 is squash-merged to accepted `main` after owner/plan acceptance.
- **B6** closes when the final exact-head Regression Shield/security is green.

No feature implementation is authorized by this closure record.
'''
    AUDIT.write_text(text, encoding="utf-8")

    # Master-plan README navigation should no longer look V9-only.
    text = MP_README.read_text(encoding="utf-8")
    text = text.replace(
        "Эта папка хранит **завершённые owner-approved спецификации и audit trail** развития Omni-CIO. Она не является текущей очередью незавершённых задач.",
        "Эта папка хранит **owner-approved master programs, program locks и audit trail** развития Omni-CIO. Завершённые программы не являются очередью задач; активная программа определяется её Program Lock/Current Status.",
    )
    v10_section = r'''
## Omni-CIO V10 Personal Autonomous Investment Platform — approved plan, implementation 0%

Canonical planning artifacts:

- `OMNI_CIO_V10_MASTER_PLAN.md` — searchable canonical program for developers/AI/code review;
- `Omni-CIO_V10_Master_Plan_RU.pdf` — owner-readable synchronized copy;
- `OMNI_CIO_V10_MASTER_PLAN.sha256` — integrity manifest;
- `OMNI_CIO_V10_PROGRAM_LOCK.md` — scope/precedence/exclusivity lock;
- `OMNI_CIO_V10_PLAN_READINESS_AUDIT.md` — pre-development readiness audit;
- `OMNI_CIO_V10_ACCOUNT_INDEPENDENCE_AMENDMENT.md` — historical owner-approved amendment retained as audit trail after consolidation.

Current V10 progress authority: `../../knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

V10 feature implementation remains **0% / NOT STARTED** until an explicit owner `START V10` instruction after the program-lock PR is accepted into `main`. V9 remains the protected runtime/recovery baseline until a future V10 work package intentionally replaces a boundary and passes its exit gate.

'''
    if "## Omni-CIO V10 Personal Autonomous" not in text:
        text = insert_before(text, "## Omni-CIO v9 Portfolio Autopilot", v10_section)
    MP_README.write_text(text, encoding="utf-8")

    # AGENTS: canonical MD first, PDF paired; readiness gate explicit.
    text = AGENTS.read_text(encoding="utf-8")
    text = text.replace(
        "Owner-approved/program-locked next program:\n\n`docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`",
        "Owner-approved/program-locked next program:\n\n`docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`\n\nPaired owner-readable PDF:\n\n`docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`",
    )
    text = text.replace(
        "4. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;\n5. `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;\n6. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;",
        "4. `docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md`;\n5. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;\n6. `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;\n7. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;",
    )
    if "V10 planning-readiness rule:" not in text:
        marker = "The V10 program lock does **not** itself authorize implementation. V10 feature work begins only after a new explicit owner instruction to start V10 development."
        addition = marker + "\n\nV10 planning-readiness rule: before that start instruction, accepted `main` must contain the consolidated Markdown/PDF pair + regenerated SHA-256 manifest + plan-readiness audit, exact-head CI/security must be green, and V10 must still be 0%."
        text = text.replace(marker, addition)
    AGENTS.write_text(text, encoding="utf-8")

    # Keep the amendment, but state consolidation to prevent split authority.
    text = AMEND.read_text(encoding="utf-8")
    if "## 10. Consolidation status" not in text:
        text += r'''

## 10. Consolidation status

This amendment's mandatory requirements have been incorporated into the canonical `OMNI_CIO_V10_MASTER_PLAN.md` and regenerated paired PDF during the final plan-readiness pass. This file is retained as historical owner-approved audit evidence. It is no longer a competing source of truth; if wording differs, the accepted canonical Master Plan + Program Lock govern future implementation.
'''
    AMEND.write_text(text, encoding="utf-8")


def render_pdf(markdown_text: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer

    font_candidates = [
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    ]
    regular = bold = None
    for r, b in font_candidates:
        if r.exists() and b.exists():
            regular, bold = r, b
            break
    if not regular:
        raise RuntimeError("No Cyrillic-capable TTF font found")
    pdfmetrics.registerFont(TTFont("V10Sans", str(regular)))
    pdfmetrics.registerFont(TTFont("V10Sans-Bold", str(bold)))

    doc = SimpleDocTemplate(
        str(PDF), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=17 * mm, bottomMargin=17 * mm,
        title="Omni-CIO V10 Master Plan", author="Omni-CIO project",
    )
    styles = getSampleStyleSheet()
    base = ParagraphStyle("V10Body", parent=styles["BodyText"], fontName="V10Sans", fontSize=8.6, leading=11.5, spaceAfter=4)
    h1 = ParagraphStyle("V10H1", parent=base, fontName="V10Sans-Bold", fontSize=15, leading=18, spaceBefore=9, spaceAfter=7)
    h2 = ParagraphStyle("V10H2", parent=base, fontName="V10Sans-Bold", fontSize=12, leading=15, spaceBefore=8, spaceAfter=5)
    h3 = ParagraphStyle("V10H3", parent=base, fontName="V10Sans-Bold", fontSize=10, leading=13, spaceBefore=6, spaceAfter=4)
    title = ParagraphStyle("V10Title", parent=h1, fontSize=19, leading=23, alignment=TA_CENTER, textColor=colors.HexColor("#162033"), spaceAfter=10)
    code = ParagraphStyle("V10Code", parent=base, fontName="V10Sans", fontSize=7.5, leading=9.5, leftIndent=6, backColor=colors.HexColor("#F2F4F7"), borderPadding=5)

    def safe_inline(s: str) -> str:
        s = re.sub(r"<[^>]+>", " ", s)
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<font name='V10Sans'>\1</font>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", s)
        return s

    story = []
    in_code = False
    code_lines: list[str] = []
    first_heading = True
    for raw in markdown_text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if not in_code:
                in_code = True
                code_lines = []
            else:
                story.append(Preformatted("\n".join(code_lines), code))
                story.append(Spacer(1, 3))
                in_code = False
            continue
        if in_code:
            code_lines.append(line.replace("\\|", "|"))
            continue
        if not line.strip():
            continue
        if line.startswith("# "):
            if not first_heading:
                story.append(PageBreak())
            story.append(Paragraph(safe_inline(line[2:]), title if first_heading else h1))
            first_heading = False
        elif line.startswith("## "):
            story.append(Paragraph(safe_inline(line[3:]), h2))
        elif line.startswith("### "):
            story.append(Paragraph(safe_inline(line[4:]), h3))
        elif line.startswith("| ") or line.startswith("|-") or line.startswith("| **"):
            story.append(Preformatted(line, code))
        elif re.match(r"^\s*[-*]\s+", line):
            body = re.sub(r"^\s*[-*]\s+", "", line)
            story.append(Paragraph("• " + safe_inline(body), base))
        elif re.match(r"^\s*\d+\.\s+", line):
            story.append(Paragraph(safe_inline(line), base))
        else:
            cleaned = line.replace("<table>", "").replace("</table>", "")
            if re.match(r"^<.*>$", cleaned.strip()):
                continue
            story.append(Paragraph(safe_inline(cleaned), base))

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("V10Sans", 7)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(16 * mm, 9 * mm, "Omni-CIO V10 Master Plan - canonical planning document")
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def write_manifest() -> None:
    lines = []
    for path in (PDF, MASTER):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    SHA.write_text("\n".join(lines) + "\n", encoding="utf-8")


def checks() -> None:
    text = MASTER.read_text(encoding="utf-8")
    assert "DRAFT / разработка не начата" not in text
    assert "knowledge/V10_CURRENT_PROGRAM_STATUS.md" not in text
    assert "`V10_CURRENT_PROGRAM_STATUS.md`" not in text
    assert sum(WEIGHTS.values()) == 100
    for letter, weight in WEIGHTS.items():
        table_re = rf"\| {letter}\s+\|[^\n]+\| {weight}%"
        assert re.search(table_re, text), f"Weight table missing {letter}={weight}"
    for expected in [
        "# BLOCK B - GitHub, зависимости и CI/CD (9%)",
        "# BLOCK C - Lenovo Omni-CIO Node (12%)",
        "# BLOCK D - V10 Core и данные (14%)",
        "# BLOCK E - Omni-CIO Web Platform (14%)",
        "Account Independence / Deployment Portability",
        "RPO (Recovery Point Objective)",
        "RTO (Recovery Time Objective)",
        "External Web Access / OWNER Authentication Security Gate",
        "full-disk encryption",
        "clock-drift",
        "Logging/privacy policy",
        "Model/runtime auto-update запрещён",
        "clean-room portability",
        "OWASP AISVS",
        "Custom GPT",
    ]:
        assert expected in text, f"Missing required consolidated requirement: {expected}"
    assert PDF.exists() and PDF.stat().st_size > 100_000
    from pypdf import PdfReader
    reader = PdfReader(str(PDF))
    assert len(reader.pages) >= 20, f"Unexpected PDF page count: {len(reader.pages)}"
    extracted = "\n".join((p.extract_text() or "") for p in reader.pages[:5])
    assert "Omni-CIO" in extracted and "V10" in extracted
    manifest = SHA.read_text(encoding="utf-8")
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() in manifest
    assert hashlib.sha256(MASTER.read_bytes()).hexdigest() in manifest


def main() -> None:
    markdown = consolidate_master()
    update_supporting_docs()
    # Reload after support docs in case no master changes are needed elsewhere.
    markdown = MASTER.read_text(encoding="utf-8")
    render_pdf(markdown)
    write_manifest()
    checks()
    print(f"V10 plan consolidated: {MASTER.stat().st_size} bytes")
    print(f"PDF: {PDF.stat().st_size} bytes")
    print(SHA.read_text(encoding='utf-8'))


if __name__ == "__main__":
    main()
