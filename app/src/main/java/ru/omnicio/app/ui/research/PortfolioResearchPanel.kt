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
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
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
import ru.omnicio.app.data.research.InstrumentPage
import ru.omnicio.app.data.research.ResearchClient

/** The containing Ideas list owns scrolling. This panel never creates a nested list. */
@Composable
fun PortfolioResearchPanel(accessToken: String) {
    val client = remember { ResearchClient() }
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false) }
    var data by remember(accessToken) { mutableStateOf<JSONObject?>(null) }
    var error by remember(accessToken) { mutableStateOf<String?>(null) }
    var expanded by remember(accessToken) { mutableStateOf(false) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ ->
            active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false
        }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    LaunchedEffect(accessToken, active) {
        if (!active || accessToken.isBlank()) return@LaunchedEffect
        while (isActive) {
            when (val result = withContext(Dispatchers.IO) { client.read(accessToken) }) {
                is BackendResult.Success -> { data = result.value; error = null }
                is BackendResult.Failure -> {
                    error = result.message
                    if (!result.retryable) return@LaunchedEffect
                }
            }
            delay(60_000)
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Проверка ваших бумаг", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text("Решения на основе данных, без автоматических сделок. Риск потерь исключить нельзя.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        val snapshot = data
        if (snapshot == null) {
            if (error == null) Text("Проверяем данные брокера…")
        } else {
            Text("Проверка: ${snapshot.text("as_of") ?: "время не получено"}", style = MaterialTheme.typography.bodySmall)
            snapshot.optJSONObject("risk")?.text("explanation")?.let { Text(it) }
            snapshot.optJSONArray("source_errors").strings().forEach { Text(it, color = MaterialTheme.colorScheme.error) }
            val cards = snapshot.optJSONArray("cards") ?: JSONArray()
            if (cards.length() == 0) Text(snapshot.text("message") ?: "Бумаги для проверки не найдены.")
            for (i in 0 until minOf(cards.length(), if (expanded) 100 else 3)) {
                cards.optJSONObject(i)?.let { ResearchCard(it) }
            }
            if (cards.length() > 3) TextButton(onClick = { expanded = !expanded }) {
                Text(if (expanded) "Свернуть" else "Все проверенные позиции (${cards.length()})")
            }
            Text("Новые покупки не предлагаются, пока не проверены кандидаты, доступность, отчётность и риск. Отсутствие рейтинга не означает отсутствие риска.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun ResearchCard(card: JSONObject) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(card.text("name") ?: "Инструмент", style = MaterialTheme.typography.titleMedium)
            Text(listOfNotNull(card.text("ticker"), card.text("isin"), card.text("class_code")).joinToString(" · "), style = MaterialTheme.typography.bodySmall)
            Text(card.text("explanation") ?: "Данных недостаточно.")
            val credit = card.optJSONObject("credit")
            val ratings = credit?.optJSONArray("ratings") ?: JSONArray()
            for (i in 0 until ratings.length()) {
                val rating = ratings.getJSONObject(i)
                val subject = if (rating.text("subject_kind") == "issue") "выпуск" else "компания"
                Text("${rating.text("agency")}: ${rating.text("grade")} · $subject", fontWeight = FontWeight.SemiBold)
                val source = rating.optJSONObject("source")
                Text("Опубликовано ${source?.text("published_at") ?: "неизвестно"}", style = MaterialTheme.typography.bodySmall)
            }
            credit?.optJSONArray("warnings").strings().take(2).forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            val statement = card.optJSONObject("statement")
            statement?.optJSONArray("messages").strings().forEach { Text(it) }
            card.optJSONObject("broker_fundamentals")?.optJSONArray("messages").strings().forEach { Text(it) }
            val news = card.optJSONArray("news") ?: JSONArray()
            for (i in 0 until minOf(news.length(), 3)) {
                val item = news.getJSONObject(i)
                Text(item.text("title") ?: "Новость", fontWeight = FontWeight.SemiBold)
                Text("${item.text("source") ?: "Брокер"} · ${item.text("published_at") ?: ""}", style = MaterialTheme.typography.bodySmall)
            }
            if (news.length() > 0) Text("Заголовок — повод проверить событие, а не команда торговать.", style = MaterialTheme.typography.bodySmall)
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
    }) { Text("Открыть в Т‑Инвестициях") }
    TextButton(onClick = {
        context.getSystemService(ClipboardManager::class.java)
            .setPrimaryClip(ClipData.newPlainText("Инструмент", searchHint))
        message = "Название и идентификаторы скопированы."
    }) { Text("Скопировать для поиска") }
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

private fun JSONObject.text(key: String): String? = if (!has(key) || isNull(key)) null else optString(key).takeIf { it.isNotBlank() }
private fun JSONArray?.strings(): List<String> = if (this == null) emptyList() else (0 until length()).mapNotNull { optString(it).takeIf(String::isNotBlank) }
