package ru.omnicio.app.data.updates

import javax.net.ssl.HttpsURLConnection

/** Configure one first-party request before credentials or any I/O. */
internal fun HttpsURLConnection.configureUpdateTransport() {
    requestMethod = "GET"
    instanceFollowRedirects = false
    connectTimeout = 10_000
    readTimeout = 30_000
    useCaches = false
    setRequestProperty("Cache-Control", "no-cache")
    setRequestProperty("Accept-Encoding", "identity")
}
