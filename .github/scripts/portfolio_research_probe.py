"""Search, comparison and dossier acceptance through actual production controls."""
from datetime import timedelta
from native_input_evidence import active_window_id, native_input_ready
from native_window_evidence import wait_for_new_app_window

DOSSIER_SUFFIX = '/dossier'
INSTRUMENTS_PATH = '/workspace/instruments/'
BACK_LABEL = 'Назад'


ACCOUNT_A = "synthetic-account-a"
ACCOUNT_B = "synthetic-account-b"
SHARE_A = "synthetic-share-a"
SHARE_B = "synthetic-share-b"
EVENT = "event:synthetic-reviewed-event"
PRIMARY_URL = "https://example.invalid/synthetic/synthetic-primary"
REPORT_URL = "https://example.invalid/synthetic/report-document"
AREA = "workspace-content"


def _context_risks(case):
    from business_ui_probe import labels
    p = case.probe
    original_window = active_window_id(p.tree())
    p.tap_visible("Действия с бумагой")
    wait_for_new_app_window(p, original_window, "SYN-A", AREA)
    original_window = active_window_id(p.tree())
    p.tap_resource("instrument-context-risks", AREA)
    wait_for_new_app_window(p, original_window, "SYN-A", AREA)
    p.reveal("Риски этой бумаги", AREA)
    p.reveal("СИНТЕТИЧЕСКАЯ концентрация выбранной бумаги", AREA)
    p.reveal("42.4242%", AREA)
    p.reveal("Лимит превышен", AREA)
    p.reveal("Кредитное качество", AREA)
    p.tap("Изменения риска этой бумаги", AREA)
    p.reveal("СИНТЕТИЧЕСКОЕ изменение риска выбранной бумаги", AREA)
    p.reveal("Риски этой бумаги", AREA, direction="start")
    reader = getattr(p.read_tree, "__self__", None)
    for _ in range(24):
        visible = [label for node in p.tree().iter("node") if node.get("visible-to-user") == "true" for label in labels(node)]
        if any("другой бумаги" in label for label in visible):
            raise AssertionError("The contextual risk panel mixed a different instrument into the selected UID")
        if not reader.scroll_list(AREA, "end"):
            break
    else:
        raise AssertionError("The bounded contextual risk panel could not be checked to its actual end")
    original_window = active_window_id(p.tree())
    p.tap("Назад к действиям", AREA)
    wait_for_new_app_window(p, original_window, "SYN-A", AREA)
    p.tap_resource("instrument-context-events", AREA)
    case.call("/workspace/risks", {"currency": "RUB"})
    case.call(INSTRUMENTS_PATH + SHARE_A + DOSSIER_SUFFIX, {})


def _rating_history(case):
    p = case.probe
    p.tap("Как менялся рейтинг", AREA)
    observed = []
    for kind, ago, grade, subject, status in (("issue", 6, "TEST-ISSUE", SHARE_A, "withdrawn"),
                                             ("issuer", 4, "TEST-ISSUER", "synthetic-issuer", "active")):
        resource = "dossier-rating-history-synthetic-rating-" + kind + "-history"
        moment = (case.day - timedelta(days=ago)).strftime("%d.%m.%Y") + " 13:00"
        for text in (moment, "СИНТЕТИЧЕСКОЕ историческое агентство · " + grade,
                     "СИНТЕТИЧЕСКАЯ историческая шкала", "Выпуск" if kind == "issue" else "Эмитент", subject, status):
            case.record_text(resource, text)
        case.record_fold(resource, "Публикация и актуальность рейтинга", expanded=True)
        case.record_text(resource, "Публикация: " + moment)
        case.record_text(resource, "https://example.invalid/synthetic/synthetic-rating-" + kind + "-history")
        observed.append({"resource": resource, "published_at_moscow": moment, "grade": grade,
                         "subject_kind": kind, "subject_id": subject, "status": status})
        case.record_fold(resource, "Публикация и актуальность рейтинга", expanded=False, direction="start")
    case.extra["rating_history"] = observed
    p.tap("Как менялся рейтинг", AREA, direction="start")


