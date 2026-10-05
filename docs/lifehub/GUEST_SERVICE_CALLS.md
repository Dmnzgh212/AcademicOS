# Host-mediated guest service calls

Core-Wasm plugins may import
`lifehub.call_service_json(ref_ptr, ref_len, request_ptr, request_len, out_ptr, out_capacity) -> i32`.
The UTF-8 ref identifies one installed JSON computation service; the request is
complete UTF-8 JSON. Response bytes are copied into the validated output buffer.
The return is byte length or negative required length for a too-small buffer.
A retry is a new call and consumes another call allowance.

The import has no caller-ID argument. `LifeHub.run_wasm` binds caller identity to
the installed manifest before invoking the guest. Every call goes through the
same exact service declaration, contract, package digest and local grant checks
as `call_service`. Guest strings are not capability handles. Destination refs
outside the manifest/grant are rejected. Host code may still orchestrate directly.

Each core-Wasm run allows at most four service calls, including buffer-size retry
calls. Guest buffers and JSON are validated before invoking the target. The target
runs under `lifehub.service-json@1` with independent bounded fuel/memory and no
storage, network, effects or nested service-call imports. Call errors abort guest
execution; staged proposals/effects from that failed run are not persisted by the
kernel. JSON service calls themselves do not stage durable changes.

This is a synchronous core-Wasm ABI addition, not WIT or recursive service RPC.
A caller with storage-read authority can include that data in the request: the
service grant explicitly permits disclosure to the chosen installed computation
provider, but no general information-flow analysis or purpose tracking is claimed.
Provider code is confined to the computation profile. Same-user filesystem races
remain outside current package guarantees.

The shipped `examples/lifehub/json_echo` client now contains actual Wasm code.
Its CLI integration test covers denial before grant, successful guest invocation,
and denial after revocation. Runtime tests cover call budget, invalid output
buffer rejection before provider invocation, and unavailable unbound callbacks.
