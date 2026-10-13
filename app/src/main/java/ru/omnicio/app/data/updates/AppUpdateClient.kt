package ru.omnicio.app.data.updates

import java.io.File
import java.io.IOException
import java.net.URI
import javax.net.ssl.HttpsURLConnection
import ru.omnicio.app.data.backend.BackendConfig

internal class AppUpdateClient(
    private val baseUrl: String = BackendConfig.BASE_URL,
) {
    fun fetchRelease(): AppRelease {
        val connection = open("$baseUrl/releases/current.json", accept = "application/json")
        return try {
            val status = connection.responseCode
            if (status != HttpsURLConnection.HTTP_OK) {
                throw IOException("Сервер обновлений ответил кодом $status.")
            }
            val declared = connection.contentLengthLong
            if (declared > MAX_MANIFEST_BYTES) {
                throw IOException("Описание обновления слишком большое.")
            }
            val bytes = connection.inputStream.use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8 * 1024)
                var total = 0L
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    if (total > MAX_MANIFEST_BYTES) {
                        throw IOException("Описание обновления слишком большое.")
                    }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            AppRelease.parse(bytes.toString(Charsets.UTF_8))
        } finally {
            connection.disconnect()
        }
    }

    fun download(
        release: AppRelease,
        destination: File,
        onProgress: (received: Long, total: Long) -> Unit,
    ) {
        val connection = open(release.url, accept = "application/vnd.android.package-archive")
        try {
            val status = connection.responseCode
            if (status != HttpsURLConnection.HTTP_OK) {
                throw IOException("Сервер APK ответил кодом $status.")
            }
            val declared = connection.contentLengthLong
            if (declared > 0L && declared != release.sizeBytes) {
                throw IOException("Размер APK не совпадает с описанием обновления.")
            }
            destination.parentFile?.mkdirs()
            val temporary = File(destination.parentFile, destination.name + ".part")
            if (temporary.exists() && !temporary.delete()) {
                throw IOException("Не удалось очистить временный APK.")
            }
            try {
                connection.inputStream.use { input ->
                    temporary.outputStream().buffered().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        var received = 0L
                        var reported = -1L
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            received += count
                            if (received > release.sizeBytes || received > MAX_APK_BYTES) {
                                throw IOException("APK превышает разрешённый размер.")
                            }
                            output.write(buffer, 0, count)
                            if (received - reported >= 256 * 1024 || received == release.sizeBytes) {
                                reported = received
                                onProgress(received, release.sizeBytes)
                            }
                        }
                        output.flush()
                        if (received != release.sizeBytes) {
                            throw IOException("APK загружен не полностью.")
                        }
                    }
                }
                if (destination.exists() && !destination.delete()) {
                    throw IOException("Не удалось заменить старый APK обновления.")
                }
                if (!temporary.renameTo(destination)) {
                    throw IOException("Не удалось подготовить APK к проверке.")
                }
            } finally {
                if (temporary.exists()) temporary.delete()
            }
        } finally {
            connection.disconnect()
        }
    }

    private fun open(url: String, accept: String): HttpsURLConnection {
        val uri = URI(url)
        if (uri.scheme != "https" || uri.host != UPDATE_HOST || uri.port != -1) {
            throw IOException("Запрещённый адрес сервера обновлений.")
        }
        return (uri.toURL().openConnection() as HttpsURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10_000
            readTimeout = 60_000
            instanceFollowRedirects = false
            useCaches = false
            setRequestProperty("Accept", accept)
            setRequestProperty("Cache-Control", "no-cache")
            setRequestProperty("X-Analyst-App-Version-Code", ru.omnicio.app.BuildConfig.VERSION_CODE.toString())
        }
    }

    companion object {
        private const val MAX_MANIFEST_BYTES = 64L * 1024L
    }
}
