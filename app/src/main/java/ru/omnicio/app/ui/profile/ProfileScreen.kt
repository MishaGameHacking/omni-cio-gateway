package ru.omnicio.app.ui.profile

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import kotlinx.coroutines.launch
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumPageHeader
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
import ru.omnicio.app.ui.theme.LocalThemePreference
import ru.omnicio.app.ui.theme.ThemeMode

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
    val workspace = LocalWorkspaceNavigator.current
    var section by rememberSaveable { mutableIntStateOf(0) }
    var dialog by rememberSaveable { mutableStateOf<String?>(null) }
    val contentState = rememberLazyListState()
    val sectionScope = rememberCoroutineScope()

    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = Color.Transparent,
            contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = {
                AnalystBottomBar(
                    selected = AnalystTab.Profile,
                    onPortfolioClick = onPortfolioClick,
                    onProfileClick = {},
                )
            },
        ) { insets ->
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(insets)
                    .consumeWindowInsets(insets)
                    .semantics { testTagsAsResourceId = true },
            ) {
                SpectrumPageHeader(
                    title = "Профиль",
                    subtitle = accountSubtitle(user),
                    symbol = SpectrumSymbol.Profile,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 16.dp),
                )
                // The fixed rail is above the scrolling body in both drawing
                // and accessibility occlusion order, including after dialogs.
                Column(Modifier.fillMaxWidth().zIndex(1f).clipToBounds().padding(horizontal = 20.dp)) {
                    ProfileSectionTabs(section) { section = it; sectionScope.launch { contentState.scrollToItem(0) } }
                }
                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f)
                        .clipToBounds()
                        .testTag("profile-content"),
                    state = contentState,
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 14.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    when (section) {
                        0 -> {
                            item(key = "appearance-workspace") {
                                WorkspaceLink("Оформление", "Тема, плотность, движение и приватность", SpectrumSymbol.Allocation) {
                                    workspace(WorkspaceRoute.Appearance)
                                }
                            }
                            item(key = "screenshots") {
                                ProfileToggle(
                                    title = "Запретить снимки экрана",
                                    subtitle = if (screenshotsBlocked) {
                                        "Снимки и запись экрана заблокированы"
                                    } else {
                                        "Скриншоты разрешены"
                                    },
                                    symbol = SpectrumSymbol.Risk,
                                    checked = screenshotsBlocked,
                                    onChange = onScreenshotsBlockedChange,
                                )
                            }
                            item(key = "notification-preferences") {
                                WorkspaceLink("Уведомления", "Предупреждения и обзоры", SpectrumSymbol.Notifications) {
                                    workspace(WorkspaceRoute.NotificationSettings)
                                }
                            }
                            item(key = "assistant-workspace") {
                                WorkspaceLink("Ассистент", "Портфель, действия и объяснения", SpectrumSymbol.Analyst) {
                                    workspace(WorkspaceRoute.Assistant)
                                }
                            }
                            item(key = "security") {
                                ProfileAction(
                                    title = "Безопасность",
                                    subtitle = "Вход и доступ к портфелю",
                                    spectrum = SpectrumSymbol.Risk,
                                ) {
                                    dialog = "security"
                                }
                            }
                        }

                        1 -> {
                            item(key = "profile-overview") { ProfileIdentityCard(user, tApiConfigured) }
                            item(key = "strategies") {
                                WorkspaceLink("Моя стратегия", "Цель, отбор, доли и поступления", SpectrumSymbol.Goal) {
                                    workspace(WorkspaceRoute.Strategies)
                                }
                            }
                            item(key = "tapi") {
                                ProfileAction(
                                    title = "Подключение T‑API",
                                    subtitle = if (tApiConfigured) {
                                        "Подключено · проверить доступ"
                                    } else {
                                        "Подключить данные вашего брокерского счёта"
                                    },
                                    spectrum = SpectrumSymbol.Sources,
                                    badge = LocalBrokerConnection.current?.title ?: if (tApiConfigured) "Подключено" else "Не подключено",
                                    onClick = onOpenTApi,
                                )
                            }
                            item(key = "portfolio") {
                                ProfileAction(
                                    title = "Данные портфеля",
                                    subtitle = "Счета и позиции из вашего T‑Invest API",
                                    spectrum = SpectrumSymbol.Portfolio,
                                    onClick = onPortfolioClick,
                                )
                            }
                            item(key = "account") {
                                ProfileAction(
                                    title = user.name?.takeIf(String::isNotBlank) ?: "Аккаунт Telegram",
                                    subtitle = listOfNotNull(
                                        user.username?.let { "@$it" },

                                    ).joinToString(" · "),
                                    spectrum = SpectrumSymbol.Messages,
                                ) {
                                    dialog = "account"
                                }
                            }
                            item(key = "logout") {
                                ProfileAction(
                                    title = "Выйти",
                                    subtitle = "Завершить вход на этом устройстве",
                                    spectrum = SpectrumSymbol.Update,
                                    danger = true,
                                ) {
                                    dialog = "logout"
                                }
                            }
                        }

                        else -> {
                            item(key = "education") {
                                ProfileAction(
                                    title = "Обучение",
                                    subtitle = "Пошаговые уроки, риски, новости и отчётность",
                                    spectrum = SpectrumSymbol.Education,
                                    onClick = onOpenEducation,
                                )
                            }
                            item(key = "about") {
                                ProfileAction(
                                    title = "О приложении",
                                    subtitle = "Analyst AI · ${BuildConfig.VERSION_NAME}",
                                    spectrum = SpectrumSymbol.Analyst,
                                ) {
                                    dialog = "about"
                                }
                            }
                            item(key = "api-info") {
                                ProfileAction(
                                    title = "Источники данных",
                                    subtitle = "T‑Invest API и официальные материалы",
                                    spectrum = SpectrumSymbol.Sources,
                                    onClick = onOpenTApi,
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    when (dialog) {
        "security" -> InformationDialog(
            title = "Безопасность",
            text = "Токен T‑Invest передаётся по HTTPS и хранится зашифрованным на сервере Analyst AI, отдельно от APK. Используйте read-only токен.\n\nСеанс на устройстве хранится зашифрованным; серверный срок действия — 30 дней. После удаления приложения нужно войти снова.\n\nAnalyst AI не выставляет торговые поручения. Запрет скриншотов включается только вами. Для отзыва доступа удалите токен в T‑Инвестициях и отключите T‑API здесь.",
        ) {
            dialog = null
        }

        "about" -> InformationDialog(
            title = "О приложении",
            text = "Analyst AI\nВерсия ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})\n\nПерсональная аналитика портфеля на основе T‑Invest API. Это независимое приложение, не официальное приложение Т‑Банка.\n\nТестовая сборка только для Android 16 и новее. Нет автоматических сделок. ИИ‑обзоры доступны только при подключении моделей на сервере. Исторические графики не подменяются демонстрационными значениями.",
        ) {
            dialog = null
        }

        "account" -> InformationDialog(
            title = "Аккаунт Analyst AI",
            text = "Вход выполнен через Telegram.\nTelegram ID: ${user.telegramId}\n\nСерверные данные портфеля привязаны к этому аккаунту.",
        ) {
            dialog = null
        }

        "logout" -> AlertDialog(
            onDismissRequest = { dialog = null },
            title = { Text("Выйти из Analyst AI?") },
            text = {
                Text("Для следующего входа потребуется подтверждение Telegram. Токен T‑API на сервере не удаляется.")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        dialog = null
                        onLogout()
                    },
                ) {
                    Text("Выйти")
                }
            },
            dismissButton = {
                TextButton(onClick = { dialog = null }) { Text("Отмена") }
            },
        )
    }
}

@Composable
private fun ProfileIdentityCard(user: AnalystUser, tApiConfigured: Boolean) {
    val palette = LocalSpectrumPalette.current
    SpectrumCard(emphasized = true) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            SpectrumIcon(
                symbol = SpectrumSymbol.Analyst,
                modifier = Modifier.size(48.dp),
                selected = true,
                tile = true,
                motionAllowed = false,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(
                    user.name?.takeIf(String::isNotBlank) ?: "Analyst AI",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    user.username?.let { "@$it" } ?: "Вход через Telegram",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
                SpectrumBadge(
                    text = LocalBrokerConnection.current?.title ?: if (tApiConfigured) "Портфель подключён" else "T‑API не подключён",
                    accent = if (tApiConfigured) palette.emerald else palette.amber,
                )
            }
        }
    }
}

