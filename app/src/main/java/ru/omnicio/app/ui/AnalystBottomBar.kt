package ru.omnicio.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

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
        modifier = modifier.navigationBarsPadding(),
        color = Color.White,
        shadowElevation = 10.dp,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 2.dp, vertical = 5.dp),
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
    val contentColor = if (selected) Color(0xFF16191F) else Color(0xFF9298A2)
    TextButton(
        modifier = modifier.heightIn(min = 58.dp),
        onClick = onClick,
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 1.dp),
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            TabIcon(
                tab = tab,
                color = contentColor,
                modifier = Modifier.size(23.dp),
            )
            Text(
                text = tab.label(),
                modifier = Modifier.fillMaxWidth(),
                color = contentColor,
                fontSize = 10.sp,
                lineHeight = 12.sp,
                textAlign = TextAlign.Center,
                maxLines = 1,
                overflow = TextOverflow.Clip,
                style = MaterialTheme.typography.labelSmall,
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

@Composable
private fun TabIcon(
    tab: AnalystTab,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier) {
        val stroke = Stroke(
            width = 2.dp.toPx(),
            cap = StrokeCap.Round,
            join = StrokeJoin.Round,
        )
        when (tab) {
            AnalystTab.Portfolio -> {
                drawRoundRect(
                    color = color,
                    topLeft = Offset(size.width * 0.12f, size.height * 0.30f),
                    size = Size(size.width * 0.76f, size.height * 0.56f),
                    cornerRadius = CornerRadius(size.width * 0.10f),
                    style = stroke,
                )
                drawArc(
                    color = color,
                    startAngle = 180f,
                    sweepAngle = 180f,
                    useCenter = false,
                    topLeft = Offset(size.width * 0.35f, size.height * 0.10f),
                    size = Size(size.width * 0.30f, size.height * 0.38f),
                    style = stroke,
                )
                drawLine(
                    color = color,
                    start = Offset(size.width * 0.12f, size.height * 0.50f),
                    end = Offset(size.width * 0.88f, size.height * 0.50f),
                    strokeWidth = 2.dp.toPx(),
                    cap = StrokeCap.Round,
                )
            }

            AnalystTab.Ideas -> {
                drawCircle(
                    color = color,
                    radius = size.minDimension * 0.29f,
                    center = Offset(size.width * 0.42f, size.height * 0.40f),
                    style = stroke,
                )
                drawLine(
                    color = color,
                    start = Offset(size.width * 0.62f, size.height * 0.62f),
                    end = Offset(size.width * 0.86f, size.height * 0.86f),
                    strokeWidth = 2.4.dp.toPx(),
                    cap = StrokeCap.Round,
                )
            }

            AnalystTab.Pulse -> {
                drawCircle(
                    color = color,
                    radius = size.minDimension * 0.40f,
                    center = center,
                    style = stroke,
                )
                val wave = Path().apply {
                    moveTo(size.width * 0.17f, size.height * 0.54f)
                    lineTo(size.width * 0.33f, size.height * 0.54f)
                    lineTo(size.width * 0.43f, size.height * 0.32f)
                    lineTo(size.width * 0.56f, size.height * 0.70f)
                    lineTo(size.width * 0.66f, size.height * 0.50f)
                    lineTo(size.width * 0.83f, size.height * 0.50f)
                }
                drawPath(wave, color = color, style = stroke)
            }

            AnalystTab.Chat -> {
                drawRoundRect(
                    color = color,
                    topLeft = Offset(size.width * 0.10f, size.height * 0.15f),
                    size = Size(size.width * 0.80f, size.height * 0.62f),
                    cornerRadius = CornerRadius(size.width * 0.14f),
                    style = stroke,
                )
                val tail = Path().apply {
                    moveTo(size.width * 0.36f, size.height * 0.77f)
                    lineTo(size.width * 0.30f, size.height * 0.91f)
                    lineTo(size.width * 0.54f, size.height * 0.77f)
                }
                drawPath(tail, color = color, style = stroke)
                drawLine(
                    color = color,
                    start = Offset(size.width * 0.28f, size.height * 0.39f),
                    end = Offset(size.width * 0.72f, size.height * 0.39f),
                    strokeWidth = 1.8.dp.toPx(),
                    cap = StrokeCap.Round,
                )
                drawLine(
                    color = color,
                    start = Offset(size.width * 0.28f, size.height * 0.56f),
                    end = Offset(size.width * 0.58f, size.height * 0.56f),
                    strokeWidth = 1.8.dp.toPx(),
                    cap = StrokeCap.Round,
                )
            }

            AnalystTab.Profile -> {
                drawCircle(
                    color = color,
                    radius = size.minDimension * 0.18f,
                    center = Offset(size.width * 0.50f, size.height * 0.31f),
                    style = stroke,
                )
                drawArc(
                    color = color,
                    startAngle = 195f,
                    sweepAngle = 150f,
                    useCenter = false,
                    topLeft = Offset(size.width * 0.17f, size.height * 0.47f),
                    size = Size(size.width * 0.66f, size.height * 0.54f),
                    style = stroke,
                )
            }
        }
    }
}
