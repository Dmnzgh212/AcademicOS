import pytest

from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.shells.reference_web import render_workspace
from academicos.lifehub.shells.workspace import ReferenceWorkspaceStore
from test_lifehub import _write_plugin


def _workspace(hub):
    return ReferenceWorkspaceStore(hub.store.conn)


def test_shell_reopening_preserves_saved_layout_and_workspace_isolation(tmp_path):
    root, db = tmp_path / 'plugins', tmp_path / 'hub.db'
    _write_plugin(root)
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        assert _workspace(hub).layout() == []
        render_workspace(hub, token='test')
        saved = {'extension_ref': 'demo.sample:main', 'x': 2, 'y': 9,
                 'width': 7, 'height': 6, 'visible': False, 'config': {'label': 'mine'}}
        _workspace(hub).save_layout([saved])
        expected = _workspace(hub).layout()
        render_workspace(hub, token='test')
        assert _workspace(hub).layout() == expected
        assert _workspace(hub).layout('second') == []
        render_workspace(hub, token='test', workspace_id='second')
        assert _workspace(hub).layout('second')[0]['visible'] == 1
        assert _workspace(hub).layout() == expected
    finally:
        hub.close()
    reopened = LifeHub(db_path=db, plugins_path=root)
    try:
        assert _workspace(reopened).layout() == expected
        render_workspace(reopened, token='test')
        assert _workspace(reopened).layout() == expected
    finally:
        reopened.close()


def test_shell_preparation_respects_opt_out_and_adds_new_contributions(tmp_path):
    root = tmp_path / 'plugins'
    plugin = _write_plugin(root)
    manifest = plugin / 'plugin.toml'
    manifest.write_text(manifest.read_text().replace('default_workspace = true',
                                                    'default_workspace = false'))
    hub = LifeHub(db_path=tmp_path / 'hub.db', plugins_path=root)
    try:
        render_workspace(hub, token='test')
        assert _workspace(hub).layout() == []
    finally:
        hub.close()
    _write_plugin(root, folder='new', plugin_id='demo.new', writes='new')
    hub = LifeHub(db_path=tmp_path / 'hub.db', plugins_path=root)
    try:
        assert _workspace(hub).layout() == []
        render_workspace(hub, token='test')
        assert [x['extension_ref'] for x in _workspace(hub).layout()] == ['demo.new:main']
        render_workspace(hub, token='test')
        assert len(_workspace(hub).layout()) == 1
    finally:
        hub.close()


def test_invalid_shell_config_is_visible_without_blocking_other_plugins(tmp_path):
    root = tmp_path / 'plugins'
    bad = _write_plugin(root, folder='bad', plugin_id='demo.bad', writes='bad')
    path = bad / 'plugin.toml'
    path.write_text(path.read_text().replace('width = 5', 'width = "custom"'))
    good = _write_plugin(root)
    hub = LifeHub(db_path=tmp_path / 'hub.db', plugins_path=root)
    try:
        hub.seed_declared_data()
        page = render_workspace(hub, token='test')
        assert 'Unsupported workspace layout: demo.bad:main' in page
        assert 'Local item' in page
        assert [x['extension_ref'] for x in _workspace(hub).layout()] == ['demo.sample:main']
        assert len(hub.catalog()['packages']) == 2
    finally:
        hub.close()
    path = good / 'plugin.toml'
    path.write_text(path.read_text().replace('limit = 5', 'limit = "invalid"'))
    hub = LifeHub(db_path=tmp_path / 'hub.db', plugins_path=root)
    try:
        assert 'Invalid surface record configuration' in render_workspace(hub, token='test')
    finally:
        hub.close()


@pytest.mark.parametrize('limit', [None, True, 1.5, float('inf'), '8', 0, -1, 101])
def test_invalid_surface_limit_is_rejected_before_record_access(tmp_path, monkeypatch, limit):
    from academicos.lifehub.shells.reference_web import _extension_body

    root = tmp_path / 'plugins'
    _write_plugin(root)
    hub = LifeHub(db_path=tmp_path / 'hub.db', plugins_path=root)
    try:
        extension = hub.extension('demo.sample:main')
        extension.contribution.config['limit'] = limit
        calls = []
        monkeypatch.setattr(hub, 'read_records', lambda *a, **kw: calls.append(a))
        assert 'Invalid surface record configuration' in _extension_body(hub, extension)
        assert calls == []
    finally:
        hub.close()
