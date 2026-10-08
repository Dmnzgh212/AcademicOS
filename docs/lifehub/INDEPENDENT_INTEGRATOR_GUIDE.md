# Independent background application integration

This guide targets the stacked prototype at PR #59, runtime base
`9b3d47719848a6d97839c7a2b7d461e190b462de`, proof revision
`7ef4ec4308497bb14cc57576b43f17d3b6a66069`.
These features are not represented as merged main or an accepted M1 release.
M1 still requires an actual developer outside Engine implementation to perform
and report an integration. Running the author's examples is a baseline check,
not evidence of independent authorship.

## Start from an installed artifact

Download the matching wheel and recovery evidence from
[CI run 367](https://github.com/Dmnzgh212/AcademicOS/actions/runs/37707048863).
Create a disposable virtual environment with Python 3.11 or 3.12 and install:

```sh
python -m pip install /path/to/academicos-0.1.0-py3-none-any.whl 'wasmtime>=36,<37'
```

Use that environment's `python` for every command below. On Windows PowerShell,
quote the wheel path with double quotes if needed. Work in a fresh directory
outside the source checkout. No editable install, Shell server or guest-side
Python runner is required. The developer may compile a core-Wasm module using
any toolchain that emits the ABI below; WAT examples are references, not a
required source language or a WIT Component Model interface.

## Package and guest contracts

Create two separately reviewable packages: a persistent provider and a consumer
that calls it. Give them your own package IDs and document the domain payload
schema and observable background work. Keep domain rules in these packages.
A package is a ZIP archive named `.lhpkg`; the minimal layout is:

- `plugin.toml`
- `worker.wasm`

Minimal provider manifest (replace names and interface with your own):

```toml
manifest_version = 1
api = "lifehub@1"
id = "integrator.provider"
name = "Integrator Provider"
version = "1.0.0"

[[components]]
id = "service"
runner = "lifehub.wasm-background"
contract = "lifehub.service-json@1"
provides = ["integrator.status@1"]

[components.config]
module = "worker.wasm"

# Optional, explicit recovery policy. Omit this table for manual restart.
[components.config.restart]
max_retries = 2
window = 60
backoff = 0.2
max_backoff = 0.8
```

The persistent provider exports `memory` and `ready`, `tick`, `run`, each
`() -> i32`. `ready` returns 1; successful `tick` and `run` return 0. During
`run`, emit exactly one JSON response through the imports below. Guest state
must actually change on idle `tick` turns if that is your demonstrated work;
no host ledger update counts as guest work. Guest memory resets on replacement.

| Provider import | Parameters | Result |
| --- | --- | --- |
| `lifehub_service.read_request` | i32 pointer, i32 capacity | i32 bytes copied; negative required size if capacity is insufficient |
| `lifehub_service.write_response` | i32 pointer, i32 byte length | i32 byte length; duplicate/invalid response fails the execution |

Minimal consumer manifest:

```toml
manifest_version = 1
api = "lifehub@1"
id = "integrator.consumer"
name = "Integrator Consumer"
version = "1.0.0"

[[components]]
id = "observe"
runner = "lifehub.wasm"
requires = ["integrator.status@1"]

[components.config]
module = "worker.wasm"
```

Its guest exports `memory` and `run() -> i32` and calls the host import
`lifehub.call_interface_json` with six i32 values: interface UTF-8 pointer/length,
request JSON pointer/length, response pointer/capacity. Successful return is
response byte length. Route resolution and caller identity come from the host,
not a caller/provider field in JSON. Check your own response schema; the sample
observer's fixed six-digit codec is not a general JSON parser. The public control
start result exposes this consumer's bounded i32 result, not arbitrary trusted
Python runner output.

Messages are UTF-8 JSON, at most 64 KiB, with finite numbers and bounded container
nesting (64). Modules are at most 2 MiB; guest linear memory is capped at 8 MiB,
with one instance/memory and no tables. Each mediated turn gets 1,000,000 fuel.
The background runner admits only the two provider imports above: no WASI,
filesystem, network, storage or outgoing nested service imports. Do not add a
host import to make your application fit; record that limitation as friction.

## Review, install, discover and authorize

Review both archives before approval. The printed `sha256-content` is the
installer's content digest, not necessarily the SHA256 of the ZIP file itself.
Record both identities in the report and pass the reviewed content digest:

```sh
python -I -m academicos.lifehub.cli review-package provider.lhpkg
python -I -m academicos.lifehub.cli install-package provider.lhpkg --approve-hash REVIEWED_PROVIDER_CONTENT_DIGEST --db data/integration.db --installed data/integration-installed
python -I -m academicos.lifehub.cli review-package consumer.lhpkg
python -I -m academicos.lifehub.cli install-package consumer.lhpkg --approve-hash REVIEWED_CONSUMER_CONTENT_DIGEST --db data/integration.db --installed data/integration-installed
python -I -m academicos.lifehub.cli engine-serve --db data/integration.db --installed data/integration-installed --auth-file data/integration.key
```

Keep only the Engine process running. In a second terminal in the same working
directory, each CLI invocation connects briefly and disconnects:

```sh
python -I -m academicos.lifehub.cli engine-components --db data/integration.db --auth-file data/integration.key
python -I -m academicos.lifehub.cli engine-start integrator.provider:service --db data/integration.db --auth-file data/integration.key
python -I -m academicos.lifehub.cli engine-start integrator.consumer:observe --db data/integration.db --auth-file data/integration.key
```

The consumer must fail before grant. Review the exact route, inspect the result,
then pass its `approval_digest` as `--approve-hash`:

```sh
python -I -m academicos.lifehub.cli engine-route-review integrator.consumer:observe integrator.status@1 integrator.provider:service --db data/integration.db --auth-file data/integration.key
python -I -m academicos.lifehub.cli engine-route-grant integrator.consumer:observe integrator.status@1 integrator.provider:service --approve-hash REVIEWED_ROUTE_DIGEST --db data/integration.db --auth-file data/integration.key
python -I -m academicos.lifehub.cli engine-start integrator.consumer:observe --db data/integration.db --auth-file data/integration.key
python -I -m academicos.lifehub.cli engine-route-revoke integrator.consumer:observe integrator.status@1 integrator.provider:service --db data/integration.db --auth-file data/integration.key
```

Observe guest-owned work after disconnecting every client for an explicit
interval. Revoke must deny the next consumer operation. An installed package or
requested interface is not authority. Keep the authkey in operator tooling;
never put it in a package, guest memory, log or shared evidence bundle.

## Recovery and lifecycle evidence

Current CLI supports `engine-executions` and `engine-stop EXECUTION_ID`.
`desired-components`, `supervisor-health` and `stop-component` are public control
operations without dedicated CLI commands. A trusted local operator may use:

```python
from pathlib import Path
from academicos.lifehub.control import CONTROL_API, control_request
from academicos.lifehub.daemon import default_control_endpoint, load_authkey

address, family = default_control_endpoint(Path("data"))
response = control_request(
    address,
    {"api": CONTROL_API, "op": "desired-components"},
    authkey=load_authkey(Path("data/integration.key")),
    family=family,
)
print(response)
```

Use `{"api": CONTROL_API, "op": "stop-component", "ref":
"integrator.provider:service"}` to cancel pending recovery as well as stopping
its live execution. Synchronous control dispatch cannot process a second-client
revoke during an active request; do not claim instantaneous concurrent cutoff.

Run actual guest/Engine kill, finite crash-loop, stop, uninstall and identical
reinstall scenarios with your packages. Preserve new execution IDs, interrupted
history, retained revocation and old-guest termination observations. Do not call
`start` after Engine restart to stand in for automatic restoration. The reference
`run_recovery.py` is fixed to the author's sample IDs; passing it does not verify
your own packages. Adapt operator orchestration, not Engine Core, and retain
that script plus your sources and exact compiled archives.

## Independent report and friction record

Provide developer identity/role and authorship provenance, exact source revision,
wheel/package SHA256 and reviewed content digests, OS/Python, commands,
work interval and observations, execution IDs, policy, logs, failures and Core diff.
The evidence must state whether the developer participated in Engine authoring.
Do not relabel an Engine-authored example as external integration.

For every problem, record the concrete action, expected/actual outcome,
reproduction, affected contract and proposed ownership: documentation/SDK,
plugin domain logic, or a candidate generic platform mechanism. A requested Core
change needs evidence under the existing Core admission rules. Missing aggregate
process/memory ceilings and live-stall detection remain documented limits;
PersonIR and compiler work remain frozen.
