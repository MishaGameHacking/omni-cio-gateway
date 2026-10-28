package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.saveable.listSaver

val StrategyDraftSaver = listSaver<StrategyDraft, Any>(
    save = { listOf(it.goal, it.horizon, it.market, it.qualification, it.reserve, it.companyLimit,
        it.sectorLimit, it.reinvest, it.currencyIncome, it.ratings.joinToString("|")) },
    restore = { StrategyDraft(goal = it[0] as Int, horizon = it[1] as Int, market = it[2] as Int,
        qualification = it[3] as Int, reserve = it[4] as Int, companyLimit = it[5] as Int,
        sectorLimit = it[6] as Int, reinvest = it[7] as Int, currencyIncome = it[8] as Boolean,
        ratings = (it[9] as String).split("|").filter { rating -> rating in RatingChoices }.toSet()) },
)

internal val StrategyPercentDraftSaver = listSaver<StrategyPercentDraft, String>(
    save = { listOf(it.reserve, it.company, it.sector) },
    restore = { if (it.size == 3) StrategyPercentDraft(it[0], it[1], it[2]) else null },
)
