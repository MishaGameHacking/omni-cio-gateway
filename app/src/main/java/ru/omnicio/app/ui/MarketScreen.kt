package ru.omnicio.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.math.BigDecimal

internal data class MarketInstrument(val uid: String, val ticker: String, val name: String, val lot: Int)
internal data class MarketQuote(val price: BigDecimal?, val currency: String?, val status: String?,
    val time: String?, val source: String?)
internal fun parseMarketQuote(root: JSONObject) = MarketQuote(root.decimal("cash_price"),
    root.text("cash_price_currency"), root.text("quote_status"), root.text("quote_time"), root.text("source"))
internal data class MarketUiState(
    val query: String = "", val loaded: Boolean = false,
    val items: List<MarketInstrument> = emptyList(),
    val selected: MarketInstrument? = null, val quote: MarketQuote? = null,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun MarketScreen(state: AppUiState, model: OmnicioViewModel) {
    var query by remember { mutableStateOf(state.market.query) }
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Что купить", style = MaterialTheme.typography.headlineLarge) }
        item {
            OutlinedTextField(query, { query = it.take(64) }, label = { Text("Название или тикер") },
                singleLine = true, modifier = Modifier.fillMaxWidth())
            TextButton(onClick = { model.searchMarket(query) }, enabled = query.isNotBlank() && !state.busy) {
                Text("Найти инструмент")
            }
        }
        if (!state.market.loaded) item {
            Text("Найдите акции, облигации и фонды. Карточки и котировки загружаются с сервера.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else if (state.market.items.isEmpty()) item { Text("По запросу «${state.market.query}» ничего не найдено.") }
        items(state.market.items, key = { it.uid }) { item ->
            ListItem(headlineContent = { Text(item.name) }, supportingContent = { Text(item.ticker) },
                trailingContent = { Text("Лот ${item.lot}", style = MaterialTheme.typography.bodySmall) },
                modifier = Modifier.clickable(enabled = !state.busy) { model.loadMarketInstrument(item) },
                colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.background))
        }
    }
    state.market.selected?.let { selected ->
        ModalBottomSheet(onDismissRequest = model::closeMarketInstrument,
            properties = sheetProperties(state.screenshotsBlocked)) {
            Column(Modifier.padding(20.dp).fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(selected.name, style = MaterialTheme.typography.headlineMedium)
                Text(selected.ticker, color = MaterialTheme.colorScheme.onSurfaceVariant)
                val quote = state.market.quote
                if (quote == null) Text("Котировка не получена.") else {
                    val currency = quote.currency
                    Text(if (currency == null) "Цена в валюте не предоставлена" else
                        money(quote.price, currency = currency.uppercase()),
                        style = MaterialTheme.typography.headlineLarge)
                    Text(statusLabel(quote.status))
                    Text(timestampLabel(quote.time), style = MaterialTheme.typography.bodySmall)
                    Text("Источник: ${quote.source ?: "не указан"}", style = MaterialTheme.typography.bodySmall)
                }
                Text("Лот: ${selected.lot}")
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}
