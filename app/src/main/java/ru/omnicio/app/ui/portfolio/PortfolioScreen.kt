package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.math.BigDecimal
import java.text.NumberFormat
import java.util.Locale
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab

data class ApiDecimal(
    val units: Long,
    val nano: Int,
) {
    fun toBigDecimal(): BigDecimal =
        BigDecimal.valueOf(units).add(BigDecimal.valueOf(nano.toLong(), 9))
}

data class MoneyAmount(
    val value: ApiDecimal,
    val currency: String,
)

data class PortfolioPosition(
    val id: String,
    val title: String,
    val ticker: String?,
    val quantity: ApiDecimal?,
    val currentValue: MoneyAmount?,
    val expectedYieldPercent: ApiDecimal?,
)

data class PortfolioAccount(
    val id: String,
    val name: String,
    val totalValue: MoneyAmount,
    val expectedYieldPercent: ApiDecimal?,
    val positions: List<PortfolioPosition>,
)

data class PortfolioAllocation(
    val title: String,
    val sharePercent: ApiDecimal,
)

data class PortfolioSnapshot(
    val totalValue: MoneyAmount,
    val expectedYieldAmount: MoneyAmount?,
    val expectedYieldPercent: ApiDecimal?,
    val accounts: List<PortfolioAccount>,
    val allocations: List<PortfolioAllocation>,
)

sealed interface PortfolioUiState {
    data object NotConnected : PortfolioUiState
    data object Loading : PortfolioUiState
    data class Ready(val snapshot: PortfolioSnapshot) : PortfolioUiState
    data class Error(val message: String) : PortfolioUiState
}

private val ScreenBackground = Color(0xFFF5F6F8)
private val CardBackground = Color(0xFFFFFFFF)
private val AccentBlue = Color(0xFF6EA5F8)
private val PositiveGreen = Color(0xFF16A34A)
private val NegativeRed = Color(0xFFDC2626)
private val MutedText = Color(0xFF8A9099)
private val Divider = Color(0xFFE8EAED)

@Composable
fun PortfolioScreen(
    state: PortfolioUiState,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = ScreenBackground,
        bottomBar = {
            AnalystBottomBar(
                selected = AnalystTab.Portfolio,
                onPortfolioClick = {},
                onProfileClick = onProfileClick,
            )
        },
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .background(ScreenBackground)
                .padding(innerPadding),
            contentPadding = PaddingValues(
                start = 20.dp,
                top = 12.dp,
                end = 20.dp,
                bottom = 24.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                PortfolioHeader()
            }

            when (state) {
                PortfolioUiState.NotConnected -> {
                    item {
                        NotConnectedCard()
                    }
                    item {
                        SectionTitle("Счета")
                    }
                    item {
                        EmptyAccountsCard()
                    }
                }

                PortfolioUiState.Loading -> {
                    item {
                        LoadingCard()
                    }
                }

                is PortfolioUiState.Error -> {
                    item {
                        ErrorCard(message = state.message)
                    }
                }

                is PortfolioUiState.Ready -> {
                    item {
                        PortfolioSummaryCard(snapshot = state.snapshot)
                    }

                    item {
                        SectionTitle("Счета")
                    }

                    if (state.snapshot.accounts.isEmpty()) {
                        item {
                            EmptyAccountsCard()
                        }
                    } else {
                        items(
                            items = state.snapshot.accounts,
                            key = { it.id },
                        ) { account ->
                            AccountCard(account = account)
                        }
                    }

                    if (state.snapshot.allocations.isNotEmpty()) {
                        item {
                            PortfolioStructureCard(
                                totalValue = state.snapshot.totalValue,
                                allocations = state.snapshot.allocations,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PortfolioHeader() {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column {
            Text(
                text = "Analyst AI",
                style = MaterialTheme.typography.labelLarge,
                color = MutedText,
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = "Портфель",
                fontSize = 34.sp,
                lineHeight = 40.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }

        Surface(
            modifier = Modifier.size(44.dp),
            shape = CircleShape,
            color = Color(0xFF111318),
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = "AI",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
    }
}

@Composable
private fun NotConnectedCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
    ) {
        Column(
            modifier = Modifier.padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "Данные портфеля ещё не подключены",
                fontSize = 24.sp,
                lineHeight = 30.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Analyst AI не подставляет демонстрационные суммы. После подключения T‑Invest API здесь появятся только фактические данные пользователя.",
                style = MaterialTheme.typography.bodyLarge,
                color = MutedText,
            )
            ApiSourceBadge()
        }
    }
}

@Composable
private fun ApiSourceBadge() {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = Color(0xFFEAF2FF),
    ) {
        Text(
            text = "Источник данных · T‑Invest API",
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            color = Color(0xFF356EC9),
            style = MaterialTheme.typography.labelLarge,
        )
    }
}

@Composable
private fun LoadingCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
    ) {
        Row(
            modifier = Modifier.padding(24.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(26.dp),
                color = AccentBlue,
                strokeWidth = 3.dp,
            )
            Spacer(modifier = Modifier.width(14.dp))
            Column {
                Text(
                    text = "Получаем портфель",
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 18.sp,
                )
                Text(
                    text = "Загружаются фактические данные пользователя",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MutedText,
                )
            }
        }
    }
}

@Composable
private fun ErrorCard(message: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
    ) {
        Column(
            modifier = Modifier.padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "Не удалось получить портфель",
                fontWeight = FontWeight.Bold,
                fontSize = 20.sp,
            )
            Text(
                text = message,
                style = MaterialTheme.typography.bodyLarge,
                color = NegativeRed,
            )
        }
    }
}

