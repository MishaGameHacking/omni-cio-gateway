package ru.omnicio.app.data.backend

data class AnalystUser(
    val telegramId: String,
    val name: String?,
    val username: String?,
    val pictureUrl: String?,
)

data class AnalystSession(
    val accessToken: String,
    val expiresInSeconds: Long,
    val user: AnalystUser,
)

sealed interface BackendResult<out T> {
    data class Success<T>(val value: T) : BackendResult<T>
    data class Failure(val message: String, val retryable: Boolean, val statusCode: Int? = null) : BackendResult<Nothing>
}


data class OwnerAccessStatus(
    val configured: Boolean,
    val minimumPasswordLength: Int,
    val maximumPasswordBytes: Int,
)
