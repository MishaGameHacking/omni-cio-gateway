package ru.omnicio.app.ui.workspace

/** Presentation draft only. Never consumed by trade, recommendation or risk calculations. */
data class StrategyDraft(
    val goal: Int = 0,
    val horizon: Int = 2,
    val market: Int = 0,
    val qualification: Int = 0,
    val reserve: Int = 10,
    val companyLimit: Int = 5,
    val sectorLimit: Int = 25,
    val reinvest: Int = 0,
    val currencyIncome: Boolean = true,
    val ratings: Set<String> = RatingChoices.toSet(),
)
val RatingChoices = listOf("AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-")
