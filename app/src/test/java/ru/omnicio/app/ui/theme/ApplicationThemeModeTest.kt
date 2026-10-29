package ru.omnicio.app.ui.theme

import android.content.res.Configuration
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class ApplicationThemeModeTest {
    private class Source : SystemThemeSource {
        var currentValue: SystemThemeObservation = SystemThemeObservation.Known(false)
        var callback: ((SystemThemeObservation) -> Unit)? = null
        val calls = mutableListOf<String>()
        var registrationFailure = false
        var readFailure = false
        var unexpectedReadFailure = false
        var cleanupFailure = false

        override fun current(): SystemThemeObservation {
            calls += "current"
            if (readFailure) throw SystemThemePlatformFailure(SystemThemeUnavailableReason.DISPLAY_UNAVAILABLE)
            if (unexpectedReadFailure) throw IllegalStateException("Synthetic programming failure")
            return currentValue
        }

        override fun register(listener: (SystemThemeObservation) -> Unit) {
            calls += "register"
            callback = listener
            if (registrationFailure) throw SystemThemePlatformFailure(SystemThemeUnavailableReason.CONTEXT_UNAVAILABLE)
        }

        override fun unregister(listener: (SystemThemeObservation) -> Unit) {
            calls += "unregister"
            assertTrue(callback === listener)
            if (cleanupFailure) throw SystemThemePlatformFailure(SystemThemeUnavailableReason.DISPLAY_UNAVAILABLE)
        }
    }

    @Test fun applicationPolicyUsesThePlatformApplicationContract() {
        assertEquals(1, applicationNightMode(ThemeMode.LIGHT))
        assertEquals(2, applicationNightMode(ThemeMode.DARK))
        assertEquals(0, applicationNightMode(ThemeMode.SYSTEM))
    }

    @Test fun undefinedNightBitsAreUnknownRatherThanInventedDaylight() {
        assertEquals(SystemThemeObservation.Known(false), systemThemeObservation(Configuration.UI_MODE_TYPE_NORMAL or Configuration.UI_MODE_NIGHT_NO))
        assertEquals(SystemThemeObservation.Known(true), systemThemeObservation(Configuration.UI_MODE_TYPE_DESK or Configuration.UI_MODE_NIGHT_YES))
        assertEquals(SystemThemeObservation.Unknown(SystemThemeUnavailableReason.UNDEFINED_CONFIGURATION),
            systemThemeObservation(Configuration.UI_MODE_TYPE_NORMAL))
        assertEquals(SystemThemeObservation.Unknown(SystemThemeUnavailableReason.UNDEFINED_CONFIGURATION),
            systemThemeObservation(Configuration.UI_MODE_NIGHT_MASK))
    }

    @Test fun sessionSubscribesBeforeReadingAndPublishesRealSourceChanges() {
        val source = Source()
        val observed = mutableListOf<SystemThemeObservation>()
        val session = SystemThemeObservationSession(source) { observed += it }
        assertEquals(listOf("register", "current"), source.calls)
        assertEquals(listOf(SystemThemeObservation.Known(false)), observed)
        source.callback!!(SystemThemeObservation.Known(true))
        source.callback!!(SystemThemeObservation.Unknown(SystemThemeUnavailableReason.UNDEFINED_CONFIGURATION))
        assertEquals(listOf(SystemThemeObservation.Known(false), SystemThemeObservation.Known(true),
            SystemThemeObservation.Unknown(SystemThemeUnavailableReason.UNDEFINED_CONFIGURATION)), observed)
        session.close()
    }

    @Test fun queuedCallbacksCannotChangeTheUiAfterDisposal() {
        val source = Source()
        val observed = mutableListOf<SystemThemeObservation>()
        val session = SystemThemeObservationSession(source) { observed += it }
        val queued = source.callback!!
        session.close()
        session.close()
        queued(SystemThemeObservation.Known(true))
        assertEquals(listOf(SystemThemeObservation.Known(false)), observed)
        assertEquals(listOf("register", "current", "unregister"), source.calls)
    }

    @Test fun partialRegistrationFailureIsExplicitAndStillUnregisters() {
        val source = Source().apply { registrationFailure = true }
        val observed = mutableListOf<SystemThemeObservation>()
        val session = SystemThemeObservationSession(source) { observed += it }
        source.callback!!(SystemThemeObservation.Known(true))
        session.close()
        assertEquals(listOf(SystemThemeObservation.Unknown(SystemThemeUnavailableReason.CONTEXT_UNAVAILABLE)), observed)
        assertEquals(listOf("register", "unregister"), source.calls)
    }

    @Test fun removedDisplayDuringInitialReadCannotRetainAPreviousKnownValue() {
        val source = Source().apply { readFailure = true }
        val observed = mutableListOf<SystemThemeObservation>()
        val session = SystemThemeObservationSession(source) { observed += it }
        source.callback!!(SystemThemeObservation.Known(true))
        session.close()
        assertEquals(listOf(SystemThemeObservation.Unknown(SystemThemeUnavailableReason.DISPLAY_UNAVAILABLE)), observed)
        assertEquals(listOf("register", "current", "unregister"), source.calls)
    }

    @Test fun removedContextDuringCleanupDoesNotRearmItsCallback() {
        val source = Source().apply { cleanupFailure = true }
        val observed = mutableListOf<SystemThemeObservation>()
        val session = SystemThemeObservationSession(source) { observed += it }
        session.close()
        source.callback!!(SystemThemeObservation.Known(true))
        session.close()
        assertEquals(listOf(SystemThemeObservation.Known(false)), observed)
        assertEquals(listOf("register", "current", "unregister"), source.calls)
    }

    @Test fun unexpectedFailuresPropagateAfterReleasingTheRegistration() {
        val source = Source().apply { unexpectedReadFailure = true }
        val observed = mutableListOf<SystemThemeObservation>()
        try {
            SystemThemeObservationSession(source) { observed += it }
            fail("Unexpected programming failure was swallowed")
        } catch (expected: IllegalStateException) {
            assertEquals("Synthetic programming failure", expected.message)
        }
        source.callback!!(SystemThemeObservation.Known(true))
        assertTrue(observed.isEmpty())
        assertEquals(listOf("register", "current", "unregister"), source.calls)
    }
}


