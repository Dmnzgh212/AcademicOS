# Readiness and cooperative shutdown

Running and ready are distinct. `RunnerStart.ready` defaults to false. A trusted
runner may report immediate readiness, or the trusted host may notify Engine with
`set_ready(execution_id, bool)`. A guest JSON payload cannot set it; no control
operation is added for setting readiness. Readiness never grants authority.

Readiness is live process state, not durable liveness evidence. Terminal or recovered
executions report false. Start/stop/recovery states retain the existing durable ledger.
Listing and control responses expose the same live readiness as execution lookup.

`shutdown()` attempts to stop every running handle through its registered runner,
records failures without abandoning the remaining stops, closes storage and reports
an ExceptionGroup if any runner stop failed. Daemon close uses shutdown and removes
its owned Unix socket even when a runner fails. Repeated shutdown is harmless.

`close()` remains explicitly storage-only for low-level teardown and recovery tests.
It must not be confused with graceful shutdown. Engine start refuses a closed manager.

This is cooperative host-runner lifecycle machinery. It cannot force a runner to
terminate, bound a blocking stop, certify that a process really died, or implement
restart/backoff/watchdog policies. A FAILED stop means teardown was uncertain, not
that Engine killed the workload.

Pure JSON providers in the current IPC slice remain synchronous invocations, not
long-lived instances. This readiness field does not retrofit their dispatch into a
supervised service. Dependency readiness/on-demand activation remains a separate
future slice. No Windows service or AF_PIPE certification is implied.

Tests cover not-ready running work, transitions/control visibility, terminal-state
rejection, recovery without readiness, all-runner stop attempts with failure history,
and daemon socket cleanup on successful and failed cooperative shutdown.
