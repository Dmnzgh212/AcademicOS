"""Compile the sample core-Wasm package; never installs or grants permissions."""

from pathlib import Path
import argparse
import zipfile

import wasmtime


def build(destination: Path) -> None:
    source = Path(__file__).resolve().parent
    module = wasmtime.wat2wasm((source / "reader.wat").read_text())
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("plugin.toml", (source / "plugin.toml").read_bytes())
        archive.writestr("reader.wasm", module)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    build(parser.parse_args().destination)
