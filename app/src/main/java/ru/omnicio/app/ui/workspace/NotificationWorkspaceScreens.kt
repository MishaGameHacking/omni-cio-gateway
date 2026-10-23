package ru.omnicio.app.ui.workspace

import android.Manifest
import android.content.Intent
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.time.LocalTime
import java.time.ZoneId
import ru.omnicio.app.data.notifications.WorkspaceNotificationService
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spectrum.*

private const val NOTIFICATION_PREFERENCES_PATH = "/workspace/notifications/preferences"


@Composable
fun NotificationDeliveryRuntime() {
    val resource = rememberWorkspaceResource(NOTIFICATION_PREFERENCES_PATH)
    val context = LocalContext.current
    LaunchedEffect(resource.data) {
        val enabled = resource.data?.optJSONObject("preferences")?.optBoolean("enabled") ?: return@LaunchedEffect
        if (enabled) WorkspaceNotificationService.schedule(context) else WorkspaceNotificationService.cancel(context)
    }
}

@Composable
fun NotificationSettingsScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource(NOTIFICATION_PREFERENCES_PATH)
    val context = LocalContext.current
    var draft by rememberSaveable { mutableStateOf<String?>(null) }
    var draftVersion by rememberSaveable { mutableStateOf<Int?>(null) }
    var preview by remember { mutableStateOf<JSONObject?>(null) }
    var applied by remember { mutableStateOf<String?>(null) }
    var delivery by remember { mutableStateOf(WorkspaceNotificationService.canNotify(context)) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        delivery = granted && WorkspaceNotificationService.schedule(context)
    }
    val save = rememberWorkspaceAction(onFailure = { failure ->
        if (failure.reply.status == 409) resource.refresh()
    }) { result ->
        draft = result.optJSONObject("preferences")?.toString(); resource.refresh(); preview = null
        draftVersion = notificationPreferenceVersion(result)
        applied = result.optString("applied_at").takeIf(String::isNotBlank)
        val enabled = result.optJSONObject("preferences")?.optBoolean("enabled") == true
        if (!enabled) WorkspaceNotificationService.cancel(context) else delivery = WorkspaceNotificationService.schedule(context)
    }
    val simulate = rememberWorkspaceAction { preview = it }
    LaunchedEffect(resource.data) {
        if (draft == null) {
            draft = resource.data?.optJSONObject("preferences")?.toString()
            draftVersion = notificationPreferenceVersion(resource.data)
        }
    }
    val foreground = workspaceForeground()
    LaunchedEffect(foreground) { if (foreground) delivery = WorkspaceNotificationService.canNotify(context) }
    val config = remember(draft) { draft?.let(::JSONObject) }
    val edit: (String, Any) -> Unit = { key, value ->
        if (!save.busy && !simulate.busy) { draft = JSONObject(config?.toString() ?: "{}").put(key, value).toString(); applied = null; preview = null }
    }
    WorkspaceDetailPage("Уведомления", "Ваше время, условия и подтверждение применения", onBack, SpectrumSymbol.Notifications) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { WorkspaceRequestState(resource) }
            config?.let { settings ->
                item { SpectrumCard {
                    WorkspaceToggle("Получать события", "Применяется на сервере после сохранения", settings.optBoolean("enabled")) { edit("enabled", it) }
                    WorkspaceToggle("Утренние и вечерние обзоры", "Только по заданному времени", settings.optBoolean("briefs_enabled")) { edit("briefs_enabled", it) }
                    WorkspaceToggle("Критичные изменения", "По подтверждённым правилам риска", settings.optBoolean("critical_enabled")) { edit("critical_enabled", it) }
                } }
                item { SpectrumCard {
                    WorkspaceTextInput(settings.text("timezone", "Europe/Moscow"), { edit("timezone", it.take(80)) }, "Часовой пояс", Modifier.fillMaxWidth(), enabled = !save.busy)
                    Text("Например, Europe/Moscow. Все указанные ниже часы относятся к этому поясу.", style = MaterialTheme.typography.bodySmall)
                    listOf("morning" to "Утро", "evening" to "Вечер", "quiet_start" to "Тихие часы с", "quiet_end" to "Тихие часы до").forEach { (key, title) ->
                        WorkspaceTextInput(settings.text(key, ""), { edit(key, it.take(5)) }, title + " · ЧЧ:ММ", Modifier.fillMaxWidth(), enabled = !save.busy)
                    }
                    Text("Ночной интервал может переходить через полночь. Сервер проверяет тихие часы перед выдачей события устройству.")
                } }
                item { SpectrumCard(emphasized = true) {
                    val version = draftVersion
                    val valid = NotificationRulesStatus(settings, version, notificationPreferenceVersion(resource.data),
                        !save.busy && !simulate.busy && !resource.busy) {
                        draft = null; draftVersion = null; preview = null; applied = null; resource.refresh()
                    }
                    SpectrumPrimaryButton("Применить правила", {
                        save.perform(NOTIFICATION_PREFERENCES_PATH, JSONObject(settings.toString()).put("expected_version", checkNotNull(version)), "PUT")
                    }, Modifier.fillMaxWidth(), valid && !save.busy && !simulate.busy)
                    SpectrumSecondaryButton("Проверить на прошлых событиях", { simulate.perform("/workspace/notifications/preview", JSONObject().put("preferences", settings)) },
                        Modifier.fillMaxWidth(), valid && !save.busy && !simulate.busy)
                    WorkspaceActionState(save); WorkspaceActionState(simulate)
                    applied?.let { Text("Применено сервером: " + localMoment(it), color = LocalSpectrumPalette.current.emerald) }
                    if (applied == null) resource.data?.text("applied_at", "")?.takeIf(String::isNotBlank)?.let { Text("Последнее применение: " + localMoment(it)) }
                } }
            }
            item { SpectrumCard {
                Text("Доставка на это устройство", style = MaterialTheme.typography.titleMedium)
                Text(if (delivery) "Android разрешает показ уведомлений." else "Показ уведомлений пока не разрешён на устройстве.")
                Text("Устройство периодически получает события при доступной сети. Android может отложить проверку в фоновом режиме; мгновенная доставка не гарантируется. Все события доступны в приложении.")
                if (!delivery) SpectrumPrimaryButton("Разрешить уведомления", { permission.launch(Manifest.permission.POST_NOTIFICATIONS) }, Modifier.fillMaxWidth())
                SpectrumSecondaryButton("Настройки уведомлений Android", {
                    context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
                }, Modifier.fillMaxWidth())
            } }
            preview?.let { result -> item { NotificationPreview(result) } }
        }
    }
}

