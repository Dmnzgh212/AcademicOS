# Bounded JSON service ABI v1

A service contribution can declare `contract = "lifehub.service-json@1"`.
Trusted host code invokes `call_service(caller_id, ref, request)` only after the
existing exact-ref, two-package-digest service grant. Review/grant/revoke APIs and
CLI accept this contract. Direct core-Wasm activation does not accept it.

The guest exports `memory` and `run: () -> i32`, with zero meaning success.
Only two imports are available under `lifehub_service`:

- `read_request(ptr, capacity) -> i32`: copies the complete UTF-8 JSON request;
  returns its byte length, or negative required length when capacity is too small.
- `write_response(ptr, length) -> i32`: supplies exactly one complete UTF-8 JSON
  response. Returns length; rejects invalid/nonfinite JSON and repeated responses.

Pointers and capacities are validated against guest memory. Input, raw output and
canonical output are limited to 64 KiB; modules, memory and fuel use the existing
runtime bounds. Responses are released only after zero status, exactly one valid
response, and a final package/grant check. Traps and failures discard responses.
Each invocation has fresh memory and fuel.

CLI requests, guest service requests and provider responses share the same JSON
message validation. Nonfinite constants and exponent overflow are rejected;
container nesting is limited to 64 levels, and parser nesting failures become
validation errors. Guest requests are validated
before invoking the bound provider callback.

This execution profile links no storage, effects, filesystem, network, WASI or
nested service-call imports, even if the provider manifest requests those rights.
It is a bounded computation service. JSON data cannot carry executable callbacks
or capabilities. The trusted caller must already be entitled to disclose request
data to the provider: this slice does not infer information-flow policy from JSON.

Caller identity still comes from trusted host code, not guest data. No guest RPC
bridge or remote API is provided. Requests/results are transient, not a durable
message queue, and no service result is automatically committed to personal state.
This ABI is core-Wasm and not the WIT Component Model.
