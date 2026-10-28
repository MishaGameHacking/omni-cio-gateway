package ru.omnicio.app.ui.theme

import org.junit.Assert.assertTrue
import org.junit.Test

class DisplayedThemeTest {
    @Test fun savedModesCannotChangeTheSingleStyleWhenSystemPreferenceChanges() {
        for (mode in ThemeMode.entries) for (systemDark in listOf(false, true))
            for (last in listOf(null, false, true)) for (configuration in listOf(false, true))
                assertTrue(displayedThemeDark(mode, SystemThemeObservation.Known(systemDark), last, configuration))
    }
    @Test fun unavailableDisplayCannotIntroduceAnotherPalette() {
        for (reason in SystemThemeUnavailableReason.entries) for (mode in ThemeMode.entries)
            assertTrue(displayedThemeDark(mode, SystemThemeObservation.Unknown(reason), false, false))
    }
}
