package ru.omnicio.app.ui.portfolio

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.portfolio.PortfolioDataClient

internal data class AccountData(val json: JSONObject?, val error: String?, val loading: Boolean)

@Composable
internal fun rememberAccountData(token: String, accountId: String, section: String,
                                 parameters: Map<String, String> = emptyMap(), interval: Long = 30_000): AccountData {
    val lifecycle = (LocalContext.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: true) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ -> active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: true }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    var json by remember(token, accountId, section, parameters) { mutableStateOf<JSONObject?>(null) }
    var error by remember(token, accountId, section, parameters) { mutableStateOf<String?>(null) }
    var loading by remember(token, accountId, section, parameters) { mutableStateOf(false) }
    val client = remember { PortfolioDataClient() }
    LaunchedEffect(token, accountId, section, parameters, active) {
        if (!active || token.isBlank()) return@LaunchedEffect
        var wait = interval
        while (isActive) {
            loading = true
            try {
                when (val result = withContext(Dispatchers.IO) { client.details(token, accountId, section, parameters) }) {
                    is BackendResult.Success -> { json = result.value; error = null; wait = interval }
                    is BackendResult.Failure -> {
                        error = result.message
                        if (!result.retryable) return@LaunchedEffect
                        wait = (wait * 2).coerceAtMost(120_000)
                    }
                }
            } finally { loading = false }
            delay(wait)
        }
    }
    return AccountData(json, error, loading)
}

@Composable
internal fun AccountDataNotice(data: AccountData) {
    when {
        data.error != null -> Notice(data.error)
        data.json == null -> Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            Text("Загружаем данные счёта…")
        }
        else -> Notice("Получено ${dateText(data.json.optString("asOf"))} · обновляется автоматически")
    }
}

internal data class PortfolioPeriod(val start: String?, val end: String?) {
    fun parameters(): Map<String, String> = buildMap {
        start?.let { put("start", it) }
        end?.let { put("end", it) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun PeriodControls(period: PortfolioPeriod, onChange: (PortfolioPeriod) -> Unit) {
    var selected by rememberSaveable { mutableIntStateOf(5) }
    var calendar by remember { mutableStateOf(false) }
    val today = LocalDate.now(Moscow)
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        ChoiceRow(listOf("День", "Месяц", "6 мес", "12 мес", today.year.toString(), "Всё время", "Период"), selected) { index ->
            if (index == 6) calendar = true else {
                selected = index
                val start = when (index) {
                    0 -> today
                    1 -> today.minusMonths(1)
                    2 -> today.minusMonths(6)
                    3 -> today.minusYears(1)
                    4 -> today.withDayOfYear(1)
                    else -> null
                }
                onChange(PortfolioPeriod(start?.toString(), null))
            }
        }
        if (selected == 6) Notice("${period.start} — ${period.end}")
    }
    if (calendar) {
        val todayMillis = today.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
        val picker = rememberDateRangePickerState(
            initialSelectedStartDateMillis = period.start?.let { LocalDate.parse(it).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli() },
            initialSelectedEndDateMillis = period.end?.let { LocalDate.parse(it).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli() },
            selectableDates = object : SelectableDates {
                override fun isSelectableDate(utcTimeMillis: Long): Boolean = utcTimeMillis <= todayMillis
                override fun isSelectableYear(year: Int): Boolean = year <= today.year
            },
        )
        DatePickerDialog(onDismissRequest = { calendar = false },
            confirmButton = {
                TextButton(enabled = picker.selectedStartDateMillis != null && picker.selectedEndDateMillis != null,
                    onClick = {
                        val first = picker.selectedStartDateMillis
                        val last = picker.selectedEndDateMillis
                        if (first != null && last != null) {
                            onChange(PortfolioPeriod(Instant.ofEpochMilli(first).atZone(ZoneOffset.UTC).toLocalDate().toString(),
                                Instant.ofEpochMilli(last).atZone(ZoneOffset.UTC).toLocalDate().toString()))
                            selected = 6; calendar = false
                        }
                    }) { Text("Применить") }
            }, dismissButton = { TextButton(onClick = { calendar = false }) { Text("Отмена") } }) {
            DateRangePicker(state = picker, modifier = Modifier.heightIn(max = 520.dp), title = { Text("Выбор периода", Modifier.padding(16.dp)) })
        }
    }
}
