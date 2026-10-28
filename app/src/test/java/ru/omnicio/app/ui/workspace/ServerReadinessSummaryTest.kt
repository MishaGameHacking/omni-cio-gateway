package ru.omnicio.app.ui.workspace

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

/** Synthetic status payloads only; these are not owner portfolio observations. */
class ServerReadinessSummaryTest {
    private val now = Instant.parse("2026-10-27T17:30:00Z")

    private fun lane(at: String = now.minusSeconds(10).toString()): JSONObject = JSONObject()
        .put("id", "events").put("state", "current").put("coverage_complete", true)
        .put("freshness", JSONObject().put("as_of", at).put("state", "fresh").put("current", true))

    private fun status(lanes: JSONArray = JSONArray().put(lane())): JSONObject = JSONObject()
        .put("schema_version", 1).put("evaluated_at", now.minusSeconds(1).toString())
        .put("valuation_as_of", "2020-01-01T00:00:00Z")
        .put("execution_mode", "read_only").put("real_orders_enabled", false).put("lanes", lanes)

    @Test fun reportsReadOnlyWithoutRefreshingPortfolioTime() {
        val result = serverReadinessSummary(status(), now)
        assertTrue(result.evaluationCurrent)
        assertEquals("2020-01-01T00:00:00Z", result.valuationAt)
        assertEquals("Сбор и анализ · без торговых поручений", result.mode)
        assertEquals("Получены актуальные данные", result.lanes[1].state)
        assertEquals("Нет подтверждённых сведений", result.lanes[0].state)
    }

    @Test fun futureAndExpiredObservationsAreNotFresh() {
        for (at in listOf(now.plusSeconds(1), now.minusSeconds(1200))) {
            val result = serverReadinessSummary(status(JSONArray().put(lane(at.toString()))), now)
            assertEquals("Данные устарели или дата некорректна", result.lanes[1].state)
        }
    }

    @Test fun oldEvaluationDoesNotMakeRetainedPayloadCurrent() {
        val result = serverReadinessSummary(status().put("evaluated_at", now.minusSeconds(1200).toString()), now)
        assertFalse(result.evaluationCurrent)
        assertEquals("Режим работы не подтверждён", result.mode)
        assertEquals("Статус сервера устарел или не подтверждён", result.lanes[1].state)
    }

    @Test fun duplicatedLaneIdentityCannotGrantPositiveStatus() {
        val result = serverReadinessSummary(status(JSONArray().put(lane()).put(lane())), now)
        assertEquals("Нет подтверждённых сведений", result.lanes[1].state)
    }

    @Test fun booleanStringsAreNotAcceptedAsEvidence() {
        val result = serverReadinessSummary(status(JSONArray().put(lane().put("coverage_complete", "true")))
            .put("real_orders_enabled", "false"), now)
        assertEquals("Проверка данных не завершена", result.lanes[1].state)
        assertEquals("Режим работы не подтверждён", result.mode)
    }

    @Test fun missingUnknownAndMalformedRepliesRemainUnknown() {
        for (payload in listOf(null, JSONObject(), status().put("schema_version", 2),
            status().put("schema_version", "1"))) {
            val result = serverReadinessSummary(payload, now)
            assertFalse(result.supported)
            assertEquals(5, result.lanes.size)
            assertTrue(result.lanes.all { it.state == "Нет подтверждённых сведений" })
        }
        val result = serverReadinessSummary(status(JSONArray().put(lane("not-a-date"))), now)
        assertEquals("Время данных не подтверждено", result.lanes[1].state)
    }

    @Test fun futureEvaluationIsNotAWorkingServerAttestation() {
        val result = serverReadinessSummary(status().put("evaluated_at", now.plusSeconds(1).toString()), now)
        assertFalse(result.evaluationCurrent)
    }

    @Test fun displayParsingDoesNotMutateThePayload() {
        val payload = status()
        val before = payload.toString()
        serverReadinessSummary(payload, now)
        assertEquals(before, payload.toString())
    }
}
