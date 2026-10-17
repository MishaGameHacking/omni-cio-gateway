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
import ru.omnicio.app.ui.workspace.*

@Composable
internal fun InsightPreview(card: InsightCard, now: Instant = Instant.now(), open: () -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = !card.isRead, onClick = open) {
        SpectrumBadge(when (card.severity) { "critical" -> "Критично"; "warning" -> "Требует внимания"; "watch" -> "Наблюдение"; else -> "Информация" })
        Text(insightValidity(card.createdAt, card.validUntil, now), style = MaterialTheme.typography.bodySmall)
        Text(card.title, style = MaterialTheme.typography.titleMedium)
        Text(PrivateValue(card.summary), style = MaterialTheme.typography.bodyMedium, maxLines = 2,
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

internal fun insightActive(card: InsightCard, now: Instant): Boolean =
    runCatching { Instant.parse(card.validUntil).isAfter(now) }.getOrDefault(true)

@Composable
internal fun RiskCoverageCard() {
    SpectrumCard {
        Text("Полнота оценки", style = MaterialTheme.typography.titleMedium)
        Text("Подтверждены только факты в полученных сигналах. Комплексная оценка не рассчитана.")
        listOf("Кредитное качество", "Компании и отрасли", "Ликвидность", "Ставка и сроки", "Инфляция и валюта", "Доступность активов").forEach { category ->
            DetailFold(category) { Text("Оценка не получена. Показатель и объяснение появятся после расчёта этого направления.") }
        }
    }
}
