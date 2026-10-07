from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from academicos.lifehub.manifest import ComponentSpec, ExtensionContribution, PluginManifest, load_manifest


@dataclass(frozen=True)
class PluginBundle:
    root: Path
    manifest: PluginManifest

    @property
    def seed_file(self) -> Path:
        return self.root / "seed.json"


@dataclass(frozen=True)
class RegisteredComponent:
    plugin_id: str
    plugin_name: str
    component: ComponentSpec
    root: Path

    @property
    def ref(self) -> str:
        return f"{self.plugin_id}:{self.component.id}"


@dataclass(frozen=True)
class RegisteredExtension:
    plugin_id: str
    plugin_name: str
    contribution: ExtensionContribution
    root: Path

    @property
    def ref(self) -> str:
        return f"{self.plugin_id}:{self.contribution.id}"


class PluginRegistry:
    """Discovers plugin packages and indexes arbitrary extension points."""

    def __init__(
        self,
        root: str | Path = "lifehub_plugins",
        *,
        verify: Callable[[Path, PluginManifest], None] | None = None,
        managed: bool = False,
    ) -> None:
        self.root = Path(root)
        self._verify = verify
        self._managed = managed
        self._bundles: tuple[PluginBundle, ...] | None = None
        self._components: tuple[RegisteredComponent, ...] | None = None
        self._extensions: tuple[RegisteredExtension, ...] | None = None

    def discover(self) -> tuple[PluginBundle, ...]:
        managed = self._managed or (self.root / ".lifehub-managed").exists()
        if managed and self._verify is None:
            raise PermissionError("managed plugin directory requires approval verification")
        if managed:
            self._bundles = None
            self._components = None
            self._extensions = None
        if self._bundles is not None:
            return self._bundles
        if not self.root.exists():
            self._bundles = ()
            self._components = ()
            self._extensions = ()
            return self._bundles

        found: dict[str, PluginBundle] = {}
        components: list[RegisteredComponent] = []
        extensions: list[RegisteredExtension] = []
        for manifest_path in sorted(self.root.glob("*/plugin.toml")):
            if managed and (manifest_path.parent.is_symlink() or manifest_path.is_symlink()):
                raise PermissionError(
                    f"installed plugin manifest path is a symlink: {manifest_path}"
                )
            manifest = load_manifest(manifest_path)
            if managed:
                assert self._verify is not None
                self._verify(manifest_path.parent, manifest)
            if manifest.id in found:
                raise ValueError(f"duplicate plugin id: {manifest.id}")
            bundle = PluginBundle(manifest_path.parent, manifest)
            found[manifest.id] = bundle
            components.extend(
                RegisteredComponent(
                    plugin_id=manifest.id,
                    plugin_name=manifest.name,
                    component=component,
                    root=manifest_path.parent,
                )
                for component in manifest.components
            )
            extensions.extend(
                RegisteredExtension(
                    plugin_id=manifest.id,
                    plugin_name=manifest.name,
                    contribution=contribution,
                    root=manifest_path.parent,
                )
                for contribution in manifest.contributes
            )

        self._bundles = tuple(found.values())
        self._components = tuple(components)
        self._extensions = tuple(extensions)
        return self._bundles

    def components(self) -> tuple[RegisteredComponent, ...]:
        self.discover()
        assert self._components is not None
        return self._components

    def component(self, ref: str) -> RegisteredComponent:
        for component in self.components():
            if component.ref == ref:
                return component
        raise KeyError(ref)

    def extensions(self, point: str | None = None) -> tuple[RegisteredExtension, ...]:
        self.discover()
        assert self._extensions is not None
        if point is None:
            return self._extensions
        return tuple(item for item in self._extensions if item.contribution.point == point)

    def extension(self, ref: str) -> RegisteredExtension:
        for extension in self.extensions():
            if extension.ref == ref:
                return extension
        raise KeyError(ref)

    def bundle(self, plugin_id: str) -> PluginBundle:
        for bundle in self.discover():
            if bundle.manifest.id == plugin_id:
                return bundle
        raise KeyError(plugin_id)

    def points(self) -> tuple[str, ...]:
        return tuple(sorted({item.contribution.point for item in self.extensions()}))
