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
    val allocation = resource.data?.optJSONObject("allocation")
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
    val requestExit: (() -> Unit) -> Unit = { proceed -> proceed() }
    RegisterPanelExit(WorkspaceRoute.Strategies, requestExit)
    SpatialBackHandler(onBack = onBack)
    WorkspaceDetailPage("Моя стратегия", "Цель, понятные настройки и действия по портфелю", onBack, SpectrumSymbol.Strategy,
        adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            if (!compact || !WindowInsets.isImeVisible) SpectrumTabs(listOf("Стратегия", "Настройки", "План"), tab, { tab = it }, Modifier.padding(horizontal = 20.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = if (compact) 0.dp else 20.dp),
                verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item {
                    WorkspaceRequestState(resource)
                    Text("Профиль портфеля",
                        style = MaterialTheme.typography.labelLarge)
                    AutoSaveStatus(record) { auto?.retry(AutoSaveKind.Strategy) }
                }
                when (tab) {
                    0 -> {
                        if (active?.optJSONObject("config")?.has("construction") == true) item {
                            StrategyAllocationSummary(allocation)
                        }
                        item { StrategyProfilesPanel(resource.data?.optJSONObject("profiles"), config,
                            editor.canEdit, { next -> edit(next); tab = 1 }, edit) }
                    }
                    1 -> {
                        item { StrategySimpleSettings(config, resource.data?.records("available_accounts").orEmpty(),
                            editor.canEdit, edit) }
                    }
                    else -> item { StrategyActionPlanPanel() }
                }
                if (!validStrategy(config)) item {
                    SpectrumCard {
                        Text("Завершите настройку", style = MaterialTheme.typography.titleMedium)
                        strategyValidationIssues(config).forEach { Text(it, color = MaterialTheme.colorScheme.error) }
                        SpectrumSecondaryButton("Открыть параметры", { tab = 1 }, Modifier.fillMaxWidth())
                    }
                }
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

internal fun strategyValidationIssues(config: JSONObject): List<String> = buildList {
    val horizon = config.opt("horizon_months") as? Int
    if (horizon == null || horizon !in 1..600) add("Горизонт: укажите от 1 до 600 месяцев.")
    val reserve = config.optJSONObject("reserve")
    val amount = reserve?.optString("amount")?.toBigDecimalOrNull()
    if (amount == null || amount.signum() < 0) add("Резерв: укажите сумму от нуля.")
    addAll(strategyLimitIssues(config.optJSONObject("limits")))
    if (config.has("mandate")) {
        addAll(strategyMandateIssues(config.optJSONObject("mandate")))
        if (reserve?.optString("currency") != "RUB") add("Для инвестиционного профиля выберите резерв в RUB.")
    }
}

private fun strategyLimitIssues(limits: JSONObject?): List<String> =
    limitTitles.mapNotNull { (key, title) ->
        val number = limits?.optString(key)?.toBigDecimalOrNull()
        if (number == null || number.signum() <= 0 || number > java.math.BigDecimal(100))
            "$title: лимит должен быть больше 0 и не больше 100%."
        else null
    }

private fun mandatePercentIssues(mandate: JSONObject): List<String> {
    val labels = mapOf("loss_capacity_percent" to "Допустимый убыток", "bond_target_percent" to "Доля облигаций",
        "share_target_percent" to "Доля акций", "max_discretionary_turnover_percent" to "Предел оборота",
        "max_trade_cost_percent" to "Предел издержек")
    return labels.mapNotNull { (key, label) ->
        val number = mandate.optString(key).toBigDecimalOrNull()
        if (number == null || number < java.math.BigDecimal.ZERO || number > java.math.BigDecimal(100))
            "$label: укажите значение от 0 до 100%."
        else null
    }
}

private fun mandateChoiceIssues(mandate: JSONObject): List<String> = buildList {
    listOf(Triple("minimum_rating_level", "Минимальный рейтинг", 0..9),
        Triple("turnover_window_days", "Период учёта оборота", 1..366),
        Triple("rebalance_cooldown_days", "Пауза между перераспределениями", 0..365)).forEach { (key, label, range) ->
        val number = mandate.opt(key) as? Int
        if (number == null || number !in range) add("$label: выберите допустимое значение.")
    }
    if (mandate.opt("reinvest_coupons") !is Boolean) add("Купоны: выберите способ использования.")
    if (mandate.opt("reinvest_dividends") !is Boolean) add("Дивиденды: выберите способ использования.")
}

private fun strategyMandateIssues(mandate: JSONObject?): List<String> = buildList {
    if (mandate == null) {
        add("Инвестиционный профиль: выберите состав и счёт.")
        return@buildList
    }
    if (mandate.optString("account_id").isBlank()) add("Счёт: выберите подключённый счёт.")
    addAll(mandatePercentIssues(mandate))
    addAll(mandateChoiceIssues(mandate))
    if (!validPortfolioMandate(mandate) && isEmpty())
        add("Проверьте состав портфеля, сумму долей 100% и основную сессию.")
}

internal fun validStrategy(config: JSONObject): Boolean = strategyValidationIssues(config).isEmpty()

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
    if (before?.optJSONObject("reserve")?.toString() != after.optJSONObject("reserve")?.toString())
        Text("Резерв: " + PrivateValue(moneyText(before?.optJSONObject("reserve"))) + " → " + PrivateValue(moneyText(after.optJSONObject("reserve"))))
}

private fun strategyValue(value: String?): String = when (value) {
    "preservation" -> "Сохранение"; "income" -> "Выплаты"; "growth" -> "Рост"; "moderate" -> "Умеренный"
    "conservative" -> "Консервативный"; "aggressive" -> "Высокий"; else -> value ?: UNSPECIFIED_VALUE
}

