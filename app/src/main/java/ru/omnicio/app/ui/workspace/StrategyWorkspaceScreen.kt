package ru.omnicio.app.ui.workspace

import ru.omnicio.app.ui.spatial.SpatialBackHandler as BackHandler
import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton
import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog
import ru.omnicio.app.ui.spectrum.SpectrumSlider as Slider
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import kotlinx.coroutines.launch
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import kotlin.math.roundToInt

@Composable
fun StrategyWorkspaceScreen(userId: String, onBack: () -> Unit, onCurrentRules: () -> Unit) {
    val context = LocalContext.current
    val store = remember(userId) { context.applicationContext.getSharedPreferences("strategy_draft_$userId", 0) }
    var baseline by rememberSaveable(userId, stateSaver = StrategyDraftSaver) { mutableStateOf(StrategyDraft(
        goal = store.getInt("goal", 0).coerceIn(0, 2), horizon = store.getInt("horizon", 2).coerceIn(0, 2),
        market = store.getInt("market", 0).coerceIn(0, 1), reserve = store.getInt("reserve", 10).coerceIn(0, 50),
        companyLimit = store.getInt("company", 5).coerceIn(1, 15), sectorLimit = store.getInt("sector", 25).coerceIn(5, 50),
        reinvest = store.getInt("reinvest", 0).coerceIn(0, 2), currencyIncome = store.getBoolean("currency", true),
        ratings = store.getStringSet("ratings", RatingChoices.toSet()).orEmpty().intersect(RatingChoices.toSet()),
    )) }
    var draft by rememberSaveable(userId, stateSaver = StrategyDraftSaver) { mutableStateOf(baseline) }
    var percentages by rememberSaveable(userId, stateSaver = StrategyPercentDraftSaver) { mutableStateOf(StrategyPercentDraft(draft)) }
    var section by rememberSaveable { mutableIntStateOf(0) }
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val selectSection: (Int) -> Unit = { section = it; scope.launch { listState.scrollToItem(0) } }
    var saved by rememberSaveable { mutableStateOf(false) }
    var leaving by remember { mutableStateOf(false) }
    var openActiveAfterLeave by remember { mutableStateOf(false) }
    val candidate = percentages.applyTo(draft)
    val valid = candidate != null && draft.ratings.isNotEmpty()
    val dirty = draft != baseline || percentages != StrategyPercentDraft(baseline)
    val changes = strategyChanges(baseline, candidate ?: draft) +
        if (candidate == null) listOf("Проценты требуют исправления") else emptyList()
    val leave: () -> Unit = { if (dirty) leaving = true else onBack() }
    BackHandler(onBack = leave)
    val save: () -> Boolean = {
        percentages.applyTo(draft)?.takeIf { it.ratings.isNotEmpty() }?.let { verified ->
            store.edit().putInt("goal", verified.goal).putInt("horizon", verified.horizon).putInt("market", verified.market)
                .putInt("reserve", verified.reserve).putInt("company", verified.companyLimit).putInt("sector", verified.sectorLimit)
                .putInt("reinvest", verified.reinvest).putBoolean("currency", verified.currencyIncome).putStringSet("ratings", verified.ratings).apply()
            baseline = verified; draft = verified; percentages = StrategyPercentDraft(verified); saved = true
            true
        } ?: false
    }
    WorkspaceDetailPage("Моя стратегия", "Действующие правила и будущие изменения", leave, SpectrumSymbol.Goal) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            SpectrumTabs(listOf("Цель", "Отбор", "Доли", "Доход"), section, selectSection, Modifier.padding(horizontal = 20.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                state = listState, contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item { SpectrumCard {
                    SpectrumBadge("Черновик · не применяется")
                    Text("Шаг ${section + 1} из 4. Сохраняется на устройстве. Расчёт по этим правилам ещё не подключён.")
                    SpectrumTextButton("Действующие правила анализа",
                        onClick = { if (dirty) { openActiveAfterLeave = true; leaving = true } else onCurrentRules() },
                        symbol = SpectrumSymbol.Forward)
                } }
                when (section) {
                    0 -> {
                        item { SpectrumCard { WorkspaceChoices("Главная цель", listOf("Сохранение капитала", "Рост капитала", "Регулярные выплаты"), draft.goal) { draft = draft.copy(goal = it) } } }
                        item { SpectrumCard { WorkspaceChoices("Горизонт", listOf("До года", "1–3 года", "Более 3 лет"), draft.horizon) { draft = draft.copy(horizon = it) } } }
                        item { Text("Цель и срок определяют компромисс между колебаниями стоимости и доступностью денег. Доходность не гарантирована.", style = MaterialTheme.typography.bodyMedium) }
                    }
                    1 -> {
                        item { SpectrumCard { WorkspaceChoices("Рынок", listOf("Московская биржа", "Вне Московской биржи"), draft.market) { draft = draft.copy(market = it) }
                            Text("Доступность проверяется у брокера. Заблокированные активы не становятся доступными от выбора настройки.") } }
                        item { SpectrumCard { Text("Статус инвестора", style = MaterialTheme.typography.titleMedium)
                            Text("Не подтверждён брокером. Приложение не может изменить квалификацию.") } }
                        item { RatingDraftControl(draft.ratings) { draft = draft.copy(ratings = it) } }
                    }
                    2 -> {
                        item { DraftSlider("Денежный резерв", "Деньги для ближайших потребностей; меньше средств участвует в инвестициях.", percentages, StrategyPercentField.Reserve, draft.reserve) { percentages = it } }
                        item { DraftSlider("Предел на компанию", "Несколько выпусков одного эмитента суммируются после подключения расчёта.", percentages, StrategyPercentField.Company, draft.companyLimit) { percentages = it } }
                        item { DraftSlider("Предел на отрасль", "Снижает зависимость от одной части экономики.", percentages, StrategyPercentField.Sector, draft.sectorLimit) { percentages = it } }
                    }
                    else -> {
                        item { SpectrumCard { WorkspaceChoices("Поступления", listOf("Реинвестировать", "Пополнять резерв", "Сохранять для выплат"), draft.reinvest) { draft = draft.copy(reinvest = it) } } }
                        item { SpectrumCard { WorkspaceToggle("Валютная привязка", "Рассматривать рублёвые выплаты, зависящие от курса валюты", draft.currencyIncome) { draft = draft.copy(currencyIncome = it) }
                            Text("Валюта расчёта портфеля — отдельная настройка. Привязка выплат не устраняет валютный риск.") } }
                    }
                }
                item { DetailFold("Что изменено (${changes.size})") {
                    changes.ifEmpty { listOf("Изменений нет") }.forEach { Text(it) }
                } }
                item { StrategyImpact(null) }
                if (section < 3) item { SpectrumPrimaryButton("Далее", { selectSection(section + 1) }, Modifier.fillMaxWidth()) }
                if (candidate == null) item { Text("Исправьте проценты во вкладке «Доли» перед сохранением.", color = MaterialTheme.colorScheme.error) }
                if (draft.ratings.isEmpty()) item { Text("Выберите хотя бы один рейтинг.", color = MaterialTheme.colorScheme.error) }
                item { SpectrumPrimaryButton(if (saved && !dirty) "Черновик сохранён" else "Сохранить черновик", { save() },
                    Modifier.fillMaxWidth(), enabled = dirty && valid) }
            }
        }
    }
    val finish = if (openActiveAfterLeave) onCurrentRules else onBack
    if (leaving) DraftLeaveDialog(valid,
        onStay = { leaving = false; openActiveAfterLeave = false },
        onSave = { if (save()) { leaving = false; finish() } },
        onDiscard = { draft = baseline; percentages = StrategyPercentDraft(baseline); leaving = false; finish() })
}

