package ru.omnicio.app.ui.workspace

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton
import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import ru.omnicio.app.ui.spectrum.*

@Composable
fun NotificationDeliveryDraft() {
    val user = LocalWorkspaceSession.current.userId
    val context = LocalContext.current
    val store = remember(user) { context.getSharedPreferences("notification_draft_$user", 0) }
    var frequency by remember(user) { mutableIntStateOf(store.getInt("frequency", 1).coerceIn(0, 2)) }
    var quiet by remember(user) { mutableStateOf(store.getBoolean("quiet", false)) }
    var from by remember(user) { mutableIntStateOf(store.getInt("from", 22).coerceIn(0, 23)) }
    var until by remember(user) { mutableIntStateOf(store.getInt("until", 8).coerceIn(0, 23)) }
    var picker by remember { mutableStateOf<String?>(null) }
    var saved by remember { mutableStateOf(false) }
    DetailFold("Расписание доставки · черновик") {
        SpectrumBadge("Не применяется сервером")
        WorkspaceChoices("Информационные обзоры", listOf("Сразу", "Раз в день", "Раз в неделю"), frequency) { frequency = it; saved = false }
        WorkspaceToggle("Тихие часы", "Часовой пояс устройства: ${java.time.ZoneId.systemDefault().id}", quiet) { quiet = it; saved = false }
        if (quiet) Row {
            TextButton(onClick = { picker = "from" }) { Text("С ${from.toString().padStart(2, '0')}:00") }
            TextButton(onClick = { picker = "until" }) { Text("До ${until.toString().padStart(2, '0')}:00") }
        }
        Text("Действующие переключатели ниже сохраняются на сервере. Это расписание начнёт работать после подключения доставки.")
        SpectrumSecondaryButton(if (saved) "Черновик сохранён" else "Сохранить расписание", {
            store.edit().putInt("frequency", frequency).putBoolean("quiet", quiet).putInt("from", from).putInt("until", until).apply(); saved = true
        }, Modifier.fillMaxWidth(), enabled = !saved && (!quiet || from != until))
        if (quiet && from == until) Text("Укажите разное время начала и окончания.", color = MaterialTheme.colorScheme.error)
    }
    if (picker != null) AlertDialog(onDismissRequest = { picker = null }, title = { Text("Час · время устройства") },
        text = { Column { (0..7).forEach { row -> Row { (0..2).forEach { column -> val hour = row * 3 + column
            TextButton(onClick = { if (picker == "from") from = hour else until = hour; picker = null; saved = false }) { Text("${hour.toString().padStart(2, '0')}:00") }
        } } } } }, confirmButton = { TextButton(onClick = { picker = null }) { Text("Отмена") } })
}
