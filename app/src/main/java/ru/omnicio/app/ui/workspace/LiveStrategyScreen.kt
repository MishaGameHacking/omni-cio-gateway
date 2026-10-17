package ru.omnicio.app.ui.workspace

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.ui.spectrum.*

private val limitTitles = linkedMapOf("position_percent" to "Одна позиция", "issuer_percent" to "Компания",
    "group_percent" to "Связанная группа", "sector_percent" to "Отрасль", "currency_percent" to "Валюта")

@Composable
fun LiveStrategyScreen(userId: String, onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/strategy")
    val active = resource.data?.optJSONObject("active")
    val context = LocalContext.current
    val storage = remember(context) { EncryptedWorkspaceStore(context) }
    var configText by rememberSaveable(userId) { mutableStateOf(defaultStrategy().toString()) }
    var baseline by rememberSaveable(userId) { mutableStateOf(configText) }
    var loaded by remember(userId) { mutableStateOf(false) }
    var tab by rememberSaveable(userId) { mutableIntStateOf(0) }
    var preview by remember { mutableStateOf<JSONObject?>(null) }
    var leaving by remember { mutableStateOf(false) }
    var savedMessage by remember { mutableStateOf<String?>(null) }
    val config = remember(configText) { JSONObject(configText) }
    val dirty = configText != baseline
    val version = active?.optInt("version") ?: 0
    val previewAction = rememberWorkspaceAction { result ->
        result.optJSONObject("config")?.let { configText = it.toString() }
        preview = result
    }
    val confirmAction = rememberWorkspaceAction { result ->
        result.optJSONObject("active")?.optJSONObject("config")?.let { configText = it.toString(); baseline = configText }
        preview = null; resource.refresh()
        savedMessage = "Сервер подтвердил новую версию правил."
    }
    LaunchedEffect(resource.data) {
        if (resource.data != null && !loaded) {
            val restored = withContext(Dispatchers.IO) { storage.readJson(userId, "strategy_editor")?.optJSONObject("config") }
            configText = (restored ?: active?.optJSONObject("config") ?: defaultStrategy()).toString()
            baseline = active?.optJSONObject("config")?.toString() ?: defaultStrategy().toString()
            loaded = true
        }
    }
    LaunchedEffect(userId, configText, loaded) {
        if (loaded) withContext(Dispatchers.IO) { storage.saveJson(userId, "strategy_editor", JSONObject().put("config", JSONObject(configText))) }
    }
    val edit: (JSONObject) -> Unit = { if (!previewAction.busy && !confirmAction.busy) { configText = it.toString(); preview = null; savedMessage = null } }
    val leave: () -> Unit = { if (dirty) leaving = true else onBack() }
    BackHandler(onBack = leave)
    WorkspaceDetailPage("Моя стратегия", "Версии правил и влияние на текущий портфель", leave, SpectrumSymbol.Goal) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            SpectrumTabs(listOf("Цель", "Резерв", "Лимиты", "Версии"), tab, { tab = it }, Modifier.padding(horizontal = 20.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item { WorkspaceRequestState(resource) }
                item { SpectrumCard(emphasized = true) {
                    Text(if (active == null) "Правила ещё не подтверждены" else "Действует версия " + version, style = MaterialTheme.typography.titleLarge)
                    Text(if (dirty) "Изменения сохранены как ваш черновик. Для применения нужен расчёт и подтверждение."
                        else "Подтверждённая версия используется при серверной проверке портфеля.")
                    active?.optString("confirmed_at")?.let { Text(localMoment(it), style = MaterialTheme.typography.bodySmall) }
                    savedMessage?.let { Text(it, color = LocalSpectrumPalette.current.emerald) }
                } }
                when (tab) {
                    0 -> item { StrategyGoalEditor(config, edit) }
                    1 -> item { StrategyReserveEditor(config, edit) }
                    2 -> limitTitles.forEach { (key, title) -> item { StrategyLimitEditor(title, key, config, edit) } }
                    else -> resource.data?.records("history").orEmpty().forEach { old -> item {
                        SpectrumCard {
                            Text("Версия " + old.optInt("version"), style = MaterialTheme.typography.titleMedium)
                            Text(localMoment(old.text("confirmed_at", "")), style = MaterialTheme.typography.bodySmall)
                            val previous = old.optJSONObject("config") ?: JSONObject()
                            StrategyDifference(active?.optJSONObject("config"), previous)
                            SpectrumSecondaryButton("Проверить возврат к этой версии", {
                                previewAction.perform("/workspace/strategy/preview", JSONObject().put("expected_version", version)
                                    .put("config", previous).put("rollback_to_version", old.optInt("version")))
                            }, Modifier.fillMaxWidth(), !previewAction.busy && !confirmAction.busy)
                        }
                    } }
                }
                item { DetailFold("Сравнить с действующими правилами") { StrategyDifference(active?.optJSONObject("config"), config) } }
                preview?.let { result -> item { StrategyPreview(result) {
                    confirmAction.perform("/workspace/strategy/confirm", JSONObject().put("preview_id", result.text("preview_id"))
                        .put("expected_version", result.optInt("expected_version")).put("request_id", UUID.randomUUID().toString()))
                } } }
                item {
                    WorkspaceActionState(previewAction); WorkspaceActionState(confirmAction)
                    SpectrumPrimaryButton("Рассчитать влияние", {
                        previewAction.perform("/workspace/strategy/preview", JSONObject().put("expected_version", version).put("config", config))
                    }, Modifier.fillMaxWidth(), !previewAction.busy && !confirmAction.busy && validStrategy(config), SpectrumSymbol.Risk)
                }
                if (!validStrategy(config)) item { Text("Проверьте горизонт, сумму резерва и лимиты от 0 до 100%.", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
    if (leaving) WorkspaceDialog("Изменения стратегии", { leaving = false }) {
        Text("Черновик сохранён на этом устройстве. Действующие правила изменятся только после подтверждения сервера.")
        SpectrumPrimaryButton("Продолжить редактирование", { leaving = false }, Modifier.fillMaxWidth())
        SpectrumSecondaryButton("Вернуться позже", { leaving = false; onBack() }, Modifier.fillMaxWidth())
        SpectrumSecondaryButton("Отменить изменения", { configText = baseline; leaving = false; onBack() }, Modifier.fillMaxWidth())
    }
}

private fun defaultStrategy(): JSONObject = JSONObject().put("goal", "preservation").put("horizon_months", 36)
    .put("reserve", JSONObject().put("amount", "0").put("currency", "RUB"))
    .put("limits", JSONObject().apply { limitTitles.keys.forEach { put(it, "100") } })
    .put("risk_level", "moderate").put("allowed_markets", JSONArray().put("MOEX"))

internal fun validStrategy(config: JSONObject): Boolean {
    val horizon = config.optInt("horizon_months", 0)
    val amount = config.optJSONObject("reserve")?.optString("amount")?.toBigDecimalOrNull()
    val limits = config.optJSONObject("limits") ?: return false
    return horizon in 1..600 && amount != null && amount.signum() >= 0 && limitTitles.keys.all {
        val number = limits.optString(it).toBigDecimalOrNull()
        number != null && number.signum() >= 0 && number <= java.math.BigDecimal(100)
    }
}

@Composable
private fun StrategyGoalEditor(config: JSONObject, edit: (JSONObject) -> Unit) {
    val choices = listOf("preservation", "income", "growth")
    SpectrumCard {
        WorkspaceChoices("Цель", listOf("Сохранение капитала", "Регулярные выплаты", "Рост капитала"),
            choices.indexOf(config.text("goal")).coerceAtLeast(0)) { edit(JSONObject(config.toString()).put("goal", choices[it])) }
        WorkspaceTextInput(config.optInt("horizon_months", 36).toString(),
            { raw -> raw.toIntOrNull()?.let { edit(JSONObject(config.toString()).put("horizon_months", it)) } },
            "Горизонт, месяцев", Modifier.fillMaxWidth(), keyboard = KeyboardOptions(keyboardType = KeyboardType.Number))
        Text("Выбор цели не добавляет ожидаемую прибыль к капиталу. Доступность инструмента проверяется у брокера.")
    }
}

@Composable
private fun StrategyReserveEditor(config: JSONObject, edit: (JSONObject) -> Unit) {
    val reserve = config.getJSONObject("reserve")
    SpectrumCard {
        WorkspaceTextInput(reserve.text("amount", "0"), { raw ->
            edit(JSONObject(config.toString()).put("reserve", JSONObject(reserve.toString()).put("amount", raw.replace(',', '.').take(18))))
        }, "Неприкосновенный резерв", Modifier.fillMaxWidth(), keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        WorkspaceChoices("Валюта резерва", listOf("RUB", "USD", "EUR"), listOf("RUB", "USD", "EUR").indexOf(reserve.text("currency")).coerceAtLeast(0)) {
            edit(JSONObject(config.toString()).put("reserve", JSONObject(reserve.toString()).put("currency", listOf("RUB", "USD", "EUR")[it])))
        }
        Text("Сервер проверит достаточность оценки в той же валюте. Значение 0 означает, что резерв в этих правилах не задан.")
    }
}

@Composable
private fun StrategyLimitEditor(title: String, key: String, config: JSONObject, edit: (JSONObject) -> Unit) {
    val limits = config.getJSONObject("limits")
    SpectrumCard {
        WorkspaceTextInput(limits.text(key, "100"), { raw ->
            edit(JSONObject(config.toString()).put("limits", JSONObject(limits.toString()).put(key, raw.replace(',', '.').take(8))))
        }, title + ", %", Modifier.fillMaxWidth(), keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        Text("Ограничение применяется к подтверждённой доле. 100% не ограничивает эту долю; неизвестные связи не считаются нулём.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun StrategyDifference(before: JSONObject?, after: JSONObject) {
    if (before == null) Text("До подтверждения активной версии нет.")
    listOf("goal", "horizon_months", "risk_level").forEach { field ->
        val label = when (field) { "goal" -> "Цель"; "horizon_months" -> "Горизонт, месяцев"; else -> "Профиль риска" }
        if (before?.opt(field) != after.opt(field)) Text(label + ": " + strategyValue(before?.text(field, "Не задано")) + " → " + strategyValue(after.text(field)))
    }
    val oldLimits = before?.optJSONObject("limits")
    val newLimits = after.optJSONObject("limits")
    limitTitles.forEach { (key, label) -> if (oldLimits?.opt(key) != newLimits?.opt(key)) Text(label + ": " + (oldLimits?.text(key) ?: "Не задано") + " → " + (newLimits?.text(key) ?: "Не задано") + "%") }
    Text("Резерв: " + PrivateValue(moneyText(before?.optJSONObject("reserve"))) + " → " + PrivateValue(moneyText(after.optJSONObject("reserve"))))
}

private fun strategyValue(value: String?): String = when (value) {
    "preservation" -> "Сохранение"; "income" -> "Выплаты"; "growth" -> "Рост"; "moderate" -> "Умеренный"
    "conservative" -> "Консервативный"; "aggressive" -> "Высокий"; else -> value ?: "Не задано"
}

@Composable
private fun StrategyPreview(preview: JSONObject, confirm: () -> Unit) {
    val impact = preview.optJSONObject("impact") ?: JSONObject()
    SpectrumCard(emphasized = true) {
        Text("Влияние на текущий портфель", style = MaterialTheme.typography.titleLarge)
        Text("Нарушений новых лимитов: " + impact.records("breaches").size)
        impact.records("breaches").forEach { item -> Text(item.text("label", "Ограничение") + ": " + item.text("share_percent") + "% / " + item.text("limit_percent") + "%") }
        impact.optJSONObject("reserve_gap")?.let { Text("Недостающий резерв: " + PrivateValue(moneyText(it))) }
        impact.strings("warnings").forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
        Text("Расчёт действителен до " + localMoment(preview.text("expires_at", "")), style = MaterialTheme.typography.bodySmall)
        Text("Если портфель или правила изменятся, потребуется новый расчёт.", style = MaterialTheme.typography.bodySmall)
        SpectrumPrimaryButton("Подтвердить эту версию", confirm, Modifier.fillMaxWidth(), preview.optBoolean("can_confirm"), SpectrumSymbol.Goal)
    }
}

