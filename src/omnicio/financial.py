"""Shared units and input bounds for exact monetary calculations.

These are accounting conventions, not return assumptions or trading authority.
Decimal arithmetic and each caller's existing rounding direction remain intact.
"""

from decimal import Decimal

# One percent is 1/100 of a whole. Keep an integer so float simulations and
# Decimal accounting can use the same unit without mixing numeric types.
PERCENT_SCALE = 100
MONTHS_PER_YEAR = 12
# A kopeck is the displayed RUB quantum and the existing reconciliation tolerance;
# provider quotations retain their original precision until a caller rounds them.
RUB_QUANTUM = Decimal("0.01")
# Input validation ceiling, not available cash, a forecast, or an execution limit.
MAX_USER_AMOUNT_RUB = Decimal("1000000000000")
