from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = ROOT / "gpt" / "INSTRUCTIONS_COMPACT.md"
CONFIGURATION = ROOT / "gpt" / "CONFIGURATION.md"
POLICY = ROOT / "gpt" / "PERSONAL_PORTFOLIO_POLICY_TEMPLATE.md"
ACCEPTANCE = ROOT / "gpt" / "PORTFOLIO_GPT_ACCEPTANCE_V1.md"
SCOPE = ROOT / "docs" / "master-plan" / "OMNI_CIO_PORTFOLIO_GPT_RESET_V1.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_portfolio_gpt_required_assets_exist() -> None:
    for path in (INSTRUCTIONS, CONFIGURATION, POLICY, ACCEPTANCE, SCOPE):
        assert path.is_file(), path
        assert path.stat().st_size > 0, path


def test_compact_instructions_define_strict_portfolio_workflow() -> None:
    text = _read(INSTRUCTIONS)

    for required in (
        "персональный инвестиционный AI-ассистент",
        "trading_methods=false",
        "getPortfolioAnalytics",
        "getCashLiquiditySnapshot",
        "getPurchaseCapacityPreview",
        "Ничего не делать",
        "Ограниченное изменение",
        "Более существенное изменение",
        "кредитные рейтинги",
        "качества данных",
        "Личная политика",
        "не создавай",
    ):
        assert required in text

    for forbidden in (
        "в целом всё заебись",
        "пахнет пиздецом",
        "к собачьим хуям",
        "подготовь Telegram-пост",
        "publishTelegramChannelPost",
        "создай отдельный сайт",
        "автономно торгуй",
    ):
        assert forbidden not in text


def test_configuration_uses_existing_gpt_and_minimal_capabilities() -> None:
    text = _read(CONFIGURATION)

    assert "update in place" in text
    assert "Web Search" in text
    assert "Code Interpreter / Data Analysis" in text
    assert "Actions" in text
    assert "Image generation — не требуется" in text
    assert "Apps — текущий GPT использует Actions" in text
    assert "ровно 14 GET operations" in text


def test_scope_excludes_non_portfolio_products() -> None:
    text = _read(SCOPE)

    for excluded in (
        "отдельный сайт или web-кабинет",
        "мобильное приложение",
        "собственная языковая модель",
        "Telegram-бот, Telegram-публикации и Telegram API",
        "автономное управление деньгами",
    ):
        assert excluded in text

    assert "работать только по командам пользователя" in text
    assert "не входят в текущий scope" in text


def test_acceptance_covers_safety_quality_and_portfolio_jobs() -> None:
    text = _read(ACCEPTANCE)

    for scenario in (
        "A2. Запрос сделки",
        "C1. Полный анализ",
        "D1. Partial data",
        "E1. Концентрация",
        "F1. Новости по портфелю",
        "G1. Анализ облигации",
        "H1. Поиск кандидатов",
        "H2. Purchase capacity",
        "I1. Что продать",
    ):
        assert scenario in text


def test_personal_policy_contains_required_risk_controls() -> None:
    text = _read(POLICY)

    for required in (
        "Максимально допустимая просадка",
        "Минимальный денежный резерв",
        "Максимальная доля одного эмитента",
        "Минимально допустимый кредитный рейтинг",
        "Целевые классы активов",
        "Запреты",
    ):
        assert required in text