@Composable
private fun PortfolioSummaryCard(snapshot: PortfolioSnapshot) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
    ) {
        Column(
            modifier = Modifier.padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = "Общая стоимость",
                style = MaterialTheme.typography.bodyLarge,
                color = MutedText,
            )
            Text(
                text = snapshot.totalValue.formatted(),
                fontSize = 36.sp,
                lineHeight = 42.sp,
                fontWeight = FontWeight.Bold,
            )

            YieldRow(
                amount = snapshot.expectedYieldAmount,
                percent = snapshot.expectedYieldPercent,
            )

            Spacer(modifier = Modifier.height(4.dp))
            ApiSourceBadge()
        }
    }
}

@Composable
private fun YieldRow(
    amount: MoneyAmount?,
    percent: ApiDecimal?,
) {
    if (amount == null && percent == null) {
        return
    }

    val sign = percent?.toBigDecimal()?.signum()
        ?: amount?.value?.toBigDecimal()?.signum()
        ?: 0

    val color = when {
        sign > 0 -> PositiveGreen
        sign < 0 -> NegativeRed
        else -> MutedText
    }

    val parts = buildList {
        amount?.let { add(it.formatted(withSign = true)) }
        percent?.let { add(it.formattedPercent(withSign = true)) }
    }

    Surface(
        shape = RoundedCornerShape(999.dp),
        color = color.copy(alpha = 0.10f),
    ) {
        Text(
            text = parts.joinToString(" · "),
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            color = color,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        fontSize = 25.sp,
        lineHeight = 30.sp,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.onSurface,
    )
}

@Composable
private fun EmptyAccountsCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
    ) {
        Text(
            text = "Счета появятся после получения реальных данных T‑Invest API.",
            modifier = Modifier.padding(22.dp),
            style = MaterialTheme.typography.bodyLarge,
            color = MutedText,
        )
    }
}

@Composable
private fun AccountCard(account: PortfolioAccount) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
    ) {
        Column(modifier = Modifier.padding(22.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Top,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = account.totalValue.formatted(),
                        fontSize = 24.sp,
                        lineHeight = 30.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        text = account.name,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }

                account.expectedYieldPercent?.let { value ->
                    Spacer(modifier = Modifier.width(10.dp))
                    YieldPercentChip(value = value)
                }
            }

            if (account.positions.isEmpty()) {
                Spacer(modifier = Modifier.height(18.dp))
                Text(
                    text = "Позиции отсутствуют",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MutedText,
                )
            } else {
                Spacer(modifier = Modifier.height(18.dp))
                HorizontalDivider(color = Divider)
                account.positions.forEachIndexed { index, position ->
                    PositionRow(position = position)
                    if (index != account.positions.lastIndex) {
                        HorizontalDivider(color = Divider)
                    }
                }
            }
        }
    }
}

