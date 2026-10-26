package ru.omnicio.app.ui.workspace

import ru.omnicio.app.ui.spatial.SpatialBackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.RegisterPanelExit

private const val UNSPECIFIED_VALUE = "Не задано"


private val limitTitles = linkedMapOf("position_percent" to "Одна позиция", "issuer_percent" to "Компания",
    "group_percent" to "Связанная группа", "sector_percent" to "Отрасль", "currency_percent" to "Валюта")

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LiveStrategyScreen(userId: String, onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/strategy")
    val active = resource.data?.optJSONObject("active")
    val auto = LocalWorkspaceAutoSave.current
    val record = auto?.get(AutoSaveKind.Strategy)
    val context = LocalContext.current
    val storage = remember(context) { EncryptedWorkspaceStore(context) }
    var configText by rememberSaveable(userId) { mutableStateOf(defaultStrategy().toString()) }
    var hasEditorState by rememberSaveable(userId) { mutableStateOf(false) }
    var loaded by remember(userId) { mutableStateOf(false) }
    var tab by rememberSaveable(userId) { mutableIntStateOf(0) }
    val version = active?.optInt("version") ?: 0
    val config = remember(configText) { JSONObject(configText) }
    LaunchedEffect(resource.data, auto?.ready) {
        if (resource.data != null && auto?.ready == true && !loaded) {
            if (!hasEditorState) {
                val restored = withContext(Dispatchers.IO) { storage.readJson(userId, "strategy_editor")?.optJSONObject("config") }
                configText = record?.draft ?: (restored ?: active?.optJSONObject("config") ?: defaultStrategy()).toString()
                hasEditorState = true
            }
            loaded = true
        }
    }
    LaunchedEffect(record?.revision, record?.draft, record?.phase) {
        if (record != null) {
            configText = record.draft
            if (record.phase == AutoSavePhase.Saved) resource.refresh()
        }
    }
    val editor = StrategyEditorAvailability(hasEditorState, auto?.ready != true)
    val edit: (JSONObject) -> Unit = { next ->
        if (editor.canEdit) {
            configText = next.toString()
            auto?.edit(AutoSaveKind.Strategy, config, next,
                version, validStrategy(next))
        }
    }
    val restoreVersion = rememberWorkspaceAction { result -> result.optJSONObject("config")?.let(edit) }
    val requestExit: (() -> Unit) -> Unit = { proceed -> proceed() }
    RegisterPanelExit(WorkspaceRoute.Strategies, requestExit)
    SpatialBackHandler(onBack = onBack)
    WorkspaceDetailPage("Моя стратегия", "Правила сохраняются после проверки сервером", onBack, SpectrumSymbol.Strategy,
        adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            if (!compact || !WindowInsets.isImeVisible) SpectrumTabs(listOf("Цель", "Профиль", "Резерв", "Лимиты", "Версии"), tab, { tab = it }, Modifier.padding(horizontal = 20.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = if (compact) 0.dp else 20.dp),
                verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item {
                    WorkspaceRequestState(resource)
                    Text(if (version > 0) "Действует версия $version" else "Активной версии пока нет",
                        style = MaterialTheme.typography.labelLarge)
                    AutoSaveStatus(record) { auto?.retry(AutoSaveKind.Strategy) }
                }
                when (tab) {
                    0 -> item { StrategyGoalEditor(config, editor.canEdit, edit) }
                    1 -> item { StrategyMandateEditor(config, resource.data?.records("available_accounts").orEmpty(), editor.canEdit, edit) }
                    2 -> item { StrategyReserveEditor(config, editor.canEdit, edit) }
                    3 -> limitTitles.forEach { (key, title) -> item { StrategyLimitEditor(title, key, config, editor.canEdit, edit) } }
                    else -> resource.data?.records("history").orEmpty().forEach { old -> item {
                        StrategyHistoryCard(old, active, loaded, editor, version, restoreVersion)
                    } }
                }
                item { DetailFold("Сравнить с действующими правилами") { StrategyDifference(active?.optJSONObject("config"), config) } }
                item { WorkspaceActionState(restoreVersion) }
                if (!validStrategy(config)) item { Text("Выберите обязательные параметры профиля; проверьте горизонт, резерв и лимиты. Черновик сохранён на устройстве.", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

private fun defaultStrategy(): JSONObject = JSONObject().put("goal", "preservation").put("horizon_months", 36)
    .put("reserve", JSONObject().put("amount", "0").put("currency", "RUB"))
    .put("limits", JSONObject().apply { limitTitles.keys.forEach { put(it, "100") } })
    .put("risk_level", "moderate").put("allowed_markets", JSONArray().put("MOEX"))

/** A restored draft remains editable while its server state reloads. */
internal data class StrategyEditorAvailability(val hasEditorState: Boolean, val operationBusy: Boolean) {
    val canEdit: Boolean get() = hasEditorState && !operationBusy

    fun editIfAllowed(update: () -> Unit) {
        if (canEdit) update()
    }
}

internal fun validStrategy(config: JSONObject): Boolean {
    val horizon = config.opt("horizon_months") as? Int ?: return false
    val amount = config.optJSONObject("reserve")?.optString("amount")?.toBigDecimalOrNull()
    val limits = config.optJSONObject("limits") ?: return false
    if (config.has("mandate") && (config.optJSONObject("mandate")?.let(::validPortfolioMandate) != true || config.optJSONObject("reserve")?.optString("currency") != "RUB")) return false
    return horizon in 1..600 && amount != null && amount.signum() >= 0 && limitTitles.keys.all {
        val number = limits.optString(it).toBigDecimalOrNull()
        number != null && number.signum() > 0 && number <= java.math.BigDecimal(100)
    }
}

@Composable
private fun StrategyGoalEditor(config: JSONObject, enabled: Boolean, edit: (JSONObject) -> Unit) {
    val choices = listOf("preservation", "income", "growth")
    SpectrumCard {
        WorkspaceChoices("Цель", listOf("Сохранение капитала", "Регулярные выплаты", "Рост капитала"),
            choices.indexOf(config.text("goal")).coerceAtLeast(0), enabled) { edit(JSONObject(config.toString()).put("goal", choices[it])) }
        val riskLevels = listOf("conservative", "moderate", "aggressive")
        WorkspaceChoices("Отношение к риску", listOf("Консервативное", "Умеренное", "Высокое"),
            riskLevels.indexOf(config.text("risk_level")).coerceAtLeast(0), enabled) { edit(JSONObject(config.toString()).put("risk_level", riskLevels[it])) }
        StrategyNumberChoice("Горизонт", config.opt("horizon_months")?.toString().orEmpty(), "мес.", enabled,
            "1", "600", listOf("12", "36", "60", "120"), listOf("1", "12")) {
            edit(JSONObject(config.toString()).put("horizon_months", it.toInt()))
        }
        Text("Выбор цели не добавляет ожидаемую прибыль к капиталу. Доступность инструмента проверяется у брокера.")
    }
}

@Composable
private fun StrategyReserveEditor(config: JSONObject, enabled: Boolean, edit: (JSONObject) -> Unit) {
    val reserve = config.getJSONObject("reserve")
    SpectrumCard {
        StrategyNumberChoice("Неприкосновенный резерв", reserve.text("amount", "0"), reserve.text("currency"), enabled,
            "0", "999999999999999.99", listOf("0", "1000", "10000", "100000"), listOf("1000", "100", "1", "0.01")) { amount ->
            edit(JSONObject(config.toString()).put("reserve", JSONObject(reserve.toString()).put("amount", amount)))
        }
        WorkspaceChoices("Валюта резерва", listOf("RUB", "USD", "EUR"), listOf("RUB", "USD", "EUR").indexOf(reserve.text("currency")).coerceAtLeast(0), enabled) {
            edit(JSONObject(config.toString()).put("reserve", JSONObject(reserve.toString()).put("currency", listOf("RUB", "USD", "EUR")[it])))
        }
        Text("Сервер проверит достаточность оценки в той же валюте. Значение 0 означает, что резерв в этих правилах не задан.")
    }
}

@Composable
private fun StrategyLimitEditor(title: String, key: String, config: JSONObject, enabled: Boolean, edit: (JSONObject) -> Unit) {
    val limits = config.getJSONObject("limits")
    SpectrumCard {
        StrategyNumberChoice(title, limits.text(key, "100"), "%", enabled, "0.01", "100",
            listOf("1", "3", "5", "8", "10", "20", "100"), listOf("1", "0.1", "0.01"), true) { percent ->
            edit(JSONObject(config.toString()).put("limits", JSONObject(limits.toString()).put(key, percent)))
        }
        Text("Ограничение применяется к подтверждённой доле. 100% не ограничивает эту долю; неизвестные связи не считаются нулём.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun StrategyDifference(before: JSONObject?, after: JSONObject) {
    if (before == null) Text("До подтверждения активной версии нет.")
    listOf("goal", "horizon_months", "risk_level").forEach { field ->
        val label = when (field) { "goal" -> "Цель"; "horizon_months" -> "Горизонт, месяцев"; else -> "Профиль риска" }
        if (before?.opt(field) != after.opt(field)) Text(label + ": " + strategyValue(before?.text(field, UNSPECIFIED_VALUE)) + " → " + strategyValue(after.text(field)))
    }
    val oldLimits = before?.optJSONObject("limits")
    val newLimits = after.optJSONObject("limits")
    limitTitles.forEach { (key, label) -> if (oldLimits?.opt(key) != newLimits?.opt(key)) Text(label + ": " + (oldLimits?.text(key) ?: UNSPECIFIED_VALUE) + " → " + (newLimits?.text(key) ?: UNSPECIFIED_VALUE) + "%") }
    Text("Резерв: " + PrivateValue(moneyText(before?.optJSONObject("reserve"))) + " → " + PrivateValue(moneyText(after.optJSONObject("reserve"))))
}

private fun strategyValue(value: String?): String = when (value) {
    "preservation" -> "Сохранение"; "income" -> "Выплаты"; "growth" -> "Рост"; "moderate" -> "Умеренный"
    "conservative" -> "Консервативный"; "aggressive" -> "Высокий"; else -> value ?: UNSPECIFIED_VALUE
}

@Composable
private fun StrategyHistoryCard(old: JSONObject, active: JSONObject?, loaded: Boolean,
    editor: StrategyEditorAvailability, version: Int, previewAction: WorkspaceAction) {
    SpectrumCard {
        Text("Версия " + old.optInt("version"), style = MaterialTheme.typography.titleMedium)
        Text(localMoment(old.text("confirmed_at", "")), style = MaterialTheme.typography.bodySmall)
        val previous = old.optJSONObject("config") ?: JSONObject()
        StrategyDifference(active?.optJSONObject("config"), previous)
        SpectrumSecondaryButton("Проверить возврат к этой версии", {
            if (loaded && editor.canEdit) previewAction.perform("/workspace/strategy/preview", JSONObject().put("expected_version", version)
                .put("rollback_to_version", old.optInt("version")))
        }, Modifier.fillMaxWidth(), loaded && editor.canEdit)
    }
}
