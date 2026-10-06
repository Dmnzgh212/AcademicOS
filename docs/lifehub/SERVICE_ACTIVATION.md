# Service activation v1

This slice provides explicit, trusted-host activation of installed core-Wasm
services. It is not yet guest-to-guest RPC, input/output transport, or a WIT ABI.

A provider declares a contribution with `point = "lifehub.service"`,
`entrypoint = "lifehub.wasm"`, `contract = "lifehub.core-wasm@1"`, and an
approved module path. A caller requests exact contribution refs in
`permissions.service_call`. The existing catalog discovers those contributions.

Trusted host code calls `grant_service(caller_id, ref, contract)` after a local
user decision, `activate_service(...)` to invoke, and `revoke_service(...)` to
remove authority. No guest import or HTTP endpoint exposes these methods.
Caller IDs must be derived from authenticated execution context if a future
bridge is added; accepting an ID supplied in guest JSON would be unsafe.

The grant binds exact ref, contract, caller package digest and provider package
digest. Each use verifies both installed packages and checks an exact grant;
namespace-prefix matching is not used for service authority. Package changes
require a new matching grant. Uninstall removes outgoing and incoming service
grants, preventing reinstall from silently restoring activation authority.

Provider execution uses the provider's own capabilities, fuel/memory limits and
staged proposal/effect services. Activation does not give the caller read access
to provider records. However, activation can trigger any behavior permitted to
the provider: granting service activation is authority to start that module,
not proof it is pure or that it cannot read sensitive data. User-facing grant
review must therefore show provider permissions before exposing this API in a
shell. The return value is only the existing run-status integer; no service
payload or protected result channel is implemented.

The threat boundary remains approved package verification with same-user
filesystem races outside current guarantees. This slice does not implement
shared transaction semantics, delegation, recursive service calls, or automatic
activation.

## Local CLI review

`lifehub review-service CALLER REF CONTRACT --db DB --installed PACKAGES`
prints `lifehub.service-review@1` JSON with both package digests, provider
requested permissions, current exact grant status, and an approval digest.
It does not grant or execute. Use the returned digest with
`lifehub grant-service CALLER REF CONTRACT --approve-hash DIGEST` (same DB/root).
A stale digest is rejected if either approved package changed. The trusted
in-process grant API can still be used by host code without a review digest;
the CLI requires one. Requested permissions shown in review are not a list of
currently effective storage grants.

`lifehub revoke-service CALLER REF CONTRACT` (same DB/root) removes all matching
bindings, including stale ones. Activation itself remains an in-process host API
in this slice. This CLI is a trusted local administrative surface; caller IDs
entered by the local operator are not authenticated guest identities.

## Reviewed grant binding

When an approval digest is supplied, grant_service hashes the exact caller and
binding it will persist, rather than validating a separately regenerated review.
A changed binding rejects the approval and writes no service grant. This closes
a two-lookup consistency gap; it does not prove atomicity against every concurrent
package or grant update. Later activation still checks current snapshots.
