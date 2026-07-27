# Changelog

Все заметные изменения Omni-CIO Gateway фиксируются здесь. Источник истины по коду — ветка `main`; подробности релизов находятся в соответствующих Pull Request.

## [Unreleased]

- Структурирование репозитория, документации, конфигурации Custom GPT и эксплуатационных инструкций.

## [3.9.1] — 2026-07-27

### Added
- Асинхронная целостность официального брокерского отчёта.
- Возврат настоящего `task_id` при первом вызове без преждевременного опроса.
- Обработка T-Invest `30058` как штатного состояния `pending`.
- Ограничение периода официального отчёта до `1..31` дня.

### Safety
- `trading_methods=false`.
- Стабильный Render entrypoint `app:app`.

## [3.9.0] — 2026-07-27

- Official Broker Report & Operations Reconciliation.
- Пагинация отчёта, сверка сделок, денежных потоков и комиссий по каждой валюте.

## [3.8.0] — 2026-07-27

- Operations Analytics & Cash Flow Reconciliation.
- Защита от дублей, parent/child и повторного учёта комиссий.

## [3.7.1] — 2026-07-27

- Purchase Capacity Integrity.
- Арифметическая проверка суммы, комиссии и остатка.

## [3.7.0] — 2026-07-27

- Purchase Capacity Preview без создания заявки.

## [3.6.0] — 2026-07-27

- Cash & Liquidity Diagnostics.

## [3.5.0] — 2026-07-27

- Portfolio Analytics Core.

## [3.4.0] — 2026-07-27

- Portfolio Market Snapshot.

## [3.3.3] — 2026-07-27

- Regression Shield, CI и проверка read-only контракта.
