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
import ru.omnicio.app.ui.spatial.SpatialWindow

/** Uses a current position resolved by account and id; no stale detail snapshot. */
@Composable
internal fun InstrumentDetailsScreen(position: PortfolioPosition, close: () -> Unit, accountName: String? = null,
    embedded: Boolean = false, sharedKey: String = position.id, accountId: String? = null) {
    var section by rememberSaveable(position.id) { mutableIntStateOf(0) }
    val labels = instrumentDetailLabels(position.instrumentType, position.currentNkd != null)
    val session = LocalWorkspaceSession.current
    val askAnalyst = LocalAskAnalyst.current
    val navigate = LocalWorkspaceNavigator.current
    val openPortfolio = LocalPortfolioDestination.current
    val discuss = {
        close()
        askAnalyst(ChatContext(mode = "instrument", instrumentUid = position.id,
            title = position.ticker ?: position.title, accountId = accountId))
    }
    val content: @Composable () -> Unit = {
        SpectrumBackground(Modifier.fillMaxSize()) {
            Scaffold(containerColor = androidx.compose.ui.graphics.Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
                topBar = { WorkspaceHeader(position.ticker ?: labels.type, accountName ?: "Ваша позиция", close) },
                bottomBar = { ru.omnicio.app.ui.spatial.SpatialSurface(kind = ru.omnicio.app.ui.spatial.SpatialSurfaceKind.Dock, color = MaterialTheme.colorScheme.background) {
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
                    Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        ru.omnicio.app.ui.spatial.SpatialObject(sharedKey) {
                            SpectrumAssetMark(position.instrumentType, position.company ?: position.title, instrumentSharedModifier(sharedKey).size(64.dp))
                        }
                        Column(Modifier.weight(1f)) {
                            Text(position.title, style = MaterialTheme.typography.titleMedium)
                            Text(position.ticker ?: labels.type, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    SpectrumTabs(listOf("Позиция", "Котировки", "Досье", "Исследование", "Паспорт"), section, { section = it }, Modifier.padding(horizontal = 20.dp))
                    LazyColumn(Modifier.fillMaxWidth().weight(1f), contentPadding = PaddingValues(20.dp),
                        verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                        if (position.blocked) item(key = "restriction") { SpectrumCard(emphasized = true) {
                            Text("Есть ограничения у брокера", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.error)
                            Text("Возможность сделки уточните в Т‑Инвестициях.")
                            DataRow("Заблокировано", position.blockedQuantity.quantityText())
                        } }
                        if (section == 0) {
                            item(key = "position-summary") { InstrumentPositionSummary(position) }
                            item(key = "watch-position") { WatchPositionAction(position) }
                            item(key = "position-actions") { SpectrumCard {
                                Text("Разобраться в позиции", style = MaterialTheme.typography.titleLarge)
                                SpectrumPrimaryButton("Обсудить с аналитиком", discuss, Modifier.fillMaxWidth(), enabled = session.token.isNotBlank())
                                SpectrumSecondaryButton("Проверить мои правила и стратегию", { close(); navigate(WorkspaceRoute.Strategies) }, Modifier.fillMaxWidth())
                                SpectrumSecondaryButton("События и отчётность этой бумаги", { section = 2 }, Modifier.fillMaxWidth())
                                if (accountId != null) SpectrumSecondaryButton("Календарь выплат счёта", {
                                    close(); openPortfolio(PortfolioDestination(section = 4, accountId = accountId))
                                }, Modifier.fillMaxWidth())
                            } }
                        }
                        if (section == 1) item {
                            if (position.instrumentType in setOf("cash", "currency") && position.id.startsWith("cash:"))
                                Text("Денежный остаток не является торгуемым инструментом. История его стоимости входит в динамику счёта.")
                            else InstrumentQuotesPanel(position, accountId, close)
                        }
                        if (section == 2) item { InstrumentDossierPanel(position, close) }
                        if (section == 3) item {
                            if (session.token.isBlank()) WorkspaceEmpty("Исследование недоступно", "Нужен действующий сеанс и сведения из источников.")
                            else PortfolioResearchPanel(session.token, instrumentId = position.id, showRefresh = false)
                            SpectrumSecondaryButton("Обсудить эту бумагу", discuss, Modifier.fillMaxWidth(), enabled = session.token.isNotBlank())
                        }
                        if (section == 4) item(key = "instrument-identifiers") { InstrumentPassport(position) }
                    }
                }
                }
                }
            }
        }
    }
    if (embedded) content() else Dialog(onDismissRequest = close,
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
            SpatialWindow(Modifier.fillMaxSize()) { content() }
        }
}

@Composable
private fun InstrumentPositionSummary(position: PortfolioPosition) {
    val labels = instrumentDetailLabels(position.instrumentType, position.currentNkd != null)
    SpectrumCard {

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
                                }
}

@Composable
private fun InstrumentPassport(position: PortfolioPosition) {
    SpectrumCard {

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
                            }
}

