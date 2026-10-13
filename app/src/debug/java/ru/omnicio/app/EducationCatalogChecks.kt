package ru.omnicio.app

import java.net.URI
import ru.omnicio.app.ui.education.EducationCatalog
import ru.omnicio.app.ui.education.EducationCategory

/** Synthetic debug checks only; they never open a network connection. */
internal fun runEducationCatalogChecks(): Int {
    val lessons = EducationCatalog.lessons
    check(lessons.isNotEmpty())
    check(lessons.map { it.id }.toSet().size == lessons.size)
    check(lessons.map { it.category }.toSet() == EducationCategory.entries.toSet())
    check(lessons.any { it.id == "news-impact" })
    check(lessons.all { it.title.isNotBlank() && it.explanation.length >= 80 })
    check(lessons.all { it.minutes in 3..30 })
    check(lessons.all { it.checkpoints.size >= 3 })
    check(lessons.all { it.sources.isNotEmpty() })

    val allowedHosts = setOf(
        "school.moex.com",
        "www.investor.gov",
        "investor.gov",
        "fincult.info",
        "www.fincult.info",
        "cbr.ru",
        "www.cbr.ru",
    )
    val sources = lessons.flatMap { it.sources }
    check(sources.all { source ->
        val uri = URI(source.url)
        uri.scheme == "https" && uri.host in allowedHosts && uri.userInfo == null && uri.fragment == null
    })
    check(sources.all { it.organization.isNotBlank() && it.title.isNotBlank() })
    return 10
}
