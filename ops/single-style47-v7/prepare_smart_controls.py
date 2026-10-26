"""Administrative source-text preparation; all execution and tests stay on Windows."""

def apply(files, base):
    ui='app/src/main/java/ru/omnicio/app/ui/'
    def get(p): return files[p] if p in files else base(p)
    def replace(p,old,new,count=1):
        s=get(p);assert s.count(old)==count,(p,old[:90],s.count(old));files[p]=s.replace(old,new)

    files[ui+'workspace/SuggestedInputModel.kt']='''package ru.omnicio.app.ui.workspace

import java.time.ZoneId
import java.util.Locale

/** A suggestion carries an actual source value, never a generated instrument ID. */
data class WorkspaceSuggestion(val value: String, val label: String, val keywords: String = "")

internal fun matchingSuggestions(options: List<WorkspaceSuggestion>, query: String): List<WorkspaceSuggestion> {
    val tokens = query.trim().lowercase(Locale.ROOT).split(Regex("\\\\s+")).filter(String::isNotEmpty)
    val unique = options.filter { it.label.isNotBlank() }.distinctBy { it.value }
    if (tokens.isEmpty()) return unique
    return unique.filter { item ->
        val text = (item.label + " " + item.value + " " + item.keywords).lowercase(Locale.ROOT)
        tokens.all(text::contains)
    }.sortedBy { item -> if (item.label.lowercase(Locale.ROOT).startsWith(tokens.first())) 0 else 1 }
}

internal fun notificationZoneSuggestions(deviceZone: String, current: String): List<WorkspaceSuggestion> {
    val cities = mapOf("Europe/Moscow" to "Москва", "Europe/Kaliningrad" to "Калининград",
        "Europe/Samara" to "Самара", "Asia/Yekaterinburg" to "Екатеринбург", "Asia/Omsk" to "Омск",
        "Asia/Krasnoyarsk" to "Красноярск", "Asia/Irkutsk" to "Иркутск", "Asia/Yakutsk" to "Якутск",
        "Asia/Vladivostok" to "Владивосток", "Asia/Magadan" to "Магадан", "Asia/Kamchatka" to "Камчатка")
    val available = ZoneId.getAvailableZoneIds()
    return (listOf(deviceZone, current) + available.sorted()).distinct().filter { it in available }.map { zone ->
        WorkspaceSuggestion(zone, (cities[zone]?.plus(" · ") ?: "") + zone.replace('_', ' '),
            if (zone == deviceZone) "Часовой пояс устройства" else "")
    }
}
'''

    files[ui+'workspace/WorkspaceSuggestedControls.kt']='''package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import java.time.LocalTime
import java.util.Locale
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spatial.SpatialChoiceVisual

/** Every source option is reachable; lazy rendering is not an option-count limit. */
@Composable
fun WorkspaceChoicePicker(title: String, value: String, options: List<WorkspaceSuggestion>,
    enabled: Boolean = true, modifier: Modifier = Modifier, onSelect: (String) -> Unit) {
    var open by rememberSaveable(title) { mutableStateOf(false) }
    val selected = options.firstOrNull { it.value == value }
    val label = selected?.label ?: value.takeIf { it.isNotBlank() } ?: "Выбрать"
    SpectrumTextButton("$title · $label", { open = true }, modifier.fillMaxWidth().heightIn(min = 48.dp),
        enabled = enabled, symbol = SpectrumSymbol.Expand)
    if (open) SuggestionPickerDialog(title, value, options, enabled, { open = false }) {
        if (enabled && options.any { candidate -> candidate.value == it }) { onSelect(it); open = false }
    }
}

@Composable
private fun SuggestionPickerDialog(title: String, value: String, options: List<WorkspaceSuggestion>,
    enabled: Boolean, onClose: () -> Unit, onSelect: (String) -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    val found = remember(options, query) { matchingSuggestions(options, query) }
    SpectrumModal(onDismissRequest = onClose) {
        SpectrumCard {
            Text(title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { heading() })
            WorkspaceTextInput(query, { query = it.take(120) }, "Найти вариант", Modifier.fillMaxWidth()
                .testTag("suggestion-search"), enabled = enabled)
            Text("Вариантов: " + found.size, style = MaterialTheme.typography.bodySmall)
            if (found.isEmpty()) Text("Совпадений нет. Измените поиск; текущее значение сохранено.")
            LazyColumn(Modifier.weight(1f, fill = false).fillMaxWidth().selectableGroup()
                .testTag("suggestion-options"), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                items(found, key = { it.value }) { item ->
                    Row(Modifier.fillMaxWidth().heightIn(min = 56.dp)
                        .selectable(item.value == value, enabled = enabled, role = Role.RadioButton,
                            onClick = { onSelect(item.value) }).padding(vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        SpatialChoiceVisual(item.value == value, Modifier.size(24.dp), enabled = enabled)
                        Text(item.label, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }
            SpectrumSecondaryButton("Вернуться", onClose, Modifier.fillMaxWidth())
        }
    }
}

/** Suggestions are explicit draft edits; typing does not select or submit one. */
@Composable
fun WorkspaceSuggestionRow(query: String, options: List<WorkspaceSuggestion>,
    enabled: Boolean = true, modifier: Modifier = Modifier, onSelect: (String) -> Unit) {
    val found = remember(query, options) { matchingSuggestions(options, query) }
    var all by rememberSaveable { mutableStateOf(false) }
    if (found.isNotEmpty()) LazyRow(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(found.take(4), key = { it.value }) { item ->
            SpectrumTextButton(item.label, { if (enabled) onSelect(item.value) },
                enabled = enabled, symbol = SpectrumSymbol.Search)
        }
        if (found.size > 4) item { SpectrumTextButton("Все варианты · " + found.size,
            { all = true }, enabled = enabled, symbol = SpectrumSymbol.Expand) }
    }
    if (all) SuggestionPickerDialog("Выбор из доступных данных", "", found, enabled, { all = false }) {
        if (enabled && found.any { candidate -> candidate.value == it }) { onSelect(it); all = false }
    }
}

/** Clock selection is kept local until the user accepts it. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkspaceTimeChoice(title: String, value: String, enabled: Boolean, onSelect: (String) -> Unit) {
    var open by rememberSaveable(title) { mutableStateOf(false) }
    SpectrumTextButton(title + " · " + value.ifBlank { "Выбрать время" }, { open = true },
        Modifier.fillMaxWidth(), enabled = enabled, symbol = SpectrumSymbol.Calendar)
    if (open) {
        val parsed = remember(value) { runCatching { LocalTime.parse(value) }.getOrNull() }
        val time = rememberTimePickerState(initialHour = parsed?.hour ?: 9,
            initialMinute = parsed?.minute ?: 0, is24Hour = true)
        SpectrumAlertDialog(onDismissRequest = { open = false }, title = { Text(title) },
            text = {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    if (LocalDensity.current.fontScale >= 1.5f) TimeInput(time) else TimePicker(time)
                }
            }, confirmButton = {
                SpectrumPrimaryButton("Выбрать время", {
                    if (enabled) { onSelect(String.format(Locale.ROOT, "%02d:%02d", time.hour, time.minute)); open = false }
                }, Modifier.fillMaxWidth(), enabled)
            }, dismissButton = { SpectrumSecondaryButton("Отмена", { open = false }, Modifier.fillMaxWidth()) })
    }
}

/** A checkbox expresses inclusion in a collection, independently of other choices. */
@Composable
fun WorkspaceCheckbox(title: String, checked: Boolean, enabled: Boolean = true, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp)
        .toggleable(checked, enabled = enabled, role = Role.Checkbox, onValueChange = onChange),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Checkbox(checked, onCheckedChange = null, enabled = enabled)
        Text(title, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
    }
}
'''

    path=ui+'workspace/NotificationWorkspaceScreens.kt'
    old='''                    WorkspaceTextInput(settings.text("timezone", "Europe/Moscow"), { edit("timezone", it.take(80)) }, "Часовой пояс", Modifier.fillMaxWidth(), enabled = !save.busy)
                    Text("Например, Europe/Moscow. Все указанные ниже часы относятся к этому поясу.", style = MaterialTheme.typography.bodySmall)'''
    new='''                    val zone = settings.text("timezone", "Europe/Moscow")
                    val deviceZone = remember { ZoneId.systemDefault().id }
                    val zones = remember(deviceZone, zone) { notificationZoneSuggestions(deviceZone, zone) }
                    WorkspaceChoicePicker("Часовой пояс", zone, zones, !save.busy && !simulate.busy) { edit("timezone", it) }
                    Text("Все часы относятся к выбранному поясу. Поиск принимает город или идентификатор пояса.", style = MaterialTheme.typography.bodySmall)'''
    replace(path,old,new)
    replace(path,'                    WorkspaceTextInput(settings.text(key, ""), { edit(key, it.take(5)) }, title + " · ЧЧ:ММ", Modifier.fillMaxWidth(), enabled = !save.busy)',
        '                    WorkspaceTimeChoice(title, settings.text(key, ""), !save.busy && !simulate.busy) { edit(key, it) }')

    path=ui+'workspace/RiskScenarioDialog.kt'
    old='''            if (candidates.isNotEmpty()) DetailFold("Выбрать из подтверждённых позиций") {
                candidates.take(40).forEach { candidate -> SpectrumSecondaryButton(candidate.text("label"), { edit("target", candidate.text("id")) }, Modifier.fillMaxWidth(), !action.busy) }
                if (candidates.size > 40) Text("Показаны первые 40 значений. Точный код можно ввести в поле ниже.")
            }
            WorkspaceTextInput(current.text("target", ""), { edit("target", it.take(160)) }, "Код из источника или UID инструмента", Modifier.fillMaxWidth(), enabled = !action.busy)'''
    new='''            WorkspaceChoicePicker("Объект сценария", current.text("target", ""),
                candidates.map { WorkspaceSuggestion(it.text("id"), it.text("label")) }, !action.busy) { edit("target", it) }
            DetailFold("Точный код из источника") {
                WorkspaceTextInput(current.text("target", ""), { edit("target", it.take(160)) }, "Код из источника или UID инструмента", Modifier.fillMaxWidth(), enabled = !action.busy)
            }'''
    replace(path,old,new)

    path=ui+'workspace/ChatContextEditor.kt'
    old='''                WorkspaceTextInput(search, { search = it.take(100) }, "Найти инструмент", Modifier.fillMaxWidth())
                selected?.let { Text("Выбрано: " + it.title, style = MaterialTheme.typography.titleMedium) }
                val found = positions.filter { search.isBlank() || it.title.contains(search, true) || it.ticker?.contains(search, true) == true }
                DetailFold("Инструменты · " + found.size, initiallyOpen = selected == null) {
                    found.take(20).forEach { position -> SpectrumSecondaryButton(position.title, { instrument = position.id }, Modifier.fillMaxWidth()) }
                    if (found.size > 20) Text("Уточните поиск, чтобы выбрать из остальных инструментов.")
                }'''
    new='''                WorkspaceChoicePicker("Инструмент", instrument.orEmpty(), positions.map {
                    WorkspaceSuggestion(it.id, it.title, listOfNotNull(it.ticker, it.isin).joinToString(" "))
                }) { instrument = it }'''
    replace(path,old,new)
    replace(path,'                    SpectrumSecondaryButton("Убрать событие из контекста", { keepEvent = false }, Modifier.fillMaxWidth())',
        '                    WorkspaceCheckbox("Включить эту публикацию", keepEvent) { keepEvent = it }')
    # The checkbox remains available after exclusion, allowing a reversible selection.
    replace(path,'                if (keepEvent && instrument == current.instrumentUid && current.eventId != null) {',
        '                if (instrument == current.instrumentUid && current.eventId != null) {')
    replace(path,'                Text("Период ограничивает доступные операции.',
        '''                val today = remember { LocalDate.now() }
                WorkspaceSuggestionRow("", listOf(WorkspaceSuggestion("month", "Последний месяц"),
                    WorkspaceSuggestion("year", "С начала года"), WorkspaceSuggestion("all", "Весь период"))) { period ->
                    start = when (period) { "month" -> today.minusMonths(1).toString(); "year" -> today.withDayOfYear(1).toString(); else -> "" }
                    end = if (period == "all") "" else today.toString()
                }
                Text("Период ограничивает доступные операции.''')

    path=ui+'workspace/LiveStrategyScreen.kt'
    replace(path,'        Text("Выбор цели не добавляет ожидаемую прибыль к капиталу.',
        '''        WorkspaceSuggestionRow("", listOf(12, 36, 60, 120).map { WorkspaceSuggestion(it.toString(), "$it мес.") }, enabled) { months ->
            edit(JSONObject(config.toString()).put("horizon_months", months.toInt()))
        }
        Text("Выбор цели не добавляет ожидаемую прибыль к капиталу.''')
    replace(path,'        Text("Ограничение применяется к подтверждённой доле.',
        '''        val percent = limits.text(key, "").toFloatOrNull()?.takeIf { it.isFinite() && it in 0f..100f }
        if (percent != null) SpectrumSlider(percent, { next ->
            edit(JSONObject(config.toString()).put("limits", JSONObject(limits.toString()).put(key, next.toInt().toString())))
        }, Modifier.fillMaxWidth().semantics { contentDescription = title + ", %" }, enabled = enabled,
            valueRange = 0f..100f, steps = 99)
        Text("Ограничение применяется к подтверждённой доле.''')
    replace(path,'import androidx.compose.ui.Modifier\n','import androidx.compose.ui.Modifier\nimport androidx.compose.ui.semantics.contentDescription\n')

    path=ui+'portfolio/PortfolioAssetBrowser.kt'
    replace(path,'        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {',
        '''        if (query.isNotBlank()) WorkspaceSuggestionRow(query,
            allCurrent.map { WorkspaceSuggestion(it.position.ticker ?: it.position.title, it.position.title,
                listOfNotNull(it.position.ticker, it.position.isin).joinToString(" ")) },
            modifier = Modifier.padding(horizontal = 20.dp)) { query = it }
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {''')
    old='''            WorkspaceChoices("Счёт", listOf("Все счета") + snapshot.accounts.map { it.name }, snapshot.accounts.indexOfFirst { it.id == accountId } + 1) {
                accountId = snapshot.accounts.getOrNull(it - 1)?.id
            }
            WorkspaceChoices("Класс", labels, kinds.indexOf(kind).coerceAtLeast(0)) { kind = kinds[it] }
            WorkspaceChoices("Группировать", listOf("По счетам", "По названиям компаний", "По отраслям", "Проверенные эмитенты", "Проверенные группы"), group) { group = it; exposureId = null }
            WorkspaceChoices("Порядок", listOf("Сначала ограничения", "По стоимости", "По доле", "По названию"), order) { order = it }'''
    new='''            WorkspaceChoicePicker("Счёт", accountId.orEmpty(), listOf(WorkspaceSuggestion("", "Все счета")) +
                snapshot.accounts.map { WorkspaceSuggestion(it.id, it.name) }) { accountId = it.ifBlank { null } }
            WorkspaceChoicePicker("Класс", kind, kinds.mapIndexed { index, id -> WorkspaceSuggestion(id, labels[index]) }) { kind = it }
            WorkspaceChoicePicker("Группировать", group.toString(), listOf("По счетам", "По названиям компаний", "По отраслям", "Проверенные эмитенты", "Проверенные группы")
                .mapIndexed { index, title -> WorkspaceSuggestion(index.toString(), title) }) { group = it.toInt(); exposureId = null }
            WorkspaceChoicePicker("Порядок", order.toString(), listOf("Сначала ограничения", "По стоимости", "По доле", "По названию")
                .mapIndexed { index, title -> WorkspaceSuggestion(index.toString(), title) }) { order = it.toInt() }
            WorkspaceCheckbox("Только из наблюдения", onlyWatched) { onlyWatched = it }'''
    replace(path,old,new)

    files['app/src/test/java/ru/omnicio/app/ui/workspace/SuggestedInputModelTest.kt']='''package ru.omnicio.app.ui.workspace

import org.junit.Assert.*
import org.junit.Test

class SuggestedInputModelTest {
    @Test fun searchUsesEveryWordAndReturnsOnlyExistingValues() {
        val options = listOf(WorkspaceSuggestion("id-1", "Первая компания", "FIRST RU0001"),
            WorkspaceSuggestion("id-2", "Вторая компания", "SECOND RU0002"))
        assertEquals(listOf(options[0]), matchingSuggestions(options, " ПЕРВАЯ ru0001 "))
        assertTrue(matchingSuggestions(options, "неизвестный uid").isEmpty())
        assertTrue(matchingSuggestions(options, "первая RU0002").isEmpty())
    }
    @Test fun duplicateLabelsKeepDistinctSourceIdsAndNoOptionCountCeiling() {
        val options = (1..2500).map { WorkspaceSuggestion("id-$it", "Название", "$it") }
        assertEquals(2500, matchingSuggestions(options, "").size)
        assertEquals("id-2500", matchingSuggestions(options, "2500").single().value)
        assertEquals(options, matchingSuggestions(options + options[0], ""))
    }
    @Test fun blankAllOptionAndUnknownCurrentValueDoNotCreateSyntheticChoices() {
        val all = WorkspaceSuggestion("", "Все счета")
        assertEquals(listOf(all), matchingSuggestions(listOf(all), ""))
        val zones = notificationZoneSuggestions("Europe/Moscow", "missing-zone")
        assertEquals("Europe/Moscow", zones.first().value)
        assertFalse(zones.any { it.value == "missing-zone" })
        assertEquals("Europe/Moscow", matchingSuggestions(zones, "Москва").single().value)
    }
}
'''
