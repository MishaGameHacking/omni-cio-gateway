package ru.omnicio.app.ui.profile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.SpectrumIcon
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
    onOpenAnalysisSettings: () -> Unit,
    onOpenEducation: () -> Unit,
    onLogout: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var section by rememberSaveable { mutableIntStateOf(0) }
    var dialog by rememberSaveable { mutableStateOf<String?>(null) }
    val theme = LocalThemePreference.current
    val motion = LocalSpectrumMotionPreference.current
    Scaffold(modifier = modifier.fillMaxSize(), containerColor = MaterialTheme.colorScheme.background,
        bottomBar = { AnalystBottomBar(AnalystTab.Profile, onPortfolioClick, {}) }) { insets ->
        Column(Modifier.fillMaxSize().padding(insets).padding(horizontal = 20.dp)
            .semantics { testTagsAsResourceId = true }) {
            Column(Modifier.padding(top = 16.dp, bottom = 8.dp)) {
                Text(user.name?.takeIf(String::isNotBlank) ?: "Analyst AI", fontWeight = FontWeight.SemiBold)
                Text("Профиль", fontSize = 32.sp, fontWeight = FontWeight.Bold)
            }
            // Tabs stay reachable even after scrolling a long settings section.
            ProfileSectionTabs(section) { section = it }
            LazyColumn(modifier = Modifier.fillMaxWidth().weight(1f).testTag("profile-content"),
                contentPadding = PaddingValues(top = 12.dp, bottom = 20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)) {
                when (section) {
                    0 -> {
                        item(key = "theme") { ProfileAction("Оформление", theme.mode.title, "◐", SpectrumSymbol.Allocation) { dialog = "theme" } }
                        item(key = "motion") {
                            ProfileToggle("Живые RGB-эффекты",
                                if (motion.enabled) "Короткая анимация иконок включена" else "Иконки остаются статичными",
                                SpectrumSymbol.Analyst, motion.enabled, motion.select)
                        }
                        item(key = "screenshots") {
                            ProfileToggle("Запретить снимки экрана",
                                if (screenshotsBlocked) "Снимки и запись экрана заблокированы" else "Скриншоты разрешены",
                                SpectrumSymbol.Risk, screenshotsBlocked, onScreenshotsBlockedChange)
                        }
                        item(key = "security") { ProfileAction("Безопасность", "Хранение токенов, сеанс и доступ к данным", "⌾", SpectrumSymbol.Risk) { dialog = "security" } }
                    }
                    1 -> {
                        item(key = "tapi") { ProfileAction("T‑API", if (tApiConfigured) "Подключён · проверить или заменить токен" else "Подключить T‑Invest API", "T", SpectrumSymbol.Sources, onOpenTApi) }
                        item(key = "investment-profile") { ProfileAction("Инвестиционный профиль", "Риск, горизонт и резерв", "AI", SpectrumSymbol.Analyst, onOpenAnalysisSettings) }
                        item(key = "portfolio") { ProfileAction("Данные портфеля", "Счета и позиции из вашего T‑Invest API", "₽", SpectrumSymbol.Portfolio, onPortfolioClick) }
                        item(key = "account") { ProfileAction(user.name ?: "Telegram", listOfNotNull(user.username?.let { "@$it" }, "ID ${user.telegramId}").joinToString(" · "), "TG", SpectrumSymbol.Messages) { dialog = "account" } }
                        item(key = "logout") { ProfileAction("Выйти", "Завершить вход на этом устройстве", "↪") { dialog = "logout" } }
                    }
                    2 -> {
                        item(key = "education") { ProfileAction("Обучение инвестициям", "Пошаговые уроки, риски, новости и отчётность", "◈", SpectrumSymbol.Sources, onOpenEducation) }
                        item(key = "about") { ProfileAction("О приложении", "Analyst AI · ${BuildConfig.VERSION_NAME}", "i", SpectrumSymbol.Analyst) { dialog = "about" } }
                        item(key = "api-info") { ProfileAction("T‑Invest API", "Подключение и официальная инструкция", "?", SpectrumSymbol.Sources, onOpenTApi) }
                    }
                }
            }
        }
    }
    when (dialog) {
        "theme" -> AlertDialog(onDismissRequest = { dialog = null }, title = { Text("Оформление") }, text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                ThemeMode.entries.forEach { mode ->
                    Row(Modifier.fillMaxWidth().selectable(selected = theme.mode == mode, role = Role.RadioButton,
                        onClick = { theme.select(mode); dialog = null }).padding(vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        RadioButton(selected = theme.mode == mode, onClick = null)
                        Spacer(Modifier.width(12.dp))
                        Text(mode.title)
                    }
                }
            }
        }, confirmButton = { TextButton(onClick = { dialog = null }) { Text("Закрыть") } })
        "security" -> InformationDialog("Безопасность",
            "Токен T‑Invest передаётся по HTTPS и хранится зашифрованным на сервере Analyst AI, отдельно от APK. Используйте read-only токен.\n\nСеанс на устройстве хранится зашифрованным; серверный срок действия — 30 дней. После удаления приложения нужно войти снова.\n\nAnalyst AI не выставляет торговые поручения. Запрет скриншотов включается только вами. Для отзыва доступа удалите токен в T‑Инвестициях и отключите T‑API здесь.") { dialog = null }
        "about" -> InformationDialog("О приложении",
            "Analyst AI\nВерсия ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})\n\nПортфель, операции и аналитика на основе T‑Invest API. Это независимое приложение, не официальное приложение Т‑Банка.\n\nТестовая сборка для Android 13+. Нет автоматических сделок. ИИ-обзоры доступны только при подключении моделей на сервере. Исторические графики не подменяются демонстрационными значениями.") { dialog = null }
        "account" -> InformationDialog("Аккаунт Analyst AI", "Вход выполнен через Telegram.\nTelegram ID: ${user.telegramId}\n\nСерверные данные портфеля привязаны к этому аккаунту.") { dialog = null }
        "logout" -> AlertDialog(onDismissRequest = { dialog = null }, title = { Text("Выйти из Analyst AI?") },
            text = { Text("Для следующего входа потребуется подтверждение Telegram. Токен T‑API на сервере не удаляется.") },
            confirmButton = { TextButton(onClick = { dialog = null; onLogout() }) { Text("Выйти") } },
            dismissButton = { TextButton(onClick = { dialog = null }) { Text("Отмена") } })
    }
}

