package ru.omnicio.app

import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.*
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.ChronoUnit

internal const val PORTFOLIO_PROBE_TOKEN = "debug-portfolio-fixture-only"
internal const val PORTFOLIO_PROBE_ACCOUNT_A = "synthetic-account-a"
internal const val PORTFOLIO_PROBE_ACCOUNT_B = "synthetic-account-b"
internal const val PORTFOLIO_PROBE_SHARE_A = "synthetic-share-a"
internal const val PORTFOLIO_PROBE_SHARE_B = "synthetic-share-b"
internal const val PORTFOLIO_PROBE_BOND = "synthetic-bond"
internal const val PORTFOLIO_PROBE_UNMAPPED = "synthetic-unmapped"
internal const val PORTFOLIO_PROBE_EVENT = "event:synthetic-reviewed-event"
internal const val PORTFOLIO_PROBE_THREAD = "synthetic-portfolio-thread"

/** Deliberately synthetic records, shared by the bounded production-screen acceptance cases. */
internal class PortfolioProbeData(val day: LocalDate = LocalDate.now(ZoneId.of("Europe/Moscow"))) {
    val asOf: String = "${day.minusDays(1)}T20:00:00Z"
    val historyStart: String = day.minusDays(14).toString()
    val historyEnd: String = day.minusDays(1).toString()
    val historyInstant: String = "${day.minusDays(4)}T10:00:00Z"

    fun obj(vararg values: Pair<String, Any?>): JSONObject = JSONObject().apply {
        values.forEach { (key, value) -> put(key, value ?: JSONObject.NULL) }
    }
    private fun array(vararg values: Any?) = JSONArray(values.toList())
    private fun money(amount: String) = obj("amount" to amount, "currency" to "RUB")
    private fun apiMoney(amount: Long) = obj("value" to obj("units" to amount.toString(), "nano" to 0), "currency" to "RUB")
    private fun section(data: JSONObject, state: String = "available", reason: String? = null) =
        obj("state" to state, "data" to data, "reason" to reason, "as_of" to asOf, "sources" to array(source("synthetic-broker-source")))

    fun source(id: String, url: String? = null) = obj("id" to id, "provider" to "СИНТЕТИЧЕСКИЙ источник · $id",
        "method" to "debug-only production UI fixture", "subject_id" to PORTFOLIO_PROBE_SHARE_A,
        "observed_at" to asOf, "published_at" to asOf, "expires_at" to null,
        "unit" to "source record", "currency" to null, "url" to url)

    fun snapshot(): PortfolioSnapshot {
        fun m(amount: Long) = MoneyAmount(ApiDecimal(amount, 0), "RUB")
        fun position(id: String, title: String, ticker: String, quantity: Long, amount: Long, type: String = "share") =
            PortfolioPosition(id, title, ticker, ApiDecimal(quantity, 0), m(amount), null, currentPrice = m(1000),
                instrumentType = type, sector = "СИНТЕТИЧЕСКАЯ отрасль", company = "СИНТЕТИЧЕСКАЯ компания")
        val first = listOf(
            position(PORTFOLIO_PROBE_SHARE_A, "СИНТЕТИЧЕСКАЯ компания", "SYN-A", 2, 2000),
            position(PORTFOLIO_PROBE_SHARE_B, "СИНТЕТИЧЕСКАЯ компания", "SYN-B", 3, 3000),
            position(PORTFOLIO_PROBE_BOND, "СИНТЕТИЧЕСКАЯ облигация", "SYN-BOND", 4, 4000, "bond"),
            position("synthetic-cash", "СИНТЕТИЧЕСКИЙ остаток", "RUB", 1000, 1000, "cash"),
        )
        val second = listOf(
            position(PORTFOLIO_PROBE_SHARE_A, "СИНТЕТИЧЕСКАЯ компания", "SYN-A", 5, 5000),
            position(PORTFOLIO_PROBE_UNMAPPED, "СИНТЕТИЧЕСКАЯ бумага без координат", "SYN-ZZ", 1, 1500),
        )
        return PortfolioSnapshot(m(16500), null, null, listOf(
            PortfolioAccount(PORTFOLIO_PROBE_ACCOUNT_A, "СИНТЕТИЧЕСКИЙ счёт A", m(10000), null, first),
            PortfolioAccount(PORTFOLIO_PROBE_ACCOUNT_B, "СИНТЕТИЧЕСКИЙ счёт B", m(6500), null, second),
        ), emptyList(), asOf)
    }

