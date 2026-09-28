from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from academicos.lifehub.manifest import ExtensionContribution, PluginManifest, load_manifest


@dataclass(frozen=True)
class PluginBundle:
    root: Path
    manifest: PluginManifest

    @property
    def seed_file(self) -> Path:
        return self.root / "seed.json"


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

    def __init__(self, root: str | Path = "lifehub_plugins") -> None:
        self.root = Path(root)
        self._bundles: tuple[PluginBundle, ...] | None = None
        self._extensions: tuple[RegisteredExtension, ...] | None = None

    def discover(self) -> tuple[PluginBundle, ...]:
        if self._bundles is not None:
            return self._bundles
        if not self.root.exists():
            self._bundles = ()
            self._extensions = ()
            return self._bundles

        found: dict[str, PluginBundle] = {}
        extensions: list[RegisteredExtension] = []
        for manifest_path in sorted(self.root.glob("*/plugin.toml")):
            manifest = load_manifest(manifest_path)
            if manifest.id in found:
                raise ValueError(f"duplicate plugin id: {manifest.id}")
            bundle = PluginBundle(manifest_path.parent, manifest)
            found[manifest.id] = bundle
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
        self._extensions = tuple(extensions)
        return self._bundles

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
