package ru.omnicio.app.data.workspace

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ChatRouteQuoteTest {
    private val standard = ChatRouteQuote(true, "standard", false, 100L, "a".repeat(64))

    @Test fun ordinaryAutoNeedsNoSecondConfirmation() {
        assertTrue(standard.usable)
        assertFalse(standard.needsConfirmation("auto"))
    }

    @Test fun premiumCannotSilentlyDispatchFromAuto() {
        assertTrue(standard.copy(selectedTier = "premium").needsConfirmation("auto"))
        assertTrue(standard.copy(confirmationRequired = true).needsConfirmation("auto"))
        assertTrue(standard.needsConfirmation("premium"))
    }

    @Test fun missingOrMalformedCeilingsFailClosed() {
        listOf(null, -1L, 1_000_000_000_000_001L).forEach {
            assertFalse(standard.copy(ceilingMicroRub = it).usable)
        }
    }

    @Test fun zeroCostLocalRouteCanBeSentWithItsExactQuote() {
        assertTrue(standard.copy(ceilingMicroRub = 0L).usable)
        assertFalse(standard.copy(ceilingMicroRub = 0L, routeId = "").usable)
    }

    @Test fun incompleteOrUnknownRoutesFailClosed() {
        assertFalse(standard.copy(available = false).usable)
        listOf("", "auto", "unknown").forEach { assertFalse(standard.copy(selectedTier = it).usable) }
        listOf("", "a".repeat(63), "G".repeat(64), "https://example.invalid").forEach {
            assertFalse(standard.copy(routeId = it).usable)
        }
    }
}
