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
                    Text(profile.text("title", ""), Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                }
                Text(profile.text("description", ""), color = MaterialTheme.colorScheme.onSurfaceVariant)
                val value = profile.optJSONObject("config")
                val mandate = value?.optJSONObject("mandate")
                Text("Облигации ${mandate?.text("bond_target_percent", "—")}% · акции ${mandate?.text("share_target_percent", "—")}%",
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
        val mandate = proposed?.optJSONObject("mandate")
        Text(selected.text("description", ""))
        Text("Горизонт: ${proposed?.optInt("horizon_months")} мес.")
        Text("Резерв: " + PrivateValue(moneyText(proposed?.optJSONObject("reserve"))))
        Text("Предел одной позиции: ${proposed?.optJSONObject("limits")?.text("position_percent", "—")}%")
        Text("Лимит оборота: ${mandate?.text("max_discretionary_turnover_percent", "—")}% за ${mandate?.optInt("turnover_window_days")} дней")
        if (!selected.optBoolean("ready_for_preview")) Text(
            "В параметрах проверьте счёт и допустимые потери. Нулевой допуск потерь блокирует новые покупки.",
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
