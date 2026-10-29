package ru.omnicio.app.ui.portfolio

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.math.BigDecimal

class AnalyticsWorkspaceTest {
    private fun document(currency: String, points: String) = JSONObject("""{"currency":"$currency","history":[$points]}""")
    @Test fun multiAccountHistoryNeverFillsAbsentBalances() {
        val a = document("RUB", """{"date":"2026-01-01T00:00:00Z","value":"100"},{"date":"2026-01-02T00:00:00Z","value":"110"}""")
        val b = document("RUB", """{"date":"2026-01-02T00:00:00Z","value":"200"}""")
        val points = joinedAnalyticsHistory(listOf(a, b))
        assertEquals(1, points.size)
        assertEquals("2026-01-02T00:00:00Z", points.single().date)
        assertEquals(BigDecimal("310"), points.single().value)
    }
    @Test fun currenciesAndMissingAccountsAreNeverSummed() {
        val a = document("RUB", """{"date":"2026-01-01T00:00:00Z","value":"100"}""")
        val b = document("USD", """{"date":"2026-01-01T00:00:00Z","value":"2"}""")
        assertTrue(joinedAnalyticsHistory(listOf(a, b)).isEmpty())
        assertTrue(joinedAnalyticsHistory(listOf(a, document("RUB", ""))).isEmpty())
    }
}
