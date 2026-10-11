package ru.omnicio.app.ui

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import java.net.URLEncoder
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

internal data class AppUiState(
    val darkTheme: Boolean = false,
    val amountsHidden: Boolean = false,
    val authenticated: Boolean = false,
    val publicId: String? = null,
    val busy: Boolean = false,
    val error: String? = null,
    val notice: String? = null,
    val authConfig: JSONObject? = null,
    val legalConsent: JSONObject? = null,
    val workspace: ServerWorkspace? = null,
    val accounts: List<BrokerAccount> = emptyList(),
    val socialFlow: SocialFlow? = null,
    val identities: JSONObject? = null,
    val sessions: List<JSONObject> = emptyList(),
    val assistant: AssistantUiState = AssistantUiState(),
    val strategy: StrategyUiState = StrategyUiState(),
)

internal data class SocialFlow(
    val id: String, val provider: String, val authorizationUrl: String,
    val expiresAt: Long, val registrationRequired: Boolean = false, val launchPending: Boolean = true,
)

/** Financial data and credentials never enter SavedStateHandle or persistent storage. */
internal class OmnicioViewModel(application: Application) : AndroidViewModel(application) {
    private val preferences = application.getSharedPreferences("omnicio_appearance", Context.MODE_PRIVATE)
    private var api = ServerApi()
    private var generation = 0
    private val mutable = MutableStateFlow(AppUiState(
        darkTheme = preferences.getBoolean("dark_theme", false),
        amountsHidden = preferences.getBoolean("amounts_hidden", false),
    ))
    val uiState: StateFlow<AppUiState> = mutable.asStateFlow()

    init {
        // Remove all state from the retired fixture implementation, including fake connections.
        application.getSharedPreferences("omnicio_local_nonsecret_state", Context.MODE_PRIVATE)
            .edit().clear().apply()
        loadConfig()
    }

    fun setDarkTheme(value: Boolean) {
        preferences.edit().putBoolean("dark_theme", value).apply()
        mutable.value = mutable.value.copy(darkTheme = value)
    }

    fun toggleAmountsHidden() {
        val value = !mutable.value.amountsHidden
        preferences.edit().putBoolean("amounts_hidden", value).apply()
        mutable.value = mutable.value.copy(amountsHidden = value)
    }

