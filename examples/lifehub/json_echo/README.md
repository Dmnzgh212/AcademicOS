# JSON service CLI round trip

This example builds two packages: an echo computation service and a client
manifest and core-Wasm module requesting that exact service. The client module
uses a host-mediated guest service call bound to its installed package identity.

After installing `.[dev,wasm]`, from the repository root:

```sh
python examples/lifehub/json_echo/build.py /tmp/lifehub-echo
lifehub review-package /tmp/lifehub-echo/provider.zip
lifehub review-package /tmp/lifehub-echo/caller.zip
lifehub install-package /tmp/lifehub-echo/provider.zip --approve-hash PROVIDER_DIGEST --db /tmp/echo.db --installed /tmp/echo-installed
lifehub install-package /tmp/lifehub-echo/caller.zip --approve-hash CALLER_DIGEST --db /tmp/echo.db --installed /tmp/echo-installed
lifehub catalog --point lifehub.service --db /tmp/echo.db --plugins /tmp/echo-installed
lifehub review-service example.client example.echo:echo lifehub.service-json@1 --db /tmp/echo.db --installed /tmp/echo-installed
lifehub grant-service example.client example.echo:echo lifehub.service-json@1 --approve-hash SERVICE_REVIEW_DIGEST --db /tmp/echo.db --installed /tmp/echo-installed
```

Replace the package digests with the review-package output and the service digest
with `approval_digest` from review-service. Create a UTF-8 request file containing
`{"text":"hello","value":42}`, then call:

```sh
lifehub call-service example.client example.echo:echo --request /tmp/request.json --db /tmp/echo.db --installed /tmp/echo-installed
lifehub revoke-service example.client example.echo:echo lifehub.service-json@1 --db /tmp/echo.db --installed /tmp/echo-installed
```

The response is the same JSON value. Before revoking, you can also run the Wasm
client:

```sh
lifehub run-wasm example.client:invoke --db /tmp/echo.db --installed /tmp/echo-installed
```

It sends `{"message":"hello from Wasm"}` to the echo service and returns its
response byte length (29). Both call routes fail after revocation.
The CLI reads at most 64 KiB plus one byte to detect oversized files, rejects
nonfinite/invalid JSON, and emits a response only after successful authorized
execution. Input data is explicitly disclosed to the chosen provider by the
trusted local operator. No filesystem/network/storage/effect guest import is
available to this service profile. No request or response is persisted.

`tests/test_lifehub_echo_cli.py` builds these actual files and exercises installation,
review, grant, call, oversized/nonfinite input rejection, and revocation through
the CLI, including the executable Wasm client. The user-supplied caller ID in this CLI remains a trusted administrative
choice; it must not be copied into a future untrusted guest API.
