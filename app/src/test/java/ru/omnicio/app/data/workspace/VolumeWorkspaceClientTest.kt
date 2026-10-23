package ru.omnicio.app.data.workspace

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class VolumeWorkspaceClientTest {
    // This foreign origin is rejected before any connection or credential use,
    // even after the production backend is configured.
    private val client = VolumeWorkspaceClient("https://transport-test.invalid")

    @Test
    fun catalogueSearchTreatsDotsAndUrlSyntaxAsQueryData() {
        for (query in listOf("..", "A..B", "../me", "Облигации..", "A?B#C&D=..", "%2e%2e")) {
            val reply = client.request("test-only", "/workspace/catalogue?query=${VolumeWorkspaceClient.encode(query)}")
            assertEquals("network_unavailable", reply.code)
            assertFalse(reply.ambiguous)
            assertTrue(reply.retryable)
        }
    }

    @Test
    fun rootWorkspaceQueriesAlsoPermitLiteralDots() {
        assertEquals("network_unavailable", client.request("test-only", "/workspace?query=..").code)
    }

    @Test
    fun traversalInThePathRemainsRejected() {
        for (path in listOf("/workspace/../me", "/workspace/catalogue/../../me", "/workspace/A..B?query=safe")) {
            assertThrows(IllegalArgumentException::class.java) { client.request("test-only", path) }
        }
    }

    @Test
    fun encodedTraversalInThePathIsRejected() {
        for (path in listOf("/workspace/%2e%2e/me", "/workspace/.%2E/me", "/workspace/%2E./me")) {
            assertThrows(IllegalArgumentException::class.java) { client.request("test-only", path) }
        }
    }

    @Test
    fun foreignPathsAndFragmentsRemainRejected() {
        for (path in listOf("/me", "/workspace-other", "https://other.invalid/workspace",
            "//other.invalid/workspace", "/workspace/catalogue#result", "/workspace?query=safe#fragment")) {
            assertThrows(IllegalArgumentException::class.java) { client.request("test-only", path) }
        }
    }

    @Test
    fun unsupportedMethodsRemainRejected() {
        assertThrows(IllegalArgumentException::class.java) { client.request("test-only", "/workspace", "CONNECT") }
    }
}
