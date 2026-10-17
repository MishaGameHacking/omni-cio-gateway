package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.PortfolioAccount

@Composable
internal fun AccountSelector(accounts: List<PortfolioAccount>, selectedId: String, onSelect: (String) -> Unit,
    modifier: Modifier = Modifier) {
    var expanded by remember { mutableStateOf(false) }
    Box(modifier) {
        TextButton(onClick = { expanded = true }, modifier = Modifier.heightIn(min = 48.dp)) {
            Text((accounts.firstOrNull { it.id == selectedId }?.name ?: "Выберите счёт") + " ▾")
        }
        DropdownMenu(expanded, { expanded = false }) {
            accounts.forEach { account -> DropdownMenuItem(text = { Text(account.name) }, onClick = {
                onSelect(account.id); expanded = false
            }) }
        }
    }
}

