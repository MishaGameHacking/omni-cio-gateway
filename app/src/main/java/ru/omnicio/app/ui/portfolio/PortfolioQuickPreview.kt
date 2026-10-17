package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.data.workspace.rememberPersonalWorkspace
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spatial.SpatialWindow
import ru.omnicio.app.ui.workspace.WorkspaceGestureHint

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun PortfolioQuickPreview(position: PortfolioPosition, accountName: String?, close: () -> Unit, open: () -> Unit) {
    ModalBottomSheet(onDismissRequest = close, dragHandle = null) {
        SpatialWindow(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).navigationBarsPadding().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            WorkspaceGestureHint("position-preview", "Краткий просмотр позиции",
                "Удержание открывает эту сводку. Кнопка «Кратко» в строке делает то же самое; полная карточка доступна ниже.")
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                SpectrumAssetMark(position.instrumentType, position.title, Modifier.size(56.dp))
                Column { Text(position.title, style = MaterialTheme.typography.titleLarge); accountName?.let { Text(it) } }
            }
            DataRow("Стоимость", position.currentValue.moneyText())
            DataRow("Цена", position.currentPrice.moneyText())
            Text(if (position.blocked) "Есть ограничения у брокера" else "Источник: текущие сведения T‑Invest")
            WatchPositionAction(position)
            SpectrumPrimaryButton("Открыть карточку", open, Modifier.fillMaxWidth())
            SpectrumSecondaryButton("Закрыть", close, Modifier.fillMaxWidth())
        }
        }
    }
}

@Composable
internal fun WatchPositionAction(position: PortfolioPosition) {
    val personal = rememberPersonalWorkspace()
    val watch = personal.watches.firstOrNull { it.uid == position.id }
    var editor by rememberSaveable(position.id) { mutableStateOf(false) }
    var reason by rememberSaveable(position.id, watch?.reason) { mutableStateOf(watch?.reason ?: "") }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        TextButton(onClick = { editor = true }, enabled = personal.loaded && !personal.busy) {
            Text(if (watch == null) "Наблюдать" else "Причина наблюдения")
        }
        if (watch != null) TextButton(onClick = { personal.unwatch(position.id) }, enabled = !personal.busy) { Text("Убрать из наблюдения") }
    }
    personal.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    if (editor) AlertDialog(onDismissRequest = { editor = false }, title = { Text("Зачем наблюдаем?") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(position.title)
            SpectrumTextField(reason, { reason = it.take(800) }, label = { Text("Ваша причина или вопрос") }, modifier = Modifier.fillMaxWidth())
            Text("Личная отметка сохраняется на этом устройстве. Она не является сигналом на сделку.", style = MaterialTheme.typography.bodySmall)
        }
    }, confirmButton = { TextButton(onClick = { personal.watch(position.id, position.title, reason); editor = false },
        enabled = reason.isNotBlank() && !personal.busy) { Text("Сохранить") } },
        dismissButton = { TextButton(onClick = { editor = false }) { Text("Отмена") } })
}
