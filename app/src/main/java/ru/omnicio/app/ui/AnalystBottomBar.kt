package ru.omnicio.app.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

enum class AnalystTab {
    Portfolio,
    Profile,
}

@Composable
fun AnalystBottomBar(
    selected: AnalystTab,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.navigationBarsPadding(),
        color = Color.White,
        shadowElevation = 10.dp,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp),
        ) {
            BottomBarItem(
                modifier = Modifier.weight(1f),
                selected = selected == AnalystTab.Portfolio,
                symbol = "▰",
                label = "Портфель",
                onClick = onPortfolioClick,
            )
            BottomBarItem(
                modifier = Modifier.weight(1f),
                selected = selected == AnalystTab.Profile,
                symbol = "●",
                label = "Профиль",
                onClick = onProfileClick,
            )
        }
    }
}

@Composable
private fun BottomBarItem(
    selected: Boolean,
    symbol: String,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    androidx.compose.material3.TextButton(
        modifier = modifier,
        onClick = onClick,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = symbol,
                color = if (selected) Color(0xFF16191F) else Color(0xFF9AA0A8),
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                text = label,
                color = if (selected) Color(0xFF16191F) else Color(0xFF9AA0A8),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
            )
        }
    }
}
