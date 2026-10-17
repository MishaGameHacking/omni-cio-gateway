package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*

@Composable
fun WorkspaceLink(title: String, detail: String, symbol: SpectrumSymbol, onClick: () -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth(), onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(symbol, Modifier.size(40.dp), selected = true)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                if (detail.isNotBlank()) Text(detail, style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("›", style = MaterialTheme.typography.titleLarge, color = LocalSpectrumPalette.current.cyan)
        }
    }
}

@Composable
fun WorkspaceToggle(title: String, detail: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 56.dp)
        .toggleable(checked, role = Role.Switch, onValueChange = onChange).padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            if (detail.isNotBlank()) Text(detail, style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked, onCheckedChange = null)
    }
}

@Composable
fun WorkspaceChoices(title: String, choices: List<String>, selected: Int, onSelect: (Int) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Column(Modifier.selectableGroup()) {
            choices.forEachIndexed { index, choice ->
                Row(Modifier.fillMaxWidth().heightIn(min = 48.dp)
                    .selectable(selected == index, role = Role.RadioButton, onClick = { onSelect(index) })
                    .padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    RadioButton(selected == index, onClick = null)
                    Text(choice, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
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
