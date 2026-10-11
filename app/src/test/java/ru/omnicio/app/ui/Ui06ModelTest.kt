package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Ui06ModelTest {
    @Test
    fun migrationRetriesUntilVersionMarkerPersists() {
        assertEquals(
            LocalMigrationStatus.FAILED,
            migrationStatusFor(storedVersion = 1, persistSucceeded = false),
        )
        assertEquals(
            LocalMigrationStatus.MIGRATED,
            migrationStatusFor(storedVersion = 1, persistSucceeded = true),
        )
        assertEquals(
            LocalMigrationStatus.CURRENT,
            migrationStatusFor(
                storedVersion = CURRENT_LOCAL_SCHEMA_VERSION,
                persistSucceeded = false,
            ),
        )
    }

    @Test
    fun layoutClassificationCoversCompactPhoneAndWide() {
        assertEquals(AppLayoutMode.COMPACT, appLayoutMode(320))
        assertEquals(AppLayoutMode.STANDARD, appLayoutMode(360))
        assertEquals(AppLayoutMode.STANDARD, appLayoutMode(839))
        assertEquals(AppLayoutMode.WIDE, appLayoutMode(840))
    }

    @Test
    fun largeFontScaleUsesCompactOrStackedLayoutsBeforeWideBreakpoint() {
        assertEquals(AppLayoutMode.COMPACT, effectiveLayoutMode(599, 1.3f))
        assertEquals(AppLayoutMode.STANDARD, effectiveLayoutMode(600, 1.3f))
        assertEquals(AppLayoutMode.WIDE, effectiveLayoutMode(840, 1.5f))

        assertTrue(shouldStackMetricCards(639, 1.0f))
        assertFalse(shouldStackMetricCards(640, 1.0f))
        assertTrue(shouldStackMetricCards(700, 1.3f))
        assertFalse(shouldStackMetricCards(840, 1.3f))

        assertFalse(shouldStackDetailLine(1.29f))
        assertTrue(shouldStackDetailLine(1.3f))
    }

    @Test
    fun notificationPermissionStartsAtAndroid13() {
        assertFalse(notificationPermissionRequired(32))
        assertTrue(notificationPermissionRequired(33))
        assertTrue(notificationPermissionRequired(36))
    }

    @Test
    fun saverLabelsExplainBackgroundDelay() {
        val delayed = "отложены"

        assertTrue(powerSaverLabel(true).contains(delayed))
        assertTrue(dataSaverLabel(true).contains(delayed))
        assertFalse(powerSaverLabel(false).contains(delayed))
    }
}
