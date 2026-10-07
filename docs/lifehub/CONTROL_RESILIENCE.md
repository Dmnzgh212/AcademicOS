# Local Engine control resilience

The trusted local operator control channel remains separate from component IPC.
Messages use the existing finite JSON, depth and 64 KiB bounds; no pickle decoding.

Authentication failure or handshake disconnect rejects that client. Invalid UTF-8,
malformed JSON, oversized frames and disconnected clients close the connection.
The server accepts subsequent clients. Oversized/unserializable responses return
a small bounded error. Listener failures and unexpected controller failures still
propagate; they are not hidden in an infinite retry loop.

Tests cover these failures followed by a successful request, plus a real AF_UNIX
sequence of wrong authentication, malformed JSON, oversized frame, disconnect and
valid ping. Windows AF_PIPE requires separate validation.

This slice does **not** claim complete denial-of-service isolation: authentication
handshakes and incomplete frames still use blocking multiprocessing connection
operations. There is no per-client deadline, concurrency or rate limit yet. The
endpoint is a trusted local operator API, never a guest component transport.

The cumulative audit at PR #44 passed remote CI run 346 (259 tests, Python 3.11
and 3.12 plus wheel/platform/examples gates). This slice adds ten tests.
