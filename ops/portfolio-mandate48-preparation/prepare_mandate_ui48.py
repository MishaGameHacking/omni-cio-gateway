"""Prepare keyboard-free strategy controls and explicit portfolio mandate choices."""

CONTROLS = '''package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import java.math.BigDecimal
import ru.omnicio.app.ui.spectrum.*

/** Stepping preserves the loaded decimal exactly; no Float is persisted. */
internal fun steppedStrategyNumber(value: String, step: String, direction: Int,
    minimum: String, maximum: String): String? {
    if (direction != -1 && direction != 1) return null
    val current = value.toBigDecimalOrNull() ?: return null
    val delta = step.toBigDecimalOrNull()?.takeIf { it.signum() > 0 } ?: return null
    val lower = minimum.toBigDecimalOrNull() ?: return null
    val upper = maximum.toBigDecimalOrNull() ?: return null
    if (lower > upper || current < lower || current > upper) return null
    return (current + delta * BigDecimal(direction)).coerceIn(lower, upper).stripTrailingZeros().toPlainString()
}

@Composable
internal fun StrategyNumberChoice(title: String, value: String, unit: String, enabled: Boolean,
    minimum: String, maximum: String, presets: List<String>, steps: List<String>,
    percentSlider: Boolean = false, onChange: (String) -> Unit) {
    var increment by rememberSaveable(title) { mutableStateOf(steps.first()) }
    val current = value.toBigDecimalOrNull()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(if (current == null) "Выберите значение" else "$value $unit", style = MaterialTheme.typography.titleLarge)
        WorkspaceSuggestionRow("", presets.map { WorkspaceSuggestion(it, "$it $unit") }, enabled) { onChange(it) }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            val minus = steppedStrategyNumber(value, increment, -1, minimum, maximum)
            val plus = steppedStrategyNumber(value, increment, 1, minimum, maximum)
            SpectrumSecondaryButton("− $increment", { minus?.let(onChange) },
                Modifier.weight(1f).semantics { contentDescription = "$title, уменьшить на $increment $unit" },
                enabled && minus != null && minus.toBigDecimal() != current)
            SpectrumSecondaryButton("+ $increment", { plus?.let(onChange) },
                Modifier.weight(1f).semantics { contentDescription = "$title, увеличить на $increment $unit" },
                enabled && plus != null && plus.toBigDecimal() != current)
        }
        if (steps.size > 1) DetailFold("Шаг изменения · $increment $unit") {
            WorkspaceSuggestionRow("", steps.map { WorkspaceSuggestion(it, "$it $unit") }, enabled) { increment = it }
        }
        if (percentSlider && current != null && current >= BigDecimal.ZERO && current <= BigDecimal(100)) {
            SpectrumSlider(current.toFloat(), { selected ->
                // Each deliberate tick chooses a visible whole percentage. The
                // exact fractional value stays intact until the user moves it.
                val chosen = BigDecimal(kotlin.math.round(selected).toInt())
                    .coerceIn(minimum.toBigDecimal(), maximum.toBigDecimal()).stripTrailingZeros().toPlainString()
                onChange(chosen)
            }, Modifier.fillMaxWidth().semantics { contentDescription = "$title, целые проценты" },
                enabled = enabled, valueRange = 0f..100f, steps = 99)
        }
    }
}

internal fun newMandateDraft(): JSONObject = JSONObject().put("base_currency", "RUB")
    .put("allowed_sessions", JSONArray().put("main"))

internal fun validPortfolioMandate(value: JSONObject): Boolean {
    if (value.optString("base_currency") != "RUB" || value.optString("account_id").isBlank()) return false
    val fields = listOf("loss_capacity_percent", "bond_target_percent", "share_target_percent",
        "max_discretionary_turnover_percent", "max_trade_cost_percent")
    val numbers = fields.map { value.optString(it).toBigDecimalOrNull() ?: return false }
    if (numbers.any { it < BigDecimal.ZERO || it > BigDecimal(100) }) return false
    val bonds = numbers[1]; val shares = numbers[2]
    if ((bonds + shares).compareTo(BigDecimal(100)) != 0) return false
    when (value.optString("asset_mode")) {
        "bonds" -> if (bonds.compareTo(BigDecimal(100)) != 0 || shares.signum() != 0) return false
        "shares" -> if (shares.compareTo(BigDecimal(100)) != 0 || bonds.signum() != 0) return false
        "mixed" -> if (bonds.signum() <= 0 || shares.signum() <= 0) return false
        else -> return false
    }
    val rating = value.opt("minimum_rating_level") as? Int ?: return false
    val cooldown = value.opt("rebalance_cooldown_days") as? Int ?: return false
    val turnoverWindow = value.opt("turnover_window_days") as? Int ?: return false
    if (rating !in 0..9 || cooldown !in 0..365 || turnoverWindow !in 1..366) return false
    if (value.opt("reinvest_coupons") !is Boolean || value.opt("reinvest_dividends") !is Boolean) return false
    val sessions = value.optJSONArray("allowed_sessions") ?: return false
    return sessions.length() == 1 && sessions.optString(0) == "main"
}

@Composable
internal fun StrategyMandateEditor(config: JSONObject, accounts: List<JSONObject>, enabled: Boolean,
    onEdit: (JSONObject) -> Unit) {
    val mandate = config.optJSONObject("mandate") ?: newMandateDraft()
    val change: (String, Any) -> Unit = { key, value ->
        onEdit(JSONObject(config.toString()).put("mandate", JSONObject(mandate.toString()).put(key, value)))
    }
    SpectrumCard(emphasized = true) {
        Text("Инвестиционный профиль", style = MaterialTheme.typography.titleLarge)
        Text("Выбор сохраняется автоматически. Пока обязательные параметры не выбраны, изменения остаются вашим черновиком.")
        Text("Торговля выключена. Правила используются для проверки допустимости предложений.", style = MaterialTheme.typography.bodySmall)
        val modes = listOf("bonds", "shares", "mixed")
        WorkspaceChoices("Состав", listOf("Облигации", "Акции", "Облигации и акции"),
            modes.indexOf(mandate.optString("asset_mode")), enabled) { index ->
            val next = JSONObject(mandate.toString()).put("asset_mode", modes[index])
            when (index) {
                0 -> next.put("bond_target_percent", "100").put("share_target_percent", "0")
                1 -> next.put("bond_target_percent", "0").put("share_target_percent", "100")
                else -> if (mandate.optString("asset_mode") != "mixed") {
                    next.remove("bond_target_percent"); next.remove("share_target_percent")
                }
            }
            onEdit(JSONObject(config.toString()).put("mandate", next))
        }
        if (mandate.optString("asset_mode") == "mixed") {
            StrategyNumberChoice("Доля облигаций", mandate.optString("bond_target_percent"), "%", enabled,
                "0.01", "99.99", listOf("20", "40", "60", "80"), listOf("1", "0.1", "0.01"), true) { bonds ->
                val next = JSONObject(mandate.toString()).put("bond_target_percent", bonds)
                    .put("share_target_percent", (BigDecimal(100) - bonds.toBigDecimal()).stripTrailingZeros().toPlainString())
                onEdit(JSONObject(config.toString()).put("mandate", next))
            }
            Text("Доля акций: " + mandate.optString("share_target_percent", "не выбрана") + "%")
        }
        Text("Счёт", style = MaterialTheme.typography.titleMedium)
        val selected = accounts.firstOrNull { it.optString("id") == mandate.optString("account_id") }
        Text(selected?.optString("name")?.takeIf { it.isNotBlank() } ?: "Выберите подключённый счёт")
        WorkspaceSuggestionRow("", accounts.map { WorkspaceSuggestion(it.getString("id"),
            it.optString("name").ifBlank { "Счёт · " + it.getString("id").takeLast(4) }) }, enabled) { change("account_id", it) }
        if (accounts.isEmpty()) Text("Подключённые счета появятся после обновления портфеля.")
        Text("Валюта профиля · RUB. Основная биржевая сессия.", style = MaterialTheme.typography.bodySmall)
    }
    SpectrumCard {
        StrategyNumberChoice("Допустимый убыток", mandate.optString("loss_capacity_percent"), "%", enabled,
            "0", "100", listOf("0", "1", "5", "10", "20"), listOf("1", "0.1", "0.01"), true) { change("loss_capacity_percent", it) }
        Text("0% запрещает увеличение риска. Выбранное значение не гарантирует ограничения фактических потерь.", style = MaterialTheme.typography.bodySmall)
        DetailFold("Минимальный кредитный рейтинг") {
            val ratings = listOf("AAA", "AA+", "AA", "AA−", "A+", "A", "A−", "BBB+", "BBB", "BBB−")
            Text((mandate.opt("minimum_rating_level") as? Int)?.let { ratings.getOrNull(it) } ?: "Выберите порог")
            WorkspaceSuggestionRow("", ratings.mapIndexed { index, text -> WorkspaceSuggestion(index.toString(), text) }, enabled) {
                change("minimum_rating_level", it.toInt())
            }
            Text("Порог можно только сузить в диапазоне AAA–BBB−. Для ОФЗ действует отдельная политика.", style = MaterialTheme.typography.bodySmall)
        }
    }
    SpectrumCard {
        DetailFold("Оборот и расходы") {
            StrategyNumberChoice("Период учёта оборота", mandate.opt("turnover_window_days")?.toString().orEmpty(), "дн.", enabled,
                "1", "366", listOf("7", "30", "90", "365"), listOf("1", "7", "30")) { change("turnover_window_days", it.toInt()) }
            StrategyNumberChoice("Предел обычного оборота", mandate.optString("max_discretionary_turnover_percent"), "%", enabled,
                "0", "100", listOf("0", "1", "5", "10"), listOf("1", "0.1", "0.01"), true) { change("max_discretionary_turnover_percent", it) }
            StrategyNumberChoice("Предел издержек сделки", mandate.optString("max_trade_cost_percent"), "%", enabled,
                "0", "100", listOf("0", "0.1", "0.25", "0.5", "1"), listOf("0.01", "0.1", "1")) { change("max_trade_cost_percent", it) }
            StrategyNumberChoice("Пауза между перераспределениями", mandate.opt("rebalance_cooldown_days")?.toString().orEmpty(), "дн.", enabled,
                "0", "365", listOf("0", "7", "30", "90"), listOf("1", "7", "30")) { change("rebalance_cooldown_days", it.toInt()) }
        }
        listOf("reinvest_coupons" to "Купоны", "reinvest_dividends" to "Дивиденды").forEach { (key, title) ->
            val value = mandate.opt(key) as? Boolean
            if (value == null) WorkspaceChoices("$title · реинвестирование", listOf("Оставлять в резерве", "Использовать для покупок"), -1, enabled) {
                change(key, it == 1)
            } else WorkspaceToggle("$title · реинвестирование", "Учитывается при распределении поступлений", value,
                enabled = enabled) { change(key, it) }
        }
    }
}
'''

