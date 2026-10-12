package ru.omnicio.app.ui.profile

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
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
    onOpenAnalysisSettings: () -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var section by rememberSaveable { mutableIntStateOf(0) }
    var dialog by rememberSaveable { mutableStateOf<String?>(null) }
    val theme = LocalThemePreference.current
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            AnalystBottomBar(AnalystTab.Profile, onPortfolioClick, {})
        },
    ) { insets ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(insets),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item(key = "header") {
                Column {
                    Text(user.name?.takeIf(String::isNotBlank) ?: "Analyst AI", fontWeight = FontWeight.SemiBold)
                    Text("Профиль", fontSize = 32.sp, fontWeight = FontWeight.Bold)
                }
            }
            item(key = "tabs") {
                Row(Modifier.fillMaxWidth()) {
                    listOf("Настройки", "Профиль", "Инфо").forEachIndexed { index, title ->
                        TextButton(
                            onClick = { section = index },
                            modifier = Modifier.weight(1f),
                            contentPadding = PaddingValues(horizontal = 4.dp, vertical = 12.dp),
                        ) {
                            Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(title, maxLines = 1, softWrap = false, overflow = TextOverflow.Ellipsis,
                                    color = if (section == index) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                                    fontWeight = if (section == index) FontWeight.Bold else FontWeight.Medium)
                                Spacer(Modifier.height(8.dp))
                                HorizontalDivider(thickness = 2.dp,
                                    color = if (section == index) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.background)
                            }
                        }
                    }
                }
            }
            when (section) {
                0 -> {
                    item { ProfileAction("Оформление", theme.mode.title, "◐") { dialog = "theme" } }
                    item {
                        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                            Row(Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text("Запретить снимки экрана", fontWeight = FontWeight.Bold)
                                    Text(if (screenshotsBlocked) "Снимки и запись экрана заблокированы" else "Скриншоты разрешены",
                                        color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                                }
                                Switch(checked = screenshotsBlocked, onCheckedChange = onScreenshotsBlockedChange)
                            }
                        }
                    }
                    item { ProfileAction("Безопасность", "Хранение токенов, сеанс и доступ к данным", "⌾") { dialog = "security" } }
                }
                1 -> {
                    item { ProfileAction("T‑API", if (tApiConfigured) "Подключён · проверить или заменить токен" else "Подключить T‑Invest API", "T", onOpenTApi) }
                    item { ProfileAction("Инвестиционный профиль", "Риск, горизонт и резерв", "AI", onOpenAnalysisSettings) }
                    item { ProfileAction("Данные портфеля", "Счета и позиции из вашего T‑Invest API", "₽", onPortfolioClick) }
                    item { ProfileAction(user.name ?: "Telegram", listOfNotNull(user.username?.let { "@$it" }, "ID ${user.telegramId}").joinToString(" · "), "TG") { dialog = "account" } }
                    item { ProfileAction("Выйти", "Завершить вход на этом устройстве", "↪") { dialog = "logout" } }
                }
                2 -> {
                    item { ProfileAction("О приложении", "Analyst AI · ${BuildConfig.VERSION_NAME}", "i") { dialog = "about" } }
                    item { ProfileAction("T‑Invest API", "Подключение и официальная инструкция", "?", onOpenTApi) }
                }
            }
        }
    }
    when (dialog) {
        "theme" -> AlertDialog(
            onDismissRequest = { dialog = null },
            title = { Text("Оформление") },
            text = {
                Column {
                    ThemeMode.entries.forEach { mode ->
                        Row(Modifier.fillMaxWidth().selectable(
                            selected = theme.mode == mode, role = Role.RadioButton,
                            onClick = { theme.select(mode); dialog = null },
                        ).padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(selected = theme.mode == mode, onClick = null)
                            Spacer(Modifier.width(12.dp))
                            Text(mode.title)
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { dialog = null }) { Text("Закрыть") } },
        )
        "security" -> InformationDialog("Безопасность",
            "Токен T‑Invest передаётся по HTTPS и хранится зашифрованным на сервере Analyst AI, отдельно от APK. Используйте read-only токен.\n\nСеанс на устройстве хранится зашифрованным; серверный срок действия — 30 дней. После удаления приложения нужно войти снова.\n\nAnalyst AI не выставляет торговые поручения. Запрет скриншотов включается только вами. Для отзыва доступа удалите токен в T‑Инвестициях и отключите T‑API здесь.") { dialog = null }
        "about" -> InformationDialog("О приложении",
            "Analyst AI\nВерсия ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})\n\nПортфель, операции и аналитика на основе T‑Invest API. Это независимое приложение, не официальное приложение Т‑Банка.\n\nТестовая сборка для Android 13+. Нет автоматических сделок. ИИ-обзоры доступны только при подключении моделей на сервере. Исторические графики не подменяются демонстрационными значениями.") { dialog = null }
        "account" -> InformationDialog("Аккаунт Analyst AI", "Вход выполнен через Telegram.\nTelegram ID: ${user.telegramId}\n\nСерверные данные портфеля привязаны к этому аккаунту.") { dialog = null }
        "logout" -> AlertDialog(
            onDismissRequest = { dialog = null }, title = { Text("Выйти из Analyst AI?") },
            text = { Text("Для следующего входа потребуется подтверждение Telegram. Токен T‑API на сервере не удаляется.") },
            confirmButton = { TextButton(onClick = { dialog = null; onLogout() }) { Text("Выйти") } },
            dismissButton = { TextButton(onClick = { dialog = null }) { Text("Отмена") } },
        )
    }
}

@Composable
private fun ProfileAction(title: String, subtitle: String, symbol: String, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
            }
            Text(symbol, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold, fontSize = 22.sp)
        }
    }
}

@Composable
private fun InformationDialog(title: String, text: String, close: () -> Unit) {
    AlertDialog(onDismissRequest = close, title = { Text(title) },
        text = { Column(Modifier.verticalScroll(rememberScrollState())) { Text(text) } },
        confirmButton = { TextButton(onClick = close) { Text("Понятно") } })
}
