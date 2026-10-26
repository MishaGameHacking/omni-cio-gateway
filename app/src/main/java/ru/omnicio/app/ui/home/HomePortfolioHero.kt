package ru.omnicio.app.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.portfolio.SignedAmount
import ru.omnicio.app.ui.portfolio.moneyText
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

@Composable
internal fun HomePortfolioHero(state: PortfolioUiState, currency: PortfolioCurrency,
    refreshing: Boolean, error: String?, onPortfolio: () -> Unit, onConnect: () -> Unit) {
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    SpectrumCard(Modifier.testTag("home-real-portfolio"), emphasized = true) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Portfolio, Modifier.size(40.dp), selected = true)
            Text("Мой портфель", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
        }
        if (snapshot != null) {
            Text(snapshot.totalValue.moneyText(), style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold, modifier = Modifier.testTag("home-portfolio-balance"))
            if (snapshot.expectedYieldAmount != null || snapshot.expectedYieldPercent != null) {
                SignedAmount(snapshot.expectedYieldAmount, snapshot.expectedYieldPercent)
                Text("Текущий результат брокера", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("Данные: " + relativeObservation(snapshot.asOf) + if (refreshing) " · обновляем" else "",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (snapshot.totalValue.currency != currency.name)
                Text("Оценка в ${snapshot.totalValue.currency}; запрошена ${currency.name}", style = MaterialTheme.typography.bodySmall)
            if (error != null) Text("Сохранённый срез · $error", color = MaterialTheme.colorScheme.error)
            if (snapshot.warnings.isNotEmpty()) SpectrumBadge("Есть ограничения данных", accent = LocalSpectrumPalette.current.amber)
            SpectrumPrimaryButton("Открыть портфель", onPortfolio, Modifier.fillMaxWidth())
        } else when (state) {
            PortfolioUiState.Loading, PortfolioUiState.ApiConnected -> {
                SpectrumLoadingIndicator(description = "Получаем портфель")
                Text("Получаем счета и активы", style = MaterialTheme.typography.titleMedium)
                Text("Стоимость появится после ответа источника.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            is PortfolioUiState.Error -> {
                Text("Данные пока недоступны", style = MaterialTheme.typography.titleMedium)
                Text(state.message, color = MaterialTheme.colorScheme.error)
                SpectrumSecondaryButton("Открыть портфель", onPortfolio, Modifier.fillMaxWidth())
            }
            else -> {
                Text("Ваш капитал в одном месте", style = MaterialTheme.typography.titleMedium)
                Text("Подключите данные счёта, чтобы видеть стоимость, состав и изменения.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                SpectrumPrimaryButton("Подключить портфель", onConnect, Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
internal fun HomePortfolioActions(onRisk: () -> Unit, onStrategy: () -> Unit, onAnalyst: () -> Unit) {
    val font = LocalDensity.current.fontScale
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val actions = listOf(Triple("Риски", SpectrumSymbol.Risk, onRisk),
            Triple("Стратегия", SpectrumSymbol.Goal, onStrategy), Triple("Аналитик", SpectrumSymbol.Analyst, onAnalyst))
        if (font >= 1.5f || maxWidth < 320.dp) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                actions.forEach { (title, symbol, click) ->
                    SpectrumTextButton(title, click, Modifier.fillMaxWidth(), symbol = symbol)
                }
            }
        } else Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            actions.forEach { (title, symbol, click) ->
                SpectrumCard(Modifier.weight(1f), onClick = click) {
                    SpectrumIcon(symbol, Modifier.align(Alignment.CenterHorizontally).size(32.dp), selected = true)
                    Text(title, Modifier.align(Alignment.CenterHorizontally), style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}
