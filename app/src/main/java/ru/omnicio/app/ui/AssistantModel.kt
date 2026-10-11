package ru.omnicio.app.ui

import org.json.JSONObject
import java.util.UUID

/** Server chat state stays in process memory, including the draft and recovery ID. */
internal data class AssistantUiState(
    val available: Boolean = false,
    val loaded: Boolean = false,
    val conversations: List<ChatSummary> = emptyList(),
    val conversation: ChatConversation? = null,
    val pendingRequest: String? = null,
    val draft: String = "",
    val contextAccepted: Boolean = false,
) {
    val canSend: Boolean get() = available && loaded && contextAccepted &&
        conversation != null && pendingRequest == null &&
        conversation.requestStatus != "running" && draft.trim().length in 1..4000

    fun withoutServerData() = copy(available = false, loaded = false,
        conversations = emptyList(), conversation = null)
}

internal data class ChatSummary(val id: String, val title: String)
internal data class ChatConversation(
    val id: String, val title: String, val version: Int,
    val messages: List<ChatMessage>, val nextBefore: Int?, val requestStatus: String?,
)
internal data class ChatMessage(
    val position: Int, val role: String, val content: String, val at: String?,
    val sources: List<ChatSource>,
)
internal data class ChatSource(val title: String, val url: String?, val at: String?)

private fun JSONObject.chatId(key: String): String = UUID.fromString(getString(key)).toString()

internal fun parseConversation(root: JSONObject) = ChatConversation(
    root.chatId("id"), root.getString("title"), root.getInt("version"),
    root.getJSONArray("messages").objects().map { row ->
        val role = row.getString("role")
        if (role !in setOf("user", "assistant")) throw ApiFailure(200, "invalid_response")
        ChatMessage(row.getInt("position"), role, row.getString("content"), row.text("created_at"),
            row.optJSONArray("sources")?.objects()?.map { source ->
                ChatSource(source.text("label") ?: "Источник",
                    source.text("url"), source.text("observed_at"))
            }.orEmpty())
    },
    if (root.isNull("next_before")) null else root.getInt("next_before"),
    root.optJSONObject("latest_request")?.text("status"),
)

internal fun ServerApi.loadAssistant(previous: AssistantUiState, selectedId: String? = null): AssistantUiState {
    // GETs only. Reopening a tab never creates a conversation or invokes the model.
    val status = request("/api/assistant/status")
    val summaries = request("/api/assistant/conversations").getJSONArray("items").objects().map {
        ChatSummary(it.chatId("id"), it.getString("title"))
    }
    val pending = previous.pendingRequest?.let { id ->
        try { request("/api/assistant/requests/$id") }
        catch (error: ApiFailure) { if (error.status == 404) null else throw error }
    }
    val id = pending?.chatId("conversation_id") ?: selectedId ?: previous.conversation?.id
        ?: summaries.firstOrNull()?.id
    val conversation = id?.let { parseConversation(request("/api/assistant/conversations/$it")) }
    return previous.copy(loaded = true,
        available = status.getBoolean("enabled") && status.getBoolean("configured"),
        conversations = summaries, conversation = conversation,
        draft = if (pending != null) "" else previous.draft,
        pendingRequest = if (pending?.text("status") == "running") previous.pendingRequest else null)
}