@Composable
private fun YieldPercentChip(value: ApiDecimal) {
    val sign = value.toBigDecimal().signum()
    val color = when {
        sign > 0 -> PositiveGreen
        sign < 0 -> NegativeRed
        else -> MutedText
    }

    Surface(
        shape = RoundedCornerShape(999.dp),
        color = color.copy(alpha = 0.10f),
    ) {
        Text(
            text = value.formattedPercent(withSign = true),
            modifier = Modifier.padding(horizontal = 9.dp, vertical = 5.dp),
            color = color,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun PositionRow(position: PortfolioPosition) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            modifier = Modifier.size(46.dp),
            shape = CircleShape,
            color = Color(0xFFF0F2F4),
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text(
                    text = position.ticker
                        ?.take(2)
                        ?.uppercase(Locale.ROOT)
                        ?: "•",
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF4B515A),
                )
            }
        }

        Spacer(modifier = Modifier.width(14.dp))

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = position.title,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )

            position.quantity?.let { quantity ->
                Text(
                    text = "Количество: ${quantity.formattedQuantity()}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MutedText,
                )
            }
        }

        position.currentValue?.let { currentValue ->
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = currentValue.formatted(),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                )
                position.expectedYieldPercent?.let { yield ->
                    Text(
                        text = yield.formattedPercent(withSign = true),
                        style = MaterialTheme.typography.bodySmall,
                        color = when {
                            yield.toBigDecimal().signum() > 0 -> PositiveGreen
                            yield.toBigDecimal().signum() < 0 -> NegativeRed
                            else -> MutedText
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun PortfolioStructureCard(
    totalValue: MoneyAmount,
    allocations: List<PortfolioAllocation>,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
    ) {
        Column(
            modifier = Modifier.padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Text(
                text = "Структура портфеля",
                fontSize = 24.sp,
                lineHeight = 30.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = totalValue.formatted(),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )

            allocations.forEach { allocation ->
                AllocationRow(allocation = allocation)
            }
        }
    }
}

@Composable
private fun AllocationRow(allocation: PortfolioAllocation) {
    val decimalPercent = allocation.sharePercent.toBigDecimal()
    val fraction = decimalPercent
        .divide(BigDecimal("100"))
        .toFloat()
        .coerceIn(0f, 1f)

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = allocation.title,
                style = MaterialTheme.typography.bodyMedium,
                color = MutedText,
            )
            Text(
                text = allocation.sharePercent.formattedPercent(),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(CircleShape)
                .background(Color(0xFFE8EEF7)),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(fraction)
                    .fillMaxHeight()
                    .background(AccentBlue),
            )
        }
    }
}

private fun MoneyAmount.formatted(withSign: Boolean = false): String {
    val decimal = value.toBigDecimal()
    val number = decimal.formattedNumber(
        minFractionDigits = 2,
        maxFractionDigits = 2,
        withSign = withSign,
    )
    return "$number ${currencySymbol(currency)}"
}

private fun ApiDecimal.formattedPercent(withSign: Boolean = false): String =
    "${toBigDecimal().formattedNumber(0, 2, withSign)}%"

private fun ApiDecimal.formattedQuantity(): String =
    toBigDecimal().formattedNumber(0, 8, withSign = false)

private fun BigDecimal.formattedNumber(
    minFractionDigits: Int,
    maxFractionDigits: Int,
    withSign: Boolean,
): String {
    val formatter = NumberFormat.getNumberInstance(Locale.forLanguageTag("ru-RU")).apply {
        minimumFractionDigits = minFractionDigits
        maximumFractionDigits = maxFractionDigits
        isGroupingUsed = true
    }

    val formatted = formatter.format(this)
    return if (withSign && signum() > 0) "+$formatted" else formatted
}

private fun currencySymbol(currency: String): String =
    when (currency.uppercase(Locale.ROOT)) {
        "RUB" -> "₽"
        "USD" -> "$"
        "EUR" -> "€"
        else -> currency.uppercase(Locale.ROOT)
    }

@Preview(showBackground = true, backgroundColor = 0xFFF5F6F8)
@Composable
private fun PortfolioScreenPreview() {
    MaterialTheme {
        PortfolioScreen(
            state = PortfolioUiState.NotConnected,
            onProfileClick = {},
        )
    }
}
