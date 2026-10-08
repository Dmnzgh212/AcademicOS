"""Regression tests for proof-tool startup; real transport is exercised in CI smoke."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def proof():
    path = Path(__file__).resolve().parents[1] / "examples/lifehub-third-party-apps/run_demo.py"
    spec = importlib.util.spec_from_file_location("proof_startup_regression", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup_start(monkeypatch, proof, tmp_path):
    class Child:
        def poll(self):
            return None
    child = Child()
    monkeypatch.setattr(proof.subprocess, "Popen", lambda *a, **k: child)
    monkeypatch.setattr(proof.time, "sleep", lambda _: None)
    cleaned = []
    monkeypatch.setattr(proof, "stop_daemon", lambda *args: cleaned.append(args[0]))
    (tmp_path / "engine.key").write_bytes(b"")
    return child, cleaned


def test_partial_key_is_retried_before_ping(monkeypatch, proof, tmp_path):
    child, cleaned = setup_start(monkeypatch, proof, tmp_path)
    attempts = []
    def load(_):
        attempts.append(1)
        if len(attempts) == 1:
            raise ValueError("LifeHub engine auth key is too short")
        return b"x" * 32
    monkeypatch.setattr(proof, "load_authkey", load)
    monkeypatch.setattr(proof, "request", lambda *a: {"ok": True, "result": "ready"})
    assert proof.start_daemon(tmp_path, tmp_path / "db", tmp_path / "installed",
                              "endpoint", "AF_PIPE") == (child, b"x" * 32)
    assert len(attempts) == 2 and cleaned == []


def test_invalid_key_timeout_cleans_started_child(monkeypatch, proof, tmp_path):
    child, cleaned = setup_start(monkeypatch, proof, tmp_path)
    def invalid(_):
        raise ValueError("incomplete key")
    monkeypatch.setattr(proof, "load_authkey", invalid)
    with pytest.raises(TimeoutError):
        proof.start_daemon(tmp_path, tmp_path / "db", tmp_path / "installed",
                           "endpoint", "AF_PIPE")
    assert cleaned == [child]


def test_unexpected_ping_failure_cleans_child_without_retry(monkeypatch, proof, tmp_path):
    child, cleaned = setup_start(monkeypatch, proof, tmp_path)
    monkeypatch.setattr(proof, "load_authkey", lambda _: b"x" * 32)
    monkeypatch.setattr(proof, "request", lambda *a: {"ok": False, "error": "denied"})
    with pytest.raises(AssertionError, match="unexpected Engine rejection"):
        proof.start_daemon(tmp_path, tmp_path / "db", tmp_path / "installed",
                           "endpoint", "AF_PIPE")
    assert cleaned == [child]
