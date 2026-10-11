package ru.omnicio.app.ui

internal data class ServerEvent(
    val id: String,
    val title: String,
    val detail: String,
    val at: String?,
    val severity: String?,
    val source: String?,
    val read: Boolean,
)

internal data class ServerGoal(
    val id: String,
    val title: String,
    val target: java.math.BigDecimal?,
    val date: String?,
    val status: String?,
)
