import json

import pytest

from academicos.lifehub.kernel import LifeHub
from test_lifehub import _write_plugin


def test_catalog_supports_alternative_shells_without_exposing_host_paths(tmp_path):
    plugins = tmp_path / "plugins"
    _write_plugin(plugins)
    hub = LifeHub(db_path=tmp_path / "hub.db", plugins_path=plugins)
    try:
        catalog = hub.catalog(point="future.capability.that-core-does-not-know")
        assert catalog["api"] == "lifehub.catalog@1"
        assert [x["ref"] for x in catalog["extensions"]] == ["demo.sample:future"]
        assert str(tmp_path) not in json.dumps(catalog)
        assert "requested_permissions" in catalog["packages"][0]
        catalog["extensions"][0]["config"]["injected"] = True
        catalog["packages"][0]["requested_permissions"]["storage_write"].append("finance")
        assert "injected" not in hub.extension("demo.sample:future").contribution.config
        with pytest.raises(PermissionError):
            hub.scoped_store("demo.sample").append("finance", "one", {})
        with pytest.raises(ValueError, match="unsupported catalog API"):
            hub.catalog(api="lifehub.catalog@2")
    finally:
        hub.close()
