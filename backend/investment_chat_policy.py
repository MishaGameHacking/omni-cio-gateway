"""Bounded, no-network admission and complexity policy for investment chat.

This conservative lexical policy is not a trained semantic classifier or an
accuracy guarantee. Unknown topics ask for clarification, not a paid guess.
Only server-loaded, owner-scoped user questions may supply follow-up context.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from collections.abc import Sequence

try:
    from .ai_policy import AnalysisTier
except ImportError:  # uvicorn top-level imports
    from ai_policy import AnalysisTier

POLICY_VERSION = "investment-chat-v1"
SCOPE_MESSAGE = (
    "Analyst AI отвечает только на вопросы об инвестициях, активах и мировой "
    "финансовой политике. Этот запрос не относится к поддерживаемым темам."
)
CLARIFY_MESSAGE = (
    "Уточните инвестиционный вопрос: укажите актив, портфель, рыночный показатель "
    "или влияние события на финансовые рынки. Вызов модели не выполнен."
)
TIER_MESSAGE = (
    "Для этого вопроса нужен более глубокий анализ. Выберите автоматический "
    "режим или подходящую глубину; стоимость будет проверена до отправки."
)

FINANCE = re.compile(
    r"\b(?:актив\w*|капитал\w*|валют\w*|фрс|ецб|инвест\w*|портфел\w*|облигац\w*|дивиденд\w*|эмитент\w*|"
    r"дефолт\w*|банкрот\w*|котиров\w*|ребаланс\w*|диверсифик\w*|"
    r"инфляц\w*|дефляц\w*|брокер\w*|ценн\w*\s+бумаг\w*|"
    r"акци[яиюй]|акциями|акциях|ликвидност\w*|волатильност\w*|"
    r"фондов\w*|бирж\w*|купонов\w*|купон\w*|доходност\w*|"
    r"денежн\w*\s+поток\w*|ключев\w*\s+ставк\w*|"
    r"центральн\w*\s+банк\w*|финансов\w*|долгов\w*|"
    r"бухгалтер\w*|отчетност\w*|мсфо|рсбу|офз|иис|нкд|"
    r"investment\w*|portfolio\w*|bond\w*|stock\w*|equities|equity|"
    r"dividend\w*|issuer\w*|default\w*|bankrupt\w*|inflation|deflation|"
    r"rebalanc\w*|diversif\w*|securit(?:y|ies)|valuation\w*|"
    r"earnings|cash\s+flow\w*|financial\w*|monetary|fiscal|"
    r"interest\s+rates?|etf\w*|ebitda|ebit|ifrs|gaap|cvar|var)\b",
    re.IGNORECASE,
)
OUTSIDE = re.compile(
    r"\b(?:рецепт\w*|борщ\w*|приготов\w*|погод\w*|гороскоп\w*|"
    r"зодиак\w*|анекдот\w*|сказк\w*|стихотвор\w*|поздравлен\w*|"
    r"диагноз\w*|антибиотик\w*|лечени\w*|лекарств\w*|"
    r"recipe\w*|cook(?:ing)?|weather|horoscope\w*|joke\w*|poem\w*|"
    r"diagnos\w*|antibiotic\w*|medical\s+treatment)\b",
    re.IGNORECASE,
)
UNRELATED_TASK = re.compile(
    r"\b(?:напиши|сочини|придумай|сгенерируй|write|generate|compose)\b"
    r"[^.!?\n]{0,90}\b(?:код|скрипт|программ\w*|python|javascript|"
    r"стих\w*|песн\w*|рассказ\w*|роман\w*|сказк\w*|code|script|story|song)\b",
    re.IGNORECASE,
)
INJECTION = re.compile(
    r"\b(?:игнорируй|забудь|отмени|ignore|disregard|override)\b"
    r"[^.!?\n]{0,90}\b(?:инструкц\w*|правил\w*|ограничен\w*|"
    r"instructions?|rules?|restrictions?|system)\b|"
    r"\b(?:system\s+prompt|developer\s+message|системн\w*\s+промпт)\b",
    re.IGNORECASE,
)
RETAIL = re.compile(r"\bакци\w*\b[^.!?\n]{0,50}\b(?:магазин\w*|супермаркет\w*|скидк\w*)\b", re.IGNORECASE)
FOLLOW_UP = re.compile(
    r"(?:(?:а|и|and|а\s+какие)\s+)?(?:почему|поясни|объясни|подробнее|"
    r"что\s+это\s+значит|какие\s+риски|риски|что\s+дальше|"
    r"приведи\s+пример|why|explain|more\s+detail|what\s+risks)[?.!\s]*",
    re.IGNORECASE,
)
DEFINITION = re.compile(r"^\s*(?:что\s+такое|что\s+означает|объясни\s+термин|what\s+is|define)\b", re.IGNORECASE)
DEEP = re.compile(r"\b(?:дефолт\w*|банкрот\w*|ковенант\w*|реструктуризац\w*|платежеспособ\w*|default\w*|bankrupt\w*|covenant\w*|solvency)\b", re.IGNORECASE)
STANDARD = re.compile(
    r"\b(?:сравн\w*|проанализ\w*|анализ\w*|аудит\w*|проверь|"
    r"диверсифик\w*|ребаланс\w*|продать|продаж\w*|купить|покупк\w*|"
    r"реинвест\w*|отчетност\w*|рекоменд\w*|распредел\w*|"
    r"compare|analy[sz]\w*|audit|rebalance|diversif\w*|buy|sell|allocate|recommend\w*)\b",
    re.IGNORECASE,
)
ANALYTIC_REQUEST = re.compile(r"\b(?:сравни\w*|проанализ\w*|проверь|оцени\w*|рассчита\w*|compare|analy[sz]e|assess|calculate|audit)\b", re.IGNORECASE)
LIMITS = {AnalysisTier.FAST: 600, AnalysisTier.STANDARD: 1200, AnalysisTier.PREMIUM: 1600}
TIER_ORDER = {AnalysisTier.FAST: 0, AnalysisTier.STANDARD: 1, AnalysisTier.PREMIUM: 2}


class ChatPolicyError(ValueError):
    def __init__(self, code: str, user_message: str):
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class ChatPlan:
    tier: AnalysisTier
    required_tier: AnalysisTier
    max_output_tokens: int
    reason: str
    policy_version: str = POLICY_VERSION

    def metadata(self) -> dict:
        return {"selected_tier": self.tier.value, "required_tier": self.required_tier.value,
                "max_output_tokens": self.max_output_tokens, "routing_reason": self.reason,
                "policy_version": self.policy_version, "classification_method": "deterministic_rules",
                "requires_cost_confirmation": self.tier is AnalysisTier.PREMIUM}


def normalized(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKC", text)
                            if unicodedata.category(c) != "Cf").casefold().replace("ё", "е").split())


def _outside(text: str) -> bool:
    return bool(OUTSIDE.search(text) or UNRELATED_TASK.search(text) or RETAIL.search(text) or INJECTION.search(text))


def _financial_history(history: Sequence[str]) -> bool:
    # Do not cross an unrelated previous user question or use model prose to
    # admit a follow-up. A bounded chain of genuine clarifications is allowed.
    for prior in reversed(history[-4:]):
        prior = normalized(prior[:8000])
        if _outside(prior):
            return False
        if FINANCE.search(prior):
            return True
        if not FOLLOW_UP.fullmatch(prior):
            return False
    return False


def plan_chat(text: str, requested_tier: str = "auto", *, history: Sequence[str] = ()) -> ChatPlan:
    if not isinstance(text, str) or not 1 <= len(text) <= 8000 or not text.strip():
        raise ChatPolicyError("chat_text_invalid", CLARIFY_MESSAGE)
    cleaned = normalized(text)
    if _outside(cleaned):
        raise ChatPolicyError("chat_outside_investment_scope", SCOPE_MESSAGE)
    if not FINANCE.search(cleaned) and not (FOLLOW_UP.fullmatch(cleaned) and _financial_history(history)):
        raise ChatPolicyError("chat_investment_scope_unclear", CLARIFY_MESSAGE)
    required = AnalysisTier.FAST
    simple_definition = (DEFINITION.search(cleaned) and not ANALYTIC_REQUEST.search(cleaned)
                         and len([part for part in re.split(r"[.!?;]+", cleaned) if part.strip()]) == 1)
    if not simple_definition:
        if DEEP.search(cleaned):
            required = AnalysisTier.PREMIUM
        elif STANDARD.search(cleaned):
            required = AnalysisTier.STANDARD
    if requested_tier == "auto":
        selected = required
    else:
        try:
            selected = AnalysisTier(requested_tier)
        except (ValueError, TypeError):
            raise ChatPolicyError("chat_tier_invalid", TIER_MESSAGE) from None
        if selected not in TIER_ORDER:
            raise ChatPolicyError("chat_tier_invalid", TIER_MESSAGE)
        if TIER_ORDER[selected] < TIER_ORDER[required]:
            raise ChatPolicyError("chat_tier_insufficient", TIER_MESSAGE)
    return ChatPlan(selected, required, LIMITS[selected],
                    "task_complexity" if requested_tier == "auto" else "explicit_user_tier")
