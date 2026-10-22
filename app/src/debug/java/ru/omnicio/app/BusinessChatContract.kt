package ru.omnicio.app

import java.math.BigDecimal
import java.util.UUID
import ru.omnicio.app.data.workspace.ChatRouteQuote

/** The context is serialized from the actual request JSONObject before it is captured. */
internal data class ProbeChatRequest(
    val threadId: String,
    val text: String,
    val context: String,
    val contextMode: String,
    val tier: String,
)

/** Debug-only server contract; none of these routes, prices or models are live. */
internal class BusinessChatContract(private val threadId: String, private val asOf: String) {
    private data class Estimate(val request: ProbeChatRequest, val quote: ChatRouteQuote)
    private var issued: Estimate? = null

    fun estimate(request: ProbeChatRequest): Map<String, Any?> {
        require(request.threadId == threadId && request.text.isNotBlank() && request.text.length <= 8_000)
        require(request.contextMode in setOf("general", "portfolio", "instrument"))
        require(request.tier in setOf("auto", "fast", "standard", "premium"))
        // This fixture has a fixed ordinary route; it does not simulate AI classification.
        val selected = if (request.tier == "auto") "fast" else request.tier
        val route = mapOf("fast" to "a", "standard" to "b", "premium" to "c").getValue(selected).repeat(64)
        val ceiling = 10_000L
        val quote = ChatRouteQuote(true, selected, selected == "premium", ceiling, route)
        issued = Estimate(request, quote)
        return linkedMapOf(
            "available" to quote.available,
            "reason" to null,
            "estimated_upper_bound" to mapOf(
                "amount" to BigDecimal(ceiling).movePointLeft(6).stripTrailingZeros().toPlainString(),
                "currency" to "RUB",
            ),
            "exact_invoice" to false,
            "context_as_of" to asOf,
            "model" to "synthetic-chat-$selected",
            "basis" to "synthetic_debug_contract",
            "tools" to emptyList<String>(),
            "cost_ceiling_micro_rub" to quote.ceilingMicroRub,
            "route_id" to quote.routeId,
            "selected_tier" to quote.selectedTier,
            "required_tier" to "fast",
            "max_output_tokens" to mapOf("fast" to 600, "standard" to 1200, "premium" to 1600).getValue(selected),
            "routing_reason" to "synthetic_fixed_route",
            "policy_version" to "synthetic-chat-v1",
            "classification_method" to "deterministic_rules",
            "requires_cost_confirmation" to quote.confirmationRequired,
            "synthetic" to true,
        )
    }

    fun validateSend(requestId: String, request: ProbeChatRequest, maxCost: Any?, routeId: Any?, confirmation: Any?) {
        require(UUID.fromString(requestId).toString() == requestId)
        val estimated = checkNotNull(issued) { "Message requires a preceding exact cost estimate" }
        require(request == estimated.request) { "Message inputs changed after the estimate" }
        val cost = when (maxCost) {
            is Int -> maxCost.toLong()
            is Long -> maxCost
            else -> throw IllegalArgumentException("Message ceiling must be an integer")
        }
        require(cost == estimated.quote.ceilingMicroRub) { "Message ceiling changed after the estimate" }
        require(routeId is String && routeId == estimated.quote.routeId) { "Message route changed after the estimate" }
        val confirmed = when (confirmation) {
            null -> false
            is Boolean -> confirmation
            else -> throw IllegalArgumentException("Message confirmation must be a boolean")
        }
        require(!estimated.quote.needsConfirmation(request.tier) || confirmed) { "Premium requires explicit confirmation" }
    }
}

/** The same receipt shape is returned by enqueue, lookup by request and job polling. */
internal fun businessProbeJobPayload(id: String, requestId: String, kind: String, state: String, asOf: String): Map<String, Any?> =
    linkedMapOf(
        "job_id" to id,
        "request_id" to requestId,
        "kind" to kind,
        "state" to state,
        "stage" to if (state == "uncertain") "provider_request" else "collecting",
        "created_at" to asOf,
        "updated_at" to asOf,
        "result" to null,
        "error_code" to null,
        "cancel_requested" to false,
        "can_retry" to false,
    )
