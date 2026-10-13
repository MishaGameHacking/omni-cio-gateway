package ru.omnicio.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

enum class AnalystTab {
    Portfolio,
    Ideas,
    Pulse,
    Chat,
    Profile,
}

val LocalAnalystTabNavigator = staticCompositionLocalOf<(AnalystTab) -> Unit> { {} }

@Composable
fun AnalystBottomBar(
    selected: AnalystTab,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val navigate = LocalAnalystTabNavigator.current
    Surface(
        modifier = modifier,
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.98f),
        shadowElevation = 12.dp,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(horizontal = 4.dp, vertical = 6.dp),
        ) {
            AnalystTab.entries.forEach { tab ->
                BottomBarItem(
                    modifier = Modifier.weight(1f),
                    tab = tab,
                    selected = selected == tab,
                    onClick = {
                        when (tab) {
                            AnalystTab.Portfolio -> onPortfolioClick()
                            AnalystTab.Profile -> onProfileClick()
                            else -> Unit
                        }
                        navigate(tab)
                    },
                )
            }
        }
    }
}

@Composable
private fun BottomBarItem(
    tab: AnalystTab,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val palette = LocalSpectrumPalette.current
    val motion = LocalSpectrumMotionPreference.current
    val contentColor = if (selected) {
        MaterialTheme.colorScheme.onSurface
    } else {
        MaterialTheme.colorScheme.onSurfaceVariant
    }
    val selectedBrush = Brush.linearGradient(
        colors = listOf(
            palette.cyan.copy(alpha = 0.17f),
            palette.violet.copy(alpha = 0.17f),
            palette.rose.copy(alpha = 0.10f),
        ),
    )
    TextButton(
        modifier = modifier.heightIn(min = 72.dp),
        onClick = onClick,
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 2.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(18.dp))
                .background(
                    if (selected) {
                        selectedBrush
                    } else {
                        Brush.linearGradient(listOf(Color.Transparent, Color.Transparent))
                    },
                )
                .padding(horizontal = 1.dp, vertical = 5.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            SpectrumIcon(
                symbol = tab.symbol(),
                selected = selected,
                tile = false,
                motionAllowed = motion.enabled,
                modifier = Modifier.size(27.dp),
            )
            Text(
                text = tab.label(),
                modifier = Modifier.fillMaxWidth(),
                color = contentColor,
                fontSize = 12.sp,
                lineHeight = 14.sp,
                textAlign = TextAlign.Center,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
            )
        }
    }
}

private fun AnalystTab.label(): String = when (this) {
    AnalystTab.Portfolio -> "Портфель"
    AnalystTab.Ideas -> "Что купить"
    AnalystTab.Pulse -> "Пульс"
    AnalystTab.Chat -> "Чат"
    AnalystTab.Profile -> "Профиль"
}

private fun AnalystTab.symbol(): SpectrumSymbol = when (this) {
    AnalystTab.Portfolio -> SpectrumSymbol.Portfolio
    AnalystTab.Ideas -> SpectrumSymbol.Ideas
    AnalystTab.Pulse -> SpectrumSymbol.Pulse
    AnalystTab.Chat -> SpectrumSymbol.Messages
    AnalystTab.Profile -> SpectrumSymbol.Profile
}
