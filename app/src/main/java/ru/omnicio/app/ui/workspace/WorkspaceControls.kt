package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spatial.*

@Composable
fun WorkspaceLink(title: String, detail: String, symbol: SpectrumSymbol, onClick: () -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth(), onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(symbol, Modifier.size(32.dp), selected = false, motionAllowed = false)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                if (detail.isNotBlank()) Text(detail, style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            SpatialIcon("arrow", Modifier.size(22.dp), motionAllowed = false)
        }
    }
}

@Composable
fun WorkspaceToggle(title: String, detail: String, checked: Boolean, modifier: Modifier = Modifier, enabled: Boolean = true, onChange: (Boolean) -> Unit) {
    Row(modifier.fillMaxWidth().heightIn(min = 56.dp)
        .toggleable(checked, enabled = enabled, role = Role.Switch, onValueChange = onChange).padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            if (detail.isNotBlank()) Text(detail, style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        SpatialToggleVisual(checked, Modifier.size(width = 52.dp, height = 32.dp), enabled = enabled)
    }
}

@Composable
fun WorkspaceChoices(title: String, choices: List<String>, selected: Int, enabled: Boolean = true, onSelect: (Int) -> Unit) {
    var open by rememberSaveable(title) { mutableStateOf(false) }
    SpectrumTextButton(title + " · " + (choices.getOrNull(selected) ?: "Выбрать"),
        onClick = { open = true }, modifier = Modifier.fillMaxWidth(), enabled = enabled,
        symbol = SpectrumSymbol.ChevronDown)
    if (open) WorkspaceDialog(title, { open = false }) {
        Column(Modifier.selectableGroup()) {
            choices.forEachIndexed { index, choice ->
                Row(Modifier.fillMaxWidth().heightIn(min = 48.dp)
                    .selectable(selected == index, enabled = enabled, role = Role.RadioButton,
                        onClick = { onSelect(index); open = false }).padding(vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    SpatialChoiceVisual(selected == index, Modifier.size(24.dp), enabled = enabled)
                    Text(choice, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
        SpectrumSecondaryButton("Закрыть", { open = false }, Modifier.fillMaxWidth())
    }
}

@Composable
fun WorkspaceSection(title: String, detail: String = "") {
    Column(Modifier.fillMaxWidth().padding(top = 6.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        if (detail.isNotBlank()) Text(detail, color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium)
    }
}

