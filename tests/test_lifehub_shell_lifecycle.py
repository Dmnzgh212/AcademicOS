from academicos.lifehub.kernel import LifeHub
from academicos.lifehub.web import render_workspace
from test_lifehub import _write_plugin


def test_shell_reopening_preserves_saved_layout_and_workspace_isolation(tmp_path):
    root, db = tmp_path / 'plugins', tmp_path / 'hub.db'
    _write_plugin(root)
    hub = LifeHub(db_path=db, plugins_path=root)
    try:
        assert hub.store.workspace_layout() == []
        render_workspace(hub, token='test')
        saved = {'extension_ref': 'demo.sample:main', 'x': 2, 'y': 9,
                 'width': 7, 'height': 6, 'visible': False, 'config': {'label': 'mine'}}
        hub.store.save_workspace_layout([saved])
        expected = hub.store.workspace_layout()
        render_workspace(hub, token='test')
        assert hub.store.workspace_layout() == expected
        assert hub.store.workspace_layout('second') == []
        render_workspace(hub, token='test', workspace_id='second')
        assert hub.store.workspace_layout('second')[0]['visible'] == 1
        assert hub.store.workspace_layout() == expected
    finally:
        hub.close()
    reopened = LifeHub(db_path=db, plugins_path=root)
    try:
        assert reopened.store.workspace_layout() == expected
        render_workspace(reopened, token='test')
        assert reopened.store.workspace_layout() == expected
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
        assert hub.store.workspace_layout() == []
    finally:
        hub.close()
    _write_plugin(root, folder='new', plugin_id='demo.new', writes='new')
    hub = LifeHub(db_path=tmp_path / 'hub.db', plugins_path=root)
    try:
        assert hub.store.workspace_layout() == []
        render_workspace(hub, token='test')
        assert [x['extension_ref'] for x in hub.store.workspace_layout()] == ['demo.new:main']
        render_workspace(hub, token='test')
        assert len(hub.store.workspace_layout()) == 1
    finally:
        hub.close()
