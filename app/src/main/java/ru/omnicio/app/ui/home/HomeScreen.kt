package ru.omnicio.app.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
import ru.omnicio.app.ui.workspace.*

/** A decision workspace: capital, next destination and actual allocation. */
@Composable
fun HomeScreen(user: AnalystUser, state: PortfolioUiState, selectedCurrency: PortfolioCurrency,
    refreshing: Boolean, refreshError: String?, lastUpdatedMillis: Long?, onCurrencyClick: () -> Unit,
    onOpenPortfolio: () -> Unit, onOpenRecommendations: () -> Unit, onOpenRisk: () -> Unit,
    onOpenMessages: () -> Unit, onOpenProfile: () -> Unit,
    modifier: Modifier = Modifier, onConnect: () -> Unit = onOpenProfile,
    onOpenPayments: () -> Unit = onOpenPortfolio) {
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val waiting = state == PortfolioUiState.Loading || state == PortfolioUiState.ApiConnected
    val prefs = LocalWorkspacePreferences.current.value
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Home, onOpenPortfolio, onOpenProfile) }) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding),
                contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item(key = "brand-header") { HomeHeader(user, onOpenMessages) }
                item(key = "portfolio-hero") {
                    CapitalHero(state, snapshot, selectedCurrency, refreshing, refreshError, lastUpdatedMillis,
                        prefs.hideHomeBalance, onCurrencyClick, onConnect)
                }
                item(key = "assistant") { HomeNextStep(state, snapshot, refreshError, waiting, onConnect, onOpenRisk, onOpenRecommendations) }
                if (!snapshot?.warnings.isNullOrEmpty()) {
                    item(key = "attention") { SpectrumCard {
                        Text("Требует внимания", style = MaterialTheme.typography.titleMedium)
                        snapshot!!.warnings.take(2).forEach { Text(it) }
                        if (snapshot.warnings.size > 2) DetailFold("Все ограничения (${snapshot.warnings.size})") { snapshot.warnings.drop(2).forEach { Text(it) } }
                    } }
                }
                item(key = "monitoring") { ObservationSummary(onOpenRisk) }
                item(key = "capabilities") { HomeQuickActions(onOpenPortfolio, onOpenPayments) }
                if (snapshot != null && prefs.homeStructure) {
                    item(key = "allocation") { AllocationOverview(snapshot, onOpenPortfolio) }
                }

            }
        }
    }
}

@Composable
private fun HomeHeader(user: AnalystUser, onMessagesClick: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        SpectrumBrandOrb(Modifier.size(42.dp), compact = true)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("Analyst AI", modifier = Modifier.semantics { contentDescription = user.name?.let { "Analyst AI · $it" } ?: "Analyst AI" },
                style = MaterialTheme.typography.labelLarge, color = LocalSpectrumPalette.current.cyan)
            Text("Ваш капитал", style = MaterialTheme.typography.headlineMedium)
        }
        BadgedBox(badge = { AttentionBadge() }) {
        IconButton(onClick = onMessagesClick, modifier = Modifier.size(48.dp)
            .semantics { contentDescription = "Уведомления" }) {
            SpectrumLiveFeatureIcon(SpectrumLiveFeature.Notifications, Modifier.size(34.dp),
                motionAllowed = false)
        }
        }
    }
}

