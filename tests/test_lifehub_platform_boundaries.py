from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_engine_import_graph_does_not_load_reference_web_shell() -> None:
    code = r"""
import sys
import academicos.lifehub.engine
import academicos.lifehub.daemon
import academicos.lifehub.control
import academicos.lifehub.kernel

assert "academicos.lifehub.web" not in sys.modules
assert "academicos.lifehub.shells.reference_web" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_platform_modules_do_not_import_shell_modules() -> None:
    root = Path(__file__).parents[1] / "src" / "academicos" / "lifehub"
    for name in ("engine.py", "daemon.py", "control.py", "kernel.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "academicos.lifehub.web" not in source
        assert "academicos.lifehub.shells" not in source


def test_legacy_web_module_is_only_a_compatibility_shim() -> None:
    root = Path(__file__).parents[1] / "src" / "academicos" / "lifehub"
    source = (root / "web.py").read_text(encoding="utf-8")
    assert "shells.reference_web" in source
    assert "ThreadingHTTPServer" not in source
    assert "CSS = " not in source


def test_platform_store_has_no_workspace_schema_or_api(tmp_path) -> None:
    from academicos.lifehub.store import LifeStore

    store = LifeStore(tmp_path / "platform.db")
    try:
        tables = {
            row[0]
            for row in store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "lifehub_workspace_items" not in tables
        assert "lifehub_reference_web_workspace_items" not in tables
        assert not hasattr(store, "workspace_layout")
        assert not hasattr(store, "save_workspace_layout")
        assert not hasattr(store, "sync_workspace_extensions")
    finally:
        store.close()
