package ru.omnicio.app.ui.portfolio

import java.math.BigDecimal
import java.math.MathContext
import java.time.YearMonth
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.workspace.records

internal data class TerminalAllocation(val label: String, val percent: BigDecimal)
internal data class TerminalPayment(val month: String, val currency: String, val amount: BigDecimal)
internal data class TerminalPayments(val rows: List<TerminalPayment>, val missingAmounts: Int, val complete: Boolean)

/** Never add different currencies or silently drop an unavailable account. */
internal fun terminalSum(amounts: List<MoneyAmount?>, currency: String): BigDecimal? =
    amounts.takeIf { it.isNotEmpty() && it.all { value -> value != null && value.currency.equals(currency, true) } }
        ?.sumOf { it!!.value.toBigDecimal() }

/** A partial allocation leaves an explicit unknown slice; shorts are not a pie chart. */
internal fun terminalAllocation(allocations: List<PortfolioAllocation>): List<TerminalAllocation>? {
    if (allocations.isEmpty() || allocations.any { it.title.isBlank() || it.sharePercent.toBigDecimal().signum() < 0 }) return null
    val grouped = allocations.groupBy { it.title }.map { (title, rows) ->
        TerminalAllocation(title, rows.sumOf { it.sharePercent.toBigDecimal() })
    }.filter { it.percent.signum() > 0 }.sortedByDescending { it.percent }
    val sum = grouped.sumOf { it.percent }
    if (sum.signum() <= 0 || sum > BigDecimal("100.05")) return null
    if (sum < BigDecimal("99.95")) return grouped + TerminalAllocation("Не распределено", BigDecimal(100) - sum)
    // Only broker rounding within 0.05 percentage points is normalized for geometry.
    return grouped.map { it.copy(percent = it.percent.multiply(BigDecimal(100)).divide(sum, MathContext.DECIMAL64)) }
}

internal fun terminalPayments(documents: List<JSONObject>): TerminalPayments {
    var missing = 0
    val values = documents.flatMap { it.records("items") }.mapNotNull { row ->
        val month = runCatching { YearMonth.parse(row.optString("date").take(7)).toString() }.getOrNull()
        val estimate = row.optJSONObject("estimate")
        val number = estimate?.optJSONObject("value")
        val units = number?.optString("units")?.toBigDecimalOrNull()
        val nano = number?.optString("nano")?.toIntOrNull()
        val currency = estimate?.optString("currency")?.takeIf { it.matches(Regex("[A-Za-z]{3}")) }?.uppercase()
        if (month == null || units == null || nano == null || nano !in -999999999..999999999 || currency == null) {
            missing++; null
        } else {
            val amount = units + BigDecimal.valueOf(nano.toLong(), 9)
            if (amount.signum() < 0) { missing++; null } else TerminalPayment(month, currency, amount)
        }
    }
    return TerminalPayments(values.groupBy { it.month to it.currency }.map { (key, rows) ->
        TerminalPayment(key.first, key.second, rows.sumOf { it.amount })
    }.sortedWith(compareBy<TerminalPayment> { it.currency }.thenBy { it.month }), missing,
        documents.isNotEmpty() && documents.all { it.optBoolean("complete") })
}