/** At narrow widths/large fonts, the switch moves below the text, not into it. */
@Composable
private fun ProfileToggle(title: String, subtitle: String, symbol: SpectrumSymbol, checked: Boolean, onChange: (Boolean) -> Unit) {
    val fontScale = LocalDensity.current.fontScale
    Card(modifier = Modifier.fillMaxWidth().toggleable(checked, role = Role.Switch, onValueChange = onChange),
        shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        BoxWithConstraints(Modifier.padding(20.dp)) {
            val stacked = maxWidth < 300.dp || fontScale > 1.3f
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    SpectrumIcon(symbol, Modifier.size(44.dp), tile = true, motionAllowed = false)
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                        Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyLarge)
                    }
                    if (!stacked) Switch(checked = checked, onCheckedChange = null)
                }
                if (stacked) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    Switch(checked = checked, onCheckedChange = null)
                }
            }
        }
    }
}

@Composable
private fun ProfileAction(title: String, subtitle: String, symbol: String, spectrum: SpectrumSymbol? = null, onClick: () -> Unit) {
    val motion = LocalSpectrumMotionPreference.current
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyLarge)
            }
            if (spectrum != null) SpectrumIcon(spectrum, Modifier.size(46.dp), tile = true, motionAllowed = motion.enabled)
            else Text(symbol, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold, fontSize = 22.sp)
        }
    }
}

@Composable
private fun InformationDialog(title: String, text: String, close: () -> Unit) {
    AlertDialog(onDismissRequest = close, title = { Text(title) },
        text = { Column(Modifier.verticalScroll(rememberScrollState())) { Text(text) } },
        confirmButton = { TextButton(onClick = close) { Text("Понятно") } })
}
