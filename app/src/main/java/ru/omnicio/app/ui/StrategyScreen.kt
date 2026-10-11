package ru.omnicio.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import kotlin.math.roundToInt

@Composable
internal fun StrategySettings(state: AppUiState, model: OmnicioViewModel) {
    val strategy = state.strategy
    OmniCard {
        SectionTitle("Стратегия")
        Text("Выберите подход для анализа портфеля. Будущая прибыль не гарантируется.")
        OutlinedButton(onClick = model::loadStrategy, enabled = !state.busy) {
            Text(if (strategy.loaded) "Загрузить сохранённые условия" else "Загрузить стратегии")
        }
        if (state.amountsHidden) Text("Условия скрыты вместе с суммами.")
        else strategy.catalog?.let { StrategyEditor(strategy, state.busy, model) }
    }
}

@Composable
private fun StrategyEditor(state: StrategyUiState, busy: Boolean, model: OmnicioViewModel) {
    val catalog = state.catalog ?: return
    val saved = state.selection?.optJSONObject("document")
    val presets = catalog.getJSONArray("presets").objects()
    var document by remember(state) { mutableStateOf(saved?.let { JSONObject(it.toString()) }) }
    var intent by remember(state) { mutableStateOf("edit") }
    var showCustom by remember(state) { mutableStateOf(saved?.optBoolean("customized") == true) }
    presets.forEach { preset ->
        val selected = !showCustom && document?.text("base_preset_id") == preset.getString("id")
        FilterChip(selected, onClick = {
            document = strategyTemplate(preset.getJSONObject("document"), document)
            intent = "select"
            showCustom = false
        }, label = { Text(preset.getString("title")) }, enabled = !busy)
    }
    FilterChip(showCustom, onClick = {
        val base = state.selection?.optJSONObject("custom_document") ?: document
            ?: presets.first { it.getString("id") == catalog.getJSONObject("custom").getString("base_id") }
                .getJSONObject("document")
        document = JSONObject(base.toString()).put("customized", true)
        intent = "edit"
        showCustom = true
    }, label = { Text(catalog.getJSONObject("custom").getString("title")) }, enabled = !busy)
    document?.let { current ->
        val preset = presets.find { it.getString("id") == current.getString("base_preset_id") }
        Text(preset?.getString("description") ?: "Сохранённый подход из предыдущей версии")
        preset?.let { Text(it.getString("risk"), style = MaterialTheme.typography.bodySmall) }
        Text("Доли ниже — выбранные условия, а не прогноз доходности.", style = MaterialTheme.typography.bodySmall)
        if (showCustom) CustomStrategyForm(current, busy) {
            document = it
            intent = "edit"
        } else allocationLabels.forEach { (key, title) ->
            MetricRow(title, "${current.getJSONObject("allocation").getInt(key)} %")
        }
        Text("Сохранение меняет рабочую стратегию для проверки портфеля. Торговые рекомендации пока не включены.",
            style = MaterialTheme.typography.bodySmall)
        Button(onClick = { model.saveStrategy(JSONObject(current.toString()), intent) },
            enabled = !busy && strategyAllocationValid(current)) { Text("Сохранить на сервере") }
    }
    if (saved != null) {
        Text("На сервере: версия ${state.version} · ${timestampLabel(state.selection?.text("updated_at"))}",
            style = MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick = model::assessStrategy, enabled = !busy) { Text("Проверить сохранённую стратегию по счёту") }
    }
    state.assessment?.let { StrategyAssessment(it) }
}

@Composable
private fun CustomStrategyForm(document: JSONObject, busy: Boolean, onChange: (JSONObject) -> Unit) {
    allocationLabels.forEach { (key, title) ->
        val value = document.getJSONObject("allocation").getInt(key)
        Text("$title: $value %")
        Slider(value.toFloat(), onValueChange = {
            val changed = JSONObject(document.toString())
            val weight = it.roundToInt()
            changed.getJSONObject("allocation").put(key, weight)
            val cap = mapOf("shares" to "max_share_percent", "bonds" to "max_bond_percent", "funds" to "max_etf_percent")[key]
            cap?.let { field -> changed.getJSONObject("policy").put(field, weight.toString()) }
            onChange(changed.put("customized", true))
        }, valueRange = 0f..100f, steps = 99,
            modifier = Modifier.semantics { contentDescription = "Доля: $title" }, enabled = !busy &&
            !document.getJSONArray("locked").toString().contains("\"$key\"") &&
            !document.getJSONArray("excluded").toString().contains("\"$key\""))
    }
    if (!strategyAllocationValid(document)) Text("Сумма долей должна быть 100 %.", color = MaterialTheme.colorScheme.error)
    Text("Доли задают также пределы для классов активов. Заблокированные категории сохранённой стратегии недоступны.",
        style = MaterialTheme.typography.bodySmall)
    StrategyNumber(document, "profile", "horizon_months", "Срок в месяцах", busy, onChange)
    StrategyNumber(document, "profile", "reserve_rub", "Неприкосновенный резерв, ₽", busy, onChange)
    StrategyNumber(document, "profile", "planned_withdrawal_rub", "Запланированные изъятия, ₽", busy, onChange)
    StrategyNumber(document, "profile", "max_drawdown_percent", "Допустимое снижение, % (не гарантия)", busy, onChange)
    StrategyNumber(document, "policy", "max_issuer_percent", "Предел на одного эмитента, %", busy, onChange)
    StrategyNumber(document, "policy", "max_sector_percent", "Предел на отрасль, %", busy, onChange)
    Text("Пустое поле означает, что условие не задано. Сервер не заменит его нулём.", style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun StrategyNumber(document: JSONObject, section: String, key: String, label: String,
    busy: Boolean, onChange: (JSONObject) -> Unit) {
    OutlinedTextField(document.getJSONObject(section).text(key).orEmpty(), { value ->
        if (value.length <= 24 && value.all { it.isDigit() || it == '.' || it == ',' }) {
            val changed = JSONObject(document.toString())
            changed.getJSONObject(section).put(key, value.replace(',', '.').ifBlank { null } ?: JSONObject.NULL)
            onChange(changed.put("customized", true))
        }
    }, label = { Text(label) }, enabled = !busy, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth())
}

@Composable
private fun StrategyAssessment(result: JSONObject) {
    HorizontalDivider()
    SectionTitle("Проверка портфеля")
    Text(timestampLabel(result.text("captured_at")))
    result.text("valid_until")?.let { Text("Срок актуальности: ${timestampLabel(it)}", style = MaterialTheme.typography.bodySmall) }
    Text(result.text("scope") ?: "Для проверки сначала сохраните стратегию.")
    result.optJSONArray("checks")?.objects()?.forEach { check ->
        val status = when (check.getString("state")) {
            "evaluated" -> "Проверено"
            "blocked" -> "Есть ограничение"
            "inapplicable" -> "Не применяется"
            else -> "Недостаточно данных"
        }
        Text("${check.getString("title")} · $status", style = MaterialTheme.typography.titleSmall)
        Text(check.getString("detail"), style = MaterialTheme.typography.bodySmall)
    }
}
