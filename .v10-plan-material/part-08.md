ьного решения - локально ввести trading token для OWNER execution contour.

37. Предоставить off-device backup место/диск или согласовать альтернативу.

38. Дать owner acceptance перед включением каждого потенциально опасного внешнего/Real режима.

# 19. Финальный Definition of Done V10

- GitHub является точным source of truth по коду, архитектуре, зависимостям, release и recovery.

- Lenovo автоматически возвращается в HEALTHY/DEGRADED safe state после reboot.

- Core работает без Custom GPT/OpenAI.

- Portfolio/read-only T-Invest слой имеет freshness/completeness и корректную identity.

- Watchtower реально обнаруживает material events, дедуплицирует и создаёт incidents.

- Research хранит provenance; AI можно выключить без поломки системы.

- Web полностью выполняет роль основного кабинета и показывает факты/риски/решения/планы/health.

- Telegram доставляет owner alerts и безопасно открывает нужный Web incident.

- Guardian формирует один основной decision либо честный blocker, а target sizing делает Optimizer.

- Shadow Mode пройден на реальном портфеле без unauthorized writes.

- Real execution требует exact immutable plan approval; drift останавливает plan.

- Idempotent replay не создаёт второй submit; ambiguous possible-submit ведёт только к reconciliation.

- Backup реально восстанавливается на fresh environment.

- Fault injection/security/soak tests проходят без P0/P1 blockers.

- Custom GPT можно отключить - Personal Omni-CIO продолжает мониторинг, анализ и Web/Telegram работу.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Определение 100%<br />
</strong>V10 считается завершённой только когда все 10 блоков и WP0-WP50 имеют COMPLETE по своим Exit Gate. Красивый сайт, работающий Telegram или даже один успешный real order отдельно не означают завершение программы.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 20. Реестр внешних технических ориентиров и источников

**Важно:** эти ссылки используются как planning references. Перед каждым implementation WP конкретные версии и требования должны быть повторно проверены по официальным источникам.

- **GitHub - Self-hosted runners reference:** [<u>https://docs.github.com/en/actions/reference/runners/self-hosted-runners</u>](https://docs.github.com/en/actions/reference/runners/self-hosted-runners) - Runner работает на собственной машине, принимает jobs по outbound HTTPS; требует своевременных обновлений.

- **GitHub - Adding self-hosted runners:** [<u>https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners</u>](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners) - GitHub рекомендует self-hosted runners использовать только с private repositories из-за риска выполнения кода из public forks/PR.

- **Telegram - Mini Apps:** [<u>https://core.telegram.org/bots/webapps</u>](https://core.telegram.org/bots/webapps) - Mini Apps позволяют использовать один mobile-first Web App внутри Telegram; initData требуется валидировать server-side и проверять freshness auth_date.

- **Ollama - Tool calling:** [<u>https://docs.ollama.com/capabilities/tool-calling</u>](https://docs.ollama.com/capabilities/tool-calling) - Локальный model provider может вызывать ограниченный allowlist tools.

- **Ollama - Structured outputs:** [<u>https://docs.ollama.com/capabilities/structured-outputs</u>](https://docs.ollama.com/capabilities/structured-outputs) - AI output можно принудительно ограничивать JSON schema.

- **React - Versions:** [<u>https://react.dev/versions</u>](https://react.dev/versions) - На момент формирования документа official docs указывают latest major 19.2.

- **Vite - Releases:** [<u>https://vite.dev/releases</u>](https://vite.dev/releases) - На момент формирования документа current supported line включает Vite 8.1; точный patch фиксировать перед WP2.

- **PostgreSQL - Versioning policy:** [<u>https://www.postgresql.org/support/versioning/</u>](https://www.postgresql.org/support/versioning/) - На момент формирования документа PostgreSQL 18.4 - текущий minor поддерживаемой ветки 18; использовать current supported minor на deployment date.

- **OWASP ASVS:** [<u>https://owasp.org/www-project-application-security-verification-standard/</u>](https://owasp.org/www-project-application-security-verification-standard/) - Latest stable ASVS 5.0.0 - baseline для Web/API security acceptance.

- **OWASP AISVS:** [<u>https://owasp.org/www-project-artificial-intelligence-security-verification-standard-aisvs-docs/</u>](https://owasp.org/www-project-artificial-intelligence-security-verification-standard-aisvs-docs/) - AISVS 1.0 released 24.06.2026 - дополнительный security checklist для AI-enabled части.

# Приложение A. Шаблон V10_CURRENT_PROGRAM_STATUS.md

**Рекомендуемая структура канонического файла прогресса:**

\# Omni-CIO V10 CURRENT PROGRAM STATUS  
  
Overall: 0% / 100%  
Current block: A  
Current WP: WP0  
State: NOT STARTED  
  
\## Blocks  
A Architecture ........ 0/5  
B GitHub/CI ........... 0/10  
C Lenovo Node ......... 0/15  
D Core/Data ........... 0/15  
E Web ................. 0/15  
F Telegram ............ 0/8  
G Research/AI ......... 0/12  
H Guardian ............ 0/8  
I Real Execution ...... 0/7  
J Hardening/Release ... 0/5  
  
\## Current blocker  
None  
  
\## Last accepted evidence  
- PR: ...  
- commit: ...  
- Regression Shield: ...  
  
\## Next exact step  
WP0 ...

# Приложение B. Шаблон PR для каждого WP

- Scope: только один WP/один defect set.

- Why: ссылка на master-plan и current status.

- Financial/safety boundaries: что изменяется и что явно не изменяется.

- Deliverables: список файлов/interfaces/migrations.

- Tests: unit/contract/integration/security/E2E.

- Rollback: как вернуть предыдущий accepted state.

- Owner action: none / exact ручное действие.

- Exit evidence: exact-head SHA, CI run, zero unresolved threads.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Финальная директива для будущей разработки<br />
</strong>Не оптимизировать скорость разработки ценой безопасности. Сначала устранить дефект и доказать исправление; только затем продолжать roadmap. Для real-money системы цена лишнего PR ниже цены одной неограниченной ошибки в production.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>