internal fun strategyChanges(before: StrategyDraft, after: StrategyDraft): List<String> = listOfNotNull(
    if (before.goal != after.goal) "Цель" else null,
    if (before.horizon != after.horizon) "Горизонт" else null,
    if (before.market != after.market) "Рынок" else null,
    if (before.ratings != after.ratings) "Допустимые рейтинги" else null,
    if (before.reserve != after.reserve) "Резерв: ${before.reserve}% → ${after.reserve}%" else null,
    if (before.companyLimit != after.companyLimit) "Компания: ${before.companyLimit}% → ${after.companyLimit}%" else null,
    if (before.sectorLimit != after.sectorLimit) "Отрасль: ${before.sectorLimit}% → ${after.sectorLimit}%" else null,
    if (before.reinvest != after.reinvest) "Распределение поступлений" else null,
    if (before.currencyIncome != after.currencyIncome) "Валютная привязка" else null,
)

@Composable
private fun DraftSlider(title: String, description: String, draft: StrategyPercentDraft, field: StrategyPercentField,
    fallback: Int, onChange: (StrategyPercentDraft) -> Unit) {
    val range = field.range
    val parsed = draft.value(field)
    SpectrumCard {
        Text(title, style = MaterialTheme.typography.titleMedium)
        SpectrumTextField(draft.text(field), { next -> onChange(draft.edit(field, next)) },
            label = { Text("Проценты") }, trailingIcon = { Text("%") }, isError = parsed == null, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth())
        if (parsed == null) Text("От ${range.first} до ${range.last}%", color = MaterialTheme.colorScheme.error)
        Slider((parsed ?: fallback).toFloat(), { onChange(draft.edit(field, it.roundToInt().toString())) },
            valueRange = range.first.toFloat()..range.last.toFloat(), steps = range.last - range.first - 1)
        Text(description, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun DraftLeaveDialog(valid: Boolean, onStay: () -> Unit, onSave: () -> Unit, onDiscard: () -> Unit) {
    AlertDialog(onDismissRequest = onStay, title = { Text("Сохранить изменения?") },
        text = { Text("Несохранённые изменения черновика будут потеряны.") },
        confirmButton = { TextButton(enabled = valid, onClick = onSave) { Text("Сохранить и выйти") } },
        dismissButton = { TextButton(onClick = onDiscard) { Text("Не сохранять") } })
}

@Composable
private fun RatingDraftControl(ratings: Set<String>, onChange: (Set<String>) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val threshold = RatingChoices.indexOfLast { it in ratings }.coerceAtLeast(0)
    SpectrumCard {
        Text("Кредитные рейтинги", style = MaterialTheme.typography.titleLarge)
        SpectrumTextButton("Минимум: ${RatingChoices[threshold]}", onClick = { open = true }, symbol = SpectrumSymbol.Expand)
        DetailFold("Исключения (${RatingChoices.take(threshold + 1).count { it !in ratings }})") {
            RatingChoices.take(threshold + 1).forEach { rating -> WorkspaceToggle(rating, "Включать в отбор", rating in ratings) { enabled ->
                onChange(if (enabled) ratings + rating else ratings - rating)
            } }
        }
    }
    if (open) AlertDialog(onDismissRequest = { open = false }, title = { Text("Минимальный рейтинг") },
        text = { Column { RatingChoices.forEachIndexed { index, rating ->
            TextButton(onClick = { onChange(RatingChoices.take(index + 1).toSet()); open = false }) { Text(rating) }
        } } }, confirmButton = { TextButton(onClick = { open = false }) { Text("Закрыть") } })
}
