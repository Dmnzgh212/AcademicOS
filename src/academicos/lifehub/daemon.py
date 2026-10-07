"""Persistent local daemon wrapper for the shell-independent LifeHub Engine."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from academicos.lifehub.control import EngineControlServer
from academicos.lifehub.engine import LifeHubEngine

DEFAULT_ENGINE_AUTH_FILE = Path("data/lifehub-engine.key")


def default_control_endpoint(data_dir: str | Path = "data") -> tuple[str, str]:
    """Return a local-only control endpoint for the current host OS."""
    if os.name == "nt":
        return (r"\\.\pipe\lifehub-engine", "AF_PIPE")
    return (str(Path(data_dir) / "lifehub-engine.sock"), "AF_UNIX")


def load_or_create_authkey(path: str | Path = DEFAULT_ENGINE_AUTH_FILE) -> bytes:
    """Create a private random control key once, then reuse it."""
    key_path = Path(path)
    if key_path.exists():
        return load_authkey(key_path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    key_path.write_text(key.hex(), encoding="ascii")
    try:
        key_path.chmod(0o600)
    except OSError:
        # Windows ACLs are not represented faithfully by POSIX chmod.
        pass
    return key


def load_authkey(path: str | Path = DEFAULT_ENGINE_AUTH_FILE) -> bytes:
    key_path = Path(path)
    try:
        text = key_path.read_text(encoding="ascii").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"LifeHub engine auth file does not exist: {key_path}; start the engine first"
        ) from exc
    try:
        key = bytes.fromhex(text)
    except ValueError as exc:
        raise ValueError("LifeHub engine auth file is not valid hexadecimal") from exc
    if len(key) < 32:
        raise ValueError("LifeHub engine auth key is too short")
    return key


class LifeHubEngineDaemon:
    """Own one persistent engine process and its authenticated local IPC listener."""

    def __init__(
        self,
        *,
        db_path: str | Path = "data/lifehub.db",
        plugins_path: str | Path = "data/lifehub-installed",
        address: str | None = None,
        family: str | None = None,
        authkey: bytes,
    ) -> None:
        default_address, default_family = default_control_endpoint(Path(db_path).parent)
        self.address = address or default_address
        self.family = family or default_family
        self.engine = LifeHubEngine(db_path=db_path, plugins_path=plugins_path)
        self._owns_unix_path = self.family == "AF_UNIX"
        if self._owns_unix_path and Path(self.address).exists():
            self.engine.close()
            raise FileExistsError(
                f"LifeHub engine socket already exists: {self.address}; "
                "do not remove it unless no engine process is running"
            )
        try:
            self.server = EngineControlServer(
                self.engine,
                self.address,
                authkey=authkey,
                family=self.family,
            )
        except BaseException:
            self.engine.close()
            raise

    def serve_once(self) -> None:
        self.server.serve_once()

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def close(self) -> None:
        self.server.close()
        try:
            self.engine.shutdown()
        finally:
            if self._owns_unix_path:
                path = Path(self.address)
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
