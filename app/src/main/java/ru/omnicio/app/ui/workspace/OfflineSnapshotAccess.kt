package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.backend.SessionTransitions
import ru.omnicio.app.data.workspace.OfflinePortfolio
import ru.omnicio.app.data.workspace.OfflinePortfolioStore
import ru.omnicio.app.data.updates.ClientVersion
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.updates.UpdateGateUi
import org.json.JSONObject
import androidx.activity.compose.LocalActivity
import android.os.CancellationSignal
import ru.omnicio.app.ui.auth.showDevicePrompt
import ru.omnicio.app.ui.auth.rememberOwnerAccessLifecycle

/** A frozen reader is separate from the normal version-gated application. It has no network actions. */
@Composable
fun OfflineSnapshotAccess(gate: UpdateGateUi) {
    val context = LocalContext.current
    val activity = LocalActivity.current
    var unlocked by remember { mutableStateOf(false) }
    var unlocking by remember { mutableStateOf(false) }
    var unlockError by remember { mutableStateOf<String?>(null) }
    var cancellation by remember { mutableStateOf<CancellationSignal?>(null) }
    var cached by remember { mutableStateOf<OfflinePortfolio?>(null) }
    var open by remember { mutableStateOf(false) }
    val lifecycle = rememberOwnerAccessLifecycle {
        unlocked = false; open = false; cached = null
        cancellation?.cancel(); unlocking = false
    }
    val accessGate = lifecycle.gate
    DisposableEffect(accessGate) {
        onDispose { accessGate.background(); cancellation?.cancel() }
    }
    val blocked by ClientVersion.blocked.collectAsState()
    val permitted = gate.decision == null && gate.error != null && !gate.checking && !blocked && lifecycle.foreground
    LaunchedEffect(permitted, gate.decision, blocked, unlocked) {
        if (permitted && unlocked) {
            val ticket = accessGate.begin() ?: return@LaunchedEffect
            val stored = SessionTransitions.run {
                val session = AuthSessionStore(context)
                if (session.loadAccessToken() == null) null else session.loadCachedUser()?.telegramId?.let { OfflinePortfolioStore(context).read(it) }
            }
            if (accessGate.complete(ticket)) cached = stored
        } else cached = null
        if (!permitted || !unlocked) open = false
    }
    if (permitted && !unlocked) {
        SpectrumSecondaryButton("Разблокировать сохранённый снимок", {
            val owner = activity
            val ticket = accessGate.begin()
            if (ticket == null) unlockError = "Откройте приложение для доступа к снимку."
            else if (owner == null) unlockError = "Проверка блокировки устройства недоступна."
            else {
                unlocking = true
                val signal = CancellationSignal()
                cancellation = signal
                try {
                    showDevicePrompt(owner, signal,
                        { if (accessGate.complete(ticket)) { unlocking = false; unlocked = true } },
                        { error -> if (accessGate.complete(ticket)) { unlocking = false; unlockError = error } })
                } catch (_: RuntimeException) {
                    unlocking = false; unlockError = "Не удалось проверить блокировку устройства."
                }
            }
        }, Modifier.fillMaxWidth(), enabled = !unlocking)
        unlockError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    }
    if (permitted && unlocked && cached != null) SpectrumSecondaryButton("Посмотреть последний сохранённый снимок", { open = true }, Modifier.fillMaxWidth())
    if (open && permitted && unlocked) cached?.let { snapshot -> WorkspaceDialog("Сохранённый снимок", { open = false }) {
        Text("Нет подтверждённого соединения. Эти данные доступны только для чтения и могут отличаться от текущего портфеля.")
        Text("Получено: " + localMoment(java.time.Instant.ofEpochMilli(snapshot.receivedAtMillis).toString()))
        Text("Оценка: " + offlineMoney(snapshot.snapshot.totalValue), style = MaterialTheme.typography.headlineSmall)
        snapshot.snapshot.accounts.forEach { account ->
            DetailFold(account.name + " · " + offlineMoney(account.totalValue)) {
                account.positions.forEach { position ->
                    Text(position.title, style = MaterialTheme.typography.titleSmall)
                    Text(position.currentValue?.let { offlineMoney(it) } ?: "Оценка не получена")
                }
            }
        }
        SpectrumSecondaryButton("Вернуться к проверке соединения", { open = false }, Modifier.fillMaxWidth())
    } }
}

@Composable
private fun offlineMoney(value: ru.omnicio.app.data.portfolio.MoneyAmount): String =
    PrivateValue(moneyText(JSONObject().put("amount", value.value.toBigDecimal().toPlainString()).put("currency", value.currency)))