@Composable
private fun CapitalHero(state: PortfolioUiState, snapshot: PortfolioSnapshot?, currency: PortfolioCurrency,
    refreshing: Boolean, error: String?, updated: Long?, hidden: Boolean, onCurrency: () -> Unit,
    onConnect: () -> Unit) {
    SpectrumCard(emphasized = true) {
        if (snapshot == null) {
            Text("Всё начинается с вашего счёта", style = MaterialTheme.typography.headlineSmall)
            Text(when (state) {
                PortfolioUiState.NotConnected -> "Подключите портфель Т-Инвестиций"
                is PortfolioUiState.Error -> state.message
                else -> "Получаем счета и позиции…"
            }, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (state == PortfolioUiState.Loading || state == PortfolioUiState.ApiConnected) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
            } else SpectrumPrimaryButton("Подключение счёта", onConnect, Modifier.fillMaxWidth())
        } else {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Всего в портфеле", Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(onClick = onCurrency, modifier = Modifier.heightIn(min = 48.dp)) { Text("${currency.name} ▾") }
            }
            Text(if (hidden) "••• •••" else snapshot.totalValue.moneyText(),
                style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
            BalanceVisibilityButton()
            if (snapshot.totalValue.currency != currency.name) Text("Показана предыдущая оценка в ${snapshot.totalValue.currency}. Запрошена ${currency.name}.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (!hidden) {
                SignedAmount(snapshot.expectedYieldAmount, snapshot.expectedYieldPercent)
                Text("Текущий результат брокера", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = .35f))
            val observed = snapshot.asOf ?: updated?.let { java.time.Instant.ofEpochMilli(it).toString() }
            Text("Данные: ${relativeObservation(observed)}${if (refreshing) " · обновляем" else ""}",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (error != null) SpectrumBadge("Сохранённые данные · обновление не удалось", accent = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun AllocationOverview(snapshot: PortfolioSnapshot, onOpenPortfolio: () -> Unit) {
    SpectrumCard {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("Распределение", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
            TextButton(onClick = onOpenPortfolio) { Text("Подробнее ›") }
        }
        val valid = snapshot.allocations.all { it.sharePercent.toBigDecimal().signum() >= 0 } &&
            snapshot.allocations.sumOf { it.sharePercent.toBigDecimal() } <= java.math.BigDecimal("100.1")
        if (LocalWorkspacePreferences.current.value.hideHomeBalance) { Text("Структура скрыта"); return@SpectrumCard }
        if (snapshot.allocations.isEmpty()) Text("Структура пока не получена")
        val palette = LocalSpectrumPalette.current
        val colors = listOf(palette.cyan, palette.violet, palette.amber, palette.blue, palette.rose)
        val sorted = snapshot.allocations.sortedByDescending { it.sharePercent.toBigDecimal() }
        val visible = sorted.take(3)
        visible.forEachIndexed { index, item ->
            DataRow(item.title, item.sharePercent.percentText())
            if (valid) SpectrumProgressBar(item.sharePercent.toBigDecimal().toFloat() / 100f, accent = colors[index])
        }
        if (sorted.size > 3) DetailFold("Остальные категории (${sorted.size - 3})") {
            sorted.drop(3).forEach { DataRow(it.title, it.sharePercent.percentText()) }
        }
        Text("Счетов: ${snapshot.accounts.size}", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun HomeNextStep(state: PortfolioUiState, snapshot: PortfolioSnapshot?, refreshError: String?, waiting: Boolean,
    onConnect: () -> Unit, onOpenRisk: () -> Unit, onOpenRecommendations: () -> Unit) {
                    SpectrumCard(emphasized = true) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            SpectrumAnalystAvatar(
                                mood = when {
                                    refreshError != null || snapshot?.warnings?.isNotEmpty() == true -> AnalystAvatarMood.Attention
                                    snapshot == null -> AnalystAvatarMood.Waiting
                                    else -> AnalystAvatarMood.Ready
                                },
                                motionAllowed = LocalSpectrumMotionPreference.current.enabled,
                                modifier = Modifier.size(64.dp).testTag("spectrum-ai-analyst"))
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("Следующий шаг", style = MaterialTheme.typography.titleLarge)
                                Text(when { waiting -> "Получаем данные счёта"; state is PortfolioUiState.Error -> "Проверьте доступ к данным"; snapshot == null -> "Подключите счёт, чтобы начать"; snapshot.warnings.isNotEmpty() -> "Проверьте ограничения данных ниже"; else -> "Ознакомьтесь с последним анализом" },
                                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                        SpectrumPrimaryButton(when {
                            waiting -> "Получаем данные…"
                            state is PortfolioUiState.Error -> "Проверить подключение"
                            snapshot == null -> "Подключить портфель"
                            snapshot.warnings.isNotEmpty() -> "Посмотреть риски"
                            else -> "Посмотреть анализ"
                        },
                            when {
                                snapshot == null -> onConnect
                                snapshot.warnings.isNotEmpty() -> onOpenRisk
                                else -> onOpenRecommendations
                            }, Modifier.fillMaxWidth(), enabled = !waiting)
                    }
}