def _metric_conflicts(case):
    p = case.probe
    p.reveal("СИНТЕТИЧЕСКОЕ расхождение периодов", AREA)
    observed = []
    for index, value, currency, period in ((0, "12.5", "RUB", "2026-06-30T00:00:00Z"),
                                          (1, "8.25", "USD", "2025-06-30T00:00:00Z")):
        resource = "dossier-conflict-observation-" + str(index)
        for text in (period, currency, "СИНТЕТИЧЕСКАЯ прибыль из конфликтующей записи", value,
                     "СИНТЕТИЧЕСКАЯ неизвестная выручка", "Не получено",
                     "Источник обозначает нулём отсутствие данных. Числовая оценка не подставляется."):
            case.record_text(resource, text)
        observed.append({"resource": resource, "value": value, "currency": currency, "period": period,
                         "revenue": "missing; explicit source sentinel"})
    p.reveal("Наблюдения относятся к разным периодам или валютам.", AREA)
    case.extra["conflicting_observations"] = observed


def exercise_discovery(case):
    from portfolio_chart_probe import month_before
    p = case.probe
    case.call("/workspace", {"currency": "RUB"})
    case.call("/analysis/research", {})
    p.find("Найти и исследовать")
    p.tap("Активы", "profile-tabs")
    case.search("SYN")
    for uid in (SHARE_A, SHARE_B):
        p.tap_resource("discovery-compare-" + ACCOUNT_A + ":" + uid, AREA)
    p.tap_visible("Сравнить (2/3)")
    p.find("Сравнение")
    p.reveal("SYN-A · SYN-B", AREA)
    p.reveal("Цены представлены в одной валюте; сравнивается стоимость единицы инструмента, не доходность за период.", AREA)
    p.tap("Одинаковый период по реальным котировкам", AREA)
    case.prefix("Общие закрытия: ")
    p.reveal("Это изменение цены закрытия. Выплаты, комиссии, налоги и индивидуальные сделки не включены.", AREA)
    case.capture("common-period")
    p.reveal("Количество", AREA)
    p.reveal("2", AREA)
    p.reveal("3", AREA)
    case.capture("comparison")
    p.tap_visible(BACK_LABEL)
    case.observed()  # The source transcript is behind a modal until it closes.
    for uid in (SHARE_A, SHARE_B):
        case.call(INSTRUMENTS_PATH + uid + "/candles",
                  {"start": str(month_before(case.day)), "end": str(case.day), "interval": "day"})
    p.tap_visible("Снять выбор")

    p.tap("Выплаты", "profile-tabs")
    case.search("PAYOUT")
    p.reveal("СИНТЕТИЧЕСКАЯ выплата PAYOUT", AREA)
    p.reveal("Право и количество на дату реестра не подтверждены.", AREA)
    p.tap("Исследования", "profile-tabs")
    case.search("ARCHIVE")
    p.tap_resource("discovery-archive-synthetic-saved-research", AREA)
    p.find("Сохранённое")
    p.reveal("СИНТЕТИЧЕСКИЙ архив ARCHIVE", AREA)
    p.reveal("Сохранённый снимок", AREA)
    p.reveal(f"{case.history_start} — {case.history_end}", AREA)
    p.reveal("СИНТЕТИЧЕСКАЯ заметка: проверить исходный период", AREA)
    case.capture("archive")
    p.tap_visible(BACK_LABEL)  # Selected archive -> archive list.
    p.reveal("Название, заметка или источник", AREA)
    p.tap_visible(BACK_LABEL)  # Archive list -> the actual search screen.
    p.find("Найти и исследовать")
    case.search("RESEARCH")
    original_window = active_window_id(p.tree())
    p.tap_resource("discovery-research-" + SHARE_A, AREA)
    wait_for_new_app_window(p, original_window, "Закрыть разбор", AREA)
    p.reveal("Показана одна выбранная карточка. Общие выводы относятся к исходному анализу.", AREA)
    p.reveal("СИНТЕТИЧЕСКОЕ исследование RESEARCH", AREA)
    p.tap("Закрыть разбор", AREA, direction="start")
    case.observed()

    p.tap("Наблюдение", "profile-tabs")
    case.search(SHARE_A)
    p.reveal("СИНТЕТИЧЕСКАЯ причина: изучить отчётность", AREA)
    original_window = active_window_id(p.tree())
    p.tap("Открыть бумагу на всех счетах", AREA)
    wait_for_new_app_window(p, original_window, "Закрыть досье", AREA)
    p.reveal("Эта бумага на всех счетах", AREA)
    p.reveal("СИНТЕТИЧЕСКИЙ счёт A", AREA)
    p.reveal("СИНТЕТИЧЕСКИЙ счёт B", AREA)
    case.capture("watch-dossier")
    p.tap("Закрыть досье", AREA, direction="start")
    case.call(INSTRUMENTS_PATH + SHARE_A + DOSSIER_SUFFIX, {})
    return ["typed-global-search", "comparison-exact-account-and-distinct-uids", "two-instruments-exact-common-quote-period",
            "payout-eligibility-unknown", "encrypted-archive-date-note",
            "single-research-selection", "watch-reason-and-all-accounts"]


