package ru.omnicio.app.data.updates

import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/** Reads at most limit + one detection byte, checking cancellation between reads.
 * A drip-fed body must not hide inside one large readNBytes call.
 */
internal fun readUpdatePolicy(input: InputStream, limit: Int, checkpoint: () -> Unit): ByteArray {
    require(limit in 1..65_536)
    val output = ByteArrayOutputStream(minOf(limit, 1024))
    val buffer = ByteArray(minOf(limit + 1, 1024))
    while (true) {
        checkpoint()
        val count = input.read(buffer, 0, minOf(buffer.size, limit - output.size() + 1))
        checkpoint()
        if (count == -1) return output.toByteArray()
        check(count > 0) { "Сервер вернул неполное описание обновления." }
        check(count <= limit - output.size()) { "Описание обновления превышает допустимый размер." }
        output.write(buffer, 0, count)
    }
}

internal fun decodeUpdatePolicy(bytes: ByteArray): String = Charsets.UTF_8.newDecoder()
    .onMalformedInput(CodingErrorAction.REPORT)
    .onUnmappableCharacter(CodingErrorAction.REPORT)
    .decode(ByteBuffer.wrap(bytes)).toString()

/** The sibling disconnects a blocking HTTPS operation on timeout OR cancellation.
 * withTimeoutOrNull handles only its own deadline; outer cancellation propagates.
 * Closing may depend on the platform. This is not a hard real-time OS guarantee.
 */
internal suspend fun <T : Any> withTimedUpdateCall(
    timeoutMillis: Long,
    disconnect: () -> Unit,
    read: suspend () -> T,
): T {
    require(timeoutMillis > 0)
    val result = withTimeoutOrNull(timeoutMillis) {
        coroutineScope {
            val closer = launch(Dispatchers.IO, start = CoroutineStart.UNDISPATCHED) {
                try { awaitCancellation() } finally { disconnect() }
            }
            try { read() } finally { closer.cancel() }
        }
    }
    return result ?: error("Время проверки обновления истекло. Повторите попытку.")
}
