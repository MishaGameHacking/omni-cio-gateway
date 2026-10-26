package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import org.json.JSONArray
import org.json.JSONObject
import java.math.BigDecimal
import ru.omnicio.app.ui.spectrum.*

private val scenarioAxes = listOf("all", "currency", "sector", "country", "instrument")
private val scenarioLabels = listOf("Весь портфель", "Валюта инструмента", "Отрасль", "Страна риска", "Инструмент")

private fun scenarioDraft(id: String) = JSONObject().put("id", id).put("title", "Сценарий " + id)
    .put("axis", "all").put("target", "").put("percent", "")

@Composable
fun RiskScenarioDialog(risks: JSONObject?, onClose: () -> Unit) {
    var draftsText by rememberSaveable { mutableStateOf(JSONArray().put(scenarioDraft("A")).put(scenarioDraft("B")).toString()) }
    var selected by rememberSaveable { mutableIntStateOf(0) }
    var result by remember { mutableStateOf<JSONObject?>(null) }
    val action = rememberWorkspaceAction { result = it }
    val drafts = remember(draftsText) { JSONArray(draftsText).let { rows -> (0 until rows.length()).map { rows.getJSONObject(it) } } }
    val current = drafts[selected.coerceIn(drafts.indices)]
    val currency = LocalWorkspaceSnapshot.current?.text("currency", "RUB") ?: "RUB"
    val edit: (String, String) -> Unit = { field, value ->
        if (!action.busy) {
            val copy = JSONArray(draftsText)
            copy.getJSONObject(selected).put(field, value)
            if (field == "axis") copy.getJSONObject(selected).put("target", "")
            draftsText = copy.toString(); result = null
        }
    }
    WorkspaceDialog("Сравнение ваших сценариев", onClose) {
        Text("Задайте 2–4 гипотезы. Сервер рассчитает их на одном снимке портфеля и в одной валюте. Проценты задаёте вы; расчёт не является прогнозом.")
        WorkspaceChoices("Редактируемый сценарий", drafts.map { it.text("title") }, selected) { selected = it }
        WorkspaceTextInput(current.text("title"), { edit("title", it.take(80)) }, "Название сценария", Modifier.fillMaxWidth(), enabled = !action.busy)
        WorkspaceChoices("Область изменения", scenarioLabels, scenarioAxes.indexOf(current.text("axis")).coerceAtLeast(0)) { edit("axis", scenarioAxes[it]) }
        if (current.text("axis") != "all") {
            val axis = current.text("axis")
            val candidates = risks?.records("concentrations").orEmpty().filter {
                it.text("direction") == axis || (axis == "instrument" && it.text("direction") == "position")
            }.distinctBy { it.text("id") }
            WorkspaceChoicePicker("Объект сценария", current.text("target", ""),
                candidates.map { WorkspaceSuggestion(it.text("id"), it.text("label")) }, !action.busy) { edit("target", it) }
            DetailFold("Точный код из источника") {
                WorkspaceTextInput(current.text("target", ""), { edit("target", it.take(160)) }, "Код из источника или UID инструмента", Modifier.fillMaxWidth(), enabled = !action.busy)
            }
        }
        WorkspaceTextInput(current.text("percent", ""), { edit("percent", it.replace(',', '.').replace('−', '-').take(12)) },
            "Предположение, % (от −100 до 1000)", Modifier.fillMaxWidth().testTag("scenario-percent"), enabled = !action.busy, keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        if (drafts.size < 4) SpectrumSecondaryButton("Добавить сценарий", {
            val id = ('A'..'D').first { letter -> drafts.none { it.text("id") == letter.toString() } }.toString()
            draftsText = JSONArray(draftsText).put(scenarioDraft(id)).toString(); selected = drafts.size; result = null
        }, Modifier.fillMaxWidth(), !action.busy)
        if (drafts.size > 2) SpectrumSecondaryButton("Убрать этот сценарий", {
            draftsText = JSONArray(drafts.filterIndexed { index, _ -> index != selected }).toString()
            selected = 0; result = null
        }, Modifier.fillMaxWidth(), !action.busy)
        SpectrumPrimaryButton("Сравнить сценарии", {
            val variants = JSONArray(drafts.map { draft -> JSONObject().put("id", draft.text("id")).put("title", draft.text("title"))
                .put("shocks", JSONArray().put(JSONObject().put("axis", draft.text("axis"))
                    .put("id", if (draft.text("axis") == "all") "all" else draft.text("target").trim()).put("percent", draft.text("percent")))) })
            action.perform("/workspace/risks/scenarios/compare", JSONObject().put("currency", currency).put("scenarios", variants))
        }, Modifier.fillMaxWidth(), !action.busy && drafts.all(::validScenarioDraft), SpectrumSymbol.Risk)
        WorkspaceActionState(action)
        result?.let { comparison ->
            Text("Сравнение в " + comparison.text("currency") + " · " + localMoment(comparison.text("as_of", "")), style = MaterialTheme.typography.titleMedium)
            comparison.records("scenarios").forEach { variant ->
                val answer = variant.optJSONObject("result") ?: JSONObject()
                SpectrumCard(Modifier.testTag("scenario-result-" + variant.text("id"))) {
                    Text(variant.text("title"), style = MaterialTheme.typography.titleLarge)
                    answer.records("assumptions").forEach { assumption ->
                        val axis = assumption.text("axis")
                        Text(scenarioLabels[scenarioAxes.indexOf(axis).coerceAtLeast(0)] +
                            (if (axis == "all") "" else " · " + assumption.text("id")) + ": " + assumption.text("percent") + "%")
                    }
                    Text("Исходный капитал: " + PrivateValue(moneyText(answer.optJSONObject("baseline"))))
                    Text("Изменение оценённых позиций: " + PrivateValue(moneyText(answer.optJSONObject("estimated_change"))))
                    Text("После сценария: " + PrivateValue(moneyText(answer.optJSONObject("estimated_after"))))
                    Text("Изменение применено к " + answer.optInt("covered_positions") + " из " + answer.optInt("total_positions") + " позиций")
                    val unknown = answer.strings("uncovered_instrument_uids")
                    if (unknown.isNotEmpty()) Text("Для " + unknown.size + " инструментов не хватает проверенной оценки или модели расчёта. Полный итог не подтверждён.")
                    if (!answer.optBoolean("complete")) Text("Расчёт неполный. Показанное изменение относится только к оценённым позициям; итог всего портфеля не подтверждён.")
                    Text("Оценка линейная: курсовые эффекты и модель производных инструментов не добавляются. Позиции за пределами выбранной области сохраняют текущую оценку.", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        SpectrumSecondaryButton("Закрыть", onClose, Modifier.fillMaxWidth())
    }
}

private fun validScenarioDraft(draft: JSONObject): Boolean {
    val percent = draft.text("percent", "").toBigDecimalOrNull() ?: return false
    return draft.text("title", "").isNotBlank() && percent >= BigDecimal(-100) && percent <= BigDecimal(1000) &&
        (draft.text("axis") == "all" || draft.text("target", "").isNotBlank())
}
