package ru.omnicio.app.ui.theme

import org.junit.Assert.assertFalse
import org.junit.Test

class DisplayedThemeTest {
    @Test fun savedModesCannotChangeTheSingleStyleWhenSystemPreferenceChanges() {
        for (mode in ThemeMode.entries) for (systemDark in listOf(false, true))
            for (last in listOf(null, false, true)) for (configuration in listOf(false, true))
                assertFalse(displayedThemeDark(mode, SystemThemeObservation.Known(systemDark), last, configuration))
    }
    @Test fun unavailableDisplayCannotIntroduceAnotherPalette() {
        for (reason in SystemThemeUnavailableReason.entries) for (mode in ThemeMode.entries)
            assertFalse(displayedThemeDark(mode, SystemThemeObservation.Unknown(reason), false, false))
    }
}

