package ru.omnicio.app.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Modifier
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.weight
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.PortfolioSnapshot
import ru.omnicio.app.ui.portfolio.percentText
import ru.omnicio.app.ui.spectrum.AnalystAvatarMood
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumAnalystAvatar
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumPrimaryButton
import ru.omnicio.app.ui.spectrum.SpectrumSymbol

/**
 * Home assistant block backed only by the currently loaded portfolio snapshot.
 * It does not imply that an LLM ran and never fabricates a score or return.
 */
@Composable
internal fun HomeAnalystCard(
    snapshot: PortfolioSnapshot?,
    refreshError: String?,
    onOpenRecommendations: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val mood = when {
        refreshError != null -> AnalystAvatarMood.Attention
        snapshot == null -> AnalystAvatarMood.Waiting
        snapshot.warnings.isNotEmpty() -> AnalystAvatarMood.Attention
        else -> AnalystAvatarMood.Ready
    }
    val accent = when (mood) {
        AnalystAvatarMood.Ready -> palette.emerald
        AnalystAvatarMood.Attention -> palette.amber
        AnalystAvatarMood.Waiting -> palette.blue
    }
    val status = when (mood) {
        AnalystAvatarMood.Ready -> "Данные готовы"
        AnalystAvatarMood.Attention -> "Нужно внимание"
        AnalystAvatarMood.Waiting -> "Ожидаю портфель"
    }
    val summary = analystSummary(snapshot, refreshError)

    SpectrumCard(emphasized = true) {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val stacked = maxWidth < 320.dp
            if (stacked) {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    SpectrumAnalystAvatar(mood, Modifier.size(124.dp))
                    AnalystIdentity(
                        status = status,
                        accent = accent,
                        centered = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    SpectrumAnalystAvatar(mood, Modifier.size(112.dp))
                    AnalystIdentity(
                        status = status,
                        accent = accent,
                        centered = false,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }

        Text(summary, style = MaterialTheme.typography.bodyMedium)
        Text(
            "Вывод по фактам текущего портфеля. Торговые поручения не создаются.",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SpectrumPrimaryButton(
            text = "Показать рекомендации",
            onClick = onOpenRecommendations,
            modifier = Modifier.fillMaxWidth(),
            symbol = SpectrumSymbol.Ideas,
        )
    }
}

@Composable
private fun AnalystIdentity(
    status: String,
    accent: Color,
    centered: Boolean,
    modifier: Modifier,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = if (centered) Alignment.CenterHorizontally else Alignment.Start,
        verticalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        Text(
            "Analyst AI",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "Ваш персональный AI‑аналитик",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SpectrumBadge(status, accent = accent)
    }
}

private fun analystSummary(snapshot: PortfolioSnapshot?, refreshError: String?): String = when {
    refreshError != null ->
        "Свежие данные получить не удалось. Я показываю сохранённый портфель и не подменяю его новыми предположениями."

    snapshot == null ->
        "Подключите портфель. Я разберу структуру, существенные изменения и ограничения понятным языком."

    snapshot.warnings.isNotEmpty() -> snapshot.warnings.first()

    snapshot.allocations.isEmpty() ->
        "Портфель получен, но источник пока не вернул сопоставимую структуру активов."

    else -> {
        val largest = snapshot.allocations.maxByOrNull { it.sharePercent.toBigDecimal() }
        if (largest == null) {
            "Портфель получен. Следующая проверка уточнит его структуру."
        } else {
            "Крупнейшая категория — ${largest.title}: ${largest.sharePercent.percentText()}. Сопоставьте её с горизонтом, резервом и допустимым риском."
        }
    }
}
