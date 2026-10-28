package ru.omnicio.app.ui.home

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class SystemReadinessModelTest {
    private fun lane(id: String = "valuation", state: String = "current"): JSONObject = JSONObject()
        .put("id", id).put("title", "Оценка портфеля").put("state", state).put("coverage_complete", true)
        .put("freshness", JSONObject().put("as_of", "2026-10-28T08:59:00Z")
            .put("current", true).put("state", "fresh").put("max_age_seconds", 300))

    private fun status(vararg rows: Any): JSONObject = JSONObject().put("schema_version", 1)
        .put("state", "restricted_read_only").put("evaluated_at", "2026-10-28T09:00:00Z")
        .put("valuation_as_of", "2026-10-28T08:00:00Z").put("execution_mode", "read_only")
        .put("real_orders_enabled", false).put("lanes", JSONArray(rows.toList()))

    @Test fun distinctValuationTimeDoesNotBecomeStatusTime() {
        val model = systemReadinessModel(status(lane()))!!
        assertEquals("2026-10-28T08:00:00Z", model.valuationAt)
        assertEquals("2026-10-28T09:00:00Z", model.evaluatedAt)
        assertEquals(1, model.currentCount)
        assertEquals(1f, model.freshnessFraction!!, 0f)
        assertTrue(model.readOnlyConfirmed)
        assertFalse(model.liveCashReconciled)
    }

    @Test fun onlyCompleteCurrentEvidenceCounts() {
        val partial = lane("operations").put("coverage_complete", false)
        val model = systemReadinessModel(status(lane(), lane("news", "stale"), partial))!!
        assertEquals(1, model.currentCount)
        assertEquals(3, model.lanes.size)
        assertEquals("unknown", model.lanes[2].state)
    }

    @Test fun forgedCurrentFlagCannotOverrideStaleClock() {
        val row = lane()
        row.getJSONObject("freshness").put("as_of", "2026-10-28T08:55:00Z")
        assertEquals(0, systemReadinessModel(status(row))!!.currentCount)
    }

    @Test fun futureAndInvalidClocksCannotBeCurrent() {
        for (clock in listOf("2026-10-28T10:00:00Z", "yesterday", "2026-10-28T08:59:00")) {
            val row = lane(); row.getJSONObject("freshness").put("as_of", clock)
            val model = systemReadinessModel(status(row))!!
            assertEquals(0, model.currentCount)
            assertNull(model.lanes[0].observedAt)
        }
    }

    @Test fun booleanStringsAreNotAcceptedAsVerification() {
        val row = lane().put("coverage_complete", "true")
        row.getJSONObject("freshness").put("current", "true")
        val model = systemReadinessModel(status(row).put("real_orders_enabled", "false"))!!
        assertEquals(0, model.currentCount)
        assertFalse(model.readOnlyConfirmed)
    }

    @Test fun missingOrRepeatedIdsAreNeverAllFresh() {
        val missing = lane().also { it.remove("id") }
        val model = systemReadinessModel(status(lane(), lane(), missing, "broken row"))!!
        assertEquals(4, model.lanes.size)
        assertEquals(0, model.currentCount)
    }

    @Test fun unknownSchemaAndInvalidEnvelopeAreRejected() {
        assertNull(systemReadinessModel(null))
        assertNull(systemReadinessModel(status().put("schema_version", 2)))
        assertNull(systemReadinessModel(status().put("schema_version", "1")))
        assertNull(systemReadinessModel(status().put("state", "all_done")))
        assertNull(systemReadinessModel(status().put("evaluated_at", JSONObject.NULL)))
    }

    @Test fun emptyEvidenceHasNoMadeUpPercentage() {
        val model = systemReadinessModel(status())!!
        assertEquals(0, model.currentCount)
        assertNull(model.freshnessFraction)
        assertNull(model.sourceCount)
        assertNull(model.unresolvedSources)
    }

    @Test fun sourceCountsDoNotImplyFinancialVerification() {
        val model = systemReadinessModel(status(lane()).put("provenance", JSONObject()
            .put("source_count", 4).put("unresolved_reference_count", 0).put("financial_facts_verified", true)))!!
        assertEquals(4, model.sourceCount)
        assertEquals(0, model.unresolvedSources)
        assertFalse(model.liveCashReconciled)
    }

    @Test fun negativeAndStringCountsRemainUnknown() {
        val model = systemReadinessModel(status().put("provenance", JSONObject()
            .put("source_count", -1).put("unresolved_reference_count", "0")))!!
        assertNull(model.sourceCount)
        assertNull(model.unresolvedSources)
    }

    @Test fun noticesExposeUserConditionsWithoutImplementationPaths() {
        val notices = JSONArray().put(JSONObject().put("kind", "data").put("message", "Новости устарели"))
            .put(JSONObject().put("kind", "implementation_or_acceptance").put("message", "internal/source/path"))
            .put(JSONObject().put("kind", "connection").put("message", "Нет подключения"))
        val model = systemReadinessModel(status().put("blockers", notices))!!
        assertEquals(listOf("Новости устарели", "Нет подключения"), model.notices)
    }

    @Test fun allReceivedLanesRemainAccessible() {
        val rows = (1..120).map { lane("section-$it") }.toTypedArray()
        assertEquals(120, systemReadinessModel(status(*rows))!!.lanes.size)
    }
}
