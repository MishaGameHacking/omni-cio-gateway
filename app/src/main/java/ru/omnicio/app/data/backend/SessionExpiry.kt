package ru.omnicio.app.data.backend

import java.security.MessageDigest
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/** An old in-flight response cannot sign out a new session. Tokens never enter event payloads. */
object SessionExpiry {
    private val changes = MutableSharedFlow<String>(extraBufferCapacity = 16)
    val expired = changes.asSharedFlow()
    fun fingerprint(token: String): String = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it) }
    fun observe(status: Int, bearer: String?) {
        if (status in setOf(401, 403) && !bearer.isNullOrBlank()) changes.tryEmit(fingerprint(bearer))
    }
}