@Composable
private fun NotificationRulesStatus(settings: JSONObject, version: Int?, currentVersion: Int?,
    enabled: Boolean, reload: () -> Unit): Boolean {
    val rulesValid = notificationRulesValid(settings)
    if (!rulesValid) Text("Проверьте часовой пояс и время в формате 09:00. Утренний и вечерний обзоры должны приходить в разное время.",
        color = MaterialTheme.colorScheme.error)
    if (version == null) Text("Версия правил не получена. Обновите данные перед сохранением.")
    if (version != currentVersion) {
        Text("Правила изменились на другом устройстве. Загрузите их перед сохранением; текущий черновик будет заменён.")
        SpectrumSecondaryButton("Загрузить актуальные правила", reload, Modifier.fillMaxWidth(), enabled)
    }
    return rulesValid && version != null && version == currentVersion
}

@Composable
private fun NotificationPreview(result: JSONObject) {
    SpectrumCard {
        Text("Проверка на истории", style = MaterialTheme.typography.titleLarge)
        Text("Изучено событий: " + result.optInt("evaluated_count"))
        Text("Период: " + localMoment(result.text("history_start", "не получен")) + " — " + localMoment(result.text("history_end", "не получен")))
        Text("Это просмотр результата правил. Уведомления из этой проверки не отправляются.")
        listOf("matched" to "Подошли бы", "suppressed" to "Были бы отложены или исключены").forEach { (key, title) ->
            DetailFold(title + " · " + result.records(key).size) {
                result.records(key).forEach { event ->
                    Text(notificationTitle(event), style = MaterialTheme.typography.titleSmall)
                    Text(notificationReason(event.text("reason", "")), style = MaterialTheme.typography.bodySmall)
                    event.optString("eligible_at").takeIf(String::isNotBlank)?.let { Text(localMoment(it)) }
                }
            }
        }
    }
}

