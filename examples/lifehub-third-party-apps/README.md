# LifeHub: independent third-party software proof

This directory contains **two independently authored, installable software packages**,
not a test-only fake runner and not a Web Shell.

- `thirdparty.pricing` is a Wasm price-calculation provider. It accepts
  `{"units":7}`, calculates `7 × 3`, and returns `{"total":21}`.
- `thirdparty.checkout` is a different Wasm consumer package. It declares
  `requires = ["example.pricing@1"]`, invokes that interface through LifeHub,
  reads the returned JSON, and returns the computed total **21**.

Each has its own `plugin.toml` and Wasm source. Both packages are generated
as normal `.lhpkg` archives. Neither package adds UI contributions. **No
changes to LifeHub Core are needed to add or execute them.**

## Run on Windows / Linux / macOS

Install the current LifeHub wheel or editable checkout, including Wasmtime:

```powershell
python -m pip install -e ".[dev,wasm]"
python examples/lifehub-third-party-apps/run_demo.py
```

The demonstration creates disposable local state and:

1. compiles the independently authored WAT sources into Wasm;
2. builds two reproducible ZIP-format `.lhpkg` archives;
3. reviews and installs each archive by its exact approved digest;
4. launches **a separate LifeHub Engine daemon process** using the real local
   authenticated IPC endpoint (Windows AF_PIPE, Unix AF_UNIX);
5. verifies a denied invocation before the operator grants the interface route;
6. grants the exact reviewed provider binding;
7. invokes the checkout app; verifies the **computed** result `21`;
8. revokes the route and verifies the next invocation fails;
9. kills the disposable Engine daemon, launches a **new process**, and verifies
   that execution history persists but revoked authority does not.

No browser, HTTP server, reference Web Shell, or built-in domain-specific
checkout implementation participates.

To build the installable artifacts without running the demonstration:

```powershell
python examples/lifehub-third-party-apps/run_demo.py --build-only dist/thirdparty
python -m academicos.lifehub.cli review-package dist/thirdparty/thirdparty.pricing.lhpkg
python -m academicos.lifehub.cli review-package dist/thirdparty/thirdparty.checkout.lhpkg
```

Use `install-package --approve-hash <reviewed-sha256>` to install the reviewed
artifacts into a chosen Engine state, then use `engine-serve`, `engine-route-review`,
`engine-route-grant` and `engine-start` to operate them. The demonstration
automates these public platform operations for a reproducible acceptance run.

## What this **does not** prove

This is a **headless, real-process Engine + independent app packaging and
invocation proof**, not the full LifeHub platform milestone.

The provider is currently a bounded, synchronous, one-shot pure Wasm computation.
It is **not** an independently supervised long-lived background service.
The daemon persists across invocations, but the guest app does not remain
running continuously. No boot activation, automatic restart/backoff, streams,
asynchronous events, cancellation, WIT bindings, general native app sandbox,
Windows service registration, or production installer is demonstrated.

The tiny JSON request/response parser intentionally handles this fixed example
payload only; it is not a general JSON SDK or a production price-calculation
library. Future developer-facing SDK work should remove that low-level plumbing.

**Next decisive milestone:** install a truly long-lived third-party background
component with its own lifecycle/readiness; close every Shell; observe it
continue working, communicate through a revoked-on-next-call interface, and
recover predictably after Engine restart. Do not claim that milestone from this
example.

## Why this belongs outside Core

The two packages are standalone artifacts authored using public manifest and
Wasm interfaces. They can be replaced with unrelated software without editing
`src/academicos/lifehub`. The Engine is infrastructure; these apps are its
independent consumers.
