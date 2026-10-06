# Local shell and extension contracts

`lifehub catalog --db PATH --plugins PATH [--point POINT]` emits
`lifehub.catalog@1` JSON. The `extensions` CLI command uses the same catalog.
The reference web shell uses it to discover visible contributions and counts;
its existing trusted local data/layout access remains separate.

Package `api = "lifehub@1"` describes manifest compatibility. An optional
contribution `contract` describes the consumer-specific entrypoint protocol:

- `lifehub.core-wasm@1` selects the existing core-Wasm ABI.
- `lifehub.primitive@1` selects the reference shell's primitive rendering format.

Consumers require an exact supported contract before executing or rendering.
Omitted contracts preserve existing version-1 behavior. A different contract is
still discoverable: unknown extension points and future consumers remain open,
but the existing consumer refuses to interpret incompatible contributions.
For example, a Wasm contribution with `contract = "lifehub.core-wasm@2"` is
listed in the catalog and rejected before guest execution.

This is exact version selection, not range negotiation, service RPC, or WIT.
Catalog metadata lists requested permissions, never effective capability grants.
It does not authenticate remote consumers, activate modules, or replace the
package digest checks and scoped host services. Use the CLI only as a trusted
local shell; no HTTP catalog endpoint is introduced.
