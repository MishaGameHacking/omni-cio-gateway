# Master plans Omni-CIO

Эта папка хранит исходную пользовательскую спецификацию и канонический порядок дальнейшей разработки Omni-CIO.

## Текущий канонический порядок исполнения

- [`OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU_V1.md`](OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU_V1.md) — финальный GPT-only пошаговый план владельца, версия 1.0 от 2026-08-01.
- Исходный пользовательский PDF: `OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU(1).pdf`.
- SHA-256 исходного PDF: `c4a2f940ecd3dff730f6a29c5f5389363d53b6f6463a8370896c1d606bc84355`.
- Проверка источника: 19 страниц, текстовый PDF, не зашифрован, OCR не требуется, 62 элемента оглавления.

Этот документ фиксирует обязательный порядок: сначала GPT-only scope restoration и полный audit, затем compatibility/CI, конфигурация существующего Custom GPT, Knowledge, Actions/Gateway, portfolio/market/decision workflow и только после end-to-end Preview — read-only release.

Ключевой scope нового плана:

- единственный пользовательский продукт — существующий Custom GPT внутри ChatGPT;
- отдельный сайт, web-кабинет, мобильное приложение и собственная AI-модель исключены;
- Telegram в текущем релизе — только drafts для ручной публикации;
- `trading_methods=false`, GET-only Actions и `app:app` сохраняются;
- до завершения audit запрещено начинать новые функции.

## Исходная стратегическая спецификация

- `OMNI_CIO_MASTER_PROMPT_V9.pdf` — исходный приложенный документ, 39 страниц.
- `OMNI_CIO_MASTER_PROMPT_V9.txt` — машинное извлечение текста для поиска, code review и AI-контекста; при расхождении приоритет у PDF.

Исходное имя вложения: `Мастер-промт Omni-CIO(9).pdf`.

SHA-256 PDF v9: `1fa50e7ca08f9701879bbc98c77f04e12cd66d52d2802e5f44d360e620f530f8`.

Аудит 2026-07-30 подтвердил, что приложенные версии `(8)` и `(9)` побайтно идентичны, поэтому хранится одна каноническая копия v9 без дубля.

## Иерархия источников

1. Фактический код и contracts в актуальном `main`.
2. Фактическая конфигурация существующего GPT Editor и Preview evidence.
3. Exact-head/merge-ref GitHub Actions и artifacts.
4. `AGENTS.md` и repository security policies.
5. Исходная стратегическая спецификация v9.
6. Финальный пошаговый GPT-only план v1.0 как текущий порядок исполнения.
7. Проверенные `knowledge/00_PROJECT_MASTER_CONTEXT.md` и `knowledge/16_CURRENT_PROGRAM_STATUS.md`.
8. Актуальная официальная документация платформ и источников.

Будущие цели не являются доказательством реализации. Описание будущих Shadow/Paper/Preview/Confirm-before-trade уровней не отменяет `trading_methods=false`, GET-only Actions и отсутствие broker-write methods.

## Правило конфликтов и миграции

Новый финальный план уточняет scope и имеет приоритет для порядка дальнейших работ. Пункты старой документации о самостоятельном сайте/web-кабинете, обязательном frontend-проекте, SberInvestments HTML cabinet и внешней production RAG не продолжаются автоматически. Они должны быть классифицированы в GPT-only audit как:

- конфликтующие и подлежащие удалению;
- reusable backend capability;
- optional future package вне read-only v1;
- deprecated/orphaned;
- либо подтверждённая часть end-to-end Custom GPT цепочки.

До такой классификации запрещено расширять эти направления.

## Правило изменений

- не подменять требования предположениями;
- не считать roadmap-функцию реализованной без кода, тестов и acceptance;
- каждый пакет вести отдельной веткой и PR;
- не хранить токены, ключи, полные номера счетов и реальные брокерские отчёты;
- обновлять status и issue #27 только после свежей проверки GitHub;
- исходные PDF не редактировать; изменения порядка фиксировать новой версией и checksum.
