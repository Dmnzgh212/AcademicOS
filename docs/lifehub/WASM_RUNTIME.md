# LifeHub core-Wasm read-only runtime

Install `academicos[wasm]` (or `academicos[dev,wasm]` for development). The runtime
uses Wasmtime core modules. A package must be installed and approved in the managed
directory; placing a module in the development/demo directory does not enable execution.

Declare an arbitrary extension point with `entrypoint = "lifehub.wasm"` and
`config.module = "worker.wasm"`. The module path must identify a file in the approved
package snapshot. Start it explicitly with:

```bash
lifehub run-wasm demo.example:worker --db data/lifehub.db --installed data/lifehub-installed
```

The module exports `memory` and `run: () -> i32`. It may import exactly one host
function, `lifehub.read_json: (i32, i32, i32, i32) -> i32`, whose arguments are
`namespace_ptr, namespace_len, output_ptr, output_capacity`. The function serializes
up to eight latest records as a JSON array into guest memory and returns the byte count.
If the buffer is too small, it returns the negative required size without writing.
The namespace must be requested in the package manifest and granted through LifeHub's
existing `grant-read` flow. There is no WASI linkage, filesystem access, network
access, write API, or external effect API. A result integer stays in the local caller.

The execution limit is one million Wasm fuel units; guest memory is limited to 8 MiB,
module bytes to 2 MiB, and a host read to 64 KiB. A module that traps or exceeds its
budget returns an error. No host write occurs in this ABI, so there is no partial
commit or retry behavior to infer. This is a small, testable execution boundary,
not yet a complete plugin runtime with UI activation, durable jobs, or effects.

The host obtains a verified snapshot of the approved package before selecting the
module bytes. Package changes revoke subsequent execution. Filesystem races from
another process sharing the host's file privileges remain outside this slice's
guarantees. The Wasmtime Python embedding and fuel configuration follow the
[Wasmtime Python project](https://github.com/bytecodealliance/wasmtime-py) and
[Wasmtime fuel documentation](https://docs.wasmtime.dev/api/wasmtime/struct.Store.html).
