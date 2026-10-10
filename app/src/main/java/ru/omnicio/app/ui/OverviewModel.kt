package ru.omnicio.app.ui

private const val RESYNC_NOTICE_TITLE = RESYNC_NOTICE_TITLE

internal enum class DisplayCurrency(
    val code: String,
    val symbol: String,
) {
    RUB("RUB", "₽"),
    USD("USD", "$"),
    EUR("EUR", "€"),
}

internal enum class OverviewMode(val label: String) {
    READY("Актуально"),
    DISCONNECTED("Нет подключения"),
    EMPTY("Пусто"),
    STALE("Устарело"),
    PARTIAL("Частично"),
    OFFLINE("Offline"),
    LOADING("Загрузка"),
    ERROR("Ошибка"),
}

internal data class PayoutFixture(
    val title: String,
    val dateLabel: String,
    val amountMinor: Long?,
)

internal data class OverviewSnapshot(
    val totalMinor: Long?,
    val availableMinor: Long?,
    val reserveMinor: Long?,
    val scenarioBudgetMinor: Long?,
    val sourceLabel: String,
    val updatedLabel: String,
    val freshnessLabel: String,
    val noticeTitle: String,
    val noticeBody: String,
    val expectedPayouts: List<PayoutFixture>,
    val receivedPayouts: List<PayoutFixture>,
)

internal fun overviewSnapshot(
    mode: OverviewMode,
    currency: DisplayCurrency,
): OverviewSnapshot {
    val regular = regularFixture(currency)
    return when (mode) {
        OverviewMode.READY -> regular
        OverviewMode.DISCONNECTED -> regular.copy(
            totalMinor = null,
            availableMinor = null,
            reserveMinor = null,
            scenarioBudgetMinor = null,
            sourceLabel = "Источник не подключён",
            updatedLabel = "Снимка ещё нет",
            freshnessLabel = "нет подключения",
            noticeTitle = RESYNC_NOTICE_TITLE,
            noticeBody = "Подключение T-Invest пока не настроено. Это demo-state: реальные брокерские данные не запрашиваются.",
            expectedPayouts = emptyList(),
            receivedPayouts = emptyList(),
        )
        OverviewMode.EMPTY -> regular.copy(
            totalMinor = 0,
            availableMinor = 0,
            reserveMinor = 0,
            scenarioBudgetMinor = 0,
            sourceLabel = "Демо · подтверждённый пустой счёт",
            updatedLabel = "Fixture-снимок · сейчас",
            freshnessLabel = "актуально",
            noticeTitle = "Существенных действий нет",
            noticeBody = "Портфель подтверждённо пуст. Ноль показан только потому, что состояние известно, а не вместо неизвестного значения.",
            expectedPayouts = emptyList(),
            receivedPayouts = emptyList(),
        )
        OverviewMode.STALE -> regular.copy(
            sourceLabel = "Демо · локальный снимок",
            updatedLabel = "Fixture-снимок · 3 ч назад",
            freshnessLabel = "устарело",
            noticeTitle = "Данные устарели",
            noticeBody = "Последний снимок старше допустимого окна. Значения сохранены, но требуют обновления перед новым выводом.",
        )
        OverviewMode.PARTIAL -> regular.copy(
            availableMinor = null,
            scenarioBudgetMinor = null,
            sourceLabel = "Демо · частичный T-Invest fixture",
            updatedLabel = "Частичный снимок · 2 мин назад",
            freshnessLabel = "частичные данные",
            noticeTitle = RESYNC_NOTICE_TITLE,
            noticeBody = "Часть данных отсутствует. Неизвестные деньги и бюджет не заменяются нулём.",
            expectedPayouts = listOf(
                PayoutFixture(
                    title = "ОФЗ 26238 · купон",
                    dateLabel = "18 окт",
                    amountMinor = null,
                ),
            ),
        )
        OverviewMode.OFFLINE -> regular.copy(
            sourceLabel = "Демо · локальный кэш",
            updatedLabel = "Последний снимок · 40 мин назад",
            freshnessLabel = "offline",
            noticeTitle = RESYNC_NOTICE_TITLE,
            noticeBody = "Сети нет. OMNICIO показывает последний локальный снимок и не выдаёт его за свежие данные.",
        )
        OverviewMode.LOADING -> regular.copy(
            totalMinor = null,
            availableMinor = null,
            reserveMinor = null,
            scenarioBudgetMinor = null,
            sourceLabel = "Демо · локальная загрузка",
            updatedLabel = "Обновление fixture…",
            freshnessLabel = "loading",
            noticeTitle = "Существенных действий нет",
            noticeBody = "Обновление ещё не завершено. До готового снимка приложение не подставляет прежние значения как новые.",
            expectedPayouts = emptyList(),
            receivedPayouts = emptyList(),
        )
        OverviewMode.ERROR -> regular.copy(
            totalMinor = null,
            availableMinor = null,
            reserveMinor = null,
            scenarioBudgetMinor = null,
            sourceLabel = "Демо · источник недоступен",
            updatedLabel = "Последняя попытка · сейчас",
            freshnessLabel = "ошибка",
            noticeTitle = RESYNC_NOTICE_TITLE,
            noticeBody = "Источник вернул ошибку. UI сохраняет честное состояние недоступности без фиктивных нулей.",
            expectedPayouts = emptyList(),
            receivedPayouts = emptyList(),
        )
    }
}

