package ru.omnicio.app.data.updates

import org.json.JSONObject

/** Server code identity is separate from the immutable installed Android version. */
data class ServerVersion(val revision: String) {
    val name: String get() = "srv-" + revision.take(12)

    companion object {
        private val revisionPattern = Regex("[a-f0-9]{64}")

        fun parse(metadata: JSONObject?): ServerVersion? {
            if (metadata?.opt("schema_version") != 1) return null
            val revision = metadata.opt("source_revision") as? String ?: return null
            if (!revisionPattern.matches(revision)) return null
            val result = ServerVersion(revision)
            return result.takeIf { metadata.opt("version") == it.name }
        }

        fun label(metadata: JSONObject?, checking: Boolean, unavailable: Boolean): String {
            val version = parse(metadata)
            if (unavailable) return if (version == null) "Версия системы недоступна"
                else "Последняя полученная версия системы: " + version.name + " · нет связи"
            if (checking) return if (version == null) "Проверяем версию системы…"
                else "Версия системы: " + version.name + " · проверяем…"
            return version?.let { "Версия системы: " + it.name } ?: "Сервер не сообщил версию системы"
        }
    }
}
