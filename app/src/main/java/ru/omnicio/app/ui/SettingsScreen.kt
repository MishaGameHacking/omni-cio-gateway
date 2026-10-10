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
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.ui.theme.OmniSpacing

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
) {
    val context = LocalContext.current
    val settings = uiState.settings

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .safeDrawingPadding()
            .padding(horizontal = OmniSpacing.lg),
        verticalArrangement = Arrangement.spacedBy(OmniSpacing.md),
    ) {
        item {
            TextButton(onClick = onBack) {
                Text("← Назад")
            }
        }
        item {
            StatusPill("ДЕМО · UI-06 · RELEASE CANDIDATE UX")
        }
        item {
            Text(
                text = "Настройки",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.semantics { heading() },
            )
        }
        item {
            MigrationStatusCard(
                status = uiState.migrationStatus,
                onRetry = onRetryMigration,
            )
        }
        item {
            DeviceDataCard(
                settings = settings,
                onExport = {
                    val sendIntent = Intent(Intent.ACTION_SEND).apply {
                        type = "text/plain"
                        putExtra(Intent.EXTRA_TEXT, buildLocalExportSummary(settings))
                    }
                    context.startActivity(
                        Intent.createChooser(sendIntent, "Экспорт OMNICIO"),
                    )
                },
                onDelete = onDeletePortfolio,
                onRestore = onRestoreDemoPortfolio,
            )
        }
        item {
            BrokerCard(
                settings = settings,
                onConnect = onConnectBrokerFixture,
                onDisconnect = onDisconnectBroker,
                onRevoke = onRevokeBrokerFixture,
            )
        }
        item {
            SettingsSectionTitle("Общие источники")
        }
        commonSourceCategories().forEach { source ->
            item {
                InfoCard(
                    title = source.name,
                    body = source.detail,
                )
            }
        }
        item {
            GoalReserveCard(
                settings = settings,
                onReserveMinor = onReserveMinor,
                onGoalHorizonYears = onGoalHorizonYears,
            )
        }
        item {
            NotificationsCard(
                settings = settings,
                onNotificationsEnabled = onNotificationsEnabled,
                onFastAlertsEnabled = onFastAlertsEnabled,
            )
        }
        item {
            NotificationPermissionCard()
        }
        item {
            RuntimeEnvironmentCard()
        }
        item {
            SubscriptionCard()
        }
        item {
            InfoCard(
                title = "О приложении",
                body = "OMNICIO " + BuildConfig.VERSION_NAME +
                    " · versionCode " + BuildConfig.VERSION_CODE +
                    " · package " + BuildConfig.APPLICATION_ID +
                    ". Android local-first UI. Privacy, документы и перечень источников остаются прозрачными. " +
                    "Скриншоты на текущих demo/UI-экранах не блокируются: секреты здесь не отображаются, " +
                    "а accessibility не ограничивается без необходимости.",
            )
        }
    }
}

@Composable
private fun DeviceDataCard(
    settings: LocalSettingsState,
    onExport: () -> Unit,
    onDelete: () -> Unit,
    onRestore: () -> Unit,
) {
    SettingsCard(title = "Данные на устройстве") {
        Text(
            text = if (settings.portfolioPresent) {
                "Локальный portfolio fixture: 1,8 МБ · обновлён сегодня · demo."
            } else {
                "Локальный portfolio fixture удалён · 0 Б."
            },
        )
        Text(
            text = "Экспорт формируется локально и не включает broker credential.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedButton(
            onClick = onExport,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Экспортировать локально")
        }
        if (settings.portfolioPresent) {
            Button(
                onClick = onDelete,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Удалить портфель и broker credential")
            }
        } else {
            Button(
                onClick = onRestore,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Восстановить demo-fixture")
            }
        }
    }
}

