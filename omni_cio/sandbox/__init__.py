"""Sandbox-only trading contour for Omni-CIO.

This package is intentionally isolated from the production T-Invest token and
production order service. It may talk only to the documented T-Invest Sandbox
REST endpoint and is disabled unless SANDBOX_TRADING_ENABLED is explicitly on.
"""

from .routes_v1 import maybe_register_sandbox_trading_gateway

__all__ = ["maybe_register_sandbox_trading_gateway"]
