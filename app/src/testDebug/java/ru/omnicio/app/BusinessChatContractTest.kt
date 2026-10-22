package ru.omnicio.app

import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.omnicio.app.data.workspace.ChatRouteQuote

/** Exercises the value contract used by the actual debug transport, without Android JSON stubs. */
class BusinessChatContractTest {
    private val asOf = "2026-10-17T10:00:00Z"
    private val requestId = "12345678-abcd-4321-abcd-123456789abc"
    private val request = ProbeChatRequest("synthetic-thread", "UIprobe",
        "{\"mode\":\"portfolio\",\"account_id\":\"synthetic-account\"}", "portfolio", "auto")
    private val contract = BusinessChatContract(request.threadId, asOf)

    @Test fun autoEstimateIsUsableByTheProductionQuoteAndBindsTheUnchangedAutoRequest() {
        val payload = contract.estimate(request)
        val quote = quote(payload)
        assertTrue(quote.usable)
        assertFalse(quote.needsConfirmation(request.tier))
        assertEquals("fast", quote.selectedTier)
        assertEquals(10_000L, requireNotNull(quote.ceilingMicroRub))
        assertTrue(payload.getValue("synthetic") as Boolean)
        assertFalse(payload.getValue("exact_invoice") as Boolean)
        assertNull(payload["reason"])
        assertEquals(asOf, payload["context_as_of"])
        assertEquals("synthetic-chat-fast", payload["model"])
        assertEquals("fast", payload["required_tier"])
        assertEquals(600, payload["max_output_tokens"])
        assertEquals("synthetic_debug_contract", payload["basis"])
        assertEquals(emptyList<String>(), payload["tools"])
        assertEquals("synthetic_fixed_route", payload["routing_reason"])
        assertEquals("synthetic-chat-v1", payload["policy_version"])
        assertEquals("deterministic_rules", payload["classification_method"])
        val upperBound = payload.getValue("estimated_upper_bound") as Map<*, *>
        assertEquals("RUB", upperBound["currency"])
        assertEquals(0, BigDecimal(upperBound["amount"] as String).movePointRight(6).compareTo(BigDecimal(10_000)))
        contract.validateSend(requestId, request, quote.ceilingMicroRub, quote.routeId, null)
    }

    @Test fun manualTiersReturnConcreteRoutesWithTheRequiredConfirmation() {
        val routes = mutableSetOf<String>()
        for (tier in listOf("fast", "standard", "premium")) {
            val selected = request.copy(tier = tier)
            val quote = quote(contract.estimate(selected))
            assertTrue(quote.usable)
            assertEquals(tier, quote.selectedTier)
            assertEquals(tier == "premium", quote.needsConfirmation(tier))
            assertTrue(routes.add(quote.routeId))
            contract.validateSend(requestId, selected, quote.ceilingMicroRub, quote.routeId, tier == "premium")
        }
    }

    @Test fun messageWithoutAnEstimateIsRejected() {
        val route = "a".repeat(64)
        assertThrows(IllegalStateException::class.java) {
            contract.validateSend(requestId, request, 10_000L, route, null)
        }
    }

    @Test fun everyEstimatedInputRemainsBoundToTheSend() {
        val quote = quote(contract.estimate(request))
        val changes = listOf(
            request.copy(threadId = "another-thread"),
            request.copy(text = "changed question"),
            request.copy(context = "{\"mode\":\"portfolio\",\"account_id\":\"other-account\"}"),
            request.copy(contextMode = "general"),
            request.copy(tier = "fast"),
        )
        for (changed in changes) {
            assertThrows(IllegalArgumentException::class.java) {
                contract.validateSend(requestId, changed, quote.ceilingMicroRub, quote.routeId, null)
            }
        }
        contract.validateSend(requestId, request, quote.ceilingMicroRub, quote.routeId, null)
    }

    @Test fun missingChangedAndCoercedCostsAreRejected() {
        val quote = quote(contract.estimate(request))
        val costs = listOf(null, 0L, -1L, 9_999L, 10_001L, 10_000.0, "10000", true, BigDecimal(10_000))
        for (cost in costs) {
            assertThrows(IllegalArgumentException::class.java) {
                contract.validateSend(requestId, request, cost, quote.routeId, null)
            }
        }
    }

    @Test fun bothJsonIntegerRepresentationsRetainTheQuotedCeiling() {
        val quote = quote(contract.estimate(request))
        contract.validateSend(requestId, request, 10_000, quote.routeId, false)
        contract.validateSend(requestId, request, 10_000L, quote.routeId, null)
    }

