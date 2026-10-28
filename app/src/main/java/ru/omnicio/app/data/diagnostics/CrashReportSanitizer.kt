package ru.omnicio.app.data.diagnostics

import java.util.IdentityHashMap

enum class DiagnosticStage(val wire: String) {
    PROCESS_START("process_start"), BOOTSTRAP("bootstrap"), LOGIN("login"),
    WORKSPACE("workspace"), SETTINGS("settings"), BACKGROUND("background"),
    UNKNOWN("unknown")
}

internal data class DiagnosticFrame(val className: String, val method: String, val line: Int)
internal data class DiagnosticProcessState(val version: Int?, val stage: DiagnosticStage)

/** No exception message, file path, thread name, or arbitrary process description. */
internal object CrashReportSanitizer {
    private val className = Regex("ru\\.omnicio\\.app\\.[A-Za-z_$][A-Za-z0-9_.$]{0,135}")
    private val methodName = Regex("(?:[A-Za-z_$][A-Za-z0-9_$-]{0,95}|<init>|<clinit>)")
    private val statePattern = Regex("AA1\\|([1-9][0-9]{0,9})\\|([a-z_]{1,24})")

    private fun causes(error: Throwable): List<Throwable> {
        val result = ArrayList<Throwable>(4)
        val seen = IdentityHashMap<Throwable, Boolean>()
        var next: Throwable? = error
        repeat(4) {
            val current = next
            if (current != null && seen.put(current, true) == null) {
                result.add(current)
                next = current.cause
            } else next = null
        }
        return result
    }

    fun exceptionCode(error: Throwable): String = when (causes(error).lastOrNull() ?: error) {
        is SecurityException -> "security"
        is IllegalArgumentException -> "argument"
        is IllegalStateException -> "state"
        is NullPointerException -> "null"
        is IndexOutOfBoundsException -> "bounds"
        is OutOfMemoryError -> "memory"
        is StackOverflowError -> "stack"
        is LinkageError -> "linkage"
        else -> "other"
    }

    fun frames(error: Throwable): List<DiagnosticFrame> {
        val result = LinkedHashSet<DiagnosticFrame>()
        for (cause in causes(error)) {
            for (frame in cause.stackTrace.take(64)) {
                if (className.matches(frame.className) && methodName.matches(frame.methodName)
                    && frame.lineNumber in -2..10_000_000) {
                    result.add(DiagnosticFrame(frame.className, frame.methodName, frame.lineNumber))
                    if (result.size == 8) return result.toList()
                }
            }
        }
        // Release obfuscation can remove this prefix. An empty list is honest;
        // never invent frames or transmit an unrestricted stack string instead.
        return result.toList()
    }

    fun encodeState(version: Int, stage: DiagnosticStage): ByteArray {
        require(version > 0)
        return ("AA1|" + version + "|" + stage.wire).toByteArray(Charsets.US_ASCII)
    }

    fun decodeState(bytes: ByteArray?): DiagnosticProcessState {
        val unknown = DiagnosticProcessState(null, DiagnosticStage.UNKNOWN)
        if (bytes == null || bytes.size > 128) return unknown
        val match = statePattern.matchEntire(bytes.toString(Charsets.US_ASCII)) ?: return unknown
        val version = match.groupValues[1].toIntOrNull()?.takeIf { it > 0 } ?: return unknown
        val stage = DiagnosticStage.entries.firstOrNull { it.wire == match.groupValues[2] } ?: return unknown
        return DiagnosticProcessState(version, stage)
    }
}
