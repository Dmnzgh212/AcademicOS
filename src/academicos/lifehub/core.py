"""Compatibility facade for the LifeHub v0.2 extension kernel.

New code should import from the focused modules (`manifest`, `registry`, `store`,
`network`, `kernel`). This module remains so existing callers do not break while
v0.1 dashboard code is migrated.
"""

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.manifest import ExtensionContribution, PermissionSpec, PluginManifest
from academicos.lifehub.network import EgressGateway
from academicos.lifehub.registry import PluginBundle, PluginRegistry, RegisteredExtension
from academicos.lifehub.store import LifeStore, ScopedStore, namespace_allowed

__all__ = [
    "EgressGateway",
    "ExtensionContribution",
    "LifeHub",
    "LifeStore",
    "PermissionSpec",
    "PluginBundle",
    "PluginManifest",
    "PluginRegistry",
    "RegisteredExtension",
    "ScopedStore",
    "namespace_allowed",
]
