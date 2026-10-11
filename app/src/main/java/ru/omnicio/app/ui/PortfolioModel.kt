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
)

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
