package ru.omnicio.app.data.portfolio

/** One atomic UI value. A response may only finish the request that started it. */
internal data class RefreshSnapshot<Q : Any, V : Any>(
    val value: V? = null,
    val displayedQuery: Q? = null,
    val requestedQuery: Q? = null,
    val requestId: Long = 0,
    val loading: Boolean = false,
    val error: String? = null,
    val receivedAtMillis: Long? = null,
) {
    fun start(query: Q): RefreshSnapshot<Q, V> = copy(
        requestedQuery = query, requestId = requestId + 1, loading = true, error = null,
    )

    fun succeed(id: Long, result: V, receivedAt: Long): RefreshSnapshot<Q, V> {
        if (!accepts(id)) return this
        return copy(value = result, displayedQuery = requestedQuery, loading = false,
            error = null, receivedAtMillis = receivedAt)
    }

    fun fail(id: Long, message: String): RefreshSnapshot<Q, V> {
        if (!accepts(id)) return this
        return copy(loading = false, error = message)
    }

    fun cancel(id: Long): RefreshSnapshot<Q, V> {
        if (!accepts(id)) return this
        return copy(requestId = requestId + 1, loading = false)
    }

    private fun accepts(id: Long): Boolean = loading && id == requestId
}

/** Delay after a completed request; no timer can launch an overlapping poll. */
internal class RefreshBackoff(private val baseMillis: Long, private val maximumMillis: Long = 120_000L) {
    init {
        require(baseMillis > 0 && maximumMillis >= baseMillis)
    }

    private var nextMillis = baseMillis

    fun success(): Long {
        nextMillis = baseMillis
        return nextMillis
    }

    fun failure(): Long {
        nextMillis = if (nextMillis >= maximumMillis - nextMillis) maximumMillis else nextMillis * 2
        return nextMillis
    }
}