@Composable
private fun ProfileToggle(
    title: String,
    subtitle: String,
    symbol: SpectrumSymbol,
    checked: Boolean,
    onChange: (Boolean) -> Unit,
) {
    val fontScale = LocalDensity.current.fontScale
    SpectrumCard(
        modifier = Modifier
            .fillMaxWidth()
            .toggleable(checked, role = Role.Switch, onValueChange = onChange),
    ) {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val stacked = maxWidth < 300.dp || fontScale > 1.3f
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    SpectrumIcon(symbol, Modifier.size(48.dp), tile = true, selected = true)
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                        Text(
                            subtitle,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    if (!stacked) Switch(checked = checked, onCheckedChange = null)
                }
                if (stacked) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        Switch(checked = checked, onCheckedChange = null)
                    }
                }
            }
        }
    }
}

@Composable
private fun ProfileAction(
    title: String,
    subtitle: String,
    spectrum: SpectrumSymbol,
    badge: String? = null,
    danger: Boolean = false,
    onClick: () -> Unit,
) {
    val motion = LocalSpectrumMotionPreference.current
    val palette = LocalSpectrumPalette.current
    SpectrumCard(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick,
    ) {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            SpectrumIcon(
                spectrum,
                Modifier.size(40.dp),
                tile = true,
                selected = true,
                motionAllowed = motion.enabled,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(
                    title,
                    color = if (danger) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    subtitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
                badge?.let {
                    SpectrumBadge(
                        text = it,
                        accent = if (it == "Подключено") palette.emerald else palette.amber,
                    )
                }
            }
        }
    }
}

@Composable
private fun InformationDialog(title: String, text: String, close: () -> Unit) {
    AlertDialog(
        onDismissRequest = close,
        title = { Text(title) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) { Text(text) }
        },
        confirmButton = {
            TextButton(onClick = close) { Text("Понятно") }
        },
    )
}

private fun accountSubtitle(user: AnalystUser): String {
    val identity = user.name?.takeIf(String::isNotBlank)
        ?: user.username?.let { "@$it" }
        ?: "Вход через Telegram"
    return identity
}

