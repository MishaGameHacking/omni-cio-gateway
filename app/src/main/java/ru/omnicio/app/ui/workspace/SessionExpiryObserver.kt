package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.*
import ru.omnicio.app.data.backend.SessionExpiry

@Composable
fun SessionExpiryObserver(token: String, onExpired: () -> Unit) {
    val callback by rememberUpdatedState(onExpired)
    LaunchedEffect(token) {
        val fingerprint = SessionExpiry.fingerprint(token)
        SessionExpiry.expired.collect { if (it == fingerprint) callback() }
    }
}