def _reports(case):
    p = case.probe
    p.reveal("Календарь отчётности", AREA)
    p.reveal("Все даты", AREA)
    p.reveal_resource("dossier-tabs", AREA, direction="start", for_capture=True, minimum_size=(48, 48))
    p.tap("Объявлены", "dossier-tabs")
    p.reveal("СИНТЕТИЧЕСКИЙ объявленный отчёт", AREA)
    p.reveal("Объявленная дата прошла; подтверждение публикации ещё не получено.", AREA)
    case.capture("scheduled-report")
    p.reveal("Календарь отчётности", AREA, direction="start")
    p.reveal_resource("dossier-tabs", AREA, for_capture=True, minimum_size=(48, 48))
    p.tap("Опубликованы", "dossier-tabs")
    p.reveal("СИНТЕТИЧЕСКИЙ опубликованный документ", AREA)
    p.reveal("Опубликован: есть проверенный источник документа", AREA)
    p.reveal("2026-01-01 — 2026-06-30", AREA)
    p.tap("Проверенная публикация документа", AREA)
    p.reveal(REPORT_URL, AREA)
    p.tap("Открыть источник", AREA)
    case.expect(lambda value: value["opened_sources"] == [REPORT_URL],
                "The report opened a different publication than its verified document")
    case.capture("published-report")


def _news(case):
    p = case.probe
    p.reveal_resource("dossier-news-" + EVENT, AREA)
    p.reveal("Первый СИНТЕТИЧЕСКИЙ подтверждённый факт", AREA)
    p.reveal("Принадлежность публикаций одному событию проверена по источникам.", AREA)
    p.tap("Публикации и их роли (2)", AREA)
    p.reveal("Первичный источник: проверенная связь", AREA)
    p.reveal("Републикация: роль проверена", AREA)
    p.tap("Открыть проверенный первичный источник", AREA)
    case.expect(lambda value: value["opened_sources"] == [REPORT_URL, PRIMARY_URL],
                "News opened a different publication or an unverified source")
    case.capture("primary-source")
    p.reveal_resource("dossier-news-news:synthetic-independent-news", AREA)
    p.reveal("Другой СИНТЕТИЧЕСКИЙ неподтверждённый текст", AREA)
    p.reveal("Отдельная публикация. Одинаковые заголовки не объединяют события.", AREA)
    p.reveal("Первичный источник не подтверждён. Ссылка брокера и ранняя дата публикации его не заменяют.", AREA)


