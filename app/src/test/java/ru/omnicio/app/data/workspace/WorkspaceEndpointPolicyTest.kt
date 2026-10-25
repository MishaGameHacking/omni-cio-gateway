package ru.omnicio.app.data.workspace

import org.junit.Assert.*
import org.junit.Test

class WorkspaceEndpointPolicyTest {
    @Test fun controllerRoutesAreAcceptedWithoutOpeningArbitraryEndpoints() {
        listOf("/automation/status", "/automation/preferences", "/automation/decisions").forEach {
            assertTrue(it, WorkspaceEndpointPolicy.permits(it))
        }
        listOf("/automation/orders", "/admin", "/client/apk", "https://other.invalid/workspace",
            "//other.invalid/workspace", "/automation/status/extra").forEach {
            assertFalse(it, WorkspaceEndpointPolicy.permits(it))
        }
    }

    @Test fun workspaceQueriesStillWorkButDecodedTraversalAndFragmentsDoNot() {
        assertTrue(WorkspaceEndpointPolicy.permits("/workspace"))
        assertTrue(WorkspaceEndpointPolicy.permits("/workspace?currency=RUB"))
        assertTrue(WorkspaceEndpointPolicy.permits("/workspace/catalogue?q=Company.."))
        listOf("/workspace/../admin", "/workspace/%2e%2e/admin",
            "/workspace/a%2F..%2Fadmin", "/workspace#secret", "/workspace/%xx").forEach {
            assertFalse(it, WorkspaceEndpointPolicy.permits(it))
        }
    }
}
