package ru.omnicio.app.ui

import java.math.BigDecimal
import org.junit.Assert.*
import org.junit.Test

class OverviewModelTest {
    @Test fun unknownAndConfirmedZeroHaveDifferentLabels() {
        assertEquals("Нет данных", money(null))
        assertTrue(money(BigDecimal.ZERO).startsWith("0,00"))
        assertEquals("••••", money(BigDecimal("9.99"), hidden = true))
    }

    @Test fun flatSeriesAndLargePreciseValuesHaveFiniteCoordinates() {
        assertEquals(0.5f, chartFraction(BigDecimal.ONE, BigDecimal("1.0"), BigDecimal.ONE))
        val min = BigDecimal("999999999999999.0001")
        val max = BigDecimal("999999999999999.0003")
        assertEquals(0.5f, chartFraction(BigDecimal("999999999999999.0002"), min, max))
    }

    @Test fun missingTimeOrStateCannotBecomeFresh() {
        assertEquals("Время не указано", timestampLabel(null))
        assertEquals("Время не указано", timestampLabel("not-a-time"))
        assertEquals("Нет подтверждённых данных", statusLabel(null))
        assertEquals("Данные устарели", statusLabel("stale"))
    }
}
