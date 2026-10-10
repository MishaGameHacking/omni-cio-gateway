package ru.omnicio.app.ui

import android.content.Intent
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import ru.omnicio.app.ui.theme.OmniSpacing

@Composable
internal fun SettingsScreen(
    uiState: AppUiState,
    onBack: () -> Unit,
    onDeletePortfolio: () -> Unit,
    onRestoreDemoPortfolio: () -> Unit,
    onConnectBrokerFixture: () -> Unit,
    onDisconnectBroker: () -> Unit,
    onReserveMinor: (Long) -> Unit,
    onGoalHorizonYears: (Int) -> Unit,
    onNotificationsEnabled: (Boolean) -> Unit,
    onFastAlertsEnabled: (Boolean) -> Unit,
) {
    val context = LocalContext.current
    val settings = uiState.settings

    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(OmniSpacing.md),
    ) {
        item {
            TextButton(onClick = onBack) {
                Text("← Назад")
            }
        }
        item {
            StatusPill("ДЕМО · UI-05 · НАСТРОЙКИ")
        }
        item {
            Text(
                text = "Настройки",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.semantics { heading() },
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
            SubscriptionCard()
        }
        item {
            InfoCard(
                title = "О приложении",
                body = "OMNICIO 2.4.0 · Android local-first UI. Privacy, документы и перечень источников остаются прозрачными. Основной пользовательский продукт не зависит от старого web workspace.",
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
) {
    SettingsCard(title = "T-Invest · read-only") {
        Text(
            text = if (settings.brokerConnected) {
                "Подключено · UI-fixture. Credential отмечен как локальный."
            } else {
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
        if (settings.brokerConnected) {
            OutlinedButton(
                onClick = onConnect,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Переподключить fixture")
            }
            Button(
                onClick = onDisconnect,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Отключить и очистить локальный credential")
            }
        } else {
            Button(
                onClick = onConnect,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Подключить read-only fixture")
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
        Switch(
            checked = checked,
            enabled = enabled,
            onCheckedChange = onChecked,
        )
    }
}

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
