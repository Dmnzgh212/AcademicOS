from __future__ import annotations

import fnmatch
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from academicos.lifehub.manifest import PluginManifest
from academicos.lifehub.store import LifeStore


class EgressGateway:
    """Host-owned retrieval-only outbound gateway.

    The gateway is intentionally conservative: GET/HEAD only, no request body,
    no embedded credentials, no arbitrary query string, HTTPS for external hosts,
    and explicit manifest-declared destinations. It is a policy boundary, not a
    sandbox for arbitrary executable plugin code.
    """

    def __init__(self, store: LifeStore, manifest: PluginManifest) -> None:
        self.store = store
        self.manifest = manifest

    def authorize(self, url: str, *, method: str = "GET") -> None:
        parsed = urlparse(url)
        normalized_method = method.upper()
        host = (parsed.hostname or "").lower()
        allowed = False
        try:
            if normalized_method not in {"GET", "HEAD"}:
                raise PermissionError("LifeHub egress is retrieval-only; request bodies are not allowed")
            if parsed.username or parsed.password:
                raise PermissionError("credentials embedded in URLs are not allowed")
            if parsed.query:
                raise PermissionError(
                    "arbitrary query strings are disabled; use reviewed public parameters"
                )
            if not host:
                raise PermissionError("network request has no host")
            if host in {"127.0.0.1", "localhost", "::1"}:
                if parsed.scheme != "http":
                    raise PermissionError("localhost service access must use http")
                port = parsed.port or 80
                if port not in self.manifest.permissions.localhost_ports:
                    raise PermissionError(f"localhost port {port} is not permitted")
            else:
                if parsed.scheme != "https":
                    raise PermissionError("external network access must use https")
                if not any(
                    _host_matches(host, pattern)
                    for pattern in self.manifest.permissions.network_retrieval
                ):
                    raise PermissionError(f"host {host!r} is not allowlisted")
            allowed = True
        finally:
            self.store.network_audit(
                plugin_id=self.manifest.id,
                method=normalized_method,
                host=host,
                path=parsed.path or "/",
                allowed=allowed,
            )

    def fetch(self, url: str, *, method: str = "GET", timeout: float = 15.0) -> bytes:
        self.authorize(url, method=method)
        request = Request(url, method=method.upper(), headers={"User-Agent": "LifeHub/0.2"})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read()


def _host_matches(host: str, pattern: str) -> bool:
    normalized = pattern.strip().lower()
    if normalized.startswith("*."):
        suffix = normalized[2:]
        return host != suffix and host.endswith("." + suffix)
    return fnmatch.fnmatchcase(host, normalized)