    @Test fun missingMalformedAndChangedRoutesAreRejected() {
        val quote = quote(contract.estimate(request))
        val routes = listOf(null, "", "a".repeat(63), "A".repeat(64), "b".repeat(64), 10_000L, false)
        for (route in routes) {
            assertThrows(IllegalArgumentException::class.java) {
                contract.validateSend(requestId, request, quote.ceilingMicroRub, route, null)
            }
        }
    }

    @Test fun premiumCannotBeSentWithoutExplicitBooleanConfirmation() {
        val premium = request.copy(tier = "premium")
        val quote = quote(contract.estimate(premium))
        assertTrue(quote.needsConfirmation(premium.tier))
        for (confirmation in listOf(null, false, "true", 1)) {
            assertThrows(IllegalArgumentException::class.java) {
                contract.validateSend(requestId, premium, quote.ceilingMicroRub, quote.routeId, confirmation)
            }
        }
        contract.validateSend(requestId, premium, quote.ceilingMicroRub, quote.routeId, true)
    }

    @Test fun ordinaryRequestsAlsoRejectCoercedConfirmation() {
        val quote = quote(contract.estimate(request))
        for (confirmation in listOf("false", "true", 0, 1)) {
            assertThrows(IllegalArgumentException::class.java) {
                contract.validateSend(requestId, request, quote.ceilingMicroRub, quote.routeId, confirmation)
            }
        }
    }

    @Test fun requestIdentifierMustBeCanonicalBeforeItCanBeAccepted() {
        val quote = quote(contract.estimate(request))
        val identifiers = listOf("", "synthetic-request", requestId.uppercase(), " $requestId", "1-1-1-1-1")
        for (identifier in identifiers) {
            assertThrows(IllegalArgumentException::class.java) {
                contract.validateSend(identifier, request, quote.ceilingMicroRub, quote.routeId, null)
            }
        }
    }

    @Test fun aChangedEstimateDoesNotAuthorizeThePreviousDraft() {
        val previous = quote(contract.estimate(request))
        val changed = request.copy(text = "Another draft")
        val current = quote(contract.estimate(changed))
        assertThrows(IllegalArgumentException::class.java) {
            contract.validateSend(requestId, request, previous.ceilingMicroRub, previous.routeId, null)
        }
        contract.validateSend(requestId, changed, current.ceilingMicroRub, current.routeId, null)
    }

    @Test fun changingTheReturnedPayloadCannotChangeTheServerAuthorization() {
        val payload = contract.estimate(request).toMutableMap()
        val original = quote(payload)
        payload["cost_ceiling_micro_rub"] = 20_000L
        payload["route_id"] = "d".repeat(64)
        assertThrows(IllegalArgumentException::class.java) {
            contract.validateSend(requestId, request, payload["cost_ceiling_micro_rub"], payload["route_id"], null)
        }
        contract.validateSend(requestId, request, original.ceilingMicroRub, original.routeId, null)
    }

    @Test fun invalidEstimateInputsAreNotIssuedAQuote() {
        val invalid = listOf(request.copy(threadId = "other-thread"), request.copy(text = " "),
            request.copy(text = "x".repeat(8_001)), request.copy(tier = "unknown"), request.copy(contextMode = "unknown"))
        for (candidate in invalid) {
            assertThrows(IllegalArgumentException::class.java) { contract.estimate(candidate) }
        }
    }

    @Test fun jobReceiptsPreserveTheAcceptedRequestAndActualJobKind() {
        for (kind in listOf("chat", "analysis", "reconcile")) {
            val payload = businessProbeJobPayload("synthetic-job-2", requestId, kind, "running", asOf)
            assertEquals("synthetic-job-2", payload["job_id"])
            assertEquals(requestId, payload["request_id"])
            assertEquals(kind, payload["kind"])
            assertEquals("running", payload["state"])
            assertEquals("collecting", payload["stage"])
            assertEquals(asOf, payload["created_at"])
            assertEquals(asOf, payload["updated_at"])
            assertNull(payload["result"])
            assertNull(payload["error_code"])
            assertFalse(payload.getValue("can_retry") as Boolean)
            assertFalse(payload.getValue("cancel_requested") as Boolean)
        }
    }

    @Test fun uncertainSavedJobsDoNotBecomeRetryable() {
        val payload = businessProbeJobPayload("synthetic-job", "synthetic-request", "synthetic", "uncertain", asOf)
        assertEquals("uncertain", payload["state"])
        assertEquals("provider_request", payload["stage"])
        assertFalse(payload.getValue("can_retry") as Boolean)
    }

    private fun quote(payload: Map<String, Any?>) = ChatRouteQuote(
        payload.getValue("available") as Boolean,
        payload.getValue("selected_tier") as String,
        payload.getValue("requires_cost_confirmation") as Boolean,
        payload.getValue("cost_ceiling_micro_rub") as Long,
        payload.getValue("route_id") as String,
    )
}
