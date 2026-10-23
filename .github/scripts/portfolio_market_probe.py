"""Verified geographic labels and explicit UTC/Moscow calendar instants."""
from datetime import timedelta

from portfolio_research_probe import ACCOUNT_B, SHARE_A

AREA = "workspace-content"


def _calendar(case):
    p = case.probe
    zone = p.command("shell", "getprop", "persist.sys.timezone").strip()
    if zone != "Etc/UTC":
        raise AssertionError("Calendar acceptance requires the emulator's actual Etc/UTC timezone")
    # The tabs are below the intro inside the page's vertical list.
    p.reveal_resource("profile-tabs", AREA, direction="end",
                      for_capture=True, minimum_size=(48, 48))
    p.tap("Сессии", "profile-tabs")
    case.call("/workspace/markets/calendar", {})
    p.reveal("SYNTHETIC-EXCHANGE", AREA)
    p.reveal("Торговый день по расписанию", AREA)
    p.reveal("Начало основной сессии", AREA)
    p.reveal("Ваше время · Etc/UTC", AREA)
    case.prefix(case.day.strftime("%d.%m.%Y") + " 22:30 ")
    p.reveal("Москва · Europe/Moscow", AREA)
    tomorrow = case.day + timedelta(days=1)
    case.prefix(tomorrow.strftime("%d.%m.%Y") + " 01:30 ")
    case.capture("session-midnight")
    p.reveal("Конец основной сессии", AREA)
    case.prefix(tomorrow.strftime("%d.%m.%Y") + " 01:15 ")
    case.prefix(tomorrow.strftime("%d.%m.%Y") + " 04:15 ")
    p.reveal("Начало аукциона открытия", AREA)
    p.reveal("Время не получено", AREA)
    p.tap(str(tomorrow), AREA, direction="start")
    p.reveal("Торговый день не запланирован", AREA)
    p.tap(str(case.day + timedelta(days=2)), AREA, direction="start")
    p.reveal("Статус торгового дня не получен", AREA)
    baseline = case.observed()["requests"]
    p.tap("Обновить расписание", AREA)
    case.call("/workspace/markets/calendar", {}, after=baseline)
    case.extra["calendar"] = {"device_zone": zone, "source_start": str(case.day) + "T22:30:00Z",
                              "source_end": str(tomorrow) + "T01:15:00Z",
                              "moscow_start": str(tomorrow) + "T01:30:00+03:00",
                              "moscow_end": str(tomorrow) + "T04:15:00+03:00",
                              "closed_and_unknown_days_observed": True}


def exercise_markets(case):
    p = case.probe
    p.find("Рынки и география")
    _calendar(case)
    p.reveal_resource("profile-tabs", AREA, direction="start",
                      for_capture=True, minimum_size=(48, 48))
    p.tap("География", "profile-tabs", direction="start")
    case.call("/workspace", {"currency": "RUB"})
    p.reveal("Ось: страна основного риска", AREA)
    p.reveal("Без подтверждённой страны: 2", AREA)
    p.reveal("Распределение неполное. Неизвестные связи не добавляются к какой-либо стране.", AREA)
    p.reveal("Глобус стран основного риска. Выберите страну в доступном списке ниже. Подтверждённых географических меток: 2.", AREA)
    case.capture("geography")
    p.reveal("СИНТЕТИЧЕСКАЯ страна без координат · SYNTHETIC_UNMAPPED", AREA)
    p.reveal("Для этого кода нет координат в справочнике. Строка сохраняется без выдуманной метки на глобусе.", AREA)
    p.tap("СИНТЕТИЧЕСКАЯ Россия · RU", AREA, direction="start")
    p.tap("СИНТЕТИЧЕСКАЯ компания · СИНТЕТИЧЕСКИЙ счёт B", AREA)
    case.destination(account=ACCOUNT_B, query=SHARE_A)
    p.find("SYN-A")
    p.find("СИНТЕТИЧЕСКИЙ счёт B")
    p.reveal("СИНТЕТИЧЕСКАЯ компания", AREA)
    return ["source-calendar-real-get-and-refresh", "utc-moscow-midnight-rollover",
            "closed-versus-unknown-trading-day", "unknown-auction-time-explicit",
            "country-risk-axis-and-partial-coverage", "two-real-geographic-marks",
            "unknown-country-without-invented-point", "geography-opens-exact-account-position"]
