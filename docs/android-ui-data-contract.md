# Android UI → system data contract

Статус: интерфейсный контракт после UI-06 / 2.5.0. Это граница между принятым UI и системным этапом SYS-01+.
Контракт описывает семантику, которую следующий этап должен сохранить; он не превращает demo/fixture значения UI-06 в production-данные.

## Общие правила

- Персональный портфель и его расчёты принадлежат локальному Android-контуру.
- Неизвестное числовое значение представляется как отсутствие значения (`null`/явный status), а не как `0`.
- Подтверждённый ноль допустим только когда источник действительно подтверждает нулевое значение.
- Деньги внутри детерминированных моделей передаются в minor units (`Long`) вместе с валютой; форматирование выполняется на UI-границе.
- Каждое внешнее значение, которое может устареть, должно иметь источник, время/версию и freshness/status.
- Demo/fixture и production никогда не смешиваются в одном неразличимом состоянии.
- T-Invest credential/token не входит ни в один UI export DTO, portfolio DTO, assistant event или Timeweb payload.
- BUY/SELL/HOLD authority и broker order/transfer authority отсутствуют в UI-контракте.

## AppUiState

UI-06 агрегирует:

- `installationId`: локальный случайный идентификатор установки; не логин;
- `onboardingComplete`;
- `amountsHidden`;
- `displayCurrency`;
- `overviewMode`: только UI/demo state selector до появления реального repository state;
- `settings: LocalSettingsState`;
- `migrationStatus`.

SYS-01 должен заменить простое non-secret SharedPreferences-хранение теми repository/storage источниками, для которых это требуется, не меняя смысл полей для UI без отдельной миграции контракта.

## OverviewSnapshot

Обязательная семантика:

- `totalMinor: Long?`;
- `availableMinor: Long?`;
- `reserveMinor: Long?`;
- `scenarioBudgetMinor: Long?`;
- `sourceLabel`;
- `updatedLabel`;
- `freshnessLabel`;
- одна `noticeTitle/noticeBody`;
- `expectedPayouts` отдельно от `receivedPayouts`.

Инварианты:

- пополнение не называется доходностью;
- ожидаемая выплата не становится доступными деньгами до подтверждения;
- stale/partial/offline/error/loading сохраняются как отдельные состояния;
- отсутствие цены/денег не заменяется нулём.

На SYS-этапе display labels могут быть вынесены из domain слоя, но перечисленные состояния и различия должны сохраниться.

## PortfolioPosition

Локальный портфель должен уметь предоставить UI:

- стабильный `instrumentUid`;
- ticker/ISIN при наличии;
- название;
- quantity / availableQuantity / blockedQuantity;
- currentPriceMinor и currentValueMinor как nullable;
- currency;
- shareBasisPoints как nullable;
- price status;
- risk/data status;
- lot size;
- price source и updated timestamp/status;
- payout summary;
- подтверждённые общие issuer facts;
- список локальных account sources.

Одинаковый инструмент по нескольким выбранным счетам может агрегироваться, но UI должен сохранять возможность показать исходные account contributions.

## AssistantMessage

Автоматическая лента принимает только типизированные события:

- material event;
- risk change;
- payout;
- available cash change;
- user-selected scenario result;
- stale analysis;
- sync required.

Сообщение содержит:

- стабильный event key;
- тип;
- что изменилось;
- почему относится к портфелю;
- детерминированный numeric impact либо отсутствие значения;
- source/provenance;
- occurredAt;
- не более одного безопасного действия.

Повторная публикация одной ревизии не создаёт дубль.
Открытие ленты не является причиной LLM-вызова.
Если данных недостаточно, UI не придумывает impact или action.

## LocalSettingsState

UI ожидает следующие локальные настройки/состояния:

- portfolio present;
- broker connected;
- broker credential present — только status, не секрет;
- broker revoked;
- dependent personal jobs running;
- reserve minor units;
- goal horizon years;
- notifications enabled;
- fast alerts enabled.

SYS-01/SYS-02 меняют реализацию credential/storage, но UI получает только безопасный status. Сам credential не должен появляться в `LocalSettingsState`.

## SYS-01 mapping

Первый системный выпуск должен ввести repository boundary вместо прямого использования UI persistence там, где появляются sensitive данные:

- Room/SQLite repository для локальных portfolio/ledger данных;
- encrypted-at-rest design после security review;
- database key через Android Keystore;
- broker secret через отдельный Keystore-backed secret boundary;
- versioned migrations;
- states: new install, existing DB, migration, corrupted DB, key unavailable, user wipe.

UI-06 `LocalMigrationStatus` является интерфейсным состоянием. SYS-01 может заменить внутренний механизм миграции, но должен сохранить fail-closed поведение: не показывать частично мигрированные sensitive данные как актуальные.

## Wipe/export

Local wipe должен удалить будущие sensitive portfolio/strategy/credential/queued-personal-work данные атомарно настолько, насколько позволяет storage design, и после этого UI показывает состояние отсутствия локального портфеля.

Экспорт по умолчанию:

- создаётся только по явному действию пользователя;
- не содержит T-Invest token/credential;
- не утверждает полноту данных, если repository находится в partial/corrupted/migration состоянии.

## Timeweb boundary

Разрешённый общий серверный слой отдаёт instrument/issuer intelligence по общим идентификаторам и version/freshness/provenance.
Базовый local-first клиент не должен отправлять туда полный holdings snapshot, баланс, операции, broker token или личную стратегию только ради получения общего instrument intelligence.

## Совместимость

Изменение названий Kotlin-классов допустимо.
Изменение перечисленной семантики требует отдельного versioned migration/contract change и тестов.

Этот файл является интерфейсной точкой входа для SYS-01; подробные требования безопасности и последовательность системных выпусков остаются в `docs/system-plan.md`.
