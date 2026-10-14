package ru.omnicio.app

import java.io.ByteArrayInputStream
import java.io.IOException
import java.io.InputStream
import java.nio.charset.CharacterCodingException
import java.util.concurrent.CancellationException
import ru.omnicio.app.data.updates.decodeUpdatePolicy
import ru.omnicio.app.data.updates.readUpdatePolicy

/** No network, real byte streams. Kept in the existing offline debug probe. */
internal fun runPolicyReadChecks(): Int {
    var passed = 0
    fun verify(value: Boolean) { check(value); passed++ }
    val payload = "{\"notes\":\"Проверенная сборка €\"}".toByteArray(Charsets.UTF_8)
    verify(readUpdatePolicy(ByteArrayInputStream(payload), payload.size) {}.contentEquals(payload))
    verify(decodeUpdatePolicy(payload).contains("Проверенная сборка €"))
    verify(readUpdatePolicy(ByteArrayInputStream(byteArrayOf()), 10) {}.isEmpty())
    verify(runCatching { readUpdatePolicy(ByteArrayInputStream(payload), payload.size - 1) {} }.isFailure)
    for (limit in listOf(0, -1, 65_537)) {
        verify(runCatching { readUpdatePolicy(ByteArrayInputStream(payload), limit) {} }.isFailure)
    }
    var consumed = 0
    val endless = object : InputStream() {
        override fun read(): Int { consumed++; return 1 }
    }
    verify(runCatching { readUpdatePolicy(endless, 7) {} }.isFailure)
    verify(consumed == 8)
    var checks = 0
    val stopped = CancellationException("synthetic cancellation")
    val cancelled = runCatching { readUpdatePolicy(ByteArrayInputStream(payload), 100) {
        checks++
        if (checks == 2) throw stopped
    } }.exceptionOrNull()
    verify(cancelled === stopped)
    val broken = IOException("synthetic read failure")
    val failed = object : InputStream() { override fun read(): Int = throw broken }
    verify(runCatching { readUpdatePolicy(failed, 10) {} }.exceptionOrNull() === broken)
    val zero = object : InputStream() {
        override fun read(): Int = 0
        override fun read(bytes: ByteArray, offset: Int, length: Int): Int = 0
    }
    verify(runCatching { readUpdatePolicy(zero, 10) {} }.isFailure)
    for (invalid in listOf(byteArrayOf(0xC3.toByte(), 0x28), byteArrayOf(0xFF.toByte()), byteArrayOf(0xE2.toByte(), 0x82.toByte()))) {
        verify(runCatching { decodeUpdatePolicy(invalid) }.exceptionOrNull() is CharacterCodingException)
    }
    var chunk = 0
    val fragmented = object : ByteArrayInputStream(payload) {
        override fun read(bytes: ByteArray, offset: Int, length: Int): Int {
            chunk++
            return super.read(bytes, offset, minOf(length, 1))
        }
    }
    verify(readUpdatePolicy(fragmented, payload.size) {}.contentEquals(payload))
    verify(chunk == payload.size + 1)
    var eofChecks = 0
    val emptyCancelled = runCatching { readUpdatePolicy(ByteArrayInputStream(byteArrayOf()), 10) {
        eofChecks++
        if (eofChecks == 2) throw stopped
    } }.exceptionOrNull()
    verify(emptyCancelled === stopped)
    return passed
}
