# Isolated Component ABI probe

Status: preliminary research evidence, not an Engine migration decision.

The production Wasmtime 36 Python environment has no `wasmtime.component`
module. A separate Python 3.12 environment with Wasmtime 49.0.0 executes the
hand-authored `experiments/component_abi/echo.wat`. The accompanying WIT file
describes the intended signature; it is not compiled or checked against that
component. No generated bindings, SDK, upstream source copy, or Core change
is included.

Reproduce in a disposable environment:

```sh
python -m venv /tmp/lifehub-component-probe
/tmp/lifehub-component-probe/bin/python -m pip install -e . -r experiments/component_abi/requirements.txt
/tmp/lifehub-component-probe/bin/python experiments/component_abi/compare.py
```

Do not install this requirements file in the platform test/runtime environment.
Both comparison paths run under experimental Wasmtime 49, including the
unchanged bounded JSON service implementation. This does not certify platform
compatibility with that runtime release.

| Observation | Bounded JSON ABI | Component scalar ABI |
| --- | --- | --- |
| Echo values 0, 7, u32 maximum | Preserved in JSON object | Preserved as u32 |
| String where integer intended | Framing accepts; domain schema must reject | Python binding raises TypeError |
| Negative / overflowing Python integer | Needs domain validation | Binding wraps -1 to 4294967295 and 4294967296 to 0 |
| Python bool | Needs domain validation | Accepted as 1 |
| Infinite guest loop | Existing platform fuel mechanism | Probe traps with 100 fuel |
| Authority and identity | Existing Engine routing and snapshot checks | Not implemented by this probe |

The script asserts the observed integer conversions so later binding changes
are visible. For a domain u32 input, an adapter still needs
`type(value) is int and 0 <= value < 2**32` before calling this Python binding.
Typed ABI alone is not permission, package identity, or provenance.

The component has no imports, WASI, network or filesystem access. Its store
receives memory, instance, table and fuel limits. Only the fuel trap is exercised;
resource-limit enforcement, strings/lists/resources, generated-binding quality,
startup cost, WIT compilation, cancellation and real Engine authorization remain
unmeasured. The JSON guest only echoes framed data; it does not validate a u32
domain schema. This is an ABI observation, not an end-to-end plugin comparison.

Decision: retain the current Core ABI and runtime dependency. Next useful research
is an actual WIT build/binding pipeline plus a bounded structured payload and
authorization adapter. No evidence here warrants PersonIR/compiler expansion.

Primary API reference:
https://bytecodealliance.github.io/wasmtime-py/component/index.html
