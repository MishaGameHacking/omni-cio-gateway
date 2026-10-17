package ru.omnicio.app.ui.research

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.research.*

/** Parent Ideas list owns scrolling; pages bound the number of eagerly composed cards. */
@Composable
fun PortfolioResearchPanel(accessToken: String, instrumentId: String? = null, showRefresh: Boolean = true, refreshKey: Int = 0) {
    val client = remember { ResearchClient() }
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false) }
    var state by remember(accessToken) { mutableStateOf(ResearchLoadState<JSONObject>()) }
    var retry by remember(accessToken) { mutableIntStateOf(0) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ ->
            active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false
        }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    LaunchedEffect(accessToken, active, retry, refreshKey) {
        if (!active || accessToken.isBlank()) return@LaunchedEffect
        try {
            while (isActive) {
                state = state.start()
                when (val result = withContext(Dispatchers.IO) { client.read(accessToken) }) {
                    is BackendResult.Success -> {
                        if (!validSnapshot(result.value)) {
                            state = state.failure("Ответ проверки имеет неверный формат. Повторите запрос позже.", false)
                            return@LaunchedEffect
                        }
                        state = state.success(result.value)
                    }
                    is BackendResult.Failure -> {
                        state = state.failure(result.message, result.retryable)
                        if (!result.retryable) return@LaunchedEffect
                    }
                }
                delay(60_000)
            }
        } finally { state = state.stopped() }
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Проверка ваших бумаг", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Решения на основе данных, без автоматических сделок. Риск потерь исключить нельзя.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
        if (state.stale) Text("Показан предыдущий результат. Новая проверка не выполнена; выводы могли устареть.", fontWeight = FontWeight.SemiBold)
        if (state.loading && state.data == null) ru.omnicio.app.ui.spectrum.SpectrumLoadingIndicator(description = "Получаем исследование")
        if (showRefresh) TextButton(onClick = { retry++ }, enabled = active && !state.loading && accessToken.isNotBlank(),
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
            Text(if (state.loading) "Проверяем данные…" else "Повторить проверку бумаг")
        }
        if (ru.omnicio.app.ui.workspace.LocalWorkspacePreferences.current.value.hideHomeBalance) {
            Text("Подробности скрыты режимом приватности.")
        } else state.data?.let { payload ->
            ru.omnicio.app.ui.workspace.SaveResearchButton(payload,
                defaultTitle = if (instrumentId == null) "Проверка портфеля" else "Исследование бумаги",
                instrumentId = instrumentId, observedAt = payload.text("as_of"))
            if (instrumentId == null) ResearchSnapshot(payload, accessToken)
            else {
                val cards = payload.optJSONArray("cards") ?: JSONArray()
                val match = (0 until cards.length()).mapNotNull { cards.optJSONObject(it) }
                    .firstOrNull { it.text("instrument_uid") == instrumentId }
                if (match == null) Text("По этой бумаге проверенные сведения пока не получены.") else ResearchCard(match)
            }
        }
    }
}

private fun validSnapshot(snapshot: JSONObject): Boolean {
    val cards = snapshot.optJSONArray("cards") ?: return false
    if (cards.length() > 100) return false
    val ids = mutableSetOf<String>()
    for (i in 0 until cards.length()) {
        val card = cards.optJSONObject(i) ?: return false
        val uid = card.text("instrument_uid") ?: return false
        if (!ids.add(uid)) return false
    }
    return snapshot.text("state") != "research" || snapshot.coverage(cards.length()) != null
}

private fun JSONObject.coverage(cards: Int) = researchCoverage(mapOf(
    "examined_positions" to opt("examined_positions"),
    "total_positions" to opt("total_positions"),
    "issuer_coverage_count" to opt("issuer_coverage_count"),
), cards)

