package ru.omnicio.app.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.ui.theme.OmniSpacing

private const val ANDROID_LABEL = "Android"
private const val STATUS_LABEL = "Статус"

@Composable
internal fun SettingsScreen(
    uiState: AppUiState,
    onBack: () -> Unit,
    onDeletePortfolio: () -> Unit,
    onRestoreDemoPortfolio: () -> Unit,
    onConnectBrokerFixture: () -> Unit,
    onDisconnectBroker: () -> Unit,
    onRevokeBrokerFixture: () -> Unit,
    onRetryMigration: () -> Unit,
    onReserveMinor: (Long) -> Unit,
    onGoalHorizonYears: (Int) -> Unit,
    onNotificationsEnabled: (Boolean) -> Unit,
    onFastAlertsEnabled: (Boolean) -> Unit,
    onDarkTheme: (Boolean) -> Unit,
) {
    val settings = uiState.settings
    var brokerExpanded by rememberSaveable { mutableStateOf(false) }
    var goalsExpanded by rememberSaveable { mutableStateOf(false) }
    var notificationsExpanded by rememberSaveable { mutableStateOf(false) }
    var privacyExpanded by rememberSaveable { mutableStateOf(false) }
    var subscriptionExpanded by rememberSaveable { mutableStateOf(false) }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .safeDrawingPadding(),
        contentPadding = PaddingValues(
            start = OmniSpacing.lg,
            end = OmniSpacing.lg,
            top = OmniSpacing.sm,
            bottom = OmniSpacing.xxl,
        ),
        verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
    ) {
        item { SettingsHeader(onBack = onBack) }
        item {
            ThemeCard(
                darkTheme = settings.darkTheme,
                onDarkTheme = onDarkTheme,
            )
        }
        item {
            ExpandableSettingsCard(
                title = "Подключение T-Invest",
                subtitle = when {
                    settings.brokerRevoked -> "Доступ отозван · демо"
                    settings.brokerConnected -> "Подключено · демо"
                    else -> "Не подключено · только чтение"
                },
                marker = "↗",
                expanded = brokerExpanded,
                onToggle = { brokerExpanded = !brokerExpanded },
            ) {
                BrokerDetails(
                    settings = settings,
                    onConnect = onConnectBrokerFixture,
                    onDisconnect = onDisconnectBroker,
                    onRevoke = onRevokeBrokerFixture,
                )
            }
        }
        item {
            ExpandableSettingsCard(
                title = "Цели и резерв",
                subtitle = "Резерв " +
                    formatMoney(settings.reserveMinor, DisplayCurrency.RUB, hidden = false) +
                    " · горизонт " + settings.goalHorizonYears + " г.",
                marker = "◎",
                expanded = goalsExpanded,
                onToggle = { goalsExpanded = !goalsExpanded },
            ) {
                GoalReserveDetails(
                    settings = settings,
                    onReserveMinor = onReserveMinor,
                    onGoalHorizonYears = onGoalHorizonYears,
                )
            }
        }
        item {
            ExpandableSettingsCard(
                title = "Уведомления",
                subtitle = if (settings.notificationsEnabled) {
                    "Включены · важные события"
                } else {
                    "Выключены"
                },
                marker = "◉",
                expanded = notificationsExpanded,
                onToggle = { notificationsExpanded = !notificationsExpanded },
            ) {
                NotificationsDetails(
                    settings = settings,
                    onNotificationsEnabled = onNotificationsEnabled,
                    onFastAlertsEnabled = onFastAlertsEnabled,
                )
            }
        }
        item {
            ExpandableSettingsCard(
                title = "Конфиденциальность",
                subtitle = "Локальные данные, экспорт и удаление",
                marker = "◇",
                expanded = privacyExpanded,
                onToggle = { privacyExpanded = !privacyExpanded },
            ) {
                PrivacyDetails(
                    uiState = uiState,
                    onDeletePortfolio = onDeletePortfolio,
                    onRestoreDemoPortfolio = onRestoreDemoPortfolio,
                    onRetryMigration = onRetryMigration,
                )
            }
        }
        item {
            ExpandableSettingsCard(
                title = "Подписка",
                subtitle = "Покупки пока не подключены",
                marker = "♛",
                expanded = subscriptionExpanded,
                onToggle = { subscriptionExpanded = !subscriptionExpanded },
            ) {
                SubscriptionDetails()
            }
        }
        item { AboutCard() }
    }
}

