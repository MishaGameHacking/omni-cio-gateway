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
    fun notificationPermissionStartsAtAndroid13() {
        assertFalse(notificationPermissionRequired(32))
        assertTrue(notificationPermissionRequired(33))
        assertTrue(notificationPermissionRequired(36))
    }

    @Test
    fun saverLabelsExplainBackgroundDelay() {
        assertTrue(powerSaverLabel(true).contains("отложены"))
        assertTrue(dataSaverLabel(true).contains("отложены"))
        assertFalse(powerSaverLabel(false).contains("отложены"))
    }
}
