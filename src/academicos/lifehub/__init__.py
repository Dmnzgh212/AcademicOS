"""LifeHub: open personal computing platform and execution engine."""

from academicos.lifehub.engine import (
    ComponentDescriptor,
    ExecutionState,
    LifeHubEngine,
    RunnerStart,
)
from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.manifest import ComponentSpec, ExtensionContribution, PermissionSpec, PluginManifest
from academicos.lifehub.registry import PluginRegistry, RegisteredComponent, RegisteredExtension

__all__ = [
    "ComponentDescriptor",
    "ComponentSpec",
    "ExecutionState",
    "ExtensionContribution",
    "LifeHub",
    "LifeHubEngine",
    "PermissionSpec",
    "PluginManifest",
    "PluginRegistry",
    "RegisteredComponent",
    "RegisteredExtension",
    "RunnerStart",
]
