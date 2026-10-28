package ru.omnicio.app.ui.workspace

import java.time.ZoneId
import java.util.Locale

/** A suggestion carries an actual source value, never a generated instrument ID. */
data class WorkspaceSuggestion(val value: String, val label: String, val keywords: String = "")

internal fun matchingSuggestions(options: List<WorkspaceSuggestion>, query: String): List<WorkspaceSuggestion> {
    val tokens = query.trim().lowercase(Locale.ROOT).split(Regex("\\s+")).filter(String::isNotEmpty)
    val unique = options.filter { it.label.isNotBlank() }.distinctBy { it.value }
    if (tokens.isEmpty()) return unique
    return unique.filter { item ->
        val text = (item.label + " " + item.value + " " + item.keywords).lowercase(Locale.ROOT)
        tokens.all(text::contains)
    }.sortedBy { item -> if (item.label.lowercase(Locale.ROOT).startsWith(tokens.first())) 0 else 1 }
}

internal fun notificationZoneSuggestions(deviceZone: String, current: String): List<WorkspaceSuggestion> {
    val cities = mapOf("Europe/Moscow" to "Москва", "Europe/Kaliningrad" to "Калининград",
        "Europe/Samara" to "Самара", "Asia/Yekaterinburg" to "Екатеринбург", "Asia/Omsk" to "Омск",
        "Asia/Krasnoyarsk" to "Красноярск", "Asia/Irkutsk" to "Иркутск", "Asia/Yakutsk" to "Якутск",
        "Asia/Vladivostok" to "Владивосток", "Asia/Magadan" to "Магадан", "Asia/Kamchatka" to "Камчатка")
    val available = ZoneId.getAvailableZoneIds()
    return (listOf(deviceZone, current) + available.sorted()).distinct().filter { it in available }.map { zone ->
        WorkspaceSuggestion(zone, (cities[zone]?.plus(" · ") ?: "") + zone.replace('_', ' '),
            if (zone == deviceZone) "Часовой пояс устройства" else "")
    }
}
