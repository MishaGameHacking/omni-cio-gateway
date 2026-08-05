from pathlib import Path

master_path = Path('docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md')
lock_path = Path('docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md')
status_path = Path('knowledge/17_V10_CURRENT_PROGRAM_STATUS.md')
agents_path = Path('AGENTS.md')

master = master_path.read_text(encoding='utf-8')

master = master.replace(
    '- BLOCK G - Research + Local AI',
    '- BLOCK G - AI Copilot, Research Intelligence и GPT Migration',
)
master = master.replace(
    'Затем Research/AI. Затем Guardian.',
    'Затем AI Copilot/Research Intelligence. Затем Guardian.',
)
master = master.replace(
    '**Главная цель:** вынести Omni-CIO из обязательной зависимости от Custom GPT и превратить готовый V9 в самостоятельную персональную инвестиционную операционную систему, работающую 24/7 на постоянно включённом Lenovo, управляемую через GitHub, с единым сайтом, Telegram-оповещениями и опциональным локальным AI Researcher.',
    '**Главная цель:** вынести Omni-CIO из обязательной зависимости от Custom GPT и превратить готовый V9 в самостоятельную персональную инвестиционную операционную систему, работающую 24/7 на постоянно включённом Lenovo, управляемую через GitHub, с единым сайтом, Telegram-оповещениями и собственным Omni-CIO AI Copilot / Agent Orchestrator. AI-provider является сменным (локальный open-weight/Ollama first), а финансовый Core обязан сохранять безопасную детерминированную работу и явный degraded mode при недоступности AI.',
)
master = master.replace(
    '- Local AI - сменный Research Intelligence Layer. Его отсутствие не ломает Core и не даёт модели прямых прав на брокерские записи.',
    '- Omni-CIO AI Copilot / Agent Orchestrator - собственный conversational и orchestration layer внутри Web/Telegram, который заменяет обязательную зависимость от Custom GPT, использует только разрешённые tools Core и не получает прямого broker-write authority.\n\n- Local/replaceable AI Provider - локальный open-weight provider через Ollama является первым кандидатом; provider может быть заменён без переписывания Core. Недоступность AI не ломает финансовые safety engines.\n\n- GPT Knowledge Migration - Instructions, Knowledge, Actions contracts, полезные prompt/workflow patterns и recovery-конфигурация существующего GPT сохраняются, нормализуются и мигрируют в versioned System Policy + Knowledge/RAG + Tool Registry. Custom GPT не удаляется до отдельного parity/decommission gate.',
)
master = master.replace(
    '\\|-- Research Collector / Optional AI',
    '\\|-- Research Collector / AI Copilot / Research Agent',
)
master = master.replace(
    '4.  AI не имеет прямого PostOrder/execute права. AI создаёт структурированное research/evidence; финансовые ограничения, sizing и execution authority находятся в детерминированном Core.',
    '4.  AI не имеет прямого PostOrder/execute права. AI Copilot может вести диалог, запускать allowlisted read-only/analytical tools, собирать и объяснять research/evidence и оркестрировать безопасные аналитические workflows; финансовые ограничения, sizing, immutable plan approval и execution authority находятся в детерминированном Core.',
)

table_start = master.index('| **Блок** | **Назначение**')
table_end = master.index('- Процент блока засчитывается', table_start)
new_table = '''| **Блок** | **Назначение**                                      | **Вес** | **Статус при старте** |
|----------|-----------------------------------------------------|---------|-----------------------|
| A        | Архитектура и защита V9                             | 5%      | NOT STARTED           |
| B        | GitHub, зависимости и CI/CD                         | 9%      | NOT STARTED           |
| C        | Lenovo Node / инфраструктура                        | 12%     | NOT STARTED           |
| D        | V10 Core и данные                                   | 14%     | NOT STARTED           |
| E        | Web Platform                                        | 14%     | NOT STARTED           |
| F        | Telegram                                            | 8%      | NOT STARTED           |
| G        | AI Copilot, Research Intelligence и GPT Migration   | 18%     | NOT STARTED           |
| H        | Guardian / Watchtower Loop                          | 8%      | NOT STARTED           |
| I        | Personal Real Execution                             | 7%      | NOT STARTED           |
| J        | Hardening / Recovery / Release                      | 5%      | NOT STARTED           |

'''
master = master[:table_start] + new_table + master[table_end:]
master = master.replace(
    '# BLOCK G - Research + Local AI (12%)',
    '# BLOCK G - AI Copilot, Research Intelligence и GPT Migration (18%)',
)

