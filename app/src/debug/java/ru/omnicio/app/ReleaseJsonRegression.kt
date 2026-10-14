package ru.omnicio.app

import ru.omnicio.app.data.updates.UpdateProtocol
import ru.omnicio.app.data.updates.parseReleaseJson

/** Runs on the real Android JsonReader in the existing debug fixture; no network or installer. */
internal fun runReleaseJsonChecks(): Int {
    var count = 0
    fun verify(test: () -> Unit) { test(); count += 1 }
    val hash = "a".repeat(64)
    val certificate = "b".repeat(64)
    val valid = """{"schema_version":1,"package_name":"ru.omnicio.app.debug","version_code":24,"minimum_version_code":24,"version_name":"0.6.1-preview","apk_sha256":"$hash","apk_bytes":4000000,"certificate_sha256":"$certificate","min_sdk":33,"published_at":1,"notes":"Обновление","apk_path":"/client/apk/Analyst-AI-24-$hash.apk","version_is_not_attestation":true}"""
    verify { check(UpdateProtocol.parse(parseReleaseJson(valid), 2).versionCode == 24L) }
    verify { check(parseReleaseJson(valid)["version_code"] is Long) }
    verify { check(parseReleaseJson("""{"x":null}""").containsKey("x")) }
    verify { check(parseReleaseJson("""{"x":[{"v":1},{"v":2}]}""")["x"] is List<*>) }
    verify { check(parseReleaseJson("""{"x":"\ud83d\ude00"}""")["x"] == "😀") }
    verify { check(parseReleaseJson("""{"x":9223372036854775807}""")["x"] == Long.MAX_VALUE) }
    verify { check(parseReleaseJson("{}" + " ".repeat(UpdateProtocol.MAX_MANIFEST_BYTES - 2)).isEmpty()) }
    val invalid = listOf(
        """{"version_code":23,"version_code":24}""",
        """{"version_code":24,"version_code":24}""",
        """{"version_code":23,"\u0076ersion_code":24}""",
        """{"x":null,"x":1}""", """{"extra":{"x":1,"x":2}}""",
        "{'x':1}", "{x:1}", """{"x":1,}""", "{}{}",
        """{/*comment*/"x":1}""", "[]", "null", "1", "true", "",
        """{"x":NaN}""", """{"x":Infinity}""", """{"x":1e9999}""",
        """{"x":9223372036854775808}""", """{"x":-9223372036854775809}""",
        """{"x":"\ud800"}""", """{"\udfff":1}""",
        "{" + " ".repeat(UpdateProtocol.MAX_MANIFEST_BYTES) + "}",
        "{\"extra\":" + "[".repeat(16) + "0" + "]".repeat(16) + "}",
        "{\"extra\":[" + List(1024) { "0" }.joinToString(",") + "]}",
    )
    invalid.forEach { raw -> verify { check(runCatching { parseReleaseJson(raw) }.isFailure) } }
    listOf("24.0", "24e0", "\"24\"", "true", "null").forEach { value ->
        val wrongType = valid.replace("\"version_code\":24,", "\"version_code\":$value,")
        verify { check(runCatching { UpdateProtocol.parse(parseReleaseJson(wrongType), 2) }.isFailure) }
    }
    val extended = valid.dropLast(1) + ",\"extra\":{\"future\":[1,true,null]}}"
    verify { check(UpdateProtocol.parse(parseReleaseJson(extended), 2).versionCode == 24L) }
    return count
}
