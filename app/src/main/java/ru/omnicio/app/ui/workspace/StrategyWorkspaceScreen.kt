package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import kotlin.math.roundToInt

@Composable
fun StrategyWorkspaceScreen(userId: String, onBack: () -> Unit, onCurrentRules: () -> Unit) {
    val context = LocalContext.current
    val store = remember(userId) { context.applicationContext.getSharedPreferences("strategy_draft_$userId", 0) }
    var draft by remember(userId) { mutableStateOf(StrategyDraft(
        goal = store.getInt("goal", 0).coerceIn(0, 2), horizon = store.getInt("horizon", 2).coerceIn(0, 2),
        market = store.getInt("market", 0).coerceIn(0, 1), qualification = store.getInt("qualification", 0).coerceIn(0, 1),
        reserve = store.getInt("reserve", 10).coerceIn(0, 50), companyLimit = store.getInt("company", 5).coerceIn(1, 15),
        sectorLimit = store.getInt("sector", 25).coerceIn(5, 50), reinvest = store.getInt("reinvest", 0).coerceIn(0, 2),
        currencyIncome = store.getBoolean("currency", true),
        ratings = store.getStringSet("ratings", RatingChoices.toSet()).orEmpty().intersect(RatingChoices.toSet()),
    )) }
    var section by rememberSaveable { mutableIntStateOf(0) }
    var saved by rememberSaveable { mutableStateOf(false) }
    val change: (StrategyDraft) -> Unit = { draft = it; saved = false }
    WorkspaceDetailPage("Мои стратегии", "Правила долгосрочного капитала", onBack) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            SpectrumTabs(listOf("Цель", "Отбор", "Доли", "Доход"), section, { section = it }, Modifier.padding(horizontal = 20.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item { SpectrumCard(emphasized = true) {
                    SpectrumBadge("Черновик · не применяется")
                    Text("Будущая стратегия", style = MaterialTheme.typography.titleLarge)
                    Text("Вы можете настроить и сохранить предпочтения. Расчёт по этим правилам ещё не подключён.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    SpectrumSecondaryButton("Действующий инвестиционный профиль", onCurrentRules, Modifier.fillMaxWidth())
                } }
                when (section) {
                    0 -> {
                        item { SpectrumCard { WorkspaceChoices("Главная цель", listOf("Сохранение капитала", "Рост капитала", "Регулярные выплаты"), draft.goal) { change(draft.copy(goal = it)) } } }
                        item { SpectrumCard { WorkspaceChoices("Горизонт", listOf("До года", "1–3 года", "Более 3 лет"), draft.horizon) { change(draft.copy(horizon = it)) } } }
                    }
                    1 -> {
                        item { SpectrumCard { WorkspaceChoices("Рынок", listOf("Московская биржа", "Вне Московской биржи"), draft.market) { change(draft.copy(market = it)) }
                            Text("Только доступные вашему счёту инструменты. Заблокированные исключаются.", style = MaterialTheme.typography.bodyMedium) } }
                        item { SpectrumCard { WorkspaceChoices("Статус инвестора", listOf("Неквалифицированный", "Квалифицированный"), draft.qualification) { change(draft.copy(qualification = it)) }
                            Text("Выбор не подтверждает статус у брокера и не открывает доступ к бумагам.", style = MaterialTheme.typography.bodySmall) } }
                        item { SpectrumCard {
                            Text("Кредитные рейтинги", style = MaterialTheme.typography.titleLarge)
                            Text("Нижняя граница — BBB−. Можно сузить выбор.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            RatingChoices.forEach { rating -> WorkspaceToggle(rating, "", rating in draft.ratings) { enabled ->
                                change(draft.copy(ratings = if (enabled) draft.ratings + rating else draft.ratings - rating))
                            } }
                        } }
                    }
                    2 -> {
                        item { DraftSlider("Денежный резерв", draft.reserve, 0f..50f) { change(draft.copy(reserve = it)) } }
                        item { DraftSlider("Предел на компанию", draft.companyLimit, 1f..15f) { change(draft.copy(companyLimit = it)) } }
                        item { DraftSlider("Предел на отрасль", draft.sectorLimit, 5f..50f) { change(draft.copy(sectorLimit = it)) } }
                        item { Text("Доли относятся ко всему портфелю. Несколько выпусков одной компании не создают независимую диверсификацию.", color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                    else -> {
                        item { SpectrumCard { WorkspaceChoices("Поступления", listOf("Реинвестировать", "Пополнять резерв", "Сохранять для выплат"), draft.reinvest) { change(draft.copy(reinvest = it)) } } }
                        item { SpectrumCard { WorkspaceToggle("Валютная привязка", "Рассматривать инструменты с выплатой в рублях", draft.currencyIncome) { change(draft.copy(currencyIncome = it)) }
                            Text("Валютная привязка не устраняет риски эмитента и инфраструктуры.", style = MaterialTheme.typography.bodySmall) } }
                    }
                }
                if (draft.ratings.isEmpty()) item { Text("Выберите хотя бы один допустимый рейтинг.", color = MaterialTheme.colorScheme.error) }
                item { SpectrumPrimaryButton(if (saved) "Черновик сохранён" else "Сохранить черновик", {
                    store.edit().putInt("goal", draft.goal).putInt("horizon", draft.horizon).putInt("market", draft.market)
                        .putInt("qualification", draft.qualification).putInt("reserve", draft.reserve).putInt("company", draft.companyLimit)
                        .putInt("sector", draft.sectorLimit).putInt("reinvest", draft.reinvest).putBoolean("currency", draft.currencyIncome)
                        .putStringSet("ratings", draft.ratings).apply()
                    saved = true
                }, Modifier.fillMaxWidth(), enabled = draft.ratings.isNotEmpty()) }
            }
        }
    }
}

@Composable
private fun DraftSlider(title: String, value: Int, range: ClosedFloatingPointRange<Float>, onChange: (Int) -> Unit) {
    SpectrumCard {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text("$value%", style = MaterialTheme.typography.headlineMedium)
        Slider(value.toFloat(), { onChange(it.roundToInt()) }, valueRange = range,
            steps = (range.endInclusive - range.start).toInt() - 1)
    }
}
