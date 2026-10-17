package ru.omnicio.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import java.math.BigDecimal
import ru.omnicio.app.ui.portfolio.HistoryChart
import ru.omnicio.app.ui.portfolio.HistoryPoint
import ru.omnicio.app.ui.spectrum.SpectrumTabs
import ru.omnicio.app.ui.workspace.*

/** Only src/debug may construct synthetic financial UI evidence. */
@Composable
internal fun WorkspaceVisualProbe(onBack: () -> Unit) {
    var section by remember { mutableIntStateOf(0) }
    var opened by remember { mutableStateOf(false) }
    WorkspaceDetailPage("Проверка UX100", "Тестовые состояния интерфейса", onBack) { insets ->
        Column(Modifier.fillMaxSize().padding(insets).consumeWindowInsets(insets)) {
            SpectrumTabs(listOf("План", "График", "Изменения", "События"), section, { section = it })
            LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("workspace-content"), contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)) {
                if (section == 0) item {
                    ActionPlan(listOf(PlanAction("fixture", "Проверить распределение", "Тестовый счёт", "Тестовый актив", "1 шт.", "500 ₽",
                        "Тест объяснения причины действия", "Синтетический источник", "2026-10-17", "2099-01-01T00:00:00Z", "10%", "9%",
                        listOf("Это визуальный тест. Сделки и вычисления не выполняются.")))) { opened = true }
                    if (opened) Text("Переход проверен · брокер не открывался")
                }
                if (section == 1) item {
                    BalanceVisibilityButton()
                    HistoryChart((1..17).filter { it != 8 }.map { day ->
                        HistoryPoint("2026-10-${day.toString().padStart(2, '0')}T10:00:00Z", BigDecimal(4000 + day * 30))
                    } + HistoryPoint("2026-10-17T11:00:00Z", BigDecimal("4480")), "RUB")

                }
                if (section == 2) item {
                    StrategyImpact(StrategyImpactUi(listOf(ImpactRow("Резерв", "10%", "15%"), ImpactRow("Компания", "8%", "5%")),
                        "2026-10-17", "Тестовый расчёт", "Синтетическое сравнение, не рекомендация"))
                }
                if (section == 3) item { NotificationGroup(NotificationGroupUi("test-event", "Обновления одного события", "2026-10-17", listOf("Первая проверка", "Уточнение источника"))) }
            }
        }
    }
}
