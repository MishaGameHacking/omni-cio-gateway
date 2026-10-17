package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

@Composable
fun RiskWorkspaceScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/risks")
    val checks = rememberWorkspaceResource("/workspace/risks/checks")
    val events = rememberWorkspaceResource("/workspace/risks/events?limit=100")
    val navigate = LocalWorkspaceNavigator.current
    val evidence = LocalEvidenceNavigator.current
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var scenario by remember { mutableStateOf(false) }
    val create = rememberWorkspaceAction { checks.refresh(); tab = 2 }
    WorkspaceDetailPage("Риски", "Покрытие, лимиты и проверяемые действия", onBack, SpectrumSymbol.Risk) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            SpectrumTabs(listOf("Карта", "Концентрация", "Проверки", "История"), tab, { tab = it }, Modifier.padding(horizontal = 16.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item { WorkspaceRequestState(resource); WorkspaceActionState(create) }
                if (tab <= 1) item { SpectrumCard {
                    Text("По снимку: " + (resource.data?.text("as_of", "Время не получено")?.let(::localMoment) ?: "Время не получено"))
                    Text("Версия правил: " + (resource.data?.optInt("strategy_version") ?: 0))
                    SpectrumSecondaryButton("Изменить лимиты", { navigate(WorkspaceRoute.Strategies) }, Modifier.fillMaxWidth())
                    SpectrumSecondaryButton("Рассчитать свой сценарий", { scenario = true }, Modifier.fillMaxWidth(), resource.data?.isNull("snapshot_id") == false)
                } }
                when (tab) {
                    0 -> resource.data?.records("coverage").orEmpty().forEach { axis -> item(key = axis.text("direction")) { SpectrumCard {
                        val complete = axis.text("state") == "available"
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            SpatialIcon("risk", Modifier.size(40.dp), state = if (complete) SpatialState.Idle else SpatialState.Attention)
                            Column { Text(riskDirection(axis.text("direction")), style = MaterialTheme.typography.titleLarge)
                                Text("Подтверждено " + axis.optInt("known_positions") + " из " + axis.optInt("total_positions") + " позиций") }
                        }
                        Text(if (complete) "Источники этого направления получены. Само по себе это не означает низкий риск." else "Покрытие неполное: неизвестные сведения не считаются безопасными.")
                        Text(axis.text("basis", "Основание не получено"), style = MaterialTheme.typography.bodySmall)
                        axis.strings("missing_instrument_uids").forEach { uid -> SpectrumSecondaryButton("Проверить инструмент · " + uid.take(8), { evidence(EvidenceTarget("instrument", uid)) }, Modifier.fillMaxWidth()) }
                    } } }
                    1 -> resource.data?.records("concentrations").orEmpty().sortedWith(compareByDescending<JSONObject> { it.optBoolean("breached") }.thenBy { it.text("label") }).forEach { concentration -> item(key = concentration.text("direction") + ":" + concentration.text("id")) {
                        SpectrumCard(emphasized = concentration.optBoolean("breached")) {
                            Text(concentration.text("label"), style = MaterialTheme.typography.titleLarge)
                            Text(riskDirection(concentration.text("direction")), style = MaterialTheme.typography.labelMedium)
                            Text(PrivateValue(concentration.text("share_percent", "Доля не получена") + if (!concentration.isNull("share_percent")) "%" else ""), style = MaterialTheme.typography.headlineSmall)
                            Text("Лимит: " + concentration.text("limit_percent", "Не задан") + if (!concentration.isNull("limit_percent")) "%" else "")
                            Text(if (concentration.isNull("breached")) "Сопоставление с лимитом не подтверждено" else if (concentration.optBoolean("breached")) "Лимит превышен" else "В пределах заданного лимита")
                            val share = concentration.optString("share_percent").toFloatOrNull()
                            if (share != null) SpectrumProgressBar((share / 100f).coerceIn(0f, 1f), accent = if (concentration.optBoolean("breached")) LocalSpectrumPalette.current.rose else LocalSpectrumPalette.current.cyan)
                            DetailFold("Какие позиции входят") { concentration.strings("instrument_uids").forEach { uid ->
                                SpectrumSecondaryButton("Открыть позицию · " + uid.take(8), { evidence(EvidenceTarget("instrument", uid)) }, Modifier.fillMaxWidth())
                            } }
                            SpectrumSecondaryButton("Создать список проверок", {
                                create.perform("/workspace/risks/checks", JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", "Проверить: " + concentration.text("label"))
                                    .put("instrument_uids", concentration.optJSONArray("instrument_uids") ?: JSONArray()))
                            }, Modifier.fillMaxWidth(), !create.busy)
                        }
                    } }
                    2 -> {
                        item { WorkspaceRequestState(checks) }
                        if (checks.data?.records("items").isNullOrEmpty() && !checks.busy) item { WorkspaceEmpty("Проверок пока нет", "Создайте проверку из концентрации или события. Отметка шага означает, что вы изучили его, и не означает сделку.") }
                        checks.data?.records("items").orEmpty().forEach { check -> item(key = check.text("id")) { RiskCheck(check, checks.refresh) } }
                    }
                    else -> {
                        item { WorkspaceRequestState(events) }
                        if (events.data?.records("items").isNullOrEmpty() && !events.busy) item { WorkspaceEmpty("Изменений пока не записано", "После новой проверки здесь появятся подтверждённые изменения лимитов и источники.") }
                        events.data?.records("items").orEmpty().forEach { event -> item(key = event.text("id")) { SpectrumCard {
                            Text(event.text("title", "Изменение риска"), style = MaterialTheme.typography.titleMedium)
                            Text(localMoment(event.text("occurred_at", event.text("created_at", ""))))
                            val details = event.optJSONObject("details")
                            details?.optJSONObject("before")?.let { Text("Было: " + PrivateValue(it.text("share_percent") + "%")) }
                            details?.optJSONObject("after")?.let { Text("Стало: " + PrivateValue(it.text("share_percent") + "%")) }
                            EvidenceLinks(event.strings("source_ids").map { JSONObject().put("source_id", it).put("as_of", event.text("occurred_at", "")) })
                            SpectrumSecondaryButton("Подготовить проверку события", {
                                create.perform("/workspace/risks/checks", JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", event.text("title", "Проверить событие"))
                                    .put("event_id", event.text("id")).put("instrument_uids", event.optJSONArray("instrument_uids") ?: JSONArray()))
                            }, Modifier.fillMaxWidth(), !create.busy)
                        } } }
                    }
                }
            }
        }
    }
    if (scenario) RiskScenarioDialog { scenario = false }
}

