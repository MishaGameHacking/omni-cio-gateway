package ru.omnicio.app.ui

import java.math.BigDecimal

internal data class PortfolioPosition(
    val uid: String,
    val ticker: String,
    val name: String,
    val quantity: BigDecimal?,
    val value: BigDecimal?,
    val price: BigDecimal?,
    val currency: String?,
    val share: BigDecimal?,
    val blocked: Boolean,
    val riskStatus: String?,
    val instrumentType: String? = null,
)

/** Official web card is also the fallback when Android cannot open the broker app. */
internal fun brokerInstrumentUrl(position: PortfolioPosition): String? {
    val section = mapOf("share" to "stocks", "bond" to "bonds", "etf" to "etfs")[position.instrumentType]
        ?: return null
    if (!Regex("[A-Za-z0-9_-]{1,32}").matches(position.ticker)) return null
    return "https://www.tbank.ru/invest/$section/${position.ticker}/"
}

internal data class ServerPortfolio(
    val capturedAt: String?,
    val freshness: String?,
    val analysisStatus: String?,
    val total: BigDecimal?,
    val cash: BigDecimal?,
    val freeCash: BigDecimal?,
    val blockedCash: BigDecimal?,
    val positions: List<PortfolioPosition>,
    val history: List<HistoryPoint>,
    val sources: List<SourceInfo>,
)

internal data class PortfolioAllocation(val label: String, val value: BigDecimal)

/** Use only complete nonnegative valuations; do not turn absent data into a zero slice. */
internal fun portfolioAllocation(portfolio: ServerPortfolio): List<PortfolioAllocation> {
    val total = portfolio.total?.takeIf { it.signum() > 0 } ?: return emptyList()
    val cash = portfolio.cash?.takeIf { it.signum() >= 0 } ?: return emptyList()
    if (portfolio.positions.any { it.value == null || it.value.signum() < 0 }) return emptyList()
    val values = portfolio.positions.groupBy { position ->
        when (position.instrumentType) {
            "share" -> "Акции"
            "bond" -> "Облигации"
            "etf" -> "Фонды"
            else -> "Другие инструменты"
        }
    }.map { (label, positions) -> PortfolioAllocation(label, positions.fold(BigDecimal.ZERO) { sum, item ->
        sum + requireNotNull(item.value)
    }) }.toMutableList()
    values.add(PortfolioAllocation("Рубли", cash))
    val remainder = total - values.fold(BigDecimal.ZERO) { sum, item -> sum + item.value }
    if (remainder.signum() < 0) return emptyList()
    if (remainder.signum() > 0) values.add(PortfolioAllocation("Прочая стоимость", remainder))
    return values.filter { it.value.signum() > 0 }
}