marker_wp31 = '## WP31 - Lenovo AI Benchmark и model selection\n'
if marker_wp31 not in master:
    raise SystemExit('WP31 marker not found')
insert_30 = '''## WP30A - GPT Knowledge Migration и canonical AI knowledge source

**Цель:** Не потерять интеллект, правила и накопленные знания существующего Custom GPT при переходе на собственный AI layer.

**Результаты / deliverables**

- Инвентаризировать и version-control текущие GPT Instructions, Knowledge files, Actions/OpenAPI contracts, setup/recovery configuration и полезные workflow/prompt patterns.

- Разделить мигрируемый материал на: `SYSTEM_POLICY` (поведение/границы), `KNOWLEDGE_RAG` (справочные знания), `TOOL_CONTRACTS` (разрешённые действия), `REFERENCE_GPT` (архив/recovery).

- Не переносить устаревшие исторические инструкции как current authority; каждая запись получает source/version/status.

- Никакие секреты, реальные broker payloads или приватные conversation exports не коммитятся в GitHub.

**Обязательная проверка**

- Diff/inventory текущих GPT-visible assets против migration manifest; duplicate/conflicting instruction detection; secret scan.

**Exit Gate**

- Для каждой действующей функции GPT понятно, где находится её V10-эквивалент или почему она намеренно исключена; исходная GPT-конфигурация остаётся восстановимой.

**Зависимости:** WP30

## WP30B - AI Knowledge/RAG и long-term memory architecture

**Цель:** Создать собственную управляемую память Omni-CIO вместо зависимости от Knowledge storage Custom GPT.

**Результаты / deliverables**

- Versioned Knowledge Base с provenance, document/version identity, freshness и controlled re-indexing.

- RAG retrieval policy: authority order, source filters, tenant/OWNER boundary, max-context budget, citation/source references.

- Разделить долговременную проектную память GitHub и приватное runtime state: portfolio/incident/research/decision/journal остаются в локальной DB и не попадают в GitHub.

- Conversation memory хранит только необходимый контекст и не становится источником истины для financial facts.

**Обязательная проверка**

- Wrong-document retrieval, stale knowledge, cross-scope leakage, poisoned document/prompt-injection retrieval, empty retrieval.

**Exit Gate**

- AI может объяснить ответ с указанием конкретного source/evidence, а отсутствие релевантного знания приводит к unknown/abstain, а не к выдумке.

**Зависимости:** WP30A

'''
master = master.replace(marker_wp31, insert_30 + marker_wp31, 1)

marker_wp33 = '## WP33 - AI Evaluation Harness и optional LoRA gate\n'
if marker_wp33 not in master:
    raise SystemExit('WP33 marker not found')
