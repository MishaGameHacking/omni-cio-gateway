# Omni-CIO — архивный пошаговый GPT-only план v1

Версия: 1.0
Дата документа: 2026-08-01
Статус: **архивирован как более широкий план; не является текущим product scope**

Исходный пользовательский PDF: `OMNI_CIO_FINAL_STEP_BY_STEP_MASTER_PROMPT_RU(1).pdf`
SHA-256 исходного PDF: `c4a2f940ecd3dff730f6a29c5f5389363d53b6f6463a8370896c1d606bc84355`

## Почему документ архивирован

После повторного уточнения владельца продукт был сужен до одного назначения:

> существующий Custom GPT внутри ChatGPT, который работает только с личным портфелем владельца через read-only Gateway Actions.

Текущая обязательная спецификация:

[`OMNI_CIO_PORTFOLIO_GPT_RESET_V1.md`](OMNI_CIO_PORTFOLIO_GPT_RESET_V1.md)

Она исключает из активной разработки:

- отдельные пользовательские интерфейсы;
- собственную AI-модель;
- публичный продукт;
- любые внешние publishing-интеграции;
- автономное исполнение;
- текущую разработку торгового режима.

## Сохранённая ценность исходного плана

Исходный PDF остаётся историческим evidence и может использоваться только для непротиворечащих требований:

- строгая read-only безопасность;
- GitHub workflow;
- проверка свежести и качества данных;
- портфельная аналитика;
- новости и кредитные рейтинги;
- поиск активов;
- диверсификация;
- точные денежные расчёты;
- Preview acceptance;
- запрет ложных заявлений о реализации.

## Правило применения

При любом конфликте приоритет имеет `OMNI_CIO_PORTFOLIO_GPT_RESET_V1.md`.

Ни один пункт исходного широкого плана не продолжается автоматически. Новая функция допускается только если она непосредственно улучшает end-to-end цепочку:

```text
существующий Custom GPT
  -> Instructions
  -> minimal Knowledge
  -> read-only Actions
  -> Gateway
  -> T-Invest / разрешённые официальные источники
  -> проверенный ответ владельцу
```

## Неизменяемые инварианты

- `trading_methods=false`;
- GET-only user Actions;
- stable `app:app`;
- no order create/replace/cancel;
- no transfer/withdrawal;
- secrets вне GitHub и GPT Knowledge;
- masked account ID;
- no recommendation on stale/partial/contradictory data;
- owner-only Preview and Update.
