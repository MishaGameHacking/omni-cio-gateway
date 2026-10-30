package ru.omnicio.app.ui.portfolio

import java.math.BigDecimal
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import ru.omnicio.app.data.portfolio.*

class TerminalMetricsTest {
    private fun money(n: Long,currency: String="RUB")=MoneyAmount(ApiDecimal(n,0),currency)
    private fun slice(name: String,n: Long)=PortfolioAllocation(name,ApiDecimal(n,0))

    @Test fun mixedCurrenciesAndMissingAccountsNeverProduceATotal() {
        assertNull(terminalSum(listOf(money(100),money(50,"USD")),"RUB"))
        assertNull(terminalSum(listOf(money(100),null),"RUB"))
        assertNull(terminalSum(emptyList(),"RUB"))
        assertEquals(0,BigDecimal(150).compareTo(terminalSum(listOf(money(100),money(50)),"RUB")))
    }

    @Test fun partialAllocationRetainsUnknownShareInsteadOfInflatingKnownAssets() {
        val result=terminalAllocation(listOf(slice("Акции",25),slice("Деньги",50)))!!
        assertEquals(0,BigDecimal(25).compareTo(result.first { it.label=="Акции" }.percent))
        assertEquals(0,BigDecimal(25).compareTo(result.last().percent))
        assertEquals("Не распределено",result.last().label)
    }

    @Test fun shortAndOverallocatedPortfoliosAreNotRenderedAsAnOrdinaryDonut() {
        assertNull(terminalAllocation(listOf(slice("Акции",120),slice("Деньги",-20))))
        assertNull(terminalAllocation(listOf(slice("Акции",70),slice("Деньги",50))))
        assertNull(terminalAllocation(listOf(slice("Акции",0))))
    }

    private fun payment(month: String,amount: Long,currency: String)=JSONObject().put("date",month+"-15")
        .put("estimate",JSONObject().put("value",JSONObject().put("units",amount.toString()).put("nano",0)).put("currency",currency))

    @Test fun paymentChartsKeepCurrenciesSeparateAndDiscloseMissingEstimates() {
        val doc=JSONObject().put("complete",true).put("items",JSONArray()
            .put(payment("2026-11",100,"RUB")).put(payment("2026-11",50,"RUB"))
            .put(payment("2026-11",2,"USD")).put(JSONObject().put("date","2026-12-01")))
        val result=terminalPayments(listOf(doc))
        assertEquals(2,result.rows.size)
        assertEquals(BigDecimal(150),result.rows.first { it.currency=="RUB" }.amount.stripTrailingZeros().setScale(0))
        assertEquals(1,result.missingAmounts)
        assertTrue(result.complete)
    }

    @Test fun malformedDatesAndNegativeEstimatesDoNotBecomeZeroPayments() {
        val doc=JSONObject().put("complete",false).put("items",JSONArray()
            .put(payment("not-date",50,"RUB")).put(payment("2026-12",-2,"RUB")))
        val result=terminalPayments(listOf(doc))
        assertTrue(result.rows.isEmpty())
        assertEquals(2,result.missingAmounts)
        assertFalse(result.complete)
    }
}
