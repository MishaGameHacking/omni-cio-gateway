package ru.omnicio.app.data.updates

import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import java.io.File
import java.io.OutputStream
import java.security.MessageDigest
import java.time.Instant
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

    private fun connect(path: String): HttpsURLConnection =
        (UpdateProtocol.requestUri(BackendConfig.BASE_URL, path).toURL().openConnection() as HttpsURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10_000
            readTimeout = 30_000
            useCaches = false
            setRequestProperty("Cache-Control", "no-cache")
            ClientVersion.attach(this)
        }

    suspend fun current(): ReleaseDescriptor = withContext(Dispatchers.IO) {
        val connection = connect(UpdateProtocol.policyPath(BuildConfig.APPLICATION_ID))
        connection.readTimeout = 10_000
        connection.setRequestProperty("Accept-Encoding", "identity")
        try {
            withTimedUpdateCall(45_000, disconnect = {
                runCatching { connection.disconnect() }.onFailure {
                    Log.w("AnalystUpdate", "Не удалось закрыть соединение проверки обновления.")
                }
            }) {
                ensureActive()
                check(connection.responseCode == 200) { "Сервер обновлений пока недоступен. Повторите проверку." }
                val declared = connection.contentLengthLong
                check(declared in -1L..UpdateProtocol.MAX_MANIFEST_BYTES.toLong()) { "Некорректный размер описания обновления." }
                val bytes = connection.inputStream.use { input ->
                    readUpdatePolicy(input, UpdateProtocol.MAX_MANIFEST_BYTES) { ensureActive() }
                }
                check(declared == -1L || declared == bytes.size.toLong()) { "Описание обновления загружено не полностью." }
                val json = JSONObject(decodeUpdatePolicy(bytes))
                val fields = json.keys().asSequence().associateWith { json.get(it) }
                UpdateProtocol.parse(fields, Instant.now().epochSecond)
            }
        } finally { connection.disconnect() }
    }

    suspend fun acknowledge(token: String) = withContext(Dispatchers.IO) {
        val connection = connect("/client/ready")
        try {
            connection.requestMethod = "POST"
            connection.setRequestProperty("Authorization", "Bearer $token")
            when (val status = connection.responseCode) {
                200 -> Unit
                401 -> Unit // The existing authentication flow handles an expired session.
                426 -> { ClientVersion.observeStatus(status); error("Версия уже изменилась. Проверяем обновление.") }
                else -> error("Не удалось подтвердить версию на сервере.")
            }
        } finally { connection.disconnect() }
    }

    suspend fun download(context: Context, release: ReleaseDescriptor, progress: (Int) -> Unit): File =
        downloadLock.withLock { downloadLocked(context, release, progress) }

    private suspend fun downloadLocked(context: Context, release: ReleaseDescriptor, progress: (Int) -> Unit): File = withContext(Dispatchers.IO) {
        check(release.decision(BuildConfig.APPLICATION_ID, BuildConfig.VERSION_CODE.toLong(), Build.VERSION.SDK_INT) == ReleaseDecision.UPDATE_REQUIRED)
        val directory = File(context.filesDir, "updates")
        check((directory.isDirectory || directory.mkdirs()) && directory.isDirectory) { "Не удалось подготовить место для обновления." }
        val complete = File(directory, release.filename)
        if (complete.isFile && runCatching { verifyArchive(context, complete, release) }.isSuccess) return@withContext complete
        val partial = File(directory, "download.part")
        val connection = connect(release.apkPath)
        try {
            check(directory.usableSpace >= release.bytes * 3 + 20 * 1024 * 1024) { "Недостаточно свободной памяти для обновления." }
            check(connection.responseCode == 200) { "Не удалось скачать APK с сервера Analyst AI." }
            val advertised = connection.contentLengthLong
            check(advertised == -1L || advertised == release.bytes) { "Размер файла не совпадает с описанием." }
            val deadline = System.nanoTime() + 10L * 60 * 1_000_000_000
            connection.inputStream.use { input ->
                partial.outputStream().use { output ->
                    copyUpdateDownload(input, output, release.bytes, release.sha256, progress) {
                        ensureActive()
                        check(System.nanoTime() < deadline) { "Время скачивания истекло. Повторите попытку." }
                    }
                    output.fd.sync()
                }
            }
            verifyArchive(context, partial, release)
            check(!complete.exists() || complete.delete()) { "Не удалось заменить повреждённый APK." }
            check(partial.renameTo(complete)) { "Не удалось сохранить обновление." }
            directory.listFiles()?.filter { it != complete && it.name.endsWith(".apk") }?.forEach(::deleteTemporary)
            complete
        } finally {
            connection.disconnect()
            deleteTemporary(partial)
        }
    }

    fun verifyArchive(context: Context, file: File, release: ReleaseDescriptor) {
        check(file.length() == release.bytes) { "Повреждённый файл обновления." }
        // Bound hashing if a file is unexpectedly replaced/grows after the stat.
        val sink = object : OutputStream() {
            override fun write(value: Int) = Unit
            override fun write(buffer: ByteArray, offset: Int, length: Int) = Unit
        }
        file.inputStream().use { input -> copyVerifiedInstallStream(input, sink, release.bytes, release.sha256) {} }
        val flags = PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong())
        val installed = context.packageManager.getPackageInfo(context.packageName, flags)
        val candidate = context.packageManager.getPackageArchiveInfo(file.absolutePath, flags)
            ?: error("Android не распознал APK.")
        check(candidate.packageName == context.packageName && candidate.packageName == release.packageName)
        check(candidate.longVersionCode == release.versionCode && candidate.longVersionCode > installed.longVersionCode)
        check(candidate.versionName == release.versionName) { "Название версии APK не совпадает с описанием." }
        val application = candidate.applicationInfo ?: error("APK не содержит метаданных приложения.")
        check(application.minSdkVersion == release.minSdk && application.minSdkVersion <= Build.VERSION.SDK_INT)
        check(application.flags and (ApplicationInfo.FLAG_TEST_ONLY or ApplicationInfo.FLAG_DEBUGGABLE) == 0)
        val expected = setOf(release.certificateSha256)
        check(certificates(installed) == expected && certificates(candidate) == expected) {
            "Подпись APK отличается. Установка остановлена; удалять приложение не нужно."
        }
    }

    private fun certificates(info: android.content.pm.PackageInfo): Set<String> = info.signingInfo?.apkContentsSigners
        ?.map { hex(MessageDigest.getInstance("SHA-256").digest(it.toByteArray())) }?.toSet() ?: emptySet()

    private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it) }

    private fun deleteTemporary(file: File) {
        if (file.exists() && !file.delete()) Log.w("AnalystUpdate", "Не удалось удалить временный APK; исходный результат сохранён.")
    }
}
