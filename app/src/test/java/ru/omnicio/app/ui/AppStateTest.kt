package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class AppStateTest {
    @Test
    fun installationIdLabelShortensLongLocalId() {
        assertEquals("12345678…", installationIdLabel("12345678-1234-5678"))
    }

    @Test
    fun installationIdLabelKeepsShortIdReadable() {
        assertEquals("local", installationIdLabel("local"))
    }

    @Test
    fun moneyFormattingKeepsUnknownDistinctFromZero() {
        assertEquals("нет данных", formatMoney(null, DisplayCurrency.RUB, hidden = false))
        assertEquals("0 ₽", formatMoney(0, DisplayCurrency.RUB, hidden = false))
    }

    @Test
    fun moneyFormattingHandlesSmallLargeNegativeAndForeignCurrencyValues() {
        assertEquals("100 ₽", formatMoney(10_000, DisplayCurrency.RUB, hidden = false))
        assertEquals(
            "100 000 000 ₽",
            formatMoney(10_000_000_000, DisplayCurrency.RUB, hidden = false),
        )
        assertEquals("-1 250 ₽", formatMoney(-125_000, DisplayCurrency.RUB, hidden = false))
        assertEquals("1 234,56 $", formatMoney(123_456, DisplayCurrency.USD, hidden = false))
    }

    @Test
    fun hiddenMoneyNeverLeaksAmountOrCurrency() {
        assertEquals("••••", formatMoney(123_456, DisplayCurrency.EUR, hidden = true))
    }

    @Test
    fun partialOverviewDoesNotInventMissingMoney() {
        val snapshot = overviewSnapshot(OverviewMode.PARTIAL, DisplayCurrency.RUB)
        assertEquals(null, snapshot.availableMinor)
        assertEquals(null, snapshot.scenarioBudgetMinor)
        assertEquals(15_000_000L, snapshot.reserveMinor)
    }

    @Test
    fun disconnectedAndEmptyStatesHaveDifferentSemantics() {
        val disconnected = overviewSnapshot(OverviewMode.DISCONNECTED, DisplayCurrency.RUB)
        val empty = overviewSnapshot(OverviewMode.EMPTY, DisplayCurrency.RUB)

        assertEquals(null, disconnected.totalMinor)
        assertEquals(0L, empty.totalMinor)
    }
}
