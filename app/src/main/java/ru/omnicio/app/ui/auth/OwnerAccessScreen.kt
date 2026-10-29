package ru.omnicio.app.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalInspectionMode
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

/** Secrets live only in memory while this screen is mounted, never in saved UI state. */
@Composable
fun OwnerAccessScreen(
    loading: Boolean = false,
    loadingLabel: String = "Проверяем доступ…",
    errorMessage: String? = null,
    migrationToken: String? = null,
    onSessionReady: (AnalystSession, Long) -> Unit,
    onAccessStart: () -> Long?,
) {
    val inspection = LocalInspectionMode.current
    val previewStatus = if (inspection) LocalOwnerAccessPreviewStatus.current else null
    val backend = remember { AnalystBackendClient() }
    val scope = rememberCoroutineScope()
    var status by remember(previewStatus) { mutableStateOf(previewStatus) }
    var statusBusy by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var password by remember { mutableStateOf("") }
    var repeated by remember { mutableStateOf("") }
    var bootstrap by remember { mutableStateOf("") }
    var failure by remember { mutableStateOf<String?>(null) }
    var revision by remember { mutableIntStateOf(0) }
    LaunchedEffect(revision, loading) {
        if (loading || inspection) return@LaunchedEffect
        statusBusy = true
        when (val result = withContext(Dispatchers.IO) { backend.ownerAccessStatus() }) {
            is BackendResult.Success -> { status = result.value; failure = null }
            is BackendResult.Failure -> failure = result.message
        }
        statusBusy = false
    }
    val setup = status?.configured == false
    val valid = if (setup) password.length >= (status?.minimumPasswordLength ?: 10) &&
        password.toByteArray(Charsets.UTF_8).size <= (status?.maximumPasswordBytes ?: 128) &&
        password == repeated && (migrationToken != null || bootstrap.isNotBlank()) else password.isNotEmpty()
    val blocked = loading || busy || statusBusy
    SpectrumBackground(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing)
            .imePadding().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.height(24.dp))
            SpectrumIcon(SpectrumSymbol.Brain, Modifier.size(64.dp), selected = true, motionAllowed = false)
            Text("Analyst AI", style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() })
            Text("Личный центр капитала", color = MaterialTheme.colorScheme.onSurfaceVariant)
            SpectrumCard(Modifier.fillMaxWidth().testTag("owner-access"), emphasized = true) {
                Text(if (setup) "Создайте личный пароль" else "Открыть систему",
                    style = MaterialTheme.typography.titleLarge)
                if (loading) {
                    SpectrumLoadingIndicator(description = loadingLabel)
                    Text(loadingLabel)
                } else {
                    if (setup) Text(if (migrationToken != null)
                        "Сохраняем ваш счёт и настройки. Пароль заменит вход через Telegram."
                        else "Первый доступ открывает только владелец с ключом настройки сервера.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    OutlinedTextField(password, { password = it; failure = null },
                        Modifier.fillMaxWidth().testTag("owner-password"), enabled = !blocked,
                        label = { Text("Пароль Analyst AI") }, singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
                    if (setup) {
                        OutlinedTextField(repeated, { repeated = it }, Modifier.fillMaxWidth(),
                            enabled = !blocked, label = { Text("Повторите пароль") }, singleLine = true,
                            visualTransformation = PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
                        Text("Не менее ${status?.minimumPasswordLength ?: 10} символов. Для быстрого входа можно использовать блокировку телефона.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (migrationToken == null) OutlinedTextField(bootstrap, { bootstrap = it },
                            Modifier.fillMaxWidth(), enabled = !blocked,
                            label = { Text("Одноразовый ключ настройки") }, singleLine = true,
                            visualTransformation = PasswordVisualTransformation(),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
                    }
                    val message = failure ?: errorMessage
                    if (message != null) Text(message, color = MaterialTheme.colorScheme.error)
                    if (blocked) SpectrumLoadingIndicator(description = "Проверяем доступ")
                    SpectrumPrimaryButton(if (setup) "Сохранить пароль и войти" else "Войти", {
                        val requestTicket = onAccessStart()
                        if (requestTicket != null) {
                        busy = true
                        val submittedPassword = password
                        val submittedBootstrap = bootstrap
                        password = ""; repeated = ""; bootstrap = ""; failure = null
                        scope.launch {
                            try {
                                val result = withContext(Dispatchers.IO) {
                                    if (setup) backend.setupOwnerPassword(submittedPassword, migrationToken, submittedBootstrap)
                                    else backend.loginOwner(submittedPassword)
                                }
                                when (result) {
                                    is BackendResult.Success -> onSessionReady(result.value, requestTicket)
                                    is BackendResult.Failure -> {
                                        failure = result.message
                                        if (result.statusCode == 409) revision++
                                    }
                                }
                            } finally { busy = false }
                        }
                        }
                    }, Modifier.fillMaxWidth().testTag("owner-login-submit"), enabled = valid && !blocked && status != null)
                    if (status == null && !blocked) SpectrumSecondaryButton("Повторить подключение", { revision++ }, Modifier.fillMaxWidth())
                }
            }
            Text("Система продолжает работу на сервере, когда приложение закрыто.",
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
    }
}
