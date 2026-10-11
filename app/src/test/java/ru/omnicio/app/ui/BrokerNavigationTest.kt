package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class BrokerNavigationTest {
    private val position = PortfolioPosition("synthetic-id", "SYNTHETIC", "Test",
        null, null, null, null, null, false, null, "share")

    @Test fun brokerDestinationIsBoundToOfficialHostAndKnownInstrumentType() {
        assertEquals("https://www.tbank.ru/invest/stocks/SYNTHETIC/", brokerInstrumentUrl(position))
        assertNull(brokerInstrumentUrl(position.copy(ticker = "../login?redirect=other")))
        assertNull(brokerInstrumentUrl(position.copy(ticker = "")))
        assertNull(brokerInstrumentUrl(position.copy(instrumentType = "future")))
        assertNull(brokerInstrumentUrl(position.copy(instrumentType = null)))
    }
}
