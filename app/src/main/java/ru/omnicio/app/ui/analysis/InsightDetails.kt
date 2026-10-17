package ru.omnicio.app.ui.analysis

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import java.time.Instant
import ru.omnicio.app.data.analysis.InsightCard
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.WorkspaceDetailPage

@Composable
internal fun InsightPreview(card: InsightCard, open: () -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = !card.isRead, onClick = open) {
        Text(card.title, style = MaterialTheme.typography.titleMedium)
        Text(card.summary, style = MaterialTheme.typography.bodyMedium, maxLines = 2,
            overflow = TextOverflow.Ellipsis, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(listOfNotNull(if (!card.isRead) "Новое" else null, analysisTime(card.createdAt)).joinToString(" · "),
            style = MaterialTheme.typography.bodySmall, color = LocalSpectrumPalette.current.cyan)
    }
}

@Composable
internal fun InsightDetails(card: InsightCard, now: Instant, readEnabled: Boolean, onRead: () -> Unit, close: () -> Unit) {
    Dialog(onDismissRequest = close, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        WorkspaceDetailPage("Событие", "Факты и необходимые действия", close) { padding ->
            Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
                .verticalScroll(rememberScrollState()).padding(20.dp)) {
                InsightCardView(card, now, readEnabled, onRead)
            }
        }
    }
}

@Composable
internal fun RiskCoverageCard() {
    var detail by remember { mutableStateOf(false) }
    SpectrumCard(onClick = { detail = true }) {
        Text("Полнота оценки", style = MaterialTheme.typography.titleMedium)
        Text("Комплексная оценка ещё не рассчитана", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("Посмотреть направления проверки ›", color = LocalSpectrumPalette.current.cyan,
            style = MaterialTheme.typography.bodyMedium)
    }
    if (detail) AlertDialog(onDismissRequest = { detail = false }, title = { Text("Что будет оцениваться") },
        text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            listOf("Кредитное качество", "Компании и отрасли", "Ликвидность", "Ставка и сроки", "Инфляция и валюта", "Доступность активов").forEach {
                Text("$it — оценка не получена")
            }
            Text("Стадия портфеля и прогресс появятся после расчёта стратегии. Отсутствие сигнала не означает защиту от риска.")
        } }, confirmButton = { TextButton(onClick = { detail = false }) { Text("Понятно") } })
}