@Composable
internal fun ResearchSnapshot(snapshot: JSONObject, accessToken: String) {
    var expanded by remember(accessToken) { mutableStateOf(false) }
    var page by remember(accessToken) { mutableIntStateOf(0) }
    if (snapshot.text("state") == "research") Text("Последняя успешная проверка: ${researchTime(snapshot.text("as_of")) ?: "время не получено"}", style = MaterialTheme.typography.bodySmall)
    val coverage = snapshot.coverage(snapshot.optJSONArray("cards")?.length() ?: 0)
    coverage?.let {
        Text(it.summary, fontWeight = FontWeight.SemiBold)
        Text(it.issuerSummary, style = MaterialTheme.typography.bodySmall)
        it.omittedWarning?.let { warning -> Text(warning, color = MaterialTheme.colorScheme.error) }
    }
    snapshot.optJSONObject("risk")?.let {
        if (it.text("state") != "sample_estimate" || coverage?.allPositionsIncluded == true) ResearchRisk(it)
        else Text("Числовая оценка не показана: результат не охватывает все позиции.")
    }
    snapshot.optJSONArray("source_errors").strings().forEach { Text(it, color = MaterialTheme.colorScheme.error) }
    val cards = snapshot.optJSONArray("cards") ?: JSONArray()
    val window = researchPage(cards.length(), page, expanded)
    if (cards.length() == 0) Text(snapshot.text("message") ?: "Бумаги для проверки не найдены.")
    for (i in window.first until window.endExclusive) {
        cards.optJSONObject(i)?.let { card ->
            key(card.text("instrument_uid")) { ResearchCard(card) }
        }
    }
    if (expanded && cards.length() > 0) {
        Text("Разобранные позиции ${window.first + 1}–${window.endExclusive} из ${cards.length()}", style = MaterialTheme.typography.bodySmall)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { page = window.page - 1 }, enabled = window.hasPrevious,
                modifier = Modifier.weight(1f).heightIn(min = 48.dp)) { Text("Предыдущие") }
            TextButton(onClick = { page = window.page + 1 }, enabled = window.hasNext,
                modifier = Modifier.weight(1f).heightIn(min = 48.dp)) { Text("Следующие") }
        }
    }
    if (cards.length() > 3) TextButton(onClick = { expanded = !expanded; page = 0 },
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
        Text(if (expanded) "Свернуть" else "Просмотреть разобранные позиции (${cards.length()})")
    }
    Text("Новые покупки не предлагаются, пока не проверены кандидаты, доступность, отчётность и риск. Отсутствие рейтинга не означает отсутствие риска.", style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun ResearchRisk(risk: JSONObject) {
    risk.text("explanation")?.let { Text(it) }
    if (risk.text("state") != "sample_estimate") return
    val raw = risk.optJSONObject("scenarios") ?: return
    val fields = raw.keys().asSequence().associateWith { raw.opt(it) }.toMutableMap()
    raw.optJSONArray("monte_carlo_interval_only")?.let { bounds ->
        fields["monte_carlo_interval_only"] = (0 until bounds.length()).map { bounds.opt(it) }
    }
    val scenario = researchScenario(fields)
    if (scenario == null) {
        Text("Числовая оценка сценариев не прошла проверку формата.", color = MaterialTheme.colorScheme.error)
        return
    }
    Text("Сценарии по прошлым данным", fontWeight = FontWeight.SemiBold)
    Text(scenario.summary)
    Text(scenario.interval, style = MaterialTheme.typography.bodySmall)
    Text("Это не вероятность банкротства и не согласованный вами предел потерь. Порог выбран для сценарной проверки; отсутствие событий в выборке не означает безопасность.", style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun ResearchCard(card: JSONObject) {
    ru.omnicio.app.ui.spectrum.SpectrumCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(card.text("name") ?: "Инструмент", style = MaterialTheme.typography.titleMedium)
            Text(listOfNotNull(card.text("ticker"), card.text("isin"), card.text("class_code")).joinToString(" · "), style = MaterialTheme.typography.bodySmall)
            Text(card.text("explanation") ?: "Данных недостаточно.")
            ru.omnicio.app.ui.workspace.DetailFold("Рейтинг, отчётность и события") {
            val credit = card.optJSONObject("credit")
            val ratings = credit?.optJSONArray("ratings") ?: JSONArray()
            for (i in 0 until ratings.length()) {
                val rating = ratings.optJSONObject(i) ?: continue
                val subject = if (rating.text("subject_kind") == "issue") "выпуск" else "компания"
                Text("${rating.text("agency")}: ${rating.text("grade")} · $subject", fontWeight = FontWeight.SemiBold)
                val source = rating.optJSONObject("source")
                Text("Опубликовано ${researchTime(source?.text("published_at")) ?: "неизвестно"}", style = MaterialTheme.typography.bodySmall)
            }
            credit?.optJSONArray("warnings").strings().forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            card.optJSONObject("statement")?.optJSONArray("messages").strings().forEach { Text(it) }
            card.optJSONObject("broker_fundamentals")?.optJSONArray("messages").strings().forEach { Text(it) }
            val news = card.optJSONArray("news") ?: JSONArray()
            for (i in 0 until minOf(news.length(), 3)) {
                val item = news.optJSONObject(i) ?: continue
                Text(item.text("title") ?: "Новость", fontWeight = FontWeight.SemiBold)
                Text("${item.text("source") ?: "Брокер"} · ${researchTime(item.text("published_at")) ?: "время неизвестно"}", style = MaterialTheme.typography.bodySmall)
            }
            if (news.length() > 0) Text("Заголовок — повод проверить событие, а не команда торговать.", style = MaterialTheme.typography.bodySmall)
            }
            InstrumentActions(card.text("instrument_url"), card.text("search_hint") ?: card.text("name") ?: "")
        }
    }
}

@Composable
private fun InstrumentActions(rawUrl: String?, searchHint: String) {
    val context = LocalContext.current
    val url = InstrumentPage.accepted(rawUrl)
    var fallback by remember(rawUrl) { mutableStateOf(false) }
    var message by remember(rawUrl) { mutableStateOf<String?>(null) }
    if (url != null) TextButton(onClick = {
        fallback = !launchPage(context, url, appOnly = true)
    }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Открыть в Т‑Инвестициях") }
    TextButton(onClick = {
        message = if (runCatching {
            context.getSystemService(ClipboardManager::class.java)
                .setPrimaryClip(ClipData.newPlainText("Инструмент", searchHint))
        }.isSuccess) "Название и идентификаторы скопированы." else "Не удалось скопировать. Используйте тикер или ISIN из карточки."
    }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Скопировать для поиска") }
    message?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
    if (fallback && url != null) AlertDialog(
        onDismissRequest = { fallback = false },
        title = { Text("Приложение не открыло карточку") },
        text = { Text("Т‑Инвестиции не установлены или эта версия не принимает ссылку. Откройте официальную страницу либо найдите бумагу по тикеру или ISIN. Сделка не отправлялась.") },
        confirmButton = { TextButton(onClick = {
            fallback = false
            if (!launchPage(context, url, appOnly = false)) message = "Не найдено приложение для ссылки. Используйте поиск по скопированным данным."
        }) { Text("Официальная страница") } },
        dismissButton = { TextButton(onClick = { fallback = false }) { Text("Закрыть") } },
    )
}

private fun launchPage(context: Context, url: String, appOnly: Boolean): Boolean {
    if (InstrumentPage.accepted(url) == null) return false
    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
        addCategory(Intent.CATEGORY_BROWSABLE)
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        if (appOnly) setPackage(InstrumentPage.BROKER_PACKAGE)
    }
    return try {
        context.startActivity(intent)
        true
    } catch (_: ActivityNotFoundException) {
        false
    } catch (_: SecurityException) {
        false
    }
}

private fun JSONObject.text(key: String): String? = (opt(key) as? String)?.takeIf { it.isNotBlank() }
private fun JSONArray?.strings(): List<String> = if (this == null) emptyList() else (0 until length()).mapNotNull { (opt(it) as? String)?.takeIf(String::isNotBlank) }

