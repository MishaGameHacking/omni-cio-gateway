package ru.omnicio.app.ui.workspace

import org.json.JSONObject
import java.time.Duration
import java.time.Instant
import java.time.format.DateTimeParseException

/** Display-only observations. Freshness never grants trading permission. */
internal data class ServerLaneSummary(val title: String, val state: String, val observedAt: String?)
internal data class ServerReadinessSummary(
    val supported: Boolean,
    val evaluationCurrent: Boolean,
    val evaluatedAt: String?,
    val valuationAt: String?,
    val mode: String,
    val lanes: List<ServerLaneSummary>,
)

private val serverLaneTitles = linkedMapOf(
    "valuation" to "Стоимость портфеля",
    "events" to "Новости и события",
    "operations" to "Операции",
    "payouts" to "Выплаты",
    "calendar" to "Календарь",
)

private fun serverInstant(raw: Any?): Instant? {
    if (raw !is String || raw.length !in 1..64) return null
    return try { Instant.parse(raw) } catch (_: DateTimeParseException) { null }
}

private fun currentServerObservation(raw: Any?, now: Instant, seconds: Int): Boolean {
    val observed = serverInstant(raw) ?: return false
    val age = Duration.between(observed, now)
    return !age.isNegative && age < Duration.ofSeconds(seconds.toLong())
}

internal fun serverReadinessSummary(payload: JSONObject?, now: Instant = Instant.now()): ServerReadinessSummary {
    val supported = payload?.opt("schema_version") == 1
    val evaluated = payload?.opt("evaluated_at")
    val evaluationCurrent = supported && currentServerObservation(evaluated, now, 1200)
    val rawLanes = payload?.optJSONArray("lanes")
    val rows = if (rawLanes != null && rawLanes.length() <= 20) {
        (0 until rawLanes.length()).mapNotNull { rawLanes.optJSONObject(it) }
    } else emptyList()
    val lanes = serverLaneTitles.map { (id, title) ->
        val matches = rows.filter { it.opt("id") == id }
        val row = matches.singleOrNull()
        val freshness = row?.optJSONObject("freshness")
        val rawTime = freshness?.opt("as_of")
        val maxAge = when (id) {
            "payouts" -> 3600
            "events", "operations" -> 1200
            else -> 900
        }
        val state = when {
            !supported || row == null -> "Нет подтверждённых сведений"
            !evaluationCurrent -> "Статус сервера устарел или не подтверждён"
            row.opt("state") == "not_collected" -> "Данные ещё не собраны"
            serverInstant(rawTime) == null -> "Время данных не подтверждено"
            !currentServerObservation(rawTime, now, maxAge) -> "Данные устарели или дата некорректна"
            row.opt("state") == "current" && row.opt("coverage_complete") == true &&
                freshness?.opt("state") == "fresh" && freshness.opt("current") == true -> "Получены актуальные данные"
            else -> "Проверка данных не завершена"
        }
        ServerLaneSummary(title, state, serverInstant(rawTime)?.toString())
    }
    val readOnly = evaluationCurrent && payload?.opt("execution_mode") == "read_only" &&
        payload.opt("real_orders_enabled") == false
    return ServerReadinessSummary(
        supported = supported,
        evaluationCurrent = evaluationCurrent,
        evaluatedAt = serverInstant(evaluated)?.toString(),
        valuationAt = serverInstant(payload?.opt("valuation_as_of"))?.toString(),
        mode = if (readOnly) "Сбор и анализ · без торговых поручений" else "Режим работы не подтверждён",
        lanes = lanes,
    )
}