@Composable
fun NotificationEventsScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/notifications/events")
    val navigate = LocalWorkspaceNavigator.current
    var selected by rememberSaveable { mutableStateOf<String?>(null) }
    WorkspaceDetailPage("События", "Содержание и подтверждённые состояния доставки", onBack, SpectrumSymbol.Notifications) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { WorkspaceRequestState(resource) }
            item { SpectrumSecondaryButton("Настроить события", { navigate(WorkspaceRoute.NotificationSettings) }, Modifier.fillMaxWidth()) }
            if (resource.data?.records("items")?.isEmpty() == true) item { WorkspaceEmpty("Новых событий пока нет", "Здесь сохраняются обзоры и подтверждённые изменения портфеля по вашим правилам.") }
            resource.data?.records("items").orEmpty().forEach { event -> item(key = event.text("id")) { SpectrumCard(onClick = { selected = event.text("id") }) {
                Text(event.text("title"), style = MaterialTheme.typography.titleLarge)
                Text(event.text("body", ""))
                Text(notificationState(event.text("state")), Modifier.testTag("notification-state-" + event.text("id")),
                    style = MaterialTheme.typography.labelMedium)
                Text(localMoment(event.text("created_at", "")), style = MaterialTheme.typography.bodySmall)
            } } }
        }
    }
    selected?.let { id -> NotificationEventOverlay(id) { selected = null; resource.refresh() } }
}

@Composable
fun NotificationEventOverlay(id: String, onClose: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/notifications/events")
    val event = resource.data?.records("items")?.firstOrNull { it.text("id") == id }
    val openReport = LocalOpenAnalysisReport.current
    val read = rememberWorkspaceAction { onClose() }
    WorkspaceDialog(notificationTitle(event), onClose) {
        WorkspaceRequestState(resource)
        if (event != null) {
            Text(event.text("body", ""))
            Text(localMoment(event.text("created_at", "")), style = MaterialTheme.typography.bodySmall)
            Text(notificationState(event.text("state")))
            if (event.text("state") != "read") SpectrumPrimaryButton("Отметить прочитанным", {
                read.perform("/workspace/notifications/" + VolumeWorkspaceClient.encode(id) + "/ack", JSONObject().put("state", "read").put("claim_id", JSONObject.NULL))
            }, Modifier.fillMaxWidth(), !read.busy)
            if (!event.isNull("source_card_id")) SpectrumSecondaryButton("Открыть выводы аналитика", { onClose(); openReport(event.text("source_card_id")) }, Modifier.fillMaxWidth())
            WorkspaceActionState(read)
        } else if (!resource.busy) Text("Это событие недоступно в текущем аккаунте или уже вышло из доступного периода.")
        SpectrumSecondaryButton("Вернуться к работе", onClose, Modifier.fillMaxWidth())
    }
}

private fun notificationTitle(event: JSONObject?) = event?.text("title", "Событие") ?: "Событие"

private fun notificationPreferenceVersion(value: JSONObject?): Int? =
    value?.optInt("version", -1)?.takeIf { it >= 0 }

internal fun notificationRulesValid(value: JSONObject): Boolean = runCatching {
    ZoneId.of(value.getString("timezone"))
    value.getString("morning") != value.getString("evening") && listOf("morning", "evening", "quiet_start", "quiet_end").all { key ->
        val time = value.getString(key)
        if (!time.matches(Regex("\\d{2}:\\d{2}"))) false else { LocalTime.parse(time); true }
    }
}.getOrDefault(false)
private fun notificationState(state: String): String = when (state) {
    "pending" -> "Ожидает подходящего времени"; "claimed" -> "Устройство получило право на показ"; "presented" -> "Устройство сообщило о показе"
    "read" -> "Прочитано"; "suppressed" -> "Исключено правилами"; else -> "Состояние уточняется"
}
private fun notificationReason(reason: String) = when (reason) {
    "rule_disabled" -> "Исключено выключенными правилами доставки"
    "quiet_hours" -> "Тихие часы"; "disabled" -> "Уведомления выключены"; "briefs_disabled" -> "Обзоры выключены"; "critical_disabled" -> "Критичные события выключены"
    "eligible", "matched" -> "Соответствует правилам"; else -> "Результат по сохранённым условиям"
}
