package ru.omnicio.app.data.backend

import java.net.URI
import javax.net.ssl.HttpsURLConnection

object BackendConfig {
    // Verified owner installation on Timeweb; every client shares this HTTPS origin.
    const val HOST = "analyst-ai-2941515.twc1.net"
    const val BASE_URL = "https://$HOST"
    const val UNAVAILABLE_MESSAGE = "Новый сервер Analyst AI ещё не настроен. Вход и синхронизация пока недоступны."
    private const val RETIRED_HOST = "176.98.178.81.sslip.io"

    val isConfigured: Boolean
        get() = URI(BASE_URL).host.let { it != RETIRED_HOST && !it.endsWith(".invalid") }

    fun requireActiveOrigin(uri: URI) {
        check(isConfigured) { UNAVAILABLE_MESSAGE }
        require(uri.scheme == "https" && uri.host == HOST && uri.rawAuthority == HOST)
        require(uri.rawUserInfo == null && uri.port == -1 && uri.rawFragment == null)
    }

    fun openConnection(uri: URI): HttpsURLConnection {
        // Check before creating a transport or attaching any session token.
        requireActiveOrigin(uri)
        return (uri.toURL().openConnection() as HttpsURLConnection).apply {
            instanceFollowRedirects = false
        }
    }
}