@Composable
private fun RiskCheck(check: JSONObject, onChanged: () -> Unit) {
    val action = rememberWorkspaceAction { onChanged() }
    SpectrumCard {
        Text(check.text("title", "Проверка риска"), style = MaterialTheme.typography.titleLarge)
        Text("Изучение оснований · торговое поручение не создаётся", style = MaterialTheme.typography.bodySmall)
        check.records("steps").forEach { step -> WorkspaceToggle(step.text("title"), "Отметка о вашем просмотре", step.text("state") == "reviewed") { reviewed ->
            action.perform("/workspace/risks/checks/" + VolumeWorkspaceClient.encode(check.text("id")),
                JSONObject().put("step_id", step.text("id")).put("state", if (reviewed) "reviewed" else "pending"), "PATCH")
        } }
        WorkspaceActionState(action)
    }
}

@Composable
private fun RiskScenarioDialog(onClose: () -> Unit) {
    var axis by rememberSaveable { mutableIntStateOf(0) }
    var id by rememberSaveable { mutableStateOf("") }
    var percent by rememberSaveable { mutableStateOf("") }
    var result by remember { mutableStateOf<JSONObject?>(null) }
    val action = rememberWorkspaceAction { result = it }
    val axes = listOf("all", "currency", "sector", "country", "instrument")
    WorkspaceDialog("Ваш сценарий изменения цен", onClose) {
        Text("Задайте гипотезу. Результат — арифметическая оценка выбранного изменения на снимке портфеля; это не прогноз доходности.")
        WorkspaceChoices("Область", listOf("Весь портфель", "Валюта", "Отрасль", "Страна", "Инструмент"), axis) { axis = it; result = null }
        if (axis > 0) WorkspaceTextInput(id, { id = it.take(160); result = null }, "Код из источника или UID инструмента", Modifier.fillMaxWidth(), enabled = !action.busy)
        WorkspaceTextInput(percent, { percent = it.replace(',', '.').take(12); result = null }, "Предположение, % (можно со знаком −)", Modifier.fillMaxWidth(), enabled = !action.busy,
            keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        val value = percent.replace('−', '-').toBigDecimalOrNull()
        SpectrumPrimaryButton("Рассчитать влияние", { action.perform("/workspace/risks/scenario", JSONObject().put("shocks", JSONArray().put(JSONObject()
            .put("axis", axes[axis]).put("id", if (axis == 0) "all" else id.trim()).put("percent", value.toString())))) }, Modifier.fillMaxWidth(),
            !action.busy && value != null && value >= java.math.BigDecimal(-100) && value <= java.math.BigDecimal(1000) && (axis == 0 || id.isNotBlank()))
        WorkspaceActionState(action)
        result?.let { answer ->
            Text("До сценария: " + PrivateValue(moneyText(answer.optJSONObject("baseline"))))
            Text("Изменение: " + PrivateValue(moneyText(answer.optJSONObject("estimated_change"))))
            Text("После сценария: " + PrivateValue(moneyText(answer.optJSONObject("estimated_after"))))
            Text("Покрыто " + answer.optInt("covered_positions") + " из " + answer.optInt("total_positions") + " позиций")
            answer.strings("assumptions").forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            Text("По состоянию на " + localMoment(answer.text("as_of", "")))
        }
        SpectrumSecondaryButton("Закрыть", onClose, Modifier.fillMaxWidth())
    }
}

internal fun riskDirection(direction: String): String = when (direction) {
    "position", "instrument" -> "Отдельные позиции"; "issuer", "company" -> "Компании"; "group" -> "Связанные группы"
    "sector" -> "Отрасли"; "currency" -> "Валюты"; "country" -> "Страны"; "rating" -> "Кредитное качество"
    "liquidity" -> "Ликвидность"; else -> direction.take(100)
}
