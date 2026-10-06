"""Build inert three-domain packages and a separate descriptor-service consumer."""

import json
from pathlib import Path
import sys
import zipfile

PLUGINS = {
    'academic': ('Academic deadlines', 'academic.deadlines', ['course', 'title', 'due']),
    'rss': ('RSS items', 'rss.items', ['title', 'link', 'guid', 'published']),
    'system': ('Local system snapshot', 'system.snapshot', ['os', 'release', 'architecture', 'python']),
}


def wat_bytes(raw):
    return ''.join(f'\\{value:02x}' for value in raw)


def reader(namespace):
    return f'''(module
      (import "lifehub" "read_json" (func $read (param i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "{namespace}")
      (func (export "run") (result i32)
        (call $read (i32.const 0) (i32.const {len(namespace)})
                   (i32.const 128) (i32.const 65000))))'''


def descriptor(body):
    request = b'{"operation":"describe"}'
    return f'''(module
      (import "lifehub_service" "read_request" (func $read (param i32 i32) (result i32)))
      (import "lifehub_service" "write_response" (func $write (param i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 8192) "{wat_bytes(request)}")
      (data (i32.const 16384) "{wat_bytes(body)}")
      (func (export "run") (result i32) (local $i i32)
        (if (i32.ne (call $read (i32.const 0) (i32.const 4096)) (i32.const {len(request)}))
          (then (return (i32.const 1))))
        (block $done (loop $check
          (br_if $done (i32.ge_u (local.get $i) (i32.const {len(request)})))
          (if (i32.ne (i32.load8_u (local.get $i))
                      (i32.load8_u (i32.add (i32.const 8192) (local.get $i))))
            (then (return (i32.const 1))))
          (local.set $i (i32.add (local.get $i) (i32.const 1))) (br $check)))
        (drop (call $write (i32.const 16384) (i32.const {len(body)}))) (i32.const 0)))'''


def build(destination):
    import wasmtime

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    archives = []
    for key, (name, namespace, fields) in PLUGINS.items():
        manifest = f'''manifest_version = 1
api = "lifehub@1"
id = "ecosystem.{key}"
name = "{name}"
version = "0.1.0"
[permissions]
storage_read = ["{namespace}"]
[[contributes]]
id = "read"
point = "ecosystem.{key}.records"
entrypoint = "lifehub.wasm"
contract = "lifehub.core-wasm@1"
[contributes.config]
module = "reader.wasm"
namespace = "{namespace}"
records_contract = "ecosystem.{key}-records@1"
[[contributes]]
id = "describe"
point = "lifehub.service"
entrypoint = "lifehub.wasm"
contract = "lifehub.service-json@1"
[contributes.config]
module = "describe.wasm"
'''
        body = json.dumps({'api': f'ecosystem.{key}-schema@1', 'namespace': namespace,
                           'fields': fields}, separators=(',', ':')).encode()
        archive = destination / f'{key}.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('plugin.toml', manifest)
            output.writestr('reader.wasm', wasmtime.wat2wasm(reader(namespace)))
            output.writestr('describe.wasm', wasmtime.wat2wasm(descriptor(body)))
        archives.append(archive)
    refs = [f'ecosystem.{key}:describe' for key in PLUGINS]
    manifest = '''manifest_version = 1
api = "lifehub@1"
id = "ecosystem.consumer"
name = "Schema consumer"
version = "0.1.0"
[permissions]
service_call = ''' + json.dumps(refs) + '\n'
    with zipfile.ZipFile(destination / 'consumer.zip', 'w') as output:
        for key in PLUGINS:
            ref = f'ecosystem.{key}:describe'
            request = b'{"operation":"describe"}'
            manifest += f'''[[contributes]]
id = "{key}"
point = "ecosystem.schema-consumer"
entrypoint = "lifehub.wasm"
contract = "lifehub.core-wasm@1"
[contributes.config]
module = "{key}.wasm"
'''
            module = f'''(module
              (import "lifehub" "call_service_json"
                (func $call (param i32 i32 i32 i32 i32 i32) (result i32)))
              (memory (export "memory") 1)
              (data (i32.const 0) "{ref}")
              (data (i32.const 128) "{wat_bytes(request)}")
              (func (export "run") (result i32)
                (call $call (i32.const 0) (i32.const {len(ref)})
                  (i32.const 128) (i32.const {len(request)})
                  (i32.const 512) (i32.const 4096))))'''
            output.writestr(f'{key}.wasm', wasmtime.wat2wasm(module))
        output.writestr('plugin.toml', manifest)
    return [*archives, destination / 'consumer.zip']


if __name__ == '__main__':
    for archive in build(sys.argv[1]):
        print(archive)
