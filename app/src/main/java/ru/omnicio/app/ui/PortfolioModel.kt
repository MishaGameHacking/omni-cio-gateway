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
