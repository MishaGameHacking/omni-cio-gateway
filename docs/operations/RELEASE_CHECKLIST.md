# Release checklist

## 1. Подготовка

- [ ] `main` актуален.
- [ ] Открытые PR и Issues проверены.
- [ ] Новая ветка создана от текущего `main`.
- [ ] Прочитаны `AGENTS.md`, master context и профильный knowledge-файл.
- [ ] Определено, какие компоненты меняются: Gateway, Telegram, Custom GPT или frontend.
- [ ] Версии компонентов явно указаны.

## 2. Код и контракты

- [ ] Gateway entrypoint остаётся `app:app`.
- [ ] Telegram entrypoint остаётся `telegram_bot.app:app`, если затронут Telegram.
- [ ] Gateway Actions только `GET`.
- [ ] Telegram вызывает Gateway только `GET`.
- [ ] Единственный Telegram POST — secret-protected webhook.
- [ ] `trading_methods=false` во всех интерфейсах.
- [ ] Не добавлены order create/replace/cancel/submit методы.
- [ ] OpenAPI object schemas содержат явные `properties`.
- [ ] Секреты, Telegram IDs и полный ID счёта отсутствуют в diff.
- [ ] Валюты не складываются без подтверждённого FX.

## 3. Telegram security, если применимо

- [ ] Проверяется `X-Telegram-Bot-Api-Secret-Token`.
- [ ] Только private chat.
- [ ] Только allowlisted user IDs.
- [ ] Duplicate update suppression включён.
- [ ] Rate limit включён.
- [ ] Account ID повторно маскируется.
- [ ] Токен не появляется в health, errors или logs.
- [ ] Реальные Telegram API вызовы отсутствуют в тестах.

## 4. Тесты

- [ ] `python scripts/check_repository_layout.py` проходит.
- [ ] `python -m compileall ...` проходит.
- [ ] `python -m pytest -q` проходит.
- [ ] Happy path покрыт.
- [ ] Partial/error path покрыт.
- [ ] Read-only и отсутствие торговли покрыты.
- [ ] Для Telegram покрыты wrong secret и unauthorized user.
- [ ] Regression Shield зелёный.

## 5. Документация

- [ ] Обновлён `CHANGELOG.md`.
- [ ] Обновлён `README.md`.
- [ ] Обновлён master context.
- [ ] Обновлён профильный `knowledge/NN_*`.
- [ ] Обновлён asset inventory.
- [ ] Обновлён соответствующий deployment runbook.
- [ ] `gpt/` обновлён, если менялся Action contract.

## 6. Pull Request

- [ ] Описание содержит изменение, безопасность, тесты и post-merge проверку.
- [ ] Head SHA зафиксирован.
- [ ] Нет нерешённых review threads.
- [ ] Для релиза выбран squash merge.

## 7. Production

### Gateway

- [ ] Render deploy использует merge commit.
- [ ] `/health` подтверждает Gateway version, commit SHA и `app:app`.
- [ ] `trading_methods=false`.
- [ ] При изменении схемы обновлён GPT Editor.

### Telegram

- [ ] Отдельный Render service создан из `render.telegram.yaml`.
- [ ] Заполнены Telegram token, allowlist и Gateway key.
- [ ] Telegram `/health` показывает version, `configured=true`, bootstrap `ok` и `telegram_bot.app:app`.
- [ ] `/start`, `/health` и одна финансовая команда протестированы.
- [ ] Unauthorized Telegram account не получает данные.
- [ ] `/report` возвращает или использует настоящий task ID.

- [ ] Project memory позволяет новому чату понять релиз только из GitHub.
