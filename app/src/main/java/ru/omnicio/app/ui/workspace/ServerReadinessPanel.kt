package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.platform.testTag
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.ui.spectrum.SpectrumSecondaryButton

/** Reads the existing authenticated status API, never schedules collection or model work. */
@Composable
internal fun ServerReadinessPanel() {
    DetailFold("Состояние сервера") {
        if (LocalInspectionMode.current) {
            Text("Для проверки состояния требуется соединение с вашим сервером.")
        } else {
            LiveServerReadiness()
        }
    }
}

@Composable
private fun LiveServerReadiness() {
    val resource = rememberWorkspaceResource("/workspace/system-readiness")
    WorkspaceRequestState(resource)
    Text("Приложение ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodySmall)
    val payload = resource.data
    if (payload != null) {
        val summary = serverReadinessSummary(payload)
        Text(summary.mode, style = MaterialTheme.typography.titleSmall)
        if (resource.error != null) {
            Text("Последний запрос не подтверждён. Ниже — ранее полученные сведения.",
                color = MaterialTheme.colorScheme.error)
        }
        if (!summary.supported) Text("Сервер вернул неподдерживаемый формат состояния.")
        Text("Проверка состояния: " + (summary.evaluatedAt?.let(::localMoment) ?: "время не получено"),
            style = MaterialTheme.typography.bodySmall)
        Text("Оценка портфеля: " + (summary.valuationAt?.let(::localMoment) ?: "время не получено"),
            style = MaterialTheme.typography.bodySmall)
        summary.lanes.forEachIndexed { index, lane ->
            Text(lane.title, style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.testTag("server-lane-$index"))
            Text(lane.state, style = MaterialTheme.typography.bodySmall)
            lane.observedAt?.let { Text(localMoment(it), style = MaterialTheme.typography.bodySmall) }
        }
        Text("Свежесть данных не подтверждает завершение анализа или готовность к торговле.",
            style = MaterialTheme.typography.bodySmall)
    }
    SpectrumSecondaryButton("Проверить состояние сервера", resource.refresh, Modifier.fillMaxWidth())
}
