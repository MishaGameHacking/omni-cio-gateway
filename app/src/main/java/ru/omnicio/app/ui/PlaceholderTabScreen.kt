package ru.omnicio.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumCard

@Composable
fun PlaceholderTabScreen(
    selected: AnalystTab,
    title: String,
    description: String,
    modifier: Modifier = Modifier,
) {
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = Color.Transparent,
            bottomBar = {
                AnalystBottomBar(
                    selected = selected,
                    onPortfolioClick = {},
                    onProfileClick = {},
                )
            },
        ) { innerPadding ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp),
            ) {
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "Analyst AI",
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            text = title,
                            fontSize = 34.sp,
                            lineHeight = 40.sp,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
                item {
                    SpectrumCard(Modifier.fillMaxWidth()) {
                        Text(
                            text = "Раздел подготовлен",
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            text = description,
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}