def apply(files, base):
    path = 'app/src/main/java/ru/omnicio/app/ui/workspace/LiveStrategyScreen.kt'
    text = files.get(path) or base(path)
    def replace(before, after):
        nonlocal text
        assert text.count(before) == 1, before[:100]
        text = text.replace(before, after)
    replace('listOf("Цель", "Резерв", "Лимиты", "Версии")', 'listOf("Цель", "Профиль", "Резерв", "Лимиты", "Версии")')
    replace('                    1 -> item { StrategyReserveEditor(config, editor.canEdit, edit) }\n                    2 -> limitTitles.forEach',
        '                    1 -> item { StrategyMandateEditor(config, resource.data?.records("available_accounts").orEmpty(), editor.canEdit, edit) }\n'
        '                    2 -> item { StrategyReserveEditor(config, editor.canEdit, edit) }\n                    3 -> limitTitles.forEach')
    replace('    return horizon in 1..600', '    if (config.has("mandate") && (config.optJSONObject("mandate")?.let(::validPortfolioMandate) != true || config.optJSONObject("reserve")?.optString("currency") != "RUB")) return false\n    return horizon in 1..600')
    start = text.index('        WorkspaceTextInput(config.opt("horizon_months")')
    end = text.index('        Text("Выбор цели', start)
    text = text[:start] + '''        StrategyNumberChoice("Горизонт", config.opt("horizon_months")?.toString().orEmpty(), "мес.", enabled,
            "1", "600", listOf("12", "36", "60", "120"), listOf("1", "12")) {
            edit(JSONObject(config.toString()).put("horizon_months", it.toInt()))
        }
''' + text[end:]
    start = text.index('        WorkspaceTextInput(reserve.text("amount"')
    end = text.index('        WorkspaceChoices("Валюта резерва"', start)
    text = text[:start] + '''        StrategyNumberChoice("Неприкосновенный резерв", reserve.text("amount", "0"), reserve.text("currency"), enabled,
            "0", "999999999999999.99", listOf("0", "1000", "10000", "100000"), listOf("1000", "100", "1", "0.01")) { amount ->
            edit(JSONObject(config.toString()).put("reserve", JSONObject(reserve.toString()).put("amount", amount)))
        }
''' + text[end:]
    start = text.index('        WorkspaceTextInput(limits.text(key')
    end = text.index('        Text("Ограничение применяется', start)
    text = text[:start] + '''        StrategyNumberChoice(title, limits.text(key, "100"), "%", enabled, "0.01", "100",
            listOf("1", "3", "5", "8", "10", "20", "100"), listOf("1", "0.1", "0.01"), true) { percent ->
            edit(JSONObject(config.toString()).put("limits", JSONObject(limits.toString()).put(key, percent)))
        }
''' + text[end:]
    replace('Проверьте горизонт, сумму резерва и лимиты больше 0 и до 100%.', 'Выберите обязательные параметры профиля; проверьте горизонт, резерв и лимиты. Черновик сохранён на устройстве.')
    # Unused pre-autosave confirmation components are removed, not exposed as a second path.
    start = text.index('@Composable\nprivate fun StrategyPreview(')
    end = text.index('@Composable\nprivate fun StrategyHistoryCard(', start)
    text = text[:start] + text[end:]
    start = text.index('@Composable\nprivate fun StrategyEditorStatus(')
    text = text[:start]
    for line in ('import androidx.compose.foundation.text.KeyboardOptions\n', 'import androidx.compose.ui.text.input.KeyboardType\n', 'import java.util.UUID\n'):
        text = text.replace(line, '')
    files[path] = text.rstrip() + '\n'
    files['app/src/main/java/ru/omnicio/app/ui/workspace/StrategyMandateControls.kt'] = CONTROLS
