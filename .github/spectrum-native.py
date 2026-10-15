"""Apply the reviewed native UI replacements to an exact, checked-out PR revision.

This one-use migration emits a candidate Git tree manifest; it does not push,
merge, publish an APK, read environment secrets, or edit authentication/data code.
The migration and payload are removed from the candidate commit.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path.cwd()
PAYLOAD = Path('.github/spectrum-payload')
changes: dict[str, str] = {}
deletions: list[str] = []
for source in sorted(PAYLOAD.rglob('*')):
    if not source.is_file():
        continue
    if source.is_symlink():
        raise RuntimeError('Payload symlink is not allowed')
    destination = source.relative_to(PAYLOAD).as_posix()
    if not destination.startswith('app/'):
        raise RuntimeError('Unexpected payload destination')
    changes[destination] = source.read_text(encoding='utf-8')
    deletions.append(source.as_posix())


def read(path: str) -> str:
    return changes[path] if path in changes else Path(path).read_text(encoding='utf-8')


def replace(path: str, old: str, new: str, expected: int = 1) -> None:
    content = read(path)
    actual = content.count(old)
    if actual != expected:
        raise RuntimeError(f'{path}: expected {expected} occurrences, got {actual}: {old[:90]!r}')
    changes[path] = content.replace(old, new)


def section(path: str, start: str, end: str, replacement: str) -> None:
    content = read(path)
    if content.count(start) != 1 or content.count(end) != 1:
        raise RuntimeError('Ambiguous section in ' + path)
    first, last = content.index(start), content.index(end)
    if last <= first:
        raise RuntimeError('Invalid section order')
    changes[path] = content[:first] + replacement.rstrip() + '\n\n' + content[last:]


APP = 'app/src/main/java/ru/omnicio/app/'
main = APP + 'MainActivity.kt'
replace(main, 'import androidx.activity.compose.setContent', 'import androidx.activity.compose.BackHandler\nimport ru.omnicio.app.ui.home.HomeScreen\nimport ru.omnicio.app.ui.home.MarketScreen\nimport ru.omnicio.app.ui.home.RisksScreen\nimport androidx.activity.compose.setContent')
replace(main, 'private enum class AppScreen {', 'private enum class AppScreen {\n    Home, Market, Risks,')
replace(main, 'mutableStateOf(AppScreen.Portfolio.name)', 'mutableStateOf(AppScreen.Home.name)')
replace(main, '.getOrDefault(AppScreen.Portfolio)', '.getOrDefault(AppScreen.Home)')
replace(main, 'screenName = AppScreen.Portfolio.name', 'screenName = AppScreen.Home.name')
replace(main, 'CompositionLocalProvider(LocalAnalystTabNavigator provides navigateToTab) {', '''BackHandler(screen != AppScreen.Home) { onScreenChange(AppScreen.Home) }
    CompositionLocalProvider(LocalAnalystTabNavigator provides navigateToTab) {''')
replace(main, 'when (screen) {', '''when (screen) {
            AppScreen.Home -> HomeScreen(
                state = portfolioState, accessToken = session.accessToken,
                selectedCurrency = portfolioCurrency,
                onCurrencyClick = { onCurrencyChange(portfolioCurrency.next()) },
                onProfileClick = openProfile,
                onAnalysisSettings = { onScreenChange(AppScreen.AnalysisSettings) },
                refreshing = portfolioRefreshing, refreshError = portfolioError,
                lastUpdatedMillis = portfolioLastSuccessMillis,
            )
            AppScreen.Market -> MarketScreen(portfolioState, openProfile)
            AppScreen.Risks -> RisksScreen(portfolioState, session.accessToken, openProfile,
                { onScreenChange(AppScreen.AnalysisSettings) })''')
replace(main, 'private fun AnalystTab.toAppScreen(): AppScreen = when (this) {', '''private fun AnalystTab.toAppScreen(): AppScreen = when (this) {
    AnalystTab.Home -> AppScreen.Home
    AnalystTab.Market -> AppScreen.Market
    AnalystTab.Education -> AppScreen.Education
    AnalystTab.Risks -> AppScreen.Risks''')
content = read(main)
first = content.index('AppScreen.Education -> EducationScreen(')
last = content.index('AppScreen.AnalysisSettings ->', first)
block = content[first:last]
if block.count('onBack = openProfile') != 1:
    raise RuntimeError('Education navigation changed')
changes[main] = content[:first] + block.replace('onBack = openProfile', 'onBack = { onScreenChange(AppScreen.Home) }') + content[last:]

portfolio = APP + 'ui/portfolio/PortfolioScreen.kt'
replace(portfolio, 'import ru.omnicio.app.ui.spectrum.SpectrumBackground', 'import ru.omnicio.app.ui.spectrum.*\nimport ru.omnicio.app.ui.LocalAnalystTabNavigator')
section(portfolio, '@Composable\nfun PortfolioScreen(', '@Composable\nprivate fun LivePositionDetails', '''@Composable
fun PortfolioScreen(
    state: PortfolioUiState, onProfileClick: () -> Unit,
    selectedCurrency: PortfolioCurrency = PortfolioCurrency.RUB,
    onCurrencyClick: () -> Unit = {}, modifier: Modifier = Modifier,
    accessToken: String = "", refreshing: Boolean = false,
    refreshError: String? = null, lastUpdatedMillis: Long? = null,
) {
    var accountId by rememberSaveable { mutableStateOf<String?>(null) }
    var accountSection by rememberSaveable { mutableIntStateOf(0) }
    var portfolioView by rememberSaveable { mutableIntStateOf(0) }
    var selectForSection by remember { mutableStateOf<Int?>(null) }
    var positionDetails by remember(accessToken) { mutableStateOf<PositionSelection?>(null) }
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val account = snapshot?.accounts?.firstOrNull { it.id == accountId }
    val listState = rememberLazyListState()
    val navigate = LocalAnalystTabNavigator.current
    BackHandler(accountId != null) { accountId = null; accountSection = 0 }
    LaunchedEffect(portfolioView) { listState.scrollToItem(0) }
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(Modifier.fillMaxSize(), containerColor = Color.Transparent,
            contentColor = MaterialTheme.colorScheme.onBackground,
            contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Portfolio, { accountId = null }, onProfileClick) },
        ) { insets ->
            if (account != null) {
                AccountScreen(account, accessToken, accountSection, { accountSection = it }, onCurrencyClick,
                    { accountId = null; accountSection = 0 }, snapshot.asOf, refreshError, Modifier.padding(insets))
            } else {
                LazyColumn(Modifier.fillMaxSize().padding(insets), state = listState,
                    contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    item(key = "header") { SpectrumHeader("Мой портфель", "Ваши активы и их структура", SpectrumSymbol.Portfolio) }
                    if (snapshot == null) item(key = "initial-state") { InitialPortfolioState(state, onProfileClick) }
                    else {
                        item(key = "total") {
                            PortfolioSummary(snapshot, selectedCurrency, refreshing, refreshError, lastUpdatedMillis, onCurrencyClick) { target ->
                                if (snapshot.accounts.size == 1) { accountId = snapshot.accounts.first().id; accountSection = target }
                                else selectForSection = target
                            }
                        }
                        item(key = "views") { ChoiceRow(listOf("Структура", "Активы", "Динамика"), portfolioView) { portfolioView = it } }
                        if (portfolioView == 0) item(key = "structure") {
                            SpectrumCard {
                                AssetStructure(snapshot.allocations, snapshot.totalValue)
                                SpectrumAction("Разобрать риски портфеля", { navigate(AnalystTab.Risks) })
                            }
                        }
                        if (portfolioView == 2 && snapshot.accounts.size == 1) item(key = "history") {
                            SpectrumCard { SpectrumSectionTitle("Динамика стоимости"); DashboardHistory(accessToken, snapshot) }
                        }
                        if (snapshot.accounts.isEmpty()) item(key = "no-accounts") {
                            SpectrumMessage("Счета пока не найдены", "Проверьте подключение брокерского счёта в профиле.", SpectrumSymbol.Portfolio)
                        }
                        items(snapshot.accounts, key = { "account:${it.id}" }) { item ->
                            if (portfolioView == 1) AccountPreviewCard(item,
                                onOpen = { accountId = item.id; accountSection = 0 },
                                onSection = { target -> accountId = item.id; accountSection = target },
                                onPosition = { positionDetails = PositionSelection(item.id, it.id) })
                            else SpectrumCard(onClick = { accountId = item.id; accountSection = if (portfolioView == 2) 3 else 0 }) {
                                SpectrumHeader(item.name, item.totalValue.moneyText(), SpectrumSymbol.Portfolio)
                                Text(if (portfolioView == 2) "Открыть аналитику счёта →" else "Открыть счёт →", color = LocalSpectrumPalette.current.cyan,
                                    style = MaterialTheme.typography.labelLarge)
                            }
                        }
                        if (snapshot.warnings.isNotEmpty()) item(key = "warnings") { Notice(snapshot.warnings.joinToString("\\n")) }
                    }
                }
            }
        }
    }
    LivePositionDetails(positionDetails, snapshot?.accounts) { positionDetails = null }
    if (selectForSection != null && snapshot != null) {
        AlertDialog(onDismissRequest = { selectForSection = null }, title = { Text("Выберите счёт") },
            containerColor = LocalSpectrumPalette.current.card,
            text = { Column(Modifier.verticalScroll(rememberScrollState())) { snapshot.accounts.forEach { item ->
                TextButton(onClick = { accountId = item.id; accountSection = selectForSection ?: 0; selectForSection = null }) { Text(item.name) }
            } } }, confirmButton = { TextButton(onClick = { selectForSection = null }) { Text("Отмена") } })
    }
}''')
section(portfolio, '@Composable\nprivate fun PortfolioShortcuts', '@Composable\nprivate fun ReturnSummaryRow', '''@Composable
private fun PortfolioShortcuts(onSection: (Int) -> Unit, enabled: Boolean = true) {
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        TextButton(onClick = { onSection(1) }, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp)) { Text("Операции →") }
        TextButton(onClick = { onSection(3) }, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp)) { Text("Аналитика →") }
    }
}''')
# The private summary is the final function in the original source.
content = read(portfolio)
marker = '@Composable\nprivate fun PortfolioSummary('
if content.count(marker) != 1:
    raise RuntimeError('Portfolio summary is ambiguous')
changes[portfolio] = content[:content.index(marker)] + '''@Composable
private fun PortfolioSummary(
    snapshot: PortfolioSnapshot, selectedCurrency: PortfolioCurrency, refreshing: Boolean,
    error: String?, lastUpdatedMillis: Long?, onCurrency: () -> Unit, openSection: (Int) -> Unit,
) {
    SpectrumCard(emphasized = true) {
        Notice("Общая стоимость")
        Text(snapshot.totalValue.moneyText(), Modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onCurrency),
            fontSize = 31.sp, lineHeight = 38.sp, fontWeight = FontWeight.Bold)
        snapshot.expectedYieldPercent?.let { ReturnSummaryRow("Доходность портфеля", snapshot.expectedYieldAmount, it) }
        val waiting = refreshing && snapshot.totalValue.currency != selectedCurrency.name
        Notice(if (waiting) "Получаем оценку в ${selectedCurrency.name}…" else "Нажмите на сумму: ₽ → $ → €")
        val observed = snapshot.asOf ?: lastUpdatedMillis?.let { java.time.Instant.ofEpochMilli(it).toString() }
        Notice(error ?: "Данные на ${dateText(observed)}")
        TextButton(onClick = { openSection(1) }, enabled = snapshot.accounts.isNotEmpty(), modifier = Modifier.heightIn(min = 48.dp)) {
            Text("История операций →")
        }
    }
}
'''
# Generic UI wording changes only; API property names are unchanged.
changes[portfolio] = read(portfolio).replace('Текущая доходность API', 'Доходность портфеля')

components = APP + 'ui/portfolio/PortfolioComponents.kt'
replace(components, 'import ru.omnicio.app.ui.spectrum.SpectrumCard', 'import ru.omnicio.app.ui.spectrum.SpectrumCard\nimport ru.omnicio.app.ui.spectrum.SpectrumTabs\nimport ru.omnicio.app.ui.spectrum.SpectrumAssetIcon')
section(components, '@Composable\ninternal fun ChoiceRow(', '@Composable\ninternal fun PositionLine', '''@Composable
internal fun ChoiceRow(options: List<String>, selected: Int, onSelect: (Int) -> Unit) {
    SpectrumTabs(options, selected, onSelect)
}''')
old_icon = '''                    Surface(shape = CircleShape, color = LocalSpectrumPalette.current.cardStrong, modifier = Modifier.size(38.dp)) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(position.ticker?.take(2) ?: "•", fontWeight = FontWeight.SemiBold, fontSize = 12.sp,
                                color = LocalSpectrumPalette.current.cyan)
                        }
                    }'''
replace(components, old_icon, '                    SpectrumAssetIcon(position.ticker, position.instrumentType, Modifier.size(46.dp))')
replace(components, 'val stroke = 11.dp.toPx()', 'val stroke = 24.dp.toPx()')
replace(components, 'minOf(maxWidth, 214.dp)', 'minOf(maxWidth, 224.dp)')
content = read(components)
marker = '@Composable\ninternal fun HistoryChart('
if content.count(marker) != 1:
    raise RuntimeError('History chart move is ambiguous')
changes[components] = content[:content.index(marker)].rstrip() + '\n'

cards = APP + 'ui/analysis/AnalysisCards.kt'
replace(cards, 'import ru.omnicio.app.ui.spectrum.SpectrumCard', 'import ru.omnicio.app.ui.spectrum.*\nimport ru.omnicio.app.ui.LocalAnalystTabNavigator')
replace(cards, 'Text(title, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)', '''val symbol = when (selected) {
                        AnalystTab.Ideas -> SpectrumSymbol.Ideas
                        AnalystTab.Pulse, AnalystTab.Chat -> SpectrumSymbol.Bell
                        else -> SpectrumSymbol.Risk
                    }
                    SpectrumHeader(title, symbol = symbol)''')
replace(cards, 'style = MaterialTheme.typography.bodyMedium)\n                }\n            },', 'style = MaterialTheme.typography.bodySmall)\n                }\n            },')
replace(cards, 'Button(onClick = onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text(buttonText) }', 'SpectrumAction(buttonText, onClick, enabled = enabled)')
section(cards, '@Composable\ninternal fun IdeaCard(', '@Composable\ninternal fun ActionCard', '''@Composable
internal fun IdeaCard(idea: AnalysisIdea) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = true) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            SpectrumIcon(SpectrumSymbol.Ideas, Modifier.size(54.dp), selected = true)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(idea.assetClass, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("Сейчас ${analysisPercent(idea.currentPercent)} · ориентир ${analysisPercent(idea.targetPercent)}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
        }
        SpectrumBadge("Идея для портфеля", accent = LocalSpectrumPalette.current.violet)
        Text(idea.explanation, style = MaterialTheme.typography.bodyMedium)
        Text("Допустимая доля: до ${analysisPercent(idea.suggestedMaxPercent)}", fontWeight = FontWeight.SemiBold)
        Text("Направление диверсификации, не торговое поручение.", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
    }
}''')

screens = APP + 'ui/analysis/AnalysisScreens.kt'
replace(screens, 'import ru.omnicio.app.ui.AnalystTab', 'import ru.omnicio.app.ui.AnalystTab\nimport ru.omnicio.app.ui.LocalAnalystTabNavigator\nimport ru.omnicio.app.ui.spectrum.*')
replace(screens, '"Сообщения", "Важные выводы Analyst AI без свободного чата"', '"Сообщения", "Выводы и уведомления Analyst AI"')
replace(screens, '"Пульс", "Изменения портфеля, утренние и вечерние проверки"', '"События", "Проверки портфеля и важные изменения"')
replace(screens, '"Что купить", "Направления диверсификации, а не торговые команды"', '"Рекомендации", "Идеи с учётом вашего портфеля и профиля"')
replace(screens, 'ActionCard("Обновить портфель и анализ"', 'ActionCard("Новые идеи для вас"')
replace(screens, 'Запрос передаётся серверу. Платная модель нужна не для каждого обновления: решение принимает серверный контроль изменений и бюджета.', 'Проверим портфель, профиль риска и доступные источники. Рекомендации появятся после завершения проверки.')
replace(screens, 'item(key = "portfolio-research") { PortfolioResearchPanel(token) }', '''item(key = "portfolio-research") {
                val navigate = LocalAnalystTabNavigator.current
                SpectrumCard(onClick = { navigate(AnalystTab.Risks) }) {
                    SpectrumHeader("Проверка вашего портфеля", "Сценарии риска и исследования инструментов →", SpectrumSymbol.Risk)
                }
            }''')

research = APP + 'ui/research/PortfolioResearchPanel.kt'
replace(research, 'import androidx.compose.material3.Card', 'import ru.omnicio.app.ui.spectrum.SpectrumCard')
replace(research, 'Card(Modifier.fillMaxWidth()) {', 'SpectrumCard(Modifier.fillMaxWidth()) {')
replace(research, 'Column(Modifier.padding(18.dp), verticalArrangement', 'Column(Modifier.fillMaxWidth(), verticalArrangement')

education = APP + 'ui/education/EducationScreen.kt'
replace(education, 'import ru.omnicio.app.ui.spectrum.SpectrumSymbol', 'import ru.omnicio.app.ui.spectrum.SpectrumSymbol\nimport ru.omnicio.app.ui.spectrum.SpectrumHeader')
replace(education, 'mutableStateOf<String?>("news-impact")', 'mutableStateOf<String?>(null)')
replace(education, 'AnalystBottomBar(AnalystTab.Profile,', 'AnalystBottomBar(AnalystTab.Education,')
replace(education, 'Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {', '''Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
                    SpectrumHeader("Обучение", symbol = SpectrumSymbol.Education, modifier = Modifier.padding(top = 12.dp))''')
section(education, '@Composable\nprivate fun LessonCard(', '@Composable\nprivate fun LessonBody', '''@Composable
private fun LessonCard(lesson: EducationLesson, expanded: Boolean, onExpand: () -> Unit) {
    val motion = LocalSpectrumMotionPreference.current
    val action = if (expanded) "Свернуть урок" else "Открыть урок"
    SpectrumCard(emphasized = expanded) {
        TextButton(onClick = onExpand, modifier = Modifier.fillMaxWidth()
            .testTag("lesson-toggle-${lesson.id}")
            .semantics { contentDescription = "$action: ${lesson.title}" },
            contentPadding = PaddingValues(0.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                SpectrumIcon(lesson.symbol, Modifier.size(52.dp), selected = expanded, motionAllowed = motion.enabled)
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(lesson.title, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface)
                    Text(lesson.subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                    Text("${lesson.minutes} мин · ${lesson.category.title}", color = LocalSpectrumPalette.current.cyan,
                        style = MaterialTheme.typography.labelMedium)
                }
                Text(if (expanded) "−" else "›", color = LocalSpectrumPalette.current.cyan)
            }
        }
        if (motion.enabled) AnimatedVisibility(visible = expanded) { LessonBody(lesson) }
        else if (expanded) LessonBody(lesson)
    }
}''')

profile = APP + 'ui/profile/ProfileScreen.kt'
replace(profile, 'import ru.omnicio.app.ui.spectrum.SpectrumSymbol', 'import ru.omnicio.app.ui.spectrum.SpectrumSymbol\nimport ru.omnicio.app.ui.spectrum.SpectrumCard\nimport ru.omnicio.app.ui.spectrum.SpectrumHeader\nimport ru.omnicio.app.ui.spectrum.SpectrumIconButton')
old_header = '''            Column(Modifier.padding(top = 16.dp, bottom = 8.dp)) {
                Text(user.name?.takeIf(String::isNotBlank) ?: "Analyst AI", fontWeight = FontWeight.SemiBold)
                Text("Профиль", fontSize = 32.sp, fontWeight = FontWeight.Bold)
            }'''
replace(profile, old_header, '''            Row(Modifier.fillMaxWidth().padding(top = 14.dp, bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                SpectrumHeader("Профиль", user.name?.takeIf(String::isNotBlank) ?: "Analyst AI", SpectrumSymbol.Profile, Modifier.weight(1f))
                SpectrumIconButton(SpectrumSymbol.Settings, "Открыть настройки", { section = 0 })
            }''')
replace(profile, 'ProfileAction("T‑API",', 'ProfileAction("Брокерский счёт",')
replace(profile, 'ProfileAction("Живые RGB-эффекты",', 'ProfileAction("Живые RGB-эффекты",', expected=0)
# ProfileToggle keeps a single full-card switch target, including at 200% font size.
replace(profile, '''    Card(modifier = Modifier.fillMaxWidth().toggleable(checked, role = Role.Switch, onValueChange = onChange),
        shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        BoxWithConstraints(Modifier.padding(20.dp)) {''', '''    SpectrumCard(modifier = Modifier.fillMaxWidth().toggleable(checked, role = Role.Switch, onValueChange = onChange)) {
        BoxWithConstraints(Modifier.fillMaxWidth()) {''')
section(profile, '@Composable\nprivate fun ProfileAction(', '@Composable\nprivate fun InformationDialog', '''@Composable
private fun ProfileAction(title: String, subtitle: String, symbol: String, spectrum: SpectrumSymbol? = null, onClick: () -> Unit) {
    val motion = LocalSpectrumMotionPreference.current
    val icon = spectrum ?: if (symbol == "↪") SpectrumSymbol.Update else SpectrumSymbol.Profile
    SpectrumCard(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(icon, Modifier.size(46.dp), motionAllowed = motion.enabled)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(title, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleMedium)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
            Text("›", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.titleLarge)
        }
    }
}''')

# Add the reusable, non-trademarked asset marks next to the new segment control.
controls = APP + 'ui/spectrum/SpectrumControls.kt'
changes[controls] = read(controls) + '''
/** A native asset-class mark, not an invented company logo. */
@Composable
fun SpectrumAssetIcon(ticker: String?, instrumentType: String, modifier: Modifier = Modifier) {
    val palette = LocalSpectrumPalette.current
    val accent = when (instrumentType) {
        "cash", "currency" -> palette.cyan
        "bond" -> palette.emerald
        "etf", "fund" -> palette.violet
        else -> palette.blue
    }
    Box(modifier.clip(RoundedCornerShape(12.dp))
        .background(Brush.linearGradient(listOf(accent.copy(alpha = .24f), palette.cardStrong)))
        .border(1.dp, accent.copy(alpha = .46f), RoundedCornerShape(12.dp)),
        contentAlignment = androidx.compose.ui.Alignment.Center) {
        Text(ticker?.take(3)?.uppercase(java.util.Locale.ROOT) ?: "•", color = accent,
            style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
    }
}
'''
art = APP + 'ui/spectrum/SpectrumArtwork.kt'
replace(art, 'val scale = size.minDimension / 256f', 'val factor = size.minDimension / 256f')
replace(art, 'scale(scale, scale, Offset.Zero)', 'scale(factor, factor, Offset.Zero)')
brand = APP + 'ui/spectrum/SpectrumDesignSystem.kt'
replace(brand, 'fun SpectrumBrand(modifier: Modifier = Modifier, compact: Boolean = false) {', 'fun SpectrumBrand(modifier: Modifier = Modifier, compact: Boolean = false) {\n    val accent = LocalSpectrumPalette.current.cyan')
replace(brand, 'SpanStyle(color = LocalSpectrumPalette.current.cyan)', 'SpanStyle(color = accent)')
risks = APP + 'ui/home/MarketAndRiskScreens.kt'
replace(risks, 'Без вымышленного рейтинга', 'Оценка пока недоступна')
replace(risks, 'В загруженных данных только денежные позиции. Число на шкале риска не подставляется: сводной серверной оценки нет.', 'На счёте пока только деньги. Для проверки отдельных инструментов нет позиций. Сводная оценка риска не рассчитана.')
replace(risks, 'Сводный балл не подставляется из макета. Доступные сценарии, ограничения и источники показаны в проверке ниже.', 'Единой оценки риска пока нет. Ниже — доступные сценарии, источники и ограничения проверки.')

build = 'app/build.gradle.kts'
replace(build, 'versionCode = 23', 'versionCode = 24')
replace(build, 'versionName = "0.6.0"', 'versionName = "0.7.0"')

probe = '.github/scripts/profile_ui_probe.py'
replace(probe, '''        self.open()
        self.palette("fff5f6f8")
        self.capture("light-initial")''', '''        self.open()
        self.palette("ff030c17")
        self.capture("dark-initial")
        self.tap(THEME_LABEL)
        self.tap("Светлая")
        self.palette("fff3f7ff")
        self.capture("light-initial")''')
changes[probe] = read(probe).replace('fff5f6f8', 'fff3f7ff').replace('ff111111', 'ff030c17')
ci = '.github/workflows/android-ci.yml'
replace(ci, "'education-large-font'", "'education-large-font', 'dark-initial'")

changes['docs/analyst-native-design-0.7.md'] = '''# Analyst AI 0.7 — native reference implementation

The 15 October owner reference replaces the old brokerage-style app shell.

## Application structure
- Primary destinations: Главная, Портфель, Рынок, Обучение, Профиль.
- Рекомендации, Риски, События and Сообщения are secondary screens, not extra bottom tabs.
- The dashboard is separate from the portfolio. Portfolio views are Структура, Активы and Динамика.
- Broker operations, account analytics, instrument details, education links, encrypted session recovery and the update gate retain their existing data paths.

## Visual system
Original native vector brain, robot, globe and filled neon glyphs; midnight blue glass surfaces; cyan edges; violet-blue action buttons; consistent typography, 20dp screen margins and compact 20dp cards. Light and system modes remain supported. Existing explicit preferences are preserved; a new installation starts in the reference midnight theme.

Every custom card and root now supplies an explicit on-colour. Normal text is checked against a 4.5:1 contrast target. Actions have at least 48dp targets; primary actions are at least 52dp. Selection animation is finite, respects the saved preference, system animation enablement and lifecycle. No animated GIF collection or continuous shader loop is introduced.

## Data integrity
The reference's balances, gains, suggested stock returns and 28/100 score are not product data. The release does not fabricate them. The chart uses validated, saved observations and retains an accessible value table; zeroes do not replace missing observations. Read-only access and broker source attribution remain intact. The market list is explicitly limited to the connected portfolio and is not falsely presented as a full exchange catalogue.

## Acceptance
Android lint and all APK variants must pass; signed upgrade compatibility and Android 13/16 installation must pass. Theme persistence, 200% fonts, educational navigation and existing mathematical/authentication/update tests remain required. A passing build alone is not a claim that every physical handset has been tested.

Primary references: https://developer.android.com/guide/topics/ui/accessibility/apps and https://developer.android.com/reference/kotlin/androidx/compose/material3/package-summary#LocalContentColor()
'''
changes['AGENTS.md'] = read('AGENTS.md').rstrip() + '''

## Owner-approved native navigation, 15 October 2026
This section supersedes earlier five-tab navigation wording above. The approved Analyst AI reference is implemented as a separate Home dashboard and five primary tabs: Главная / Портфель / Рынок / Обучение / Профиль. Рекомендации, Риски, События and Сообщения are secondary destinations. Do not restore Что купить / Пульс / Чат as the primary shell. Use the native Spectrum artwork, shared colour roles, buttons and headers; custom backgrounds must always provide an explicit readable content colour. Do not restore the giant brokerage-style pill-button account list as the home page. Preserve real data, package identity, signing, authentication and all release gates. See docs/analyst-native-design-0.7.md.
'''

deletions += ['.github/spectrum-native.py', '.github/workflows/spectrum-design-review.yml']
manifest = {'files': [{'path': path, 'content': value} for path, value in sorted(changes.items())], 'deletions': deletions}
Path('spectrum-generated.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
print('SPECTRUM_SOURCE_FILES=' + str(len(changes)))
for path in sorted(changes):
    print('SPECTRUM_CHANGED=' + path)