@Composable
private fun SettingsHeader(onBack: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
    ) {
        TextButton(onClick = onBack) {
            Text("‹")
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = "Настройки",
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                text = "Управляйте приложением под себя",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun ThemeCard(
    darkTheme: Boolean,
    onDarkTheme: (Boolean) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(OmniSpacing.md),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
        ) {
            Text(
                text = if (darkTheme) "●" else "○",
                color = MaterialTheme.colorScheme.primary,
                style = MaterialTheme.typography.headlineMedium,
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = if (darkTheme) "Тёмная тема" else "Светлая тема",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = if (darkTheme) "Оттенки чёрного" else "Светлые нейтральные оттенки",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Switch(
                checked = darkTheme,
                onCheckedChange = onDarkTheme,
                modifier = Modifier.semantics { contentDescription = "Тёмная тема" },
            )
        }
    }
}

@Composable
private fun ExpandableSettingsCard(
    title: String,
    subtitle: String,
    marker: String,
    expanded: Boolean,
    onToggle: () -> Unit,
    details: @Composable () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onToggle),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(OmniSpacing.md),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
            ) {
                Text(
                    text = marker,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.headlineSmall,
                )
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = if (expanded) "⌃" else "›",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.titleLarge,
                )
            }
            if (expanded) {
                HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.35f))
                Column(
                    modifier = Modifier.padding(OmniSpacing.md),
                    verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
                ) {
                    details()
                }
            }
        }
    }
}

@Composable
private fun BrokerDetails(
    settings: LocalSettingsState,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onRevoke: () -> Unit,
) {
    Text(
        text = "Реальный токен в версии 2.5.1 ещё не запрашивается. Здесь доступен безопасный демо-контур.",
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    when {
        settings.brokerConnected -> {
            CompactStatusLine(STATUS_LABEL, "Подключено · демо")
            OutlinedButton(onClick = onRevoke, modifier = Modifier.fillMaxWidth()) {
                Text("QA · отозвать демо-доступ")
            }
            Button(onClick = onDisconnect, modifier = Modifier.fillMaxWidth()) {
                Text("Отключить демо-доступ")
            }
        }
        settings.brokerRevoked -> {
            CompactStatusLine(STATUS_LABEL, "Доступ отозван · демо")
            Button(onClick = onConnect, modifier = Modifier.fillMaxWidth()) {
                Text("Переподключить демо-режим")
            }
            OutlinedButton(onClick = onDisconnect, modifier = Modifier.fillMaxWidth()) {
                Text("Очистить демо-состояние")
            }
        }
        else -> {
            CompactStatusLine(STATUS_LABEL, "Не подключено")
            Button(onClick = onConnect, modifier = Modifier.fillMaxWidth()) {
                Text("Включить демо-режим чтения")
            }
        }
    }
}

@Composable
private fun GoalReserveDetails(
    settings: LocalSettingsState,
    onReserveMinor: (Long) -> Unit,
    onGoalHorizonYears: (Int) -> Unit,
) {
    Text("Резерв", style = MaterialTheme.typography.labelLarge)
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
    ) {
        reservePresetsMinor().forEach { reserve ->
            FilterChip(
                selected = reserve == settings.reserveMinor,
                onClick = { onReserveMinor(reserve) },
                label = { Text(formatMoney(reserve, DisplayCurrency.RUB, hidden = false)) },
            )
        }
    }
    Text("Горизонт цели", style = MaterialTheme.typography.labelLarge)
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
    ) {
        goalHorizonPresets().forEach { years ->
            FilterChip(
                selected = years == settings.goalHorizonYears,
                onClick = { onGoalHorizonYears(years) },
                label = { Text(years.toString() + " г.") },
            )
        }
    }
}

@Composable
private fun NotificationsDetails(
    settings: LocalSettingsState,
    onNotificationsEnabled: (Boolean) -> Unit,
    onFastAlertsEnabled: (Boolean) -> Unit,
) {
    ToggleRow(
        label = "Важные уведомления",
        checked = settings.notificationsEnabled,
        onChecked = onNotificationsEnabled,
    )
    ToggleRow(
        label = "Быстрые уведомления",
        checked = settings.fastAlertsEnabled,
        enabled = settings.notificationsEnabled,
        onChecked = onFastAlertsEnabled,
    )
    NotificationPermissionCard(notificationsEnabled = settings.notificationsEnabled)
    RuntimeEnvironmentCard()
}