    fun workspace(): JSONObject {
        fun country(id: String, title: String, amount: String, vararg ids: String) = obj("id" to id, "label" to title,
            "value" to money(amount), "share_percent" to null, "instrument_uids" to JSONArray(ids.toList()),
            "source_ids" to array("synthetic-broker-source"))
        val countries = array(country("RU", "СИНТЕТИЧЕСКАЯ Россия", "7000", PORTFOLIO_PROBE_SHARE_A),
            country("US", "СИНТЕТИЧЕСКИЕ США", "3000", PORTFOLIO_PROBE_SHARE_B),
            country("SYNTHETIC_UNMAPPED", "СИНТЕТИЧЕСКАЯ страна без координат", "1500", PORTFOLIO_PROBE_UNMAPPED))
        val payout = obj("id" to "synthetic-payout", "instrument_uid" to PORTFOLIO_PROBE_BOND,
            "account_id" to PORTFOLIO_PROBE_ACCOUNT_A, "title" to "СИНТЕТИЧЕСКАЯ выплата PAYOUT",
            "kind" to "coupon", "date" to day.plusDays(4).toString(), "status" to "expected", "amount" to money("40"),
            "per_unit" to money("10"), "eligibility_unknown" to true, "source_ids" to array("synthetic-broker-source"))
        return obj("schema_version" to 1, "as_of" to asOf, "currency" to "RUB",
            "sources" to array(source("synthetic-broker-source"), source("synthetic-event-source"), source("synthetic-risk-source")),
            "sections" to obj("payouts" to section(obj("items" to array(payout), "complete" to true)),
                "events" to section(obj("items" to array(event()))),
                "exposures" to section(obj("axes" to array(obj("id" to "country", "label" to "Страна основного риска",
                    "complete" to false, "unknown_count" to 2, "items" to countries))), "partial", "СИНТЕТИЧЕСКИЕ связи получены не для всех позиций.")))
    }

    fun event() = obj("id" to PORTFOLIO_PROBE_EVENT, "kind" to "news", "title" to "СИНТЕТИЧЕСКОЕ событие",
        "summary" to "СИНТЕТИЧЕСКИЙ подтверждённый факт", "occurred_at" to historyInstant,
        "instrument_uids" to array(PORTFOLIO_PROBE_SHARE_A), "source_ids" to array("synthetic-event-source"), "relationship" to "verified")

    fun risks(): JSONObject {
        fun concentration(id: String, uid: String, title: String, amount: String, share: String, breached: Boolean) = obj(
            "direction" to "position", "id" to id, "label" to title, "value" to money(amount), "share_percent" to share,
            "limit_percent" to "30", "breached" to breached, "instrument_uids" to array(uid), "source_ids" to array("synthetic-risk-source"))
        fun riskEvent(id: String, uid: String, title: String) = obj("id" to id, "kind" to "risk_limit_breached", "title" to title,
            "occurred_at" to asOf, "instrument_uids" to array(uid), "source_ids" to array("synthetic-risk-source"),
            "sources" to array(source("synthetic-risk-source")))
        return obj("snapshot_id" to "synthetic-risk-snapshot", "as_of" to asOf, "strategy_version" to 1,
            "coverage_is_not_probability_of_loss" to true,
            "coverage" to array(obj("direction" to "ratings", "state" to "partial", "known_positions" to 3,
                "total_positions" to 5, "not_applicable_positions" to 1, "missing_instrument_uids" to array(PORTFOLIO_PROBE_SHARE_A),
                "as_of" to asOf, "age_seconds" to null, "basis" to "СИНТЕТИЧЕСКАЯ неполная проверка источников")),
            "concentrations" to array(
                concentration("synthetic-selected-risk", PORTFOLIO_PROBE_SHARE_A, "СИНТЕТИЧЕСКАЯ концентрация выбранной бумаги", "7000", "42.4242", true),
                concentration("synthetic-unrelated-risk", PORTFOLIO_PROBE_SHARE_B, "СИНТЕТИЧЕСКАЯ концентрация другой бумаги", "3000", "18.1818", false)),
            "events" to array(
                riskEvent("synthetic-selected-risk-event", PORTFOLIO_PROBE_SHARE_A, "СИНТЕТИЧЕСКОЕ изменение риска выбранной бумаги"),
                riskEvent("synthetic-unrelated-risk-event", PORTFOLIO_PROBE_SHARE_B, "СИНТЕТИЧЕСКОЕ изменение риска другой бумаги")))
    }

