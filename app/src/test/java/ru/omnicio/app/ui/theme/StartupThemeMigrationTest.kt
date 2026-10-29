package ru.omnicio.app.ui.theme

import org.junit.Assert.*
import org.junit.Test

class StartupThemeMigrationTest {
    @Test fun firstLaunchAndLegacyPreferencesMigrateBeforeNativeThemeSelection() {
        listOf(null, "LIGHT", "SYSTEM", "unknown").forEach { previous ->
            val migration = startupThemeMigration(previous)
            assertEquals(ThemeMode.DARK, migration.mode)
            assertTrue(migration.persist)
        }
    }

    @Test fun savedDarkThemeDoesNotNeedAnotherPreferenceWrite() {
        assertEquals(StartupThemeMigration(ThemeMode.DARK, false), startupThemeMigration("DARK"))
    }
}