@Composable
private fun PrivacyDetails(
    uiState: AppUiState,
    onDeletePortfolio: () -> Unit,
    onRestoreDemoPortfolio: () -> Unit,
    onRetryMigration: () -> Unit,
) {
    val context = LocalContext.current
    val settings = uiState.settings
    CompactStatusLine(
        "Данные",
        if (settings.portfolioPresent) "Локальный демо-портфель" else "Портфель удалён",
    )
    CompactStatusLine("ID устройства", installationIdLabel(uiState.installationId))
    CompactStatusLine("Схема данных", uiState.migrationStatus.label)
    if (uiState.migrationStatus == LocalMigrationStatus.FAILED) {
        Button(onClick = onRetryMigration, modifier = Modifier.fillMaxWidth()) {
            Text("Повторить локальную миграцию")
        }
    }
    OutlinedButton(
        onClick = {
            val sendIntent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, buildLocalExportSummary(settings))
            }
            runCatching {
                context.startActivity(Intent.createChooser(sendIntent, "Экспорт OMNICIO"))
            }
        },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Экспортировать локально")
    }
    if (settings.portfolioPresent) {
        Button(onClick = onDeletePortfolio, modifier = Modifier.fillMaxWidth()) {
            Text("Удалить локальный демо-портфель")
        }
    } else {
        Button(onClick = onRestoreDemoPortfolio, modifier = Modifier.fillMaxWidth()) {
            Text("Восстановить демо-портфель")
        }
    }
    Text(
        text = "Брокерский токен в экспорт не включается.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun SubscriptionDetails() {
    StatusPill("RUSTORE PAY ПОКА НЕ ПОДКЛЮЧЁН")
    subscriptionTiers().forEach { tier ->
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(tier.name, fontWeight = FontWeight.SemiBold)
                Text(
                    tier.status,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                text = if (tier.available) "Доступно" else "Позже",
                style = MaterialTheme.typography.labelMedium,
                color = if (tier.available) {
                    MaterialTheme.colorScheme.tertiary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }
    }
}

@Composable
private fun NotificationPermissionCard(
    notificationsEnabled: Boolean,
) {
    val context = LocalContext.current
    val required = notificationPermissionRequired(Build.VERSION.SDK_INT)
    var granted by rememberSaveable { mutableStateOf(safeNotificationPermissionGranted(context)) }
    var attempted by rememberSaveable { mutableStateOf(false) }
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { result ->
        attempted = true
        granted = result
    }

    when {
        !notificationsEnabled -> CompactStatusLine(ANDROID_LABEL, "Системный запрос не нужен")
        !required -> CompactStatusLine(ANDROID_LABEL, "Отдельное разрешение не требуется")
        granted -> CompactStatusLine(ANDROID_LABEL, "Разрешение выдано")
        else -> {
            CompactStatusLine(
                "Android",
                if (attempted) "Разрешение отклонено" else "Разрешение не выдано",
            )
            Button(
                onClick = {
                    attempted = true
                    launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Разрешить уведомления")
            }
            if (attempted) {
                OutlinedButton(
                    onClick = {
                        runCatching {
                            context.startActivity(
                                Intent(
                                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                    Uri.parse("package:" + context.packageName),
                                ),
                            )
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Открыть настройки Android")
                }
                TextButton(
                    onClick = { granted = safeNotificationPermissionGranted(context) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Проверить разрешение")
                }
            }
        }
    }
}

@Composable
private fun RuntimeEnvironmentCard() {
    val context = LocalContext.current
    Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs)) {
        Text("Ограничения Android", style = MaterialTheme.typography.labelLarge)
        CompactStatusLine("Батарея", powerSaverLabelSafe(safePowerSaver(context)))
        CompactStatusLine("Трафик", dataSaverLabelSafe(safeDataSaver(context)))
    }
}

private fun safeNotificationPermissionGranted(context: Context): Boolean = runCatching {
    !notificationPermissionRequired(Build.VERSION.SDK_INT) ||
        context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
        PackageManager.PERMISSION_GRANTED
}.getOrDefault(false)

private fun safePowerSaver(context: Context): Boolean? = runCatching {
    context.getSystemService(PowerManager::class.java)?.isPowerSaveMode
}.getOrNull()

private fun safeDataSaver(context: Context): Boolean? = runCatching {
    context.getSystemService(ConnectivityManager::class.java)?.restrictBackgroundStatus ==
        ConnectivityManager.RESTRICT_BACKGROUND_STATUS_ENABLED
}.getOrNull()

private fun powerSaverLabelSafe(enabled: Boolean?): String = when (enabled) {
    true -> "Экономия включена"
    false -> "Без ограничений"
    null -> "Не удалось определить"
}

private fun dataSaverLabelSafe(enabled: Boolean?): String = when (enabled) {
    true -> "Фоновый трафик ограничен"
    false -> "Без ограничений"
    null -> "Не удалось определить"
}

@Composable
private fun ToggleRow(
    label: String,
    checked: Boolean,
    enabled: Boolean = true,
    onChecked: (Boolean) -> Unit,
) {
    val largeFont = shouldStackDetailLine(LocalDensity.current.fontScale)
    if (largeFont) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Text(label)
            Switch(
                checked = checked,
                enabled = enabled,
                onCheckedChange = onChecked,
                modifier = Modifier.semantics { contentDescription = label },
            )
        }
    } else {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = label, modifier = Modifier.weight(1f))
            Switch(
                checked = checked,
                enabled = enabled,
                onCheckedChange = onChecked,
                modifier = Modifier.semantics { contentDescription = label },
            )
        }
    }
}

@Composable
private fun CompactStatusLine(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
    ) {
        Text(
            text = label,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(0.8f),
        )
        Text(text = value, modifier = Modifier.weight(1.4f))
    }
}

@Composable
private fun AboutCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xxs),
        ) {
            Text("О приложении", fontWeight = FontWeight.SemiBold)
            Text(
                text = "OMNICIO " + BuildConfig.VERSION_NAME +
                    " · код " + BuildConfig.VERSION_CODE +
                    " · " + BuildConfig.APPLICATION_ID,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
