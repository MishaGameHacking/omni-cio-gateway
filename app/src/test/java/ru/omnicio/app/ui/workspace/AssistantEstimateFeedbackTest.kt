package ru.omnicio.app.ui.workspace

import org.junit.Assert.*
import org.junit.Test
import ru.omnicio.app.data.workspace.ChatRouteQuote

class AssistantEstimateFeedbackTest {
    private val approved = ChatRouteQuote(true, "fast", false, 10_000L, "a".repeat(64))

    @Test fun successfulTransportStillShowsARejectedCurrentQuote() {
        val denied = approved.copy(available = false)
        val message = requireNotNull(assistantEstimateFeedback(denied, true, "ai_broker_connection_required"))
        assertTrue(message.contains("T‑Invest"))
        assertFalse(denied.usable)
    }

    @Test fun changedDraftDoesNotShowTheOldDenial() {
        assertNull(assistantEstimateFeedback(approved.copy(available = false), false,
            "ai_broker_connection_required"))
    }

    @Test fun noResponseDoesNotInventAFailure() {
        assertNull(assistantEstimateFeedback(null, true, null))
    }

    @Test fun approvedQuoteAndPremiumConfirmationAreNotRejections() {
        assertNull(assistantEstimateFeedback(approved, true, null))
        val premium = approved.copy(selectedTier = "premium", confirmationRequired = true)
        assertTrue(premium.needsConfirmation("auto"))
        assertNull(assistantEstimateFeedback(premium, true, null))
    }

    @Test fun malformedApprovalCannotSilentlyLookReady() {
        for (quote in listOf(approved.copy(ceilingMicroRub = null), approved.copy(ceilingMicroRub = -1),
            approved.copy(routeId = ""), approved.copy(selectedTier = "unknown"))) {
            assertFalse(quote.usable)
            assertNotNull(assistantEstimateFeedback(quote, true, null))
        }
    }

    @Test fun localInferenceWithZeroCostIsAUsableQuote() {
        val local = approved.copy(ceilingMicroRub = 0)
        assertTrue(local.usable)
        assertNull(assistantEstimateFeedback(local, true, null))
    }

    @Test fun unknownReasonUsesAFixedMessageInsteadOfUpstreamData() {
        val denied = approved.copy(available = false)
        val expected = assistantEstimateFeedback(denied, true, null)
        assertNotNull(expected)
        assertEquals(expected, assistantEstimateFeedback(denied, true, "private upstream response"))
        assertFalse(expected!!.contains("private"))
    }
}
