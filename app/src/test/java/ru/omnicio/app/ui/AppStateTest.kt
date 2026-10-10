package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class AppStateTest {
    @Test
    fun installationIdLabelShortensLongLocalId() {
        assertEquals("12345678…", installationIdLabel("12345678-1234-5678"))
    }

    @Test
    fun installationIdLabelKeepsShortIdReadable() {
        assertEquals("local", installationIdLabel("local"))
    }
}
