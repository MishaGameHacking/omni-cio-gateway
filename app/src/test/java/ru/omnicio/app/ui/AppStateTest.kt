package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class AppStateTest {
    @Test
    fun installationIdLabel_shortensLongLocalId() {
        assertEquals("12345678…", installationIdLabel("12345678-1234-5678"))
    }

    @Test
    fun installationIdLabel_keepsShortIdReadable() {
        assertEquals("local", installationIdLabel("local"))
    }
}
