"""OmniCIO application package."""

from importlib.metadata import version as package_version

__all__ = ["APPLICATION_USER_AGENT", "__version__"]

# Installed package metadata is generated from [project].version in pyproject.toml.
# Missing metadata must fail visibly; there is no fallback to an older release.
__version__ = package_version("omnicio-gateway")
APPLICATION_USER_AGENT = f"OMNICIO/{__version__} (+https://omnicio.ru)"
