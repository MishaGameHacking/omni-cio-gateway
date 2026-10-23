"""Composition root for the durable, read-only 3D workspace API."""
try:
    from . import volume_state, volume_notifications, volume_jobs, volume_chat, volume_plans, volume_analysis
except ImportError:
    import volume_state
    import volume_notifications
    import volume_jobs
    import volume_chat
    import volume_plans
    import volume_analysis


def initialize() -> None:
    volume_state.initialize()
    volume_notifications.initialize()
    volume_jobs.initialize()
    volume_chat.initialize()
    volume_plans.initialize()
    volume_analysis.initialize()
