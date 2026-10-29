package ru.omnicio.app.ui.theme

import org.junit.Assert.assertEquals
import org.junit.Test

class DisplayedThemeTest {
    @Test fun explicitThemesSurviveOppositeSystemPreference() {
        for (system in listOf(false, true)) {
            assertEquals(false, displayedThemeDark(ThemeMode.LIGHT, SystemThemeObservation.Known(system), true, true))
            assertEquals(true, displayedThemeDark(ThemeMode.DARK, SystemThemeObservation.Known(system), false, false))
            assertEquals(system, displayedThemeDark(ThemeMode.SYSTEM, SystemThemeObservation.Known(system), null, !system))
        }
    }
    @Test fun unknownSystemUsesLastDisplayedBeforeApplicationFallback() {
        val unknown = SystemThemeObservation.Unknown(SystemThemeUnavailableReason.NO_DISPLAY)
        assertEquals(true, displayedThemeDark(ThemeMode.SYSTEM, unknown, true, false))
        assertEquals(false, displayedThemeDark(ThemeMode.SYSTEM, unknown, null, false))
    }
}
