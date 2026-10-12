package ru.omnicio.app.ui.profile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab

private enum class ProfileSection {
    Settings,
    Profile,
    Info,
}

private val ProfileBackground = Color(0xFFF5F6F8)
private val ProfileCard = Color.White
private val ProfileMuted = Color(0xFF8A9099)
private val ProfileBlue = Color(0xFF4D8FEA)

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
    var sectionName by rememberSaveable { mutableStateOf(ProfileSection.Settings.name) }
    val section = remember(sectionName) {
        runCatching { ProfileSection.valueOf(sectionName) }.getOrDefault(ProfileSection.Settings)
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = ProfileBackground,
        bottomBar = {
            AnalystBottomBar(
                selected = AnalystTab.Profile,
                onPortfolioClick = onPortfolioClick,
                onProfileClick = {},
            )
        },
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(
                start = 20.dp,
                top = 18.dp,
                end = 20.dp,
                bottom = 28.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                ProfileHeader(user = user)
            }
            item {
                ProfileTabs(
                    selected = section,
                    onSelect = { selected ->
                        sectionName = selected.name
                    },
                )
            }

            when (section) {
                ProfileSection.Settings -> {
                    item {
                        ProfileCard(
                            title = "Оформление",
                            subtitle = "Как в системе",
                            symbol = "◐",
                        )
                    }
                    item {
                        ProfileSwitchCard(
                            title = "Запретить снимки экрана",
                            subtitle = if (screenshotsBlocked) {
                                "Скриншоты и запись экрана заблокированы"
                            } else {
                                "Выключено · скриншоты разрешены"
                            },
                            checked = screenshotsBlocked,
                            onCheckedChange = onScreenshotsBlockedChange,
                        )
                    }
                    item {
                        ProfileCard(
                            title = "Безопасность",
                            subtitle = "Секреты скрыты и не попадают в APK",
                            symbol = "⌾",
                        )
                    }
                }

                ProfileSection.Profile -> {
                    item {
                        ProfileCard(
                            title = "T‑API",
                            subtitle = if (tApiConfigured) {
                                "Токен сохранён · можно проверить или заменить"
                            } else {
                                "Подключить T‑Invest API"
                            },
                            symbol = "T",
                            accent = tApiConfigured,
                            onClick = onOpenTApi,
                        )
                    }
                    item {
                        ProfileCard(
                            title = "Инвестиционный профиль",
                            subtitle = "Риск, горизонт, резерв и фоновые обзоры",
                            symbol = "AI",
                            onClick = onOpenAnalysisSettings,
                        )
                    }
                    item {
                        ProfileCard(
                            title = "Данные портфеля",
                            subtitle = "Счета и позиции из T‑Invest API",
                            symbol = "₽",
                        )
                    }
                    item {
                        ProfileCard(
                            title = user.name?.takeIf { it.isNotBlank() } ?: "Telegram",
                            subtitle = buildTelegramSubtitle(user),
                            symbol = "TG",
                        )
                    }
                    item {
                        ProfileCard(
                            title = "Выйти",
                            subtitle = "Завершить сеанс Analyst AI на этом устройстве",
                            symbol = "↪",
                            onClick = onLogout,
                        )
                    }
                }

                ProfileSection.Info -> {
                    item {
                        ProfileCard(
                            title = "О приложении",
                            subtitle = "Analyst AI · версия ${BuildConfig.VERSION_NAME}",
                            symbol = "i",
                        )
                    }
                    item {
                        ProfileCard(
                            title = "T‑Invest API",
                            subtitle = "Официальная документация и правила токенов",
                            symbol = "?",
                            onClick = onOpenTApi,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ProfileHeader(user: AnalystUser) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(
            text = user.name?.takeIf { it.isNotBlank() } ?: "Analyst AI",
            color = MaterialTheme.colorScheme.onSurface,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            text = "Профиль",
            fontSize = 34.sp,
            lineHeight = 40.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
private fun ProfileTabs(
    selected: ProfileSection,
    onSelect: (ProfileSection) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        ProfileTab(
            text = "Настройки",
            selected = selected == ProfileSection.Settings,
            onClick = { onSelect(ProfileSection.Settings) },
        )
        ProfileTab(
            text = "Профиль",
            selected = selected == ProfileSection.Profile,
            onClick = { onSelect(ProfileSection.Profile) },
        )
        ProfileTab(
            text = "Инфо",
            selected = selected == ProfileSection.Info,
            onClick = { onSelect(ProfileSection.Info) },
        )
    }
}

@Composable
private fun ProfileTab(
    text: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    TextButton(onClick = onClick) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = text,
                color = if (selected) ProfileBlue else MaterialTheme.colorScheme.onSurface,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
            )
            Spacer(modifier = Modifier.height(6.dp))
            Surface(
                modifier = Modifier
                    .height(3.dp)
                    .fillMaxWidth(0.72f),
                shape = CircleShape,
                color = if (selected) ProfileBlue else Color.Transparent,
            ) {}
        }
    }
}

@Composable
private fun ProfileSwitchCard(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = ProfileCard),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 22.dp, vertical = 20.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = title,
                    fontSize = 20.sp,
                    lineHeight = 26.sp,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = subtitle,
                    color = ProfileMuted,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            Switch(
                checked = checked,
                onCheckedChange = onCheckedChange,
            )
        }
    }
}

@Composable
private fun ProfileCard(
    title: String,
    subtitle: String,
    symbol: String,
    modifier: Modifier = Modifier,
    accent: Boolean = false,
    onClick: (() -> Unit)? = null,
) {
    val colors = CardDefaults.cardColors(containerColor = ProfileCard)

    if (onClick == null) {
        Card(
            modifier = modifier.fillMaxWidth(),
            shape = RoundedCornerShape(28.dp),
            colors = colors,
        ) {
            ProfileCardContent(
                title = title,
                subtitle = subtitle,
                symbol = symbol,
                accent = accent,
            )
        }
    } else {
        Card(
            modifier = modifier.fillMaxWidth(),
            shape = RoundedCornerShape(28.dp),
            colors = colors,
            onClick = onClick,
        ) {
            ProfileCardContent(
                title = title,
                subtitle = subtitle,
                symbol = symbol,
                accent = accent,
            )
        }
    }
}

@Composable
private fun ProfileCardContent(
    title: String,
    subtitle: String,
    symbol: String,
    accent: Boolean,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 22.dp, vertical = 20.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = title,
                fontSize = 20.sp,
                lineHeight = 26.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = subtitle,
                color = if (accent) Color(0xFF178B4D) else ProfileMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        Surface(
            modifier = Modifier.size(48.dp),
            shape = CircleShape,
            color = if (accent) Color(0xFF153D2B) else Color(0xFF111318),
        ) {
            androidx.compose.foundation.layout.Box(
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = symbol,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

private fun buildTelegramSubtitle(user: AnalystUser): String {
    val username = user.username?.takeIf { it.isNotBlank() }?.let { "@$it" }
    return listOfNotNull(username, "Telegram ID ${user.telegramId}")
        .joinToString(" · ")
}
