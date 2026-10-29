package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.ui.spectrum.*

/** Personal choices only; technical constraints come from the server profile. */
@Composable
internal fun StrategySimpleSettings(config: JSONObject, accounts: List<JSONObject>, enabled: Boolean,
    edit: (JSONObject) -> Unit) {
    val settings = config.optJSONObject("construction")
    if (settings == null) {
        WorkspaceEmpty("Выберите стратегию", "Новые профили автоматически настроят ограничения и подготовят эти параметры.")
        return
    }
    val mandate = config.optJSONObject("mandate") ?: return
    val change: (String, Any) -> Unit = { key, value ->
        edit(JSONObject(config.toString()).put("construction", JSONObject(settings.toString()).put(key, value)))
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SpectrumCard {
            Text("Ваш план", style = MaterialTheme.typography.titleLarge)
            WorkspaceChoices("Счёт", accounts.map { it.optString("name").ifBlank { "Счёт · " + it.optString("id").takeLast(4) } },
                accounts.indexOfFirst { it.optString("id") == mandate.optString("account_id") }, enabled) {
                edit(JSONObject(config.toString()).put("mandate", JSONObject(mandate.toString()).put("account_id", accounts[it].getString("id"))))
            }
            StrategyNumberChoice("Горизонт", config.optInt("horizon_months", 36).toString(), "мес.", enabled,
                "12", "360", listOf("12", "36", "60", "120", "240", "360"), listOf("12")) {
                edit(JSONObject(config.toString()).put("horizon_months", it.toInt()))
            }
            StrategyNumberChoice("Возраст", if (settings.isNull("age")) "" else settings.optInt("age").toString(), "лет", enabled,
                "18", "100", listOf("18", "30", "45", "60", "75"), listOf("1")) { change("age", it.toInt()) }
            Text("Возраст не определяет риск сам по себе. Система учитывает срок, резерв и вашу способность переносить потери.", style = MaterialTheme.typography.bodySmall)
        }
        SpectrumCard {
            Text("Какие активы использовать", style = MaterialTheme.typography.titleLarge)
            val array = settings.optJSONArray("enabled_classes") ?: JSONArray()
            val selected = (0 until array.length()).map { array.getString(it) }.toSet()
            listOf("bond" to "Облигации", "share" to "Акции", "etf" to "Фонды").forEach { (key, label) ->
                WorkspaceToggle(label, when(key) {
                    "bond" -> "Проверка выплат, срока и кредитного качества"
                    "share" -> "Участие в бизнесе; цена и дивиденды меняются"
                    else -> "Индекс, комиссии и риски фонда"
                }, key in selected, enabled = enabled && (key !in selected || selected.size > 1)) { checked ->
                    change("enabled_classes", JSONArray((if (checked) selected + key else selected - key).sorted()))
                }
            }
            Text("Доступность инструментов и тесты проверяет брокер. Выключение класса не продаёт текущие позиции.", style = MaterialTheme.typography.bodySmall)
        }
        SpectrumCard {
            Text("Финансовая устойчивость", style = MaterialTheme.typography.titleLarge)
            val stability = listOf("unknown", "stable", "variable")
            WorkspaceChoices("Доход вне портфеля", listOf("Ещё не указано", "Стабильный", "Нерегулярный"),
                stability.indexOf(settings.optString("income_stability", "unknown")), enabled) { change("income_stability", stability[it]) }
            StrategyNumberChoice("Потери, которые смогу перенести", mandate.optString("loss_capacity_percent", "0"), "%", enabled,
                "0", "30", listOf("0", "5", "10", "15", "20", "30"), listOf("5")) { value ->
                edit(JSONObject(config.toString())
                    .put("mandate", JSONObject(mandate.toString()).put("loss_capacity_percent", value))
                    .put("construction", JSONObject(settings.toString()).put("loss_capacity_confirmed", true)))
            }
            Text("Это ваш бюджет риска, а не гарантия ограничения убытка. При 0% новые покупки отключены.", style = MaterialTheme.typography.bodySmall)
            StrategyNumberChoice("Держать в резерве", settings.optInt("reserve_percent", 20).toString(), "%", enabled,
                "5", "80", listOf("5", "10", "20", "30", "50", "80"), listOf("5")) { change("reserve_percent", it.toInt()) }
        }
        SpectrumCard {
            WorkspaceToggle("Облигации не ниже ключевой ставки", "Сравнивается доходность к худшему событию после комиссии, до личного налога. Акции и фонды так не сравниваются.",
                settings.optString("key_rate_mode") == "at_least_key_rate", enabled = enabled) {
                change("key_rate_mode", if (it) "at_least_key_rate" else "allow_below")
            }
            Text("При выключенном фильтре допустима меньшая доходность. Высокая доходность может означать высокий риск дефолта; ради неё лимиты не повышаются.", style = MaterialTheme.typography.bodySmall)
            WorkspaceToggle("Реинвестировать поступления", "При выключении новые покупки приостановлены; сокращение риска остаётся доступным", settings.optBoolean("reinvest", true), enabled = enabled) { value ->
                edit(JSONObject(config.toString()).put("construction", JSONObject(settings.toString()).put("reinvest", value))
                    .put("mandate", JSONObject(mandate.toString()).put("reinvest_coupons", value).put("reinvest_dividends", value)))
            }
        }
    }
}
