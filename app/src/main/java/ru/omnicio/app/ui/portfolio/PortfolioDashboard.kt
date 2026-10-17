package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.spectrum.*

/** Production portfolio presenter. No synthetic balances, goals or chart points. */
@Composable
internal fun PortfolioDashboard(
    state: PortfolioUiState,
    selectedCurrency: PortfolioCurrency,
    refreshing: Boolean,
    refreshError: String?,
    lastUpdatedMillis: Long?,
    accessToken: String,
    selectedSection: Int,
    onSelectSection: (Int) -> Unit,
    listState: LazyListState,
    onCurrencyClick: () -> Unit,
    onProfileClick: () -> Unit,
    onOpenAccount: (PortfolioAccount) -> Unit,
    onOpenSection: (Int) -> Unit,
    onPositionClick: (String, PortfolioPosition) -> Unit,
    modifier: Modifier = Modifier,
    assetQuery: String = "", assetSector: String? = null, assetKind: String? = null,
) {
    val openWorkspace = LocalWorkspaceNavigator.current
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    Column(modifier.fillMaxSize().semantics { testTagsAsResourceId = true }) {
        SpectrumPageHeader(
            title = "Портфель",
            subtitle = "Состав, счета и движение капитала",
            symbol = SpectrumSymbol.Portfolio,
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
        )
        SpectrumTabs(
            listOf("Структура", "Активы", "Динамика"),
            selectedSection,
            onSelectSection,
            Modifier.padding(horizontal = 20.dp).testTag("portfolio-sections"),
        )
        if (selectedSection == 2 && snapshot != null && snapshot.accounts.isNotEmpty()) {
            PortfolioHistorySection(snapshot.accounts, accessToken, onCurrencyClick, Modifier.weight(1f))
        } else if (selectedSection == 1 && snapshot != null) {
            PortfolioAssetBrowser(snapshot, onPositionClick, Modifier.weight(1f), assetQuery, assetSector, assetKind)
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f).fillMaxWidth().testTag("portfolio-content"),
                state = listState,
                contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                if (snapshot == null) {
                    item(key = "connection") { PortfolioConnectionCard(state, onProfileClick) }
                } else {
                    item(key = "balance") {
                        PortfolioBalanceCard(snapshot, selectedCurrency, refreshing, refreshError, lastUpdatedMillis, onCurrencyClick, onOpenSection)
                    }
                    if (selectedSection == 0) {
                        item(key = "sectors") { WorkspaceLink("Отрасли и классы", "Состав ваших вложений", SpectrumSymbol.Market) {
                            openWorkspace(WorkspaceRoute.Market)
                        } }
                        item(key = "allocation") {
                            SpectrumCard {
                                SectionHeading("Баланс активов")
                                AssetStructure(snapshot.allocations, snapshot.totalValue)
                            }
                        }
                        item(key = "accounts-title") { SectionHeading("Мои счета") }
                        items(snapshot.accounts, key = { "account:${it.id}" }) { account ->
                            PortfolioAccountLink(account) { onOpenAccount(account) }
                        }
                        item(key = "strategy") {
                            SpectrumActionTile(
                                title = "Моя стратегия",
                                subtitle = "Цель, отбор, доли и доход",
                                symbol = SpectrumSymbol.Goal,
                                onClick = { openWorkspace(WorkspaceRoute.Strategies) },
                            )
                        }
                    } else {
                        snapshot.accounts.forEach { account ->
                            item(key = "account-heading:${account.id}") {
                                PortfolioAccountLink(account) { onOpenAccount(account) }
                            }
                            items(account.positions, key = { "position:${account.id}:${it.id}" }) { position ->
                                SpectrumCard {
                                    PositionLine(position) { onPositionClick(account.id, position) }
                                }
                            }
                            if (account.positions.isEmpty()) {
                                item(key = "empty-account:${account.id}") { Notice("В этом счёте пока нет позиций.") }
                            }
                            if (account.virtualPositions.isNotEmpty()) {
                                item(key = "virtual:${account.id}") {
                                    SpectrumSecondaryButton("Виртуальные позиции счёта", { onOpenAccount(account) }, Modifier.fillMaxWidth())
                                }
                            }
                        }
                    }
                    if (snapshot.accounts.isEmpty()) {
                        item(key = "empty") { SpectrumCard { Text("Доступных счетов не найдено") } }
                    }
                    if (snapshot.warnings.isNotEmpty()) {
                        item(key = "warnings") { SpectrumCard { Notice(snapshot.warnings.joinToString("\n")) } }
                    }
                }
            }
        }
    }
}

