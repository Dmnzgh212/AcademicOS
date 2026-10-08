"""Build two real third-party .lhpkg apps and exercise a separate Engine daemon.

No LifeHub Core edits, Web Shell, synthetic Python runner, or test-only manifests.
The Wasm apps are independently authored source files in this directory.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import uuid4
import zipfile

import wasmtime

from academicos.lifehub.control import CONTROL_API, control_request
from academicos.lifehub.daemon import load_authkey
from academicos.lifehub.packages import PackageInstaller
from academicos.lifehub.store import LifeStore

HERE = Path(__file__).resolve().parent
APPS = (
    ("thirdparty.pricing", "pricing"),
    ("thirdparty.checkout", "checkout"),
)
INTERFACE = "example.pricing@1"
CONSUMER = "thirdparty.checkout:calculate"
PROVIDER = "thirdparty.pricing:calculate"


def build_packages(output: Path) -> tuple[Path, ...]:
    """Produce reproducible, standalone, inspectable third-party packages."""
    output.mkdir(parents=True, exist_ok=True)
    archives = []
    for package_id, stem in APPS:
        manifest = (HERE / stem / "plugin.toml").read_bytes()
        module = wasmtime.wat2wasm((HERE / f"{stem}.wat").read_text(encoding="utf-8"))
        archive = output / f"{package_id}.lhpkg"
        with zipfile.ZipFile(archive, "w") as package:
            for filename, data in (("plugin.toml", manifest), ("worker.wasm", module)):
                entry = zipfile.ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_STORED
                entry.external_attr = 0o644 << 16
                package.writestr(entry, data)
        archives.append(archive)
    return tuple(archives)


def install_packages(db: Path, installed: Path, archives: tuple[Path, ...]) -> None:
    """Use the ordinary reviewed-digest installer, not a private test bypass."""
    store = LifeStore(db)
    try:
        installer = PackageInstaller(installed, store)
        for archive in archives:
            review = installer.review(archive)
            installer.install(archive, approved_hash=review.content_hash)
            print(f"INSTALLED {review.manifest.id} sha256={review.content_hash}")
    finally:
        store.close()


def endpoint_for(root: Path) -> tuple[str, str]:
    if os.name == "nt":
        return (rf"\\.\pipe\lifehub-thirdparty-{uuid4().hex}", "AF_PIPE")
    return (str(root / "engine.sock"), "AF_UNIX")


def request(address: str, family: str, authkey: bytes, op: str, **fields):
    return control_request(
        address,
        {"api": CONTROL_API, "op": op, **fields},
        authkey=authkey,
        family=family,
    )


def require_ok(response: dict):
    if response.get("ok") is not True:
        raise AssertionError(f"unexpected Engine rejection: {response!r}")
    return response["result"]


def require_denied(response: dict) -> None:
    if response.get("ok") is not False:
        raise AssertionError(f"unauthorized component call succeeded: {response!r}")
    if response.get("error", {}).get("type") not in {"PermissionError", "KeyError"}:
        raise AssertionError(f"wrong denial reason: {response!r}")


def start_daemon(
    root: Path, db: Path, installed: Path, address: str, family: str
) -> tuple[subprocess.Popen, bytes]:
    auth_file = root / "engine.key"
    log = root / "engine.log"
    with log.open("ab") as output:
        process = subprocess.Popen(
            [
                sys.executable, "-I", "-m", "academicos.lifehub.cli",
                "engine-serve",
                "--db", str(db),
                "--installed", str(installed),
                "--endpoint", address,
                "--auth-file", str(auth_file),
            ],
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=root,
        )
    try:
        for _ in range(200):
            if process.poll() is not None:
                raise RuntimeError(
                    f"Engine daemon exited early ({process.returncode}); see {log}"
                )
            if auth_file.is_file():
                # Creation precedes writing: a new file may still be incomplete.
                # Only this disposable startup polls invalid/unfinished keys;
                # runtime authentication continues to reject them.
                try:
                    key = load_authkey(auth_file)
                except (ValueError, OSError):
                    time.sleep(0.05)
                    continue
                try:
                    require_ok(request(address, family, key, "ping"))
                    return process, key
                except (ConnectionError, OSError, EOFError):
                    pass
            time.sleep(0.05)
        raise TimeoutError(f"Engine daemon did not become ready; see {log}")
    except BaseException:
        stop_daemon(process, address, family)
        raise


def stop_daemon(process: subprocess.Popen, address: str, family: str) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    # This socket belongs to this disposable proof's own terminated process.
    # Never unlink a socket from an unknown or running Engine.
    if family == "AF_UNIX":
        Path(address).unlink(missing_ok=True)


def prove(root: Path) -> None:
    db = root / "engine.db"
    installed = root / "installed"
    archives = build_packages(root / "packages")
    install_packages(db, installed, archives)
    address, family = endpoint_for(root)

    process, key = start_daemon(root, db, installed, address, family)
    try:
        components = require_ok(request(address, family, key, "components"))
        assert {component["ref"] for component in components} == {CONSUMER, PROVIDER}
        assert all(component["point"] is None for component in components)
        require_denied(request(address, family, key, "start", ref=CONSUMER))

        review = require_ok(
            request(
                address, family, key, "route-review",
                consumer=CONSUMER, interface=INTERFACE, provider=PROVIDER,
            )
        )
        require_ok(
            request(
                address, family, key, "route-grant",
                consumer=CONSUMER, interface=INTERFACE, provider=PROVIDER,
                approval_digest=review["approval_digest"],
            )
        )
        execution = require_ok(request(address, family, key, "start", ref=CONSUMER))
        assert execution["state"] == "completed", execution
        assert execution["result"] == 21, execution
        print("PASS: independent checkout calls pricing provider: 7 units x 3 = 21")

        require_ok(
            request(
                address, family, key, "route-revoke",
                consumer=CONSUMER, interface=INTERFACE, provider=PROVIDER,
            )
        )
        require_denied(request(address, family, key, "start", ref=CONSUMER))
        print("PASS: revoke denies the next invocation")
    finally:
        stop_daemon(process, address, family)

    # A new Engine process must retain history but must not resurrect authority.
    process, key = start_daemon(root, db, installed, address, family)
    try:
        rows = require_ok(request(address, family, key, "executions", limit=100))
        assert any(
            row["execution_id"] == execution["execution_id"]
            and row["state"] == "completed"
            for row in rows
        )
        require_denied(request(address, family, key, "start", ref=CONSUMER))
        print("PASS: new Engine process retains history, not revoked authority")
    finally:
        stop_daemon(process, address, family)

    assert "academicos.lifehub.shells.reference_web" not in sys.modules
    print(json.dumps({
        "status": "PASS",
        "platform": sys.platform,
        "apps": [name for name, _ in APPS],
        "calculated_total": 21,
        "real_daemon_process": True,
        "browser_required": False,
        "persistent_guest_service": False,
    }))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-only", type=Path, metavar="OUTPUT_DIR")
    args = parser.parse_args()
    if args.build_only is not None:
        for archive in build_packages(args.build_only):
            print(archive)
        return
    with TemporaryDirectory(prefix="lifehub-third-party-proof-") as temp:
        prove(Path(temp))


if __name__ == "__main__":
    main()
