# Текущие исходники Timeweb — 27.10.2026

**Серверный backend обновлён; полный план N00–N11 остаётся незавершённым.**

- Проверенный code commit: [0b345c46cf89f8e5bd4dbec1b53820e1695015fa](https://github.com/MishaGameHacking/omni-cio-gateway/commit/0b345c46cf89f8e5bd4dbec1b53820e1695015fa).
- Полная резервная копия с последним отчётом: [40b261af67eca24a5131be2d5b99e06f73224817](https://github.com/MishaGameHacking/omni-cio-gateway/tree/40b261af67eca24a5131be2d5b99e06f73224817).
- SHA256 кода: `cc88859582fd6281a9051d76c8dbe399dfb885cd7eb033a34d691a3561a0998e`.
- Сервер: существующий Timeweb 9417611; backend `/opt/analyst-ai/backend`.
- Проверенный кандидат: `/var/lib/analyst-ai-build/development/candidate-n02-n04-r4-20261027-20261027T061309Z-ea5fd07f`.
- Указатель на сервере: `/var/lib/analyst-ai-build/development/current-source-n02-n04-r4-20261027.json`.
- Документы на сервере: `/var/lib/analyst-ai-build/development/handoff-n02-n04-r4-20261027`.

[Полный отчёт N00–N11](https://github.com/MishaGameHacking/omni-cio-gateway/blob/40b261af67eca24a5131be2d5b99e06f73224817/docs/AUTONOMOUS_PORTFOLIO_PROGRESS_2026-10-27.md), [исследование источников рейтингов](https://github.com/MishaGameHacking/omni-cio-gateway/blob/40b261af67eca24a5131be2d5b99e06f73224817/docs/N03_RATINGS_SOURCE_AUDIT_2026-10-27.md), [передача и последний рабочий цикл](timeweb-2026-10-27/HANDOFF.md).

Тесты: 1860 tests + 1557 subtests, 94 новых целевых теста. [Прогон](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40459662387), [применение](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40460080874), [сохранение на сервере](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40462227774).

Два фактических событийных цикла записали одну текущую операцию, одну историческую версию и два окна наблюдения. Календарь остаётся unavailable / `tinvest_unexpected_status`; точная причина HTTP-ответа пока неизвестна. Новости, операции и объявления выплат доступны. GLEIF not_applicable при eligible=0/missing=0; внешний контракт отдельно проверен публичными примерами. Обычный протокол ЦБ успешно проверен на одном ISIN, но производственный адаптер и охват четырёх КРА ещё не реализованы.

APK остаётся 49 /0.14.2-preview; новых доказательств физической установки нет. Исполнение `read_only`; реальные поручения не включены. N10 требует 30 настоящих торговых сессий. Разработка, проектные тесты и сборки выполняются на Timeweb согласно последнему прямому поручению владельца; GitHub используется для резервной копии и административного SSH-транспорта.