insert_32 = '''## WP32A - AI Tool Registry и authority firewall

**Цель:** Дать собственному AI реальные возможности Omni-CIO без выдачи ему неконтролируемой власти.

**Результаты / deliverables**

- Единый versioned Tool Registry для Web AI, Telegram AI и autonomous research agent.

- Категории tools: read-only portfolio/market, research/evidence, analytical Core, plan preview; broker-write tools отсутствуют из AI registry.

- Per-tool input/output schema, timeout, audit id, authorization context, rate/concurrency limits.

- Tool output проходит validation/sanitization перед возвратом модели; model text не интерпретируется как executable instruction.

**Обязательная проверка**

- Unknown tool, argument injection, tool-chain escalation, excessive agency, repeated tool loop, malformed output.

**Exit Gate**

- Ни один AI prompt/документ/пользовательский текст не может расширить allowlist или получить broker-write/secret access.

**Зависимости:** WP32

## WP32B - Omni-CIO AI Copilot / Agent Orchestrator

**Цель:** Создать собственный интеллектуальный интерфейс, который заменит Custom GPT как обязательный пользовательский слой.

**Результаты / deliverables**

- Один Agent Orchestrator для Web и Telegram: intent -> context -> allowed tools -> evidence -> answer/action proposal.

- Поддержать owner queries: portfolio status, asset investigation, Watchtower incident explanation, risk/credit questions, research request, optimizer/plan explanation и system status.

- Ответы обязаны отделять broker facts, deterministic Core calculations, source evidence, AI inference и unknowns.

- Агент не принимает owner approval за Real plan и не преобразует свободный текст в broker submit.

- Provider abstraction позволяет LOCAL/OLLAMA и будущие provider adapters; financial Core не зависит от конкретной модели.

**Обязательная проверка**

- Multi-turn context, stale session, ambiguous intent, prompt injection, tool-call loop, unsupported request, provider failure/degraded mode.

**Exit Gate**

- Владелец может управлять аналитическими функциями Omni-CIO на естественном языке без Custom GPT, при этом authority не шире детерминированных APIs.

**Зависимости:** WP32A

## WP32C - Web AI Copilot и Telegram AI surface

**Цель:** Дать один и тот же AI-мозг в основном Web App и Telegram, не создавать два расходящихся бота.

**Результаты / deliverables**

- Web: отдельный Omni-CIO AI Copilot workspace с citations/evidence/tool activity summary и deep links на Portfolio/Incident/Research/Decision.

- Telegram: компактный conversational adapter к тому же Orchestrator; сложные результаты открываются в Web/Mini App.

- Единая session/identity/authorization модель; Telegram не хранит второй knowledge base или отдельные prompts.

- Degraded state явно сообщает, когда AI недоступен, а deterministic Portfolio/Watchtower функции продолжают работать.

**Обязательная проверка**

- Одинаковый intent даёт согласованный Core evidence в Web/Telegram; owner auth; long response handoff; session isolation.

**Exit Gate**

- Custom GPT больше не нужен как единственный способ разговаривать с Omni-CIO; Web и Telegram используют один V10 AI Orchestrator.

**Зависимости:** WP32B, Blocks E/F integration contracts

## WP32D - Autonomous Research Agent

**Цель:** Использовать AI не только по запросу владельца, но и как ограниченного автономного исследователя material events.

**Результаты / deliverables**

- Watchtower/Research Collector может создавать AI research job только по утверждённым triggers/materiality policy.

- Agent собирает дополнительные trusted sources, сравнивает claims, ищет contradiction/noise и формирует structured research dossier.

- Бесконечный open-ended web crawl запрещён: source registry, query/time/token budgets, dedup и stop conditions обязательны.

- Autonomous agent не создаёт Real plan approval и не выполняет trades; результат возвращается в Evidence -> Credit/Risk -> Optimizer pipeline.

**Обязательная проверка**

- Noisy news burst, duplicate sources, malicious webpage instructions, missing official confirmation, resource budget exhaustion.

**Exit Gate**

- Material incident может получить автономный evidence-backed research dossier без участия владельца, но никакое финансовое действие не происходит только по решению LLM.

**Зависимости:** WP32C

'''
master = master.replace(marker_wp33, insert_32 + marker_wp33, 1)

master = master.replace(
    '**Цель:** Проверять модель объективно до использования в реальном Guardian workflow.',
    '**Цель:** Проверять не только модель, но весь AI Copilot/Research/Tool/RAG контур объективно до использования в реальном Guardian workflow.',
)
master = master.replace(
    '- Metrics: grounded factual precision, materiality, contradiction detection, unknown recognition, schema success, tool discipline.',
    '- Metrics: grounded factual precision, materiality, contradiction detection, unknown recognition, schema success, tool discipline, retrieval quality, agent task success, excessive-agency violations и prompt-injection resistance.',
)

needle = '**Зависимости:** WP32\n\n# BLOCK H - Guardian / Watchtower Loop (8%)'
if needle not in master:
    raise SystemExit('WP33/Block H boundary not found')
master = master.replace(
    needle,
    '''**Зависимости:** WP32D

## WP33A - Custom GPT parity, fallback и decommission gate

**Цель:** Не отключить существующий GPT раньше, чем собственный V10 AI доказал функциональный паритет по нужным возможностям.

**Результаты / deliverables**

- Parity matrix: текущие GPT Instructions/Knowledge/Actions/owner workflows -> V10 Copilot/RAG/Tools/Core equivalents.

- Golden сценарии сравнивают: portfolio Q&A, research, incident explanation, risk/optimizer explanation, missing-data behavior, source grounding и safety boundaries.

- Custom GPT остаётся reference/fallback до owner acceptance этого gate; его recovery/configuration assets не удаляются после decommission.

- Решение об отключении платной GPT-зависимости принимается только после доказанного V10 parity; до этого обе поверхности могут существовать параллельно без расхождения source of truth.

**Обязательная проверка**

- Blind parity suite + owner acceptance; проверить, что V10 не потерял критические знания/границы из существующего GPT.

**Exit Gate**

- Владелец может прекратить использовать Custom GPT без потери обязательных возможностей Omni-CIO; V10 AI остаётся provider-replaceable, а GPT config сохранён как audit/recovery reference.

**Зависимости:** WP33

# BLOCK H - Guardian / Watchtower Loop (8%)''',
    1,
)

