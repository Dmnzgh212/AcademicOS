"""Build echo provider and client declaration packages without installation."""

import argparse
from pathlib import Path
import zipfile

import wasmtime


def build(destination: Path) -> tuple[Path, Path]:
    source = Path(__file__).resolve().parent
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in ("provider", "caller"):
        path = destination / f"{name}.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("plugin.toml", (source / f"{name}.toml").read_bytes())
            if name == "provider":
                archive.writestr("echo.wasm", wasmtime.wat2wasm((source / "echo.wat").read_text()))
            else:
                archive.writestr(
                    "caller.wasm", wasmtime.wat2wasm((source / "caller.wat").read_text())
                )
        paths.append(path)
    return tuple(paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    build(parser.parse_args().destination)
