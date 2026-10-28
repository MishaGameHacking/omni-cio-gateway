package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import ru.omnicio.app.ui.spectrum.*

@Composable
fun AutoSaveStatus(record: AutoSaveRecord?, retry: () -> Unit) {
    val loadingError = LocalWorkspaceAutoSave.current?.loadError
    val text = loadingError ?: when (record?.phase) {
        null -> "Изменения сохраняются автоматически"
        AutoSavePhase.Pending -> "Изменение ожидает сохранения"
        AutoSavePhase.Invalid -> "Черновик · заполните отмеченные параметры"
        AutoSavePhase.Saving -> "Сохраняем…"
        AutoSavePhase.Saved -> "Сохранено на сервере"
        AutoSavePhase.Failed -> record.error ?: "Сохранение не подтверждено"
    }
    Text(text, Modifier.semantics { liveRegion = LiveRegionMode.Polite }, style = MaterialTheme.typography.bodySmall,
        color = if (record?.phase == AutoSavePhase.Failed || loadingError != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
    if (record?.phase == AutoSavePhase.Failed || loadingError != null) SpectrumTextButton("Повторить сохранение", retry, symbol = SpectrumSymbol.Update)
}

