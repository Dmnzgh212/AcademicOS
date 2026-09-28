"""LifeHub: local-first extension host for personal information and capabilities."""

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.manifest import ExtensionContribution, PermissionSpec, PluginManifest
from academicos.lifehub.registry import PluginRegistry, RegisteredExtension

__all__ = [
    "ExtensionContribution",
    "LifeHub",
    "PermissionSpec",
    "PluginManifest",
    "PluginRegistry",
    "RegisteredExtension",
]
