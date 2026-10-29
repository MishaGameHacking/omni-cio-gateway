package ru.omnicio.app.ui.home

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*
import java.math.BigDecimal
import java.time.Instant

internal data class ObservedProgress(val completed: Long, val total: Long?) {
    val fraction: Float? get() = total?.takeIf { it > 0 && completed <= it }
        ?.let { (completed.toDouble() / it).toFloat() }
}

internal fun observedProgress(completed: String?, total: String?): ObservedProgress? {
    val done = completed?.toLongOrNull()?.takeIf { it >= 0 } ?: return null
    val count = total?.takeUnless { it == "null" }?.toLongOrNull()
    if (total != null && total != "null" && count == null || count != null && (count < 0 || done > count)) return null
    return ObservedProgress(done, count)
}

internal fun observedBudgetFraction(spent: String?, cap: String?): Float? {
    val amount = spent?.toBigDecimalOrNull()?.takeIf { it >= BigDecimal.ZERO } ?: return null
    val limit = cap?.toBigDecimalOrNull()?.takeIf { it > BigDecimal.ZERO } ?: return null
    return amount.divide(limit, 6, java.math.RoundingMode.HALF_UP).toFloat().coerceIn(0f, 1f)
}

/** Only persisted counters and timestamps enter these visuals. Reading does not schedule work. */
@Composable
internal fun SystemTelemetryCard(ai: JSONObject?, now: Instant, openDetails: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    val jobs = ai?.records("jobs").orEmpty()
    val job = jobs.firstOrNull { it.text("state") in setOf("running", "queued", "cancel_requested") }
        ?: jobs.firstOrNull()
    val updated = job?.text("updated_at", "")?.let { runCatching { Instant.parse(it) }.getOrNull() }
    val stale = updated == null || updated.isAfter(now.plusSeconds(60)) || updated.isBefore(now.minusSeconds(300))
    val active = job?.text("state") == "running" && !stale
    val raw = job?.optJSONObject("progress")
    val progress = raw?.let { observedProgress(it.opt("completed")?.toString(), it.opt("total")?.toString()) }
    val checks = ai?.records("check_history").orEmpty().take(8).reversed()
    val checkCounts = checks.mapNotNull { check ->
        check.opt("observation_count")?.toString()?.toLongOrNull()?.takeIf { it >= 0 }
            ?.let { it to localMoment(check.text("checked_at", "")) }
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
    SpectrumCard(Modifier.testTag("system-telemetry")) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Text("Пульс системы", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
            SpectrumBadge(if (active) "В работе" else "Срез данных",
                accent = if (active) LocalSpectrumPalette.current.emerald else LocalSpectrumPalette.current.blue)
        }
        if (job == null) {
            Text("Пока нет сохранённых заданий", color = colors.onSurfaceVariant)
        } else {
            TelemetryJobStatus(job, progress, stale, active)
        }
        if (checkCounts.isNotEmpty()) {
            Text("Наблюдения в последних проверках", style = MaterialTheme.typography.labelLarge)
            val series = checkCounts.map { it.first }
            val axis = LocalSpectrumPalette.current.semantic.chartGrid
            Canvas(Modifier.fillMaxWidth().height(84.dp).semantics {
                contentDescription = checkCounts.joinToString("; ") { "${it.second}: ${it.first} наблюдений" }
            }) {
                drawLine(axis, Offset(0f, size.height - 1f), Offset(size.width, size.height - 1f))
                val largest = series.maxOrNull()?.coerceAtLeast(1) ?: 1
                val cell = size.width / series.size
                series.forEachIndexed { index, count ->
                    val height = size.height * (count.toDouble() / largest).toFloat()
                    if (height > 0f) drawRoundRect(if (index == series.lastIndex) colors.primary else colors.secondary,
                        Offset(cell * index + cell * .18f, size.height - height), Size(cell * .64f, height), CornerRadius(4.dp.toPx()))
                }
            }
            Text("Последняя проверка: ${checkCounts.last().first} наблюдений · ${checkCounts.last().second}",
                style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
        }
        SpectrumTextButton("Работа и расходы", openDetails, Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Forward)
    }
    ai?.optJSONObject("budget")?.let { budget -> SystemBudgetCard(budget) }
    }
}

