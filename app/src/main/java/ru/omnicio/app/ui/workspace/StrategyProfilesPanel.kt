package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.ui.spectrum.*

/** Profile contents and amounts come from the server; no presets are baked into the APK. */
@Composable
internal fun StrategyProfilesPanel(catalogue: JSONObject?, config: JSONObject, enabled: Boolean,
    select: (JSONObject) -> Unit, edit: (JSONObject) -> Unit) {
    var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
    val profiles = catalogue?.records("items").orEmpty()
    val activeId = config.optJSONObject("tuning")?.text("profile_id", "")
    val suggested = catalogue?.text("suggested_id", "")
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Основа вашей стратегии", style = MaterialTheme.typography.titleLarge)
        Text("Выберите основу. Сервер рассчитает резерв по портфелю и сохранит более строгие действующие лимиты.",
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (catalogue == null) Text("Профили появятся после обновления серверных данных.")
        profiles.forEach { profile ->
            SpectrumCard(onClick = { selectedId = profile.text("id", "") },
                emphasized = activeId == profile.text("id", "")) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    SpectrumIcon(strategyProfileSymbol(profile.text("id", "")), Modifier.size(48.dp), motionAllowed = false)
                    Text(profile.text("title", ""), Modifier.weight(1f), style = MaterialTheme.typography.titleMedium.copy(hyphens = androidx.compose.ui.text.style.Hyphens.Auto))
                }
                Text(profile.text("description", ""), color = MaterialTheme.colorScheme.onSurfaceVariant)
                val value = profile.optJSONObject("config")
                Text(strategyClassLabel(value),
                    style = MaterialTheme.typography.labelLarge)
                if (activeId == profile.text("id", "")) SpectrumBadge("Выбранная основа")
                else if (suggested == profile.text("id", "")) Text("Основа по текущим настройкам",
                    style = MaterialTheme.typography.bodySmall)
            }
        }
        config.optJSONObject("tuning")?.let { tuning ->
            SpectrumCard {
                WorkspaceToggle("Автоматическая подстройка", "Регулирует объём проверки кандидатов. Не повышает риск и не расходует деньги на ИИ.",
                    tuning.optBoolean("enabled"), enabled = enabled) { value ->
                    edit(JSONObject(config.toString()).put("tuning", JSONObject(tuning.toString()).put("enabled", value)))
                }
            }
        }
    }
    val selected = profiles.firstOrNull { it.text("id", "") == selectedId }
    if (selected != null) WorkspaceDialog(selected.text("title", "Стратегия"), { selectedId = null }) {
        val proposed = selected.optJSONObject("config")
        Text(selected.text("description", ""))
        Text("Горизонт: ${strategyYears(proposed?.optInt("horizon_months") ?: 36)} лет")
        Text("Резерв: " + PrivateValue(moneyText(proposed?.optJSONObject("reserve"))))
        Text("Предел одной позиции: ${proposed?.optJSONObject("limits")?.text("position_percent", "—")}%")
        Text("Ограничения концентрации, расходов и частоты изменений настроены автоматически.")
        if (!selected.optBoolean("ready_for_preview")) Text(
            "Проверьте счёт, срок и отношение к потерям. До этого новые покупки не рассчитываются.",
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("Изменение сохраняется на сервере после проверки. Доходность не гарантирована.",
            style = MaterialTheme.typography.bodySmall)
        SpectrumPrimaryButton("Использовать профиль", {
            proposed?.let { select(JSONObject(it.toString())) }; selectedId = null
        }, Modifier.fillMaxWidth(), enabled && proposed != null)
        SpectrumSecondaryButton("Отмена", { selectedId = null }, Modifier.fillMaxWidth())
    }
}


internal fun strategyProfileSymbol(id: String): SpectrumSymbol = when (id) {
    "capital" -> SpectrumSymbol.Capital
    "coupon" -> SpectrumSymbol.Income
    "balanced" -> SpectrumSymbol.Balanced
    "growth" -> SpectrumSymbol.Growth
    "equity" -> SpectrumSymbol.Dividends
    else -> SpectrumSymbol.Strategy
}


internal fun strategyClassLabel(config: JSONObject?): String {
    val values = config?.optJSONObject("construction")?.optJSONArray("enabled_classes")
    if (values != null) return (0 until values.length()).map { when(values.optString(it)) {
        "bond" -> "Облигации"; "share" -> "Акции"; else -> "Фонды"
    } }.joinToString(" · ")
    return "Облигации и акции"
}

@Composable
internal fun StrategyAllocationSummary(allocation: JSONObject?) {
    val weights = allocation?.optJSONObject("weights_percent") ?: return
    val waiting = (allocation.optJSONArray("missing")?.length() ?: 0) > 0
    SpectrumCard {
        Text(if (waiting) "Распределение ещё не рассчитано" else "Целевое распределение",
            style = MaterialTheme.typography.titleMedium)
        if (waiting) {
            Text("Укажите доход вне портфеля и потери, которые готовы перенести. До этого система не предлагает новые покупки.")
            Text("Ваши деньги не перемещались. Фактические остатки показаны в «Аналитике».",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            listOf("bond" to "Облигации", "share" to "Акции", "etf" to "Фонды", "cash" to "Деньги и резерв")
                .forEachIndexed { index, (key, label) ->
                    val percent = weights.optString(key).toBigDecimalOrNull()
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(label, Modifier.weight(1f))
                        Text((percent?.stripTrailingZeros()?.toPlainString() ?: "—") + " %", style = MaterialTheme.typography.labelLarge)
                    }
                    if (percent != null) SpectrumProgressBar((percent.toFloat() / 100f).coerceIn(0f, 1f),
                        accent = LocalSpectrumPalette.current.chartSeries[index % LocalSpectrumPalette.current.chartSeries.size])
                }
            Text("План, к которому стремится стратегия. Текущие доли смотрите в «Аналитике». Количество покупок ограничено целыми лотами и бюджетом.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
