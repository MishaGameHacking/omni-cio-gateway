package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import ru.omnicio.app.ui.spectrum.*

/** Future backend presentation contracts. Null means unknown, never zero or success. */
data class StrategyImpactUi(val changes: List<ImpactRow>, val asOf: String, val source: String, val limitation: String)
data class ImpactRow(val label: String, val before: String, val after: String)

@Composable
fun StrategyImpact(value: StrategyImpactUi?) {
    if (value == null) {
        WorkspaceEmpty("Влияние на портфель", "Сравнение до и после появится после подключения расчёта. Черновик не меняет текущий анализ.")
        return
    }
    SpectrumCard {
        Text("Влияние изменений", style = MaterialTheme.typography.titleMedium)
        value.changes.forEach { row ->
            Text(row.label)
            Text("${PrivateValue(row.before)} → ${PrivateValue(row.after)}")
        }
        Text("${value.source} · ${value.asOf}", style = MaterialTheme.typography.bodySmall)
        Text(value.limitation, style = MaterialTheme.typography.bodySmall)
    }
}

data class NotificationGroupUi(val eventId: String, val title: String, val latestAt: String, val updates: List<String>)

/** Group only by a verified event identity; similar-looking unrelated events stay separate. */
@Composable
fun NotificationGroup(value: NotificationGroupUi) {
    SpectrumCard {
        Text(value.title, style = MaterialTheme.typography.titleMedium)
        Text("Последнее изменение: ${value.latestAt}", style = MaterialTheme.typography.bodySmall)
        DetailFold("Обновления события (${value.updates.size})") {
            value.updates.forEach { Text(PrivateValue(it)) }
        }
    }
}

@Composable
fun ContextQuestion(instrument: String, chatAvailable: Boolean = false, open: (String) -> Unit = {}) {
    if (chatAvailable) SpectrumSecondaryButton("Объяснить эту позицию", { open(instrument) }, Modifier.fillMaxWidth())
    else Text("Объяснение позиции в диалоге появится после подключения чата.", style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant)
}
