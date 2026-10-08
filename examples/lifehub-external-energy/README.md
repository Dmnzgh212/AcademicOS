# Independent AI integrator exercise: synthetic energy budget

**Authorship disclosure:** these two application payloads are authored in a distinct
AI integration task, without editing LifeHub Engine Core. This does **not** establish
an unrelated external human developer's authorship or fulfill that human validation
requirement. The publicly documented Engine control ABI and separately installed
wheel are used; the pre-existing author-built heartbeat demo is **not** imported
as the runnable integration.

The scenario is synthetic, not real electrical monitoring: the provider increments
a private in-memory spent-units value by **7** per idle Wasm tick, and returns
`{"spent":"000000"}` with a fixed six-digit decimal field. The consumer calls the
declared `lab.energy.spent@1` interface and independently computes
`max(0, 200 - spent)`, exposed as its Wasm i32 return. It does not access Engine
internals or accept guest-selected caller identity.

Two separately packaged applications:

- `external.energy-meter:measure`: long-running `lifehub.wasm-background`
  instance, own state, finite opt-in restart policy (2 retries / 60 s).
- `external.energy-budget:remaining`: `lifehub.wasm` one-shot service consumer,
  dependent on a specifically granted live provider route.

## Install and run

Use Python 3.11/3.12 with an **installed LifeHub wheel** built from the matching
M1 PR #61 source, and `wasmtime>=36,<37` (not an editable source checkout).
Run in a fresh isolated directory, with the examples checkout only for input WAT:

```sh
python -I examples/lifehub-external-energy/independent_proof.py --output /fresh/new/output
```

The program compiles **its own** Wasm payloads with upstream Wasmtime, creates
reproducible `.lhpkg` archives, reviews both through the **public CLI**, installs
using explicit reviewed digests, and starts a separate Engine daemon process.
Each operator control request creates and closes its own local connection. The
operator authkey is never copied into guest code or evidence.

Expected behavioral checks:
- Consumer denied before route grant.
- Approved provider starts ready; live consumer computes actual headroom.
- After every client disconnects, guest-owned internal usage increases and headroom
  decreases; the numeric budget rule comes from the app, not Engine.
- Route revoke denies the next consumer call and remains denied after actual
  Engine process termination and automatic intended-state restoration.
- Actual guest OS process termination yields a *new* execution ID after bounded
  restart, without manual `start`.
- Explicit component stop suppresses restart; uninstall while running terminates
  the live guest without a subsequent call.

Artifacts include exact two source-authored `.lhpkg` ZIPs, sha256, git/platform/
Python metadata, execution IDs, pass/fail record, sanitized Engine log and built
wheel from CI. No real user data, authkey or database is uploaded.

## Explicit limitations

This app demonstrates integration under the public **currently narrow** core-Wasm
ABI, including a fixed JSON response shape. The provider cannot emit arbitrary
complex JSON without additional Wasm guest-side formatting; consumer's fixed
six-digit parser is a test fixture, not a general JSON decoder. No real power meter,
external effects, guest state checkpointing, browser or AI model is involved.

Passing this AI-authored integration is supporting evidence that an unrelated app
can be built under the documented contracts. It is **not** a human independent
integration, a security certification, or full M1 acceptance. Any actual bug,
missing API or failure is recorded before proposing an Engine change.
