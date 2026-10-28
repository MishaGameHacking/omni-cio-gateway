package ru.omnicio.app.ui.home

import java.time.Duration
import java.time.Instant
import org.json.JSONObject

internal data class ReadinessLane(
    val id: String,
    val title: String,
    val state: String,
    val observedAt: String?,
    val current: Boolean,
)

internal data class SystemReadinessModel(
    val evaluatedAt: String,
    val valuationAt: String?,
    val readOnlyConfirmed: Boolean,
    val lanes: List<ReadinessLane>,
    val notices: List<String>,
    val sourceCount: Int?,
    val unresolvedSources: Int?,
    val liveCashReconciled: Boolean,
) {
    val currentCount: Int get() = lanes.count { it.current }
    val freshnessFraction: Float? get() = lanes.takeIf { it.isNotEmpty() }
        ?.let { currentCount.toFloat() / it.size }
}

/** A status read is not a new valuation, an accepted plan, or permission to trade. */
internal fun systemReadinessModel(value: JSONObject?): SystemReadinessModel? {
    if (value?.opt("schema_version") != 1) return null
    if (value.opt("state") !in setOf("restricted_read_only", "not_connected", "awaiting_snapshot")) return null
    val evaluatedText = value.cleanText("evaluated_at") ?: return null
    val evaluated = readinessInstant(evaluatedText) ?: return null
    val rows = value.optJSONArray("lanes")
    val ids = (0 until (rows?.length() ?: 0)).map { rows?.optJSONObject(it)?.cleanText("id") }
    val repeated = ids.filterNotNull().groupingBy { it }.eachCount().filterValues { it > 1 }.keys
    val lanes = (0 until (rows?.length() ?: 0)).map { index ->
        val row = rows?.optJSONObject(index)
        val id = row?.cleanText("id") ?: "missing-$index"
        val quality = row?.optJSONObject("freshness")
        val observedText = quality?.cleanText("as_of")
        val observed = readinessInstant(observedText)
        val maximum = quality?.opt("max_age_seconds") as? Int
        val validClock = observed != null && !observed.isAfter(evaluated) && maximum != null &&
            maximum in 1..31_536_000 && Duration.between(observed, evaluated) < Duration.ofSeconds(maximum.toLong())
        val current = id !in repeated && ids[index] != null && row?.opt("state") == "current" &&
            row.opt("coverage_complete") == true && quality?.opt("current") == true &&
            quality.opt("state") == "fresh" && validClock
        val rawState = row?.cleanText("state")
        ReadinessLane(id, row?.cleanText("title") ?: "Раздел данных",
            if (current) "current" else if (rawState == "current" || id in repeated) "unknown" else rawState ?: "unknown",
            observedText?.takeIf { observed != null && !observed.isAfter(evaluated) }, current)
    }
    val blockers = value.optJSONArray("blockers")
    val notices = (0 until (blockers?.length() ?: 0)).mapNotNull { index ->
        val row = blockers?.optJSONObject(index)
        if (row?.opt("kind") in setOf("data", "connection", "configuration")) row?.cleanText("message") else null
    }.distinct()
    val provenance = value.optJSONObject("provenance")
    val valuation = value.cleanText("valuation_as_of")?.takeIf {
        readinessInstant(it)?.let { clock -> !clock.isAfter(evaluated) } == true
    }
    return SystemReadinessModel(evaluatedText, valuation,
        value.opt("execution_mode") == "read_only" && value.opt("real_orders_enabled") == false,
        lanes, notices, provenance?.nonnegativeInt("source_count"),
        provenance?.nonnegativeInt("unresolved_reference_count"),
        value.optJSONObject("accounting")?.opt("live_cash_reconciled") == true)
}

internal fun readinessStateTitle(state: String): String = when (state) {
    "current" -> "Актуально"
    "stale" -> "Нужно обновить"
    "incomplete" -> "Неполные данные"
    "not_collected", "missing" -> "Пока нет данных"
    "future", "invalid" -> "Время требует проверки"
    else -> "Не подтверждено"
}

private fun JSONObject.cleanText(key: String): String? = (opt(key) as? String)
    ?.takeIf { it.isNotBlank() && it.length <= 500 && it.none(Char::isISOControl) }

private fun JSONObject.nonnegativeInt(key: String): Int? = (opt(key) as? Int)?.takeIf { it >= 0 }
private fun readinessInstant(value: String?): Instant? = value?.let { runCatching { Instant.parse(it) }.getOrNull() }
