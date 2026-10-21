package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

private const val riskChecksPath = "/workspace/risks/checks"

@Composable
fun RiskWorkspaceScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/risks")
    val checks = rememberWorkspaceResource(riskChecksPath)
    val events = rememberWorkspaceResource("/workspace/risks/events?limit=100")
    val navigate = LocalWorkspaceNavigator.current
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var scenario by rememberSaveable { mutableStateOf(false) }
    val create = rememberWorkspaceAction { checks.refresh(); tab = 2 }
    WorkspaceDetailPage("Риски", "Покрытие, лимиты и проверяемые действия", onBack, SpectrumSymbol.Risk) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            SpectrumTabs(listOf("Карта", "Концентрация", "Проверки", "История"), tab, { tab = it }, Modifier.padding(horizontal = 16.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item { WorkspaceRequestState(resource); WorkspaceActionState(create) }
                if (tab <= 1) item { SpectrumCard {
                    Text("По снимку: " + (resource.data?.text("as_of", "Время не получено")?.let(::localMoment) ?: "Время не получено"))
                    Text("Версия правил: " + (resource.data?.optInt("strategy_version") ?: 0))
                    SpectrumSecondaryButton("Изменить лимиты", { navigate(WorkspaceRoute.Strategies) }, Modifier.fillMaxWidth())
                    SpectrumSecondaryButton("Рассчитать свой сценарий", { scenario = true }, Modifier.fillMaxWidth(), resource.data?.isNull("snapshot_id") == false)
                } }
                if (tab == 0 && resource.data != null && resource.data.records("coverage").isEmpty() && !resource.busy) item {
                    WorkspaceEmpty("Покрытие пока не получено", "Обновите снимок портфеля, чтобы проверить источники и действующие ограничения.", "Обновить", LocalWorkspaceRefresh.current)
                }
                if (tab == 1 && resource.data != null && resource.data.records("concentrations").isEmpty() && !resource.busy) item {
                    WorkspaceEmpty("Концентрации пока не рассчитаны", "Для расчёта нужны подтверждённые позиции и оценки. Отсутствие результата не означает отсутствие риска.")
                }
                when (tab) {
                    0 -> resource.data?.records("coverage").orEmpty().forEach { axis -> item(key = axis.text("direction")) { RiskCoverageCard(axis) } }
                    1 -> resource.data?.records("concentrations").orEmpty().sortedWith(compareByDescending<JSONObject> { it.optBoolean("breached") }.thenBy { it.text("label") }).forEach { concentration -> item(key = concentration.text("direction") + ":" + concentration.text("id")) {
                        RiskConcentrationCard(concentration, create)
                    } }
                    2 -> {
                        item { WorkspaceRequestState(checks) }
                        if (checks.data?.records("items").isNullOrEmpty() && !checks.busy) item { WorkspaceEmpty("Проверок пока нет", "Создайте проверку из концентрации или события. Отметка шага означает, что вы изучили его, и не означает сделку.") }
                        checks.data?.records("items").orEmpty().forEach { check -> item(key = check.text("id")) { RiskCheck(check, checks.refresh) } }
                    }
                    else -> {
                        item { WorkspaceRequestState(events) }
                        if (events.data?.records("items").isNullOrEmpty() && !events.busy) item { WorkspaceEmpty("Изменений пока не записано", "После новой проверки здесь появятся подтверждённые изменения лимитов и источники.") }
                        events.data?.records("items").orEmpty().forEach { event -> item(key = event.text("id")) { RiskHistoryCard(event, create) } }
                    }
                }
            }
        }
    }
    if (scenario) RiskScenarioDialog(resource.data) { scenario = false }
}

@Composable
private fun RiskCheck(check: JSONObject, onChanged: () -> Unit) {
    val action = rememberWorkspaceAction { onChanged() }
    val navigate = LocalEvidenceNavigator.current
    SpectrumCard {
        Text(check.text("title", "Проверка риска"), style = MaterialTheme.typography.titleLarge)
        Text("Изучение оснований · торговое поручение не создаётся", style = MaterialTheme.typography.bodySmall)
        check.optJSONObject("basis")?.let { basis -> DetailFold("Снимок и затронутые позиции") {
            Text("Наблюдение от " + localMoment(basis.text("as_of", "")))
            Text("Версия правил: " + basis.optInt("strategy_version"))
            basis.records("positions").forEach { position ->
                Text(position.text("title", "Инструмент"), style = MaterialTheme.typography.titleSmall)
                Text("Количество: " + PrivateValue(position.text("quantity")))
                Text("Оценка: " + PrivateValue(moneyText(position.optJSONObject("value"))))
                SpectrumSecondaryButton("Показать подтверждённую позицию", {
                    navigate(EvidenceTarget("instrument", position.text("instrument_uid"), accountId = position.text("account_id", "").takeIf(String::isNotBlank)))
                }, Modifier.fillMaxWidth())
            }
            basis.optJSONObject("event")?.let { event ->
                Text(event.text("title", "Событие риска"))
                Text(localMoment(event.text("occurred_at", event.text("created_at", ""))))
            }
            EvidenceLinks(check.records("sources"))
        } }
        check.records("steps").forEach { step -> WorkspaceToggle(step.text("title"), "Отметка о вашем просмотре", step.text("state") == "reviewed",
            Modifier.testTag("risk-check-${check.text("id")}-step-${step.text("id")}")) { reviewed ->
            action.perform(riskChecksPath + "/" + VolumeWorkspaceClient.encode(check.text("id")),
                JSONObject().put("step_id", step.text("id")).put("state", if (reviewed) "reviewed" else "pending"), "PATCH")
        } }
        WorkspaceActionState(action)
    }
}

