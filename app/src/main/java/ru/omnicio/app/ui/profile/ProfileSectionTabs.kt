package ru.omnicio.app.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

/** Equal tabs at normal size; horizontally scrollable single-line tabs at large font. */
@Composable
internal fun ProfileSectionTabs(selected: Int, onSelect: (Int) -> Unit) {
    val labels = listOf("Настройки", "Аккаунт", "О приложении")
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    val style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.Bold)
    val palette = LocalSpectrumPalette.current
    val labelWidth = with(density) {
        labels.maxOf { label ->
            measurer.measure(AnnotatedString(label), style, softWrap = false, maxLines = 1).size.width
        }.toDp()
    }
    val scroll = rememberScrollState()
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val width = maxOf(maxWidth / labels.size, labelWidth + 24.dp)
        val widthPixels = with(density) { width.roundToPx() }
        LaunchedEffect(selected, widthPixels) {
            scroll.scrollTo((selected * widthPixels).coerceIn(0, scroll.maxValue))
        }
        Row(
            Modifier
                .fillMaxWidth()
                .horizontalScroll(scroll)
                .selectableGroup()
                .semantics { testTagsAsResourceId = true }
                .testTag("profile-tabs"),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            labels.forEachIndexed { index, label ->
                val chosen = selected == index
                val brush = if (chosen) {
                    Brush.linearGradient(
                        listOf(
                            palette.cyan.copy(alpha = 0.16f),
                            palette.violet.copy(alpha = 0.22f),
                            palette.rose.copy(alpha = 0.08f),
                        ),
                    )
                } else {
                    Brush.linearGradient(listOf(Color.Transparent, Color.Transparent))
                }
                Box(
                    modifier = Modifier
                        .width(width)
                        .heightIn(min = 52.dp)
                        .clip(RoundedCornerShape(18.dp))
                        .background(brush)
                        .selectable(chosen, role = Role.Tab, onClick = { onSelect(index) })
                        .testTag("profile-tab-$index")
                        .padding(horizontal = 8.dp, vertical = 10.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        label,
                        maxLines = 1,
                        softWrap = false,
                        style = style,
                        color = if (chosen) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
