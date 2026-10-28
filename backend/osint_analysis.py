"""Deterministic investment triage; observations are not ratings or trading authority."""
from __future__ import annotations

from collections import Counter
import hashlib
import re
import unicodedata

try:
    from .osint_catalogue import IntakeError, MAX_TEXT
except ImportError:
    from osint_catalogue import IntakeError, MAX_TEXT

VERSION = "investment-osint-rules-v1"
TOPICS = {
    "credit_event": (r"дефолт|неисполнени[ея].{0,35}обязательств|реструктуризац|default|restructur",
                     "high", "Проверить долговые обязательства и официальные сообщения эмитента."),
    "cyber_incident": (r"утечк.{0,25}данн|кибератак|киберинцидент|взлом|data breach|cyber.attack|ransomware",
                       "high", "Возможен операционный риск; сообщение само по себе не подтверждает утечку."),
    "financial_report": (r"отч[её]тност|мсфо|рсбу|financial.statement|financial.report|ifrs|net.profit|earnings|ebitda|выручк",
                         "normal", "Сопоставить отчётный период, валюту, масштаб и состав группы перед расчётами."),
    "dividend": (r"дивиденд|dividend", "normal", "Уточнить решение органа управления, дату отсечки и условия выплаты."),
    "monetary_policy": (r"ключев.{0,15}ставк|денежно.кредитн|key.rate|monetary.policy",
                        "normal", "Изменение ставки может влиять на стоимость заимствований и оценку облигаций."),
    "sanctions": (r"санкци|sanction", "high", "Проверить применимость ограничений к компании и её операциям."),
    "rating": (r"кредитн.{0,20}рейтинг|credit.rating|rating.downgrade",
               "normal", "Найти первичное рейтинговое действие; новость не заменяет рейтинг агентства."),
    "market_event": (r"листинг|торг|облигац|акци[яий]|эмитент|бирж|bond|stock|listing|securit",
                     "normal", "Уточнить инструменты, сроки и условия события по первоисточнику."),
}
FINANCIAL_LABELS = {
    "revenue": r"выручк[а-я]*|revenue",
    "net_profit": r"чистая\s+прибыль|чистый\s+убыток|net\s+(?:income|profit|loss)",
    "ebitda": r"\bebitda\b",
    "net_debt": r"чистый\s+долг|net\s+debt",
    "total_assets": r"итого\s+актив[а-я]*|total\s+assets",
    "equity": r"итого\s+(?:собственный\s+)?капитал|total\s+equity",
}
SENSITIVE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?:password|пароль|access_token|api[_-]?key)\s*[:=]\s*[^\s]{6,}|"
    r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}")
NUMBERS = re.compile(r"(?<!\w)[(−-]?\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?\)?%?(?!\w)")


def clean_text(value: str, maximum: int = MAX_TEXT) -> str:
    value = unicodedata.normalize("NFKC", str(value or ""))[:maximum * 2]
    if SENSITIVE.search(value):
        raise IntakeError("osint_sensitive_material_rejected")
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[контакт удалён]", value)
    value = re.sub(r"\+7[\s(-]*\d{3}[)\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}", "[контакт удалён]", value)
    value = "".join(char for char in value if char in "\n\t" or unicodedata.category(char)[0] != "C")
    return re.sub(r"[^\S\n]+", " ", value).strip()[:maximum]


def fingerprint(text: str) -> str:
    normalized = " ".join(re.findall(r"[a-zа-яё0-9]+", text.casefold()))
    return hashlib.sha256(normalized.encode()).hexdigest()


def simhash(text: str) -> str:
    weights = [0] * 64
    for token, count in Counter(re.findall(r"[a-zа-яё0-9]{2,}", text.casefold())[:12000]).items():
        hashed = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big")
        for bit in range(64):
            weights[bit] += min(count, 3) * (1 if hashed & (1 << bit) else -1)
    return f"{sum(1 << bit for bit, weight in enumerate(weights) if weight > 0):016x}"


def bands(value: str) -> list[tuple[int, int]]:
    number = int(value, 16)
    return [(index, (number >> (index * 16)) & 65535) for index in range(4)]


def financial_candidates(pages: list[dict]) -> list[dict]:
    result = []
    for page in pages:
        text = page["text"]
        unit = next((name for pattern, name in (
            (r"миллион.{0,20}рубл|млн\.?\s*руб", "RUB million"),
            (r"тысяч.{0,20}рубл|тыс\.?\s*руб", "RUB thousand"),
            (r"USD.{0,15}million|millions? of.{0,10}dollars", "USD million"))
            if re.search(pattern, text, re.I)), None)
        for line in text.splitlines():
            for metric, pattern in FINANCIAL_LABELS.items():
                if re.search(pattern, line, re.I):
                    tokens = NUMBERS.findall(line)
                    if tokens:
                        result.append({"metric": metric, "page": page["page"],
                            "raw_values": tokens[:8], "unit_hint": unit, "period": None,
                            "quote": clean_text(line, 420), "status": "candidate_requires_column_and_period_validation"})
            if len(result) >= 80:
                return result
    return result


def analyze(title: str, text: str, *, report: bool = False, pages: list[dict] | None = None) -> dict:
    title, text = clean_text(title, 400), clean_text(text)
    sample = title + "\n" + text[:60000]
    matches = [name for name, (pattern, _, _) in TOPICS.items() if re.search(pattern, sample, re.I)]
    if report and "financial_report" not in matches:
        matches.insert(0, "financial_report")
    marketing = bool(re.search(r"вебинар|конференци|мастер.класс|зарегистрируйтесь|реклам[аы]|webinar", title, re.I))
    material = {"credit_event", "cyber_incident", "financial_report", "dividend", "monetary_policy", "sanctions", "rating"}
    relevant = bool(matches) and (not marketing or bool(material.intersection(matches)))
    topic = next((name for name in matches if name != "market_event"), "market_event" if matches else "irrelevant")
    stance = "source_claim"
    if topic == "cyber_incident":
        stance = "denial" if re.search(r"опроверг|не\s+подтверд|не\s+обнаруж|den(?:y|ies|ied)", sample, re.I) else "unconfirmed_report"
    evidence = []
    pattern = TOPICS.get(topic, (r"$^", "", ""))[0]
    for sentence in re.split(r"(?<=[.!?])\s+|\n", sample):
        if re.search(pattern, sentence, re.I):
            evidence.append(sentence.strip()[:420])
        if len(evidence) == 3:
            break
    impact = TOPICS.get(topic, ("", "normal", "Не обнаружена инвестиционная тема."))[2]
    label = "Источник опровергает сообщение об инциденте. " if stance == "denial" else ""
    return {"version": VERSION, "relevant": relevant, "topics": matches, "topic": topic,
            "priority": TOPICS.get(topic, ("", "normal", ""))[1], "stance": stance,
            "conclusion": label + impact, "evidence_quotes": evidence,
            "financial_candidates": financial_candidates(pages or []) if report else [],
            "independent_confirmation": "not_established", "trade_permission": False,
            "content_fingerprint": fingerprint(title + "\n" + text), "simhash": simhash(title + "\n" + text)}
