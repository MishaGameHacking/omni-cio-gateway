package ru.omnicio.app.ui.profile

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp

/** Equal tabs at normal size; horizontally scrollable single-line tabs at large font. */
@Composable
internal fun ProfileSectionTabs(selected: Int, onSelect: (Int) -> Unit) {
    val labels = listOf("Настройки", "Профиль", "Инфо")
    val density = LocalDensity.current
    val measurer = rememberTextMeasurer()
    val style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Bold)
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
        Row(Modifier.fillMaxWidth().horizontalScroll(scroll).selectableGroup()
            .semantics { testTagsAsResourceId = true }.testTag("profile-tabs")) {
            labels.forEachIndexed { index, label ->
                val chosen = selected == index
                Column(
                    modifier = Modifier.width(width).heightIn(min = 56.dp)
                        .selectable(chosen, role = Role.Tab, onClick = { onSelect(index) })
                        .testTag("profile-tab-$index").padding(horizontal = 8.dp, vertical = 10.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(label, maxLines = 1, softWrap = false, style = style,
                        color = if (chosen) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface)
                    HorizontalDivider(thickness = 2.dp,
                        color = if (chosen) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.background)
                }
            }
        }
    }
}
