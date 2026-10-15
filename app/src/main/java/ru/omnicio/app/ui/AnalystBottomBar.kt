package ru.omnicio.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
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
    Home,
    Portfolio,
    Risk,
    Education,
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
    val palette = LocalSpectrumPalette.current
    Surface(
        modifier = modifier,
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.96f),
        contentColor = MaterialTheme.colorScheme.onSurface,
        shadowElevation = 18.dp,
    ) {
        Box {
            Canvas(Modifier.fillMaxWidth()) {
                drawRect(
                    brush = Brush.horizontalGradient(
                        listOf(
                            palette.cyan.copy(alpha = 0.30f),
                            palette.blue.copy(alpha = 0.16f),
                            palette.violet.copy(alpha = 0.30f),
                            palette.rose.copy(alpha = 0.12f),
                        ),
                    ),
                    size = androidx.compose.ui.geometry.Size(size.width, 1.dp.toPx()),
                )
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(horizontal = 5.dp, vertical = 7.dp),
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
            palette.cyan.copy(alpha = 0.18f),
            palette.blue.copy(alpha = 0.12f),
            palette.violet.copy(alpha = 0.22f),
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
                .clip(RoundedCornerShape(20.dp))
                .background(
                    if (selected) {
                        selectedBrush
                    } else {
                        Brush.linearGradient(listOf(Color.Transparent, Color.Transparent))
                    },
                )
                .padding(horizontal = 1.dp, vertical = 6.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            SpectrumIcon(
                symbol = tab.symbol(),
                selected = selected,
                tile = false,
                motionAllowed = motion.enabled,
                modifier = Modifier.size(if (selected) 29.dp else 27.dp),
            )
            Text(
                text = tab.label(),
                modifier = Modifier.fillMaxWidth(),
                color = contentColor,
                fontSize = 11.sp,
                lineHeight = 14.sp,
                textAlign = TextAlign.Center,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
            )
        }
    }
}

private fun AnalystTab.label(): String = when (this) {
    AnalystTab.Home -> "Главная"
    AnalystTab.Portfolio -> "Портфель"
    AnalystTab.Risk -> "Риски"
    AnalystTab.Education -> "Обучение"
    AnalystTab.Profile -> "Профиль"
}

private fun AnalystTab.symbol(): SpectrumSymbol = when (this) {
    AnalystTab.Home -> SpectrumSymbol.Home
    AnalystTab.Portfolio -> SpectrumSymbol.Portfolio
    AnalystTab.Risk -> SpectrumSymbol.Risk
    AnalystTab.Education -> SpectrumSymbol.Education
    AnalystTab.Profile -> SpectrumSymbol.Profile
}
