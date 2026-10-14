package ru.omnicio.app

import java.time.Instant
import java.time.ZoneId
import ru.omnicio.app.ui.analysis.*

/** Pure display contract checks, not a live model call or screenshot inspection. */
internal fun runAnalysisPresentationChecks(): Int {
    var checks = 0
    fun verify(value: Boolean) { check(value); checks++ }
    queueChecks(::verify)
    sliderChecks(::verify)
    freshnessChecks(::verify)
    return checks
}

private fun queueChecks(verify: (Boolean) -> Unit) {
    for (state in listOf("queued", "coalesced", "running", "in_progress", "disabled", "unknown", "")) {
        val message = refreshDescription(state, null)
        verify(!message.contains("изменений не найдено"))
        verify(!message.contains("Анализ завершён"))
    }
    verify(refreshDescription("queued", "synthetic").contains("очередь"))
    verify(refreshDescription("completed", null).contains("не подтверждено"))
    verify(refreshDescription("completed", " ").contains("не подтверждено"))
    verify(refreshDescription("completed", "synthetic").contains("Модель: synthetic"))
    verify(refreshDescription("skipped", null).contains("не выполнялся"))
    verify(refreshDescription("fallback", null).contains("ограничения"))
    verify(ideasHeading("unknown").contains("не подтверждено"))
    verify(ideasHeading("profile_required").contains("профиль"))
}

private fun sliderChecks(verify: (Boolean) -> Unit) {
    for (range in listOf(5f..60f, 0f..50f, 10f..50f, 0f..30f, 0f..5f)) {
        val steps = profileSliderSteps(range)
        val interval = (range.endInclusive - range.start) / (steps + 1)
        verify(interval == 5f)
        for (index in 0..steps + 1) {
            val value = range.start + interval * index
            verify(selectedProfilePercent(value, range) == value.toDouble())
        }
    }
    verify(selectedProfilePercent(24.999998f, 5f..60f) == 25.0)
    verify(selectedProfilePercent(-100f, 5f..60f) == 5.0)
    verify(selectedProfilePercent(200f, 0f..50f) == 50.0)
    verify(analysisPercent(12.5) == "12,5%")
    verify(analysisPercent(Double.NaN) == "нет данных")
    verify(analysisPercent(Double.POSITIVE_INFINITY) == "нет данных")
    verify(profileLimitsValid(5.0, 0.0) && profileLimitsValid(60.0, 50.0))
    verify(profileLimitsValid(12.5, 7.5))
    for ((position, cash) in listOf(4.9 to 5.0, 60.1 to 5.0, 25.0 to -1.0,
        25.0 to 50.1, Double.NaN to 5.0, 25.0 to Double.POSITIVE_INFINITY)) {
        verify(!profileLimitsValid(position, cash))
    }
    for (range in listOf(0f..0f, 10f..5f, 0f..Float.POSITIVE_INFINITY, 0f..11f)) {
        verify(runCatching { profileSliderSteps(range) }.isFailure)
    }
    verify(runCatching { selectedProfilePercent(Float.NaN, 5f..60f) }.isFailure)
}

private fun freshnessChecks(verify: (Boolean) -> Unit) {
    val now = Instant.parse("2026-10-14T05:00:00Z")
    val created = "2026-10-14T04:00:00Z"
    verify(insightValidity(created, "2026-10-14T06:00:00Z", now).contains("не гарантия"))
    verify(insightValidity(created, now.toString(), now).contains("истёк"))
    verify(insightValidity(created, "2026-10-14T04:30:00Z", now).contains("истёк"))
    verify(insightValidity(created, created, now).contains("некорректен"))
    verify(insightValidity(created, null, now).contains("не указан"))
    verify(insightValidity(created, "invalid", now).contains("не указан"))
    verify(insightValidity("invalid", null, now).contains("не подтверждено"))
    verify(insightValidity("2026-10-14T07:00:00Z", "2026-10-14T08:00:00Z", now).contains("не подтверждено"))
    verify(analysisTime(created, ZoneId.of("Europe/Moscow"))?.contains("07:00") == true)
    verify(analysisTime("2026-10-14T04:00:00") == null)
}

fun main() { println("ANALYSIS_PRESENTATION_CHECKS=" + runAnalysisPresentationChecks()) }