    fun dossier(uid: String): JSONObject {
        val positions = snapshot().accounts.flatMap { account -> account.positions.filter { it.id == uid }.map { account to it } }
        val sample = positions.first().second
        val holdings = JSONArray(positions.map { (account, position) -> obj("account_id" to account.id,
            "account_name" to account.name, "quantity" to position.quantity?.toBigDecimal()?.toPlainString(),
            "value" to position.currentValue?.let { money(it.value.toBigDecimal().toPlainString()) }, "blocked" to false) })
        val rating = obj("agency" to "СИНТЕТИЧЕСКОЕ агентство", "scale" to "СИНТЕТИЧЕСКАЯ шкала",
            "grade" to "TEST-A", "subject_kind" to "issue", "subject_id" to uid,
            "status" to "active", "outlook" to "СИНТЕТИЧЕСКИЙ прогноз", "source" to source("synthetic-rating-source"))
        val ratingHistory = array(
            obj("agency" to "СИНТЕТИЧЕСКОЕ историческое агентство", "scale" to "СИНТЕТИЧЕСКАЯ историческая шкала",
                "grade" to "TEST-ISSUE", "subject_kind" to "issue", "subject_id" to uid, "status" to "withdrawn",
                "outlook" to "СИНТЕТИЧЕСКИЙ прошлый прогноз", "source" to reviewedRatingSource("synthetic-rating-issue-history", 6)),
            obj("agency" to "СИНТЕТИЧЕСКОЕ историческое агентство", "scale" to "СИНТЕТИЧЕСКАЯ историческая шкала",
                "grade" to "TEST-ISSUER", "subject_kind" to "issuer", "subject_id" to "synthetic-issuer", "status" to "active",
                "outlook" to "СИНТЕТИЧЕСКИЙ прогноз эмитента", "source" to reviewedRatingSource("synthetic-rating-issuer-history", 4)),
        )
        val metrics = array(obj("id" to "synthetic-margin", "label" to "СИНТЕТИЧЕСКАЯ маржа", "value" to "12.5", "unit" to "%",
            "currency" to null, "period" to "2026-Q2", "source_ids" to array("synthetic-metric-source")),
            obj("id" to "synthetic-missing", "label" to "СИНТЕТИЧЕСКИЙ отсутствующий показатель", "value" to null,
                "unit" to "RUB", "period" to "2026-Q2", "missing_reason" to "broker_zero_means_unavailable", "source_ids" to array("synthetic-metric-source")))
        val conflicts = array(obj("label" to "СИНТЕТИЧЕСКОЕ расхождение периодов", "basis_matches" to false,
            "observations" to array(conflictObservation("12.5", "RUB", "2026-06-30T00:00:00Z"),
                conflictObservation("8.25", "USD", "2025-06-30T00:00:00Z")),
            "reason" to "different_period_or_currency", "source_ids" to array("synthetic-metric-source")))
        return obj("schema_version" to 1, "instrument_uid" to uid, "as_of" to asOf,
            "sources" to array(source("synthetic-broker-source"), source("synthetic-metric-source"), source("synthetic-other-source"),
                source("synthetic-news-review"), source("synthetic-event-source")),
            "sections" to obj(
                "instrument" to section(obj("uid" to uid, "title" to sample.title, "ticker" to sample.ticker,
                    "instrument_type" to sample.instrumentType, "currency" to "RUB", "issuer_id" to "synthetic-issuer",
                    "issuer_name" to "СИНТЕТИЧЕСКИЙ проверенный эмитент", "issuer_source" to source("synthetic-broker-source"))),
                "holdings" to section(obj("items" to holdings)),
                "ratings" to section(obj("items" to array(rating), "history" to ratingHistory, "warnings" to JSONArray())),
                "metrics" to section(obj("items" to metrics, "conflicts" to conflicts), "partial", "Один СИНТЕТИЧЕСКИЙ показатель не получен."),
                "reports" to section(obj("items" to reports())),
                "news" to section(obj("items" to news(uid))),
                "events" to section(obj("items" to JSONArray()))))
    }

    private fun reviewedRatingSource(id: String, daysAgo: Long) = obj("id" to id,
        "url" to "https://example.invalid/synthetic/$id", "published_at" to "${day.minusDays(daysAgo)}T10:00:00Z",
        "checked_at" to asOf, "expires_at" to "${day.plusDays(1)}T20:00:00Z", "review_id" to "synthetic-review-$id")

