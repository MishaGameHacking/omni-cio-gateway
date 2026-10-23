package ru.omnicio.app.ui.workspace

internal enum class StrategyPercentField(val range: IntRange) {
    Reserve(0..50), Company(1..15), Sector(5..50),
}

/** Visible numeric input belongs to the whole draft, including incomplete edits. */
internal data class StrategyPercentDraft(val reserve: String, val company: String, val sector: String) {
    constructor(draft: StrategyDraft) : this(
        draft.reserve.toString(), draft.companyLimit.toString(), draft.sectorLimit.toString(),
    )

    fun text(field: StrategyPercentField): String = when (field) {
        StrategyPercentField.Reserve -> reserve
        StrategyPercentField.Company -> company
        StrategyPercentField.Sector -> sector
    }

    fun edit(field: StrategyPercentField, text: String): StrategyPercentDraft {
        val next = text.take(3)
        return when (field) {
            StrategyPercentField.Reserve -> copy(reserve = next)
            StrategyPercentField.Company -> copy(company = next)
            StrategyPercentField.Sector -> copy(sector = next)
        }
    }

    fun value(field: StrategyPercentField): Int? = text(field).toIntOrNull()?.takeIf { it in field.range }

    /** No previous numeric value can silently replace an invalid visible field. */
    fun applyTo(draft: StrategyDraft): StrategyDraft? {
        val reserveValue = value(StrategyPercentField.Reserve) ?: return null
        val companyValue = value(StrategyPercentField.Company) ?: return null
        val sectorValue = value(StrategyPercentField.Sector) ?: return null
        return draft.copy(reserve = reserveValue, companyLimit = companyValue, sectorLimit = sectorValue)
    }
}