@Composable
private fun BrokerCard(
    settings: LocalSettingsState,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
    onRevoke: () -> Unit,
) {
    SettingsCard(title = "T-Invest · read-only") {
        Text(
            text = when {
                settings.brokerRevoked ->
                    "Credential отозван · UI-fixture. Зависимые jobs остановлены."
                settings.brokerConnected ->
                    "Подключено · UI-fixture. Credential отмечен как локальный."
                else ->
                    "Не подключено. Реальный read-only token появится только на системном этапе."
            },
        )
        Text(
            text = "Credential: " +
                if (settings.brokerCredentialPresent) "локально присутствует · fixture" else "отсутствует",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = "Зависимые jobs: " +
                if (settings.dependentJobsRunning) "fixture запущены" else "остановлены",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        when {
            settings.brokerConnected -> {
                OutlinedButton(
                    onClick = onConnect,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Переподключить fixture")
                }
                OutlinedButton(
                    onClick = onRevoke,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("QA · пометить credential отозванным")
                }
                Button(
                    onClick = onDisconnect,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Отключить и очистить локальный credential")
                }
            }
            settings.brokerRevoked -> {
                Button(
                    onClick = onConnect,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Переподключить read-only fixture")
                }
                OutlinedButton(
                    onClick = onDisconnect,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Очистить отозванный credential")
                }
            }
            else -> {
                Button(
                    onClick = onConnect,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Подключить read-only fixture")
                }
            }
        }
    }
}

@Composable
private fun GoalReserveCard(
    settings: LocalSettingsState,
    onReserveMinor: (Long) -> Unit,
    onGoalHorizonYears: (Int) -> Unit,
) {
    SettingsCard(title = "Цели и резерв") {
        Text(
            text = "Резерв для локальных сценариев: " +
                formatMoney(settings.reserveMinor, DisplayCurrency.RUB, hidden = false),
        )
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            reservePresetsMinor().forEach { reserve ->
                FilterChip(
                    selected = reserve == settings.reserveMinor,
                    onClick = { onReserveMinor(reserve) },
                    label = {
                        Text(formatMoney(reserve, DisplayCurrency.RUB, hidden = false))
                    },
                )
            }
        }
        Text("Горизонт цели: " + settings.goalHorizonYears + " г.")
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
}

@Composable
private fun NotificationsCard(
    settings: LocalSettingsState,
    onNotificationsEnabled: (Boolean) -> Unit,
    onFastAlertsEnabled: (Boolean) -> Unit,
) {
    SettingsCard(title = "Уведомления") {
        ToggleRow(
            label = "Локальные/background уведомления",
            checked = settings.notificationsEnabled,
            onChecked = onNotificationsEnabled,
        )
        ToggleRow(
            label = "Optional fast alerts",
            checked = settings.fastAlertsEnabled,
            enabled = settings.notificationsEnabled,
            onChecked = onFastAlertsEnabled,
        )
        Text(
            text = "Обычный push не содержит суммы портфеля и персональные позиции.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun SubscriptionCard() {
    SettingsCard(title = "Подписка") {
        StatusPill("TEST MODE · RUSTORE PAY НЕ ПОДКЛЮЧЁН")
        Text(
            text = "Цены не показываются: платёжный SDK и production entitlement ещё не подключены.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        subscriptionTiers().forEach { tier ->
            Column(
                verticalArrangement = Arrangement.spacedBy(OmniSpacing.xxs),
                modifier = Modifier.padding(vertical = OmniSpacing.xs),
            ) {
                Text(
                    text = tier.name,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = tier.status,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = when {
                        tier.purchasable -> "Можно приобрести"
                        tier.available -> "Доступно без покупки"
                        else -> "Недоступно"
                    },
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
        Text(
            text = "Семейного тарифа и связанных аккаунтов нет.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun ToggleRow(
    label: String,
    checked: Boolean,
    enabled: Boolean = true,
    onChecked: (Boolean) -> Unit,
) {
    val switch: @Composable () -> Unit = {
        Switch(
            checked = checked,
            enabled = enabled,
            onCheckedChange = onChecked,
            modifier = Modifier.semantics {
                contentDescription = label
            },
        )
    }

    if (shouldStackDetailLine(LocalDensity.current.fontScale)) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Text(text = label)
            switch()
        }
    } else {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = label,
                modifier = Modifier
                    .weight(1f)
                    .padding(end = OmniSpacing.md),
            )
            switch()
        }
    }
}

@Composable
private fun MigrationStatusCard(
    status: LocalMigrationStatus,
    onRetry: () -> Unit,
) {
    SettingsCard(title = "Локальная схема данных") {
        Text(status.label)
        Text(
            text = when (status) {
                LocalMigrationStatus.CURRENT ->
                    "Схема локального UI-state актуальна. После перезапуска значения читаются из локального хранилища."
                LocalMigrationStatus.MIGRATED ->
                    "Маркер схемы обновлён атомарно. Если процесс завершится раньше записи, следующий запуск повторит миграцию."
                LocalMigrationStatus.FAILED ->
                    "Запись версии схемы не подтверждена. OMNICIO не считает миграцию завершённой и позволяет повторить её локально."
            },
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (status == LocalMigrationStatus.FAILED) {
            Button(
                onClick = onRetry,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Повторить локальную миграцию")
            }
        }
    }
}

@Composable
private fun NotificationPermissionCard() {
    val context = LocalContext.current
    val required = notificationPermissionRequired(Build.VERSION.SDK_INT)
    var granted by rememberSaveable {
        mutableStateOf(!required || notificationPermissionGranted(context))
    }
    var requestAttempted by rememberSaveable { mutableStateOf(false) }
    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission(),
    ) { result ->
        requestAttempted = true
        granted = result
    }

    SettingsCard(title = "Разрешение уведомлений") {
        when {
            !required -> {
                Text("Для этой версии Android отдельное runtime-разрешение не требуется.")
            }
            granted -> {
                StatusPill("РАЗРЕШЕНО")
                Text("Системное разрешение выдано. Пользовательские переключатели выше всё равно остаются отдельным выбором.")
            }
            else -> {
                StatusPill(if (requestAttempted) "PERMISSION DENIED" else "РАЗРЕШЕНИЕ НЕ ВЫДАНО")
                Text(
                    text = "Без системного разрешения Android не покажет уведомления. Портфель и локальная аналитика продолжают работать.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Button(
                    onClick = {
                        requestAttempted = true
                        launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Разрешить уведомления")
                }
                if (requestAttempted) {
                    OutlinedButton(
                        onClick = {
                            context.startActivity(
                                Intent(
                                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                    Uri.parse("package:" + context.packageName),
                                ),
                            )
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Открыть настройки Android")
                    }
                    TextButton(
                        onClick = {
                            granted = notificationPermissionGranted(context)
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Проверить разрешение снова")
                    }
                }
            }
        }
    }
}

@Composable
private fun RuntimeEnvironmentCard() {
    val context = LocalContext.current
    val powerManager = remember(context) {
        context.getSystemService(PowerManager::class.java)
    }
    val connectivityManager = remember(context) {
        context.getSystemService(ConnectivityManager::class.java)
    }
    val powerSaver = powerManager?.isPowerSaveMode == true
    val dataSaverRestricted =
        connectivityManager?.restrictBackgroundStatus ==
            ConnectivityManager.RESTRICT_BACKGROUND_STATUS_ENABLED

    SettingsCard(title = "Фоновые ограничения Android") {
        Text("Экономия батареи: " + powerSaverLabel(powerSaver))
        Text("Экономия трафика: " + dataSaverLabel(dataSaverRestricted))
        Text(
            text = "Android не является гарантированным 24/7 scheduler. Фоновые обновления могут выполняться позже, а состояние данных всегда показывается отдельно.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

private fun notificationPermissionGranted(context: Context): Boolean =
    !notificationPermissionRequired(Build.VERSION.SDK_INT) ||
        context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
        PackageManager.PERMISSION_GRANTED

@Composable
private fun SettingsSectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleLarge,
        fontWeight = FontWeight.SemiBold,
    )
}

@Composable
private fun SettingsCard(
    title: String,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            content()
        }
    }
}