@Composable
private fun TelemetryJobStatus(job: JSONObject, progress: ObservedProgress?, stale: Boolean, active: Boolean) {
    Text(telemetryStage(job.text("stage", "")), style = MaterialTheme.typography.titleMedium)
    Text(when {
        stale -> "Последнее полученное состояние · " + localMoment(job.text("updated_at", ""))
        active -> "Сервер выполняет проверку"
        job.text("state") == "completed" -> "Задание завершено"
        job.text("state") == "queued" -> "Ожидает очереди"
        job.text("state") == "failed" -> "Проверка не завершена"
        job.text("state") == "cancel_requested" -> "Ожидает остановки"
        else -> "Состояние: " + jobStateTitle(job.text("state", ""))
    }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    if (progress != null) {
        Text(if (progress.total == null) "Обработано: ${progress.completed} · общий объём уточняется"
            else "Обработано: ${progress.completed} из ${progress.total}", style = MaterialTheme.typography.bodyMedium)
        progress.fraction?.let { SpectrumProgressBar(it, enabled = active) }
    }
    if (active && progress?.fraction == null) SpectrumLoadingIndicator(description = "Работа идёт; общий объём ещё не известен")
}

@Composable
private fun SystemBudgetCard(budget: JSONObject) {
    val hidden = LocalWorkspacePreferences.current.value.hideHomeBalance
    SpectrumCard(Modifier.testTag("system-budget")) {
        Text("Расход на ИИ", style = MaterialTheme.typography.titleMedium)
        BudgetMeter("Сегодня", budget.text("estimated_and_reserved_rub", ""), budget.text("daily_cap_rub", ""), hidden)
        BudgetMeter("Этот месяц", budget.text("monthly_estimated_and_reserved_rub", ""), budget.text("monthly_cap_rub", ""), hidden)
        Text("Оценка с резервом запросов · время Москвы", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (budget.optBoolean("paid_calls_paused") || budget.opt("budget_configuration_valid") == false)
            SpectrumBadge("Платные обращения приостановлены", accent = LocalSpectrumPalette.current.amber)
    }
}

@Composable
private fun BudgetMeter(title: String, spent: String, cap: String, hidden: Boolean) {
    val validSpent = spent.toBigDecimalOrNull()?.takeIf { it >= BigDecimal.ZERO }
    val validCap = cap.toBigDecimalOrNull()?.takeIf { it >= BigDecimal.ZERO }
    Text(title, style = MaterialTheme.typography.labelLarge)
    Text(when {
        hidden -> "••• ₽"
        validSpent == null -> "Сведения о расходах не получены"
        validCap == null -> "$validSpent ₽ · лимит не подтверждён"
        validCap.signum() == 0 -> "$validSpent ₽ · платные обращения выключены"
        else -> "$validSpent / $validCap ₽"
    }, style = MaterialTheme.typography.titleMedium)
    if (!hidden) observedBudgetFraction(spent, cap)?.let { SpectrumProgressBar(it, enabled = false) }
}

private fun telemetryStage(stage: String): String = when (stage) {
    "collecting", "capital_collected" -> "Данные портфеля"
    "collecting_metadata" -> "Проверка инструментов"
    "collecting_operations" -> "История операций"
    "collecting_payouts" -> "Купоны и дивиденды"
    "collecting_news" -> "Проверка публикаций"
    "collecting_calendar" -> "Календарь событий"
    "analysis_monitor", "analysis_queued" -> "Анализ фактов"
    "persisting" -> "Сохранение результатов"
    "done" -> "Результаты сохранены"
    else -> "Серверное задание"
}
