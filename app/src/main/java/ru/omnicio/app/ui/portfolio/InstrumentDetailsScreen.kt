package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.ui.instruments.BrokerInstrumentActions
import ru.omnicio.app.ui.research.PortfolioResearchPanel
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

/** Uses a current position resolved by account and id; no stale detail snapshot. */
@Composable
internal fun InstrumentDetailsScreen(position: PortfolioPosition, close: () -> Unit, accountName: String? = null) {
    var section by rememberSaveable(position.id) { mutableIntStateOf(0) }
    val labels = instrumentDetailLabels(position.instrumentType, position.currentNkd != null)
    val session = LocalWorkspaceSession.current
    Dialog(onDismissRequest = close,
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        SpectrumBackground(Modifier.fillMaxSize()) {
            Scaffold(containerColor = androidx.compose.ui.graphics.Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
                topBar = { WorkspaceHeader(position.ticker ?: labels.type, accountName ?: "Ваша позиция", close) },
                bottomBar = { Surface(color = MaterialTheme.colorScheme.background) {
                    Box(Modifier.navigationBarsPadding().padding(horizontal = 20.dp, vertical = 8.dp)) {
                        BrokerInstrumentActions(position.instrumentType, position.ticker, position.isin, compact = true)
                    }
                } }) { insets ->
                BoxWithConstraints(Modifier.fillMaxSize().padding(insets).consumeWindowInsets(insets)) {
                val wide = maxWidth >= 840.dp
                Row(Modifier.fillMaxSize()) {
                    if (wide) Column(Modifier.width(300.dp).padding(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                        Text(position.title, style = MaterialTheme.typography.headlineSmall)
                        Text(accountName ?: "Ваша позиция")
                        Text(position.currentValue.moneyText(), style = MaterialTheme.typography.headlineMedium)
                        Text("Сводка остаётся рядом с подробностями.", style = MaterialTheme.typography.bodyMedium)
                    }
                Column(Modifier.weight(1f).fillMaxHeight()) {
                    SpectrumTabs(listOf("Позиция", "Исследование", "Паспорт"), section, { section = it }, Modifier.padding(horizontal = 20.dp))
                    LazyColumn(Modifier.fillMaxWidth().weight(1f), contentPadding = PaddingValues(20.dp),
                        verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                        if (position.blocked) item(key = "restriction") { SpectrumCard(emphasized = true) {
                            Text("Есть ограничения у брокера", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.error)
                            Text("Возможность сделки уточните в Т‑Инвестициях.")
                            DataRow("Заблокировано", position.blockedQuantity.quantityText())
                        } }
                        if (section == 0) {
                            item(key = "position-summary") { SpectrumCard {
                                Text(position.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                                Notice(labels.type)
                                DataRow("Стоимость позиции", position.currentValue.moneyText())
                                DataRow(labels.quantity, position.quantity.quantityText())
                                DataRow("Цена за единицу", position.currentPrice.moneyText())
                                DataRow("Средняя цена", position.averagePrice.moneyText())
                                labels.accrued?.let { DataRow(it, position.currentNkd.moneyText()) }
                                SignedAmount(position.expectedYieldAmount, position.expectedYieldPercent)
                                DetailFold("Результат за день и условия") {
                                    DataRow("За день", position.dailyYieldAmount.moneyText(true))
                                    Notice("Цена и количество показаны в единицах брокера. Количество — в штуках, не в лотах.")
                                    if (!position.blocked) Notice("Ограничение не отмечено. Это не подтверждение доступности торгов.")
                                }
                            } }
                            item(key = "strategy-check") { WorkspaceEmpty("Соответствие стратегии",
                                "Проверка действующих правил для этой бумаги ещё не подключена. Заключение не получено.") }
                            if (position.instrumentType == "bond") item { DetailFold("Погашение и ближайший купон") {
                                Text("Условия выпуска не получены. Календарь опубликованных выплат доступен в вашем счёте.")
                            } }
                            if (position.instrumentType == "share") item { DetailFold("Корпоративные события") {
                                Text("Проверенные события показаны в исследовании, если источник их предоставил.")
                            } }
                        }
                        if (section == 1) item {
                            if (session.token.isBlank()) WorkspaceEmpty("Исследование недоступно", "Нужен действующий сеанс и сведения из источников.")
                            else PortfolioResearchPanel(session.token, instrumentId = position.id, showRefresh = false)
                        }
                        if (section == 2) item(key = "instrument-identifiers") { SpectrumCard {
                            Text("Паспорт инструмента", style = MaterialTheme.typography.titleLarge)
                            SelectionContainer { Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                DataRow("Тикер", position.ticker ?: "—")
                                DataRow("ISIN", position.isin ?: "—")
                                position.company?.let { DataRow("Компания", it) }
                                position.exchange?.let { DataRow("Биржа", it) }
                                position.sector?.let { DataRow("Отрасль", it) }
                                DetailFold("Технические сведения") { DataRow("Идентификатор", position.id) }
                            } }
                            BrokerInstrumentActions(position.instrumentType, position.ticker, position.isin, copyOnly = true)
                            Notice("Перед сделкой сверьте название и ISIN у брокера.")
                        } }
                    }
                }
                }
                }
            }
        }
    }
}
