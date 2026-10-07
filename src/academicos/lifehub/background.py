"""Constrained persistent Wasm runner with private pipes and forced termination."""

from __future__ import annotations

import base64
import json
import queue
import subprocess
import sys
import threading

from academicos.lifehub.messages import MAX_IO_BYTES, decode_message, encode_message
from academicos.lifehub.wasm import MAX_MODULE_BYTES


class BackgroundHandle:
    def __init__(self, module, verify):
        if len(module) > MAX_MODULE_BYTES:
            raise ValueError("background module exceeds size limit")
        self.verify = verify
        self.process = subprocess.Popen(
            [sys.executable, "-I", "-m", "academicos.lifehub.background_worker"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        self.responses = queue.Queue(maxsize=1)
        self._lock = threading.Lock()

        def receive():
            try:
                while True:
                    raw = self.process.stdout.readline(MAX_IO_BYTES + 2)
                    if not raw or len(raw) > MAX_IO_BYTES + 1 or not raw.endswith(b"\n"):
                        self.responses.put(None)
                        return
                    self.responses.put(decode_message(raw[:-1]))
            except Exception:
                self.responses.put(None)

        self.reader = threading.Thread(target=receive, daemon=True)
        self.reader.start()
        try:
            bootstrap = json.dumps({"module": base64.b64encode(module).decode("ascii")})
            self.process.stdin.write(bootstrap.encode() + b"\n")
            self.process.stdin.flush()
            if self._receive() != {"ready": True}:
                raise ValueError("invalid guest readiness")
        except BaseException:
            self.stop()
            raise

    def _receive(self):
        try:
            value = self.responses.get(timeout=3)
        except queue.Empty as exc:
            self.stop()
            raise ValueError("background guest response deadline exceeded") from exc
        if value is None:
            self.stop()
            raise ValueError("background guest exited or sent invalid response")
        return value

    def call(self, request):
        raw = encode_message(request)
        with self._lock:
            self.verify()
            if self.process.poll() is not None:
                raise ValueError("background guest is no longer alive")
            try:
                self.process.stdin.write(raw + b"\n")
                self.process.stdin.flush()
                output = self._receive()
                self.verify()
                if self.process.poll() is not None:
                    raise ValueError("background guest exited before response release")
                return output
            except (OSError, PermissionError):
                self.stop()
                raise

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                stream.close()


class BackgroundWasmRunner:
    id = "lifehub.wasm-background"

    def start(self, engine, component):
        from academicos.lifehub.engine import RunnerStart, ExecutionState

        if component.requires:
            raise ValueError("background provider cannot require downstream interfaces")
        if component.contract != "lifehub.service-json@1":
            raise ValueError("background runner requires bounded JSON service contract")
        bundle = engine.kernel.bundle(component.plugin_id)
        files = engine.kernel.packages.approved_files(bundle.root, bundle.manifest)
        module = component.config.get("module")
        if not isinstance(module, str) or not module.endswith(".wasm") or module not in files:
            raise ValueError("background runner needs approved Wasm module")
        _, verify_snapshot = engine.kernel._capability_snapshot(component.plugin_id)
        def installed_identity():
            row = engine.kernel.store.conn.execute(
                "SELECT * FROM lifehub_installed_packages WHERE plugin_id=?",
                (component.plugin_id,),
            ).fetchone()
            return tuple(row) if row is not None else None
        identity = installed_identity()
        def verify():
            verify_snapshot()
            if installed_identity() != identity:
                raise PermissionError("background installation identity changed")
        handle = BackgroundHandle(files[module], verify)
        return RunnerStart(ExecutionState.RUNNING, handle=handle, ready=True)

    def stop(self, engine, component, handle):
        handle.stop()
