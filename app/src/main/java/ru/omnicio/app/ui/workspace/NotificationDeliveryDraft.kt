package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumSecondaryButton

/** Scheduling has a server-backed editor; local drafts must not compete with it. */
@Composable
fun NotificationDeliverySettingsLink(enabled: Boolean) {
    val navigate = LocalWorkspaceNavigator.current
    SpectrumCard {
        Text("Расписание доставки", style = MaterialTheme.typography.titleLarge)
        Text("Часовой пояс, тихие часы и время обзоров задаются в настройках уведомлений. Изменения действуют после подтверждения сервера.")
        if (!enabled) Text("Завершите сохранение изменений инвестиционного профиля перед переходом.")
        SpectrumSecondaryButton("Настроить расписание доставки", {
            navigate(WorkspaceRoute.NotificationSettings)
        }, Modifier.fillMaxWidth(), enabled = enabled)
    }
}
