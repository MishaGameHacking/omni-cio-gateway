package ru.omnicio.app

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest
import java.util.concurrent.CancellationException
import ru.omnicio.app.data.updates.copyVerifiedInstallStream

/** Synthetic bytes only. Passing these does not prove that Android installed an APK. */
internal fun runInstallStreamChecks(): Int {
    val data = "Synthetic stream, not an APK".toByteArray()
    fun digest(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }
    fun attempt(bytes: ByteArray = data, expected: Long = data.size.toLong(), sha: String = digest(data)): Result<Long> =
        runCatching { copyVerifiedInstallStream(bytes.inputStream(), ByteArrayOutputStream(), expected, sha) {} }
    val checks = listOf<() -> Unit>(
        {
            val output = ByteArrayOutputStream()
            check(copyVerifiedInstallStream(data.inputStream(), output, data.size.toLong(), digest(data)) {} == data.size.toLong())
            check(output.toByteArray().contentEquals(data))
        },
        { check(attempt(expected = data.size + 1L).isFailure) },
        { check(attempt(bytes = data + byteArrayOf(1)).isFailure) },
        { check(attempt(bytes = ByteArray(data.size)).isFailure) },
        { check(attempt(expected = 0).isFailure) },
        { check(attempt(expected = -1).isFailure) },
        { check(attempt(expected = 256L * 1024 * 1024 + 1).isFailure) },
        { check(attempt(sha = "invalid").isFailure) },
        {
            val output = ByteArrayOutputStream()
            val cancellation = CancellationException("test cancellation")
            val outcome = runCatching {
                copyVerifiedInstallStream(data.inputStream(), output, data.size.toLong(), digest(data)) { throw cancellation }
            }
            check(outcome.exceptionOrNull() === cancellation && output.size() == 0)
        },
        {
            val large = ByteArray(150_000) { (it % 127).toByte() }
            val output = ByteArrayOutputStream()
            var probes = 0
            val outcome = runCatching {
                copyVerifiedInstallStream(large.inputStream(), output, large.size.toLong(), digest(large)) {
                    if (++probes == 4) throw CancellationException("test cancellation")
                }
            }
            check(outcome.exceptionOrNull() is CancellationException && output.size() == 65_536)
        },
        {
            val failure = IOException("test input failure")
            val input = object : InputStream() { override fun read(): Int = throw failure }
            val outcome = runCatching { copyVerifiedInstallStream(input, ByteArrayOutputStream(), data.size.toLong(), digest(data)) {} }
            check(outcome.exceptionOrNull() === failure)
        },
        {
            val input = object : InputStream() {
                override fun read(): Int = 0
                override fun read(buffer: ByteArray, offset: Int, length: Int): Int = 0
            }
            val outcome = runCatching { copyVerifiedInstallStream(input, ByteArrayOutputStream(), data.size.toLong(), digest(data)) {} }
            check(outcome.exceptionOrNull() is IOException)
        },
        {
            val failure = IOException("test output failure")
            val output = object : OutputStream() { override fun write(value: Int) { throw failure } }
            val outcome = runCatching { copyVerifiedInstallStream(data.inputStream(), output, data.size.toLong(), digest(data)) {} }
            check(outcome.exceptionOrNull() === failure)
        },
        {
            val input = object : ByteArrayInputStream(data) {
                override fun read(buffer: ByteArray, offset: Int, length: Int): Int = super.read(buffer, offset, minOf(3, length))
            }
            val output = ByteArrayOutputStream()
            copyVerifiedInstallStream(input, output, data.size.toLong(), digest(data)) {}
            check(output.toByteArray().contentEquals(data))
        },
        {
            var closed = false
            val input = object : ByteArrayInputStream(data) { override fun close() { closed = true } }
            copyVerifiedInstallStream(input, ByteArrayOutputStream(), data.size.toLong(), digest(data)) {}
            check(!closed)
        },
        { check(attempt(sha = digest(data).uppercase()).isFailure) },
    )
    checks.forEachIndexed { index, test ->
        try { test() } catch (failure: Exception) { throw IllegalStateException("Install stream check ${index + 1} failed", failure) }
    }
    return checks.size
}
