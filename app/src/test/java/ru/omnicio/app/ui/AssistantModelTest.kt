package ru.omnicio.app.ui

import org.junit.Assert.*
import org.junit.Test

class AssistantModelTest {
    private val conversation = ChatConversation("id", "title", 0, emptyList(), null, null)
    private val pending = PendingQuestion("pending", "id", 0, "Вопрос")
    private val ready = AssistantUiState(available = true, loaded = true,
        conversation = conversation, draft = "Вопрос", contextAccepted = true)

    @Test fun sendingRequiresServerReadinessAndExplicitContextConsent() {
        assertTrue(ready.canSend)
        assertFalse(ready.copy(available = false).canSend)
        assertFalse(ready.copy(loaded = false).canSend)
        assertFalse(ready.copy(contextAccepted = false).canSend)
        assertFalse(ready.copy(conversation = null).canSend)
        assertFalse(ready.copy(draft = "  ").canSend)
        assertFalse(ready.copy(draft = "a".repeat(4001)).canSend)
    }

    @Test fun uncertainDeliveryAndRunningServerRequestPreventDuplicateSubmission() {
        assertFalse(ready.copy(pendingRequest = pending).canSend)
        assertFalse(ready.copy(conversation = conversation.copy(requestStatus = "running")).canSend)
    }

    @Test fun networkFailureClearsServerContentButPreservesRequestRecovery() {
        val failed = ready.copy(pendingRequest = pending,
            conversations = listOf(ChatSummary("id", "title"))).withoutServerData()
        assertNull(failed.conversation)
        assertTrue(failed.conversations.isEmpty())
        assertEquals(pending, failed.pendingRequest)
        assertFalse(failed.canSend)
        assertNull(AssistantUiState().pendingRequest)
        assertEquals("", AssistantUiState().draft)
    }
}
