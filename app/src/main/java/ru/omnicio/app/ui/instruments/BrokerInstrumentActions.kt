package ru.omnicio.app.ui.instruments

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog
import ru.omnicio.app.ui.spectrum.SpectrumActionButton as Button
import androidx.compose.material3.Text
import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext

/** Navigation only. Neither link nor clipboard creates a broker order. */
@Composable
fun BrokerInstrumentActions(assetClass: String, ticker: String?, isin: String?, compact: Boolean = false, copyOnly: Boolean = false) {
    val context = LocalContext.current
    var fallback by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    val section = mapOf("share" to "stocks", "bond" to "bonds", "etf" to "etfs")[assetClass]
    val validTicker = ticker?.takeIf { Regex("[A-Za-z0-9][A-Za-z0-9_.-]{0,39}").matches(it) && !it.contains("..") }
    val uri = if (section != null && validTicker != null) Uri.parse("https://www.tbank.ru/invest/$section/$validTicker/") else null
    Column {
        if (uri != null && !copyOnly) {
            Button(modifier = Modifier.fillMaxWidth(), onClick = {
                try {
                    context.startActivity(Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE)
                        .addFlags(Intent.FLAG_ACTIVITY_REQUIRE_NON_BROWSER))
                } catch (_: ActivityNotFoundException) { fallback = true }
                catch (_: SecurityException) { fallback = true }
            }) { Text("Открыть в Т‑Инвестициях") }
        }
        val searchText = listOfNotNull(validTicker, isin?.takeIf { Regex("[A-Z]{2}[A-Z0-9]{10}").matches(it) }).joinToString(" · ")
        if (searchText.isNotBlank() && !compact) {
            TextButton(onClick = {
                context.getSystemService(Context.CLIPBOARD_SERVICE).let { it as ClipboardManager }
                    .setPrimaryClip(ClipData.newPlainText("Инструмент", searchText))
                message = "Тикер и ISIN скопированы для поиска у брокера."
            }) { Text("Скопировать тикер и ISIN") }
        }
        message?.let { Text(it) }
    }
    if (fallback && uri != null) {
        AlertDialog(onDismissRequest = { fallback = false }, title = { Text("Открыть карточку инструмента") },
            text = { Text("Android не нашёл приложение, которое открывает эту ссылку. Можно открыть официальную страницу Т‑Инвестиций или найти инструмент по тикеру. Сделка не создаётся.") },
            confirmButton = { TextButton(onClick = {
                fallback = false
                try { context.startActivity(Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE)) }
                catch (_: ActivityNotFoundException) { message = "Браузер недоступен. Используйте тикер для поиска." }
                catch (_: SecurityException) { message = "Android запретил открытие ссылки. Используйте тикер для поиска." }
            }) { Text("Открыть страницу") } },
            dismissButton = { TextButton(onClick = { fallback = false }) { Text("Отмена") } })
    }
}
