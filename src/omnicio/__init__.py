"""OmniCIO application package."""

from importlib.metadata import version as package_version

__all__ = ["__version__"]

__version__ = package_version("omnicio-gateway")
