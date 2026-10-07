# Single Engine manager ownership

Reproduced lifecycle bug: constructing a second Engine over an active database
ran recovery and marked the first manager's running executions interrupted.

Engine now acquires an exclusive transaction in a separate SQLite sidecar before
constructing the kernel or updating recovery history. Busy/locked ownership fails
closed with PermissionError. Platform data transactions remain independent.
Canonical path aliases share the lease. The sidecar is retained, not unlinked.

Storage close/shutdown releases the lease. Initialization failure also releases it.
The OS/SQLite releases the connection's lock when its process dies; a persistent
sidecar file does not itself imply a live owner. Tests kill a separate owner process
and acquire the same lease afterwards without deleting the sidecar.

This is cooperative trusted-local manager coordination, not protection against an
operator deleting/replacing files or writing directly through LifeStore. Hard-link
aliases, hostile filesystem races and network-filesystem locking guarantees are
outside this slice. Child runner processes are not magically killed when the
manager dies. Recovery still records interrupted work, not restored live handles.

Tests cover second-manager denial without live-ledger mutation, path aliases,
independent databases, process death and failed initialization. Linux full CI and
a Windows/Python 3.12 lease-only CI job validate these cases. The Windows job does
not certify AF_PIPE, background providers, Windows service installation or the
complete Engine milestone.
