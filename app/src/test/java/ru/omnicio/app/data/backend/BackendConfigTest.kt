package ru.omnicio.app.data.backend

import java.net.URI
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Test
import ru.omnicio.app.data.updates.UpdateProtocol

class BackendConfigTest {
    @Test
    fun pendingInstallationCannotCreateATransportForSavedCredentials() {
        assertFalse(BackendConfig.isConfigured)
        val destination = URI(BackendConfig.BASE_URL + "/me")
        val failure = assertThrows(IllegalStateException::class.java) {
            BackendConfig.openConnection(destination)
        }
        assertEquals(BackendConfig.UNAVAILABLE_MESSAGE, failure.message)
    }

    @Test
    fun retiredAndForeignAddressesCannotBecomeFallbacks() {
        val destinations = listOf(
            URI("https://176.98.178.81.sslip.io/me"),
            URI("https://other.invalid/me"),
            URI("http://" + BackendConfig.HOST + "/me"),
            URI("https://user@" + BackendConfig.HOST + "/me"),
        )
        for (destination in destinations) {
            assertThrows(IllegalStateException::class.java) { BackendConfig.openConnection(destination) }
        }
    }

    @Test
    fun updatePolicyUsesTheSameOriginAndRejectsTheRetiredChannel() {
        assertEquals(BackendConfig.HOST, UpdateProtocol.HOST)
        val retired = "https://176.98.178.81.sslip.io"
        val path = UpdateProtocol.policyPath(UpdateProtocol.PREVIEW_PACKAGE)
        assertThrows(IllegalArgumentException::class.java) { UpdateProtocol.requestUri(retired, path) }
    }
}
