package ru.omnicio.app.ui.home

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spatial.SpatialWindow
import ru.omnicio.app.ui.workspace.WorkspaceGestureHint

internal val dashboardCards = linkedMapOf(
    "assistant" to "Следующий шаг", "changes" to "С прошлого посещения", "composition" to "Состав капитала",
    "attribution" to "Причины изменения", "payouts" to "Выплаты", "goal" to "Цель и резерв",
    "monitoring" to "Наблюдение", "allocation" to "Распределение",
)

internal fun normalizedDashboardOrder(saved: List<String>): List<String> =
    saved.filter { it in dashboardCards }.distinct().let { known -> known + dashboardCards.keys.filterNot(known::contains) }

internal fun moveDashboardCard(order: List<String>, id: String, delta: Int): List<String> {
    val from = order.indexOf(id)
    if (from < 0) return order
    val target = (from + delta).coerceIn(0, order.lastIndex)
    return order.toMutableList().apply { removeAt(from); add(target, id) }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun DashboardOrderEditor(order: List<String>, saved: List<String>, busy: Boolean, error: String?,
    onPreview: (List<String>) -> Unit, onSave: () -> Unit, onClose: () -> Unit) {
    val currentOrder by rememberUpdatedState(order)
    val change by rememberUpdatedState(onPreview)
    val rowHeight = with(LocalDensity.current) { 76.dp.toPx() }
    var dragging by remember { mutableStateOf<String?>(null) }
    var drift by remember { mutableFloatStateOf(0f) }
    ModalBottomSheet(onDismissRequest = onClose, dragHandle = null) {
        SpatialWindow(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Порядок главного экрана", style = MaterialTheme.typography.titleLarge)
            Text("Удерживайте карточку и перемещайте вверх или вниз. Порядок на главном меняется в режиме просмотра до сохранения.")
            WorkspaceGestureHint("dashboard-reorder", "Порядок карточек",
                "Удерживайте карточку для перемещения. Кнопки «Выше» и «Ниже» меняют порядок без жестов; результат применяется после сохранения.")
            order.forEachIndexed { index, id ->
                key(id) {
                    ru.omnicio.app.ui.spatial.SpatialSurface(color = if (dragging == id) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
                        state = if (dragging == id) ru.omnicio.app.ui.spatial.SpatialState.Selected else ru.omnicio.app.ui.spatial.SpatialState.Idle,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 68.dp).pointerInput(id, busy) {
                            if (!busy) detectDragGesturesAfterLongPress(
                                onDragStart = { dragging = id; drift = 0f },
                                onDragEnd = { dragging = null; drift = 0f },
                                onDragCancel = { dragging = null; drift = 0f },
                                onDrag = { changePointer, amount ->
                                    changePointer.consume(); drift += amount.y
                                    if (drift >= rowHeight || drift <= -rowHeight) {
                                        val step = if (drift > 0f) 1 else -1
                                        change(moveDashboardCard(currentOrder, id, step)); drift -= rowHeight * step
                                    }
                                },
                            )
                        }.semantics { stateDescription = "Позиция ${index + 1} из ${order.size}" }) {
                        Row(Modifier.padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            SpectrumIcon(SpectrumSymbol.Portfolio, Modifier.size(28.dp), selected = dragging == id)
                            Text(dashboardCards.getValue(id), Modifier.weight(1f).padding(horizontal = 8.dp))
                            TextButton(onClick = { onPreview(moveDashboardCard(order, id, -1)) }, enabled = index > 0 && !busy) { Text("Выше") }
                            TextButton(onClick = { onPreview(moveDashboardCard(order, id, 1)) }, enabled = index < order.lastIndex && !busy) { Text("Ниже") }
                        }
                    }
                }
            }
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            SpectrumPrimaryButton(if (busy) "Сохраняем…" else "Сохранить порядок", onSave, Modifier.fillMaxWidth(), enabled = !busy && order != saved)
            TextButton(onClick = { onPreview(saved) }, enabled = !busy && order != saved, modifier = Modifier.fillMaxWidth()) { Text("Отменить изменения порядка") }
            TextButton(onClick = onClose, modifier = Modifier.fillMaxWidth()) { Text("Закрыть") }
            Spacer(Modifier.windowInsetsBottomHeight(WindowInsets.safeDrawing).heightIn(min = 16.dp))
        }
        }
    }
}
