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

val StrategyDraftSaver = androidx.compose.runtime.saveable.listSaver<StrategyDraft, Any>(
    save = { listOf(it.goal, it.horizon, it.market, it.qualification, it.reserve, it.companyLimit,
        it.sectorLimit, it.reinvest, it.currencyIncome, it.ratings.joinToString("|")) },
    restore = { StrategyDraft(goal = it[0] as Int, horizon = it[1] as Int, market = it[2] as Int,
        qualification = it[3] as Int, reserve = it[4] as Int, companyLimit = it[5] as Int,
        sectorLimit = it[6] as Int, reinvest = it[7] as Int, currencyIncome = it[8] as Boolean,
        ratings = (it[9] as String).split("|").filter { rating -> rating in RatingChoices }.toSet()) },
)
