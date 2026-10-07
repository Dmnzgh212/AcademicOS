# LifeHub platform boundaries

LifeHub is a platform engine. User interfaces are optional clients.

The dependency direction is one-way:

```text
Desktop / CLI / Web / other shells
              |
              v
        LifeHub Engine
              |
    runtime / packages / IPC
              |
         host operating system
```

The reverse dependency is forbidden.

## Hard rule

The platform path must remain usable if every optional UI shell is removed.

These modules are part of the platform path and must not import Web/UI code:

- `kernel.py`
- `engine.py`
- `daemon.py`
- `control.py`

The legacy reference Web implementation now lives under
`academicos.lifehub.shells.reference_web`. The old
`academicos.lifehub.web` module is only a compatibility shim for existing
callers and tests.

The normal `lifehub` CLI import path also does not import the Web shell.
Only the legacy `demo --serve` and `serve` commands load it lazily.

## Acceptance condition

A platform change is invalid if it requires any of the following in order to
install, resolve, start, supervise, route, authorize or stop a component:

- HTML
- CSS
- `http.server`
- workspace layout
- widget rendering
- a browser

A shell may depend on the engine. The engine may never depend on a shell.


## Presentation persistence

Workspace layout is not platform state.

The core `LifeStore` no longer creates a workspace table and exposes no
workspace layout API. The optional reference Web shell owns its layout through
`ReferenceWorkspaceStore`, which creates
`lifehub_reference_web_workspace_items` only when that shell is actually used.

For compatibility, the reference shell can import rows from the historical
`lifehub_workspace_items` table if an older database contains it. That migration
logic lives in the shell and is invisible to the Engine.

Therefore a fresh Engine database contains no widget or workspace schema.