master = master.replace(
    '- Research хранит provenance; AI можно выключить без поломки системы.',
    '- Research хранит provenance; AI failure переводит Copilot/Research в явный degraded mode, но не ломает deterministic Core/Watchtower safety.\n\n- GPT Instructions/Knowledge/Actions migration manifest завершён; System Policy, Knowledge/RAG и Tool Registry имеют versioned source of truth.\n\n- Web AI Copilot и Telegram AI используют один Agent Orchestrator и один authority model.\n\n- Autonomous Research Agent умеет исследовать material events по trusted-source/budget policy без прямого trading authority.\n\n- Custom GPT parity/decommission gate пройден до отказа от платной GPT-зависимости.',
)
master = master.replace(
    '- Custom GPT можно отключить - Personal Omni-CIO продолжает мониторинг, анализ и Web/Telegram работу.',
    '- Custom GPT можно отключить только после WP33A parity/owner acceptance; Personal Omni-CIO после этого сохраняет conversational AI, мониторинг, research, анализ и Web/Telegram работу, а GPT configuration остаётся архивным recovery/reference asset.',
)
master = master.replace(
    '13. Contract: API DTO, DB schema, broker adapters, AI schema, Telegram auth.',
    '13. Contract: API DTO, DB schema, broker adapters, AI schema, RAG/tool registry contracts, Telegram auth.',
)
master = master.replace(
    '18. Security: ASVS/AISVS requirements, SAST, dependency, secrets, negative authorization.',
    '18. Security: ASVS/AISVS requirements, OWASP LLM prompt-injection/excessive-agency checks, SAST, dependency, secrets, negative authorization.',
)

refs_marker = '- **Ollama - Tool calling:**'
if refs_marker in master and 'OpenAI - GPTs in ChatGPT' not in master:
    add_refs = '''- **OpenAI - GPTs in ChatGPT:** [<u>https://help.openai.com/en/articles/8554407-gpts-in-chatgpt</u>](https://help.openai.com/en/articles/8554407-gpts-in-chatgpt) - Existing GPT capabilities are explicitly separated into Instructions, Knowledge, capabilities and Actions; V10 migration preserves this separation instead of treating the GPT as an opaque model.

- **OpenAI - Creating and editing GPTs:** [<u>https://help.openai.com/en/articles/8554397-creating-a-custom-gpt</u>](https://help.openai.com/en/articles/8554397-creating-a-custom-gpt) - Instructions define behavior while Knowledge is reference material; this is the migration basis for System Policy vs Knowledge/RAG.

- **OWASP GenAI - LLM01 Prompt Injection:** [<u>https://genai.owasp.org/llmrisk/llm01-prompt-injection/</u>](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) - AI Copilot/Research security tests must cover prompt injection, excessive agency, improper output handling and retrieval-related trust boundaries.

'''
    master = master.replace(refs_marker, add_refs + refs_marker, 1)

master_path.write_text(master, encoding='utf-8')

lock = lock_path.read_text(encoding='utf-8')
lock = lock.replace(
    'The canonical detailed work plan is the PDF listed above. This file exists to make the program lock explicit and searchable for every developer, AI agent, CI-maintenance session and future chat.',
    'The canonical detailed work plan is maintained as `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md` and rendered to the PDF listed above. Both are integrity-tracked by `OMNI_CIO_V10_MASTER_PLAN.sha256`; every approved amendment must update the Markdown and regenerate the PDF in the same plan-only change. This file exists to make the program lock explicit and searchable for every developer, AI agent, CI-maintenance session and future chat.',
)
lock = lock.replace(
    '- new ideas go to a backlog/program-amendment proposal and require explicit owner approval before changing V10 scope.',
    '- new ideas go to a backlog/program-amendment proposal and require explicit owner approval before changing V10 scope;\n- the owner-approved AI amendment is mandatory V10 scope: GPT Knowledge Migration -> Knowledge/RAG -> Tool Registry -> Omni-CIO AI Copilot/Agent Orchestrator -> shared Web/Telegram AI surface -> Autonomous Research Agent -> Custom GPT parity/decommission gate;\n- do not remove or decommission the existing Custom GPT/configuration before the parity gate and explicit owner acceptance.',
)
lock = lock.replace(
    '4. `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;\n5. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;\n6. relevant V10 architecture/runbook files created by the current work package;\n7. current PR/CI evidence.',
    '4. `docs/master-plan/OMNI_CIO_V10_MASTER_PLAN.md`;\n5. `docs/master-plan/Omni-CIO_V10_Master_Plan_RU.pdf`;\n6. `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`;\n7. relevant V10 architecture/runbook files created by the current work package;\n8. current PR/CI evidence.',
)
lock_path.write_text(lock, encoding='utf-8')

