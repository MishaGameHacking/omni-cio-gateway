package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.saveable.Saver

/** Only navigation identifiers and filters are retained, never financial objects. */
internal val PortfolioDestinationSaver = Saver<PortfolioDestination?, List<String>>(
    save = { target ->
        target?.let { listOf(it.section.toString(), it.accountId.orEmpty(), it.query,
            it.sector.orEmpty(), it.kind.orEmpty(), it.operationId.orEmpty(), it.operationDate.orEmpty()) }
            ?: emptyList()
    },
    restore = { fields ->
        if (fields.size != 7) null
        else fields[0].toIntOrNull()?.takeIf { it in 0..4 }?.let { section ->
            PortfolioDestination(section, fields[1].takeIf(String::isNotBlank), fields[2],
                fields[3].takeIf(String::isNotBlank), fields[4].takeIf(String::isNotBlank),
                fields[5].takeIf(String::isNotBlank), fields[6].takeIf(String::isNotBlank))
        }
    },
)
