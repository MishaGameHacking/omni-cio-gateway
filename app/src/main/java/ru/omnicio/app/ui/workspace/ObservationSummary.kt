package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.analysis.AnalysisBackendClient
import ru.omnicio.app.data.analysis.AnalysisStatus
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumSymbol

data class WorkspaceSession(val token: String = "", val userId: String = "")
val LocalWorkspaceSession = staticCompositionLocalOf { WorkspaceSession() }

@Composable
fun ObservationSummary(onDetails: () -> Unit) {
    val session = LocalWorkspaceSession.current
    var status by remember(session.token) { mutableStateOf<AnalysisStatus?>(null) }
    var failed by remember(session.token) { mutableStateOf(false) }
    LaunchedEffect(session.token) {
        if (session.token.isNotBlank()) {
            when (val result = withContext(Dispatchers.IO) { AnalysisBackendClient().fetchStatus(session.token) }) {
                is BackendResult.Success -> status = result.value
                is BackendResult.Failure -> failed = true
            }
        }
    }
    SpectrumCard(onClick = onDetails) {
        Text("Наблюдение", style = MaterialTheme.typography.titleMedium)
        val label = when (status?.monitoring?.state) {
            "current" -> "Данные поступают"
            "waiting" -> "Ожидаем первую проверку"
            "delayed", "check_failed" -> "Проверка задерживается"
            "not_connected" -> "Нужно подключить счёт"
            "disabled" -> "Наблюдение отключено"
            else -> if (failed) "Не удалось проверить состояние" else "Состояние ещё не получено"
        }
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        status?.monitoring?.lastSnapshotAt?.let { Text("Портфель: ${relativeObservation(it)}", style = MaterialTheme.typography.bodySmall) }
        Text("Анализ: ${status?.lastRun?.createdAt?.let { relativeObservation(it) } ?: "время не получено"}", style = MaterialTheme.typography.bodySmall)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Подробности", color = MaterialTheme.colorScheme.primary)
            SpectrumIcon(SpectrumSymbol.Forward, Modifier.size(20.dp))
        }
    }
}

@Composable
fun AttentionBadge() {
    val token = LocalWorkspaceSession.current.token
    var count by remember(token) { mutableStateOf<Int?>(null) }
    LaunchedEffect(token) {
        if (token.isNotBlank()) {
            val response = withContext(Dispatchers.IO) { AnalysisBackendClient().fetchFeed(token) }
            if (response is BackendResult.Success) {
                val now = java.time.Instant.now()
                count = response.value.cards.count { !it.isRead && it.severity in setOf("critical", "warning") &&
                    ru.omnicio.app.ui.analysis.insightActive(it, now) }
            }
        }
    }
    if ((count ?: 0) > 0) SpectrumBadge(count.toString())
}
