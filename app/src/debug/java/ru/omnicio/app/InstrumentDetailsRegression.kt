package ru.omnicio.app

import java.util.Locale
import ru.omnicio.app.ui.portfolio.instrumentDetailLabels

/** Offline label checks; no device rendering or actual financial records. */
internal fun runInstrumentDetailsChecks(): Int {
    var count = 0
    fun verify(value: Boolean) { check(value); count++ }
    for (kind in listOf("cash", "currency")) {
        val labels = instrumentDetailLabels(kind, false)
        verify(labels.quantity == "Количество, единиц валюты")
        verify(labels.accrued == null)
    }
    for (kind in listOf("share", "bond", "etf")) {
        verify(instrumentDetailLabels(kind, false).quantity == "Количество, шт.")
    }
    verify(instrumentDetailLabels("bond", false).accrued == "НКД на одну облигацию")
    verify(instrumentDetailLabels("share", false).accrued == null)
    verify(instrumentDetailLabels("share", true).accrued == "Начисленный доход (данные API)")
    for (kind in listOf("", "future", "option", "unexpected")) {
        verify(instrumentDetailLabels(kind, false).quantity == "Количество по данным брокера")
    }
    verify(instrumentDetailLabels("unexpected", false).type == "Тип не определён")
    verify(instrumentDetailLabels("  BOND  ", false) == instrumentDetailLabels("bond", false))
    val original = Locale.getDefault()
    try {
        Locale.setDefault(Locale.forLanguageTag("tr-TR"))
        verify(instrumentDetailLabels("CURRENCY", false).type == "Валюта")
        verify(instrumentDetailLabels("SHARE", false).type == "Акция")
    } finally { Locale.setDefault(original) }
    return count
}

fun main() { println("INSTRUMENT_DETAIL_CHECKS=" + runInstrumentDetailsChecks()) }
