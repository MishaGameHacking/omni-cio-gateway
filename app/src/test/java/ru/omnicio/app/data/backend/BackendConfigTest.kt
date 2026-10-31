package ru.omnicio.app.data.backend

import java.net.URI
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.omnicio.app.data.updates.UpdateProtocol

class BackendConfigTest {
    @Test
    fun verifiedOwnerInstallationUsesTheExactHttpsOrigin() {
        assertTrue(BackendConfig.isConfigured)
        assertEquals("https://laptop-npsga016.tail9f8db0.ts.net", BackendConfig.BASE_URL)
        val destination = URI(BackendConfig.BASE_URL + "/me")
        val connection = BackendConfig.openConnection(destination)
        assertEquals(destination, connection.url.toURI())
        assertFalse(connection.instanceFollowRedirects)
        connection.disconnect()
    }

    @Test
    fun retiredAndForeignAddressesCannotBecomeFallbacks() {
        val destinations = listOf(
            URI("https://analyst-ai-2941515.twc1.net/me"),
            URI("https://176.98.178.81.sslip.io/me"),
            URI("https://backend-not-configured.invalid/me"),
            URI("https://other.invalid/me"),
            URI("http://" + BackendConfig.HOST + "/me"),
            URI("https://user@" + BackendConfig.HOST + "/me"),
            URI("https://" + BackendConfig.HOST + ":443/me"),
            URI("https://" + BackendConfig.HOST + "/me#fragment"),
            URI("https://" + BackendConfig.HOST + ".other.invalid/me"),
        )
        for (destination in destinations) {
            assertThrows(IllegalArgumentException::class.java) { BackendConfig.openConnection(destination) }
        }
    }

    @Test
    fun updatePolicyUsesTheSameOriginAndRejectsTheRetiredChannel() {
        assertEquals(BackendConfig.HOST, UpdateProtocol.HOST)
        val path = UpdateProtocol.policyPath(UpdateProtocol.PREVIEW_PACKAGE)
        assertEquals(
            URI(BackendConfig.BASE_URL + path),
            UpdateProtocol.requestUri(BackendConfig.BASE_URL, path),
        )
        assertThrows(IllegalArgumentException::class.java) {
            UpdateProtocol.requestUri("https://176.98.178.81.sslip.io", path)
        }
        assertThrows(IllegalArgumentException::class.java) {
            UpdateProtocol.requestUri("https://analyst-ai-2941515.twc1.net", path)
        }
    }
}
