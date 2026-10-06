# LifeHub real-plugin validation, first pass

Core is frozen. These providers are outside `src/academicos/lifehub` and add no
host imports, capability types, runtime special cases or domain terms to Core.

| Package | Actual adapter | Records contract | Input in acceptance run |
| --- | --- | --- | --- |
| ecosystem.academic | Course/deadline CSV provider with explicit offset validation | ecosystem.academic-records@1 | Real-format synthetic export; live user export pending |
| ecosystem.rss | Offline RSS 2.0 item provider with declaration/size/row rejection | ecosystem.rss-records@1 | Real-format synthetic feed; live user feed pending |
| ecosystem.system | Minimal local OS/runtime snapshot, no hostname/process/environment data | ecosystem.system-records@1 | Live host snapshot |

Each installed provider declares read access only to its namespace, has a Wasm
record-reader entrypoint, and a bounded JSON descriptor service. An independently
installed `ecosystem.consumer` calls all three descriptor services with package-bound
guest identity. This is a real schema-information service, not a records service:
`{"operation":"describe"}` returns namespace and field metadata; other operations fail.
Data remains available only through scoped `lifehub.records@1`, not through descriptors.

## Operator collection boundary

`adapters.py` and `operator.py` are explicitly run trusted operator companions.
They parse a user-selected local file or collect the minimal system snapshot.
They are not sandboxed guest connectors and are not executed from installed ZIPs.
`--approve-ingest` is mandatory. Operator ingress uses the trusted host storage API
with `operator.ingress` provenance; this is not a guest write capability or a Shell.
Installing a provider and ingesting source data do not grant the guest read access.
There are no live Brightspace logins, RSS downloads, background jobs or hidden egress.
CSV headers are `course,title,due`, with explicit-offset ISO deadlines. RSS is a
bounded 2.0 subset: title, HTTP(S) link, optional guid/pubDate; Atom/RDF are rejected.
Each input file is capped at 1 MiB and each ingest at 100 records.

## Build and operate

With the accepted platform wheel and Wasmtime installed:

```sh
python ecosystem/lifehub/build.py /tmp/lifehub-domain-packages
lifehub review-package /tmp/lifehub-domain-packages/academic.zip
lifehub install-package /tmp/lifehub-domain-packages/academic.zip --approve-hash REVIEWED_DIGEST --db /tmp/domain.db --installed /tmp/domain-installed
python -I ecosystem/lifehub/operator.py academic --source CHOSEN_CSV --approve-ingest --db /tmp/domain.db --installed /tmp/domain-installed
lifehub run-wasm ecosystem.academic:read --db /tmp/domain.db --installed /tmp/domain-installed
```

The first run is denied. Grant `academic.deadlines` with `grant-read` explicitly,
then execute/read/export; revoke with `revoke-read` to deny access again. RSS and
system follow the same flow with `rss.items` and `system.snapshot` respectively.
Use the existing catalog and records Shells, never direct database reads in Shells.
Service grants use `review-service` and its exact digest, not install approval.

## Reproduce the common lifecycle acceptance

Use a non-editable installed-wheel interpreter outside the checkout:

```sh
/path/to/wheel-venv/bin/python -I ecosystem/lifehub/validate.py "$PWD"
```

The harness operates only in temporary storage with the shipped fixtures and a
minimal local system snapshot. Automatic approvals are only for its generated
packages. It checks review/install/catalog, denied requested capabilities,
explicit grants, Wasm/records, host and guest descriptor calls, independent Shells,
revoke on old handles, controlled tamper, uninstall, disappearance, incoming grant
removal and denied old execution. It prints per-domain JSON evidence.

This first pass validates three domain implementations and actual platform use.
It does **not** certify Brightspace integration, all feeds, a remote connector or
live academic/RSS user-data acceptance. Those are explicitly pending.