    /** Mirrors volume_market._fundamental_conflict: structured value plus typed metric records. */
    private fun conflictObservation(value: String, currency: String, period: String) = obj(
        "source_id" to "synthetic-metric-source", "period" to period, "currency" to currency,
        "value" to obj("currency" to currency, "fiscalPeriodEndDate" to period, "netIncomeTtm" to value, "revenueTtm" to null),
        "metrics" to array(
            obj("id" to "netIncomeTtm", "label" to "СИНТЕТИЧЕСКАЯ прибыль из конфликтующей записи", "value" to value,
                "unit" to "currency", "currency" to currency, "period" to period, "source_ids" to array("synthetic-metric-source"), "missing_reason" to null),
            obj("id" to "revenueTtm", "label" to "СИНТЕТИЧЕСКАЯ неизвестная выручка", "value" to null,
                "unit" to "currency", "currency" to currency, "period" to period, "source_ids" to array("synthetic-metric-source"),
                "missing_reason" to "broker_zero_means_unavailable")))

    private fun reports() = array(
        obj("id" to "synthetic-scheduled", "title" to "СИНТЕТИЧЕСКИЙ объявленный отчёт", "date" to day.minusDays(3).toString(),
            "status" to "scheduled", "publication_confirmed" to false, "period_year" to day.year, "period_num" to 2,
            "source_ids" to array("synthetic-broker-source")),
        obj("id" to "synthetic-published", "title" to "СИНТЕТИЧЕСКИЙ опубликованный документ", "date" to day.minusDays(2).toString(),
            "status" to "published", "publication_confirmed" to true, "period_start" to "2026-01-01", "period_end" to "2026-06-30",
            "source" to source("synthetic-report-document", "https://example.invalid/synthetic/report-document")),
        obj("id" to "synthetic-undated", "title" to "СИНТЕТИЧЕСКИЙ отчёт без даты", "date" to null,
            "status" to "scheduled", "publication_confirmed" to false, "source_ids" to array("synthetic-broker-source")),
    )

    private fun news(uid: String): JSONArray {
        val primary = source("synthetic-primary", "https://example.invalid/synthetic/synthetic-primary")
        fun publication(id: String, role: String) = obj("provider" to "СИНТЕТИЧЕСКИЙ поставщик · $id",
            "source_id" to id, "broker_news_id" to id, "published_at" to asOf, "publication_role" to role,
            "publication_role_basis" to "СИНТЕТИЧЕСКАЯ проверенная связь", "url" to "https://example.invalid/synthetic/$id",
            "review_source_id" to "synthetic-news-review")
        return array(obj("id" to PORTFOLIO_PROBE_EVENT, "title" to "СИНТЕТИЧЕСКАЯ публикация", "summary" to "Первый СИНТЕТИЧЕСКИЙ подтверждённый факт",
            "published_at" to asOf, "instrument_uids" to array(uid), "relationship" to "verified", "event_identity_verified" to true,
            "deduplication" to "reviewed_event_identity", "sources" to array(publication("synthetic-primary", "primary"), publication("synthetic-repost", "repost")),
            "primary_sources" to array(primary), "evidence_sources" to array(source("synthetic-news-review"))),
            obj("id" to "news:synthetic-independent-news", "title" to "СИНТЕТИЧЕСКАЯ публикация", "summary" to "Другой СИНТЕТИЧЕСКИЙ неподтверждённый текст",
                "published_at" to asOf, "instrument_uids" to array(uid), "relationship" to "broker_link", "event_identity_verified" to false,
                "deduplication" to "broker_news_id", "sources" to array(obj("provider" to "СИНТЕТИЧЕСКИЙ неизвестный поставщик",
                    "source_id" to "synthetic-unreviewed", "broker_news_id" to "synthetic-unreviewed", "published_at" to asOf,
                    "publication_role" to "unknown", "publication_role_basis" to "not_reviewed", "review_source_id" to null)),
                "primary_sources" to JSONArray(), "evidence_sources" to JSONArray()))
    }

