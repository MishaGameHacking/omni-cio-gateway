package ru.omnicio.app.data.workspace

import org.junit.Assert.*
import org.junit.Test

class AiAvailabilityMessageTest {
    @Test fun missingServerSetupDoesNotAskTheUserToLogInAgain() {
        for (code in listOf("timeweb_ai_key_missing", "ai_model_identifier_missing_or_invalid",
            "ai_prices_missing_stale_or_invalid", "ai_no_approved_route_for_task")) {
            val message = VolumeWorkspaceClient.chatPolicyMessage(code)
            assertNotNull(code, message)
            assertFalse(message!!.contains("Telegram"))
            assertTrue(message.contains("не отправлен"))
        }
    }
    @Test fun unknownServerErrorIsNotPresentedAsAnApprovedAiRoute() {
        assertNull(VolumeWorkspaceClient.chatPolicyMessage("unknown_upstream_error"))
        assertNull(VolumeWorkspaceClient.chatPolicyMessage(null))
    }
}
