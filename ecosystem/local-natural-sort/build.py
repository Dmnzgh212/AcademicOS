"""Compile a localized C function with Zig 0.13; never install/grant a package."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import wasmtime

HERE = Path(__file__).resolve().parent


def without_unused_table(module):
    # Zig emits a reserved, unexported 1-entry funcref table even without function pointers.
    # Remove only that exact section; Wasmtime validation rejects any remaining table use.
    result = bytearray(module[:8])
    pos = 8
    while pos < len(module):
        begin = pos
        kind = module[pos]
        pos += 1
        size = shift = 0
        while True:
            byte = module[pos]
            pos += 1
            size |= (byte & 127) << shift
            if byte < 128:
                break
            shift += 7
            if shift > 28:
                raise ValueError('invalid compiled section length')
        end = pos + size
        if end > len(module):
            raise ValueError('truncated compiled section')
        if kind == 4:
            if module[pos:end] != bytes.fromhex('0170010101'):
                raise ValueError('compiler table changed; review required')
        else:
            result.extend(module[begin:end])
        pos = end
    result = bytes(result)
    wasmtime.Module(wasmtime.Engine(), result)  # Reject referenced/missing table.
    return result


def build(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        module = Path(temp) / 'sort.wasm'
        subprocess.run([sys.executable, '-m', 'ziglang', 'cc', '-target', 'wasm32-freestanding',
                        '-Oz', '-nostdlib', '-fno-builtin', '-Wl,--no-entry',
                        '-Wl,--export-memory', '-Wl,--initial-memory=0x200000',
                        '-Wl,--max-memory=0x200000',
                        str(HERE / 'module.c'), str(HERE / 'vendor/strnatcmp.c'),
                        '-o', str(module)], check=True, timeout=60)
        result = []
        for name in ('provider', 'client'):
            entries = {'plugin.toml': (HERE / f'{name}.toml').read_bytes()}
            if name == 'provider':
                entries['sort.wasm'] = without_unused_table(module.read_bytes())
                entries['NOTICE.md'] = (HERE / 'NOTICE.md').read_bytes()
            path = destination / f'{name}.lhpkg'
            with zipfile.ZipFile(path, 'w') as archive:
                for key, data in sorted(entries.items()):
                    info = zipfile.ZipInfo(key, date_time=(1980, 1, 1, 0, 0, 0))
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data)
            result.append(path)
        (destination / 'package-hashes.json').write_text(json.dumps(
            {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in result}, indent=2)+'\n')
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    build(parser.parse_args().destination)