@Composable
private fun RiskEventObservation(label: String, value: JSONObject?, kind: String) {
    if (value == null) return
    if (kind.startsWith("risk_rating")) {
        DetailFold(label + " · кредитное основание") {
            Text(if (value.text("state") == "available") "Проверенные сведения" else "Сведения требуют проверки")
            value.records("items").forEach { rating ->
                Text(rating.text("agency") + " · " + rating.text("grade"), style = MaterialTheme.typography.titleSmall)
                Text("Шкала: " + rating.text("scale") + "; объект: " + when (rating.text("subject_kind")) { "issue" -> "выпуск"; "issuer" -> "эмитент"; else -> rating.text("subject_kind") })
                Text("Статус: " + rating.text("status") + "; прогноз: " + rating.text("outlook"))
            }
            value.strings("warnings").forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
    } else {
        Text(label + ": " + if (value.isNull("share_percent")) "Доля не подтверждена" else PrivateValue(value.text("share_percent") + "%"))
        if (!value.isNull("limit_percent")) Text("Лимит: " + value.text("limit_percent") + "%", style = MaterialTheme.typography.bodySmall)
    }
}

internal fun riskDirection(direction: String): String = when (direction) {
    "position", "instrument" -> "Отдельные позиции"; "issuer", "company" -> "Компании"; "group" -> "Связанные группы"
    "sector" -> "Отрасли"; "currency" -> "Валюты"; "country" -> "Страны"; "rating", "ratings" -> "Кредитное качество"
    "liquidity" -> "Ликвидность"; "trading" -> "Доступность торгов"; else -> direction.take(100)
}

@Composable
private fun RiskCoverageCard(axis: JSONObject) {
    val evidence = LocalEvidenceNavigator.current
    SpectrumCard {
                            val complete = axis.text("state") == "available"
                            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                SpatialIcon("risk", Modifier.size(40.dp), state = if (complete) SpatialState.Idle else SpatialState.Attention)
                                Column { Text(riskDirection(axis.text("direction")), style = MaterialTheme.typography.titleLarge)
                                    Text("Подтверждено " + axis.optInt("known_positions") + " из " + axis.optInt("total_positions") + " позиций") }
                            }
                            Text(if (complete) "Источники этого направления получены. Само по себе это не означает низкий риск." else "Покрытие неполное: неизвестные сведения не считаются безопасными.")
                            Text(axis.text("basis", "Основание не получено"), style = MaterialTheme.typography.bodySmall)
                            axis.strings("missing_instrument_uids").forEach { uid -> SpectrumSecondaryButton("Проверить инструмент · " + uid.take(8), { evidence(EvidenceTarget("instrument", uid)) }, Modifier.fillMaxWidth()) }
                        }
}

@Composable
private fun RiskConcentrationCard(concentration: JSONObject, create: WorkspaceAction) {
    val evidence = LocalEvidenceNavigator.current
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
                                    create.perform(riskChecksPath, JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", "Проверить: " + concentration.text("label"))
                                        .put("instrument_uids", concentration.optJSONArray("instrument_uids") ?: JSONArray()))
                                }, Modifier.fillMaxWidth(), !create.busy)
                            }
}

@Composable
private fun RiskHistoryCard(event: JSONObject, create: WorkspaceAction) {
    SpectrumCard {
                                Text(event.text("title", "Изменение риска"), style = MaterialTheme.typography.titleMedium)
                                Text(localMoment(event.text("occurred_at", event.text("created_at", ""))))
                                val details = event.optJSONObject("details")
                                RiskEventObservation("Было", details?.optJSONObject("before"), event.text("kind", ""))
                                RiskEventObservation("Стало", details?.optJSONObject("after"), event.text("kind", ""))
                                if (event.text("kind").endsWith("data_stale")) Text("Новых подтверждённых данных недостаточно. Это событие не означает, что риск устранён.")
                                EvidenceLinks(event.records("sources").ifEmpty { event.strings("source_ids").map { JSONObject().put("source_id", it).put("as_of", event.text("occurred_at", "")) } })
                                SpectrumSecondaryButton("Подготовить проверку события", {
                                    create.perform(riskChecksPath, JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", event.text("title", "Проверить событие"))
                                        .put("event_id", event.text("id")).put("instrument_uids", event.optJSONArray("instrument_uids") ?: JSONArray()))
                                }, Modifier.fillMaxWidth(), !create.busy)
                            }
}
