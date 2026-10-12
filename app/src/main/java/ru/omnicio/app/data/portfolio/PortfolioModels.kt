package ru.omnicio.app.data.portfolio

import java.math.BigDecimal

enum class PortfolioCurrency {
    RUB, USD, EUR;
    fun next(): PortfolioCurrency = entries[(ordinal + 1) % entries.size]
}

data class ApiDecimal(val units: Long, val nano: Int) {
    fun toBigDecimal(): BigDecimal = BigDecimal.valueOf(units).add(BigDecimal.valueOf(nano.toLong(), 9))
}

data class MoneyAmount(val value: ApiDecimal, val currency: String)

data class PortfolioPosition(
    val id: String,
    val title: String,
    val ticker: String?,
    val quantity: ApiDecimal?,
    val currentValue: MoneyAmount?,
    val expectedYieldPercent: ApiDecimal?,
    val currentPrice: MoneyAmount? = null,
    val averagePrice: MoneyAmount? = null,
    val expectedYieldAmount: MoneyAmount? = null,
    val dailyYieldAmount: MoneyAmount? = null,
    val currentNkd: MoneyAmount? = null,
    val blocked: Boolean = false,
    val blockedQuantity: ApiDecimal? = null,
    val instrumentType: String = "",
    val sector: String? = null,
    val company: String? = null,
    val isin: String? = null,
    val exchange: String? = null,
)

data class PortfolioAccount(
    val id: String,
    val name: String,
    val totalValue: MoneyAmount,
    val expectedYieldPercent: ApiDecimal?,
    val positions: List<PortfolioPosition>,
    val dailyYieldAmount: MoneyAmount? = null,
    val dailyYieldPercent: ApiDecimal? = null,
    val allocations: List<PortfolioAllocation> = emptyList(),
    val openedAt: String? = null,
    val accountType: String? = null,
    val limitsLoading: Boolean = false,
    val virtualPositions: List<PortfolioPosition> = emptyList(),
)

data class PortfolioAllocation(val title: String, val sharePercent: ApiDecimal)

data class PortfolioSnapshot(
    val totalValue: MoneyAmount,
    val expectedYieldAmount: MoneyAmount?,
    val expectedYieldPercent: ApiDecimal?,
    val accounts: List<PortfolioAccount>,
    val allocations: List<PortfolioAllocation>,
    val asOf: String? = null,
    val warnings: List<String> = emptyList(),
)

sealed interface PortfolioUiState {
    data object NotConnected : PortfolioUiState
    data object ApiConnected : PortfolioUiState
    data object Loading : PortfolioUiState
    data class Ready(val snapshot: PortfolioSnapshot) : PortfolioUiState
    data class Error(val message: String) : PortfolioUiState
}
