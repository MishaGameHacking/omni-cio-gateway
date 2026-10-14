package ru.omnicio.app.data.updates

import java.io.InputStream
import java.io.OutputStream

/** Stream once, bound bytes, verify the hash; the caller still verifies APK identity/signature. */
internal fun copyUpdateDownload(
    input: InputStream,
    output: OutputStream,
    expectedBytes: Long,
    expectedSha256: String,
    onProgress: (Int) -> Unit,
    checkActive: () -> Unit,
) {
    var received = 0L
    var previous = -1
    val progressOutput = object : OutputStream() {
        override fun write(value: Int) {
            output.write(value)
            report(1)
        }
        override fun write(bytes: ByteArray, offset: Int, count: Int) {
            output.write(bytes, offset, count)
            report(count)
        }
        private fun report(count: Int) {
            received += count
            val percent = (100 * received / expectedBytes).toInt()
            // 100 means verified completion, not simply that all bytes arrived.
            val intermediate = percent.coerceIn(0, 99)
            if (intermediate != previous) { onProgress(intermediate); previous = intermediate }
        }
    }
    copyVerifiedInstallStream(input, progressOutput, expectedBytes, expectedSha256, checkActive)
    checkActive()
    onProgress(100)
}
