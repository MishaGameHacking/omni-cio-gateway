package ru.omnicio.app.ui.workspace

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
        var previous by remember { mutableStateOf(String.format(Locale.ROOT, "%02d:%02d", time.hour, time.minute)) }
        LaunchedEffect(time.hour, time.minute, enabled) {
            val next = String.format(Locale.ROOT, "%02d:%02d", time.hour, time.minute)
            if (enabled && next != previous) { previous = next; onSelect(next) }
        }
        SpectrumAlertDialog(onDismissRequest = { open = false }, title = { Text(title) },
            text = {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    if (LocalDensity.current.fontScale >= 1.5f) TimeInput(time) else TimePicker(time)
                }
            }, confirmButton = {
                SpectrumPrimaryButton("Готово", { open = false }, Modifier.fillMaxWidth())
            })
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
