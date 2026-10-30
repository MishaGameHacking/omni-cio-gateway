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

    @Test fun brokerAndSnapshotPrerequisitesTellTheOwnerWhatIsMissing() {
        for (code in listOf("ai_broker_connection_required", "tinvest_not_connected",
            "ai_broker_binding_unavailable", "ai_broker_connection_changed")) {
            val message = requireNotNull(VolumeWorkspaceClient.chatPolicyMessage(code))
            assertTrue(code, message.contains("T‑Invest"))
            assertFalse(code, message.contains("Telegram"))
        }
        val snapshot = requireNotNull(VolumeWorkspaceClient.chatPolicyMessage("workspace_refresh_required"))
        assertTrue(snapshot.contains("Данные портфеля"))
        assertTrue(snapshot.contains("дождитесь"))
    }

    @Test fun unsettledCostIsNotPresentedAsAKeyOrPasswordFailure() {
        for (code in listOf("ai_workspace_reconciliation_required", "ai_worker_reconciliation_required",
            "ai_budget_reconciliation_required", "ai_usage_requires_reconciliation")) {
            val message = requireNotNull(VolumeWorkspaceClient.chatPolicyMessage(code))
            assertTrue(code, message.contains("до сверки"))
            assertFalse(code, message.contains("Войдите"))
            assertFalse(code, message.contains("повторите отправку"))
        }
    }

    @Test fun dailyAndMonthlyLimitsStayDistinct() {
        val daily = requireNotNull(VolumeWorkspaceClient.chatPolicyMessage("ai_user_budget_exhausted"))
        val monthly = requireNotNull(VolumeWorkspaceClient.chatPolicyMessage("ai_user_monthly_budget_exhausted"))
        assertTrue(daily.contains("Дневной"))
        assertTrue(monthly.contains("Месячный"))
        assertNotEquals(daily, monthly)
    }

    @Test fun uncertainJobNeverPromisesANewAutomaticRequestOrARefund() {
        val message = VolumeWorkspaceClient.jobFailureMessage("workspace_paid_outcome_unknown")
        assertTrue(message.contains("не подтверждены"))
        assertTrue(message.contains("автоматического повторного платного запроса нет"))
        assertFalse(message.contains("возвращ"))
        assertFalse(message.contains("не отправлен"))
    }

    @Test fun providerAuthenticationIsNotConfusedWithOwnerLogin() {
        val message = VolumeWorkspaceClient.jobFailureMessage("ai_http_401")
        assertTrue(message.contains("серверный ключ ИИ"))
        assertFalse(message.contains("Войдите"))
        assertFalse(message.contains("Telegram"))
    }

    @Test fun invalidPaidResponseIsNotDisplayedAsSuccess() {
        for (code in listOf("ai_chat_claims_invalid", "ai_chat_evidence_not_in_context",
            "ai_chat_highlight_not_in_context", "ai_chat_action_not_allowed", "ai_content_not_json")) {
            val message = VolumeWorkspaceClient.jobFailureMessage(code)
            assertTrue(code, message.contains("не опубликован"))
            assertTrue(code, message.contains("повторного запроса нет"))
            assertFalse(code, message.contains("не отправлен"))
        }
    }

    @Test fun unknownFailureCannotEchoAnUpstreamBodyOrSecret() {
        val upstream = "unknown: Bearer secret-value; private question"
        val message = VolumeWorkspaceClient.jobFailureMessage(upstream)
        assertEquals(message, VolumeWorkspaceClient.jobFailureMessage(null))
        assertFalse(message.contains("secret-value"))
        assertFalse(message.contains("private question"))
    }

}
