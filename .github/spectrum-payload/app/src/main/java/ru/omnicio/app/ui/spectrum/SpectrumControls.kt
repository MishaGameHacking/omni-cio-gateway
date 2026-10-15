package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun SpectrumTabs(options: List<String>, selected: Int, onSelect: (Int) -> Unit, modifier: Modifier = Modifier) {
    val palette = LocalSpectrumPalette.current
    val shape = RoundedCornerShape(12.dp)
    Row(modifier.fillMaxWidth().clip(shape).background(palette.card)
        .border(1.dp, palette.cyan.copy(alpha = .16f), shape)
        .horizontalScroll(rememberScrollState()).selectableGroup().padding(4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        options.forEachIndexed { index, title ->
            val active = index == selected
            val fill = if (active) Brush.linearGradient(listOf(Color(0xFF345AE0), Color(0xFF6540C9)))
                else Brush.linearGradient(listOf(Color.Transparent, Color.Transparent))
            Box(Modifier.heightIn(min = 48.dp).clip(RoundedCornerShape(8.dp)).background(fill)
                .selectable(selected = active, role = Role.Tab, onClick = { onSelect(index) })
                .padding(horizontal = 13.dp, vertical = 12.dp)) {
                Text(title, color = if (active) Color.White else MaterialTheme.colorScheme.onSurfaceVariant,
                    fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                    style = MaterialTheme.typography.bodySmall, maxLines = 1, softWrap = false)
            }
        }
    }
}
