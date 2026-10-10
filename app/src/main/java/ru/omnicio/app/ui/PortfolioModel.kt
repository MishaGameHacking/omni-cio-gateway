package ru.omnicio.app.ui

private const val DEFAULT_PORTFOLIO_SIZE = 4
private const val PRIMARY_ACCOUNT_LABEL = "Основной счёт"
private const val SYNTHETIC_UID_PREFIX = "fixture-instrument-"

internal enum class PriceStatus(val label: String) {
    CURRENT("цена актуальна"),
    STALE("цена устарела"),
    MISSING("цены нет"),
}

internal enum class RiskDataStatus(val label: String) {
    NORMAL("данные полные"),
    ATTENTION("нужна проверка"),
    INCOMPLETE("данные неполные"),
}

internal enum class PortfolioFixtureSize(
    val count: Int,
    val label: String,
) {
    DEFAULT(DEFAULT_PORTFOLIO_SIZE, "Демо"),
    ZERO(0, "0"),
    ONE(1, "1"),
    HUNDRED(100, "100"),
    THOUSAND(1000, "1000"),
}

internal data class AccountPositionFixture(
    val accountLabel: String,
    val quantity: Long,
    val availableQuantity: Long,
    val blockedQuantity: Long,
    val currentValueMinor: Long?,
)

internal data class RawPortfolioPosition(
    val instrumentUid: String,
    val name: String,
    val ticker: String?,
    val isin: String?,
    val quantity: Long,
    val availableQuantity: Long,
    val blockedQuantity: Long,
    val currentPriceMinor: Long?,
    val currentValueMinor: Long?,
    val priceStatus: PriceStatus,
    val riskStatus: RiskDataStatus,
    val priceSource: String,
    val priceUpdatedLabel: String,
    val lotSize: Int,
    val currency: DisplayCurrency,
    val payoutLabel: String,
    val issuerFacts: List<String>,
    val accountLabel: String,
)

internal data class PortfolioPosition(
    val instrumentUid: String,
    val name: String,
    val ticker: String?,
    val isin: String?,
    val quantity: Long,
    val availableQuantity: Long,
    val blockedQuantity: Long,
    val currentPriceMinor: Long?,
    val currentValueMinor: Long?,
    val shareBasisPoints: Int?,
    val priceStatus: PriceStatus,
    val riskStatus: RiskDataStatus,
    val priceSource: String,
    val priceUpdatedLabel: String,
    val lotSize: Int,
    val currency: DisplayCurrency,
    val payoutLabel: String,
    val issuerFacts: List<String>,
    val accounts: List<AccountPositionFixture>,
)

internal fun portfolioFixture(size: PortfolioFixtureSize): List<PortfolioPosition> {
    if (size == PortfolioFixtureSize.DEFAULT) {
        return withPortfolioShares(aggregatePortfolioPositions(defaultRawPositions()))
    }
    if (size.count == 0) {
        return emptyList()
    }
    if (size.count == 1) {
        return withPortfolioShares(aggregatePortfolioPositions(defaultRawPositions())).take(1)
    }
    return withPortfolioShares(generateSyntheticPositions(size.count))
}

internal fun portfolioPositionByUid(instrumentUid: String): PortfolioPosition? {
    val defaultPosition = withPortfolioShares(
        aggregatePortfolioPositions(defaultRawPositions()),
    ).firstOrNull { it.instrumentUid == instrumentUid }
    if (defaultPosition != null) {
        return defaultPosition
    }
    if (!instrumentUid.startsWith(SYNTHETIC_UID_PREFIX)) {
        return null
    }
    val index = instrumentUid.removePrefix(SYNTHETIC_UID_PREFIX).toIntOrNull() ?: return null
    if (index !in 0 until PortfolioFixtureSize.THOUSAND.count) {
        return null
    }
    return withPortfolioShares(generateSyntheticPositions(PortfolioFixtureSize.THOUSAND.count))
        .firstOrNull { it.instrumentUid == instrumentUid }
}

internal fun filterPortfolio(
    positions: List<PortfolioPosition>,
    query: String,
): List<PortfolioPosition> {
    val normalized = query.trim().lowercase()
    if (normalized.isEmpty()) {
        return positions
    }
    return positions.filter { position ->
        sequenceOf(
            position.name,
            position.ticker,
            position.isin,
            position.instrumentUid,
        )
            .filterNotNull()
            .any { it.lowercase().contains(normalized) }
    }
}