    fun candles(uid: String, parameters: Map<String, String>): JSONObject {
        val interval = parameters.getValue("interval")
        val start = LocalDate.parse(parameters.getValue("start")); val end = LocalDate.parse(parameters.getValue("end"))
        val span = ChronoUnit.DAYS.between(start, end).toInt()
        val dates = when (interval) {
            "hour" -> (0 until 40).map { end.atStartOfDay().minusHours(39L - it).toString() + ":00Z" }
            "week" -> (0..span step 7).map { "${start.plusDays(it.toLong())}T10:00:00Z" }
            "month" -> listOf("${start}T10:00:00Z", "${end}T10:00:00Z").distinct()
            else -> (0..span).map { "${start.plusDays(it.toLong())}T10:00:00Z" }
        }
        val percent = uid == PORTFOLIO_PROBE_BOND
        val displayedDates = dates.take(120)
        val rows = displayedDates.mapIndexed { index, time ->
            val price = (if (percent) BigDecimal("98.125000001") else BigDecimal("100.125000001")).add(BigDecimal(index))
            obj("time" to time, "open" to price.toPlainString(), "low" to price.subtract(BigDecimal("0.5")).toPlainString(),
                "high" to price.add(BigDecimal.ONE).toPlainString(), "close" to price.add(BigDecimal("0.25")).toPlainString(),
                "volume_lots" to (100 + index).toString(), "is_complete" to (index < displayedDates.lastIndex), "source_id" to "synthetic-candles-source")
        }
        return obj("schema_version" to 1, "instrument_uid" to uid, "interval" to interval, "start" to start.toString(), "end" to end.toString(),
            "as_of" to asOf, "state" to "partial", "reason" to "Последняя СИНТЕТИЧЕСКАЯ свеча ещё формируется.",
            "unit" to if (percent) "percent_of_nominal" else "quote_currency", "unit_label" to if (percent) "% номинала" else "RUB за инструмент",
            "currency" to if (percent) null else "RUB", "candles" to JSONArray(rows), "sources" to array(source("synthetic-candles-source")),
            "events" to array(event()))
    }

    fun analytics(parameters: Map<String, String>, missingInstant: Boolean): JSONObject {
        val from = parameters["start"]?.let(LocalDate::parse) ?: LocalDate.parse(historyStart)
        val until = parameters["end"]?.let(LocalDate::parse) ?: LocalDate.parse(historyEnd)
        val points = (0..13).map { day.minusDays(14L - it) }.filter { it in from..until && it != day.minusDays(7) }.flatMap { date ->
            if (date == day.minusDays(4)) listOfNotNull(
                if (missingInstant) null else obj("date" to historyInstant, "value" to "101.25"),
                obj("date" to "${date}T18:00:00Z", "value" to "901.75"))
            else listOf(obj("date" to "${date}T18:00:00Z", "value" to when (date) {
                day.minusDays(10) -> "0"; day.minusDays(9) -> "-25.5"
                else -> (16500 - ChronoUnit.DAYS.between(date, day.minusDays(1)) * 100).toString()
            }))
        }
        return obj("asOf" to asOf, "currency" to "RUB", "complete" to true, "historyResolution" to (parameters["history_resolution"] ?: "day"),
            "history" to JSONArray(points), "historyTruncated" to false,
            "summary" to array(obj("category" to "deposits", "amount" to apiMoney(200))))
    }

    fun research() = obj("as_of" to asOf, "state" to "research", "currency" to "RUB",
        "examined_positions" to 1, "total_positions" to 4, "issuer_coverage_count" to 1,
        "analysis_is_complete" to false, "autotrading" to false, "paid_model_calls" to 0, "profile_configured" to false,
        "source_errors" to JSONArray(), "cards" to array(obj("instrument_uid" to PORTFOLIO_PROBE_SHARE_A,
        "name" to "СИНТЕТИЧЕСКОЕ исследование RESEARCH", "ticker" to "SYN-A", "isin" to "SYNTHETIC-ISIN",
        "issuer_id" to "synthetic-issuer", "explanation" to "СИНТЕТИЧЕСКОЕ объяснение для поиска", "action" to "watch")))

    fun tradingCalendar() = obj("schema_version" to 1, "as_of" to asOf, "timezone" to "UTC", "display_timezones" to array("Europe/Moscow", "device_local"),
        "exchanges" to array(obj("exchange" to "SYNTHETIC-EXCHANGE", "days" to array(
            obj("date" to day.toString(), "isTradingDay" to true, "startTime" to "${day}T22:30:00Z", "endTime" to "${day.plusDays(1)}T01:15:00Z"),
            obj("date" to day.plusDays(1).toString(), "isTradingDay" to false),
            obj("date" to day.plusDays(2).toString(), "isTradingDay" to null)))),
        "source" to source("synthetic-calendar-source"), "basis" to "broker_sections_not_guaranteed_instrument_availability")
}
