package ru.omnicio.app.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.backend.*
import ru.omnicio.app.ui.spectrum.*

internal val LocalOwnerAccessPreviewStatus = staticCompositionLocalOf<OwnerAccessStatus?> { null }

/** Password fields and request copies are memory-only, never saved UI state. */
private class OwnerAccessForm(previewStatus: OwnerAccessStatus?) {
    var status by mutableStateOf(previewStatus)
    var statusBusy by mutableStateOf(false)
    var busy by mutableStateOf(false)
    var password by mutableStateOf("")
    var repeated by mutableStateOf("")
    var bootstrap by mutableStateOf("")
    var failure by mutableStateOf<String?>(null)
    var revision by mutableIntStateOf(0)
    val setup: Boolean get() = status?.configured == false
    val minimumLength: Int get() = status?.minimumPasswordLength ?: 10
    val blocked: Boolean get() = busy || statusBusy

    fun valid(migrationToken: String?): Boolean {
        if (!setup) return password.isNotEmpty()
        return password.length >= minimumLength &&
            password.toByteArray(Charsets.UTF_8).size <= (status?.maximumPasswordBytes ?: 128) &&
            password == repeated && (migrationToken != null || bootstrap.isNotBlank())
    }

    fun takeSubmission(migrationToken: String?, loginAccessToken: String?): OwnerAccessSubmission {
        val submission = OwnerAccessSubmission(setup, password, bootstrap, migrationToken, loginAccessToken)
        busy = true
        password = ""
        repeated = ""
        bootstrap = ""
        failure = null
        return submission
    }
}

private data class OwnerAccessSubmission(
    val setup: Boolean,
    val password: String,
    val bootstrap: String,
    val migrationToken: String?,
    val loginAccessToken: String?,
)

private suspend fun refreshOwnerAccessStatus(backend: AnalystBackendClient, form: OwnerAccessForm) {
    form.statusBusy = true
    try {
        when (val result = withContext(Dispatchers.IO) { backend.ownerAccessStatus() }) {
            is BackendResult.Success -> { form.status = result.value; form.failure = null }
            is BackendResult.Failure -> form.failure = result.message
        }
    } finally { form.statusBusy = false }
}

private suspend fun submitOwnerAccess(
    backend: AnalystBackendClient,
    form: OwnerAccessForm,
    submission: OwnerAccessSubmission,
    requestTicket: Long,
    onSessionReady: (AnalystSession, Long) -> Unit,
) {
    try {
        val result = withContext(Dispatchers.IO) {
            if (submission.setup) backend.setupOwnerPassword(submission.password, submission.migrationToken, submission.bootstrap)
            else backend.loginOwner(submission.password, submission.loginAccessToken)
        }
        when (result) {
            is BackendResult.Success -> onSessionReady(result.value, requestTicket)
            is BackendResult.Failure -> {
                form.failure = result.message
                if (result.statusCode == 409) form.revision++
            }
        }
    } finally { form.busy = false }
}

@Composable
fun OwnerAccessScreen(
    loading: Boolean = false,
    loadingLabel: String = "Проверяем доступ…",
    errorMessage: String? = null,
    migrationToken: String? = null,
    loginAccessToken: String? = null,
    onSessionReady: (AnalystSession, Long) -> Unit,
    onAccessStart: () -> Long?,
) {
    val inspection = LocalInspectionMode.current
    val previewStatus = if (inspection) LocalOwnerAccessPreviewStatus.current else null
    val backend = remember { AnalystBackendClient() }
    val scope = rememberCoroutineScope()
    val form = remember(previewStatus) { OwnerAccessForm(previewStatus) }
    LaunchedEffect(form.revision, loading) {
        if (!loading && !inspection) refreshOwnerAccessStatus(backend, form)
    }
    OwnerAccessFrame {
        SpectrumCard(Modifier.fillMaxWidth().testTag("owner-access"), emphasized = true) {
            Text(if (form.setup) "Создайте личный пароль" else "Открыть систему", style = MaterialTheme.typography.titleLarge)
            if (loading) {
                SpectrumLoadingIndicator(description = loadingLabel)
                Text(loadingLabel)
            } else {
                OwnerPasswordFields(form, migrationToken)
                OwnerAccessActions(form, errorMessage, migrationToken) {
                    val ticket = onAccessStart()
                    if (ticket != null) {
                        val submission = form.takeSubmission(migrationToken, loginAccessToken)
                        scope.launch { submitOwnerAccess(backend, form, submission, ticket, onSessionReady) }
                    }
                }
            }
        }
    }
}

@Composable
private fun OwnerAccessFrame(content: @Composable () -> Unit) {
    SpectrumBackground(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing)
            .imePadding().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.height(24.dp))
            SpectrumIcon(SpectrumSymbol.Brain, Modifier.size(64.dp), selected = true, motionAllowed = false)
            Text("Analyst AI", style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() })
            Text("Личный центр капитала", color = MaterialTheme.colorScheme.onSurfaceVariant)
            content()
            Text("Система продолжает работу на сервере, когда приложение закрыто.",
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun OwnerSecretField(value: String, change: (String) -> Unit, label: String,
    enabled: Boolean, modifier: Modifier = Modifier) {
    OutlinedTextField(value, change, modifier.fillMaxWidth(), enabled = enabled,
        label = { Text(label) }, singleLine = true, visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
}

@Composable
private fun OwnerPasswordFields(form: OwnerAccessForm, migrationToken: String?) {
    if (form.setup) Text(if (migrationToken != null)
        "Сохраняем ваш счёт и настройки. Пароль заменит вход через Telegram."
        else "Первый доступ открывает только владелец с ключом настройки сервера.",
        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    OwnerSecretField(form.password, { form.password = it; form.failure = null }, "Пароль Analyst AI",
        !form.blocked, Modifier.testTag("owner-password"))
    if (form.setup) {
        OwnerSecretField(form.repeated, { form.repeated = it }, "Повторите пароль", !form.blocked)
        Text("Не менее ${form.minimumLength} символов. Для быстрого входа можно использовать блокировку телефона.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (migrationToken == null) OwnerSecretField(form.bootstrap, { form.bootstrap = it },
            "Одноразовый ключ настройки", !form.blocked)
    }
}

@Composable
private fun OwnerAccessActions(form: OwnerAccessForm, errorMessage: String?, migrationToken: String?, submit: () -> Unit) {
    val message = form.failure ?: errorMessage
    if (message != null) Text(message, color = MaterialTheme.colorScheme.error)
    if (form.blocked) SpectrumLoadingIndicator(description = "Проверяем доступ")
    SpectrumPrimaryButton(if (form.setup) "Сохранить пароль и войти" else "Войти", submit,
        Modifier.fillMaxWidth().testTag("owner-login-submit"),
        enabled = form.valid(migrationToken) && !form.blocked && form.status != null)
    if (form.status == null && !form.blocked)
        SpectrumSecondaryButton("Повторить подключение", { form.revision++ }, Modifier.fillMaxWidth())
}