internal fun aggregatePortfolioPositions(
    rawPositions: List<RawPortfolioPosition>,
): List<PortfolioPosition> = rawPositions
    .groupBy { it.instrumentUid }
    .values
    .map { group ->
        val first = group.first()
        val knownValue = if (group.all { it.currentValueMinor != null }) {
            group.sumOf { it.currentValueMinor ?: 0L }
        } else {
            null
        }
        PortfolioPosition(
            instrumentUid = first.instrumentUid,
            name = first.name,
            ticker = first.ticker,
            isin = first.isin,
            quantity = group.sumOf { it.quantity },
            availableQuantity = group.sumOf { it.availableQuantity },
            blockedQuantity = group.sumOf { it.blockedQuantity },
            currentPriceMinor = if (group.all { it.currentPriceMinor == first.currentPriceMinor }) {
                first.currentPriceMinor
            } else {
                null
            },
            currentValueMinor = knownValue,
            shareBasisPoints = null,
            priceStatus = group.maxBy { priceStatusRank(it.priceStatus) }.priceStatus,
            riskStatus = group.maxBy { riskStatusRank(it.riskStatus) }.riskStatus,
            priceSource = first.priceSource,
            priceUpdatedLabel = group.maxBy { priceStatusRank(it.priceStatus) }.priceUpdatedLabel,
            lotSize = first.lotSize,
            currency = first.currency,
            payoutLabel = first.payoutLabel,
            issuerFacts = group.flatMap { it.issuerFacts }.distinct(),
            accounts = group.map {
                AccountPositionFixture(
                    accountLabel = it.accountLabel,
                    quantity = it.quantity,
                    availableQuantity = it.availableQuantity,
                    blockedQuantity = it.blockedQuantity,
                    currentValueMinor = it.currentValueMinor,
                )
            },
        )
    }
    .sortedByDescending { it.currentValueMinor ?: Long.MIN_VALUE }

private fun withPortfolioShares(
    positions: List<PortfolioPosition>,
): List<PortfolioPosition> {
    val knownTotal = positions.mapNotNull { it.currentValueMinor }.sum()
    if (knownTotal <= 0L) {
        return positions
    }
    return positions.map { position ->
        val value = position.currentValueMinor
        position.copy(
            shareBasisPoints = if (value == null) {
                null
            } else {
                ((value * 10_000L) / knownTotal).toInt()
            },
        )
    }
}

internal fun formatShare(basisPoints: Int?): String {
    if (basisPoints == null) {
        return "доля: нет данных"
    }
    val whole = basisPoints / 100
    val fraction = basisPoints % 100
    return if (fraction == 0) {
        "доля: " + whole + "%"
    } else {
        "доля: " + whole + "," + fraction.toString().padStart(2, '0') + "%"
    }
}

internal fun formatQuantity(quantity: Long): String = quantity.toString() + " шт."

private fun priceStatusRank(status: PriceStatus): Int = when (status) {
    PriceStatus.CURRENT -> 0
    PriceStatus.STALE -> 1
    PriceStatus.MISSING -> 2
}

private fun riskStatusRank(status: RiskDataStatus): Int = when (status) {
    RiskDataStatus.NORMAL -> 0
    RiskDataStatus.ATTENTION -> 1
    RiskDataStatus.INCOMPLETE -> 2
}

