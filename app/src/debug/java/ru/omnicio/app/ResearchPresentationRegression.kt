package ru.omnicio.app

import java.time.ZoneId
import ru.omnicio.app.data.research.*

/** Pure presentation tests; no broker data, network request or investment recommendation. */
internal fun runResearchPresentationChecks(): Int {
    var checks = 0
    fun verify(value: Boolean) { check(value); checks++ }
    checkLoadState(::verify)
    checkPaging(::verify)
    checkScenario(::verify)
    checkCoverage(::verify)
    return checks
}

private fun checkLoadState(verify: (Boolean) -> Unit) {
    val initial = ResearchLoadState<String>()
    verify(initial.data == null && !initial.loading)
    verify(initial.start().loading)
    val current = initial.success("fixture")
    val failed = current.failure("offline", retryable = true)
    verify(failed.data == "fixture" && failed.stale && !failed.loading)
    verify(failed.start().stale && failed.start().error == "offline")
    verify(failed.success("next") == ResearchLoadState(data = "next"))
    verify(current.failure("expired", retryable = false).data == null)
    verify(!initial.failure("offline", retryable = true).stale)
    verify(current.start().stopped() == current)
    verify(initial.data == null && current.error == null)
}

private fun checkPaging(verify: (Boolean) -> Unit) {
    for (total in listOf(0, 1, 3, 4, 9, 10, 11, 99, 100)) {
        val seen = mutableListOf<Int>()
        val pages = researchPage(total, 0, true).pageCount
        for (page in 0 until pages) {
            val window = researchPage(total, page, true)
            verify(window.endExclusive - window.first <= 10)
            seen.addAll(window.first until window.endExclusive)
        }
        verify(seen == (0 until total).toList())
        verify(researchPage(total, Int.MAX_VALUE, true).endExclusive == total)
        verify(researchPage(total, Int.MIN_VALUE, true).page == 0)
        verify(researchPage(total, 99, false).endExclusive <= 3)
    }
    for (bad in listOf(-1, 101, Int.MAX_VALUE)) verify(runCatching { researchPage(bad, 0, true) }.isFailure)
    verify(researchTime("2026-10-14T05:00:00Z", ZoneId.of("Europe/Moscow"))?.contains("08:00") == true)
    verify(researchTime("invalid") == null && researchTime(null) == null)
    verify(researchTime("2026-10-14T05:00:00") == null)
}

private fun checkScenario(verify: (Boolean) -> Unit) {
    val fields: Map<String, Any?> = mapOf(
        "method" to "joint_moving_block_buy_and_hold_v1", "is_default_probability" to false,
        "guarantee" to false, "paths" to 500, "horizon_sessions" to 20, "capital_floor" to 0.8,
        "conditional_breach_frequency" to 0.0, "monte_carlo_interval_only" to listOf(0.0, 0.008),
    )
    verify(researchScenario(fields)?.breaches == 0)
    verify(researchScenario(fields)?.summary?.contains("0 из 500") == true)
    verify(researchScenario(fields)?.interval?.contains("не учитывает") == true)
    for ((key, value) in listOf(
        "method" to "unknown", "is_default_probability" to true, "guarantee" to true,
        "paths" to 500.0, "paths" to "500", "paths" to -1, "paths" to 6000,
        "horizon_sessions" to true, "capital_floor" to Double.NaN, "capital_floor" to 1.0,
        "conditional_breach_frequency" to Double.POSITIVE_INFINITY,
        "conditional_breach_frequency" to "0.0", "conditional_breach_frequency" to -0.1,
        "conditional_breach_frequency" to 0.0001,
        "monte_carlo_interval_only" to listOf(0.0, 0.0),
        "monte_carlo_interval_only" to listOf(0.0, "0.01"),
        "monte_carlo_interval_only" to listOf(-0.1, 0.01),
        "monte_carlo_interval_only" to listOf(0.0, 0.01, 0.02),
    )) verify(researchScenario(fields + (key to value)) == null)
    val one = fields + mapOf("paths" to 5000L, "conditional_breach_frequency" to 0.0002,
        "monte_carlo_interval_only" to listOf(0.00003, 0.0011))
    verify(researchScenario(one)?.summary?.contains("1 из 5000") == true)
}

fun main() { println("RESEARCH_PRESENTATION_CHECKS=" + runResearchPresentationChecks()) }

private fun checkCoverage(verify: (Boolean) -> Unit) {
    val fields: Map<String, Any?> = mapOf("examined_positions" to 100, "total_positions" to 137,
        "issuer_coverage_count" to 60)
    val partial = researchCoverage(fields, 100)
    verify(partial?.allPositionsIncluded == false)
    verify(partial?.summary == "Разобрано 100 из 137 позиций портфеля.")
    verify(partial?.omittedWarning?.contains("37 позиций") == true)
    verify(partial?.issuerSummary?.contains("60 из 100") == true)
    verify(researchCoverage(fields + ("total_positions" to 100L), 100)?.omittedWarning == null)
    for ((key, value) in listOf("examined_positions" to 99, "examined_positions" to true,
        "total_positions" to 99, "total_positions" to "137", "total_positions" to Long.MAX_VALUE,
        "issuer_coverage_count" to 101, "issuer_coverage_count" to -1,
        "issuer_coverage_count" to null, "total_positions" to 137.0)) {
        verify(researchCoverage(fields + (key to value), 100) == null)
    }
    verify(researchCoverage(emptyMap(), 0) == null)
    verify(researchCoverage(fields, 101) == null)
    val empty = mapOf<String, Any?>("examined_positions" to 0, "total_positions" to 0,
        "issuer_coverage_count" to 0)
    verify(researchCoverage(empty, 0)?.summary == "Разобрано 0 из 0 позиций портфеля.")
}
