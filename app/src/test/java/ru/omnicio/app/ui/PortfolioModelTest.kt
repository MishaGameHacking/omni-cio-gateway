package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PortfolioModelTest {
    @Test
    fun aggregateMergesSameInstrumentAcrossAccounts() {
        val raw = listOf(
            rawPosition(account = "A", quantity = 2, available = 2, blocked = 0, value = 10_000),
            rawPosition(account = "B", quantity = 3, available = 2, blocked = 1, value = 15_000),
        )

        val position = aggregatePortfolioPositions(raw).single()

        assertEquals(5L, position.quantity)
        assertEquals(4L, position.availableQuantity)
        assertEquals(1L, position.blockedQuantity)
        assertEquals(25_000L, position.currentValueMinor)
        assertEquals(listOf("A", "B"), position.accounts.map { it.accountLabel })
    }

    @Test
    fun aggregateDoesNotInventValueWhenOneAccountPriceIsMissing() {
        val raw = listOf(
            rawPosition(account = "A", quantity = 2, available = 2, blocked = 0, value = 10_000),
            rawPosition(
                account = "B",
                quantity = 3,
                available = 3,
                blocked = 0,
                value = null,
                priceStatus = PriceStatus.MISSING,
            ),
        )

        val position = aggregatePortfolioPositions(raw).single()

        assertNull(position.currentValueMinor)
        assertEquals(PriceStatus.MISSING, position.priceStatus)
    }

    @Test
    fun requiredFixtureSizesRemainComplete() {
        assertEquals(0, portfolioFixture(PortfolioFixtureSize.ZERO).size)
        assertEquals(1, portfolioFixture(PortfolioFixtureSize.ONE).size)
        assertEquals(100, portfolioFixture(PortfolioFixtureSize.HUNDRED).size)
        assertEquals(1000, portfolioFixture(PortfolioFixtureSize.THOUSAND).size)
    }

    @Test
    fun localSearchMatchesNameTickerIsinAndUid() {
        val positions = portfolioFixture(PortfolioFixtureSize.DEFAULT)

        assertEquals(1, filterPortfolio(positions, "сбер").size)
        assertEquals(1, filterPortfolio(positions, "SBER").size)
        assertEquals(1, filterPortfolio(positions, "RU0009029540").size)
        assertEquals(1, filterPortfolio(positions, "uid-sber-demo").size)
        assertTrue(filterPortfolio(positions, "external-market-only").isEmpty())
    }

    @Test
    fun staleAndMissingPricesStayExplicit() {
        val positions = portfolioFixture(PortfolioFixtureSize.DEFAULT)

        val stale = positions.first { it.instrumentUid == "uid-ofz-26238-demo" }
        val missing = positions.first { it.instrumentUid == "uid-no-price-demo" }

        assertEquals(PriceStatus.STALE, stale.priceStatus)
        assertEquals(PriceStatus.MISSING, missing.priceStatus)
        assertNull(missing.currentValueMinor)
        assertNull(missing.shareBasisPoints)
    }

    private fun rawPosition(
        account: String,
        quantity: Long,
        available: Long,
        blocked: Long,
        value: Long?,
        priceStatus: PriceStatus = PriceStatus.CURRENT,
    ): RawPortfolioPosition = RawPortfolioPosition(
        instrumentUid = "same-uid",
        name = "Fixture",
        ticker = "FX",
        isin = "RUDEMO",
        quantity = quantity,
        availableQuantity = available,
        blockedQuantity = blocked,
        currentPriceMinor = value,
        currentValueMinor = value,
        priceStatus = priceStatus,
        riskStatus = RiskDataStatus.NORMAL,
        priceSource = "fixture",
        priceUpdatedLabel = "now",
        lotSize = 1,
        currency = DisplayCurrency.RUB,
        payoutLabel = "fixture",
        issuerFacts = listOf("fixture"),
        accountLabel = account,
    )
}
