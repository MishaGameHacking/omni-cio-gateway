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
    val challengeId: String? = null,
    val challengePurpose: String? = null,
    val workspace: ServerWorkspace? = null,
    val accounts: List<BrokerAccount> = emptyList(),
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
        if (expired) {
            api = ServerApi()
            mutable.value = mutable.value.copy(authenticated = false, publicId = null)
        }
        mutable.value = mutable.value.copy(error = apiError(error), workspace = null, accounts = emptyList())
    }

    fun loadConfig() = request({ client ->
        val config = client.request("/api/auth/config")
        if (config.text("auth_provider") != "email" || config.optJSONObject("legal_versions") == null) {
            throw ApiFailure(409, "server_update_required")
        }
        config
    }) {
        mutable.value = mutable.value.copy(authConfig = it)
    }

    fun login(email: String, password: String) = request({ client ->
        val result = client.request("/api/auth/email/login", "POST",
            JSONObject().put("email", email.trim()).put("password", password))
        client.acceptLogin(result)
        client.profile
    }) { id ->
        mutable.value = mutable.value.copy(authenticated = true, publicId = id, challengeId = null)
        // The next composition requests the workspace after busy is cleared.
    }

    fun register(email: String, password: String) {
        val legal = mutable.value.authConfig?.optJSONObject("legal_versions") ?: return
        request({ it.request("/api/auth/email/register", "POST", JSONObject()
            .put("email", email.trim()).put("password", password)
            .put("accept_privacy", true).put("accept_personal_data", true)
            .put("accept_terms", true).put("confirm_age_18", true).put("legal_versions", legal)) }) {
            mutable.value = mutable.value.copy(challengeId = it.getString("challenge_id"), challengePurpose = "register")
        }
    }

    fun resetPassword(email: String) = request({ it.request("/api/auth/email/password-reset/request", "POST",
        JSONObject().put("email", email.trim())) }) {
        mutable.value = mutable.value.copy(challengeId = it.getString("challenge_id"), challengePurpose = "reset")
    }

    fun verify(code: String, newPassword: String) {
        val id = mutable.value.challengeId ?: return
        val reset = mutable.value.challengePurpose == "reset"
        request({ client ->
            val body = JSONObject().put("challenge_id", id).put("code", code)
            if (reset) body.put("password", newPassword)
            val result = client.request(if (reset) "/api/auth/email/password-reset/confirm"
                else "/api/auth/email/verify", "POST", body)
            if (!reset) client.acceptLogin(result)
            client.profile
        }) { profile ->
            mutable.value = mutable.value.copy(challengeId = null, challengePurpose = null,
                authenticated = !reset, publicId = profile,
                notice = if (reset) "Пароль изменён. Войдите с новым паролем." else null)
        }
    }

    fun resendCode() {
        val id = mutable.value.challengeId ?: return
        request({ it.request("/api/auth/email/resend", "POST", JSONObject().put("challenge_id", id)) }) {
            mutable.value = mutable.value.copy(challengeId = it.getString("challenge_id"), notice = "Новый код отправлен.")
        }
    }

    fun cancelChallenge() {
        if (!mutable.value.busy) mutable.value = mutable.value.copy(challengeId = null, challengePurpose = null)
    }

    fun refresh() {
        if (!mutable.value.authenticated) return
        request({ it.workspace() }) { mutable.value = mutable.value.copy(workspace = it) }
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
        mutable.value = mutable.value.copy(workspace = it, accounts = emptyList(),
            notice = "Счёт подключён. Сервер получает первый снимок; используйте «Обновить у брокера».")
    }

    fun disconnectBroker() = request({ client ->
        client.request("/api/broker/tbank", "DELETE")
        client.workspace()
    }) { mutable.value = mutable.value.copy(workspace = it, accounts = emptyList()) }

    fun markRead(id: String) = request({ client ->
        client.request("/api/events/read", "POST", JSONObject().put("ids", JSONArray().put(id)).put("read", true))
        client.workspace()
    }) { mutable.value = mutable.value.copy(workspace = it) }

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
        if (mutable.value.busy) return
        request({ it.request("/api/auth/logout", "POST", JSONObject()) }) {
            generation += 1
            api = ServerApi()
            mutable.value = AppUiState(darkTheme = mutable.value.darkTheme,
                amountsHidden = mutable.value.amountsHidden, authConfig = mutable.value.authConfig)
        }
    }
}