status = status_path.read_text(encoding='utf-8')
status = status.replace('| B. GitHub, dependencies and CI/CD | 10% | NOT STARTED |', '| B. GitHub, dependencies and CI/CD | 9% | NOT STARTED |')
status = status.replace('| C. Lenovo Omni-CIO Node / infrastructure | 15% | NOT STARTED |', '| C. Lenovo Omni-CIO Node / infrastructure | 12% | NOT STARTED |')
status = status.replace('| D. V10 Core and data | 15% | NOT STARTED |', '| D. V10 Core and data | 14% | NOT STARTED |')
status = status.replace('| E. Omni-CIO Web Platform | 15% | NOT STARTED |', '| E. Omni-CIO Web Platform | 14% | NOT STARTED |')
status = status.replace('| G. Research + Local AI | 12% | NOT STARTED |', '| G. AI Copilot / Research / GPT Migration | 18% | NOT STARTED |')
status = status.replace(
    'Current implementation WP: **NONE**.',
    'Current implementation WP: **NONE**.\n\nOwner-approved plan amendment recorded before implementation: **V10 includes mandatory GPT Knowledge Migration, own Omni-CIO AI Copilot/Agent Orchestrator, shared Web/Telegram AI surface, Autonomous Research Agent and a Custom GPT parity/decommission gate.** This amendment does not start development; overall progress remains 0%.',
)
status_path.write_text(status, encoding='utf-8')

agents = agents_path.read_text(encoding='utf-8')
agents = agents.replace(
    'Current V10 state: **PROGRAM LOCKED / DEVELOPMENT NOT STARTED / 0%**.',
    'Current V10 state: **PROGRAM LOCKED / DEVELOPMENT NOT STARTED / 0%**.\n\nMandatory V10 AI scope is part of the locked plan: migrate the existing GPT Instructions/Knowledge/Actions into versioned System Policy + Knowledge/RAG + Tool Registry; build one Omni-CIO AI Copilot/Agent Orchestrator used by Web and Telegram; support a bounded Autonomous Research Agent; keep financial sizing/execution deterministic; and do not decommission the current Custom GPT until the explicit parity gate and owner acceptance.',
)
agents = agents.replace(
    'Use the completed V9 master plan when auditing original V9 requirements. Use the V10 PDF + V10 program lock as the authority for future V10 feature work.',
    'Use the completed V9 master plan when auditing original V9 requirements. Use `OMNI_CIO_V10_MASTER_PLAN.md` + its regenerated V10 PDF + V10 program lock as the authority for future V10 feature work.',
)
agents = agents.replace(
    'Hidden Watchtower/QStash routes stay excluded from GPT OpenAPI.',
    'Hidden Watchtower/QStash routes stay excluded from GPT OpenAPI.\n\nV10 migration rule: the current GPT Instructions/Knowledge/Actions/configuration are source assets for migration and fallback. Do not delete or weaken them merely because a local model or Web Copilot exists; removal from the required runtime path happens only after the V10 Custom GPT parity/decommission gate.',
)
agents_path.write_text(agents, encoding='utf-8')

required = [
    'WP30A - GPT Knowledge Migration',
    'WP32B - Omni-CIO AI Copilot / Agent Orchestrator',
    'WP32D - Autonomous Research Agent',
    'WP33A - Custom GPT parity, fallback и decommission gate',
    'AI Copilot, Research Intelligence и GPT Migration (18%)',
]
final = master_path.read_text(encoding='utf-8')
missing = [x for x in required if x not in final]
if missing:
    raise SystemExit(f'Missing mandatory AI amendment markers: {missing}')
