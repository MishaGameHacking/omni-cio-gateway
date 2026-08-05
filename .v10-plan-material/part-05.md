 Contradiction cases, wrong instrument, stale source, unsupported claim.

**Exit Gate**

- Risk/Credit потребляют evidence contracts, а не свободный текст новости.

**Зависимости:** WP28

## WP30 - AI Provider Abstraction

**Цель:** Сделать локальный AI сменным и необязательным.

**Результаты / deliverables**

- Provider interface: NONE и OLLAMA минимум.

- Timeout, cancellation, model metadata, prompt/schema version, deterministic-ish settings для classification where applicable.

- AI job isolated from trading authority и secret store.

**Обязательная проверка**

- Provider NONE full Core regression; provider down/deadlock; invalid response.

**Exit Gate**

- Отключение AI не ломает Watchtower/Core и не разрешает unsafe fallback.

**Зависимости:** WP29

## WP31 - Lenovo AI Benchmark и model selection

**Цель:** Выбрать минимальную модель, которая проходит именно Omni-CIO задачи на реальном железе.

**Результаты / deliverables**

- Проверить 4B/8B и при ресурсах 14B open-weight candidates через Ollama.

- Измерить tokens/sec, first-token latency, RAM/VRAM, GPU temperature, long context stability.

- Не фиксировать бренд навсегда; model registry хранит name/version/quantization/hash/eval score.

**Обязательная проверка**

- Одинаковый benchmark corpus; thermal soak; concurrent lightweight Core load.

**Exit Gate**

- Выбрана самая маленькая модель, удовлетворяющая установленным quality/latency порогам.

**Зависимости:** WP30

**Участие владельца:** Разрешить локальную установку Ollama/model weights; если место/железо не подходит, AI остаётся disabled.

## WP32 - Structured AI Researcher

**Цель:** Использовать AI для чтения/синтеза, но не для прямого финансового исполнения.

**Результаты / deliverables**

- Strict JSON schema: event_type, facts, contradictions, unknowns, materiality, confidence, source refs.

- Tool calls только read-only research/core tools.

- Prompt injection defense: внешняя страница не может изменить system policy/tool authority.

- AI summary сохраняется отдельно от canonical evidence.

**Обязательная проверка**

- JSON validity; tool allowlist; malicious article prompt injection; hallucinated source; unsupported conclusion.

**Exit Gate**

- AI не может создать broker order или изменить risk limit; invalid output отбрасывается validator.

**Зависимости:** WP31

## WP33 - AI Evaluation Harness и optional LoRA gate

**Цель:** Проверять модель объективно до использования в реальном Guardian workflow.

**Результаты / deliverables**

- Corpus: downgrade/default/delisting/liquidity/report/news noise/duplicate/rumor/contradictions/stale/wrong identity.

- Metrics: grounded factual precision, materiality, contradiction detection, unknown recognition, schema success, tool discipline.

- OWASP AI security requirements применить как security checklist для AI-enabled части.

- LoRA/QLoRA разрешить только после доказанного систематического gap; обучение модели с нуля вне scope.

**Обязательная проверка**

- Blind benchmark old/new model; adversarial/prompt injection suite; regression threshold.

**Exit Gate**

- AI provider допускается в production Guardian только после прохождения заранее заданных порогов; иначе AI_ENABLED=false.

**Зависимости:** WP32

# BLOCK H - Guardian / Watchtower Loop (8%)

## WP34 - Production Watchtower wiring

**Цель:** Превратить реализованный V9 Watchtower в реально подключённый V10 monitoring loop с canonical providers.

**Результаты / deliverables**

- Providers: portfolio, risk, credit, market/evidence, policy, data quality.

- Durable state в V10 DB, semantic fingerprints/dedup/reopen semantics.

- Watchtower не выполняет сделки.

**Обязательная проверка**

- Baseline first run; duplicate run; persistent event; resolved/reappeared; stale provider.

**Exit Gate**

- Периодическая проверка реального OWNER портфеля создаёт incident только на material change.

**Зависимости:** Blocks D,G

## WP35 - Incident lifecycle engine

**Цель:** Управлять проблемой как полноценным state machine от обнаружения до закрытия.

**Результаты / deliverables**

- DETECTED -> INVESTIGATING -> EVIDENCE_READY -> RISK_RECALCULATED -> DECISION_READY -> OWNER_NOTIFIED -> RESOLVED/ESCALATED.

- Every transition journaled с correlation id.

- Retry/recovery rules per state.

**Обязательная проверка**

- Crash/restart в каждом состоянии; duplicate transition rejection.

**Exit Gate**

- Любой incident имеет однозначное текущее состояние и replayable history.

**Зависимости:** WP34

## WP36 - Guardian Decision Pipeline

**Цель:** Связать Research, Credit/Risk, Strategy, Optimizer и Plans в один автономный analysis workflow.

**Результаты / deliverables**

- Watchtower trigger запускает research only when needed.

- Evidence validation до strong action.

- Optimizer рассчитывает target, lots, cash/risk before-after; AI не задаёт цифры напрямую.

- NO_ACTION/CASH остаётся полноценным результатом.

**Обязательная проверка**

- Golden incident scenarios; missing/contradictory evidence; optimizer infeasible result.

**Exit Gate**

- Для material incident формируется один Decision object с exact source inputs и reproducible output.

**Зависимости:** WP35

## WP37 - One Main Decision policy

**Цель:** Не перекладывать профессиональный sizing на владельца через меню случайных процентов.

**Результаты / deliverables**

- MAIN_DECISION = NO_ACTION/HOLD/REDUCE/EXIT/REALLOCATE.

- Если confidence недостаточен: REVIEW_REQUIRED/INSUFFICIENT_EVIDENCE вместо ложной точности.

- Alternatives используются для объяснения decision dominance, а не как просьба владельцу угадать правильное действие.

**Обязательная проверка**

- Same inputs -> same decision; uncertainty threshold boundary tests.

**Exit Gate**

- Однозначное решение либо честный blocker; нет ложной "100% гарантии рынка".

**Зависимости:** WP36

## WP38 - Explainability и owner alert package

**Цель:** Каждое решение должно быть доказуемым до отправки владельцу.

**Результаты / deliverables**

- Что произошло, что доказано, что неизвестно, impact на весь portfolio, target, before/after, costs, reasons, cancel triggers.

- Telegram получает concise alert; Web получает полный dossier.

- Every explanation links to Decision/Plan hashes.

**Обязательная проверка**

- No-source claim detection; numerical consistency UI/API.

**Exit Gate**

- Владелец может проверить почему система решила и