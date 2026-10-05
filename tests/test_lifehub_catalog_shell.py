import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
from academicos.lifehub.kernel import LifeHub
from test_lifehub import _write_plugin

SOURCE = Path(__file__).resolve().parents[1] / "examples/lifehub/catalog_shell/shell.py"


def test_independent_shell_renders_actual_catalog_and_unknown_points(tmp_path):
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    hub = LifeHub(db_path=tmp_path / "hub.db", plugins_path=plugins)
    try:
        catalog = hub.catalog()
    finally:
        hub.close()
    for style in ("text", "html"):
        result = subprocess.run(
            [sys.executable, "-I", str(SOURCE), "--style", style],
            input=json.dumps(catalog),
            text=True,
            capture_output=True,
            check=True,
        )
        assert "demo.sample:future" in result.stdout
        assert "future.capability.that-core-does-not-know" in result.stdout
        assert "sample.future" in result.stdout
        assert str(tmp_path) not in result.stdout


def test_shell_escapes_untrusted_metadata_and_rejects_wrong_version():
    spec = importlib.util.spec_from_file_location("catalog_shell", SOURCE)
    shell = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shell)
    catalog = {
        "api": "lifehub.catalog@1",
        "packages": [{"id": "x", "name": "<script>x</script>"}],
        "extensions": [{"ref": "x:escape\x1b[31m", "plugin_id": "x", "point": "unknown"}],
    }
    assert "<script>" not in shell.render(catalog, style="html")
    assert "&lt;script&gt;" in shell.render(catalog, style="html")
    assert "\x1b" not in shell.render(catalog)
    assert "\\u001b" in shell.render(catalog)
    with pytest.raises(ValueError, match="unsupported catalog"):
        shell.render({"api": "lifehub.catalog@2"})