@Composable
private fun PortfolioBalanceCard(
    snapshot: PortfolioSnapshot,
    selectedCurrency: PortfolioCurrency,
    refreshing: Boolean,
    error: String?,
    lastUpdatedMillis: Long?,
    onCurrency: () -> Unit,
    onOpenSection: (Int) -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val fontScale = LocalDensity.current.fontScale
    SpectrumCard(emphasized = true) {
        Text("Общий капитал", color = palette.cyan, style = MaterialTheme.typography.labelLarge)
        Text(
            snapshot.totalValue.moneyText(),
            modifier = Modifier,
            style = MaterialTheme.typography.headlineLarge,
            fontWeight = FontWeight.Bold,
        )
        if (snapshot.expectedYieldAmount != null || snapshot.expectedYieldPercent != null) {
            SignedAmount(snapshot.expectedYieldAmount, snapshot.expectedYieldPercent)
            Notice("Текущий результат брокера")
        }
        CurrencyChoice(selectedCurrency.name)
        val waiting = refreshing && snapshot.totalValue.currency != selectedCurrency.name
        Notice(if (waiting) "Получаем оценку в ${selectedCurrency.name}…" else "Оценка брокера в ${selectedCurrency.name}")
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val enabled = snapshot.accounts.isNotEmpty()
            if (portfolioStackedLayout(maxWidth.value, fontScale)) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SpectrumSecondaryButton("Операции", { onOpenSection(1) }, Modifier.fillMaxWidth(), enabled)
                    SpectrumPrimaryButton("Аналитика", { onOpenSection(3) }, Modifier.fillMaxWidth(), enabled)
                }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SpectrumSecondaryButton("Операции", { onOpenSection(1) }, Modifier.weight(1f), enabled)
                    SpectrumPrimaryButton("Аналитика", { onOpenSection(3) }, Modifier.weight(1f), enabled)
                }
            }
        }
        val observed = snapshot.asOf ?: lastUpdatedMillis?.let { java.time.Instant.ofEpochMilli(it).toString() }
        if (error != null) {
            SpectrumBadge("Не удалось обновить", accent = MaterialTheme.colorScheme.error)
            Notice(error)
        }
        Notice("Данные: ${dateText(observed)}" + if (refreshing) " · обновляем" else " · автообновление")
    }
}

@Composable
private fun PortfolioAccountLink(account: PortfolioAccount, onOpen: () -> Unit) {
    SpectrumCard(onClick = onOpen) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Portfolio, Modifier.size(48.dp), selected = true, tile = true)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(account.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text(account.totalValue.moneyText(), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                Text("Позиций: ${account.positions.size} · открыть счёт", color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun PortfolioConnectionCard(state: PortfolioUiState, onProfile: () -> Unit) {
    SpectrumCard(emphasized = true) {
        SpectrumIcon(SpectrumSymbol.Portfolio, Modifier.size(64.dp), selected = true, tile = true)
        when (state) {
            PortfolioUiState.Loading, PortfolioUiState.ApiConnected -> {
                CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                SectionHeading("Собираем ваш портфель")
                Notice("Загружаем счета и позиции из подключённого T‑Invest API.")
            }
            is PortfolioUiState.Error -> {
                SectionHeading("Данные пока недоступны")
                Notice(state.message)
                Notice("Повторная проверка выполняется автоматически, пока приложение открыто.")
            }
            else -> {
                SectionHeading("Начните со своего портфеля")
                Notice("Подключите read-only токен брокера. Баланс, активы и история появятся из ваших данных, без демонстрационных сумм.")
                SpectrumPrimaryButton("Подключить портфель", onProfile, Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Sources)
            }
        }
    }
}

@Composable
private fun PortfolioHistorySection(
    accounts: List<PortfolioAccount>,
    accessToken: String,
    onCurrency: () -> Unit,
    modifier: Modifier,
) {
    var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
    val account = accounts.firstOrNull { it.id == selectedId } ?: accounts.first()
    Column(modifier.fillMaxWidth()) {
        if (accounts.size > 1) {
            SpectrumTabs(accounts.map { it.name }, accounts.indexOf(account), { selectedId = accounts[it].id }, Modifier.padding(horizontal = 20.dp, vertical = 8.dp))
        }
        if (accessToken.isBlank()) {
            SpectrumCard(Modifier.padding(20.dp)) { Notice("История стоимости доступна после входа в Analyst AI.") }
        } else {
            // Existing authenticated analytics, with its real snapshot history,
            // period controls, loading/errors and incomplete-data warnings.
            AccountAnalytics(accessToken, account, onCurrency, historyOnly = true)
        }
    }
}

