"""Default-off real-money trading v1.

The package is isolated from the existing read-only credential. Real-money
routes are conditionally registered only behind explicit server configuration,
and execution additionally requires durable state plus exact owner confirmation.
"""
