package ru.omnicio.app.data.updates

import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import java.io.File
import java.net.URI
import java.security.MessageDigest
import javax.net.ssl.HttpsURLConnection
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.backend.BackendConfig

class UpdateClient {
    private companion object { val downloadLock = Mutex() }
    private fun connect(path: String): HttpsURLConnection {
        require(path.startsWith("/client/") && !path.contains(".."))
        val base = URI(BackendConfig.BASE_URL)
        require(base.scheme == "https" && base.userInfo == null && base.query == null && base.fragment == null)
        return (URI(BackendConfig.BASE_URL + path).toURL().openConnection() as HttpsURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10_000
            readTimeout = 30_000
            useCaches = false
            ClientVersion.attach(this)
        }
    }

    suspend fun current(): ReleaseDescriptor = withContext(Dispatchers.IO) {
        val connection = connect("/client/update-policy?package_name=${BuildConfig.APPLICATION_ID}")
        try {
            check(connection.responseCode == 200) { "Сервер обновлений пока недоступен. Повторите проверку." }
            val bytes = connection.inputStream.use { it.readNBytes(16_385) }
            check(bytes.size <= 16_384) { "Некорректное описание обновления." }
            val json = JSONObject(String(bytes, Charsets.UTF_8))
            fun integer(name: String): Long = json.get(name).toString().toLongOrNull()
                ?: error("Некорректная версия обновления.")
            check(integer("schema_version") == 1L)
            val release = ReleaseDescriptor(
                json.getString("package_name"), integer("version_code"), json.getString("version_name"),
                json.getString("apk_sha256"), integer("apk_bytes"), json.getString("certificate_sha256"),
                integer("min_sdk").also { check(it in 33..100) }.toInt(), json.optString("notes"),
            )
            check(integer("minimum_version_code") == release.versionCode)
            check(json.getString("apk_path") == "/client/apk/${release.filename}")
            release
        } finally { connection.disconnect() }
    }

    suspend fun acknowledge(token: String) = withContext(Dispatchers.IO) {
        val connection = connect("/client/ready")
        try {
            connection.requestMethod = "POST"
            connection.setRequestProperty("Authorization", "Bearer $token")
            when (val status = connection.responseCode) {
                200 -> Unit
                401 -> Unit // Login can be restored/repeated by the normal auth layer.
                426 -> { ClientVersion.observeStatus(status); error("Версия уже изменилась. Проверяем обновление.") }
                else -> error("Не удалось подтвердить версию на сервере.")
            }
        } finally { connection.disconnect() }
    }

    suspend fun download(context: Context, release: ReleaseDescriptor, progress: (Int) -> Unit): File =
        downloadLock.withLock { downloadLocked(context, release, progress) }

    private suspend fun downloadLocked(context: Context, release: ReleaseDescriptor, progress: (Int) -> Unit): File = withContext(Dispatchers.IO) {
        check(release.decision(BuildConfig.APPLICATION_ID, BuildConfig.VERSION_CODE.toLong(), Build.VERSION.SDK_INT) == ReleaseDecision.UPDATE_REQUIRED)
        val directory = File(context.filesDir, "updates").apply { mkdirs() }
        val complete = File(directory, release.filename)
        if (complete.isFile && runCatching { verifyArchive(context, complete, release) }.isSuccess) return@withContext complete
        val partial = File(directory, "download.part")
        val connection = connect(release.apkPath)
        try {
            check(directory.usableSpace >= release.bytes * 3 + 20 * 1024 * 1024) { "Недостаточно свободной памяти для обновления." }
            check(connection.responseCode == 200) { "Не удалось скачать APK с сервера Analyst AI." }
            val advertised = connection.contentLengthLong
            check(advertised == -1L || advertised == release.bytes) { "Размер файла не совпадает с описанием." }
            var received = 0L
            val deadline = System.nanoTime() + 10L * 60 * 1_000_000_000
            connection.inputStream.use { input ->
                partial.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var previousProgress = -1
                    while (true) {
                        ensureActive()
                        check(System.nanoTime() < deadline) { "Время скачивания истекло. Повторите попытку." }
                        val count = input.read(buffer)
                        if (count < 0) break
                        received += count
                        check(received <= release.bytes) { "Размер обновления превышает ожидаемый." }
                        output.write(buffer, 0, count)
                        val percent = (100 * received / release.bytes).toInt()
                        if (percent != previousProgress) { progress(percent); previousProgress = percent }
                    }
                    output.fd.sync()
                }
            }
            check(received == release.bytes) { "Файл скачан не полностью. Повторите попытку." }
            verifyArchive(context, partial, release)
            check(partial.renameTo(complete)) { "Не удалось сохранить обновление." }
            // Remove only obsolete APKs from this dedicated private directory.
            directory.listFiles()?.filter { it != complete && it.name.endsWith(".apk") }?.forEach { it.delete() }
            complete
        } finally { connection.disconnect(); partial.delete() }
    }

    fun verifyArchive(context: Context, file: File, release: ReleaseDescriptor) {
        check(file.length() == release.bytes) { "Повреждённый файл обновления." }
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) { val count = input.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
        }
        check(hex(digest.digest()) == release.sha256) { "Проверка целостности обновления не пройдена." }
        val flags = PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong())
        val installed = context.packageManager.getPackageInfo(context.packageName, flags)
        val candidate = context.packageManager.getPackageArchiveInfo(file.absolutePath, flags)
            ?: error("Android не распознал APK.")
        check(candidate.packageName == context.packageName && candidate.packageName == release.packageName)
        check(candidate.longVersionCode == release.versionCode && candidate.longVersionCode > installed.longVersionCode)
        val application = candidate.applicationInfo ?: error("APK не содержит метаданных приложения.")
        check(application.minSdkVersion == release.minSdk && application.minSdkVersion <= Build.VERSION.SDK_INT)
        check(application.flags and ApplicationInfo.FLAG_TEST_ONLY == 0)
        fun certificates(info: android.content.pm.PackageInfo): Set<String> = info.signingInfo?.apkContentsSigners
            ?.map { hex(MessageDigest.getInstance("SHA-256").digest(it.toByteArray())) }?.toSet() ?: emptySet()
        val expected = setOf(release.certificateSha256)
        check(certificates(installed) == expected && certificates(candidate) == expected) {
            "Подпись APK отличается. Установка остановлена; удалять приложение не нужно."
        }
    }

    private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it) }
}