def _exact_holding(case):
    p = case.probe
    original_window = active_window_id(p.tree())
    p.tap_resource("dossier-fact-news-" + EVENT, AREA, direction="start")
    wait_for_new_app_window(p, original_window, "Контекст факта", AREA)
    p.reveal("Контекст факта", AREA)
    p.reveal("Первый СИНТЕТИЧЕСКИЙ подтверждённый факт", AREA)
    p.tap("Перейти к компании", AREA)
    p.reveal("СИНТЕТИЧЕСКИЙ проверенный эмитент", AREA, direction="start")
    p.reveal("synthetic-issuer", AREA)
    p.tap("Мои позиции в этой бумаге", AREA)
    p.tap_resource("dossier-holding-" + ACCOUNT_B, AREA)
    case.destination(account=ACCOUNT_B, query=SHARE_A)
    p.find("СИНТЕТИЧЕСКАЯ компания")
    p.find("SYN-A")
    p.find("СИНТЕТИЧЕСКИЙ счёт B")
    case.capture("selected-holding")


def _event_draft(case):
    p = case.probe
    p.tap("Досье", "profile-tabs")
    case.call(INSTRUMENTS_PATH + SHARE_A + DOSSIER_SUFFIX, {})
    # The selected holding opens a new position. Traverse its long dossier by
    # visible sections before locating the action in the exact event record.
    for heading in ("Эта бумага на всех счетах", "Паспорт рейтинга",
                    "Показатели компании", "Календарь отчётности", "События и новости"):
        p.reveal(heading, AREA, max_swipes=20)
    case.record_text("dossier-news-" + EVENT, "Факт → компания → моя позиция")
    p.tap_resource("dossier-impact-" + EVENT, AREA)
    p.find("Ассистент")
    expected = {"mode": "instrument", "instrument_uid": SHARE_A, "account_id": None,
                "start": None, "end": None, "event_id": EVENT, "title": "СИНТЕТИЧЕСКАЯ публикация"}
    case.expect(lambda value: value["current_page"] == "assistant" and value["chat_context"] == expected,
                "The real assistant lost the specific event or instrument context")
    case.call("/workspace/chat/threads", {})
    case.call("/workspace/chat/threads/synthetic-portfolio-thread/messages", {})
    p.tap_resource("assistant-event-question", AREA)
    question = "Как это событие может повлиять на мои позиции?"
    p.tap_visible("Ваш вопрос")
    p.wait_for(lambda: native_input_ready(p.tree(), question), "Event shortcut did not fill the real native draft and show its keyboard")
    p.dismiss_keyboard()
    after = case.observed()
    if any(row["method"] != "GET" for row in after["calls"]):
        raise AssertionError("Opening or filling an event question unexpectedly sent a paid request")
    case.extra["event_draft"] = {"text": question, "context": after["chat_context"], "model_request_count": 0}
    case.capture("event-draft")


def exercise_dossier(case):
    p = case.probe
    _context_risks(case)
    p.reveal("СИНТЕТИЧЕСКОЕ агентство · TEST-A", AREA)
    p.reveal("СИНТЕТИЧЕСКАЯ шкала", AREA)
    p.reveal("Выпуск", AREA)
    p.reveal(SHARE_A, AREA)
    _rating_history(case)
    p.reveal("СИНТЕТИЧЕСКИЙ отсутствующий показатель", AREA)
    p.reveal("Источник обозначает нулём отсутствие данных. Числовая оценка не подставляется.", AREA)
    _metric_conflicts(case)
    _reports(case)
    _news(case)
    _exact_holding(case)
    _event_draft(case)
    return ["context-menu-exact-instrument-risks-and-events", "rating-exact-issue-and-scale",
            "rating-history-source-date-exact-subject", "missing-number-not-zero", "structured-conflict-values-periods-currencies",
            "scheduled-date-not-publication", "verified-report-period-source",
            "primary-versus-republication", "same-headline-independent-event",
            "fact-to-issuer-to-exact-holding", "event-context-opens-production-assistant",
            "suggested-question-remains-unsent"]
