package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.ui.instruments.BrokerInstrumentActions
import ru.omnicio.app.ui.spectrum.*

private const val CompanyLabel = "Компания"
private const val ExchangeLabel = "Биржа"
private const val NoInstrumentData = "Нет данных"

/** Full-screen native view. The caller resolves a current position before rendering. */
@Composable
internal fun InstrumentDetailsScreen(position: PortfolioPosition, close: () -> Unit) {
    var section by rememberSaveable(position.id) { mutableIntStateOf(0) }
    val labels = instrumentDetailLabels(position.instrumentType, position.currentNkd != null)
    Dialog(onDismissRequest = close,
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        SpectrumBackground(Modifier.fillMaxSize()) {
            Scaffold(containerColor = Color.Transparent, contentColor = MaterialTheme.colorScheme.onBackground,
                contentWindowInsets = WindowInsets.safeDrawing) { insets ->
                Column(Modifier.fillMaxSize().padding(insets)) {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                        TextButton(onClick = close, modifier = Modifier.heightIn(min = 48.dp)) { Text("‹ Назад") }
                        Text(position.ticker?.takeIf(String::isNotBlank) ?: labels.type,
                            Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
                            style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    }
                    LazyColumn(Modifier.fillMaxWidth().weight(1f), contentPadding = PaddingValues(20.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        item(key = "instrument-identity") { InstrumentPriceHero(position) }
                        item(key = "instrument-tabs") {
                            SpectrumTabs(listOf("Обзор", "Моя позиция", "Сведения"), section, { section = it })
                        }
                        when (section) {
                            0 -> instrumentOverview(position)
                            1 -> item(key = "position-amounts") { InstrumentHolding(position) }
                            else -> item(key = "instrument-identifiers") { InstrumentIdentifiers(position) }
                        }
                        item(key = "source-disclosure") {
                            Notice("Источник — подключённый брокерский счёт. «—» означает, что значение не получено. Суммы показаны в валютах источника. Переход к брокеру не создаёт заявку.")
                        }
                    }
                }
            }
        }
    }
}

private fun LazyListScope.instrumentOverview(position: PortfolioPosition) {
    item(key = "broker-navigation") { BrokerInstrumentActions(position.instrumentType, position.ticker, position.isin) }
    item(key = "instrument-overview") {
        SpectrumCard {
            SpectrumHeader("Об инструменте", symbol = SpectrumSymbol.Sources)
            DataRow("Тип", instrumentDetailLabels(position.instrumentType, position.currentNkd != null).type)
            DataRow(CompanyLabel, position.company ?: NoInstrumentData)
            DataRow("Отрасль", position.sector ?: NoInstrumentData)
            DataRow(ExchangeLabel, position.exchange ?: "—")
            Notice("История котировок этого инструмента пока не подключена. Текущая цена не заменяется демонстрационным графиком.")
        }
    }
    item(key = "instrument-assistant") {
        SpectrumCard {
            SpectrumHeader("Аналитик о вашем портфеле", "Исследования и риски — в разделе «Риски» на главной", SpectrumSymbol.Robot)
            Notice("Индивидуальный прогноз по этой бумаге здесь не рассчитан. Цена и результат позиции не являются рекомендацией купить или продать.")
        }
    }
}

@Composable
private fun InstrumentHolding(position: PortfolioPosition) {
    val labels = instrumentDetailLabels(position.instrumentType, position.currentNkd != null)
    SpectrumCard {
        SpectrumHeader("Моя позиция", symbol = SpectrumSymbol.Portfolio)
        DataRow("Стоимость позиции", position.currentValue.moneyText())
        DataRow(labels.quantity, position.quantity.quantityText())
        DataRow("Результат позиции", position.expectedYieldAmount.moneyText(true))
        position.expectedYieldPercent?.let { DataRow("Доходность", it.percentText()) }
        DataRow("За день", position.dailyYieldAmount.moneyText(true))
        DataRow("Средняя цена", position.averagePrice.moneyText())
        labels.accrued?.let { DataRow(it, position.currentNkd.moneyText()) }
        DataRow("Заблокированное количество", position.blockedQuantity.quantityText())
        DataRow("Блокировка", if (position.blocked) "Отмечена брокером" else "Не отмечена")
        Notice("Отсутствие отметки о блокировке не подтверждает доступность торгов. Количество не переводится в лоты.")
    }
}

@Composable
private fun InstrumentIdentifiers(position: PortfolioPosition) {
    SpectrumCard {
        SpectrumHeader("Сведения и идентификаторы", symbol = SpectrumSymbol.Sources)
        SelectionContainer {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                DataRow("Тикер", position.ticker ?: "—")
                DataRow("ISIN", position.isin ?: "—")
                DataRow("Идентификатор", position.id)
                DataRow(CompanyLabel, position.company ?: NoInstrumentData)
                DataRow(ExchangeLabel, position.exchange ?: "—")
            }
        }
        BrokerInstrumentActions(position.instrumentType, position.ticker, position.isin)
    }
}

@Composable
private fun InstrumentPriceHero(position: PortfolioPosition) {
    SpectrumCard(emphasized = true) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumAssetIcon(position.ticker, position.instrumentType, Modifier.size(56.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(position.ticker ?: position.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(position.title, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Text(position.currentPrice.moneyText(), fontSize = 32.sp, lineHeight = 40.sp, fontWeight = FontWeight.Bold)
        Notice("Текущая цена за единицу")
        position.dailyYieldAmount?.let { DataRow("Изменение стоимости вашей позиции за день", it.moneyText(true)) }
        if (position.blocked) SpectrumBadge("Есть ограничения", accent = LocalSpectrumPalette.current.amber)
    }
}
