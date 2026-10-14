package ru.omnicio.app.data.updates

import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest

/** Reverify the bytes actually staged into PackageInstaller, not just a prior path read. */
internal fun copyVerifiedInstallStream(
    input: InputStream,
    output: OutputStream,
    expectedBytes: Long,
    expectedSha256: String,
    checkCancellation: () -> Unit,
): Long {
    require(expectedBytes in 1..(256L * 1024 * 1024)) { "Некорректный размер APK." }
    require(expectedSha256.matches(Regex("[0-9a-f]{64}"))) { "Некорректная контрольная сумма APK." }
    val digest = MessageDigest.getInstance("SHA-256")
    val buffer = ByteArray(64 * 1024)
    var received = 0L
    while (true) {
        checkCancellation()
        val count = input.read(buffer)
        if (count < 0) break
        if (count == 0) throw IOException("Чтение APK остановилось. Повторите обновление.")
        checkCancellation()
        received += count
        check(received <= expectedBytes) { "APK изменился после проверки. Установка остановлена." }
        digest.update(buffer, 0, count)
        output.write(buffer, 0, count)
    }
    check(received == expectedBytes) { "APK скопирован не полностью. Установка остановлена." }
    val actual = digest.digest().joinToString("") { "%02x".format(it) }
    check(actual == expectedSha256) { "APK изменился после проверки. Установка остановлена." }
    checkCancellation()
    // Caller owns/ closes the streams, fsyncs the session, then commits it.
    return received
}
