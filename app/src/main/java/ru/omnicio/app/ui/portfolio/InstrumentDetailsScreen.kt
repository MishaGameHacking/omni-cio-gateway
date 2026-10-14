package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.ui.instruments.BrokerInstrumentActions
import ru.omnicio.app.ui.spectrum.SpectrumBackground

/** Displays the live position supplied by LivePositionDetails, never a stored copy. */
@Composable
internal fun InstrumentDetailsScreen(position: PortfolioPosition, close: () -> Unit) {
    val labels = instrumentDetailLabels(position.instrumentType, position.currentNkd != null)
    Dialog(onDismissRequest = close,
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        SpectrumBackground(Modifier.fillMaxSize()) {
            Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing) { insets ->
                Column(Modifier.fillMaxSize().padding(insets)) {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        TextButton(onClick = close, modifier = Modifier.heightIn(min = 48.dp)) { Text("‹ Назад") }
                        Text(position.ticker?.takeIf { it.isNotBlank() } ?: labels.type,
                            modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis,
                            style = MaterialTheme.typography.titleMedium)
                    }
                    LazyColumn(Modifier.fillMaxWidth().weight(1f), contentPadding = PaddingValues(20.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        item(key = "position-summary") {
                            CompactCard {
                                Text(position.title, style = MaterialTheme.typography.headlineSmall,
                                    fontWeight = FontWeight.Bold)
                                Notice(labels.type)
                                DataRow("Стоимость вашей позиции", position.currentValue.moneyText())
                                DataRow(labels.quantity, position.quantity.quantityText())
                                DataRow("Результат позиции", position.expectedYieldAmount.moneyText(true))
                                position.expectedYieldPercent?.let { DataRow("Доходность, полученная от API", it.percentText()) }
                                DataRow("За день", position.dailyYieldAmount.moneyText(true))
                            }
                        }
                        item(key = "position-prices") {
                            CompactCard {
                                SectionHeading("Цена и ограничения")
                                DataRow("Текущая цена за единицу", position.currentPrice.moneyText())
                                DataRow("Средняя цена", position.averagePrice.moneyText())
                                labels.accrued?.let { DataRow(it, position.currentNkd.moneyText()) }
                                DataRow("Заблокированное количество", position.blockedQuantity.quantityText())
                                DataRow("Блокировка по данным API", if (position.blocked) "Да" else "Не отмечена")
                                if (position.blocked) Notice("Есть ограничения. Возможность сделки нужно уточнить в приложении брокера.")
                                Notice("Отсутствие отметки о блокировке не подтверждает, что торги сейчас доступны.")
                            }
                        }
                        item(key = "instrument-identifiers") {
                            CompactCard {
                                SectionHeading("Как найти инструмент")
                                SelectionContainer {
                                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                        DataRow("Тикер", position.ticker ?: "—")
                                        DataRow("ISIN", position.isin ?: "—")
                                        DataRow("Компания по данным API", position.company ?: "Не указана API")
                                        DataRow("Биржа", position.exchange ?: "—")
                                        DataRow("Отрасль", position.sector ?: "Не указана API")
                                        DataRow("Идентификатор", position.id)
                                    }
                                }
                                BrokerInstrumentActions(position.instrumentType, position.ticker, position.isin)
                                Notice("Переход открывает карточку брокера, а не создаёт заявку. Проверьте название, тикер и ISIN перед сделкой.")
                            }
                        }
                        item(key = "data-limitations") {
                            Notice("«—» означает, что значение не получено или не может быть корректно рассчитано. Цены и результаты показаны в валютах API, количество не переводится в лоты. Это сведения о позиции, не обещание дохода и не полный анализ компании.")
                        }
                    }
                }
            }
        }
    }
}