    private fun <T> request(action: suspend (ServerApi) -> T, success: (T) -> Unit) {
        if (mutable.value.busy) return
        val current = api
        val expectedGeneration = generation
        mutable.value = mutable.value.copy(busy = true, error = null, notice = null)
        viewModelScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { action(current) }
                if (generation == expectedGeneration) success(result)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (generation == expectedGeneration) handleFailure(error)
            } finally {
                if (generation == expectedGeneration) mutable.value = mutable.value.copy(busy = false)
            }
        }
    }

    private fun handleFailure(error: Exception) {
        val expired = mutable.value.authenticated && error is ApiFailure &&
            (error.status == 401 || error.code == "profile_context_changed")
        val strategyRejected = error is ApiFailure &&
            (error.code.startsWith("strategy_") || error.code == "settings_version_conflict")
        if (expired) {
            api = ServerApi()
            mutable.value = mutable.value.copy(authenticated = false, publicId = null)
        }
        mutable.value = mutable.value.copy(error = apiError(error), workspace = null, accounts = emptyList(),
            strategy = if (!expired && strategyRejected) mutable.value.strategy.copy(assessment = null) else StrategyUiState(),
            assistant = if (expired) AssistantUiState() else mutable.value.assistant.withoutServerData(),
            legalConsent = if (expired) null else mutable.value.legalConsent,
            socialFlow = if (expired) null else mutable.value.socialFlow,
            identities = if (expired) null else mutable.value.identities,
            sessions = if (expired) emptyList() else mutable.value.sessions)
        if (error is ApiFailure && error.code in setOf(
                "updated_legal_consent_required", "legal_versions_changed")) {
            mutable.value = if (mutable.value.authenticated) mutable.value.copy(legalConsent = JSONObject())
                else mutable.value.copy(authConfig = null)
        }
    }

    fun loadConfig() = request({ client ->
        val config = client.request("/api/auth/config")
        if (config.optJSONObject("social_providers") == null || config.optJSONObject("legal_versions") == null) {
            throw ApiFailure(409, "server_update_required")
        }
        config
    }) {
        mutable.value = mutable.value.copy(authConfig = it)
    }

    fun startSocial(provider: String) = request({ client ->
        client.request("/api/auth/social/$provider/start", "POST", JSONObject()
            .put("purpose", if (mutable.value.authenticated) "link" else "login")
            .put("android_package", ru.omnicio.app.BuildConfig.APPLICATION_ID))
    }) { result ->
        val url = result.getString("authorization_url")
        val parsed = java.net.URI(url)
        val host = if (provider == "telegram") "oauth.telegram.org" else "id.vk.ru"
        if (parsed.scheme != "https" || parsed.host != host || parsed.userInfo != null ||
            parsed.port != -1 || parsed.fragment != null) throw ApiFailure(200, "invalid_response")
        mutable.value = mutable.value.copy(socialFlow = SocialFlow(result.getString("flow_id"), provider,
            url, android.os.SystemClock.elapsedRealtime() + result.getLong("expires_in_seconds") * 1000))
    }

    fun socialOpened() {
        mutable.value = mutable.value.copy(socialFlow = mutable.value.socialFlow?.copy(launchPending = false))
    }

    fun completeSocial(accepted: Boolean = false) {
        val flow = mutable.value.socialFlow ?: return
        if (android.os.SystemClock.elapsedRealtime() >= flow.expiresAt) {
            mutable.value = mutable.value.copy(error = "Время входа истекло. Начните вход заново.")
            return
        }
        if (flow.registrationRequired && !accepted) return
        val legal = mutable.value.authConfig?.optJSONObject("legal_versions") ?: return
        request({ client ->
            val body = JSONObject().put("flow_id", flow.id)
            if (accepted) body.put("consent", JSONObject().put("accept_privacy", true)
                .put("accept_personal_data", true).put("accept_terms", true)
                .put("confirm_age_18", true).put("legal_versions", legal))
            val result = client.request("/api/auth/social/complete", "POST", body)
            if (result.has("public_id")) client.acceptLogin(result)
            result
        }) { result ->
            when (result.optString("status")) {
                "pending" -> mutable.value = mutable.value.copy(notice = "Ожидаем подтверждение. Завершите вход у провайдера и вернитесь в приложение.")
                "registration_required" -> mutable.value = mutable.value.copy(socialFlow = flow.copy(registrationRequired = true))
                else -> mutable.value = mutable.value.copy(authenticated = true,
                    publicId = result.getString("public_id"), socialFlow = null,
                    workspace = null, identities = null, sessions = emptyList(), notice = "Вход подтверждён.")
            }
        }
    }

    fun cancelSocial() {
        val flow = mutable.value.socialFlow ?: return
        request({ it.request("/api/auth/social/cancel", "POST", JSONObject().put("flow_id", flow.id)) }) {
            mutable.value = mutable.value.copy(socialFlow = null)
        }
    }

    fun loadAccess() = request({ client ->
        client.request("/api/auth/identities") to client.request("/api/me/sessions")
    }) { (identities, sessions) ->
        mutable.value = mutable.value.copy(identities = identities,
            sessions = sessions.getJSONArray("sessions").objects())
    }

    fun revokeOtherSessions() = request({ client ->
        client.request("/api/me/sessions/revoke-others", "POST", JSONObject())
        client.request("/api/me/sessions")
    }) { mutable.value = mutable.value.copy(sessions = it.getJSONArray("sessions").objects(),
        notice = "Другие сессии завершены.") }

    fun refresh() {
        if (!mutable.value.authenticated || mutable.value.socialFlow != null) return
        request({ client ->
            val legal = client.request("/api/auth/legal")
            legal to if (legal.getBoolean("accepted")) client.workspace() else null
        }) { (legal, workspace) ->
            mutable.value = mutable.value.copy(workspace = workspace,
                legalConsent = if (legal.getBoolean("accepted")) null else legal.getJSONObject("legal_versions"))
        }
    }

    fun acceptLegal() {
        val versions = mutable.value.legalConsent?.takeIf { it.length() > 0 } ?: return
        request({ client ->
            val result = client.request("/api/auth/legal", "POST", JSONObject()
                .put("accept_privacy", true).put("accept_personal_data", true)
                .put("accept_terms", true).put("confirm_age_18", true).put("legal_versions", versions))
            if (!result.getBoolean("accepted")) throw ApiFailure(409, "updated_legal_consent_required")
            client.workspace()
        }) { mutable.value = mutable.value.copy(legalConsent = null, workspace = it) }
    }

    fun syncPortfolio() {
        val id = mutable.value.publicId ?: return
        request({ client ->
            client.request("/api/workspace/refresh", "POST", JSONObject().put("expected_public_id", id).put("scope", "quick"))
            var finished = false
            for (attempt in 0 until 10) {
                delay(2_000)
                val status = client.request("/api/workspace/refresh").getString("status")
                if (status !in setOf("queued", "running")) { finished = true; break }
            }
            client.workspace() to finished
        }) { (workspace, finished) ->
            mutable.value = mutable.value.copy(workspace = workspace,
                notice = if (finished) "Ответ сервера получен. Проверьте время и состояние данных."
                    else "Сервер продолжает обновление. Повторите проверку позже.")
        }
    }

    fun previewBroker(credential: String) = request({ it.request("/api/broker/tbank/accounts", "POST",
        JSONObject().put("credential", credential.trim()).put("environment", "prod").put("accept_personal_terms", true)) }) {
        mutable.value = mutable.value.copy(accounts = it.getJSONArray("accounts").objects().map { row ->
            BrokerAccount(row.getString("id"), row.getString("name"), row.getString("status"))
        })
    }

    fun clearAccounts() { mutable.value = mutable.value.copy(accounts = emptyList()) }

    fun connectBroker(credential: String, account: String) = request({ client ->
        client.request("/api/broker/tbank", "PUT", JSONObject().put("credential", credential.trim())
            .put("environment", "prod").put("account_id", account).put("accept_personal_terms", true))
        client.workspace()
    }) {
        mutable.value = mutable.value.copy(workspace = it, accounts = emptyList(), assistant = AssistantUiState(), strategy = StrategyUiState(),
            notice = "Счёт подключён. Сервер получает первый снимок; используйте «Обновить у брокера».")
    }

    fun disconnectBroker() = request({ client ->
        client.request("/api/broker/tbank", "DELETE")
        client.workspace()
    }) { mutable.value = mutable.value.copy(workspace = it, accounts = emptyList(), assistant = AssistantUiState(), strategy = StrategyUiState()) }

    fun markRead(id: String) = request({ client ->
        client.request("/api/events/read", "POST", JSONObject().put("ids", JSONArray().put(id)).put("read", true))
        client.workspace()
    }) { mutable.value = mutable.value.copy(workspace = it) }

    fun loadAssistant(id: String? = null) {
        val previous = mutable.value.assistant
        request({ it.loadAssistant(previous, id) }) {
            mutable.value = mutable.value.copy(assistant = it)
        }
    }

    fun newConversation() = request({ client ->
        val created = client.request("/api/assistant/conversations", "POST",
            JSONObject().put("title", "Мой портфель"))
        client.loadAssistant(mutable.value.assistant, created.getString("id"))
    }) { mutable.value = mutable.value.copy(assistant = it.copy(draft = "")) }

    fun setAssistantDraft(value: String) {
        if (value.length <= 4000) mutable.value = mutable.value.copy(
            assistant = mutable.value.assistant.copy(draft = value))
    }

    fun acceptAssistantContext(value: Boolean) {
        mutable.value = mutable.value.copy(assistant = mutable.value.assistant.copy(contextAccepted = value))
    }

    fun setAssistantTask(task: String) {
        val chat = mutable.value.assistant
        if (!mutable.value.busy && chat.pendingRequest == null && task in chat.availableTasks) {
            mutable.value = mutable.value.copy(assistant = chat.copy(task = task))
        }
    }

    fun sendAssistantMessage() {
        val chat = mutable.value.assistant
        if (mutable.value.busy || mutable.value.amountsHidden || !chat.canSend) return
        val conversation = chat.conversation ?: return
        submitQuestion(PendingQuestion(java.util.UUID.randomUUID().toString(),
            conversation.id, conversation.version, chat.draft.trim(), chat.task))
    }

    fun retryAssistantMessage() {
        val chat = mutable.value.assistant
        if (mutable.value.busy || mutable.value.amountsHidden || !chat.available ||
            !chat.contextAccepted || !chat.pendingMissing) return
        chat.pendingRequest?.let { submitQuestion(it) }
    }

    private fun submitQuestion(question: PendingQuestion) {
        val chat = mutable.value.assistant
        mutable.value = mutable.value.copy(assistant = chat.copy(pendingRequest = question, pendingMissing = false))
        request({ client ->
            client.request("/api/assistant/messages", "POST", JSONObject()
                .put("conversation_id", question.conversationId).put("request_id", question.id)
                .put("expected_version", question.version).put("message", question.message)
                .put("context", "investment").put("include_news", true).put("task", question.task))
            client.loadAssistant(chat.copy(draft = "", pendingRequest = question), question.conversationId)
        }) { mutable.value = mutable.value.copy(assistant = it) }
    }

    fun loadOlderMessages() {
        val chat = mutable.value.assistant
        val conversation = chat.conversation ?: return
        val before = conversation.nextBefore ?: return
        request({ client ->
            val older = parseConversation(client.request("/api/assistant/conversations/${conversation.id}?before=$before"))
            if (older.version != conversation.version) throw ApiFailure(409, "assistant_context_changed")
            older
        }) { older ->
            mutable.value = mutable.value.copy(assistant = chat.copy(conversation = older.copy(
                messages = (older.messages + conversation.messages).distinctBy { it.position }.sortedBy { it.position })))
        }
    }

    fun loadStrategy() {
        val id = mutable.value.publicId ?: return
        request({ it.loadStrategy(id) }) { mutable.value = mutable.value.copy(strategy = it) }
    }

    fun saveStrategy(document: JSONObject, intent: String) {
        val id = mutable.value.publicId ?: return
        val current = mutable.value.strategy
        if (!current.loaded) return
        request({ client ->
            client.request("/api/profile/strategy", "PUT", JSONObject()
                .put("expected_public_id", id).put("expected_version", current.version)
                .put("intent", intent).put("document", document))
            client.loadStrategy(id)
        }) { mutable.value = mutable.value.copy(strategy = it, notice = "Рабочая стратегия сохранена. Запустите проверку по счёту.") }
    }

    fun assessStrategy() {
        val id = mutable.value.publicId ?: return
        val current = mutable.value.strategy
        if (!current.loaded || current.version == 0) return
        request({ client ->
            client.request("/api/profile/strategy/account-assessment", "POST", JSONObject()
                .put("expected_public_id", id).put("expected_version", current.version)).also {
                if (it.getString("public_id") != id) throw ApiFailure(409, "profile_context_changed")
            }
        }) { mutable.value = mutable.value.copy(strategy = current.copy(assessment = it)) }
    }

    fun loadMoreEvents() {
        val workspace = mutable.value.workspace ?: return
        val cursor = workspace.nextEventCursor ?: return
        request({ it.request("/api/events?cursor=" + URLEncoder.encode(cursor, "UTF-8")) }) {
            mutable.value = mutable.value.copy(workspace = workspace.copy(
                events = (workspace.events + parseEvents(it)).distinctBy { event -> event.id },
                nextEventCursor = it.text("next_cursor")))
        }
    }

    fun createGoal(title: String, target: String, date: String, allocation: String) = request({ client ->
        val document = JSONObject().put("title", title.trim()).put("kind", "capital")
            .put("target_amount_rub", target.replace(',', '.')).put("target_date", date)
            .put("start_date", java.time.LocalDate.now().toString()).put("progress_source", "portfolio")
            .put("allocation_percent", allocation.replace(',', '.')).put("manual_amount_rub", JSONObject.NULL)
            .put("status", "active")
        client.request("/api/goals", "POST", JSONObject().put("document", document))
        client.workspace()
    }) { mutable.value = mutable.value.copy(workspace = it, notice = "Цель сохранена на сервере.") }

    fun logout() {
        val previous = api
        generation += 1
        api = ServerApi()
        mutable.value = AppUiState(darkTheme = mutable.value.darkTheme,
            amountsHidden = mutable.value.amountsHidden, authConfig = mutable.value.authConfig)
        viewModelScope.launch(Dispatchers.IO) {
            // Local access ends immediately even when server revocation is unavailable.
            try { previous.request("/api/auth/logout", "POST", JSONObject()) }
            catch (_: java.io.IOException) { /* The discarded session is no longer usable by this client. */ }
        }
    }
}
