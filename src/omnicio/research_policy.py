"""Versioned mathematical contracts shared by research, screening and replay.

The research engine version is independent of the application release. Historical
capability sets are explicit: a release bump must not silently reinterpret an
archived run. Changing these assumptions requires reviewing replay invariants.
"""

RESEARCH_ENGINE_VERSION = "1.3.3"
CORRECTED_MATH_ENGINES = frozenset({"1.3.1", "1.3.2", "1.3.3"})
UNIT_AWARE_ENGINES = frozenset({"1.3.2", "1.3.3"})
SUPPORTED_RESEARCH_ENGINES = frozenset({"1.1.0", "1.2.0", "1.3.0"}) | CORRECTED_MATH_ENGINES

# Hard per-run bounds; they do not claim coverage of the complete market.
MAX_RESEARCH_ASSETS = 100
MAX_RESEARCH_DAYS = 1095
MIN_TRAIN_OBSERVATIONS = 60
MIN_TEST_OBSERVATIONS = 20
# Disclosed daily-return annualization convention, not a calendar-day forecast.
ANNUALIZATION_SESSIONS = 252
# Trailing observed income uses a fixed 365-day window, not a fiscal-year guess.
CASHFLOW_WINDOW_DAYS = 365
