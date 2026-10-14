package ru.omnicio.app.data.updates

import android.util.JsonReader
import android.util.JsonToken
import java.io.IOException
import java.io.StringReader

private const val INVALID_RELEASE_JSON = "Некорректное описание обновления. Повторите проверку."
private const val MAX_JSON_DEPTH = 16
private const val MAX_JSON_VALUES = 1024

/** Detect duplicate decoded names before a Map can overwrite them. Unknown fields remain extensible. */
internal fun parseReleaseJson(text: String): Map<String, Any?> {
    require(text.length <= UpdateProtocol.MAX_MANIFEST_BYTES) { INVALID_RELEASE_JSON }
    require(text.toByteArray(Charsets.UTF_8).size <= UpdateProtocol.MAX_MANIFEST_BYTES) { INVALID_RELEASE_JSON }
    try {
        return JsonReader(StringReader(text)).use { reader ->
            reader.isLenient = false
            val fields = ReleaseJsonReader(reader).readObject(0)
            require(reader.peek() == JsonToken.END_DOCUMENT) { INVALID_RELEASE_JSON }
            fields
        }
    } catch (error: IOException) {
        throw IllegalArgumentException(INVALID_RELEASE_JSON, error)
    } catch (error: IllegalStateException) {
        throw IllegalArgumentException(INVALID_RELEASE_JSON, error)
    }
}

private class ReleaseJsonReader(private val reader: JsonReader) {
    private var values = 0

    private fun visit(depth: Int) {
        values += 1
        require(depth <= MAX_JSON_DEPTH && values <= MAX_JSON_VALUES) { INVALID_RELEASE_JSON }
    }

    fun readObject(depth: Int): Map<String, Any?> {
        visit(depth)
        reader.beginObject()
        val result = linkedMapOf<String, Any?>()
        while (reader.hasNext()) {
            val name = unicodeText(reader.nextName())
            require(!result.containsKey(name)) { INVALID_RELEASE_JSON }
            result[name] = readValue(depth + 1)
        }
        reader.endObject()
        return result
    }

    private fun readArray(depth: Int): List<Any?> {
        visit(depth)
        reader.beginArray()
        val result = mutableListOf<Any?>()
        while (reader.hasNext()) result.add(readValue(depth + 1))
        reader.endArray()
        return result
    }

    private fun readValue(depth: Int): Any? = when (reader.peek()) {
        JsonToken.BEGIN_OBJECT -> readObject(depth)
        JsonToken.BEGIN_ARRAY -> readArray(depth)
        else -> {
            visit(depth)
            readScalar()
        }
    }

    private fun readScalar(): Any? = when (reader.peek()) {
        JsonToken.STRING -> unicodeText(reader.nextString())
        JsonToken.BOOLEAN -> reader.nextBoolean()
        JsonToken.NULL -> { reader.nextNull(); null }
        JsonToken.NUMBER -> number(reader.nextString())
        else -> error(INVALID_RELEASE_JSON)
    }

    private fun number(raw: String): Number {
        // nextLong() may accept a fractional/exponent token. Preserve wire type
        // so UpdateProtocol can reject 23.0 / 23e0 instead of accepting code 23.
        if (raw.none { it == '.' || it == 'e' || it == 'E' }) {
            return raw.toLongOrNull() ?: error(INVALID_RELEASE_JSON)
        }
        val value = raw.toDoubleOrNull() ?: error(INVALID_RELEASE_JSON)
        require(value.isFinite()) { INVALID_RELEASE_JSON }
        return value
    }

    private fun unicodeText(value: String): String {
        var index = 0
        while (index < value.length) {
            val character = value[index++]
            if (character.isHighSurrogate()) {
                require(index < value.length && value[index].isLowSurrogate()) { INVALID_RELEASE_JSON }
                index += 1
            } else {
                require(!character.isLowSurrogate()) { INVALID_RELEASE_JSON }
            }
        }
        return value
    }
}
