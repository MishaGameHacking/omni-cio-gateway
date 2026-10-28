package ru.omnicio.app.data.diagnostics

import org.junit.Assert.*
import org.junit.Test

class CrashReportSanitizerTest {
    @Test fun exceptionMessageIsNeverReadAndRootCategoryIsBounded() {
        val dangerous = object : RuntimeException() {
            override val message: String get() = error("must not read private message")
        }
        dangerous.stackTrace = arrayOf(StackTraceElement("ru.omnicio.app.MainActivity", "onCreate", "/private/token", 7))
        assertEquals("other", CrashReportSanitizer.exceptionCode(dangerous))
        assertEquals(listOf(DiagnosticFrame("ru.omnicio.app.MainActivity", "onCreate", 7)),
            CrashReportSanitizer.frames(dangerous))
        assertEquals("security", CrashReportSanitizer.exceptionCode(
            IllegalStateException("private outer", SecurityException("private inner"))))
    }

    @Test fun onlyBoundedApplicationSymbolsAreCollected() {
        val failure = RuntimeException("https://example.invalid/?token=private")
        failure.stackTrace = arrayOf(
            StackTraceElement("java.lang.Thread", "run", "Thread.java", 1),
            StackTraceElement("ru.omnicio.app.MainActivity", "https://secret.invalid", "ignored", 1),
            StackTraceElement("ru.omnicio.app.MainActivity", "onCreate", "ignored", -3),
        ) + (0 until 20).map {
            StackTraceElement("ru.omnicio.app.MainActivity", "method" + it, "/private/file", it)
        }
        val safe = CrashReportSanitizer.frames(failure)
        assertEquals(8, safe.size)
        assertEquals("method0", safe.first().method)
        assertEquals("method7", safe.last().method)
        assertFalse(safe.toString().contains("private"))
        assertFalse(safe.toString().contains("https"))
    }

    @Test fun absentAndMalformedHistoricalVersionRemainUnknown() {
        for (raw in listOf(null, byteArrayOf(), ByteArray(129),
            "AA1|2147483648|workspace".toByteArray(),
            "AA1|38|https://example.invalid".toByteArray(),
            "AA1|038|workspace".toByteArray())) {
            val result = CrashReportSanitizer.decodeState(raw)
            assertNull(result.version)
            assertEquals(DiagnosticStage.UNKNOWN, result.stage)
        }
    }

    @Test fun processStateRoundTripDoesNotInventCurrentVersion() {
        val decoded = CrashReportSanitizer.decodeState(
            CrashReportSanitizer.encodeState(37, DiagnosticStage.BOOTSTRAP))
        assertEquals(37, decoded.version)
        assertEquals(DiagnosticStage.BOOTSTRAP, decoded.stage)
        assertTrue(CrashReportSanitizer.encodeState(38, DiagnosticStage.WORKSPACE).size <= 128)
    }

    @Test fun obfuscatedAndForeignFramesAreNotInvented() {
        val failure = RuntimeException()
        failure.stackTrace = arrayOf(StackTraceElement("a.b", "c", "SourceFile", 4))
        assertTrue(CrashReportSanitizer.frames(failure).isEmpty())
    }
}