private fun defaultRawPositions(): List<RawPortfolioPosition> = listOf(
    RawPortfolioPosition(
        instrumentUid = "uid-sber-demo",
        name = "Сбер Банк",
        ticker = "SBER",
        isin = "RU0009029540",
        quantity = 70,
        availableQuantity = 70,
        blockedQuantity = 0,
        currentPriceMinor = 31_250,
        currentValueMinor = 2_187_500,
        priceStatus = PriceStatus.CURRENT,
        riskStatus = RiskDataStatus.NORMAL,
        priceSource = "T-Invest exchange fixture",
        priceUpdatedLabel = "5 мин назад",
        lotSize = 10,
        currency = DisplayCurrency.RUB,
        payoutLabel = "Дивиденд: ожидается · fixture",
        issuerFacts = listOf(
            "Эмитент: ПАО Сбербанк · demo",
            "Факт источника отмечается отдельно от локального расчёта.",
        ),
        accountLabel = PRIMARY_ACCOUNT_LABEL,
    ),
    RawPortfolioPosition(
        instrumentUid = "uid-sber-demo",
        name = "Сбер Банк",
        ticker = "SBER",
        isin = "RU0009029540",
        quantity = 50,
        availableQuantity = 48,
        blockedQuantity = 2,
        currentPriceMinor = 31_250,
        currentValueMinor = 1_562_500,
        priceStatus = PriceStatus.CURRENT,
        riskStatus = RiskDataStatus.NORMAL,
        priceSource = "T-Invest exchange fixture",
        priceUpdatedLabel = "5 мин назад",
        lotSize = 10,
        currency = DisplayCurrency.RUB,
        payoutLabel = "Дивиденд: ожидается · fixture",
        issuerFacts = listOf(
            "Эмитент: ПАО Сбербанк · demo",
            "Факт источника отмечается отдельно от локального расчёта.",
        ),
        accountLabel = "ИИС",
    ),
    RawPortfolioPosition(
        instrumentUid = "uid-ofz-26238-demo",
        name = "ОФЗ 26238",
        ticker = "SU26238RMFS4",
        isin = "RU000A1038V6",
        quantity = 34,
        availableQuantity = 34,
        blockedQuantity = 0,
        currentPriceMinor = 5_800,
        currentValueMinor = 1_972_000,
        priceStatus = PriceStatus.STALE,
        riskStatus = RiskDataStatus.ATTENTION,
        priceSource = "T-Invest bond fixture",
        priceUpdatedLabel = "3 ч назад · stale",
        lotSize = 1,
        currency = DisplayCurrency.RUB,
        payoutLabel = "Купон: 18 окт · fixture",
        issuerFacts = listOf(
            "Тип: государственная облигация · demo",
            "Цена помечена устаревшей и не выдаётся за текущую.",
        ),
        accountLabel = PRIMARY_ACCOUNT_LABEL,
    ),
    RawPortfolioPosition(
        instrumentUid = "uid-no-price-demo",
        name = "Облигация без цены",
        ticker = null,
        isin = "RU000DEMO000",
        quantity = 12,
        availableQuantity = 12,
        blockedQuantity = 0,
        currentPriceMinor = null,
        currentValueMinor = null,
        priceStatus = PriceStatus.MISSING,
        riskStatus = RiskDataStatus.INCOMPLETE,
        priceSource = "Цена отсутствует · fixture",
        priceUpdatedLabel = "нет данных",
        lotSize = 1,
        currency = DisplayCurrency.RUB,
        payoutLabel = "Выплаты: нет подтверждённых данных",
        issuerFacts = listOf(
            "Общих фактов недостаточно для оценки · demo.",
        ),
        accountLabel = PRIMARY_ACCOUNT_LABEL,
    ),
)

private fun generateSyntheticPositions(count: Int): List<PortfolioPosition> = List(count) { index ->
    val status = when {
        index % 17 == 0 -> PriceStatus.MISSING
        index % 7 == 0 -> PriceStatus.STALE
        else -> PriceStatus.CURRENT
    }
    val value = if (status == PriceStatus.MISSING) null else 100_000L + index * 10_000L
    PortfolioPosition(
        instrumentUid = SYNTHETIC_UID_PREFIX + index,
        name = "Fixture инструмент " + (index + 1),
        ticker = "FX" + index.toString().padStart(4, '0'),
        isin = "RUDEMO" + index.toString().padStart(6, '0'),
        quantity = (index % 50 + 1).toLong(),
        availableQuantity = (index % 50 + 1).toLong(),
        blockedQuantity = 0,
        currentPriceMinor = if (value == null) null else 10_000L + index,
        currentValueMinor = value,
        shareBasisPoints = null,
        priceStatus = status,
        riskStatus = if (status == PriceStatus.MISSING) {
            RiskDataStatus.INCOMPLETE
        } else {
            RiskDataStatus.NORMAL
        },
        priceSource = "Synthetic local fixture",
        priceUpdatedLabel = when (status) {
            PriceStatus.CURRENT -> "сейчас · fixture"
            PriceStatus.STALE -> "3 ч назад · stale"
            PriceStatus.MISSING -> "нет данных"
        },
        lotSize = 1,
        currency = DisplayCurrency.RUB,
        payoutLabel = "Выплаты: fixture",
        issuerFacts = listOf("Синтетический QA-инструмент."),
        accounts = listOf(
            AccountPositionFixture(
                accountLabel = "Fixture-счёт",
                quantity = (index % 50 + 1).toLong(),
                availableQuantity = (index % 50 + 1).toLong(),
                blockedQuantity = 0,
                currentValueMinor = value,
            ),
        ),
    )
}
