package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.testTagsAsResourceId
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

/** Decimal text is never rounded through Float. A field commits on Done or focus loss. */
internal fun strategyNumberInput(raw: String, minimum: String, maximum: String, whole: Boolean): String? {
    val normalized = raw.trim().replace(',', '.')
    if (!Regex("[0-9]+(?:\\.[0-9]+)?").matches(normalized)) return null
    val number = normalized.toBigDecimalOrNull() ?: return null
    if (number < minimum.toBigDecimal() || number > maximum.toBigDecimal()) return null
    if (whole && number.stripTrailingZeros().scale() > 0) return null
    return number.stripTrailingZeros().toPlainString()
}

@Suppress("UNUSED_PARAMETER")
@Composable
internal fun StrategyNumberChoice(title: String, value: String, unit: String, enabled: Boolean,
    minimum: String, maximum: String, presets: List<String>, steps: List<String>,
    percentSlider: Boolean = false, onChange: (String) -> Unit) {
    val ownerId = LocalWorkspaceSession.current.userId
    var text by rememberSaveable(ownerId, title, value) { mutableStateOf(value) }
    var submitted by remember(ownerId, title, value) { mutableStateOf(value) }
    var focused by remember(ownerId, title) { mutableStateOf(false) }
    val whole = unit == "мес." || unit == "дн."
    val parsed = strategyNumberInput(text, minimum, maximum, whole)
    val focusManager = androidx.compose.ui.platform.LocalFocusManager.current
    val commit = {
        if (enabled && parsed != null && parsed != submitted) {
            submitted = parsed
            onChange(parsed)
        }
    }
    SpectrumTextField(text, { text = it }, Modifier.fillMaxWidth()
        .semantics { testTagsAsResourceId = true }
        .testTag(if (title == "Горизонт") "strategy-horizon" else "strategy-number-" + title)
        .onFocusChanged { state ->
        if (focused && !state.hasFocus) commit()
        focused = state.hasFocus
    }, enabled = enabled, singleLine = true,
        label = { Text(title) }, trailingIcon = { Text(unit, Modifier.padding(end = 12.dp)) },
        isError = parsed == null,
        supportingText = {
            if (parsed == null) Text(if (text.isBlank()) "Укажите значение" else
                "От $minimum до $maximum $unit" + if (whole) ". Целое число." else "")
            else if (text != value) Text("Сохранится после завершения ввода")
        },
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(
            keyboardType = if (whole) androidx.compose.ui.text.input.KeyboardType.Number else androidx.compose.ui.text.input.KeyboardType.Decimal,
            imeAction = androidx.compose.ui.text.input.ImeAction.Done),
        keyboardActions = androidx.compose.foundation.text.KeyboardActions(onDone = { commit(); focusManager.clearFocus() }))
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
        Text("Заполните профиль один раз. Изменения сохраняются после проверки сервером.", style = MaterialTheme.typography.bodySmall)
        SpectrumBadge("Режим анализа · сделки выключены")
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
        WorkspaceChoices("Счёт", accounts.map { account ->
            account.optString("name").ifBlank { "Счёт · " + account.getString("id").takeLast(4) }
        }, accounts.indexOfFirst { it.optString("id") == mandate.optString("account_id") }, enabled) {
            change("account_id", accounts[it].getString("id"))
        }
        if (accounts.isEmpty()) Text("Подключённые счета появятся после обновления портфеля.")
        Text("Валюта профиля · RUB. Основная биржевая сессия.", style = MaterialTheme.typography.bodySmall)
    }
    SpectrumCard {
        StrategyNumberChoice("Допустимый убыток", mandate.optString("loss_capacity_percent"), "%", enabled,
            "0", "100", listOf("0", "1", "5", "10", "20"), listOf("1", "0.1", "0.01"), true) { change("loss_capacity_percent", it) }
        Text("0% запрещает увеличение риска. Выбранное значение не гарантирует ограничения фактических потерь.", style = MaterialTheme.typography.bodySmall)
        val ratings = listOf("AAA", "AA+", "AA", "AA−", "A+", "A", "A−", "BBB+", "BBB", "BBB−")
        WorkspaceChoices("Минимальный рейтинг", ratings, mandate.optInt("minimum_rating_level", -1), enabled) {
            change("minimum_rating_level", it)
        }

    }
    SpectrumCard {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Оборот и расходы", style = MaterialTheme.typography.titleMedium)
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
            } else WorkspaceToggle("$title · реинвестирование", "Ваш выбор для будущих поступлений", value,
                enabled = enabled) { change(key, it) }
        }
    }
}

