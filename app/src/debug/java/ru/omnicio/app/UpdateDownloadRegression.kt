package ru.omnicio.app

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest
import java.util.concurrent.CancellationException
import ru.omnicio.app.data.updates.copyUpdateDownload

internal fun runUpdateDownloadChecks(): Int {
    val payload = ByteArray(150_000) { (it % 251).toByte() }
    val digest = MessageDigest.getInstance("SHA-256").digest(payload).joinToString("") { "%02x".format(it) }
    val progress = mutableListOf<Int>()
    val output = ByteArrayOutputStream()
    copyUpdateDownload(ByteArrayInputStream(payload), output, payload.size.toLong(), digest, { progress.add(it) }) {}
    check(output.toByteArray().contentEquals(payload))
    check(progress.last() == 100 && progress.dropLast(1).all { it in 0..99 })
    check(progress.zipWithNext().all { (a, b) -> a < b })
    var checked = 3
    fun reject(input: InputStream, bytes: Long, sha: String = digest) {
        val updates = mutableListOf<Int>()
        check(runCatching { copyUpdateDownload(input, ByteArrayOutputStream(), bytes, sha, { updates.add(it) }) {} }.isFailure)
        check(100 !in updates)
        checked += 2
    }
    reject(ByteArrayInputStream(payload.copyOf(payload.size - 1)), payload.size.toLong())
    reject(ByteArrayInputStream(payload + byteArrayOf(1)), payload.size.toLong())
    reject(ByteArrayInputStream(payload), payload.size.toLong(), "0".repeat(64))
    reject(object : InputStream() { override fun read() = 0; override fun read(b: ByteArray, off: Int, len: Int) = 0 }, 1)
    val cancelled = runCatching { copyUpdateDownload(ByteArrayInputStream(payload), ByteArrayOutputStream(), payload.size.toLong(), digest, {}) { throw CancellationException("synthetic") } }.exceptionOrNull()
    check(cancelled is CancellationException); checked++
    val failure = java.io.IOException("synthetic disk failure")
    val broken = object : OutputStream() { override fun write(value: Int) { throw failure } }
    val caught = runCatching { copyUpdateDownload(ByteArrayInputStream(payload), broken, payload.size.toLong(), digest, {}) {} }.exceptionOrNull()
    check(caught === failure); checked++
    return checked
}
