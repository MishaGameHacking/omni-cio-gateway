package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.workspace.OfflinePortfolio
import ru.omnicio.app.data.workspace.OfflinePortfolioStore
import ru.omnicio.app.data.updates.ClientVersion
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.updates.UpdateGateUi
import org.json.JSONObject

/** A frozen reader is separate from the normal version-gated application. It has no network actions. */
@Composable
fun OfflineSnapshotAccess(gate: UpdateGateUi) {
    val context = LocalContext.current
    val blocked by ClientVersion.blocked.collectAsState()
    var cached by remember { mutableStateOf<OfflinePortfolio?>(null) }
    var open by remember { mutableStateOf(false) }
    val permitted = gate.decision == null && gate.error != null && !gate.checking && !blocked
    LaunchedEffect(permitted) {
        cached = if (permitted) withContext(Dispatchers.IO) {
            val session = AuthSessionStore(context)
            if (session.loadAccessToken() == null) null else session.loadCachedUser()?.telegramId?.let { OfflinePortfolioStore(context).read(it) }
        } else null
        if (!permitted) open = false
    }
    if (permitted && cached != null) SpectrumSecondaryButton("Посмотреть последний сохранённый снимок", { open = true }, Modifier.fillMaxWidth())
    if (open) cached?.let { snapshot -> WorkspaceDialog("Сохранённый снимок", { open = false }) {
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
