# Windows Engine boundary validation

This validation slice follows the readiness/shutdown and single-manager lease work
in #48–49. It changes tests/CI/docs only; no runtime/security source changes.

Windows/Python 3.12 CI now exercises:

- exclusive manager ownership, owner process termination and reacquisition;
- real AF_PIPE wrong authentication, malformed JSON, oversized frame and disconnect,
  followed by a valid request;
- separate control clients observing a shared live runner handle and readiness;
- daemon close cooperatively stopping that runner and preserved stopped history;
- first-class Wasm interface calls, snapshot/revocation/uninstall boundaries;
- readiness transitions/recovery and cooperative shutdown failures;
- wheel build/install and isolated installed-wheel component IPC lifecycle smoke.

The two new AF_PIPE tests deliberately skip on Linux; Linux transport tests remain
unchanged. An actual Windows CI result is required, not a simulated transport.

These checks do not certify Windows service registration, native runner sandboxing,
OS ACL isolation, stalled handshake/frame deadlines, forced shutdown, background
restart/backoff, hardware access, or every Python/Windows version.

## Cumulative review notes (#48–50)

Readiness remains transient observation, never authority. The lease prevents a second
cooperating manager from changing live execution history before recovery. Cooperative
shutdown preserves failed stops without claiming processes were forcibly terminated.
The existing pure JSON provider is still one-shot computation; these changes do not
turn it into a persistent supervised service. Keep the Engine stack Draft pending
review of remaining lifecycle and WIT work.
