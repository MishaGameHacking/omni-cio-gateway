package ru.omnicio.app.data.backend

import org.junit.Assert.*
import org.junit.Test

class OwnerSessionRestorationTest {
    private val user = AnalystUser("owner", "Owner", null, null)
    private fun status(configured: Boolean) = BackendResult.Success(OwnerAccessStatus(configured, 10, 128))

    @Test fun passwordFallbackKeepsValidatedLegacySessionForEnrollment() {
        var cleared = false
        val result = restoreOwnerSessionAccess("legacy", true, { BackendResult.Success(user) },
            { status(false) }, { cleared = true })
        assertEquals(OwnerSessionAccess.Migration("legacy"), result)
        assertFalse(cleared)
    }

    @Test fun passwordFallbackDoesNotRestoreWorkspaceWhenPasswordAlreadyExists() {
        val result = restoreOwnerSessionAccess("current", true, { BackendResult.Success(user) },
            { status(true) }, { fail("Valid session must be preserved") })
        assertEquals(OwnerSessionAccess.Password(validatedAccessToken = "current"), result)
    }

    @Test fun retryableValidationFailureCannotAuthorizeMigrationOrCachedWorkspace() {
        val result = restoreOwnerSessionAccess("saved", false,
            { BackendResult.Failure("offline", true) },
            { fail("Owner status must follow successful identity validation"); status(false) },
            { fail("Transient failure must preserve saved credential") })
        assertEquals(OwnerSessionAccess.Password("offline"), result)
    }

    @Test fun rejectedCredentialIsClearedBeforeAnyEnrollmentOffer() {
        var cleared = false
        val result = restoreOwnerSessionAccess("expired", true,
            { BackendResult.Failure("expired", false, 401) },
            { fail("Invalid identity cannot enroll"); status(false) }, { cleared = true })
        assertTrue(cleared)
        assertEquals(OwnerSessionAccess.Password("expired"), result)
    }

    @Test fun unknownOwnerConfigurationCannotAuthorizeWorkspace() {
        val result = restoreOwnerSessionAccess("saved", false, { BackendResult.Success(user) },
            { BackendResult.Failure("unavailable", true) }, { fail("Valid session must be preserved") })
        assertEquals(OwnerSessionAccess.Password("unavailable"), result)
    }

    @Test fun deviceUnlockRestoresOnlyValidatedConfiguredOwner() {
        val result = restoreOwnerSessionAccess("saved", false, { BackendResult.Success(user) },
            { status(true) }, { fail("Valid session must be preserved") })
        assertEquals(OwnerSessionAccess.Restored("saved", user), result)
    }
}