private fun regularFixture(currency: DisplayCurrency): OverviewSnapshot = OverviewSnapshot(
    totalMinor = fixtureMoney(currency, rub = 128_453_000, usd = 1_564_800, eur = 1_347_200),
    availableMinor = fixtureMoney(currency, rub = 18_490_000, usd = 225_100, eur = 193_700),
    reserveMinor = fixtureMoney(currency, rub = 15_000_000, usd = 182_600, eur = 157_100),
    scenarioBudgetMinor = fixtureMoney(currency, rub = 3_490_000, usd = 42_500, eur = 36_500),
    sourceLabel = "Демо · T-Invest read-only fixture",
    updatedLabel = "Fixture-снимок · 5 мин назад",
    freshnessLabel = "актуально",
    noticeTitle = "Появились свободные деньги",
    noticeBody = "Доступно для новых покупок больше заданного demo-резерва. Это только UI-fixture, не инвестиционная рекомендация.",
    expectedPayouts = listOf(
        PayoutFixture(
            title = "ОФЗ 26238 · купон",
            dateLabel = "18 окт",
            amountMinor = fixtureMoney(currency, rub = 1_234_500, usd = 15_050, eur = 12_950),
        ),
        PayoutFixture(
            title = "SBER · дивиденд",
            dateLabel = "25 окт",
            amountMinor = fixtureMoney(currency, rub = 842_000, usd = 10_260, eur = 8_820),
        ),
    ),
    receivedPayouts = listOf(
        PayoutFixture(
            title = "ОФЗ 26212 · купон",
            dateLabel = "7 окт",
            amountMinor = fixtureMoney(currency, rub = 589_000, usd = 7_180, eur = 6_180),
        ),
    ),
)

private fun fixtureMoney(
    currency: DisplayCurrency,
    rub: Long,
    usd: Long,
    eur: Long,
): Long = when (currency) {
    DisplayCurrency.RUB -> rub
    DisplayCurrency.USD -> usd
    DisplayCurrency.EUR -> eur
}

internal fun formatMoney(
    minorUnits: Long?,
    currency: DisplayCurrency,
    hidden: Boolean,
): String {
    if (hidden) {
        return "••••"
    }
    if (minorUnits == null) {
        return "нет данных"
    }

    val negative = minorUnits < 0
    val absolute = if (negative) -minorUnits else minorUnits
    val whole = absolute / 100
    val fraction = absolute % 100
    val grouped = groupThousands(whole)
    val fractionText = if (fraction == 0L) {
        ""
    } else {
        "," + fraction.toString().padStart(2, '0')
    }
    val sign = if (negative) "-" else ""
    return sign + grouped + fractionText + " " + currency.symbol
}

private fun groupThousands(value: Long): String = value
    .toString()
    .reversed()
    .chunked(3)
    .joinToString(" ")
    .reversed()
