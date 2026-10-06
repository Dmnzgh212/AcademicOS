# LifeHub core-Wasm runtime

> Architecture status (2026-10-03): this is the current **conventional executable plugin boundary** for LifeHub experiments. It is useful independently of PersonIR/POP and is the baseline against which a new IR must justify itself. Core Wasm is not being claimed as the final ABI; WIT/Component Model remains a possible future typed boundary.


Install `academicos[wasm]` (or `academicos[dev,wasm]` for development). The runtime
uses Wasmtime core modules. A package must be installed and approved in the managed
directory; placing a module in the development/demo directory does not enable execution.

Declare an arbitrary extension point with `entrypoint = "lifehub.wasm"` and
`config.module = "worker.wasm"`. The module path must identify a file in the approved
package snapshot. Start it explicitly with:

```bash
lifehub run-wasm demo.example:worker --db data/lifehub.db --installed data/lifehub-installed
```

The module exports `memory` and `run: () -> i32`. It may import three host
functions. `lifehub.read_json: (i32, i32, i32, i32) -> i32` takes
`namespace_ptr, namespace_len, output_ptr, output_capacity`. The function serializes
up to eight latest records as a JSON array into guest memory and returns the byte count.
If the buffer is too small, it returns the negative required size without writing.
The namespace must be requested in the package manifest and granted through LifeHub's
existing `grant-read` flow. `lifehub.propose_json: (i32, i32, i32, i32, i32, i32) -> i32`
takes `namespace_ptr, namespace_len, record_key_ptr, record_key_len, payload_ptr,
payload_len`. The payload must be a JSON object. It returns the number of proposals
staged during this invocation. This import never writes a record. See
`PROPOSAL_COMMIT.md` for the separate review and commit flow.
`lifehub.request_effect_json: (i32, i32) -> i32` takes the pointer and length of
a JSON object with `kind`, `destination`, `purpose`, and `payload` keys. It stages
an external effect request and returns the number staged in this run. See
`EFFECT_LEDGER.md` for the review and fake execution flow. There is no WASI linkage,
filesystem access, network access, direct write API, or direct external effect API.
A result integer stays in the local caller.

The execution limit is one million Wasm fuel units; guest memory is limited to 8 MiB,
module bytes to 2 MiB, a host IO call to 64 KiB, and one invocation to eight proposals
and four effect requests.
A module that traps or exceeds its budget returns an error and no staged proposal is
saved. This is a small, testable execution boundary, not yet a complete plugin runtime
with UI activation, durable jobs, or effects.

The host obtains a verified snapshot of the approved package before selecting the
module bytes. Package changes revoke subsequent execution. Filesystem races from
another process sharing the host's file privileges remain outside this slice's
guarantees. The Wasmtime Python embedding and fuel configuration follow the
[Wasmtime Python project](https://github.com/bytecodealliance/wasmtime-py) and
[Wasmtime fuel documentation](https://docs.wasmtime.dev/api/wasmtime/struct.Store.html).

Execution retains its starting approved content digest. Before persisting staged
proposals or effect requests, the host begins a database write transaction and
checks that approval still exists, the digest is unchanged, and package files
still verify. Uninstall, tampering, or approved replacement during execution
rejects the run and leaves no staged requests persisted. The write transaction
protects the database check/submission sequence; filesystem updates are not
atomically coordinated with SQLite.
