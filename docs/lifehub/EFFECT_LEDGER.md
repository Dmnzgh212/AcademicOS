# Explicit effect requests and uncertain outcomes

> Architecture status (2026-10-03): this is **conventional host safety/recovery infrastructure**, not proof of an Effect-as-Data or PersonIR novelty claim. The useful properties are explicit staging, scope checks, separation of approval from dispatch, durable outcome state, idempotency, and conservative handling of uncertain external outcomes.


An installed core-Wasm extension may request an effect only if its approved manifest
declares the exact `kind` and `destination` pair:

```toml
[[permissions.effect_request]]
kind = "test.record"
destination = "demo.outbox"
```

The `lifehub.request_effect_json` import accepts a JSON object with exactly `kind`,
`destination`, `purpose`, and `payload`. `purpose` is a nonempty human-readable reason;
`payload` is the data proposed for disclosure. Requests are staged in memory during
execution and saved only if the module finishes successfully. Identical requests
from the same package and extension have one durable identity, including after an
uncertain outcome, so rerunning the module cannot silently send them again.

The user examines the entire request, then decides:

```bash
lifehub effects --db data/lifehub.db
lifehub approve-effect 1 --db data/lifehub.db --installed data/lifehub-installed
lifehub dispatch-fake-effect 1 --db data/lifehub.db --installed data/lifehub-installed
# or, before dispatch:
lifehub reject-effect 1 --db data/lifehub.db
```

Approval does not execute anything. It rechecks package identity and manifest scope.
Dispatch is a separate host action; this release registers only `test.record`, which
records a fake delivery in the local database. No email, payment, device, or external
network executor is available. The host marks the request `in_flight` durably before
calling the executor. A normal return marks it `succeeded`; an exception after the
call starts marks it `unknown`. A process exit can leave `in_flight`. After confirming
the old worker has stopped, the operator can run `lifehub mark-effect-unknown 1`.
Neither `unknown` nor `in_flight` is retried automatically. The ledger preserves the
request, decision, attempt and outcome for inspection. Uninstall invalidates only
pending or approved requests; an in-flight outcome remains unresolved.

This slice demonstrates the authority and recovery boundary with a fake executor.
Any future real executor needs destination validation, credential handling, delivery
receipts where available, and service-specific recovery logic before activation.
