package ru.omnicio.app.ui.profile

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import org.json.JSONObject
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spectrum.SpectrumSwitch as Switch
import ru.omnicio.app.ui.theme.LocalThemePreference
import ru.omnicio.app.ui.workspace.*

/** One settings hierarchy. Server options show the acknowledged server value. */
@Composable
fun ProfileScreen(
    user: AnalystUser,
    tApiConfigured: Boolean,
    screenshotsBlocked: Boolean,
    onScreenshotsBlockedChange: (Boolean) -> Unit,
    onPortfolioClick: () -> Unit,
    onOpenTApi: () -> Unit,
    onOpenEducation: () -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val navigate = LocalWorkspaceNavigator.current
    val presentation = LocalWorkspacePreferences.current
    val resource = rememberWorkspaceResource("/automation/status")
    val status = resource.data?.takeIf { it.optInt("schema_version") == 1 }
    var appliedVersion by remember(user.telegramId) { mutableStateOf<Int?>(null) }
    var appliedEnabled by remember(user.telegramId) { mutableStateOf<Boolean?>(null) }
    var acknowledgementError by remember(user.telegramId) { mutableStateOf<String?>(null) }
    val save = rememberWorkspaceAction(onFailure = { resource.refresh() }) { response ->
        val acknowledgedEnabled = response.opt("enabled") as? Boolean
        val acknowledgedVersion = response.opt("version") as? Int
        if (acknowledgedEnabled != null && acknowledgedVersion != null && acknowledgedVersion >= 0) {
            appliedVersion = acknowledgedVersion
            appliedEnabled = acknowledgedEnabled
            acknowledgementError = null
        } else {
            acknowledgementError = "Сервер не подтвердил настройку. Проверяем сохранённое значение."
        }
        resource.refresh()
    }
    val observedVersion = status?.optInt("preference_version", -1) ?: -1
    val useAcknowledged = appliedVersion?.let { it > observedVersion } == true
    val version = if (useAcknowledged) appliedVersion ?: -1 else observedVersion
    val enabled = if (useAcknowledged) appliedEnabled == true else status?.optBoolean("enabled") == true
    val canEdit = version >= 0 && status != null && resource.error == null && !save.busy && !resource.busy
    val foreground = workspaceForeground()
    val refreshStatus by rememberUpdatedState(resource.refresh)
    LaunchedEffect(foreground) {
        if (foreground) while (isActive) { delay(20_000); refreshStatus() }
    }
    var dialog by rememberSaveable { mutableStateOf<String?>(null) }
    val broker = LocalBrokerConnection.current
    val brokerLabel = when {
        status?.optBoolean("broker_connected") == true -> "Доступ к данным подтверждён"
        status?.has("broker_connected") == true -> "Нужен токен для чтения данных"
        broker == BrokerConnectionState.Unknown -> "Статус подключения не получен"
        tApiConfigured -> "Подключение сохранено"
        else -> "Подключить данные счёта"
    }
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Profile, onPortfolioClick, {}) }) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).clipToBounds()
                .semantics { testTagsAsResourceId = true }.testTag("profile-content"),
                contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item(key = "settings-header") {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        ru.omnicio.app.ui.AnalystHeaderMenu()
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Настройки", style = MaterialTheme.typography.headlineLarge,
                                modifier = Modifier.semantics { heading() })
                            Text("Правила работы вашей системы", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                item(key = "automation-preference") {
                    SpectrumCard(modifier = Modifier.testTag("automation-preference")) {
                        SettingsToggle("Автоматический анализ",
                            when {
                                save.busy -> "Сохраняем настройку на сервере…"
                                version < 0 -> "Получаем сохранённую настройку"
                                !enabled -> "Новые фоновые проверки приостановлены"
                                status?.optBoolean("scheduler_enabled") != true -> "Включён в настройках; запуск на сервере ещё не подтверждён"
                                status?.optBoolean("broker_connected") != true -> "Ожидает подключения данных брокера"
                                else -> "Фоновые проверки включены"
                            }, enabled, canEdit, Modifier.testTag("automation-enabled")) { next ->
                            save.perform("/automation/preferences",
                                JSONObject().put("enabled", next).put("expected_version", version), method = "PUT")
                        }
                        resource.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                        save.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                        acknowledgementError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                        if (resource.busy && status == null) SpectrumLoadingIndicator(description = "Получаем настройку анализа")
                        if (resource.error != null)
                            SpectrumSecondaryButton("Повторить проверку", resource.refresh, Modifier.fillMaxWidth(),
                                enabled = !resource.busy && !save.busy)
                        Text("Переключатель меняет серверную настройку анализа. Он не включает реальные сделки.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item(key = "strategy-settings") {
                    SettingsGroup("Анализ и стратегия") {
                        SettingsLink("Моя стратегия", "Цель, горизонт, допустимый риск и ограничения", SpectrumSymbol.Goal) {
                            navigate(WorkspaceRoute.Strategies)
                        }
                        SettingsDivider()
                        SettingsLink("Правила анализа", "Риск, горизонт, денежный резерв и размер позиции", SpectrumSymbol.Analyst) {
                            navigate(WorkspaceRoute.AnalysisSettings)
                        }
                        SettingsDivider()
                        SettingsLink("Расходы и журнал", "Стоимость анализа, проверки и причины остановки", SpectrumSymbol.Pulse) {
                            navigate(WorkspaceRoute.AnalysisTimeline)
                        }
                    }
                }
                item(key = "connections-settings") {
                    SettingsGroup("Подключения") {
                        SettingsLink("Т-Инвестиции", brokerLabel, SpectrumSymbol.Sources, onClick = onOpenTApi)
                        SettingsDivider()
                        SettingsLink("Уведомления", "Время обзоров, важные события и тихие часы", SpectrumSymbol.Notifications) {
                            navigate(WorkspaceRoute.NotificationSettings)
                        }
                        SettingsDivider()
                        SettingsLink("Устройства", "Активные сеансы и отзыв доступа", SpectrumSymbol.Profile) {
                            navigate(WorkspaceRoute.Devices)
                        }
                    }
                }
                item(key = "appearance-settings") {
                    SettingsGroup("Интерфейс") {
                        SettingsLink("Оформление", "Единый стиль · движение и удобство", SpectrumSymbol.Settings) {
                            navigate(WorkspaceRoute.Appearance)
                        }
                        SettingsDivider()
                        SettingsToggle("Анимация", "Учитывает системное отключение движения",
                            presentation.value.motion != MotionLevel.OFF) { next ->
                            presentation.update(presentation.value.copy(motion = if (next) MotionLevel.LIVE else MotionLevel.OFF))
                        }
                        SettingsDivider()
                        SettingsToggle("Отклик касаний", "Короткая вибрация при действии", presentation.value.haptics) { next ->
                            presentation.update(presentation.value.copy(haptics = next))
                        }
                    }
                }
                item(key = "privacy-settings") {
                    SettingsGroup("Приватность") {
                        SettingsToggle("Запретить снимки экрана",
                            if (screenshotsBlocked) "Снимки и запись экрана заблокированы" else "Скриншоты разрешены",
                            screenshotsBlocked, onChange = onScreenshotsBlockedChange)
                        SettingsDivider()
                        SettingsLink("Безопасность", "Хранение доступа и режим работы", SpectrumSymbol.Risk,
                            modifier = Modifier.testTag("profile-security-action")) { dialog = "security" }
                    }
                }
                item(key = "account-settings") {
                    SettingsGroup("Аккаунт") {
                        Text(user.name?.takeIf(String::isNotBlank) ?: "Вход через Telegram",
                            style = MaterialTheme.typography.titleMedium)
                        SettingsLink("О приложении", "Версия " + BuildConfig.VERSION_NAME, SpectrumSymbol.Update) { dialog = "about" }
                        SettingsDivider()
                        SettingsLink("Выйти", "Завершить сеанс на этом устройстве", SpectrumSymbol.Profile, danger = true) {
                            dialog = "logout"
                        }
                    }
                }
            }
        }
    }
    when (dialog) {
        "security" -> SettingsInformation("Безопасность",
            "Доступ к брокерским данным хранится зашифрованным на сервере. Используйте токен для чтения данных. Сеанс на устройстве также зашифрован. Текущий режим не выставляет реальные торговые поручения. Для отзыва доступа отключите токен у брокера и в настройках подключения.") { dialog = null }
        "about" -> SettingsInformation("Analyst AI",
            "Версия " + BuildConfig.VERSION_NAME + " (" + BuildConfig.VERSION_CODE + "). Персональная система анализа. Независимое приложение, не официальное приложение Т-Банка. Доступность анализа зависит от подключённых источников и серверных настроек.") { dialog = null }
        "logout" -> WorkspaceDialog("Выйти из Analyst AI?", onDismiss = { dialog = null }) {
            Text("Для следующего входа потребуется подтверждение Telegram. Подключение брокера на сервере сохранится.")
            SpectrumPrimaryButton("Выйти", { dialog = null; onLogout() }, Modifier.fillMaxWidth())
            SpectrumSecondaryButton("Остаться", { dialog = null }, Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun SettingsGroup(title: String, content: @Composable ColumnScope.() -> Unit) {
    SpectrumCard {
        Text(title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { heading() })
        content()
    }
}

@Composable
private fun SettingsDivider() {
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
}

@Composable
private fun SettingsLink(title: String, subtitle: String, symbol: SpectrumSymbol,
    modifier: Modifier = Modifier, danger: Boolean = false, onClick: () -> Unit) {
    Row(modifier.fillMaxWidth().heightIn(min = 64.dp)
        .clickable(role = Role.Button, onClick = onClick).padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        SpatialIcon(symbol.asset, Modifier.size(28.dp),
            tint = if (danger) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
            motionAllowed = false)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium,
                color = if (danger) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
            Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        SpatialIcon(SpectrumSymbol.Forward.asset, Modifier.size(20.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant, motionAllowed = false)
    }
}

@Composable
private fun SettingsToggle(title: String, subtitle: String, checked: Boolean, enabled: Boolean = true,
    modifier: Modifier = Modifier, onChange: (Boolean) -> Unit) {
    val largeText = LocalDensity.current.fontScale > 1.3f
    Column(modifier.fillMaxWidth().heightIn(min = 64.dp)
        .toggleable(value = checked, enabled = enabled, role = Role.Switch, onValueChange = onChange)
        .padding(vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (!largeText) Switch(checked, onCheckedChange = null, enabled = enabled)
        }
        if (largeText) Switch(checked, onCheckedChange = null, enabled = enabled,
            modifier = Modifier.align(Alignment.End))
    }
}

@Composable
private fun SettingsInformation(title: String, body: String, close: () -> Unit) {
    WorkspaceDialog(title, onDismiss = close) {
        Text(body)
        SpectrumSecondaryButton("Понятно", close, Modifier.fillMaxWidth())
    }
}
