package ru.omnicio.app.ui

internal data class BrokerAccount(val id: String, val name: String, val status: String)
internal data class ServerConnection(val connected: Boolean, val name: String?, val verifiedAt: String?, val accountId: String? = null)
internal data class ServerWorkspace(
    val connection: ServerConnection,
    val portfolio: ServerPortfolio?,
    val events: List<ServerEvent>,
    val nextEventCursor: String?,
    val goals: List<ServerGoal>,
)

