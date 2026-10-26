package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.spectrum.SpectrumTextButton
import ru.omnicio.app.ui.workspace.WorkspaceDialog

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.PortfolioAccount

@Composable
internal fun AccountSelector(accounts: List<PortfolioAccount>, selectedId: String, onSelect: (String) -> Unit,
    modifier: Modifier = Modifier) {
    var expanded by remember { mutableStateOf(false) }
    val largeText = LocalDensity.current.fontScale >= 1.5f
    val scroll = rememberScrollState()
    Box(if (largeText) modifier.horizontalScroll(scroll) else modifier) {
        SpectrumTextButton(accounts.firstOrNull { it.id == selectedId }?.name ?: "Выберите счёт", { expanded = true },
            symbol = SpectrumSymbol.Expand)
        if (expanded) WorkspaceDialog("Выберите счёт", { expanded = false }) {
            accounts.forEach { account -> SpectrumTextButton(account.name, {
                onSelect(account.id); expanded = false
            }, Modifier.fillMaxWidth(), symbol = if (account.id == selectedId) SpectrumSymbol.Check else SpectrumSymbol.Portfolio) }
            SpectrumTextButton("Закрыть", { expanded = false }, Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Close)
        }
    }
}

