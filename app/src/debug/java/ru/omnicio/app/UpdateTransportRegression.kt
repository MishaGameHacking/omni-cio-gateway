package ru.omnicio.app

import java.net.URI
import javax.net.ssl.HttpsURLConnection
import ru.omnicio.app.data.updates.configureUpdateTransport

/** Configure real URL connection objects without connecting to any server. */
internal fun runUpdateTransportChecks(): Int {
    val paths = listOf("/client/update-policy", "/client/ready", "/client/apk/test.apk")
    for (path in paths) {
        val connection = URI("https://example.invalid$path").toURL().openConnection() as HttpsURLConnection
        try {
            val tlsFactory = connection.sslSocketFactory
            val hostVerifier = connection.hostnameVerifier
            // Do not depend on the process-wide default being secure.
            connection.instanceFollowRedirects = true
            connection.configureUpdateTransport()
            check(!connection.instanceFollowRedirects)
            check(!connection.useCaches)
            check(connection.connectTimeout == 10_000)
            check(connection.readTimeout == 30_000)
            check(connection.requestMethod == "GET")
            check(connection.getRequestProperty("Cache-Control") == "no-cache")
            check(connection.getRequestProperty("Accept-Encoding") == "identity")
            check(connection.sslSocketFactory === tlsFactory)
            check(connection.hostnameVerifier === hostVerifier)
        } finally {
            connection.disconnect()
        }
    }
    return 27
}
