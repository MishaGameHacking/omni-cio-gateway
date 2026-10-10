package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AssistantModelTest {
    @Test
    fun feedContainsAllRequiredEventFamilies() {
        val types = assistantFeed().map { it.type }.toSet()

        assertEquals(AssistantEventType.entries.toSet(), types)
    }

    @Test
    fun repeatedPublicationDoesNotDuplicateOneEvent() {
        val feed = assistantFeed()
        val payoutMessages = feed.filter { it.eventKey == "payout-demo" }

        assertEquals(1, payoutMessages.size)
        assertTrue(payoutMessages.single().changed.contains("уточнена"))
    }

    @Test
    fun insufficientDataCannotInventImpactOrAction() {
        val message = assistantFeed().first { it.eventKey == "issuer-sber-demo" }

        assertFalse(message.sufficientData)
        assertNull(message.impact)
        assertNull(message.action)
        assertEquals(
            "Числовое влияние: недостаточно данных",
            formatAssistantImpact(message.impact),
        )
    }

    @Test
    fun deterministicImpactFormattingIsStableAcrossReopen() {
        val firstOpen = assistantFeed()
        val secondOpen = assistantFeed()
        val risk = firstOpen.first { it.eventKey == "risk-ofz-demo" }

        assertEquals(firstOpen, secondOpen)
        assertEquals("Числовое влияние: +80 б.п.", formatAssistantImpact(risk.impact))
    }

    @Test
    fun ordinaryPushPreviewOmitsPortfolioDetailsAndAmounts() {
        val message = assistantFeed().first { it.eventKey == "cash-demo" }
        val preview = assistantPushPreview(message)
        val impact = formatAssistantImpact(message.impact)

        assertEquals("OMNICIO · важное обновление", preview.title)
        assertFalse(preview.body.contains(message.changed))
        assertFalse(preview.body.contains(impact))
        assertFalse(preview.body.contains("1 500"))
        assertTrue(preview.body.contains("OMNICIO"))
    }

    @Test
    fun assistantExposesOnlySafeNonTradingActions() {
        val kinds = assistantFeed().mapNotNull { it.action?.kind }.toSet()
        val labels = assistantFeed().mapNotNull { it.action?.label }.joinToString(" ").uppercase()

        assertEquals(
            setOf(
                AssistantActionKind.OPEN_SOURCE,
                AssistantActionKind.OPEN_POSITION,
                AssistantActionKind.RUN_SCENARIO,
                AssistantActionKind.SYNC,
            ),
            kinds,
        )
        assertFalse(labels.contains("BUY"))
        assertFalse(labels.contains("SELL"))
        assertFalse(labels.contains("HOLD"))
        assertFalse(labels.contains("КУПИТЬ"))
        assertFalse(labels.contains("ПРОДАТЬ"))
    }
}
