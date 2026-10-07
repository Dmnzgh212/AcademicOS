"""Smoke an installed platform using disposable synthetic packages and loopback HTTP."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    import academicos
    from academicos.lifehub.kernel import LifeHub
    from academicos.lifehub.shells.reference_web import make_handler

    repo = Path(sys.argv[1]).resolve()
    if Path(academicos.__file__).resolve().is_relative_to(repo):
        raise RuntimeError("requires an installed wheel, not the source checkout")
    checks = []
    with tempfile.TemporaryDirectory(prefix="lifehub-platform-smoke-") as directory:
        work = Path(directory)

        def process(args, *, success=True, input_text=None):
            result = subprocess.run([sys.executable, "-I", *map(str, args)], cwd=work,
                                    input=input_text, text=True, capture_output=True, timeout=60)
            if success and result.returncode:
                raise RuntimeError(result.stderr)
            if not success and (result.returncode == 0 or result.stdout):
                raise RuntimeError("denied operation succeeded or emitted output")
            return result.stdout

        process([repo / "scripts/lifehub_wheel_smoke.py", repo])
        checks.append("echo service and guest grant/revoke")
        archive = work / "reader.zip"
        process([repo / "examples/lifehub/reader/build.py", archive])
        db, installed = work / "hub.db", work / "installed"
        host = ["--db", db, "--plugins", installed]
        execution = ["--db", db, "--installed", installed]

        def cli(*args, success=True):
            return process(["-m", "academicos.lifehub.cli", *args], success=success)

        digest = re.search(r"sha256-content: ([0-9a-f]{64})",
                           cli("review-package", archive)).group(1)
        cli("install-package", archive, "--approve-hash", digest, *execution)
        hub = LifeHub(db_path=db, plugins_path=installed)
        try:
            hub.store.append_record(plugin_id="synthetic.producer", namespace="sample.records",
                                    record_key="smoke", payload={"message": "synthetic smoke"})
        finally:
            hub.close()
        catalog = cli("catalog", *host)
        assert json.loads(catalog)["packages"][0]["id"] == "example.reader"
        shell = repo / "examples/lifehub/catalog_shell/shell.py"
        assert "example.reader" in process([shell], input_text=catalog)
        assert "example.reader" in process([shell, "--style", "html"], input_text=catalog)
        process([shell], input_text='{"api":"unsupported"}', success=False)
        checks.append("catalog text/HTML shells and invalid-input rejection")
        cli("run-wasm", "example.reader:read", *execution, success=False)
        cli("records", "example.reader", "sample.records", *host, success=False)
        cli("grant-read", "example.reader", "sample", *host)
        assert "Result:" in cli("run-wasm", "example.reader:read", *execution)
        records = cli("records", "example.reader", "sample.records", *host)
        assert len(json.loads(records)["records"]) == 1
        rendered = process([repo / "examples/lifehub/records_shell/shell.py"], input_text=records)
        assert "synthetic smoke" in rendered
        checks.append("reader denied/granted and independent records shell")

        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            db_path=db, plugins_path=installed, token="synthetic-smoke-token"))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"

            def http(path, *, headers=None, data=None, status=200):
                request = Request(base + path, headers=headers or {}, data=data)
                try:
                    response = urlopen(request, timeout=5)  # noqa: S310
                except HTTPError as exc:
                    response = exc
                with response:
                    assert response.status == status, (path, response.status)
                    return response.read()

            assert http("/healthz") == b"ok\n"
            assert b"LifeHub" in http("/")
            assert http("/assets/app.js")
            http("/", headers={"Host": "untrusted.invalid"}, status=403)
            headers = {"Content-Type": "application/json"}
            http("/api/layout", headers=headers, data=b"[]", status=403)
            headers["X-LifeHub-Token"] = "synthetic-smoke-token"
            headers["Origin"] = "http://untrusted.invalid"
            http("/api/layout", headers=headers, data=b"[]", status=403)
            headers["Origin"] = base
            assert http("/api/layout", headers=headers, data=b"[]") == b"ok\n"
            checks.append("real loopback HTTP health/assets/page and Host/Origin/token checks")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        cli("revoke-read", "example.reader", "sample", *host)
        cli("run-wasm", "example.reader:read", *execution, success=False)
        cli("records", "example.reader", "sample.records", *host, success=False)
        cli("grant-read", "example.reader", "sample", *host)
        (installed / "example.reader" / "tampered.txt").write_text("synthetic tamper")
        cli("run-wasm", "example.reader:read", *execution, success=False)
        cli("catalog", *host, success=False)
        cli("uninstall-package", "example.reader", *execution)
        assert json.loads(cli("catalog", *host))["packages"] == []
        cli("run-wasm", "example.reader:read", *execution, success=False)
        checks.append("revoke/tamper/uninstall fail closed")
    print(json.dumps({"status": "PASS", "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
