package ru.omnicio.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.delay
import ru.omnicio.app.R

internal fun providerLabel(provider: String): String = when (provider) {
    "telegram" -> "Telegram"
    "vkid" -> "VK ID"
    "email" -> "Почта"
    else -> "Другой способ"
}

@Composable
internal fun SocialButtons(state: AppUiState, model: OmnicioViewModel, linking: Boolean = false) {
    val linked = state.identities?.optJSONArray("providers")
    listOf("telegram" to R.drawable.ic_telegram, "vkid" to R.drawable.ic_vk).forEach { (provider, icon) ->
        val present = linked != null && (0 until linked.length()).any { linked.optString(it) == provider }
        val available = state.authConfig?.optJSONObject("social_providers")?.optBoolean(provider) == true
        OutlinedButton(onClick = { model.startSocial(provider) },
            enabled = !state.busy && available && !present && (!linking || state.identities != null),
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            OmniIcon(icon)
            Spacer(Modifier.width(10.dp))
            Text(when {
                present -> "${providerLabel(provider)} подключён"
                !available -> "${providerLabel(provider)} — пока недоступен"
                linking -> "Подключить ${providerLabel(provider)}"
                else -> "Войти через ${providerLabel(provider)}"
            })
        }
    }
}

@Composable
internal fun SocialFlowScreen(state: AppUiState, model: OmnicioViewModel) {
    val flow = state.socialFlow ?: return
    val uri = LocalUriHandler.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val form = remember(flow.id, state.authConfig?.optJSONObject("legal_versions")?.toString()) { ConsentFormState() }
    var browserError by remember(flow.id) { mutableStateOf(false) }
    fun openBrowser() {
        try { uri.openUri(flow.authorizationUrl); browserError = false }
        catch (_: IllegalArgumentException) { browserError = true }
        catch (_: android.content.ActivityNotFoundException) { browserError = true }
    }
    LaunchedEffect(flow.id) {
        if (flow.launchPending) { model.socialOpened(); openBrowser() }
    }
    LaunchedEffect(flow.id, lifecycle) {
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            repeat(3) { delay(1500); model.completeSocial() }
        }
    }
    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.safeDrawingPadding().imePadding().fillMaxSize()
            .verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(if (flow.registrationRequired) "Создать аккаунт OMNICIO" else
                "Вход через ${providerLabel(flow.provider)}")
            StatusMessages(state)
            if (flow.registrationRequired) {
                Text("Этот способ входа ещё не связан с аккаунтом OMNICIO. Если аккаунт уже есть, вернитесь ко входу и подключите новый способ в его настройках.")
                RegistrationConsent(form)
                Button(onClick = { model.completeSocial(accepted = true) },
                    enabled = !state.busy && form.adult && form.terms && form.privacy && form.consent) {
                    Text("Создать аккаунт и войти")
                }
            } else {
                Text("Подтвердите вход в официальном интерфейсе ${providerLabel(flow.provider)}, затем вернитесь в OMNICIO.")
                if (browserError) Text("Не удалось открыть браузер. Проверьте, что браузер установлен.")
                Button(onClick = { model.completeSocial() }, enabled = !state.busy) { Text("Я подтвердил — продолжить") }
                TextButton(onClick = { openBrowser() }, enabled = !state.busy) { Text("Открыть страницу подтверждения") }
            }
            TextButton(onClick = model::cancelSocial, enabled = !state.busy) { Text("Отменить") }
            TextButton(onClick = model::logout) { Text("Выйти и очистить текущий вход") }
        }
    }
}

@Composable
internal fun AccessSettings(state: AppUiState, model: OmnicioViewModel) {
    LaunchedEffect(state.publicId, state.identities == null) {
        if (state.identities == null) model.loadAccess()
    }
    OmniCard {
        OmniIcon(R.drawable.ic_shield)
        SectionTitle("Способы входа")
        Text("Подключайте дополнительные способы здесь — они будут открывать тот же профиль и портфель.")
        if (state.identities == null) {
            Text("Способы входа ещё не загружены.")
            OutlinedButton(onClick = model::loadAccess, enabled = !state.busy) { Text("Обновить способы входа") }
        }
        SocialButtons(state, model, linking = true)
        if (state.sessions.isNotEmpty()) {
            HorizontalDivider()
            SectionTitle("Активные сессии")
            state.sessions.forEach { session ->
                Text("${providerLabel(session.optString("auth_provider"))} · " +
                    if (session.optBoolean("current")) "Это приложение" else "Другая сессия")
                Text(timestampLabel(session.text("last_seen_at")), style = MaterialTheme.typography.bodySmall)
            }
            OutlinedButton(onClick = model::revokeOtherSessions,
                enabled = !state.busy && state.sessions.any { !it.optBoolean("current") }) {
                Text("Завершить другие сессии")
            }
        }
    }
}
