"""LifeHub: open personal computing platform and execution engine."""

from academicos.lifehub.engine import (
    ComponentDescriptor,
    ExecutionState,
    LifeHubEngine,
    RunnerStart,
)
from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.manifest import ExtensionContribution, PermissionSpec, PluginManifest
from academicos.lifehub.registry import PluginRegistry, RegisteredExtension

__all__ = [
    "ComponentDescriptor",
    "ExecutionState",
    "ExtensionContribution",
    "LifeHub",
    "LifeHubEngine",
    "PermissionSpec",
    "PluginManifest",
    "PluginRegistry",
    "RegisteredExtension",
    "RunnerStart",
]
