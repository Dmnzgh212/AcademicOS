from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.network import EgressGateway
from academicos.lifehub.store import LifeStore


@pytest.mark.parametrize("status", [200, 301, 302, 303, 307, 308])
def test_fetch_never_follows_redirects(status):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(status if self.path == "/start" else 200)
            if status != 200 and self.path == "/start":
                # Even an otherwise permitted destination must be requested separately.
                self.send_header("Location", "/target")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    store = LifeStore(":memory:")
    try:
        manifest = PluginManifest.model_validate({
            "id": "test.egress", "name": "Egress", "version": "1.0.0",
            "permissions": {"localhost_ports": [server.server_port]},
        })
        gateway = EgressGateway(store, manifest)
        url = f"http://127.0.0.1:{server.server_port}/start"
        if status == 200:
            assert gateway.fetch(url) == b"ok"
        else:
            with pytest.raises(PermissionError, match="automatic redirects"):
                gateway.fetch(url)
        assert requests == ["/start"]
        assert gateway.fetch(f"http://127.0.0.1:{server.server_port}/target") == b"ok"
        assert requests == ["/start", "/target"]
    finally:
        store.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
