package ru.omnicio.app

import org.json.JSONArray
import org.json.JSONObject

/** Synthetic, debug-only observations for the production analysis timeline. */
internal fun timelineProbeAi(scenario: String): JSONObject {
    val empty = scenario == "empty"
    val partial = scenario == "partial"
    val morning = timelineProbeCheck(scenario, TIMELINE_CHECK)
    val evening = timelineProbeCheck(scenario, TIMELINE_EVENING_CHECK)
    return timelineObject(
        "last_run" to if (empty || partial) null else timelineObject(
            "id" to "synthetic-analysis-run", "created_at" to TIMELINE_AS_OF, "state" to "completed",
            "reason" to "morning_brief", "tier" to "standard", "card_id" to TIMELINE_REPORT),
        "last_check" to if (empty) null else morning,
        "slot_checks" to if (empty) JSONArray() else timelineArray(morning, evening),
        "check_history" to if (empty) JSONArray() else timelineArray(
            timelineObject("check_id" to TIMELINE_CHECK, "checked_at" to TIMELINE_AS_OF,
                "state" to if (partial) "skipped" else "ready", "reason" to if (partial) "cooldown" else "portfolio_changed",
                "observation_count" to 1)),
        "next_runs" to if (empty) JSONArray() else timelineArray(
            timelineObject("slot" to "morning", "at" to "2026-10-18T06:00:00Z", "gate" to if (partial) "awaiting_calendar" else "scheduled"),
            timelineObject("slot" to "evening", "at" to "2026-10-18T16:00:00Z", "gate" to "market_closed")),
        "monitor_jobs" to JSONArray(), "jobs" to JSONArray(),
        "analysis_diff" to if (empty || partial) null else timelineComparison(),
        "budget" to if (empty) null else timelineObject("estimated_and_reserved_rub" to "0.01",
            "day" to "2026-10-17", "timezone" to "Europe/Moscow", "unresolved_attempts" to if (partial) 1 else 0,
            "paid_calls_paused" to partial),
        "readiness" to timelineObject("available" to (!empty && !partial),
            "reason" to if (partial) "budget_exhausted" else if (empty) "provider_not_configured" else "available"),
    )
}

internal fun timelineProbeCheck(scenario: String, identifier: String): JSONObject? {
    if (identifier !in setOf(TIMELINE_CHECK, TIMELINE_EVENING_CHECK) || scenario == "empty") return null
    val evening = identifier == TIMELINE_EVENING_CHECK
    val skipped = evening || scenario == "partial"
    return timelineObject("check_id" to identifier, "checked_at" to if (evening) "2026-10-16T16:05:00Z" else TIMELINE_AS_OF,
        "slot" to if (evening) "evening" else "morning", "timezone" to "Europe/Moscow",
        "scheduled_at" to if (evening) "2026-10-16T16:00:00Z" else "2026-10-17T06:00:00Z",
        "state" to if (skipped) "skipped" else "ready",
        "reason" to if (evening) "market_closed" else if (skipped) "cooldown" else "portfolio_changed",
        "tier" to if (skipped) null else "standard", "card_id" to if (skipped) null else TIMELINE_REPORT,
        "run_id" to if (skipped) null else "synthetic-analysis-run", "error_code" to null,
        "trigger" to timelineTrigger(skipped))
}

internal fun timelineProbeFacts(): JSONObject = timelineObject(
    "current_card_id" to TIMELINE_REPORT, "previous_card_id" to "synthetic-previous-analysis",
    "has_more" to false, "items" to timelineArray(timelineObject(
        "id" to "position:synthetic-account:synthetic-stock", "state" to "changed",
        "before" to timelineFact("1000", "2026-10-16T10:00:00Z"),
        "after" to timelineFact("1100", TIMELINE_AS_OF),
        "provenance_changed" to true, "source_ids" to timelineArray(TIMELINE_SOURCE))))

private fun timelineComparison() = timelineObject(
    "current_card_id" to TIMELINE_REPORT, "previous_card_id" to "synthetic-previous-analysis",
    "fact_comparison_available" to true, "added" to JSONArray(), "removed" to JSONArray(),
    "changed" to timelineArray(timelineObject("field" to "summary", "before" to "Синтетический прежний вывод",
        "after" to "Синтетический обновлённый вывод")),
    "unchanged" to timelineArray(timelineObject("field" to "title", "value" to "Синтетическое наблюдение")),
    "structured_facts" to timelineObject("available" to true,
        "counts" to timelineObject("added" to 0, "changed" to 1, "unchanged" to 1)),
)

private fun timelineTrigger(skipped: Boolean) = timelineObject(
    "snapshot_id" to "synthetic-snapshot", "previous_snapshot_id" to "synthetic-previous-snapshot",
    "as_of" to TIMELINE_AS_OF, "comparison_basis" to "previous_autonomous_observation", "first_observation" to false,
    "policy_signals" to timelineObject("morning_due" to !skipped, "portfolio_changed" to true,
        "cash_changed" to false, "critical_risk" to false, "digest_changed" to true,
        "minutes_since_last_analysis" to if (skipped) 5 else 720),
    "observations" to timelineArray(timelineObject("id" to "synthetic-position-change", "kind" to "position_changed",
        "title" to "Синтетическое изменение позиции", "before" to timelinePosition("1000"),
        "after" to timelinePosition("1100"), "instrument_uids" to timelineArray("synthetic-stock"),
        "source_ids" to timelineArray(TIMELINE_SOURCE))),
    "sources" to timelineArray(timelineObject("id" to TIMELINE_SOURCE, "provider" to "СИНТЕТИЧЕСКИЙ источник проверки",
        "method" to "debug-only observations", "observed_at" to TIMELINE_AS_OF, "url" to null)),
    "coverage" to timelineObject("total" to 1, "included" to 1, "truncated" to false),
)

private fun timelinePosition(amount: String) = timelineObject("account_id" to "synthetic-account",
    "instrument_uid" to "synthetic-stock", "quantity" to "1",
    "value" to timelineObject("amount" to amount, "currency" to "RUB"))

private fun timelineFact(amount: String, asOf: String) = timelineObject(
    "value" to timelinePosition(amount), "as_of" to asOf,
    "highlight" to timelineObject("section" to "instrument", "id" to "synthetic-stock",
        "account_id" to "synthetic-account", "label" to "Показать связанную позицию"))

private fun timelineObject(vararg pairs: Pair<String, Any?>) = JSONObject().apply {
    pairs.forEach { (key, value) -> put(key, value ?: JSONObject.NULL) }
}
private fun timelineArray(vararg values: Any?) = JSONArray(values.toList())

private const val TIMELINE_AS_OF = "2026-10-17T10:00:00Z"
private const val TIMELINE_CHECK = "synthetic-monitor-check"
private const val TIMELINE_EVENING_CHECK = "synthetic-evening-check"
private const val TIMELINE_REPORT = "synthetic-analysis"
private const val TIMELINE_SOURCE = "synthetic-monitor-source"
